import logging
from importlib import import_module
from typing import Optional

from base.utilities.langfuse_client_utility import LangfuseClientWrapper


LOGGER = logging.getLogger(__name__)


def _get_langfuse_callback_handler_class():
    errors = []

    for module_name in ("langfuse.langchain", "langfuse.callback"):
        try:
            module = import_module(module_name)
            return getattr(module, "CallbackHandler")
        except (AttributeError, ImportError, ModuleNotFoundError) as exc:
            errors.append(f"{module_name}: {exc!r}")

    LOGGER.warning(
        "Langfuse CallbackHandler import unavailable. Tried: %s",
        "; ".join(errors),
    )
    return None


def langfuse_callback_handler(trace_context: Optional[dict] = None):
    """
    Creates a Langfuse CallbackHandler, used to update traces to Langfuse.

    Returns:
        CallbackHandler instance or None when Langfuse is unavailable.
    """
    langfuse_client = LangfuseClientWrapper.get_langfuse_client()
    if langfuse_client is None:
        return None

    try:
        callback_handler_class = _get_langfuse_callback_handler_class()
        if callback_handler_class is None:
            return None

        kwargs = {}
        if trace_context:
            kwargs["trace_context"] = trace_context
        return callback_handler_class(**kwargs)
    except Exception:
        LOGGER.exception("Failed to initialize Langfuse callback handler")
        return None


def get_langfuse_metadata(
    user_id: str = None,
    session_id: str = None,
    tags: list = None,
    **additional_metadata,
) -> dict:
    """
    Helper function to construct Langfuse metadata dictionary.
    Pass during LLM invocation to get trace updates on Langfuse.
    """
    metadata = {}

    if user_id:
        metadata["langfuse_user_id"] = user_id
    if session_id:
        metadata["langfuse_session_id"] = session_id
    if tags:
        metadata["langfuse_tags"] = tags

    metadata.update(additional_metadata)
    return metadata
