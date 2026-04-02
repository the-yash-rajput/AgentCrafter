from dataclasses import dataclass
from typing import Any, Optional

DEFAULT_TIMEOUT_SECONDS = 15.0
DEFAULT_MAX_MEMORY_MB = 256


@dataclass(frozen=True, slots=True)
class PythonTaskConfig:
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    max_memory_mb: Optional[int] = DEFAULT_MAX_MEMORY_MB

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

        return cls(timeout_seconds=timeout_seconds, max_memory_mb=max_memory_mb)


@dataclass(frozen=True, slots=True)
class PythonTaskResult:
    output: dict[str, Any]
    duration_ms: int
