"""Per-turn latency telemetry (context doc §3: "instrument first, optimize
second").

Every conversational turn produces one TurnRecord with per-stage timings:

    endpoint_ms   user stopped speaking → final transcript ready
    llm_first_ms  transcript ready → first LLM token
    tool_ms       legal_search round-trip (0 when no tool call)
    tts_first_ms  first sentence ready → first audio byte
    e2e_ms        user stopped speaking → agent audio starts (the number users feel)

Records are appended to a JSONL file per session and aggregated on demand into
P50/P95 per stage for the dashboard and the latency regression eval (§6.6).
"""
from __future__ import annotations

import json
import logging
import statistics
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from server.config import get_settings

log = logging.getLogger("legallyai.voice.telemetry")

STAGES = ("endpoint_ms", "stt_final_ms", "llm_first_ms", "tool_ms", "tts_first_ms", "e2e_ms")


@dataclass
class TurnRecord:
    session_id: str
    turn_index: int
    started_at: float = field(default_factory=time.time)
    user_text: str = ""
    agent_text: str = ""
    interrupted: bool = False
    delivered_chars: int = 0  # how much of agent_text was actually heard (§4.2)
    tool_called: bool = False
    tool_query: str = ""
    weak_retrieval: bool = False
    # Stage timings (ms). -1 = not measured this turn.
    endpoint_ms: int = -1
    stt_final_ms: int = -1
    llm_first_ms: int = -1
    tool_ms: int = 0
    tts_first_ms: int = -1
    e2e_ms: int = -1

    def to_dict(self) -> dict:
        return asdict(self)


class TurnLog:
    """Append-only JSONL sink + in-memory aggregation for one server process."""

    def __init__(self, telemetry_dir: str | None = None) -> None:
        self._dir = Path(telemetry_dir or get_settings().telemetry_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._records: list[TurnRecord] = []

    def append(self, record: TurnRecord) -> None:
        self._records.append(record)
        path = self._dir / f"{record.session_id}.jsonl"
        try:
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
        except OSError as e:  # telemetry must never break the call
            log.warning("Could not persist turn record: %s", e)
        log.info(
            "turn %d [%s]: e2e=%dms endpoint=%dms llm_first=%dms tool=%dms tts_first=%dms%s",
            record.turn_index, record.session_id[:8], record.e2e_ms, record.endpoint_ms,
            record.llm_first_ms, record.tool_ms, record.tts_first_ms,
            " INTERRUPTED" if record.interrupted else "",
        )

    def summary(self) -> dict:
        """P50/P95 per stage over this process's turns (dashboard endpoint)."""
        out: dict = {"turns": len(self._records), "stages": {}}
        for stage in STAGES:
            values = [getattr(r, stage) for r in self._records if getattr(r, stage) >= 0]
            if not values:
                continue
            out["stages"][stage] = {
                "p50": int(statistics.median(values)),
                "p95": int(_p95(values)),
                "n": len(values),
            }
        s = get_settings()
        e2e = out["stages"].get("e2e_ms")
        # None (unknown) until there is data — a budget can't pass vacuously.
        out["within_budget"] = (
            e2e["p50"] <= s.latency_p50_target_ms and e2e["p95"] <= s.latency_p95_target_ms
            if e2e
            else None
        )
        return out


def _p95(values: list[int]) -> float:
    if len(values) == 1:
        return float(values[0])
    values = sorted(values)
    k = 0.95 * (len(values) - 1)
    lo, hi = int(k), min(int(k) + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (k - lo)


def load_records(telemetry_dir: str | None = None) -> list[dict]:
    """Read every persisted turn record (used by the latency regression eval)."""
    d = Path(telemetry_dir or get_settings().telemetry_dir)
    records: list[dict] = []
    for path in sorted(d.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    log.warning("Skipping corrupt telemetry line in %s", path.name)
    return records
