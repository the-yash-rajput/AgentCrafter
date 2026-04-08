from __future__ import annotations

import os
from dataclasses import dataclass

from type_defs import ExecutionContext


MODEL_CALL_LIMIT_CONTEXT_KEY = "model_call_limiter"
DEFAULT_MODEL_CALL_LIMIT = int(os.getenv("MODEL_CALL_LIMIT", "15"))


@dataclass(slots=True)
class ModelCallLimiter:
    run_limit: int = DEFAULT_MODEL_CALL_LIMIT
    call_count: int = 0

    def consume(self) -> int:
        if self.call_count >= self.run_limit:
            raise RuntimeError(f"Model call limit exceeded: {self.call_count}/{self.run_limit}")

        self.call_count += 1
        return self.call_count


def ensure_model_call_limiter(
    execution_context: ExecutionContext | None,
    *,
    run_limit: int | None = None,
) -> ModelCallLimiter:
    resolved_limit = run_limit if run_limit is not None else DEFAULT_MODEL_CALL_LIMIT
    if execution_context is None:
        return ModelCallLimiter(run_limit=resolved_limit)

    limiter = execution_context.get(MODEL_CALL_LIMIT_CONTEXT_KEY)
    if isinstance(limiter, ModelCallLimiter):
        return limiter

    limiter = ModelCallLimiter(run_limit=resolved_limit)
    execution_context[MODEL_CALL_LIMIT_CONTEXT_KEY] = limiter
    return limiter


def consume_model_call(
    execution_context: ExecutionContext | None,
    *,
    run_limit: int | None = None,
) -> int:
    limiter = ensure_model_call_limiter(execution_context, run_limit=run_limit)
    return limiter.consume()
