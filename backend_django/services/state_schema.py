from __future__ import annotations

import json
from typing import Any

from type_defs import JSONMapping, StatePayload


def apply_state_schema_defaults(
    input_data: StatePayload | None,
    state_schema: JSONMapping | None,
) -> StatePayload:
    resolved_input = dict(input_data or {})
    schema = state_schema or {}

    initial_state: StatePayload = {}
    for key, field_schema in schema.items():
        if not isinstance(key, str) or not key:
            continue
        if not isinstance(field_schema, dict):
            continue
        if "default" not in field_schema:
            continue
        initial_state[key] = _coerce_default_value(
            field_schema.get("default"),
            str(field_schema.get("type") or "").strip().lower(),
        )

    return {
        **initial_state,
        **resolved_input,
    }


def get_state_schema_session_key(state_schema: JSONMapping | None) -> str | None:
    schema = state_schema or {}
    for key, field_schema in schema.items():
        if not isinstance(key, str) or not isinstance(field_schema, dict):
            continue
        if field_schema.get("is_session_id"):
            return key

    return None


def _coerce_default_value(value: Any, field_type: str) -> Any:
    if value is None:
        return None

    if field_type in {"", "any", "string", "str"}:
        return value

    if field_type in {"bool", "boolean"}:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y"}:
                return True
            if normalized in {"false", "0", "no", "n"}:
                return False
        return bool(value)

    if field_type in {"int", "integer"}:
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    if field_type in {"float", "number"}:
        try:
            return float(value)
        except (TypeError, ValueError):
            return value

    if field_type in {"list", "array", "dict", "object"} and isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value

    return value
