from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

log = logging.getLogger("legallyai.voice.events")


class EventBus:

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
        payload = json.dumps({"type": event_type, **data}, ensure_ascii=False)
        for q in self._queues.get(session_id, []):
            try:
                q.put_nowait(payload)
            except asyncio.QueueFull:
                log.debug("UI queue full for %s; dropping %s event", session_id, event_type)


bus = EventBus()
