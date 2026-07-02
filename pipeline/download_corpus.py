"""Phase 0 — download a narrow slice of the Indian SC judgment corpus (brief §5).

Source: "Indian Supreme Court Judgments" on the AWS Open Data Registry
(CC-BY-4.0), maintained by the Open Justice India project
(github.com/vanga/indian-supreme-court-judgments). Public bucket, anonymous
(unsigned) access.

Bucket layout (verified):
  metadata/parquet/year=YYYY/metadata.parquet     <- structured metadata
  data/pdf/year=YYYY/english/{path}_EN.pdf         <- per-judgment English PDF
  data/tar/year=YYYY/english/english.tar           <- whole-year text archive

Parquet columns: title, petitioner, respondent, description, judge,
  author_judge, citation, case_id, cnr, decision_date, disposal_nature,
  court, available_languages, raw_html, path, nc_display, scraped_at, year.

This script reads the parquet metadata and, for up to --limit judgments per
year, downloads the individual English PDF and extracts its text, writing one
normalized JSON per judgment to data/raw/ for chunk_embed.py.

Per-PDF download keeps small slices cheap. For the FULL corpus, prefer the
year `english.tar` archives and run embedding on free Kaggle/Colab GPU (brief §3).

Usage:
  python download_corpus.py --start-year 2015 --end-year 2024 --limit 25
"""
from __future__ import annotations

import argparse
import io
import json
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("download_corpus")

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"

BUCKET = "indian-supreme-court-judgments"
ATTRIBUTION = "CC-BY-4.0 — Indian Supreme Court Judgments, Open Justice India (vanga), via AWS Open Data."


def _s3():
    import boto3
    from botocore import UNSIGNED
    from botocore.config import Config

    return boto3.client("s3", config=Config(signature_version=UNSIGNED))


def _read_parquet(s3, year: int):
    import pandas as pd

    key = f"metadata/parquet/year={year}/metadata.parquet"
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    return pd.read_parquet(io.BytesIO(obj["Body"].read()))


def _extract_pdf_text(data: bytes) -> str:
    """Extract text from PDF bytes; PyMuPDF first, pypdf fallback."""
    try:
        import fitz  # PyMuPDF

        with fitz.open(stream=data, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc).strip()
    except Exception:  # noqa: BLE001 - fall back to pypdf
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            return "\n".join((p.extract_text() or "") for p in reader.pages).strip()
        except Exception as e:  # noqa: BLE001
            log.warning("    PDF text extraction failed: %s", e)
            return ""


def _normalize_outcome(disposal_nature: str) -> str:
    """Keep the raw disposal label but tag a coarse binary where obvious."""
    d = (disposal_nature or "").lower()
    if "allow" in d:
        return f"{disposal_nature} (Granted)"
    if "dismiss" in d:
        return f"{disposal_nature} (Dismissed)"
    return disposal_nature or "Unknown"


def main() -> None:
    ap = argparse.ArgumentParser(description="Download SC judgment corpus slice.")
    ap.add_argument("--start-year", type=int, default=2015)
    ap.add_argument("--end-year", type=int, default=2024)
    ap.add_argument("--limit", type=int, default=25, help="max judgments PER YEAR")
    ap.add_argument("--min-chars", type=int, default=500, help="skip docs with less text")
    ap.add_argument("--out", type=Path, default=RAW_DIR)
    args = ap.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    s3 = _s3()
    manifest = {"bucket": BUCKET, "license": ATTRIBUTION, "years": {}, "files": []}
    total = 0

    for year in range(args.start_year, args.end_year + 1):
        try:
            df = _read_parquet(s3, year)
        except Exception as e:  # noqa: BLE001
            log.warning("year %d: no metadata (%s), skipping", year, e)
            continue

        log.info("year %d: %d judgments in metadata; taking up to %d", year, len(df), args.limit)
        taken = 0
        for _, row in df.iterrows():
            if taken >= args.limit:
                break
            path = str(row.get("path") or "").strip()
            if not path:
                continue
            pdf_key = f"data/pdf/year={year}/english/{path}_EN.pdf"
            try:
                obj = s3.get_object(Bucket=BUCKET, Key=pdf_key)
                text = _extract_pdf_text(obj["Body"].read())
            except Exception as e:  # noqa: BLE001
                log.warning("    %s: download/extract failed (%s)", pdf_key, e)
                continue
            if len(text) < args.min_chars:
                continue

            doc = {
                "case_name": str(row.get("title") or ""),
                "citation": str(row.get("citation") or ""),
                "neutral_citation": str(row.get("case_id") or ""),
                "court": str(row.get("court") or "Supreme Court of India"),
                "year": int(year),
                "decision_date": str(row.get("decision_date") or ""),
                "judges": str(row.get("judge") or ""),
                "outcome": _normalize_outcome(str(row.get("disposal_nature") or "")),
                "source_pdf": f"s3://{BUCKET}/{pdf_key}",
                "full_text": text,
            }
            out_path = args.out / f"{year}_{path}.json"
            out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
            manifest["files"].append(out_path.name)
            taken += 1
            total += 1
            log.info("    [%d] %s", total, doc["case_name"][:70])

        manifest["years"][str(year)] = taken

    (args.out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    log.info("Done. Wrote %d judgments to %s", total, args.out)
    if total == 0:
        raise SystemExit("No judgments downloaded — check network/year range.")


if __name__ == "__main__":
    main()
