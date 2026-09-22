"""Tiny parallel-orchestration helper — a lightweight alternative to a full
agent framework (CrewAI etc.) for a pipeline this size.

`run_parallel({"name": callable, ...})` runs the callables on a thread pool and
returns `{"name": result}`. Threads inherit the caller's context (so the
request id keeps showing in their logs), each task is individually timed, and
fan-out / fan-in is logged so you can see the concurrency in the server log. If
any task raises, the others are awaited and the first error is re-raised
unchanged (same type/behaviour as calling it inline).

Threads — not asyncio — because the two things we overlap are a network-bound
LLM/HTTP call (releases the GIL while waiting) and CPU-bound torch inference;
both make progress on separate threads without rewriting the sync call sites.
"""
from __future__ import annotations

import concurrent.futures as cf
import contextvars
import logging
import time
from typing import Callable, Dict

log = logging.getLogger("legally.parallel")


def _timed(name: str, fn: Callable[[], object]) -> object:
    start = time.perf_counter()
    try:
        return fn()
    finally:
        log.debug("  - task %s took %.0f ms", name, (time.perf_counter() - start) * 1000)


def run_parallel(
    tasks: Dict[str, Callable[[], object]], *, max_workers: int | None = None
) -> Dict[str, object]:
    """Run ``tasks`` concurrently and return their results by name.

    Order of the returned dict matches ``tasks``. Re-raises the first task error
    (after the others settle), preserving its original type.
    """
    if not tasks:
        return {}
    if len(tasks) == 1:
        (name, fn), = tasks.items()
        return {name: fn()}

    names = list(tasks)
    log.info("fan-out: %s", ", ".join(names))
    start = time.perf_counter()
    results: Dict[str, object] = {}
    first_error: Exception | None = None

    with cf.ThreadPoolExecutor(
        max_workers=max_workers or len(tasks), thread_name_prefix="orch"
    ) as ex:
        future_to_name = {}
        for name, fn in tasks.items():
            ctx = contextvars.copy_context()
            future_to_name[ex.submit(ctx.run, _timed, name, fn)] = name

        for future in cf.as_completed(future_to_name):
            name = future_to_name[future]
            try:
                results[name] = future.result()
            except Exception as e:  # noqa: BLE001
                log.warning("task %s raised: %s", name, e)
                if first_error is None:
                    first_error = e

    dur = (time.perf_counter() - start) * 1000
    log.info(
        "fan-in: %d/%d ok in %.0f ms", len(results), len(tasks), dur
    )
    if first_error is not None:
        raise first_error
    return {name: results[name] for name in names}
