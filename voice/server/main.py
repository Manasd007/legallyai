"""Legally AI Voice server: FastAPI + WebRTC entrypoint.

Endpoints:
    POST /api/offer?session_id=  → WebRTC signaling; starts one pipeline per call
    WS   /ws/events/{session_id} → live transcript / latency / status events
    GET  /api/metrics            → P50/P95 per stage (this process)
    POST /api/summary/{session_id} → post-call text summary with full citations
    GET  /api/health

This is a headless service. The UI lives in the Legally AI Next.js frontend
(`frontend/components/VoiceCall.tsx`), which talks to this origin directly —
WebRTC signaling and the events WebSocket both need a real origin, and Vercel
rewrites do not proxy WebSockets. Hence CORS below rather than a proxy.

Run:  uvicorn server.main:app --host 0.0.0.0 --port 7860
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pipecat.transports.smallwebrtc.connection import SmallWebRTCConnection
from pipecat.workers.runner import WorkerRunner

from server import summary as summary_mod
from server.config import get_settings
from server.pipeline.builder import build_pipeline_worker
from server.pipeline.session import SessionHub
from server.telemetry.events import bus
from server.telemetry.turns import TurnLog
from server.tools.legal_search import close_client

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("legallyai.voice.main")

turn_log = TurnLog()
# session_id → SessionHub; kept after the call ends so the summary endpoint can
# still see the transcript. Bounded pruning keeps a long-lived process healthy.
sessions: dict[str, SessionHub] = {}
MAX_KEPT_SESSIONS = 50

_pipeline_tasks: set[asyncio.Task] = set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    missing = [k for k in ("deepgram_api_key", "groq_api_key") if not getattr(s, k)]
    if missing:
        log.warning("Missing keys in .env: %s — calls will fail until set.", ", ".join(missing))
    yield
    for t in _pipeline_tasks:
        t.cancel()
    await close_client()


app = FastAPI(title="Legally AI Voice", version="0.1.0", lifespan=lifespan)

# The frontend is served from a different origin (Next.js dev on :3000, Vercel in
# prod), so every call here is cross-origin. Only the frontend origins are
# allowed — this service holds no cookies, but the offer/summary routes start
# real work and shouldn't be reachable from arbitrary pages.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "rag_base_url": s.rag_base_url,
        "active_sessions": len(_pipeline_tasks),
    }


@app.post("/api/offer")
async def offer(body: dict, session_id: str) -> dict:
    """WebRTC signaling: accept the browser's SDP offer, spin up a pipeline for
    this call, return the answer."""
    sdp, sdp_type = body.get("sdp"), body.get("type")
    if not sdp or not sdp_type:
        raise HTTPException(status_code=400, detail="sdp and type are required")

    if len(sessions) >= MAX_KEPT_SESSIONS:
        # Drop the oldest finished sessions (insertion order = age).
        for old_id in list(sessions)[: len(sessions) - MAX_KEPT_SESSIONS + 1]:
            sessions.pop(old_id, None)

    connection = SmallWebRTCConnection()
    await connection.initialize(sdp=sdp, type=sdp_type)

    hub = SessionHub(session_id=session_id, turn_log=turn_log)
    sessions[session_id] = hub
    worker = build_pipeline_worker(connection, hub)

    async def _run() -> None:
        # Signals belong to uvicorn; the worker cancels itself on client
        # disconnect (wired in the builder), which ends this runner.
        runner = WorkerRunner(handle_sigint=False)
        try:
            await runner.add_workers(worker)
            await runner.run()
        except Exception:  # noqa: BLE001
            log.exception("Pipeline crashed for session %s", session_id)
        finally:
            log.info("Pipeline finished for session %s", session_id)

    task = asyncio.create_task(_run(), name=f"pipeline-{session_id[:8]}")
    _pipeline_tasks.add(task)
    task.add_done_callback(_pipeline_tasks.discard)

    answer = connection.get_answer()
    if answer is None:
        raise HTTPException(status_code=500, detail="WebRTC negotiation failed")
    return answer


@app.websocket("/ws/events/{session_id}")
async def events(websocket: WebSocket, session_id: str) -> None:
    await websocket.accept()
    queue = bus.subscribe(session_id)
    try:
        while True:
            payload = await queue.get()
            await websocket.send_text(payload)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 — a UI socket must never take the server down
        log.debug("events socket closed abnormally for %s", session_id)
    finally:
        bus.unsubscribe(session_id, queue)


@app.get("/api/metrics")
def metrics() -> dict:
    return turn_log.summary()


@app.post("/api/summary/{session_id}")
async def call_summary(session_id: str) -> dict:
    hub = sessions.get(session_id)
    if hub is None:
        raise HTTPException(status_code=404, detail="Unknown session")
    return await summary_mod.build_summary(hub.transcript, hub.state)


if __name__ == "__main__":
    import uvicorn

    s = get_settings()
    uvicorn.run("server.main:app", host=s.host, port=s.port)
