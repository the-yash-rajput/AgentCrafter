import logging
import os
from typing import Any, Optional

from base.utilities.profile_env_utilities import get_environment


LOGGER = logging.getLogger(__name__)
langfuse_logger = logging.getLogger("langfuse")
langfuse_logger.setLevel(logging.DEBUG)


def _load_langfuse_sdk():
    from langfuse import Langfuse

    try:
        from langfuse import get_client
    except ImportError:
        get_client = None

    return Langfuse, get_client


class LangfuseClientWrapper:
    __langfuse_client: Optional[Any] = None
    __langfuse_init_attempted = False

    @classmethod
    def __create_langfuse_client(cls):
        cls.__langfuse_init_attempted = True

        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        base_url = os.getenv("LANGFUSE_BASE_URL", "").strip()
        host = os.getenv("LANGFUSE_HOST", "").strip()

        if not public_key or not secret_key:
            LOGGER.info("Langfuse credentials not configured. Skipping client initialization.")
            cls.__langfuse_client = None
            return None

        try:
            Langfuse, get_client = _load_langfuse_sdk()

            LOGGER.info("Initializing Langfuse client.")
            kwargs = {
                "secret_key": secret_key,
                "public_key": public_key,
                "environment": get_environment(),
            }
            if base_url:
                kwargs["base_url"] = base_url
            elif host:
                kwargs["host"] = host
            client = Langfuse(**kwargs)

            if callable(get_client):
                singleton_client = get_client()
                cls.__langfuse_client = singleton_client or client
            else:
                cls.__langfuse_client = client
        except Exception:
            LOGGER.exception("Failed to initialize Langfuse client")
            cls.__langfuse_client = None

        return cls.__langfuse_client

    @classmethod
    def get_langfuse_client(cls):
        """
        Returns the Langfuse client instance.
        """
        if cls.__langfuse_client is None and not cls.__langfuse_init_attempted:
            cls.__create_langfuse_client()
        return cls.__langfuse_client

    @classmethod
    def close(cls):
        cls.__langfuse_client = None
        cls.__langfuse_init_attempted = False
        LOGGER.info("Langfuse client closed.")
