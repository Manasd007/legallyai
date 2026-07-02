"""Optional Phase — fine-tune InLegalBERT on PredEx for win/lose (brief §10).

Produces the calibrated 3rd signal of the ensemble (backend/ensemble.py). Trains
a 2-class sequence classifier (class 1 = applicant WINS / Appeal granted; class 0
= dismissed) and saves weights to data/models/predex_inlegalbert/, which
backend/classifier.py loads automatically (config CLASSIFIER_MODEL_PATH).

Run OFFLINE on free GPU (Colab/Kaggle). Example in Colab:
    !pip install -r pipeline/requirements.txt datasets
    !python pipeline/finetune_encoder.py --dataset <verified_predex_id> \
        --text-col <col> --label-col <col> --epochs 3

DATA SOURCE — VERIFY BEFORE RUNNING:
  PredEx is the L-NLProc collection on Hugging Face (huggingface.co/L-NLProc)
  and github.com/ShubhamKumarNigam/PredEx (ACL 2024 Findings). The exact dataset
  id and column names vary across the collection's splits, so pass them via
  --dataset / --text-col / --label-col, OR point --local-train at a CSV/JSON you
  downloaded from the GitHub repo. The script auto-detects columns if you omit
  them, but always sanity-check the printed label distribution.

Why a trained classifier at all: an LLM's stated confidence is poorly calibrated;
a model trained on real Granted/Dismissed labels yields a trustworthy probability
and is benchmarkable against the PredEx test split (~0.78 macro-F1 ceiling).
"""
from __future__ import annotations

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import argparse
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("finetune_encoder")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "models" / "predex_inlegalbert"

# Heuristics for auto-detecting columns when not provided.
TEXT_COL_HINTS = ["text", "input", "case", "facts", "judgment", "context", "body"]
LABEL_COL_HINTS = ["label", "outcome", "decision", "verdict", "target", "y"]

WIN_TOKENS = ("allow", "grant", "accept", "win", "1", "favour", "favor")
LOSE_TOKENS = ("dismiss", "reject", "deny", "lose", "loss", "0", "against")


def _normalize_label(value) -> int | None:
    """Map a raw label (str/int) to 1 (win) / 0 (loss) / None (drop)."""
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        v = int(value)
        return v if v in (0, 1) else None
    s = str(value).strip().lower()
    if any(t in s for t in WIN_TOKENS):
        return 1
    if any(t in s for t in LOSE_TOKENS):
        return 0
    return None


def _pick_col(columns: list[str], hints: list[str], exclude: set[str]) -> str | None:
    cols = [c for c in columns if c not in exclude]
    for hint in hints:
        for c in cols:
            if hint in c.lower():
                return c
    return None


def _stream_balanced(args):
    """Stream a (gated/huge) HF dataset and collect up to --limit rows, balanced
    by class when --label-col is known. Avoids downloading millions of rows."""
    import pandas as pd
    from datasets import load_dataset  # type: ignore

    ds = load_dataset(args.dataset, split=args.split, streaming=True)
    try:
        ds = ds.shuffle(seed=42, buffer_size=10000)
    except Exception:  # noqa: BLE001 - some streams don't support shuffle
        pass

    label_col = args.label_col
    target = args.limit
    half = target / 2 if label_col else target
    max_scan = max(target * 50, 50000)
    rows, per, scanned = [], {0: 0, 1: 0}, 0

    for ex in ds:
        scanned += 1
        if scanned > max_scan:
            break
        if label_col is not None:
            lbl = _normalize_label(ex.get(label_col))
            if lbl is None:
                continue
            if per[lbl] >= half:
                if per[0] >= half and per[1] >= half:
                    break
                continue
            per[lbl] += 1
        rows.append(ex)
        if len(rows) >= target:
            break

    log.info("Streamed %d rows (scanned %d) from %s", len(rows), scanned, args.dataset)
    return pd.DataFrame(rows)


def _load_frame(args):
    """Return a pandas DataFrame from HF datasets or a local CSV/JSON."""
    import pandas as pd

    if args.local_train:
        p = Path(args.local_train)
        if p.suffix in (".json", ".jsonl"):
            return pd.read_json(p, lines=p.suffix == ".jsonl")
        return pd.read_csv(p)
    if args.limit and args.limit > 0:
        return _stream_balanced(args)
    from datasets import load_dataset  # type: ignore

    ds = load_dataset(args.dataset, split=args.split)
    return ds.to_pandas()


def main() -> None:
    ap = argparse.ArgumentParser(description="Fine-tune InLegalBERT on PredEx (win/lose).")
    ap.add_argument("--dataset", default="L-NLProc/PredEx", help="HF dataset id (VERIFY)")
    ap.add_argument("--split", default="train")
    ap.add_argument("--limit", type=int, default=0,
                    help="subsample to N rows (balanced) via streaming; 0 = use full split")
    ap.add_argument("--local-train", default=None, help="CSV/JSON path instead of HF")
    ap.add_argument("--text-col", default=None, help="auto-detected if omitted")
    ap.add_argument("--label-col", default=None, help="auto-detected if omitted")
    ap.add_argument("--model", default="law-ai/InLegalBERT")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--max-length", type=int, default=512)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    import numpy as np
    import torch
    from sklearn.metrics import accuracy_score, f1_score
    from transformers import (
        AutoModelForSequenceClassification,
        AutoTokenizer,
        Trainer,
        TrainingArguments,
    )

    df = _load_frame(args)
    log.info("Loaded %d rows; columns: %s", len(df), list(df.columns))

    text_col = args.text_col or _pick_col(list(df.columns), TEXT_COL_HINTS, set())
    label_col = args.label_col or _pick_col(list(df.columns), LABEL_COL_HINTS, {text_col})
    if not text_col or not label_col:
        raise SystemExit(
            f"Could not detect columns (text={text_col}, label={label_col}). "
            "Pass --text-col / --label-col explicitly."
        )
    log.info("Using text_col=%r, label_col=%r", text_col, label_col)

    df = df[[text_col, label_col]].copy()
    df["label"] = df[label_col].map(_normalize_label)
    before = len(df)
    df = df.dropna(subset=["label", text_col])
    df["label"] = df["label"].astype(int)
    log.info("Kept %d/%d rows with a clear binary label", len(df), before)
    log.info("Label distribution:\n%s", df["label"].value_counts().to_string())
    if df["label"].nunique() < 2:
        raise SystemExit("Only one class present after normalization — check --label-col.")

    # Stratified-ish split (90/10).
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    n_val = max(1, int(len(df) * 0.1))
    val_df, train_df = df.iloc[:n_val], df.iloc[n_val:]

    tok = AutoTokenizer.from_pretrained(args.model)

    def _encode(frame):
        enc = tok(
            list(frame[text_col].astype(str)),
            truncation=True,
            max_length=args.max_length,
            padding="max_length",
        )
        enc["labels"] = list(frame["label"])
        return enc

    class DS(torch.utils.data.Dataset):
        def __init__(self, enc):
            self.enc = enc

        def __len__(self):
            return len(self.enc["labels"])

        def __getitem__(self, i):
            return {k: torch.tensor(v[i]) for k, v in self.enc.items()}

    train_ds, val_ds = DS(_encode(train_df)), DS(_encode(val_df))

    model = AutoModelForSequenceClassification.from_pretrained(args.model, num_labels=2)

    def _metrics(pred):
        preds = np.argmax(pred.predictions, axis=1)
        return {
            "accuracy": accuracy_score(pred.label_ids, preds),
            "macro_f1": f1_score(pred.label_ids, preds, average="macro"),
        }

    targs = TrainingArguments(
        output_dir=str(args.out / "_checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size,
        learning_rate=args.lr,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        logging_steps=50,
        report_to=[],
    )
    trainer = Trainer(
        model=model,
        args=targs,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        compute_metrics=_metrics,
    )
    trainer.train()
    log.info("Final eval: %s", trainer.evaluate())

    args.out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.out)
    tok.save_pretrained(args.out)
    log.info("Saved classifier -> %s (class 1 = applicant wins)", args.out)
    log.info("Drop this folder into the backend host at the same path and restart.")


if __name__ == "__main__":
    main()
