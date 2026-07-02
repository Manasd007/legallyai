"""Evaluate the trained win/lose classifier on a held-out PredEx test split.

Produces the benchmark-comparable numbers for the project: accuracy, macro-F1,
per-class precision/recall/F1, and a confusion matrix. Metrics are computed by
hand (numpy only) so there is no scikit-learn dependency.

The classifier was fine-tuned on the PredEx `text` column (class 1 = applicant
wins). We evaluate on the held-out test split of the same column so the number is
a fair, leakage-free estimate.

Usage (local CPU or Colab GPU):
  python evaluate_classifier.py --limit 500          # quick representative read
  python evaluate_classifier.py                      # full test split
"""
from __future__ import annotations

import os

# transformers can pull in OpenMP; keep it from clashing on Windows.
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import argparse
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = ROOT / "data" / "models" / "predex_inlegalbert"

# Reuse the SAME label-normalisation vocabulary as training so 0/1/accepted/etc.
# all map consistently.
WIN_TOKENS = {"1", "accepted", "allowed", "granted", "win", "won", "yes", "true"}
LOSE_TOKENS = {"0", "rejected", "dismissed", "denied", "lose", "lost", "no", "false"}


def _normalize_label(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if value == 1:
            return 1
        if value == 0:
            return 0
        return None
    s = str(value).strip().lower()
    if s in WIN_TOKENS:
        return 1
    if s in LOSE_TOKENS:
        return 0
    return None


def _metrics(gold: np.ndarray, pred: np.ndarray) -> dict:
    """Accuracy, per-class precision/recall/F1, macro-F1, confusion matrix."""
    cm = np.zeros((2, 2), dtype=int)  # rows = gold, cols = pred
    for g, p in zip(gold, pred):
        cm[g, p] += 1

    acc = float((gold == pred).mean())
    per_class = {}
    f1s = []
    for c in (0, 1):
        tp = cm[c, c]
        fp = cm[1 - c, c]
        fn = cm[c, 1 - c]
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        per_class[c] = {"precision": prec, "recall": rec, "f1": f1, "support": int(cm[c].sum())}
        f1s.append(f1)

    return {
        "accuracy": acc,
        "macro_f1": float(np.mean(f1s)),
        "per_class": per_class,
        "confusion": cm,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate the win/lose classifier.")
    ap.add_argument("--dataset", default="L-NLProc/PredEx_Instruction-Tuning_Prediction")
    ap.add_argument("--split", default="test")
    ap.add_argument("--text-col", default="text")
    ap.add_argument("--label-col", default="Label")
    ap.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    ap.add_argument("--limit", type=int, default=0, help="0 = full split")
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--max-length", type=int, default=512)
    args = ap.parse_args()

    import torch
    from datasets import load_dataset
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    if not args.model.exists():
        raise SystemExit(f"Model not found at {args.model}. Train it first (finetune_encoder.py).")

    print(f"Loading test split: {args.dataset} [{args.split}]")
    # Stream when limited so huge/gated test splits aren't fully downloaded.
    stream = bool(args.limit)
    ds = load_dataset(args.dataset, split=args.split, streaming=stream)
    if stream:
        try:
            ds = ds.shuffle(seed=42, buffer_size=10000)
        except Exception:
            pass

    texts, golds = [], []
    for row in ds:
        lbl = _normalize_label(row.get(args.label_col))
        txt = row.get(args.text_col)
        if lbl is None or not txt:
            continue
        texts.append(str(txt))
        golds.append(lbl)
        if args.limit and len(texts) >= args.limit:
            break

    n = len(texts)
    pos = sum(golds)
    print(f"Evaluating {n} examples (gold positives={pos} / negatives={n - pos})")
    if n == 0:
        raise SystemExit("No labelled rows found — check --text-col/--label-col.")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    tok = AutoTokenizer.from_pretrained(str(args.model))
    model = AutoModelForSequenceClassification.from_pretrained(str(args.model)).to(device).eval()

    preds = np.empty(n, dtype=int)
    with torch.no_grad():
        for i in range(0, n, args.batch_size):
            batch = texts[i : i + args.batch_size]
            enc = tok(
                batch, padding=True, truncation=True,
                max_length=args.max_length, return_tensors="pt",
            ).to(device)
            logits = model(**enc).logits
            preds[i : i + len(batch)] = logits.argmax(-1).cpu().numpy()
            done = min(i + args.batch_size, n)
            print(f"  {done}/{n}", end="\r", flush=True)
    print()

    m = _metrics(np.array(golds), preds)
    cm = m["confusion"]

    print("\n================ Win/Lose Classifier — Test Results ================")
    print(f"Dataset      : {args.dataset} [{args.split}]  (n={n})")
    print(f"Accuracy     : {m['accuracy']:.4f}")
    print(f"Macro-F1     : {m['macro_f1']:.4f}   (PredEx encoder band ~0.55-0.63)")
    print("\nPer class:")
    for c, name in ((0, "lose (0)"), (1, "win  (1)")):
        pc = m["per_class"][c]
        print(f"  {name}: P={pc['precision']:.3f}  R={pc['recall']:.3f}  "
              f"F1={pc['f1']:.3f}  support={pc['support']}")
    print("\nConfusion matrix (rows=gold, cols=pred):")
    print("            pred:lose  pred:win")
    print(f"  gold:lose   {cm[0,0]:>7}   {cm[0,1]:>7}")
    print(f"  gold:win    {cm[1,0]:>7}   {cm[1,1]:>7}")
    print("===================================================================")


if __name__ == "__main__":
    main()
