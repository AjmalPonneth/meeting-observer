from __future__ import annotations

from worker.runtime.worker_runtime import WorkerRuntime

_runtime: WorkerRuntime | None = None


async def get_or_start_worker_runtime() -> WorkerRuntime:
    global _runtime

    if _runtime is None:
        _runtime = WorkerRuntime()
        await _runtime.start()

    return _runtime


async def stop_worker_runtime() -> None:
    global _runtime

    runtime = _runtime
    _runtime = None

    if runtime is None:
        return

    await runtime.stop()
