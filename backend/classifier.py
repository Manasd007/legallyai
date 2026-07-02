"""Optional PredEx-trained InLegalBERT win/lose classifier (brief §10).

This is the calibrated 3rd signal for the ensemble. Weights are produced OFFLINE
by pipeline/finetune_encoder.py on free GPU and dropped into
config.classifier_model_path. Until then this module reports `available: False`
and the ensemble simply runs on the other two signals — nothing breaks.

Why keep a trained classifier at all: an LLM's stated confidence is poorly
calibrated; a model trained on real Granted/Dismissed labels gives a probability
you can actually trust and benchmark against PredEx.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from config import get_settings

log = logging.getLogger("legally.classifier")


@lru_cache
def _load():
    s = get_settings()
    # Prefer local weights (dev); else fall back to the Hub repo (prod), where
    # transformers downloads + caches them. Absent both → ensemble runs on 2 signals.
    local = Path(s.classifier_model_path)
    if local.exists():
        source, kwargs = str(local), {}
    elif s.classifier_repo:
        source, kwargs = s.classifier_repo, {"revision": s.classifier_revision}
    else:
        log.info(
            "No classifier locally (%s) and no CLASSIFIER_REPO/HF_NAMESPACE set "
            "— ensemble runs without it.", local
        )
        return None
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        tok = AutoTokenizer.from_pretrained(source, **kwargs)
        model = AutoModelForSequenceClassification.from_pretrained(source, **kwargs)
        model.eval()
        log.info("Loaded PredEx classifier from %s", source)
        return tok, model, torch
    except Exception as e:  # noqa: BLE001
        log.error("Failed to load classifier (%s); continuing without it.", e)
        return None


def predict_win(text: str) -> dict:
    """Return P(applicant wins) in [0,1], or available=False if no model."""
    bundle = _load()
    if bundle is None:
        return {"available": False, "win_probability": None}
    tok, model, torch = bundle
    enc = tok(text, truncation=True, max_length=512, return_tensors="pt")
    with torch.no_grad():
        logits = model(**enc).logits
        # Convention: class index 1 == "win" (Appeal granted / applicant prevails).
        prob = torch.softmax(logits, dim=-1)[0, 1].item()
    return {"available": True, "win_probability": round(float(prob), 3)}
