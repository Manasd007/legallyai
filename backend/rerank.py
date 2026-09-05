from __future__ import annotations

import logging
from functools import lru_cache

from config import get_settings

log = logging.getLogger("legally.rerank")


@lru_cache(maxsize=1)
def _load():
    s = get_settings()
    if not s.rerank_enabled:
        return None
    source = s.reranker_repo or s.reranker_model
    try:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer

        tok = AutoTokenizer.from_pretrained(source, revision=s.reranker_revision)
        model = AutoModelForSequenceClassification.from_pretrained(source, revision=s.reranker_revision)
        model.eval()
        log.info("Loaded cross-encoder reranker from %s", source)
        return tok, model, torch
    except Exception as e:  # noqa: BLE001 - rerank is best-effort
        log.error("Failed to load reranker (%s); keeping hybrid order.", e)
        return None


def available() -> bool:
    return _load() is not None


def score_pairs(query: str, texts: list[str], batch_size: int = 16) -> list[float] | None:
    bundle = _load()
    if bundle is None or not texts:
        return None
    tok, model, torch = bundle
    scores: list[float] = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            enc = tok(
                [query] * len(batch),
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            logits = model(**enc).logits
            col = logits[:, 0] if logits.shape[-1] == 1 else logits[:, -1]
            scores.extend(col.tolist())
    return scores
