"""Legally AI — FastAPI app and routes (brief §9).

Implements the full request lifecycle (brief §6):
  router -> reformulate -> retrieve -> predict -> verify -> answer -> persist

Designed to degrade gracefully:
  * No LLM keys?  reformulation/router fall back; /api/retrieve still works.
  * No FAISS index? retrieval raises a clear 503 telling you to run Phase 0.
  * Persistence failure? logged, answer still returned.
"""
from __future__ import annotations

# PyTorch and FAISS each link their own OpenMP runtime; on Windows this trips
# "OMP: Error #15 ... multiple copies of the OpenMP runtime" and aborts the
# process. Allow the duplicate runtime BEFORE torch/faiss are imported. Must be
# the first thing we do. (For a permanent fix, build/install torch+faiss against
# a single OpenMP, but this is the supported workaround.)
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
# Quieten the HF/transformers startup noise (token nag + weight-load reports);
# loading InLegalBERT as a base encoder legitimately drops its MLM head.
os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

import logging
import threading

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
import predict as predict_mod
import reformulate as reformulate_mod
import retrieval as retrieval_mod
import router as router_mod
import statute_finder as statute_finder_mod
import verify as verify_mod
from config import get_settings, load_prompt
from llm import complete

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("legally.main")

app = FastAPI(title="Legally AI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to the Vercel domain before deploy
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Never let an unhandled error leak as plain-text "Internal Server Error".

    The frontend always parses responses as JSON, so a bare-text 500 surfaces to
    users as a cryptic "Unexpected token … is not valid JSON". Returning a proper
    JSON envelope keeps the client's error handling working everywhere."""
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong on our end. Please try again."},
    )


@app.on_event("startup")
def _warmup_models() -> None:
    """Preload the FAISS index and embedding model in the background.

    The first query otherwise pays a ~60s cold-start to load InLegalBERT, which
    can outlast the dev proxy's timeout and bubble up as a 500. Warming in a
    daemon thread keeps startup instant while making the first real request fast.
    """

    def _load() -> None:
        try:
            retrieval_mod._load_index()
            from embeddings import _load_model

            _load_model()
            log.info("Warmup complete: FAISS index + embedding model ready.")
        except FileNotFoundError as e:
            log.warning("Warmup skipped (index not built): %s", e)
        except Exception as e:  # noqa: BLE001 - warmup is best-effort
            log.warning("Warmup failed (non-fatal): %s", e)

    threading.Thread(target=_load, name="model-warmup", daemon=True).start()


# ── Auth (Supabase JWT) ──────────────────────────────────────
import functools


@functools.lru_cache(maxsize=1)
def _jwks_client():
    """Cached client for Supabase's public signing keys (JWKS).

    Modern Supabase projects sign session tokens with asymmetric keys (ES256/
    RS256) and publish the public half here. PyJWKClient fetches + caches them
    and picks the right key by the token's `kid`.
    """
    import jwt  # PyJWT

    url = get_settings().supabase_url.rstrip("/") + "/auth/v1/.well-known/jwks.json"
    return jwt.PyJWKClient(url)


def get_user_id(authorization: str | None = Header(default=None)) -> str:
    """Resolve the caller's user id from their Supabase session JWT.

    Reads the `Authorization: Bearer <token>` header and returns the verified
    `sub` (the user's uuid), so it can be trusted to scope each user's own
    history. Supports both token styles Supabase issues:
      * ES256/RS256 (current default) — verified against the project's public
        JWKS keys;
      * HS256 (legacy) — verified with SUPABASE_JWT_SECRET.
    When no token is sent we fall back to a sentinel "dev-user" so the app still
    runs without auth wired up. A bad/unverifiable token also falls back rather
    than 500-ing the request.
    """
    if not authorization:
        return "dev-user"
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return "dev-user"
    try:
        import jwt  # PyJWT

        # A little leeway absorbs minor clock skew between this server and
        # Supabase (a token's `iat` can look a few seconds in the future).
        leeway = 60
        alg = jwt.get_unverified_header(token).get("alg", "")
        if alg in ("ES256", "RS256", "EdDSA"):
            # Asymmetric: verify with the project's public key for this token.
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
                # No secret and no public key path: read claims unverified so the
                # history layer still works in local dev, but don't trust the id.
                log.warning("SUPABASE_JWT_SECRET not set — accepting JWT without verification.")
                claims = jwt.decode(token, options={"verify_signature": False})
        return claims.get("sub") or "dev-user"
    except Exception as e:  # noqa: BLE001 - a bad token must not 500 the request
        log.warning("JWT verification failed (%s); falling back to dev-user.", e)
        return "dev-user"


# ── Schemas ──────────────────────────────────────────────────
# `conversation_id` continues an existing history thread; omit it (null) to start
# a new one. Every answer echoes the id back so the client can keep appending.
class QueryBody(BaseModel):
    question: str
    conversation_id: str | None = None
    session_id: str | None = None


class FeedbackBody(BaseModel):
    prediction_id: str
    rating: int  # +1 / -1
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


# ── Routes ───────────────────────────────────────────────────
@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "corpus": s.corpus_date_range, "backend": s.vector_backend}


# ── Document analysis (upload → analyze → chat) ──────────────
@app.post("/api/doc/analyze")
async def doc_analyze_route(
    file: UploadFile = File(...),
    session_id: str | None = Form(None),
    user_id: str = Depends(get_user_id),
) -> dict:
    """Extract text from an uploaded legal document, analyze it, and cache it for
    follow-up chat. Grounded only in the document itself (not the case-law corpus).
    """
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
    # Open a "documents" thread for this upload so it shows in history (best-effort).
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
    """Answer a follow-up question grounded in a previously analyzed document."""
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
    """Explain a single legal term in plain language, using the analyzed document for
    context on how it is used. General definitional info, not legal advice."""
    doc = doc_store_mod.get(body.doc_id)
    if not doc:
        raise HTTPException(
            status_code=404,
            detail="Document not found or expired. Please upload it again.",
        )
    explanation = doc_analyze_mod.explain_term(doc, body.term)
    return {"term": body.term, "explanation": explanation}


# ── Full case view (provenance deep-dive) ───────────────────
@app.post("/api/case")
def case_route(body: CaseBody) -> dict:
    """Return a full judgment reconstructed from its chunks, with the cited chunk
    flagged so the UI can show the whole case with the relied-on passage highlighted."""
    try:
        case = case_view_mod.get_case(
            citation=body.citation, case_name=body.case_name, highlight_id=body.highlight_id
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found in the corpus.")
    return case


# ── Legal Q&A assistant (conversational RAG over the corpus) ──
@app.post("/api/chat")
def legal_chat_route(body: ChatBody, user_id: str = Depends(get_user_id)) -> dict:
    """Answer a free-form legal question conversationally, grounded in cases
    retrieved from the corpus. Stateless: the client sends the history each turn."""
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


# ── Statute & Section Finder ─────────────────────────────────
@app.post("/api/statutes")
def statutes_route(body: QueryBody, user_id: str = Depends(get_user_id)) -> dict:
    """Identify governing Acts/sections for a situation, linked to retrieved cases."""
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


@app.post("/api/retrieve")
def retrieve_only(body: QueryBody) -> dict:
    """Phase 1 debug endpoint: reformulate + retrieve, NO prediction."""
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


@app.post("/api/query")
def query(body: QueryBody, user_id: str = Depends(get_user_id)) -> dict:
    s = get_settings()
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")

    # 1) Intake router (brief §6.1)
    route = router_mod.classify(question)
    category = route["category"]

    if category == "not_legal":
        # Greetings / chit-chat / off-topic: keep it short and human, like a chat
        # assistant — no web search, no long detour. Steer back to legal help.
        # Not saved to history (nothing substantive to revisit), but we still echo
        # the thread id so a stray greeting mid-conversation doesn't drop it.
        return {
            "category": "not_legal",
            "conversation_id": body.conversation_id,
            "message": (
                "Hi! I'm Legally AI, and I help with Indian legal matters. Tell me what "
                "happened, ask a legal question, or attach a document and I'll take a look."
            ),
        }

    if category == "general_legal":
        try:
            answer = complete(
                model=s.reasoning_model,
                system=load_prompt("general_legal_v2.txt"),
                user=question,
                temperature=0.3,
                max_tokens=400,
            ).strip()
        except Exception as e:  # noqa: BLE001
            log.error("general_legal answer failed: %s", e)
            answer = "I'm unable to answer that right now. Please try again shortly."
        gl = {"category": "general_legal", "answer": answer, "disclaimer": s.disclaimer}
        gl["conversation_id"] = db.record_turn(
            user_id=user_id,
            conversation_id=body.conversation_id,
            tool="predict",
            user_text=question,
            assistant_text=answer,
            payload=gl,
            session_id=body.session_id,
        )
        return gl

    # 2) Reformulate (brief §6.2)
    reformulated = reformulate_mod.reformulate(question)

    # cache check (brief §16). The cache is global across users, so we still
    # record *this* user's turn before returning, and spread a copy so we never
    # write one user's conversation_id into the shared cached object.
    cached = cache.get(reformulated)
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

    # 3) Retrieve (brief §6.3)
    try:
        result = retrieval_mod.retrieve(reformulated, question)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))

    # 4) Predict + explain (brief §6.4)
    prediction = predict_mod.predict(reformulated, question, result)
    prediction["_model_version"] = predict_mod.MODEL_VERSION

    # 5) Verify citations + weak-retrieval hedge (brief §6.5)
    prediction = verify_mod.verify(prediction, result)

    # 5b) Win/lose (1/0) ensemble (brief §2, §10): blend the precedent vote,
    # the LLM forecast and (if trained) the PredEx classifier, judging
    # confidence by how much the independent signals agree.
    precedent = ensemble_mod.precedent_vote(result)
    clf = classifier_mod.predict_win(reformulated)
    combined = ensemble_mod.combine(
        precedent=precedent,
        llm_outcome=prediction["likely_outcome"],
        classifier=clf,
    )
    prediction_signals = {
        "precedent_vote": precedent,
        "llm_forecast": {
            "likely_outcome": prediction["likely_outcome"],
            "label": ensemble_mod.llm_outcome_to_label(prediction["likely_outcome"]),
        },
        "classifier": clf,
        **combined,
    }

    # If retrieval was weak (verify hedged), don't let the ensemble overclaim.
    if prediction["verification"].get("hedged"):
        prediction_signals["confidence"] = "low"

    # 6) Persist (best-effort) (brief §6.6)
    case_id = db.persist_query(user_id=user_id, raw_text=question, prediction=prediction)

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
        "disclaimer": s.disclaimer,
        "case_id": case_id,
    }
    cache.set(reformulated, response)
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


# ── Conversation history (the returning-user "chat sections") ─
@app.get("/api/conversations")
def conversations(user_id: str = Depends(get_user_id)) -> dict:
    """Sidebar list of the caller's past threads, most-recently-active first."""
    return {"conversations": db.list_conversations(user_id)}


@app.get("/api/conversations/{conversation_id}")
def conversation_detail(conversation_id: str, user_id: str = Depends(get_user_id)) -> dict:
    """Full thread (header + ordered messages) to rehydrate a past session."""
    thread = db.get_conversation(user_id=user_id, conversation_id=conversation_id)
    if thread is None:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return thread


# ── Sessions (workspace-level grouping of the per-tool threads) ───────────────
@app.get("/api/sessions")
def sessions(user_id: str = Depends(get_user_id)) -> dict:
    """Sidebar list of the caller's workspace sessions, most-recently-active first."""
    return {"sessions": db.list_sessions(user_id)}


@app.get("/api/sessions/{session_id}")
def session_detail(session_id: str, user_id: str = Depends(get_user_id)) -> dict:
    """All per-tool threads of one session, each with messages, to rehydrate tabs."""
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
