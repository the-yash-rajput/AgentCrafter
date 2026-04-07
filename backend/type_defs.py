from __future__ import annotations

from typing import Any, Callable, TypeAlias


JSONMapping: TypeAlias = dict[str, Any]
StatePayload: TypeAlias = dict[str, Any]
ExecutionContext: TypeAlias = dict[str, Any]
NodeRunner: TypeAlias = Callable[[StatePayload], StatePayload]
