"""PythonTaskRunner — public entry point for sandboxed Python execution."""
import pickle
import queue
import multiprocessing as mp
from typing import Any

from task_runner._worker import _run_in_child
from task_runner.errors import (
    PythonTaskConfigurationError,
    PythonTaskError,
    PythonTaskTimeoutError,
)
from task_runner.models import PythonTaskConfig, PythonTaskResult


class PythonTaskRunner:
    """Executes user-supplied Python code inside an isolated sandbox.

    Each call to run() spawns a fresh child process using the "spawn" start
    method (no inherited file descriptors, no shared memory), compiles the code
    through RestrictedPython, applies OS-level resource limits, runs the user's
    run(state) function, and returns the result via a multiprocessing Queue.

    The runner itself is stateless after __init__ and is safe to reuse across
    multiple calls — including from different threads, as the spawn context
    creates independent child processes every time.

    Raises
    ------
    PythonTaskConfigurationError
        The submitted code or state is invalid before execution even starts:
        source too large, state not serializable, state too large, compile
        errors from RestrictedPython, missing run() function, non-dict return,
        output too large to send back.

    PythonTaskError
        The child process failed at runtime (exception inside run(), OOM kill,
        unexpected exit code, or no result on the queue).

    PythonTaskTimeoutError
        The child did not finish within config.timeout_seconds. The runner
        sends SIGTERM, waits 0.5 s, then sends SIGKILL to guarantee the
        process is gone before returning.
    """

    def __init__(self) -> None:
        # "spawn" starts a clean Python interpreter — no forked state, no
        # inherited open file descriptors from the parent Django process.
        self._context = mp.get_context("spawn")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        code: str,
        state: dict[str, Any],
        config: PythonTaskConfig | None = None,
    ) -> PythonTaskResult:
        """Run user code in a sandboxed child process and return the result.

        Parameters
        ----------
        code : str
            Python source that must define a ``def run(state): ...`` function.
            The function receives a deep copy of ``state`` and must return a
            plain dict. Imports are blocked; only the safe helper set is
            available (json, math, re, random, statistics, Counter, Decimal,
            datetime, date, time, timedelta, uuid4, string constants).

        state : dict
            Input data passed to the user's run(state). Must be
            pickle-serializable and within config.max_input_bytes. The child
            receives a deep copy, so mutations inside run() never affect the
            caller's dict.

        config : PythonTaskConfig, optional
            Sandbox limits. Falls back to PythonTaskConfig() defaults when
            omitted (20 s timeout, 256 MB memory, 1 MiB I/O caps).

        Returns
        -------
        PythonTaskResult
            Holds ``output`` (the dict returned by run()) and ``duration_ms``
            (wall-clock time spent inside the child, excluding spawn overhead).
        """
        config = config or PythonTaskConfig()

        self._validate_state(state, config)

        result_queue = self._context.Queue()
        process = self._spawn_child(code, state, config, result_queue)

        try:
            self._wait_for_child(process, config)
            payload = self._read_result(result_queue, process)
            return self._build_result(payload)
        finally:
            result_queue.close()
            result_queue.join_thread()

    # ------------------------------------------------------------------
    # Private steps (called in order by run())
    # ------------------------------------------------------------------

    def _validate_state(self, state: dict[str, Any], config: PythonTaskConfig) -> None:
        """Serialize state and reject it if it is not pickle-safe or too large.

        Runs in the parent process before spawning the child, so an oversized
        or non-serializable state is caught immediately without paying the cost
        of a full process spawn.
        """
        try:
            serialized = pickle.dumps(state)
        except Exception as exc:
            raise PythonTaskConfigurationError(
                f"state is not serializable: {exc}"
            ) from exc

        if len(serialized) > config.max_input_bytes:
            raise PythonTaskConfigurationError(
                f"state exceeds the {config.max_input_bytes // 1024} KiB input size limit"
            )

    def _spawn_child(
        self,
        code: str,
        state: dict[str, Any],
        config: PythonTaskConfig,
        result_queue: mp.Queue,
    ) -> mp.Process:
        """Create, configure, and start the isolated child process.

        The child runs _run_in_child() which applies resource limits, compiles
        the restricted code, and executes run(state). It is started as a daemon
        so it is automatically killed if the parent exits unexpectedly.
        """
        process = self._context.Process(
            target=_run_in_child,
            args=(
                {
                    "code": code,
                    "state": state,
                    "timeout_seconds": config.timeout_seconds,
                    "max_memory_mb": config.max_memory_mb,
                    "max_source_bytes": config.max_source_bytes,
                    "max_output_bytes": config.max_output_bytes,
                    "max_open_files": config.max_open_files,
                    "max_processes": config.max_processes,
                },
                result_queue,
            ),
            daemon=True,
        )
        process.start()
        return process

    def _wait_for_child(self, process: mp.Process, config: PythonTaskConfig) -> None:
        """Block until the child finishes or the wall-clock timeout expires.

        On timeout: sends SIGTERM and waits 0.5 s for a graceful exit, then
        sends SIGKILL if the process is still alive. Raises PythonTaskTimeoutError
        in both cases so the caller always gets a clean error rather than a
        hung thread.
        """
        process.join(config.timeout_seconds)

        if process.is_alive():
            process.terminate()      # polite shutdown request (SIGTERM)
            process.join(0.5)

            if process.is_alive():
                process.kill()       # forceful kill (SIGKILL) — cannot be ignored
                process.join(0.5)

            raise PythonTaskTimeoutError(
                f"Python task exceeded timeout of {config.timeout_seconds:g} seconds"
            )

    def _read_result(self, result_queue: mp.Queue, process: mp.Process) -> dict:
        """Retrieve the result payload that the child put on the IPC queue.

        The child always puts exactly one dict on the queue before it exits
        (either {"ok": True, ...} or {"ok": False, ...}). If the queue is
        empty the process crashed without putting anything — use its exit code
        to produce a meaningful error.
        """
        try:
            return result_queue.get(timeout=1)
        except queue.Empty:
            if process.exitcode not in (0, None):
                raise PythonTaskError(
                    f"Python task runner exited unexpectedly with code {process.exitcode}"
                )
            raise PythonTaskError(
                "Python task runner finished without returning a result"
            )

    def _build_result(self, payload: dict) -> PythonTaskResult:
        """Translate the child's result payload into a PythonTaskResult.

        A payload with ``ok=True`` becomes a successful PythonTaskResult.
        A payload with ``ok=False`` re-raises the original exception type
        (PythonTaskConfigurationError or PythonTaskError) with the message
        that the child serialized before it exited.
        """
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
