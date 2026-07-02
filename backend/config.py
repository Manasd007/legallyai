"""Central configuration for Legally AI (brief §13).

All model IDs, rate-limit assumptions, and tunables live here so free-tier
churn never forces a change to business logic. Values come from environment
variables (see ../.env.example) with sensible defaults.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# Load backend/.env if present.
load_dotenv(Path(__file__).resolve().parent / ".env")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent  # repo root (data/ lives here)
PROMPTS_DIR = BASE_DIR / "prompts"

# Google Cloud auth reads GOOGLE_APPLICATION_CREDENTIALS as a filesystem path. We
# allow it to be written relative to backend/ in .env; resolve it to an absolute
# path here and write it back so the google client finds the key no matter which
# directory the app was launched from.
_gac = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
if _gac and not Path(_gac).is_absolute():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str((BASE_DIR / _gac).resolve())


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _get_bool(name: str, default: bool = False) -> bool:
    return _get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _get_list(name: str, default: str = "") -> list[str]:
    """Comma-separated env var -> list of trimmed, non-empty strings."""
    return [v.strip() for v in _get(name, default).split(",") if v.strip()]


def _data_path(name: str, default_rel: str) -> str:
    """Resolve a data path (index/model) against the PROJECT ROOT, not the current
    working directory — so the backend works no matter where it is launched from."""
    raw = _get(name, default_rel)
    p = Path(raw)
    return str(p if p.is_absolute() else (PROJECT_ROOT / p))


# Hugging Face namespace (your username/org). In prod the backend pulls the
# index + classifier from the Hub when they aren't on local disk; locally the
# data/ folder is used and the Hub is never touched. One var sets both repos.
_HF_NS = _get("HF_NAMESPACE", "")


def _repo(name: str, suffix: str) -> str:
    """Resolve a Hub repo id: explicit env override, else <HF_NAMESPACE>/<suffix>,
    else "" (meaning 'no Hub fallback configured')."""
    explicit = _get(name, "")
    if explicit:
        return explicit
    return f"{_HF_NS}/{suffix}" if _HF_NS else ""


class Settings(BaseModel):
    # ── LLM providers ────────────────────────────────────────
    groq_api_key: str = _get("GROQ_API_KEY")
    google_api_key: str = _get("GOOGLE_AI_STUDIO_API_KEY")
    openrouter_api_key: str = _get("OPENROUTER_API_KEY")

    router_model: str = _get("ROUTER_MODEL", "groq/llama-3.1-8b-instant")
    reformulate_model: str = _get("REFORMULATE_MODEL", "groq/llama-3.1-8b-instant")
    reasoning_model: str = _get("REASONING_MODEL", "gemini/gemini-2.0-flash")

    fallback_provider: str = _get("LLM_FALLBACK_PROVIDER", "openrouter")
    fallback_model: str = _get(
        "LLM_FALLBACK_MODEL",
        "openrouter/meta-llama/llama-3.1-8b-instruct:free",
    )

    # ── Supabase ─────────────────────────────────────────────
    supabase_url: str = _get("SUPABASE_URL")
    supabase_anon_key: str = _get("SUPABASE_ANON_KEY")
    supabase_service_key: str = _get("SUPABASE_SERVICE_KEY")
    # Project JWT secret (Supabase dashboard → Settings → API → JWT Secret).
    # Used to *verify* the caller's session token so their user id can be trusted.
    # If blank, verification is skipped and requests fall back to a dev user.
    supabase_jwt_secret: str = _get("SUPABASE_JWT_SECRET")

    # ── Retrieval ────────────────────────────────────────────
    embedding_model: str = _get("EMBEDDING_MODEL", "law-ai/InLegalBERT")
    embedding_dim: int = int(_get("EMBEDDING_DIM", "768"))
    top_k: int = int(_get("TOP_K", "5"))
    similarity_threshold: float = float(_get("SIMILARITY_THRESHOLD", "0.35"))
    vector_backend: str = _get("VECTOR_BACKEND", "faiss")  # faiss | pgvector
    faiss_index_path: str = _data_path("FAISS_INDEX_PATH", "data/index/corpus.faiss")
    faiss_meta_path: str = _data_path("FAISS_META_PATH", "data/index/corpus_meta.parquet")
    # Hub fallback for the index: when the local files above are absent (prod),
    # download these filenames from this DATASET repo, pinned to a version tag so
    # a deploy can never pick up a half-rebuilt index (brief: reproducibility).
    corpus_repo: str = _repo("CORPUS_REPO", "legally-ai-corpus-index")
    corpus_revision: str = _get("CORPUS_REVISION", "v1")
    corpus_index_file: str = _get("CORPUS_INDEX_FILE", "index/corpus.faiss")
    corpus_meta_file: str = _get("CORPUS_META_FILE", "index/corpus_meta.parquet")

    # ── Win/lose ensemble (the 1/0 prediction) ───────────────
    # Trained PredEx classifier weights (built offline, brief §10). Optional:
    # if the path is absent, the ensemble simply runs without this 3rd signal.
    classifier_model_path: str = _data_path("CLASSIFIER_MODEL_PATH", "data/models/predex_inlegalbert")
    # Hub fallback for the classifier (a MODEL repo). transformers' from_pretrained
    # loads a repo id natively; used only when the local path above is missing.
    classifier_repo: str = _repo("CLASSIFIER_REPO", "legally-ai-predex-classifier")
    classifier_revision: str = _get("CLASSIFIER_REVISION", "v1")
    # Minimum number of clearly-decided precedents for the "precedent vote"
    # to count as applicable (below this we don't claim a data-grounded lean).
    min_precedents_for_vote: int = int(_get("MIN_PRECEDENTS_FOR_VOTE", "2"))

    # ── Document analysis (upload → analyze → chat) ──────────
    # Cap how much document text we send to the LLM per call (free-tier token
    # limits) and how long an analyzed doc stays cached for follow-up chat.
    doc_max_chars: int = int(_get("DOC_MAX_CHARS", "30000"))
    doc_ttl_seconds: int = int(_get("DOC_TTL_SECONDS", "86400"))
    doc_max_upload_bytes: int = int(_get("DOC_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

    # OCR backend for scanned/handwritten/multilingual uploads.
    #   "vision_llm"    -> a multimodal LLM reads the image (default; free tier).
    #   "google_vision" -> Google Cloud Vision DOCUMENT_TEXT_DETECTION (needs a
    #                      GCP service-account JSON via GOOGLE_APPLICATION_CREDENTIALS).
    ocr_backend: str = _get("OCR_BACKEND", "vision_llm")
    # Vision-LLM backend model (Groq Llama-4 multimodal; no Tesseract binary needed).
    vision_model: str = _get("VISION_MODEL", "groq/meta-llama/llama-4-scout-17b-16e-instruct")
    ocr_max_pages: int = int(_get("OCR_MAX_PAGES", "8"))  # cap pages OCR'd per PDF
    ocr_min_chars: int = int(_get("OCR_MIN_CHARS", "200"))  # below this, treat PDF as scanned
    # Google Vision language hints (BCP-47 codes, e.g. "hi,ta,bn,en"). Optional —
    # biases recognition toward expected scripts; leave blank for auto-detect.
    ocr_language_hints: list[str] = _get_list("OCR_LANGUAGE_HINTS")
    # After OCR, optionally translate non-English text to English so the analysis
    # models handle it well. Needed for the multilingual case; Google Vision only
    # transcribes. Default off so existing English-doc behavior is unchanged.
    ocr_translate: bool = _get_bool("OCR_TRANSLATE", False)
    ocr_translate_model: str = _get("OCR_TRANSLATE_MODEL", _get("REASONING_MODEL", "gemini/gemini-2.0-flash"))

    # ── App ──────────────────────────────────────────────────
    corpus_date_range: str = _get(
        "CORPUS_DATE_RANGE", "Supreme Court of India, ~2015-present"
    )
    cache_ttl_seconds: int = int(_get("CACHE_TTL_SECONDS", "86400"))
    disclaimer: str = _get(
        "DISCLAIMER",
        "This is a research/educational tool, not legal advice. It can be wrong "
        "or incomplete. Consult a qualified advocate before acting.",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def load_prompt(name: str) -> str:
    """Read a versioned prompt template from prompts/ (brief §7)."""
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")
