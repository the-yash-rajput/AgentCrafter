from dataclasses import dataclass
from typing import Any, Optional

DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_MAX_MEMORY_MB = 256
DEFAULT_MAX_SOURCE_BYTES = 65_536       # 64 KiB
DEFAULT_MAX_INPUT_BYTES = 1_048_576     # 1 MiB
DEFAULT_MAX_OUTPUT_BYTES = 1_048_576    # 1 MiB
DEFAULT_MAX_OPEN_FILES = 512
DEFAULT_MAX_PROCESSES = 32


@dataclass(frozen=True, slots=True)
class PythonTaskConfig:
    """Sandbox limits for a single python_inline task execution.

    All limits are enforced inside the isolated child process before any user
    code runs. Invalid or out-of-range values supplied via from_inline_config()
    silently fall back to the defaults listed below.

    Parameters
    ----------
    timeout_seconds : float
        Wall-clock budget for the entire child process (compile + run).
        The parent sends SIGTERM when this expires, then SIGKILL 0.5 s later
        if the child hasn't exited. Default: 20 s.

    max_memory_mb : int or None
        Virtual-address-space ceiling applied via RLIMIT_AS and RLIMIT_DATA.
        The child is killed by the OS if it tries to map more memory than this.
        Set to None to disable the memory cap (not recommended). Default: 256 MB.

    max_source_bytes : int
        Maximum UTF-8 byte length of the submitted source code string.
        Rejects oversized code before compilation so the RestrictedPython AST
        transformer never has to process a multi-megabyte file. Default: 64 KiB.

    max_input_bytes : int
        Maximum pickle-serialized size of the state dict passed into run(state).
        Checked in the parent before the child is spawned, so an attacker cannot
        use a huge state to exhaust IPC queue memory. Default: 1 MiB.

    max_output_bytes : int
        Maximum pickle-serialized size of the dict returned by run(state).
        Checked inside the child after the user function returns, before the
        result is put on the IPC queue. Default: 1 MiB.

    max_open_files : int
        File-descriptor ceiling enforced via RLIMIT_NOFILE. Prevents the child
        from exhausting the system fd table through repeated open() calls (even
        though open() is not exposed, C extensions or subprocesses could try).
        Default: 512.

    max_processes : int
        Process / thread ceiling enforced via RLIMIT_NPROC. Blocks fork-bomb
        patterns if a native extension somehow bypasses the import restrictions.
        Default: 32.
    """

    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_memory_mb: Optional[int] = DEFAULT_MAX_MEMORY_MB
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES
    max_input_bytes: int = DEFAULT_MAX_INPUT_BYTES
    max_output_bytes: int = DEFAULT_MAX_OUTPUT_BYTES
    max_open_files: int = DEFAULT_MAX_OPEN_FILES
    max_processes: int = DEFAULT_MAX_PROCESSES

    @classmethod
    def from_inline_config(cls, config: Optional[dict]) -> "PythonTaskConfig":
        config = config or {}

        timeout_seconds = config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
        try:
            timeout_seconds = float(timeout_seconds)
        except (TypeError, ValueError):
            timeout_seconds = DEFAULT_TIMEOUT_SECONDS
        if timeout_seconds <= 0:
            timeout_seconds = DEFAULT_TIMEOUT_SECONDS

        max_memory_mb = config.get("max_memory_mb", DEFAULT_MAX_MEMORY_MB)
        try:
            max_memory_mb = int(max_memory_mb) if max_memory_mb not in ("", None) else DEFAULT_MAX_MEMORY_MB
        except (TypeError, ValueError):
            max_memory_mb = DEFAULT_MAX_MEMORY_MB
        if max_memory_mb is not None and max_memory_mb <= 0:
            max_memory_mb = DEFAULT_MAX_MEMORY_MB

        max_source_bytes = config.get("max_source_bytes", DEFAULT_MAX_SOURCE_BYTES)
        try:
            max_source_bytes = int(max_source_bytes)
        except (TypeError, ValueError):
            max_source_bytes = DEFAULT_MAX_SOURCE_BYTES
        if max_source_bytes <= 0:
            max_source_bytes = DEFAULT_MAX_SOURCE_BYTES

        max_input_bytes = config.get("max_input_bytes", DEFAULT_MAX_INPUT_BYTES)
        try:
            max_input_bytes = int(max_input_bytes)
        except (TypeError, ValueError):
            max_input_bytes = DEFAULT_MAX_INPUT_BYTES
        if max_input_bytes <= 0:
            max_input_bytes = DEFAULT_MAX_INPUT_BYTES

        max_output_bytes = config.get("max_output_bytes", DEFAULT_MAX_OUTPUT_BYTES)
        try:
            max_output_bytes = int(max_output_bytes)
        except (TypeError, ValueError):
            max_output_bytes = DEFAULT_MAX_OUTPUT_BYTES
        if max_output_bytes <= 0:
            max_output_bytes = DEFAULT_MAX_OUTPUT_BYTES

        max_open_files = config.get("max_open_files", DEFAULT_MAX_OPEN_FILES)
        try:
            max_open_files = int(max_open_files)
        except (TypeError, ValueError):
            max_open_files = DEFAULT_MAX_OPEN_FILES
        if max_open_files <= 0:
            max_open_files = DEFAULT_MAX_OPEN_FILES

        max_processes = config.get("max_processes", DEFAULT_MAX_PROCESSES)
        try:
            max_processes = int(max_processes)
        except (TypeError, ValueError):
            max_processes = DEFAULT_MAX_PROCESSES
        if max_processes <= 0:
            max_processes = DEFAULT_MAX_PROCESSES

        return cls(
            timeout_seconds=timeout_seconds,
            max_memory_mb=max_memory_mb,
            max_source_bytes=max_source_bytes,
            max_input_bytes=max_input_bytes,
            max_output_bytes=max_output_bytes,
            max_open_files=max_open_files,
            max_processes=max_processes,
        )


@dataclass(frozen=True, slots=True)
class PythonTaskResult:
    output: dict[str, Any]
    duration_ms: int
