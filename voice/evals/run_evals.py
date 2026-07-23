"""Legally AI Voice regression eval suite (context doc §6). Run before every deploy:

    python -m evals.run_evals             # everything available
    python -m evals.run_evals --suite latency

Suites:
    grounding    LLM+RAG: tool must be called; no case named that wasn't retrieved
    refusal      out-of-corpus questions must be hedged, never guessed
    context      multi-turn pronoun references must survive the turn boundary
    interruption barge-in state bookkeeping (§4.2) — pure unit checks, always runs
    repair       transcript repair rules (§4.3) — pure unit checks, always runs
    instrumentation  telemetry observer fills every stage (§3) — synthetic
                 frames, no services, always runs
    latency      P50/P95 per stage from telemetry vs the §3 budget

Suites needing external services (Groq key / RAG endpoint) SKIP with a clear
message instead of failing when those aren't reachable, so the deterministic
suites still gate a deploy anywhere. Exit code 1 on any FAIL.
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from server.config import get_settings  # noqa: E402
from server.llm.dialog_state import DialogState  # noqa: E402
from server.llm.transcript_repair import repair  # noqa: E402
from server.telemetry.turns import load_records  # noqa: E402

CASES_DIR = Path(__file__).resolve().parent / "cases"

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


def _load(name: str):
    return yaml.safe_load((CASES_DIR / name).read_text(encoding="utf-8"))


class Reporter:
    def __init__(self) -> None:
        self.results: list[tuple[str, str, str]] = []

    def add(self, suite: str, case_id: str, status: str, note: str = "") -> None:
        self.results.append((suite, case_id, status))
        print(f"  [{status}] {suite}/{case_id}" + (f" — {note}" if note else ""))

    @property
    def failed(self) -> bool:
        return any(status == FAIL for _, _, status in self.results)

    def summary(self) -> str:
        counts = {s: sum(1 for _, _, st in self.results if st == s) for s in (PASS, FAIL, SKIP)}
        return f"{counts[PASS]} passed, {counts[FAIL]} failed, {counts[SKIP]} skipped"


async def _services_available() -> tuple[bool, str]:
    s = get_settings()
    if not s.groq_api_key:
        return False, "GROQ_API_KEY not set"
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{s.rag_base_url}/api/health")
            resp.raise_for_status()
    except Exception as e:  # noqa: BLE001
        return False, f"RAG service unreachable at {s.rag_base_url} ({e})"
    return True, ""


# ── Suites ───────────────────────────────────────────────────
async def run_grounding(r: Reporter) -> None:
    ok, why = await _services_available()
    if not ok:
        r.add("grounding", "*", SKIP, why)
        return
    from evals.agent_harness import AgentHarness

    for case in _load("grounding.yaml"):
        h = AgentHarness()
        answer = (await h.turn(case["question"])).lower()
        problems = []
        if case.get("expect_tool_call") and not h.tool_queries:
            problems.append("legal_search was never called")
        if not any(m.lower() in answer for m in case["must_mention_any"]):
            problems.append(f"answer mentions none of {case['must_mention_any']}")
        # Hallucinated citations: case names spoken but never retrieved.
        retrieved_names = " ".join(
            f"{c.get('case_name','')} {c.get('citation','')}" for c in h.retrieved
        ).lower()
        for token in ("air ", " scc ", "vs.", " v. "):
            if token in answer and token not in retrieved_names and not h.retrieved:
                problems.append(f"citation-like text {token!r} with empty retrieval")
        r.add("grounding", case["id"], FAIL if problems else PASS, "; ".join(problems))


async def run_refusal(r: Reporter) -> None:
    ok, why = await _services_available()
    if not ok:
        r.add("refusal", "*", SKIP, why)
        return
    from evals.agent_harness import AgentHarness

    data = _load("refusal.yaml")
    hedge_markers = [m.lower() for m in data["hedge_markers"]]
    over_markers = [m.lower() for m in data["overconfidence_markers"]]

    for case in data["cases"]:
        h = AgentHarness()
        answer = (await h.turn(case["question"])).lower()
        problems = []
        if not any(m in answer for m in hedge_markers):
            problems.append("no hedge/refusal marker in answer")
        hits = [m for m in over_markers if m in answer]
        if hits:
            problems.append(f"overconfident language: {hits}")
        r.add("refusal", case["id"], FAIL if problems else PASS, "; ".join(problems))


async def run_context(r: Reporter) -> None:
    ok, why = await _services_available()
    if not ok:
        r.add("context", "*", SKIP, why)
        return
    from evals.agent_harness import AgentHarness

    for case in _load("context.yaml"):
        h = AgentHarness()
        for t in case["turns"]:
            answer = await h.turn(t)
        carriers = " ".join([*h.tool_queries[1:], answer]).lower()
        carried = any(m.lower() in carriers for m in case["followup_must_carry_any"])
        r.add(
            "context", case["id"], PASS if carried else FAIL,
            "" if carried else f"follow-up carried none of {case['followup_must_carry_any']}",
        )


def run_interruption(r: Reporter) -> None:
    """Deterministic §4.2 checks on the state bookkeeping itself."""
    state = DialogState(session_id="eval")
    full = "Aapko pehle ek legal notice bhejna hoga. Uske baad 15 din ka time milta hai. Phir court ja sakte hain."
    delivered = len("Aapko pehle ek legal notice bhejna hoga.")
    state.note_interruption(full, delivered)
    tail_ok = "15 din" in state.undelivered_tail and "court" in state.undelivered_tail
    r.add("interruption", "tail-recorded", PASS if tail_ok else FAIL,
          "" if tail_ok else f"tail was {state.undelivered_tail!r}")

    rendered = state.render()
    prompt_ok = "did NOT hear" in rendered and "15 din" in rendered
    r.add("interruption", "tail-in-prompt", PASS if prompt_ok else FAIL)

    state.clear_undelivered()
    cleared = state.undelivered_tail == "" and "did NOT hear" not in state.render()
    r.add("interruption", "tail-cleared-after-delivery", PASS if cleared else FAIL)


def run_repair(r: Reporter) -> None:
    """Deterministic §4.3 checks: spoken legal terms normalize correctly.

    Assertions are on the WHOLE repaired string, not a substring. A substring
    check passes on "Section 138ka case" — which is how a rewrite rule that
    swallowed the trailing space went unnoticed while feeding glued text
    straight to retrieval.
    """
    cases = [
        ("section one thirty eight ka case hai", "Section 138 ka case hai"),
        ("section one three eight NI act", "Section 138 NI Act"),
        ("dhara four twenty ka matter", "Section 420 ka matter"),
        ("mujhe anticipatory bell chahiye", "mujhe anticipatory bail chahiye"),
        ("check bounce ho gaya", "cheque bounce ho gaya"),
        ("article 21 violation", "Article 21 violation"),
        # Articles are as retrieval-critical as sections.
        ("article twenty one violation", "Article 21 violation"),
        ("anuchhed fourteen ke under", "Article 14 ke under"),
        # "fourteen" must not degrade to "four" + stranded "teen": the number-word
        # alternation is first-match-wins, so it has to be longest-first.
        ("section fourteen notice", "Section 14 notice"),
        ("section nineteen ka provision", "Section 19 ka provision"),
        # A sub-clause letter must survive without eating the following space.
        ("section 138a notice bheja", "Section 138A notice bheja"),
        ("section 138 notice", "Section 138 notice"),
    ]
    for spoken, expected in cases:
        got = repair(spoken)
        ok = got.strip().lower() == expected.strip().lower()
        r.add("repair", spoken[:30], PASS if ok else FAIL,
              "" if ok else f"got {got!r}, wanted {expected!r}")


def _pctl(sorted_values: list[int], q: float) -> int:
    """Nearest-rank percentile on an already-sorted list (matches the HUD's
    aggregation closely enough for a regression gate)."""
    return sorted_values[min(len(sorted_values) - 1, int(q * (len(sorted_values) - 1)))]


def run_latency(r: Reporter) -> None:
    """Regress every measured stage against its §3 budget, not just e2e — the
    doc's rule is 'optimize the worst stage, not the total' (§3.4), which needs
    per-stage P95, and a green e2e can still hide one stage eating the whole
    budget while another is near-free."""
    s = get_settings()
    records = [rec for rec in load_records() if rec.get("e2e_ms", -1) >= 0]
    if len(records) < 5:
        r.add("latency", "*", SKIP, f"only {len(records)} measured turns in telemetry (need 5)")
        return
    # Per-stage P95 ceilings (§3 table). tool_ms is intentionally not budgeted
    # here — the spoken ack overlaps the RAG round-trip (§3.2), so it sits
    # outside the perceived-latency chain.
    for stage, budget in s.stage_p95_budget_ms.items():
        values = sorted(rec[stage] for rec in records if rec.get(stage, -1) >= 0)
        if not values:
            r.add("latency", f"{stage}", SKIP, "no measured turns for this stage")
            continue
        p50, p95 = _pctl(values, 0.50), _pctl(values, 0.95)
        r.add("latency", f"{stage}-p95", PASS if p95 <= budget else FAIL,
              f"p50={p50}ms p95={p95}ms vs {budget}ms budget ({len(values)} turns)")
    # The headline goal (§3) is an e2e *P50* target — check it alongside the
    # per-stage P95 ceilings above.
    e2e = sorted(rec["e2e_ms"] for rec in records)
    p50 = _pctl(e2e, 0.50)
    r.add("latency", "e2e-p50", PASS if p50 <= s.latency_p50_target_ms else FAIL,
          f"{p50}ms vs {s.latency_p50_target_ms}ms target ({len(e2e)} turns)")


async def _drive_one_turn(hub, observer) -> None:
    """Push one full turn's worth of synthetic frames through the observer, in
    pipeline order, with tiny real sleeps so the wall-clock stages (endpoint,
    tool, e2e) land as positive integers rather than the -1 'unmeasured'
    sentinel. The TTFB stages are exact from the injected metric values."""
    import time as _time

    from pipecat.frames.frames import (
        BotStartedSpeakingFrame,
        FunctionCallInProgressFrame,
        FunctionCallResultFrame,
        MetricsFrame,
        UserStoppedSpeakingFrame,
        VADUserStoppedSpeakingFrame,
    )
    from pipecat.metrics.metrics import TTFBMetricsData
    from pipecat.observers.base_observer import FramePushed
    from pipecat.processors.frame_processor import FrameDirection

    async def push(frame) -> None:
        # The observer only reads data.frame; the rest are structural.
        await observer.on_push_frame(
            FramePushed(None, None, frame, FrameDirection.DOWNSTREAM, _time.time())
        )

    def ttfb(processor: str, seconds: float):
        return MetricsFrame(data=[TTFBMetricsData(processor=processor, value=seconds)])

    await push(VADUserStoppedSpeakingFrame())
    await asyncio.sleep(0.005)
    await push(UserStoppedSpeakingFrame())  # → endpoint_ms
    # Realistic processor names on purpose: "deepgramsttservice" contains BOTH
    # "stt" and "tts" as substrings, so this exercises the observer's ordering
    # guard (stt must be tested before tts).
    await push(ttfb("DeepgramSTTService", 0.30))  # → stt_final_ms = 300
    await push(ttfb("GroqLLMService", 0.25))       # → llm_first_ms = 250
    await push(FunctionCallInProgressFrame("legal_search", "call-1", {"query": "x"}))
    await asyncio.sleep(0.005)
    await push(FunctionCallResultFrame("legal_search", "call-1", {"query": "x"}, {"ok": True}))
    await push(ttfb("EdgeTTSService", 0.15))       # → tts_first_ms = 150
    await asyncio.sleep(0.005)
    await push(BotStartedSpeakingFrame())          # → e2e_ms


async def run_instrumentation(r: Reporter) -> None:
    """Offline proof that the telemetry observer actually populates every stage.

    The instrument-first mandate (§3.4) is only worth anything if the instrument
    itself is correct — but the observer had no coverage, so a Pipecat frame
    rename or a mis-wired stage would surface only mid-live-call. This drives
    synthetic frames through the *real* TurnTelemetryObserver and asserts each
    TurnRecord stage fills, the record persists to JSONL, and summary() computes
    P50/P95. Deterministic — always runs, no keys or services needed.
    """
    import tempfile
    from pathlib import Path as _Path

    from server.pipeline.session import SessionHub
    from server.telemetry.observer import TurnTelemetryObserver
    from server.telemetry.turns import TurnLog, load_records

    with tempfile.TemporaryDirectory() as tmp:
        turn_log = TurnLog(telemetry_dir=tmp)
        hub = SessionHub("instr-test", turn_log)
        observer = TurnTelemetryObserver(hub)

        hub.user_final("mera security deposit wapas nahi mil raha")  # opens turn 1
        await _drive_one_turn(hub, observer)
        rec = hub.record

        # 1. TTFB-derived stages are exact (also proves stt/tts ordering guard).
        exact = {"stt_final_ms": 300, "llm_first_ms": 250, "tts_first_ms": 150}
        for stage, want in exact.items():
            got = getattr(rec, stage)
            r.add("instrumentation", stage, PASS if got == want else FAIL,
                  f"{got}ms (expected {want}ms)")

        # 2. Wall-clock stages are populated (default -1 means the observer never
        #    wired that frame — the exact failure this suite exists to catch).
        for stage in ("endpoint_ms", "e2e_ms"):
            got = getattr(rec, stage)
            r.add("instrumentation", stage, PASS if got >= 0 else FAIL,
                  f"{got}ms (must be >=0 = measured)")
        r.add("instrumentation", "tool_ms", PASS if rec.tool_ms > 0 else FAIL,
              f"{rec.tool_ms}ms (FunctionCall frames wired)")

        # 3. Closing the turn persists exactly one JSONL record with e2e set.
        hub.agent_text_generated("Aap deposit ke liye notice bhej sakte hain.")
        hub.agent_finished()
        persisted = load_records(tmp)
        ok = len(persisted) == 1 and persisted[0].get("e2e_ms", -1) >= 0
        r.add("instrumentation", "jsonl-persist", PASS if ok else FAIL,
              f"{len(persisted)} record(s) written")

        # 4. summary() aggregates the stage into P50/P95 for the HUD + eval.
        summ = turn_log.summary()
        s_ok = summ["turns"] == 1 and "e2e_ms" in summ["stages"] \
            and "stt_final_ms" in summ["stages"]
        r.add("instrumentation", "summary-p50p95", PASS if s_ok else FAIL,
              f"stages={sorted(summ['stages'])}")


SUITES = {
    "grounding": run_grounding,
    "refusal": run_refusal,
    "context": run_context,
    "interruption": run_interruption,
    "repair": run_repair,
    "instrumentation": run_instrumentation,
    "latency": run_latency,
}


async def main() -> int:
    parser = argparse.ArgumentParser(description="Legally AI Voice eval suite")
    parser.add_argument("--suite", choices=sorted(SUITES), help="run one suite only")
    args = parser.parse_args()

    r = Reporter()
    for name, fn in SUITES.items():
        if args.suite and name != args.suite:
            continue
        print(f"\n== {name} ==")
        result = fn(r)
        if asyncio.iscoroutine(result):
            await result

    print(f"\n{r.summary()}")
    return 1 if r.failed else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
