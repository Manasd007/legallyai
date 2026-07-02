"""Query embedding with InLegalBERT (brief §4, §5).

The same model and pooling MUST be used here at runtime and offline in
pipeline/chunk_embed.py, or query/index vectors won't be comparable.

InLegalBERT is a BERT encoder (no pooled sentence head), so we mean-pool the
last hidden states over the attention mask and L2-normalize, which makes inner
product equivalent to cosine similarity for FAISS.
"""
from __future__ import annotations

from functools import lru_cache

import numpy as np

from config import get_settings


@lru_cache
def _load_model():
    # Imported lazily so the API process / tooling can start without torch
    # installed (e.g. when only inspecting config).
    import torch
    from transformers import AutoModel, AutoTokenizer

    name = get_settings().embedding_model
    tokenizer = AutoTokenizer.from_pretrained(name)
    model = AutoModel.from_pretrained(name)
    model.eval()
    return tokenizer, model, torch


def _mean_pool(last_hidden_state, attention_mask, torch):
    mask = attention_mask.unsqueeze(-1).type_as(last_hidden_state)
    summed = (last_hidden_state * mask).sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


def embed_texts(texts: list[str], batch_size: int = 16) -> np.ndarray:
    """Embed a list of texts -> (n, dim) float32, L2-normalized."""
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
    """Embed a single query -> (dim,) float32, L2-normalized."""
    return embed_texts([text])[0]
