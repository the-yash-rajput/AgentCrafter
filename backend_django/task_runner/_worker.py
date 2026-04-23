"""Child-process worker for sandboxed Python execution.

This module is private to task_runner. The only public symbol is
_run_in_child, which is passed as the target to a spawn-context Process.
"""
import asyncio
import copy
import inspect
import math
import os
import pickle
import sys
import threading
import time
import traceback
import types
from typing import Any

import multiprocessing as mp

from RestrictedPython import compile_restricted_exec

from task_runner.errors import (
    PythonTaskConfigurationError,
    PythonTaskError,
)
from task_runner.restricted_globals import build_restricted_globals


def _maxrss_bytes() -> int:
    """Return current process RSS in bytes, platform-aware."""
    try:
        import resource as _r
        rss = _r.getrusage(_r.RUSAGE_SELF).ru_maxrss
        # macOS reports bytes; Linux/BSD report kilobytes
        return rss if sys.platform == "darwin" else rss * 1024
    except Exception:
        return 0


def _start_watchdog(timeout_seconds: float, max_memory_mb: int | None, started_at: float) -> None:
    """Spawn a daemon thread that kills the child process if it blows resource budgets.

    Enforces wall-clock time and RSS memory independently of OS rlimits,
    which are unreliable on macOS for mmap-backed allocations. Calls
    os._exit(137) — a hard, instant kill that the parent interprets as
    an unexpected exit (empty queue + non-zero exitcode → PythonTaskError).
    """
    mem_limit_bytes = int(max_memory_mb * 1024 * 1024) if max_memory_mb else None

    def _watch() -> None:
        while True:
            time.sleep(0.1)
            elapsed = time.perf_counter() - started_at
            if elapsed >= timeout_seconds:
                os._exit(137)
            if mem_limit_bytes is not None and _maxrss_bytes() >= mem_limit_bytes:
                os._exit(137)

    t = threading.Thread(target=_watch, daemon=True, name="sandbox-watchdog")
    t.start()


def _apply_resource_limits(payload: dict[str, Any]) -> None:
    try:
        import resource as _resource
    except ImportError:
        return

    max_memory_mb: int | None = payload.get("max_memory_mb")
    timeout_seconds: float = float(payload.get("timeout_seconds") or 1)
    max_open_files: int = int(payload.get("max_open_files") or 512)
    max_processes: int = int(payload.get("max_processes") or 32)

    def _set(limit_name: str, soft: int, hard: int | None = None) -> None:
        limit = getattr(_resource, limit_name, None)
        if limit is None:
            return
        try:
            _resource.setrlimit(limit, (soft, hard if hard is not None else soft))
        except (OSError, ValueError):
            pass

    if max_memory_mb:
        mem_bytes = int(max_memory_mb * 1024 * 1024)
        _set("RLIMIT_AS", mem_bytes)
        _set("RLIMIT_DATA", mem_bytes)

    _set("RLIMIT_CPU", max(1, math.ceil(timeout_seconds)))
    _set("RLIMIT_NOFILE", max_open_files)
    _set("RLIMIT_NPROC", max_processes)
    _set("RLIMIT_FSIZE", 0)
    _set("RLIMIT_STACK", 8 * 1024 * 1024)


def _run_in_child(payload: dict[str, Any], result_queue: mp.Queue) -> None:
    started_at = time.perf_counter()
    try:
        # --- isolation preamble (before any user code) ---
        os.setpgrp()           # new process group — SIGKILL reaches descendants
        os.umask(0o077)        # created files aren't world-readable

        _apply_resource_limits(payload)
        _start_watchdog(
            timeout_seconds=float(payload.get("timeout_seconds") or 1),
            max_memory_mb=payload.get("max_memory_mb"),
            started_at=started_at,
        )

        max_source_bytes: int = int(payload.get("max_source_bytes") or 65_536)
        max_output_bytes: int = int(payload.get("max_output_bytes") or 1_048_576)

        code: str = payload["code"]
        if len(code.encode("utf-8")) > max_source_bytes:
            raise PythonTaskConfigurationError(
                f"Source code exceeds the {max_source_bytes // 1024} KiB limit"
            )

        compile_result = compile_restricted_exec(code, filename="<python-inline>")
        if compile_result.errors:
            raise PythonTaskConfigurationError("; ".join(compile_result.errors))

        # Reduce recursion limit AFTER compilation — compile_restricted_exec recurses
        # over the AST and needs a normal limit; this cap only applies to user code.
        sys.setrecursionlimit(200)

        namespace: dict[str, Any] = {}
        try:
            exec(compile_result.code, build_restricted_globals(), namespace)
        except ImportError as exc:
            if "__import__ not found" in str(exc):
                raise PythonTaskConfigurationError(
                    "Import statements are blocked in python_inline tasks. "
                    "Use the safe helper set instead."
                ) from exc
            raise

        run_callable = namespace.get("run")
        if not callable(run_callable):
            raise PythonTaskConfigurationError(
                "Inline python must define a callable run(state)"
            )

        state = copy.deepcopy(payload.get("state") or {})
        output = run_callable(state)
        if inspect.isawaitable(output):
            output = asyncio.run(output)
        if not isinstance(output, dict):
            raise PythonTaskConfigurationError("run(state) must return a dict")

        try:
            serialized = pickle.dumps(output)
        except Exception as exc:
            raise PythonTaskConfigurationError(
                f"run(state) return value is not serializable: {exc}"
            ) from exc
        if len(serialized) > max_output_bytes:
            raise PythonTaskConfigurationError(
                f"run(state) output exceeds the {max_output_bytes // 1024} KiB size limit"
            )

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
