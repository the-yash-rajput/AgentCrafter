from __future__ import annotations

import json
from typing import Any, Iterable

from type_defs import StatePayload


SESSION_ID_KEY = "session_id"
CONVERSATION_HISTORY_KEY = "conversation_history"

_PREFERRED_USER_KEYS = (
    "message",
    "input",
    "question",
    "query",
    "prompt",
    "user_input",
    "text",
)
_PREFERRED_ASSISTANT_KEYS = (
    "response",
    "answer",
    "output",
    "result",
    "agent_response",
    "llm_response",
    "message",
    "text",
)


def normalize_session_id(session_id: Any) -> str | None:
    if session_id is None:
        return None

    value = str(session_id).strip()
    return value or None


def strip_session_fields(payload: StatePayload | None) -> StatePayload:
    if not isinstance(payload, dict):
        return {}

    sanitized = dict(payload)
    sanitized.pop(SESSION_ID_KEY, None)
    sanitized.pop(CONVERSATION_HISTORY_KEY, None)
    return sanitized


def normalize_conversation_history(history: Any) -> list[dict[str, str]]:
    if not isinstance(history, list):
        return []

    normalized: list[dict[str, str]] = []
    for message in history:
        if not isinstance(message, dict):
            continue

        role = str(message.get("role") or "").strip().lower()
        if role not in {"system", "user", "assistant"}:
            continue

        content = _stringify_content(message.get("content"))
        if not content:
            continue

        normalized.append({"role": role, "content": content})

    return normalized


def build_conversation_turn(
    user_input: StatePayload | None,
    *,
    agent_output: Any = None,
    error: str | None = None,
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []

    user_content = _payload_to_message_content(
        strip_session_fields(user_input),
        preferred_keys=_PREFERRED_USER_KEYS,
    )
    if user_content:
        messages.append({"role": "user", "content": user_content})

    assistant_source = strip_session_fields(agent_output) if isinstance(agent_output, dict) else agent_output
    if error:
        assistant_source = agent_output if agent_output not in (None, {}, []) else {"error": error}
        if isinstance(assistant_source, dict):
            assistant_source = strip_session_fields(assistant_source)

    assistant_content = _payload_to_message_content(
        assistant_source,
        preferred_keys=_PREFERRED_ASSISTANT_KEYS,
    )
    if assistant_content:
        messages.append({"role": "assistant", "content": assistant_content})

    return messages


def flatten_conversation_history(runs: Iterable[Any]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []

    for run in runs:
        stored_turn = normalize_conversation_history(getattr(run, "conversation_turn", None))
        if stored_turn:
            messages.extend(stored_turn)
            continue

        messages.extend(
            build_conversation_turn(
                getattr(run, "input_data", None),
                agent_output=getattr(run, "output_data", None),
                error=getattr(run, "error", None),
            )
        )

    return messages


def _payload_to_message_content(payload: Any, *, preferred_keys: tuple[str, ...]) -> str:
    if isinstance(payload, str):
        return payload.strip()

    if isinstance(payload, dict):
        for key in preferred_keys:
            if key not in payload:
                continue
            content = _stringify_content(payload.get(key))
            if content:
                return content

        if len(payload) == 1:
            only_value = next(iter(payload.values()))
            content = _stringify_content(only_value)
            if content:
                return content

        return _stringify_content(payload)

    return _stringify_content(payload)


def _stringify_content(content: Any) -> str:
    if content is None:
        return ""

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, (int, float, bool)):
        return str(content)

    try:
        return json.dumps(content, ensure_ascii=True, sort_keys=True, default=str)
    except TypeError:
        return str(content).strip()
