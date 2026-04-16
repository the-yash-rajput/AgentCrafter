import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from base.utilities.langfuse_client_utility import LangfuseClientWrapper


LOGGER = logging.getLogger(__name__)


@dataclass
class PromptObject:
    name: str
    content: str
    is_active: bool = True
    source: str = "inline"
    label: Optional[str] = None


def _is_langfuse_prompt_management_enabled() -> bool:
    value = os.getenv("LANGFUSE_PROMPT_MANAGEMENT", "true").strip().lower()
    return value in {"1", "true", "yes"}


def get_langfuse_prompt_object_with_env(prompt_path: str):
    """
    Get the Langfuse prompt object for the current environment.
    """
    if not _is_langfuse_prompt_management_enabled():
        LOGGER.info("LANGFUSE_PROMPT_MANAGEMENT disabled. Skipping Langfuse prompt fetch.")
        return None

    profile_env = os.getenv("PROFILE_ENV", "local").strip().lower() or "local"
    LOGGER.info("Profile environment detected as '%s'", profile_env)

    if profile_env == "prod":
        return _fetch_prompt_with_label(prompt_path, "production")

    if profile_env == "stage":
        primary_label = os.getenv("ENV_NAMESPACE", "cellular").strip().lower() or "cellular"
    else:
        primary_label = "local"

    return _fetch_prompt_with_label(prompt_path, primary_label)


def get_prompt_with_env(prompt_path: str, fallback_content: Optional[str] = None):
    """
    Fetch a Langfuse prompt based on environment, with inline fallback.
    """
    profile_env = os.getenv("PROFILE_ENV", "local").strip().lower() or "local"
    LOGGER.info("Profile environment detected as '%s'", profile_env)

    langfuse_prompt_management = _is_langfuse_prompt_management_enabled()
    LOGGER.info(
        "LANGFUSE_PROMPT_MANAGEMENT detected as '%s'",
        langfuse_prompt_management,
    )

    if langfuse_prompt_management:
        if profile_env == "prod":
            langfuse_prompt = _fetch_prompt_with_label(prompt_path, "production")
            if langfuse_prompt:
                return _convert_langfuse_to_prompt_object(
                    langfuse_prompt,
                    prompt_path,
                    "production",
                )
            LOGGER.info(
                "%s: not available on production, falling back to inline prompt",
                prompt_path,
            )
        else:
            if profile_env == "stage":
                primary_label = os.getenv("ENV_NAMESPACE", "cellular").strip().lower() or "cellular"
            else:
                primary_label = "local"

            langfuse_prompt = _fetch_prompt_with_label(prompt_path, primary_label)
            if langfuse_prompt:
                return _convert_langfuse_to_prompt_object(
                    langfuse_prompt,
                    prompt_path,
                    primary_label,
                )

            LOGGER.info(
                "%s: not available on %s, falling back to production prompt",
                prompt_path,
                primary_label,
            )
            langfuse_prompt = _fetch_prompt_with_label(prompt_path, "production")
            if langfuse_prompt:
                return _convert_langfuse_to_prompt_object(
                    langfuse_prompt,
                    prompt_path,
                    "production",
                )

            LOGGER.info(
                "%s: not available on production, falling back to inline prompt",
                prompt_path,
            )

    if fallback_content:
        LOGGER.info("Using inline fallback prompt for '%s'", prompt_path)
        return PromptObject(
            name=prompt_path,
            content=str(fallback_content),
            source="inline",
        )

    LOGGER.warning("No prompt found for '%s'", prompt_path)
    return None


def _convert_langfuse_to_prompt_object(
    langfuse_prompt: Any,
    prompt_path: str,
    env_label: Optional[str] = None,
):
    """Helper function to convert Langfuse prompt to Prompt-like object."""
    try:
        langfuse_prompt_content = None

        if hasattr(langfuse_prompt, "get_langchain_prompt"):
            langfuse_prompt_content = langfuse_prompt.get_langchain_prompt()

        if not langfuse_prompt_content:
            prompt_payload = getattr(langfuse_prompt, "prompt", None)
            if isinstance(prompt_payload, str):
                langfuse_prompt_content = prompt_payload
            elif hasattr(prompt_payload, "prompt"):
                langfuse_prompt_content = prompt_payload.prompt

        if langfuse_prompt_content:
            LOGGER.info(
                "Fetched prompt from Langfuse for '%s' with label '%s'",
                prompt_path,
                env_label,
            )
            return PromptObject(
                name=prompt_path,
                content=str(langfuse_prompt_content),
                source="langfuse",
                label=env_label,
            )

        LOGGER.warning("No content found in Langfuse prompt for '%s'", prompt_path)
        return None
    except Exception:
        LOGGER.exception(
            "Error converting Langfuse prompt to Prompt object for '%s'",
            prompt_path,
        )
        return None


def _fetch_prompt_with_label(
    prompt_path: str,
    env_label: str,
):
    """Helper function to fetch prompt from Langfuse with a specific label."""
    try:
        langfuse_client = LangfuseClientWrapper.get_langfuse_client()
        if langfuse_client is None:
            return None
        LOGGER.info(
            "Fetching prompt '%s' with label '%s' from Langfuse",
            prompt_path,
            env_label,
        )
        return langfuse_client.get_prompt(prompt_path, label=env_label)
    except Exception as exc:
        LOGGER.warning(
            "Failed to get prompt '%s' with label '%s': %s",
            prompt_path,
            env_label,
            exc,
        )
        return None


def convert_str_to_text_prompt_client(prompt):
    """Convert a string to a Langfuse TextPromptClient when the SDK is installed."""
    try:
        from langfuse.api.resources.prompts.types.prompt import Prompt_Text
        from langfuse.model import TextPromptClient

        prompt_text = Prompt_Text(
            prompt=prompt,
            name="agent",
            version=1,
            config={},
            labels=[],
            tags=[],
            type="text",
        )
        return TextPromptClient(prompt_text)
    except Exception:
        return prompt
