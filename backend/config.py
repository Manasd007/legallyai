from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(Path(__file__).resolve().parent / ".env")

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
PROMPTS_DIR = BASE_DIR / "prompts"

_gac = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
if _gac and not Path(_gac).is_absolute():
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str((BASE_DIR / _gac).resolve())


def _get(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def _get_bool(name: str, default: bool = False) -> bool:
    return _get(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


def _get_list(name: str, default: str = "") -> list[str]:
    return [v.strip() for v in _get(name, default).split(",") if v.strip()]


def _get_map(name: str, default: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in _get(name, default).split(","):
        if "=" not in pair:
            continue
        k, v = (part.strip() for part in pair.split("=", 1))
        if k and v:
            out[k] = v
    return out


def _data_path(name: str, default_rel: str) -> str:
    raw = _get(name, default_rel)
    p = Path(raw)
    return str(p if p.is_absolute() else (PROJECT_ROOT / p))


_HF_NS = _get("HF_NAMESPACE", "")


def _repo(name: str, suffix: str) -> str:
    explicit = _get(name, "")
    if explicit:
        return explicit
    return f"{_HF_NS}/{suffix}" if _HF_NS else ""


class Settings(BaseModel):
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

    llm_seed: int = int(_get("LLM_SEED", "7"))

    conduit_base_url: str = _get("CONDUIT_BASE_URL")
    conduit_api_key: str = _get("CONDUIT_API_KEY")
    conduit_model_map: dict[str, str] = _get_map(
        "CONDUIT_MODEL_MAP", "groq=groq-llama,gemini=gpt-4o-mini,openrouter=groq-llama"
    )
    conduit_default_model: str = _get("CONDUIT_DEFAULT_MODEL", "groq-llama")

    supabase_url: str = _get("SUPABASE_URL")
    supabase_anon_key: str = _get("SUPABASE_ANON_KEY")
    supabase_service_key: str = _get("SUPABASE_SERVICE_KEY")
    supabase_jwt_secret: str = _get("SUPABASE_JWT_SECRET")

    parallel_signals: bool = _get_bool("PARALLEL_SIGNALS", True)

    validation_enabled: bool = _get_bool("VALIDATION_ENABLED", True)
    validator_model: str = _get("VALIDATOR_MODEL", _get("ROUTER_MODEL", "groq/openai/gpt-oss-20b"))

    embedding_model: str = _get("EMBEDDING_MODEL", "law-ai/InLegalBERT")
    embedding_dim: int = int(_get("EMBEDDING_DIM", "768"))
    top_k: int = int(_get("TOP_K", "5"))
    similarity_threshold: float = float(_get("SIMILARITY_THRESHOLD", "0.35"))
    vector_backend: str = _get("VECTOR_BACKEND", "faiss")
    faiss_index_path: str = _data_path("FAISS_INDEX_PATH", "data/index/corpus.faiss")
    faiss_meta_path: str = _data_path("FAISS_META_PATH", "data/index/corpus_meta.parquet")
    corpus_repo: str = _repo("CORPUS_REPO", "legally-ai-corpus-index")
    corpus_revision: str = _get("CORPUS_REVISION", "v1")
    corpus_index_file: str = _get("CORPUS_INDEX_FILE", "index/corpus.faiss")
    corpus_meta_file: str = _get("CORPUS_META_FILE", "index/corpus_meta.parquet")

    classifier_model_path: str = _data_path("CLASSIFIER_MODEL_PATH", "data/models/predex_inlegalbert")
    classifier_repo: str = _repo("CLASSIFIER_REPO", "legally-ai-predex-classifier")
    classifier_revision: str = _get("CLASSIFIER_REVISION", "v1")
    min_precedents_for_vote: int = int(_get("MIN_PRECEDENTS_FOR_VOTE", "2"))

    retrieval_mode: str = _get("RETRIEVAL_MODE", "hybrid")
    hybrid_candidates: int = int(_get("HYBRID_CANDIDATES", "40"))
    rrf_k: int = int(_get("RRF_K", "60"))
    dense_weight: float = float(_get("DENSE_WEIGHT", "1.0"))
    lexical_weight: float = float(_get("LEXICAL_WEIGHT", "1.0"))
    rerank_enabled: bool = _get_bool("RERANK_ENABLED", True)
    reranker_model: str = _get("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    reranker_repo: str = _get("RERANKER_REPO", "")
    reranker_revision: str = _get("RERANKER_REVISION", "main")
    rerank_candidates: int = int(_get("RERANK_CANDIDATES", "40"))
    case_assembly_enabled: bool = _get_bool("CASE_ASSEMBLY_ENABLED", True)
    case_max_supporting: int = int(_get("CASE_MAX_SUPPORTING", "2"))

    doc_max_chars: int = int(_get("DOC_MAX_CHARS", "30000"))
    doc_ttl_seconds: int = int(_get("DOC_TTL_SECONDS", "86400"))
    doc_max_upload_bytes: int = int(_get("DOC_MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))

    ocr_backend: str = _get("OCR_BACKEND", "vision_llm")
    vision_model: str = _get("VISION_MODEL", "groq/meta-llama/llama-4-scout-17b-16e-instruct")
    ocr_max_pages: int = int(_get("OCR_MAX_PAGES", "8"))
    ocr_min_chars: int = int(_get("OCR_MIN_CHARS", "200"))
    ocr_language_hints: list[str] = _get_list("OCR_LANGUAGE_HINTS")
    ocr_translate: bool = _get_bool("OCR_TRANSLATE", False)
    ocr_translate_model: str = _get("OCR_TRANSLATE_MODEL", _get("REASONING_MODEL", "gemini/gemini-2.0-flash"))

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
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")
