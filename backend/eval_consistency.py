"""Run-to-run consistency harness for the full legal-prediction pipeline.

The user-facing complaint this measures: "the same question gives different
answers each run." This runs the *whole* pipeline (reformulate -> retrieve ->
predict_validated -> ensemble -> coherence guard) N times per question and
reports how much the verdict, confidence, and win probability move.

It calls ``main.compute_legal_prediction`` directly, so it bypasses the answer
cache (which would make exact repeats trivially identical) and exercises the
exact logic the /api/query route uses. Retrieval is pinned by the reformulation
cache after the first run, so residual variance here is the reasoning layer's —
which is what Phases 1-3 aimed to contain. Pass --clear-cache to also re-roll
the reformulation each run and measure the full, uncached variance.

Usage:
    python eval_consistency.py                 # default questions, 3 runs each
    python eval_consistency.py --runs 5
    python eval_consistency.py --questions my_questions.txt
    python eval_consistency.py --clear-cache   # measure variance incl. reformulation
"""

from __future__ import annotations

import argparse
import os
import statistics
from collections import Counter

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

DEFAULT_QUESTIONS = [
    "The trial court rejected my suit for specific performance of an agreement to sell land. Should I appeal?",
    "My employer dismissed me without holding any disciplinary inquiry. Can I challenge the termination?",
    "I was convicted based only on the testimony of a single eyewitness with no other evidence. What are my chances on appeal?",
    "The bank classified my loan as a non-performing asset and invoked SARFAESI without a proper notice. Can I get relief?",
    "A cheque I issued bounced and the payee filed a complaint under section 138. I had already paid the debt in cash. Will I be acquitted?",
    "The High Court quashed the FIR against the accused in my complaint. Should the State appeal to the Supreme Court?",
]


def _one_run(question: str) -> dict:
    import main as main_mod

    resp, _ = main_mod.compute_legal_prediction(question)
    return {
        "outcome": resp.get("likely_outcome"),
        "confidence": resp.get("confidence"),
        "win_probability": resp.get("win_probability"),
        "win_label": resp.get("win_label"),
        "abstained": resp.get("win_probability") is None,
    }


def _summarize(question: str, runs: list[dict]) -> dict:
    outcomes = [r["outcome"] for r in runs]
    confs = [r["confidence"] for r in runs]
    probs = [r["win_probability"] for r in runs if r["win_probability"] is not None]
    abstains = [r["abstained"] for r in runs]

    outcome_stable = len(set(outcomes)) == 1
    conf_stable = len(set(confs)) == 1
    abstain_stable = len(set(abstains)) == 1
    prob_spread = (max(probs) - min(probs)) if len(probs) >= 2 else 0.0
    prob_std = statistics.pstdev(probs) if len(probs) >= 2 else 0.0

    modal_outcome, modal_n = Counter(outcomes).most_common(1)[0]
    return {
        "question": question,
        "n_runs": len(runs),
        "outcomes": outcomes,
        "confidences": confs,
        "probs": probs,
        "modal_outcome": modal_outcome,
        "modal_agreement": modal_n / len(runs),
        "outcome_stable": outcome_stable,
        "conf_stable": conf_stable,
        "abstain_stable": abstain_stable,
        "prob_spread": prob_spread,
        "prob_std": prob_std,
    }


def run(questions: list[str], n_runs: int, clear_cache: bool) -> list[dict]:
    import cache

    summaries = []
    for q in questions:
        runs = []
        for i in range(n_runs):
            if clear_cache:
                cache.clear()
            try:
                runs.append(_one_run(q))
            except Exception as e:  # noqa: BLE001
                print(f"  ! run {i + 1} failed: {e}")
        if runs:
            summaries.append(_summarize(q, runs))
    return summaries


def _report(summaries: list[dict]) -> None:
    print("\n=== Per-question consistency ===")
    for s in summaries:
        flips = len(set(s["outcomes"])) - 1
        print(f"\nQ: {s['question'][:80]}{'…' if len(s['question']) > 80 else ''}")
        print(
            f"   outcomes={s['outcomes']}  (modal '{s['modal_outcome']}' "
            f"{s['modal_agreement']*100:.0f}% of runs, {flips} flip(s))"
        )
        print(f"   confidence={s['confidences']}  {'STABLE' if s['conf_stable'] else 'VARIES'}")
        if s["probs"]:
            print(
                f"   win%={[round(p*100) for p in s['probs']]}  "
                f"spread={s['prob_spread']*100:.0f}pts  std={s['prob_std']*100:.1f}pts"
            )
        else:
            print("   win%=abstained on all runs")
        if not s["abstain_stable"]:
            print("   ! abstention INCONSISTENT (some runs showed a number, some did not)")

    if not summaries:
        print("(no scorable questions)")
        return

    n = len(summaries)
    outcome_stability = sum(s["outcome_stable"] for s in summaries) / n
    conf_stability = sum(s["conf_stable"] for s in summaries) / n
    abstain_stability = sum(s["abstain_stable"] for s in summaries) / n
    spreads = [s["prob_spread"] for s in summaries if s["probs"]]
    mean_spread = statistics.mean(spreads) if spreads else 0.0

    print("\n=== Aggregate (higher stability = more consistent) ===")
    print(f"  questions:                 {n}")
    print(f"  outcome stability:         {outcome_stability*100:.0f}%  (verdict identical across all runs)")
    print(f"  confidence stability:      {conf_stability*100:.0f}%")
    print(f"  abstention stability:      {abstain_stability*100:.0f}%  (N/A-vs-number consistent)")
    print(f"  mean win% spread:          {mean_spread*100:.0f} pts  (across runs, where a number was shown)")


def _load_questions(path: str | None) -> list[str]:
    if not path:
        return DEFAULT_QUESTIONS
    with open(path, encoding="utf-8") as f:
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", type=int, default=3, help="runs per question (default 3)")
    ap.add_argument("--questions", type=str, default=None, help="file with one question per line")
    ap.add_argument(
        "--clear-cache",
        action="store_true",
        help="clear the reformulation cache before each run (measures full variance)",
    )
    args = ap.parse_args()

    questions = _load_questions(args.questions)
    print(f"Consistency eval: {len(questions)} questions x {args.runs} runs"
          f"{' (cache cleared each run)' if args.clear_cache else ''}")
    summaries = run(questions, args.runs, args.clear_cache)
    _report(summaries)


if __name__ == "__main__":
    main()
