from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

from config import get_settings

log = logging.getLogger("legally.classifier")


@lru_cache
def _load():
    s = get_settings()
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
    bundle = _load()
    if bundle is None:
        return {"available": False, "win_probability": None}
    tok, model, torch = bundle
    enc = tok(text, truncation=True, max_length=512, return_tensors="pt")
    with torch.no_grad():
        logits = model(**enc).logits
        prob = torch.softmax(logits, dim=-1)[0, 1].item()
    return {"available": True, "win_probability": round(float(prob), 3)}
