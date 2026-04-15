import os
import unittest
from unittest.mock import patch

from base.utilities.langfuse_client_utility import LangfuseClientWrapper


class LangfuseClientUtilityTests(unittest.TestCase):
    def tearDown(self) -> None:
        LangfuseClientWrapper.close()

    def test_prefers_base_url_and_uses_singleton_client_when_available(self) -> None:
        captured_kwargs = {}
        singleton_client = object()

        class FakeLangfuse:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        with patch.dict(
            os.environ,
            {
                "LANGFUSE_PUBLIC_KEY": "pk-test",
                "LANGFUSE_SECRET_KEY": "sk-test",
                "LANGFUSE_BASE_URL": "https://cloud.langfuse.com",
                "LANGFUSE_HOST": "https://legacy.langfuse.example",
            },
            clear=False,
        ), patch(
            "base.utilities.langfuse_client_utility._load_langfuse_sdk",
            return_value=(FakeLangfuse, lambda: singleton_client),
        ):
            client = LangfuseClientWrapper.get_langfuse_client()

        self.assertIs(client, singleton_client)
        self.assertEqual(captured_kwargs["base_url"], "https://cloud.langfuse.com")
        self.assertNotIn("host", captured_kwargs)

    def test_falls_back_to_host_and_direct_client_when_singleton_missing(self) -> None:
        captured_kwargs = {}

        class FakeLangfuse:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        with patch.dict(
            os.environ,
            {
                "LANGFUSE_PUBLIC_KEY": "pk-test",
                "LANGFUSE_SECRET_KEY": "sk-test",
                "LANGFUSE_BASE_URL": "",
                "LANGFUSE_HOST": "https://legacy.langfuse.example",
            },
            clear=False,
        ), patch(
            "base.utilities.langfuse_client_utility._load_langfuse_sdk",
            return_value=(FakeLangfuse, lambda: None),
        ):
            client = LangfuseClientWrapper.get_langfuse_client()

        self.assertIsInstance(client, FakeLangfuse)
        self.assertEqual(captured_kwargs["host"], "https://legacy.langfuse.example")
