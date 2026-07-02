---
license: cc-by-4.0
language:
  - en
pretty_name: "Legally AI — Indian Supreme Court Retrieval Index (v1)"
tags:
  - legal
  - indian-law
  - supreme-court-of-india
  - retrieval
  - rag
  - faiss
  - inlegalbert
size_categories:
  - 10K<n<100K
---

# Legally AI — Indian Supreme Court Retrieval Index (v1)

A prebuilt **semantic retrieval index** over Indian Supreme Court judgments, used by the
Legally AI RAG assistant. It is the corpus side of the system — user data is **not** here.

This repo ships two parallel artifacts (row order is identical between them):

| File | What it is |
|------|------------|
| `index/corpus.faiss` | FAISS `IndexFlatIP` over L2-normalized 768-dim vectors (inner product == cosine). |
| `index/corpus_meta.parquet` | One row per vector: the judgment metadata **and the chunk text**. |
| `raw/*.json` | A small sample of the normalized source judgments + `MANIFEST.json` (build provenance). |

> ⚠️ **Not legal advice.** A research/educational resource. Outcome labels are coarse and
> heuristically derived; verify against the primary judgment before relying on anything.

## Coverage (v1)

- **Court:** Supreme Court of India
- **Years:** 2015–2024 (full decade)
- **Judgments:** 1,991
- **Chunks (vectors):** 88,988

Chunk count by rhetorical role: `Body 42,926 · Facts 17,065 · Ratio 11,339 · Arguments 7,647 ·
Issues 7,624 · Holding 2,387`.

## Metadata schema (`corpus_meta.parquet`)

| Column | Type | Notes |
|--------|------|-------|
| `id` | str | `<source-file-stem>:<row>` — stable chunk id. |
| `case_name` | str | Judgment title. |
| `citation` | str | Reporter citation (e.g. `[2022] 6 S.C.R. 817`). |
| `court` | str | `Supreme Court of India`. |
| `year` | int | Decision year. |
| `outcome` | str | Raw disposal label, coarsely tagged `(Granted)` / `(Dismissed)` where obvious. |
| `segment_role` | str | `Facts · Issues · Arguments · Ratio · Holding · Body`. |
| `chunk_text` | str | The judgment text for this chunk (≤ ~1500 chars). |

## How it was built

1. **Source download** — judgments pulled from the AWS Open Data bucket below, normalized to
   one JSON per judgment (`pipeline/download_corpus.py`).
2. **Role-aware chunking** — each judgment split into ≤1500-char chunks, each tagged with a
   rhetorical role; decisive `Ratio`/`Holding` segments are up-weighted at retrieval time.
3. **Embedding** — each chunk encoded with **`law-ai/InLegalBERT`**, mean-pooled over the
   attention mask and **L2-normalized**, then added to a FAISS `IndexFlatIP`
   (`pipeline/chunk_embed.py`).

**To reproduce / query**, the runtime MUST embed queries with the exact same model + mean-pool
+ L2-norm, or query and index vectors won't be comparable.

## Versioning

Pinned by git **tag** (`v1`). A consumer should pin a revision rather than `main`, so a deploy
can't pick up a half-rebuilt index. Future expansions (more SC judgments, same schema) ship as
`v2`, `v3`, … — never by overwriting `v1`.

## Source & license

- **License:** **CC-BY-4.0**.
- **Attribution (required):** *Indian Supreme Court Judgments, Open Justice India (vanga), via
  AWS Open Data — CC-BY-4.0.* Source bucket: `s3://indian-supreme-court-judgments`
  (https://github.com/vanga/indian-supreme-court-judgments).
- Embeddings produced with `law-ai/InLegalBERT` (credit Law-AI).

Judgments of the Supreme Court of India are public records; this index redistributes derived
text chunks under the CC-BY-4.0 terms above with attribution preserved.
