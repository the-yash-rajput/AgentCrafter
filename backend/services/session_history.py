from __future__ import annotations

import json
from typing import Any

from type_defs import StatePayload


SESSION_ID_KEY = "session_id"
CONVERSATION_HISTORY_KEY = "conversation_history"

_PREFERRED_USER_KEYS = (
    "message",
    "messages",
    "input",
    "question",
    "query",
    "prompt",
    "user_input",
    "text",
)
_PREFERRED_ASSISTANT_KEYS = (
    "final_answer",
    "assistant_message",
    "reply",
    "response",
    "answer",
    "output",
    "result",
    "agent_response",
    "llm_response",
    "structured_response",
    "messages",
    "message",
    "text",
)


def normalize_session_id(session_id: Any) -> int | None:
    if session_id is None:
        return None

    try:
        value = int(str(session_id).strip())
    except (TypeError, ValueError):
        return None

    return value if value > 0 else None


def strip_session_fields(payload: StatePayload | None) -> StatePayload:
    if not isinstance(payload, dict):
        return {}

    sanitized = dict(payload)
    sanitized.pop(SESSION_ID_KEY, None)
    sanitized.pop(CONVERSATION_HISTORY_KEY, None)
    return sanitized


def normalize_conversation_history(history: Any) -> list[dict[str, str]]:
    if isinstance(history, dict):
        history = history.get("messages")

    if not isinstance(history, (list, tuple)):
        return []

    normalized: list[dict[str, str]] = []
    for message in history:
        normalized_message = _normalize_message(message)
        if normalized_message:
            normalized.append(normalized_message)

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
        allowed_roles={"user"},
        allow_structured_fallback=False,
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
        allowed_roles={"assistant"},
        allow_structured_fallback=False,
    )
    if assistant_content:
        messages.append({"role": "assistant", "content": assistant_content})

    return messages


def _payload_to_message_content(
    payload: Any,
    *,
    preferred_keys: tuple[str, ...],
    allowed_roles: set[str] | None = None,
    allow_structured_fallback: bool = True,
) -> str:
    structured_content = _extract_latest_message_content(payload, allowed_roles=allowed_roles)
    if structured_content:
        return structured_content

    if isinstance(payload, str):
        return payload.strip()

    if isinstance(payload, dict):
        for key in preferred_keys:
            if key not in payload:
                continue
            content = _payload_to_message_content(
                payload.get(key),
                preferred_keys=preferred_keys,
                allowed_roles=allowed_roles,
                allow_structured_fallback=allow_structured_fallback,
            )
            if content:
                return content

        if len(payload) == 1:
            only_value = next(iter(payload.values()))
            content = _payload_to_message_content(
                only_value,
                preferred_keys=preferred_keys,
                allowed_roles=allowed_roles,
                allow_structured_fallback=allow_structured_fallback,
            )
            if content:
                return content

        if not allow_structured_fallback:
            return ""

        return _stringify_content(payload)

    if isinstance(payload, (list, tuple)) and not allow_structured_fallback:
        return ""

    return _stringify_content(payload)


def _extract_latest_message_content(payload: Any, *, allowed_roles: set[str] | None = None) -> str:
    messages = normalize_conversation_history(payload)
    if not messages:
        return ""

    normalized_allowed_roles = {role for role in (allowed_roles or {"system", "user", "assistant"})}
    for message in reversed(messages):
        if message["role"] in normalized_allowed_roles:
            return message["content"]

    return ""


def _normalize_message(message: Any) -> dict[str, str] | None:
    if isinstance(message, dict):
        role = _normalize_role(message.get("role") or message.get("type"))
        content = _stringify_content(message.get("content"))
        if role and content:
            return {"role": role, "content": content}
        return None

    role = _normalize_role(
        getattr(message, "role", None)
        or getattr(message, "type", None)
        or type(message).__name__
    )
    content = _stringify_content(getattr(message, "content", None))
    if role and content:
        return {"role": role, "content": content}

    return None


def _normalize_role(role: Any) -> str | None:
    normalized = str(role or "").strip().lower()
    if normalized in {"human", "user", "humanmessage"}:
        return "user"
    if normalized in {"ai", "assistant", "aimessage"}:
        return "assistant"
    if normalized in {"system", "systemmessage"}:
        return "system"
    return None


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
