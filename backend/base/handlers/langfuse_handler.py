import logging
from typing import Optional

from base.utilities.langfuse_client_utility import LangfuseClientWrapper


LOGGER = logging.getLogger(__name__)


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
        from langfuse.langchain import CallbackHandler

        kwargs = {}
        if trace_context:
            kwargs["trace_context"] = trace_context
        return CallbackHandler(**kwargs)
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

