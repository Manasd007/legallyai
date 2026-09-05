from __future__ import annotations

import argparse
import os
import random

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import ensemble as ensemble_mod
import retrieval as retrieval_mod
from config import get_settings

_QUERY_ROLES = ("Facts", "Issues", "Body", "Arguments")


def _prefix(chunk_id: str) -> str:
    return chunk_id.rsplit(":", 1)[0] if ":" in chunk_id else chunk_id


def build_gold(meta, n: int, seed: int = 13) -> list[dict]:
    by_case: dict[str, list[int]] = {}
    for i, cid in enumerate(meta["id"].astype(str).tolist()):
        by_case.setdefault(_prefix(cid), []).append(i)

    gold = []
    for prefix, rows in by_case.items():
        if len(rows) < 2:
            continue
        label = ensemble_mod.outcome_to_label(str(meta.iloc[rows[0]].get("outcome", "")))
        if label is None:
            continue
        cand = [r for r in rows if str(meta.iloc[r].get("segment_role", "")) in _QUERY_ROLES] or rows
        qrow = max(cand, key=lambda r: len(str(meta.iloc[r].get("chunk_text", ""))))
        text = str(meta.iloc[qrow].get("chunk_text", "")).strip()
        if len(text) < 120:
            continue
        gold.append({"query": text[:1500], "target": prefix, "label": label, "qrow": qrow})

    random.Random(seed).shuffle(gold)
    return gold[:n]


def _set_variant(mode: str, rerank: bool) -> None:
    s = get_settings()
    s.retrieval_mode = mode
    s.rerank_enabled = rerank
    retrieval_mod.rerank._load.cache_clear()


def eval_retrieval(gold: list[dict], variants: dict[str, tuple[str, bool]], top_k: int = 10) -> None:
    print(f"\n=== Retrieval quality ({len(gold)} queries, Recall@k / MRR) ===")
    for name, (mode, rr) in variants.items():
        _set_variant(mode, rr)
        hit5 = hit10 = 0
        rr_sum = 0.0
        for g in gold:
            res = retrieval_mod.retrieve(g["query"], g["query"], top_k=top_k)
            ranks = [j for j, c in enumerate(res.chunks)
                     if _prefix(c.chunk_id) == g["target"] and c.chunk_id != g["_qid"]]
            if ranks:
                r0 = ranks[0]
                rr_sum += 1.0 / (r0 + 1)
                hit5 += r0 < 5
                hit10 += r0 < 10
        nq = len(gold)
        print(f"  {name:16} R@5={hit5/nq:.3f}  R@10={hit10/nq:.3f}  MRR={rr_sum/nq:.3f}")


def eval_outcome(meta, gold: list[dict], top_k: int = 15, keep: int = 5) -> None:
    _set_variant("hybrid", True)
    applicable = 0
    cm = {0: {0: 0, 1: 0}, 1: {0: 0, 1: 0}}
    for g in gold:
        res = retrieval_mod.retrieve(g["query"], g["query"], top_k=top_k)
        res.chunks = [c for c in res.chunks if _prefix(c.chunk_id) != g["target"]][:keep]
        vote = ensemble_mod.precedent_vote(res)
        if vote.get("win_probability") is None:
            continue
        applicable += 1
        pred = 1 if vote["win_probability"] >= 0.5 else 0
        cm[g["label"]][pred] += 1

    print("\n=== Outcome prediction (leave-one-case-out, precedent vote) ===")
    if not applicable:
        print("  no scorable cases")
        return
    tp, fn = cm[1][1], cm[1][0]
    tn, fp = cm[0][0], cm[0][1]
    acc = (tp + tn) / applicable
    pos, neg = tp + fn, tn + fp
    baseline = max(pos, neg) / applicable
    rec_win = tp / pos if pos else 0.0
    rec_lose = tn / neg if neg else 0.0
    bal_acc = (rec_win + rec_lose) / 2
    print(f"  cases scored: {applicable}/{len(gold)}  (won={pos}, lost={neg})")
    print(f"  confusion  won->won={tp} won->lost={fn} | lost->lost={tn} lost->won={fp}")
    print(f"  accuracy={acc:.3f}  (majority-class baseline={baseline:.3f})")
    print(f"  recall  won={rec_win:.3f}  lost={rec_lose:.3f}  |  balanced-acc={bal_acc:.3f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=40, help="number of gold cases to sample")
    ap.add_argument("--skip-outcome", action="store_true")
    ap.add_argument("--only-outcome", action="store_true", help="skip the retrieval A/B loop")
    args = ap.parse_args()

    _, meta = retrieval_mod._load_index()
    retrieval_mod.lexical._build()
    gold = build_gold(meta, args.n)
    for g in gold:
        g["_qid"] = str(meta.iloc[g["qrow"]].get("id", ""))
    print(f"Gold set: {len(gold)} decided cases "
          f"({sum(g['label'] for g in gold)} won / {sum(1 for g in gold if g['label']==0)} lost)")

    if not args.only_outcome:
        variants = {
            "dense-only": ("dense", False),
            "hybrid": ("hybrid", False),
            "hybrid+rerank": ("hybrid", True),
        }
        eval_retrieval(gold, variants)
    if not args.skip_outcome:
        eval_outcome(meta, gold)


if __name__ == "__main__":
    main()
