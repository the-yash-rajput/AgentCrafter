import asyncio
import copy
import inspect
import math
import multiprocessing as mp
import queue
import time
import traceback
from typing import Any

from RestrictedPython import compile_restricted_exec

from task_runner.errors import (
    PythonTaskConfigurationError,
    PythonTaskError,
    PythonTaskTimeoutError,
)
from task_runner.models import PythonTaskConfig, PythonTaskResult
from task_runner.restricted_globals import build_restricted_globals


def _apply_resource_limits(max_memory_mb: int | None, timeout_seconds: float) -> None:
    try:
        import resource
    except ImportError:
        return

    if max_memory_mb:
        memory_limit = int(max_memory_mb * 1024 * 1024)
        for limit_name in ("RLIMIT_AS", "RLIMIT_DATA"):
            limit = getattr(resource, limit_name, None)
            if limit is None:
                continue
            try:
                resource.setrlimit(limit, (memory_limit, memory_limit))
            except (OSError, ValueError):
                continue

    cpu_limit = getattr(resource, "RLIMIT_CPU", None)
    if cpu_limit is not None:
        hard_limit = max(1, math.ceil(timeout_seconds))
        try:
            resource.setrlimit(cpu_limit, (hard_limit, hard_limit))
        except (OSError, ValueError):
            pass


def _run_in_child(payload: dict[str, Any], result_queue: mp.Queue) -> None:
    started_at = time.perf_counter()
    try:
        _apply_resource_limits(
            max_memory_mb=payload.get("max_memory_mb"),
            timeout_seconds=float(payload.get("timeout_seconds") or 1),
        )

        compile_result = compile_restricted_exec(
            payload["code"],
            filename="<python-inline>",
        )
        if compile_result.errors:
            raise PythonTaskConfigurationError("; ".join(compile_result.errors))

        namespace: dict[str, Any] = {}
        try:
            exec(compile_result.code, build_restricted_globals(), namespace)
        except ImportError as exc:
            if "__import__ not found" in str(exc):
                raise PythonTaskConfigurationError(
                    "Import statements are blocked in python_inline tasks. Use the safe helper set instead."
                ) from exc
            raise

        run_callable = namespace.get("run")
        if not callable(run_callable):
            raise PythonTaskConfigurationError("Inline python must define a callable run(state)")

        state = copy.deepcopy(payload.get("state") or {})
        output = run_callable(state)
        if inspect.isawaitable(output):
            output = asyncio.run(output)
        if not isinstance(output, dict):
            raise PythonTaskConfigurationError("run(state) must return a dict")

        duration_ms = int((time.perf_counter() - started_at) * 1000)
        result_queue.put(
            {
                "ok": True,
                "output": output,
                "duration_ms": duration_ms,
            }
        )
    except Exception as exc:
        result_queue.put(
            {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "traceback": traceback.format_exc(limit=12),
            }
        )


class PythonTaskRunner:
    def __init__(self) -> None:
        self._context = mp.get_context("spawn")

    def run(self, code: str, state: dict[str, Any], config: PythonTaskConfig | None = None) -> PythonTaskResult:
        config = config or PythonTaskConfig()
        result_queue = self._context.Queue()
        process = self._context.Process(
            target=_run_in_child,
            args=(
                {
                    "code": code,
                    "state": state,
                    "timeout_seconds": config.timeout_seconds,
                    "max_memory_mb": config.max_memory_mb,
                },
                result_queue,
            ),
            daemon=True,
        )
        process.start()
        process.join(config.timeout_seconds)

        try:
            if process.is_alive():
                process.terminate()
                process.join(1)
                raise PythonTaskTimeoutError(
                    f"Python task exceeded timeout of {config.timeout_seconds:g} seconds"
                )

            try:
                payload = result_queue.get(timeout=1)
            except queue.Empty:
                if process.exitcode not in (0, None):
                    raise PythonTaskError(
                        f"Python task runner exited unexpectedly with code {process.exitcode}"
                    )
                raise PythonTaskError("Python task runner finished without returning a result")

            if payload.get("ok"):
                return PythonTaskResult(
                    output=payload["output"],
                    duration_ms=int(payload.get("duration_ms") or 0),
                )

            error_message = payload.get("error") or "Unknown Python task failure"
            error_type = payload.get("error_type") or "PythonTaskError"
            if error_type == "PythonTaskConfigurationError":
                raise PythonTaskConfigurationError(error_message)
            raise PythonTaskError(error_message)
        finally:
            result_queue.close()
            result_queue.join_thread()
