import unittest
from unittest.mock import patch

from base.utilities.langfuse_prompt_catalog_utility import list_langfuse_prompt_names
from base.utilities.langfuse_client_utility import LangfuseClientWrapper


class LangfusePromptCatalogUtilityTests(unittest.TestCase):
    def tearDown(self) -> None:
        LangfuseClientWrapper.close()

    def test_returns_sorted_unique_names_from_api_list(self) -> None:
        class FakeResponse:
            data = [
                {"name": "beta"},
                {"name": "alpha"},
                {"name": "alpha"},
            ]

        class FakePromptsApi:
            @staticmethod
            def list(limit=None):
                self_limit = limit
                assert self_limit == 100
                return FakeResponse()

        class FakeApi:
            prompts = FakePromptsApi()

        class FakeClient:
            api = FakeApi()

        with patch(
            "base.utilities.langfuse_prompt_catalog_utility.LangfuseClientWrapper.get_langfuse_client",
            return_value=FakeClient(),
        ):
            self.assertEqual(
                list_langfuse_prompt_names(),
                (["alpha", "beta"], "langfuse", None),
            )

    def test_returns_empty_list_when_client_missing(self) -> None:
        with patch(
            "base.utilities.langfuse_prompt_catalog_utility.LangfuseClientWrapper.get_langfuse_client",
            return_value=None,
        ):
            self.assertEqual(
                list_langfuse_prompt_names(),
                ([], "none", "Langfuse client not configured"),
            )

    def test_returns_live_error_when_langfuse_listing_fails(self) -> None:
        class FakePromptsApi:
            @staticmethod
            def list(limit=None):
                raise ValueError("Expecting value: line 1 column 1 (char 0)")

        class FakeApi:
            prompts = FakePromptsApi()

        class FakeClient:
            api = FakeApi()

        with patch(
            "base.utilities.langfuse_prompt_catalog_utility.LangfuseClientWrapper.get_langfuse_client",
            return_value=FakeClient(),
        ):
            names, source, error = list_langfuse_prompt_names()

        self.assertEqual(names, [])
        self.assertEqual(source, "none")
        self.assertIn("failed", error)
