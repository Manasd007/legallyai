from __future__ import annotations

import logging
import re
from functools import lru_cache

log = logging.getLogger("legally.lexical")

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall((text or "").lower())


@lru_cache(maxsize=1)
def _build():
    from rank_bm25 import BM25Okapi

    from retrieval import _load_index

    _, meta = _load_index()
    corpus = [tokenize(str(t or "")) for t in meta["chunk_text"].tolist()]
    bm25 = BM25Okapi(corpus)
    log.info("Built BM25 lexical index over %d chunks.", len(corpus))
    return bm25, len(corpus)


def search(query: str, top_n: int) -> list[tuple[int, float]]:
    try:
        toks = tokenize(query)
        if not toks:
            return []
        bm25, n = _build()
        scores = bm25.get_scores(toks)
        k = min(top_n, n)
        top = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(i, float(scores[i])) for i in top if scores[i] > 0.0]
    except Exception as e:  # noqa: BLE001 - lexical is best-effort
        log.warning("BM25 search failed (%s); dense-only for this query.", e)
        return []
