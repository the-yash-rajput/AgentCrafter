import logging
from typing import Any

from base.utilities.langfuse_client_utility import LangfuseClientWrapper


LOGGER = logging.getLogger(__name__)
PROMPT_LIST_LIMIT = 100


def _extract_prompt_name(prompt: Any) -> str | None:
    if prompt is None:
        return None

    for key in ("name", "prompt_name", "id"):
        value = getattr(prompt, key, None)
        if isinstance(value, str) and value.strip():
            return value.strip()

    if isinstance(prompt, dict):
        for key in ("name", "prompt_name", "id"):
            value = prompt.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        nested_prompt = prompt.get("prompt")
        if isinstance(nested_prompt, dict):
            for key in ("name", "prompt_name", "id"):
                value = nested_prompt.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    return None


def list_langfuse_prompt_names() -> tuple[list[str], str, str | None]:
    """
    Return unique prompt names from Langfuse.

    The SDK surface has varied across versions, so this utility tries a few
    common access paths and returns live Langfuse results only.
    """
    client = LangfuseClientWrapper.get_langfuse_client()
    if client is None:
        return [], "none", "Langfuse client not configured"

    prompt_items: Any = None
    last_error: str | None = None

    try:
        if hasattr(client, "api") and hasattr(client.api, "prompts"):
            prompts_api = client.api.prompts
            if hasattr(prompts_api, "list"):
                response = prompts_api.list(limit=PROMPT_LIST_LIMIT)
                prompt_items = getattr(response, "data", response)
    except Exception as exc:
        last_error = f"client.api.prompts.list failed: {exc}"
        LOGGER.warning(last_error)

    if prompt_items is None:
        try:
            if hasattr(client, "prompts") and hasattr(client.prompts, "list"):
                response = client.prompts.list(limit=PROMPT_LIST_LIMIT)
                prompt_items = getattr(response, "data", response)
        except Exception as exc:
            last_error = f"client.prompts.list failed: {exc}"
            LOGGER.warning(last_error)

    if prompt_items is None:
        return [], "none", last_error

    names = {
        name
        for item in (prompt_items or [])
        if (name := _extract_prompt_name(item))
    }
    if names:
        return sorted(names), "langfuse", None

    return [], "langfuse", last_error or "Langfuse returned no prompt names"
