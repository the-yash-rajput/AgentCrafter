import json
from typing import Any


JSON_RESPONSE_INSTRUCTION = (
    "Return only valid JSON. Do not wrap it in markdown fences, prose, or explanations."
)


def strip_json_code_fences(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) < 2:
        return stripped

    if lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()

    return stripped


def parse_json_content(content: Any) -> Any:
    if not isinstance(content, str):
        return content

    candidate = strip_json_code_fences(content)

    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Expected valid JSON response but the model returned malformed JSON. "
            f"{exc.msg} at line {exc.lineno} column {exc.colno}. "
            "The response may be truncated; increase max_tokens or disable Parse JSON response."
        ) from exc
