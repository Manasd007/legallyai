from __future__ import annotations

import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import logging
import threading
import time

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import cache
import case_view as case_view_mod
import classifier as classifier_mod
import db
import doc_analyze as doc_analyze_mod
import doc_extract as doc_extract_mod
import doc_store as doc_store_mod
import ensemble as ensemble_mod
import legal_qa as legal_qa_mod
import parallel
import predict as predict_mod
import reformulate as reformulate_mod
import retrieval as retrieval_mod
import router as router_mod
import statute_finder as statute_finder_mod
import verify as verify_mod
from config import get_settings, load_prompt
from llm import complete
from logging_setup import log_stage, new_request_id, setup_logging
from textutil import normalize_query

setup_logging()
log = logging.getLogger("legally.main")

ANSWER_CACHE_VERSION = "v3"


def _answer_cache_key(question: str) -> str:
    return f"{ANSWER_CACHE_VERSION}|{get_settings().corpus_revision}|{normalize_query(question)}"

app = FastAPI(title="Legally AI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Assign a request id and log every request's method, path, status and time.

    The id is stamped on all log lines produced while handling the request
    (including pipeline stages and LLM calls) so one request can be followed
    end to end, and is echoed back in the ``X-Request-ID`` response header.
    """
    rid = new_request_id()
    start = time.perf_counter()
    client = request.client.host if request.client else "-"
    log.info(">> %s %s from %s", request.method, request.url.path, client)
    try:
        response = await call_next(request)
    except Exception:
        dur = (time.perf_counter() - start) * 1000
        log.exception("<< %s %s failed after %.0f ms", request.method, request.url.path, dur)
        raise
    dur = (time.perf_counter() - start) * 1000
    log.info(
        "<< %s %s %s in %.0f ms", request.method, request.url.path, response.status_code, dur
    )
    response.headers["X-Request-ID"] = rid
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end. Please try again."},
    )


@app.on_event("startup")
def _warmup_models() -> None:

    def _load() -> None:
        try:
            retrieval_mod._load_index()
            from embeddings import _load_model

            _load_model()
            log.info("Warmup complete: FAISS index + embedding model ready.")
            try:
                import lexical
                import rerank

                lexical._build()
                rerank._load()
                log.info("Warmup complete: BM25 index + cross-encoder reranker ready.")
            except Exception as e:  # noqa: BLE001 - hybrid/rerank are best-effort
                log.warning("Hybrid/rerank warmup failed (non-fatal): %s", e)
        except FileNotFoundError as e:
            log.warning("Warmup skipped (index not built): %s", e)
        except Exception as e:  # noqa: BLE001 - warmup is best-effort
            log.warning("Warmup failed (non-fatal): %s", e)

    threading.Thread(target=_load, name="model-warmup", daemon=True).start()


import functools


@functools.lru_cache(maxsize=1)
def _jwks_client():
    import jwt

    url = get_settings().supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url)


def get_user_id(authorization: str | None = Header(default=None)) -> str:
    if not authorization:
        return "dev-user"
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return "dev-user"
    try:
        import jwt

        leeway = 60
        alg = jwt.get_unverified_header(token).get("alg", "")
        if alg in ("ES256", "RS256", "EdDSA"):
            signing_key = _jwks_client().get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token, signing_key, algorithms=[alg], audience="authenticated", leeway=leeway
            )
        else:
            secret = get_settings().supabase_jwt_secret
            if secret:
                claims = jwt.decode(
                    token, secret, algorithms=["HS256"], audience="authenticated", leeway=leeway
                )
            else:
                log.warning("SUPABASE_JWT_SECRET not set — accepting JWT without verification.")
                claims = jwt.decode(token, options={"verify_signature": False})
        return claims.get("sub") or "dev-user"
    except Exception as e:  # noqa: BLE001 - a bad token must not 500 the request
        log.warning("JWT verification failed (%s); falling back to dev-user.", e)
        return "dev-user"


class QueryBody(BaseModel):
    question: str
    conversation_id: str | None = None
    session_id: str | None = None


class FeedbackBody(BaseModel):
    prediction_id: str
    rating: int
    note: str | None = None


class DocChatBody(BaseModel):
    doc_id: str
    question: str
    conversation_id: str | None = None
    session_id: str | None = None


class DocTermBody(BaseModel):
    doc_id: str
    term: str


class ChatTurn(BaseModel):
    role: str
    content: str


class ChatBody(BaseModel):
    question: str
    history: list[ChatTurn] = []
    conversation_id: str | None = None
    session_id: str | None = None


class CaseBody(BaseModel):
    citation: str = ""
    case_name: str = ""
    highlight_id: str = ""


class VoiceCallBody(BaseModel):

    question: str
    summary: str
    citations: list[str] = []
    tool: str = "assistant"
    conversation_id: str | None = None
    session_id: str | None = None


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "corpus": s.corpus_date_range, "backend": s.vector_backend}


@app.post("/api/doc/analyze")
async def doc_analyze_route(
    file: UploadFile = File(...),
    session_id: str | None = Form(None),
    user_id: str = Depends(get_user_id),
) -> dict:
    s = get_settings()
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > s.doc_max_upload_bytes:
        mb = s.doc_max_upload_bytes // (1024 * 1024)
        raise HTTPException(status_code=413, detail=f"File too large (max {mb} MB).")

    try:
        text, extract_meta = doc_extract_mod.extract_text(file.filename or "", data)
    except doc_extract_mod.ExtractionError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if len(text.strip()) < 100:
        raise HTTPException(
            status_code=422,
            detail="Couldn't read enough text from this file. If it's a photo or scan, "
            "make sure the document is clear and well-lit.",
        )

    analysis = doc_analyze_mod.analyze(text)
    doc_id = doc_store_mod.put(file.filename or "document", text, analysis)
    filename = file.filename or "document"
    response = {
        "doc_id": doc_id,
        "filename": filename,
        "char_count": len(text),
        "ocr": extract_meta.get("ocr", False),
        **analysis,
        "disclaimer": s.disclaimer,
    }
    response["conversation_id"] = db.record_turn(
        user_id=user_id,
        conversation_id=None,
        tool="documents",
        user_text=f"Uploaded document: {filename}",
        assistant_text=analysis.get("summary") or f"Analyzed {filename}.",
        payload=response,
        title=filename,
        session_id=session_id,
    )
    return response


@app.post("/api/doc/chat")
def doc_chat_route(body: DocChatBody, user_id: str = Depends(get_user_id)) -> dict:
    doc = doc_store_mod.get(body.doc_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found or expired. Please upload it again.",
        )
    answer = doc_analyze_mod.chat(doc, body.question, doc["history"])
    doc_store_mod.append_turn(body.doc_id, "user", body.question)
    doc_store_mod.append_turn(body.doc_id, "assistant", answer)
    conversation_id = db.record_turn(
        user_id=user_id,
        conversation_id=body.conversation_id,
        tool="documents",
        user_text=body.question,
        assistant_text=answer,
        session_id=body.session_id,
    )
    return {"answer": answer, "conversation_id": conversation_id, "disclaimer": get_settings().disclaimer}


@app.post("/api/doc/term")
def doc_term_route(body: DocTermBody) -> dict:
    doc = doc_store_mod.get(body.doc_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found or expired. Please upload it again.",
        )
    explanation = doc_analyze_mod.explain_term(doc, body.term)
    return {"term": body.term, "explanation": explanation}


@app.post("/api/case")
def case_route(body: CaseBody) -> dict:
    try:
        case = case_view_mod.get_case(
            citation=body.citation, case_name=body.case_name, highlight_id=body.highlight_id
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found in the corpus.")
    return case


@app.post("/api/chat")
def legal_chat_route(body: ChatBody, user_id: str = Depends(get_user_id)) -> dict:
    try:
        history = [{"role": t.role, "content": t.content} for t in body.history]
        result = legal_qa_mod.answer(body.question, history)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    conversation_id = db.record_turn(
        user_id=user_id,
        conversation_id=body.conversation_id,
        tool="assistant",
        user_text=body.question,
        assistant_text=result.get("answer", ""),
        payload=result,
        session_id=body.session_id,
    )
    return {**result, "conversation_id": conversation_id, "disclaimer": get_settings().disclaimer}


@app.post("/api/statutes")
def statutes_route(body: QueryBody, user_id: str = Depends(get_user_id)) -> dict:
    try:
        result = statute_finder_mod.find(body.question)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    conversation_id = db.record_turn(
        user_id=user_id,
        conversation_id=body.conversation_id,
        tool="statutes",
        user_text=body.question,
        assistant_text=result.get("summary") or "Identified governing Acts and sections.",
        payload=result,
        session_id=body.session_id,
    )
    return {**result, "conversation_id": conversation_id, "disclaimer": get_settings().disclaimer}


@app.post("/api/voice/record")
def voice_record_route(body: VoiceCallBody, user_id: str = Depends(get_user_id)) -> dict:
    tool = body.tool if body.tool in ("assistant", "predict", "statutes") else "assistant"
    payload = {"source": "voice", "voice_citations": body.citations}
    conversation_id = db.record_turn(
        user_id=user_id,
        conversation_id=body.conversation_id,
        tool=tool,
        user_text=body.question or "Voice consultation",
        assistant_text=body.summary,
        payload=payload,
        session_id=body.session_id,
    )
    return {"conversation_id": conversation_id}


@app.post("/api/retrieve")
def retrieve_only(body: QueryBody) -> dict:
    reformulated = reformulate_mod.reformulate(body.question)
    try:
        result = retrieval_mod.retrieve(reformulated, body.question)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    return {
        "reformulated_query": reformulated,
        "max_similarity": round(result.max_similarity, 4),
        "precedent_vote": ensemble_mod.precedent_vote(result),
        "chunks": [c.to_dict() for c in result.chunks],
    }


def compute_legal_prediction(question: str) -> tuple[dict, dict]:
    """Core legal-prediction pipeline with NO cache / DB / auth side effects.

    Runs reformulate -> retrieve -> precedent vote + classifier ->
    predict_validated -> verify -> ensemble.combine -> confidence reconcile ->
    coherence guard, and returns ``(response_without_ids, prediction)``. The
    /api/query route wraps this with caching and persistence; the consistency
    eval harness calls it directly so it exercises the identical logic. Raises
    FileNotFoundError if the retrieval index is unavailable.
    """
    s = get_settings()
    log.info("Legal prediction pipeline start (parallel=%s)", s.parallel_signals)

    with log_stage(log, "reformulate"):
        reformulated = reformulate_mod.reformulate(question)

    clf_text = f"{question}\n\n{reformulated}".strip()
    if s.parallel_signals:
        with log_stage(log, "retrieve+classifier (parallel)") as st:
            out = parallel.run_parallel(
                {
                    "retrieve": lambda: retrieval_mod.retrieve(reformulated, question),
                    "classifier": lambda: classifier_mod.predict_win(clf_text),
                }
            )
            result, clf = out["retrieve"], out["classifier"]
            st["chunks"] = len(result.chunks)
    else:
        with log_stage(log, "retrieve") as st:
            result = retrieval_mod.retrieve(reformulated, question)
            st["chunks"] = len(result.chunks)
        with log_stage(log, "classifier"):
            clf = classifier_mod.predict_win(clf_text)

    with log_stage(log, "precedent_vote"):
        precedent = ensemble_mod.precedent_vote(result)

    with log_stage(log, "predict_validated"):
        prediction, validation = predict_mod.predict_validated(
            reformulated, question, result, precedent=precedent, classifier=clf
        )
    prediction["_model_version"] = predict_mod.MODEL_VERSION

    with log_stage(log, "verify"):
        prediction = verify_mod.verify(prediction, result)

    with log_stage(log, "ensemble.combine") as st:
        combined = ensemble_mod.combine(
            precedent=precedent,
            llm_outcome=prediction["likely_outcome"],
            classifier=clf,
            llm_confidence=prediction.get("confidence"),
        )
        st["outcome"] = prediction.get("likely_outcome")
        st["confidence"] = prediction.get("confidence")
    prediction_signals = {
        "precedent_vote": precedent,
        "llm_forecast": {
            "likely_outcome": prediction["likely_outcome"],
            "label": ensemble_mod.llm_outcome_to_label(prediction["likely_outcome"]),
        },
        "classifier": clf,
        **combined,
    }

    if prediction["verification"].get("hedged"):
        prediction_signals["confidence"] = "low"

    _CONF_RANK = {"low": 0, "medium": 1, "high": 2}
    _reconciled = min(
        prediction_signals["confidence"],
        prediction.get("confidence", "low"),
        key=lambda c: _CONF_RANK.get(c, 0),
    )
    prediction["confidence"] = _reconciled
    prediction_signals["confidence"] = _reconciled

    _llm_label = ensemble_mod.llm_outcome_to_label(prediction["likely_outcome"])
    _final_label = prediction_signals.get("final_label")
    _hedged = prediction["verification"].get("hedged")
    _contradicts = (
        _llm_label is not None and _final_label is not None and _llm_label != _final_label
    )
    if _hedged or prediction_signals.get("final_win_probability") is None or _contradicts:
        prediction_signals["final_win_probability"] = None
        prediction_signals["final_label"] = None
        if _contradicts and not _hedged:
            prediction_signals["note"] = (
                "The written analysis and the analogous decided cases point in "
                "different directions, so no single percentage is shown; treat this "
                "as genuinely uncertain."
            )

    response = {
        "category": "legal",
        "situation_summary": prediction["situation_summary"],
        "likely_outcome": prediction["likely_outcome"],
        "confidence": prediction["confidence"],
        "win_probability": prediction_signals["final_win_probability"],
        "win_label": prediction_signals["final_label"],
        "prediction_signals": prediction_signals,
        "reasoning": prediction["reasoning"],
        "key_factors": prediction.get("key_factors", []),
        "what_would_strengthen": prediction.get("what_would_strengthen", []),
        "cited_cases": prediction["cited_cases"],
        "verification": prediction["verification"],
        "validation": validation,
        "disclaimer": s.disclaimer,
    }
    return response, prediction


@app.post("/api/query")
def query(body: QueryBody, user_id: str = Depends(get_user_id)) -> dict:
    s = get_settings()
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    route = router_mod.classify(question)
    category = route["category"]

    if category == "not_legal":
        return {
            "category": "not_legal",
            "conversation_id": body.conversation_id,
            "message": (
                "Hi! I'm Legally AI, and I help with Indian legal matters. Tell me what "
                "happened, ask a legal question, or attach a document and I'll take a look."
            ),
        }

    if category == "general_legal":
        gl_key = "general|" + _answer_cache_key(question)
        gl = cache.get(gl_key)
        if not gl:
            try:
                answer = complete(
                    model=s.reasoning_model,
                    system=load_prompt("general_legal_v2.txt"),
                    user=question,
                    temperature=0.0,
                    max_tokens=1000,
                    reasoning_effort="low",
                    seed=s.llm_seed,
                ).strip()
                gl = {"category": "general_legal", "answer": answer, "disclaimer": s.disclaimer}
                cache.set(gl_key, gl)
            except Exception as e:  # noqa: BLE001
                log.error("general_legal answer failed: %s", e)
                gl = {
                    "category": "general_legal",
                    "answer": "I'm unable to answer that right now. Please try again shortly.",
                    "disclaimer": s.disclaimer,
                }
        gl = {**gl}
        gl["conversation_id"] = db.record_turn(
            user_id=user_id,
            conversation_id=body.conversation_id,
            tool="predict",
            user_text=question,
            assistant_text=gl["answer"],
            payload=gl,
            session_id=body.session_id,
        )
        return gl

    cache_key = _answer_cache_key(question)
    cached = cache.get(cache_key)
    if cached:
        conversation_id = db.record_turn(
            user_id=user_id,
            conversation_id=body.conversation_id,
            tool="predict",
            user_text=question,
            assistant_text=cached.get("situation_summary", ""),
            payload=cached,
            session_id=body.session_id,
        )
        return {**cached, "conversation_id": conversation_id}

    try:
        response, prediction = compute_legal_prediction(question)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    case_id = db.persist_query(user_id=user_id, raw_text=question, prediction=prediction)
    response["case_id"] = case_id
    cache.set(cache_key, response)
    conversation_id = db.record_turn(
        user_id=user_id,
        conversation_id=body.conversation_id,
        tool="predict",
        user_text=question,
        assistant_text=response["situation_summary"],
        payload=response,
        case_id=case_id,
        session_id=body.session_id,
    )
    return {**response, "conversation_id": conversation_id}


@app.get("/api/history")
def history(user_id: str = Depends(get_user_id)) -> dict:
    return {"cases": db.list_history(user_id)}


@app.get("/api/conversations")
def conversations(user_id: str = Depends(get_user_id)) -> dict:
    return {"conversations": db.list_conversations(user_id)}


@app.get("/api/conversations/{conversation_id}")
def conversation_detail(conversation_id: str, user_id: str = Depends(get_user_id)) -> dict:
    thread = db.get_conversation(user_id=user_id, conversation_id=conversation_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return thread


@app.get("/api/sessions")
def sessions(user_id: str = Depends(get_user_id)) -> dict:
    return {"sessions": db.list_sessions(user_id)}


@app.get("/api/sessions/{session_id}")
def session_detail(session_id: str, user_id: str = Depends(get_user_id)) -> dict:
    sess = db.get_session(user_id=user_id, session_id=session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return sess


@app.post("/api/feedback")
def feedback(body: FeedbackBody, user_id: str = Depends(get_user_id)) -> dict:
    ok = db.add_feedback(
        user_id=user_id, prediction_id=body.prediction_id, rating=body.rating, note=body.note
    )
    if not ok:
        raise HTTPException(status_code=500, detail="could not record feedback")
    return {"ok": True}
