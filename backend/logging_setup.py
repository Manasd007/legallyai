"""Central logging configuration and small instrumentation helpers.

One `setup_logging()` call configures the whole backend: a timestamped format
that stamps every line with a per-request id (so you can follow one request's
work across modules and threads), env-driven level control, and an optional
rotating file. `log_stage()` times a pipeline step; `new_request_id()` /
`set_request_id()` manage the id that the formatter injects.

The voice service (or any other entrypoint) can import and call `setup_logging()`
too — it is idempotent, so importing modules that log stays safe.
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import sys
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator

_request_id: ContextVar[str] = ContextVar("request_id", default="-")

_CONFIGURED = False


def new_request_id() -> str:
    """Generate, install, and return a fresh short request id for this context."""
    rid = uuid.uuid4().hex[:8]
    _request_id.set(rid)
    return rid


def set_request_id(value: str) -> None:
    _request_id.set(value)


def get_request_id() -> str:
    return _request_id.get()


class _RequestIdFilter(logging.Filter):
    """Make `%(request_id)s` available to the formatter on every record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        record.request_id = _request_id.get()
        return True


def setup_logging() -> None:
    """Configure root logging for the backend. Safe to call more than once.

    Env knobs:
      LOG_LEVEL             app log level (default INFO)
      LOG_LEVEL_THIRDPARTY  level for noisy libs like httpx/litellm (default WARNING)
      LOG_FORMAT            override the log line format
      LOG_FILE              if set, also write to this rotating file
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    fmt = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s %(levelname)-7s [%(request_id)s] %(name)s: %(message)s",
    )
    datefmt = "%Y-%m-%d %H:%M:%S"
    formatter = logging.Formatter(fmt, datefmt=datefmt)
    id_filter = _RequestIdFilter()

    root = logging.getLogger()
    root.setLevel(level)
    for h in list(root.handlers):
        root.removeHandler(h)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(formatter)
    stream.addFilter(id_filter)
    root.addHandler(stream)

    log_file = os.getenv("LOG_FILE", "").strip()
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(id_filter)
        root.addHandler(file_handler)

    third = os.getenv("LOG_LEVEL_THIRDPARTY", "WARNING").upper()
    for noisy in ("httpx", "httpcore", "LiteLLM", "litellm", "urllib3", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(third)

    _CONFIGURED = True
    logging.getLogger("legally.logging").info(
        "Logging configured (level=%s, file=%s)", level, log_file or "off"
    )


@contextmanager
def log_stage(log: logging.Logger, name: str, level: int = logging.INFO) -> Iterator[dict]:
    """Time a pipeline stage and log its duration.

    Yields a mutable dict; whatever you put in it is appended to the completion
    line, e.g. ``with log_stage(log, "retrieve") as st: st["chunks"] = len(...)``.
    On an exception the elapsed time is still logged, tagged as failed, before
    the error propagates.
    """
    extra: dict = {}
    start = time.perf_counter()
    try:
        yield extra
    except Exception:
        dur = (time.perf_counter() - start) * 1000
        log.error("[FAIL] %s after %.0f ms%s", name, dur, _fmt_extra(extra))
        raise
    else:
        dur = (time.perf_counter() - start) * 1000
        log.log(level, "[OK] %s in %.0f ms%s", name, dur, _fmt_extra(extra))


def _fmt_extra(extra: dict) -> str:
    if not extra:
        return ""
    return " (" + ", ".join(f"{k}={v}" for k, v in extra.items()) + ")"
