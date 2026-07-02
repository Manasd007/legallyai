"""Phase 0 — role-aware chunk + embed + build FAISS index (brief §5).

Reads raw judgments from data/raw/, segments each into rhetorical roles
(Facts, Issues, Arguments, Ratio/Holding, ...), embeds chunks with InLegalBERT
(SAME model + mean-pool + L2-norm as backend/embeddings.py), and writes:
  * data/index/corpus.faiss        (IndexFlatIP over normalized vectors == cosine)
  * data/index/corpus_meta.parquet (parallel metadata, row order == faiss ids)

Run OFFLINE on free Kaggle/Colab GPU. The backend only reads the artifacts.

Why role-aware chunking: the Ratio/Holding segments carry the decided outcome
and reasoning; retrieval.py up-weights them. Don't chunk blindly by tokens.
"""
from __future__ import annotations

import os

# Permit PyTorch + FAISS dual OpenMP runtimes (Windows "OMP: Error #15").
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import argparse
import json
import re
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"
INDEX_DIR = ROOT / "data" / "index"

EMBEDDING_MODEL = "law-ai/InLegalBERT"
EMBEDDING_DIM = 768

# Heuristic rhetorical-role markers for Indian judgments. Replace with a trained
# rhetorical-role classifier later for better segmentation.
ROLE_MARKERS = {
    "Facts": [r"\bfacts?\b", r"\bbrief facts\b", r"\bfactual matrix\b"],
    "Issues": [r"\bissues?\b", r"\bquestions? of law\b", r"\bpoints? for determination\b"],
    "Arguments": [r"\bsubmissions?\b", r"\bcontend(?:ed|s)?\b", r"\blearned counsel\b"],
    "Ratio": [r"\bwe are of the (?:view|opinion)\b", r"\bratio\b", r"\bheld\b", r"\bwe hold\b"],
    "Holding": [r"\baccordingly\b", r"\bappeal is (?:allowed|dismissed)\b", r"\bdisposed of\b"],
}


def _load_embedder():
    import torch
    from transformers import AutoModel, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(EMBEDDING_MODEL)
    model = AutoModel.from_pretrained(EMBEDDING_MODEL)
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    return tok, model, torch, device


def _embed(texts: list[str], tok, model, torch, device, batch_size: int = 32) -> np.ndarray:
    vecs = []
    with torch.no_grad():
        for i in range(0, len(texts), batch_size):
            enc = tok(
                texts[i : i + batch_size],
                padding=True, truncation=True, max_length=512, return_tensors="pt",
            ).to(device)
            hidden = model(**enc).last_hidden_state
            mask = enc["attention_mask"].unsqueeze(-1).type_as(hidden)
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1e-9)
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
            vecs.append(pooled.cpu().numpy().astype("float32"))
    return np.vstack(vecs)


def _label_role(text: str) -> str:
    low = text.lower()
    for role, pats in ROLE_MARKERS.items():
        if any(re.search(p, low) for p in pats):
            return role
    return "Body"


def _split_long(text: str, max_chars: int) -> list[str]:
    """Hard-split an over-long block into <=max_chars pieces, preferring a
    sentence/word boundary. Needed because many SC PDFs extract with NO blank
    lines, so paragraph splitting alone leaves one giant chunk per judgment."""
    pieces: list[str] = []
    while len(text) > max_chars:
        window = text[:max_chars]
        cut = max(window.rfind(". "), window.rfind("\n"), window.rfind(" "))
        if cut <= 0:
            cut = max_chars  # no boundary found; cut hard
        pieces.append(text[: cut + 1].strip())
        text = text[cut + 1 :].strip()
    if text:
        pieces.append(text)
    return pieces


def _chunk(full_text: str, max_chars: int = 1500) -> list[tuple[str, str]]:
    """Split into size-bounded chunks, tag each with a rhetorical role.

    First split on blank-line paragraphs; then hard-split any paragraph longer
    than max_chars so we never embed a whole judgment as a single chunk (which
    would truncate to the first ~512 tokens and lose the rest)."""
    raw_paras = [p.strip() for p in re.split(r"\n\s*\n", full_text) if p.strip()]
    paras: list[str] = []
    for p in raw_paras:
        paras.extend(_split_long(p, max_chars) if len(p) > max_chars else [p])

    chunks: list[tuple[str, str]] = []
    buf = ""
    for p in paras:
        if len(buf) + len(p) > max_chars and buf:
            chunks.append((_label_role(buf), buf))
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        chunks.append((_label_role(buf), buf))
    return chunks


def main() -> None:
    ap = argparse.ArgumentParser(description="Chunk + embed corpus, build FAISS index.")
    ap.add_argument("--raw", type=Path, default=RAW_DIR)
    ap.add_argument("--out", type=Path, default=INDEX_DIR)
    args = ap.parse_args()

    import faiss
    import pandas as pd

    raw_files = sorted(args.raw.glob("*.json"))
    if not raw_files:
        raise SystemExit(
            f"No raw judgments in {args.raw}. Run download_corpus.py first (Phase 0)."
        )

    tok, model, torch, device = _load_embedder()
    rows: list[dict] = []
    texts: list[str] = []

    for fp in raw_files:
        doc = json.loads(fp.read_text(encoding="utf-8"))
        for role, chunk_text in _chunk(doc.get("full_text", "")):
            rows.append(
                {
                    "id": f"{fp.stem}:{len(rows)}",
                    "case_name": doc.get("case_name", ""),
                    "citation": doc.get("citation", ""),
                    "court": doc.get("court", ""),
                    "year": doc.get("year"),
                    "outcome": doc.get("outcome", ""),
                    "segment_role": role,
                    "chunk_text": chunk_text,
                }
            )
            texts.append(chunk_text)

    avg_len = int(sum(len(t) for t in texts) / max(len(texts), 1))
    roles = {}
    for r in rows:
        roles[r["segment_role"]] = roles.get(r["segment_role"], 0) + 1
    print(f"Chunks: {len(texts)} from {len(raw_files)} judgments | avg {avg_len} chars/chunk")
    print(f"Roles: {roles}")
    if len(texts) <= len(raw_files):
        print("WARNING: ~1 chunk per judgment — chunking likely collapsed (check PDF text).")
    print(f"Embedding {len(texts)} chunks on {device}...")
    embeddings = _embed(texts, tok, model, torch, device)

    args.out.mkdir(parents=True, exist_ok=True)
    index = faiss.IndexFlatIP(EMBEDDING_DIM)  # inner product on normalized == cosine
    index.add(embeddings)
    faiss.write_index(index, str(args.out / "corpus.faiss"))
    pd.DataFrame(rows).to_parquet(args.out / "corpus_meta.parquet", index=False)

    print(f"Wrote {index.ntotal} vectors -> {args.out/'corpus.faiss'}")
    print(f"Wrote metadata -> {args.out/'corpus_meta.parquet'}")


if __name__ == "__main__":
    main()
