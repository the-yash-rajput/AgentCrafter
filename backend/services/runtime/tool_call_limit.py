from __future__ import annotations

import os
from dataclasses import dataclass

from type_defs import ExecutionContext


TOOL_CALL_LIMIT_CONTEXT_KEY = "tool_call_limiter"
DEFAULT_TOOL_CALL_LIMIT = int(os.getenv("TOOL_CALL_LIMIT", "30"))


@dataclass(slots=True)
class ToolCallLimiter:
    run_limit: int = DEFAULT_TOOL_CALL_LIMIT
    call_count: int = 0

    def consume(self) -> int:
        if self.call_count >= self.run_limit:
            raise RuntimeError(f"Tool call limit exceeded: {self.call_count}/{self.run_limit}")

        self.call_count += 1
        return self.call_count


def ensure_tool_call_limiter(
    execution_context: ExecutionContext | None,
    *,
    run_limit: int | None = None,
) -> ToolCallLimiter:
    resolved_limit = run_limit if run_limit is not None else DEFAULT_TOOL_CALL_LIMIT
    if execution_context is None:
        return ToolCallLimiter(run_limit=resolved_limit)

    limiter = execution_context.get(TOOL_CALL_LIMIT_CONTEXT_KEY)
    if isinstance(limiter, ToolCallLimiter):
        return limiter

    limiter = ToolCallLimiter(run_limit=resolved_limit)
    execution_context[TOOL_CALL_LIMIT_CONTEXT_KEY] = limiter
    return limiter


def consume_tool_call(
    execution_context: ExecutionContext | None,
    *,
    run_limit: int | None = None,
) -> int:
    limiter = ensure_tool_call_limiter(execution_context, run_limit=run_limit)
    return limiter.consume()
