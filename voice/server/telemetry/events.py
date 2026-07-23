"""Session event bus: pushes live transcript, latency and summary events to the
browser UI over a plain WebSocket (side channel in the architecture diagram,
context doc §2).

Audio flows over WebRTC; UI state flows here. Keeping them separate means a
dropped UI socket never disturbs the audio pipeline, and the web client stays a
dumb renderer.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

log = logging.getLogger("legallyai.voice.events")


class EventBus:
    """Fan-out of JSON events to every UI socket attached to a session."""

    def __init__(self) -> None:
        self._queues: dict[str, list[asyncio.Queue]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=256)
        self._queues.setdefault(session_id, []).append(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        subs = self._queues.get(session_id, [])
        if q in subs:
            subs.remove(q)
        if not subs:
            self._queues.pop(session_id, None)

    def publish(self, session_id: str, event_type: str, data: dict[str, Any]) -> None:
        """Non-blocking publish; a slow/full UI queue drops events rather than
        ever back-pressuring the audio pipeline."""
        payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
        for q in self._queues.get(session_id, []):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                log.debug("UI queue full for %s; dropping %s event", session_id, event_type)


bus = EventBus()
