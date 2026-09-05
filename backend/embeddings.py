from __future__ import annotations

import threading

import numpy as np

from config import get_settings

_MODEL_LOCK = threading.Lock()
_MODEL_CACHE: tuple | None = None


def _load_model():
    global _MODEL_CACHE
    if _MODEL_CACHE is not None:
        return _MODEL_CACHE
    with _MODEL_LOCK:
        if _MODEL_CACHE is not None:
            return _MODEL_CACHE
        import torch
        from transformers import AutoModel, AutoTokenizer

        name = get_settings().embedding_model
        tokenizer = AutoTokenizer.from_pretrained(name)
        model = AutoModel.from_pretrained(name)
        model.eval()
        _MODEL_CACHE = (tokenizer, model, torch)
    return _MODEL_CACHE


def _mean_pool(last_hidden_state, attention_mask, torch):
    mask = attention_mask.unsqueeze(-1).type_as(last_hidden_state)
    summed = (last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


def embed_texts(texts: list[str], batch_size: int = 16) -> np.ndarray:
    tokenizer, model, torch = _load_model()
    out: list[np.ndarray] = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            enc = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=512,
                return_tensors="pt",
            )
            hidden = model(**enc).last_hidden_state
            pooled = _mean_pool(hidden, enc["attention_mask"], torch)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            out.append(pooled.cpu().numpy().astype("float32"))
    return np.vstack(out) if out else np.empty((0, get_settings().embedding_dim), "float32")


def embed_query(text: str) -> np.ndarray:
    return embed_texts([text])[0]
