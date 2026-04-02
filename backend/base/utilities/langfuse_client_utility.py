import logging
import os
from typing import Any, Optional

from base.utilities.profile_env_utilities import get_environment


LOGGER = logging.getLogger(__name__)
langfuse_logger = logging.getLogger("langfuse")
langfuse_logger.setLevel(logging.DEBUG)


class LangfuseClientWrapper:
    __langfuse_client: Optional[Any] = None
    __langfuse_init_attempted = False

    @classmethod
    def __create_langfuse_client(cls):
        cls.__langfuse_init_attempted = True

        secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        host = os.getenv("LANGFUSE_HOST", "").strip()

        if not public_key or not secret_key:
            LOGGER.info("Langfuse credentials not configured. Skipping client initialization.")
            cls.__langfuse_client = None
            return None

        try:
            from langfuse import Langfuse

            LOGGER.info("Initializing Langfuse client.")
            kwargs = {
                "secret_key": secret_key,
                "public_key": public_key,
                "environment": get_environment(),
            }
            if host:
                kwargs["host"] = host
            cls.__langfuse_client = Langfuse(**kwargs)
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

