from __future__ import annotations
from typing import Any
from langchain.agents.middleware import (
        ModelCallLimitMiddleware,
        ToolCallLimitMiddleware,
        wrap_tool_call,
    )
from langchain_core.messages import ToolMessage


def build_agent_middlewares(*, tool_run_limit: int = 30, model_run_limit: int = 15) -> list[Any]:
    
    @wrap_tool_call
    def handle_tool_errors(request, handler):
        """Handle tool execution errors with custom messages."""
        try:
            return handler(request)
        except Exception as exc:
            tool_call = getattr(request, "tool_call", {}) or {}
            return ToolMessage(
                content=(
                    "Tool error: The tool failed to run due to "
                    f"({str(exc)}). Do not try this tool again."
                ),
                tool_call_id=tool_call.get("id"),
            )

    return [
        ToolCallLimitMiddleware(run_limit=tool_run_limit),
        handle_tool_errors,
        ModelCallLimitMiddleware(run_limit=model_run_limit),
    ]

