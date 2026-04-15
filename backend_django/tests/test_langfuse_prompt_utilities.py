import os
import unittest
from unittest.mock import patch

from base.utilities.langchain_agent_prompt_utilities import (
    PromptObject,
    get_prompt_with_env,
)
from base.utilities.langfuse_client_utility import LangfuseClientWrapper
from base.utilities.profile_env_utilities import get_environment


class ProfileEnvUtilitiesTests(unittest.TestCase):
    def tearDown(self) -> None:
        LangfuseClientWrapper.close()

    def test_get_environment_maps_prod_to_production(self) -> None:
        with patch.dict(os.environ, {"PROFILE_ENV": "prod"}, clear=False):
            self.assertEqual(get_environment(), "production")

    def test_get_environment_uses_namespace_for_stage(self) -> None:
        with patch.dict(
            os.environ,
            {"PROFILE_ENV": "stage", "ENV_NAMESPACE": "sandbox"},
            clear=False,
        ):
            self.assertEqual(get_environment(), "sandbox")

    def test_get_environment_defaults_to_local(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(get_environment(), "local")


class LangfusePromptUtilitiesTests(unittest.TestCase):
    def tearDown(self) -> None:
        LangfuseClientWrapper.close()

    def test_get_prompt_with_env_falls_back_to_inline_prompt(self) -> None:
        with patch.dict(os.environ, {"LANGFUSE_PROMPT_MANAGEMENT": "false"}, clear=False):
            prompt = get_prompt_with_env("agent/support", fallback_content="Inline prompt")

        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.content, "Inline prompt")
        self.assertEqual(prompt.source, "inline")

    def test_get_prompt_with_env_prefers_langfuse_prompt(self) -> None:
        class FakePrompt:
            def get_langchain_prompt(self):
                return "Prompt from Langfuse"

        with patch.dict(
            os.environ,
            {"LANGFUSE_PROMPT_MANAGEMENT": "true", "PROFILE_ENV": "prod"},
            clear=False,
        ):
            with patch(
                "base.utilities.langchain_agent_prompt_utilities._fetch_prompt_with_label",
                return_value=FakePrompt(),
            ):
                prompt = get_prompt_with_env("agent/support", fallback_content="Inline prompt")

        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.content, "Prompt from Langfuse")
        self.assertEqual(prompt.source, "langfuse")
        self.assertEqual(prompt.label, "production")

    def test_prompt_object_retains_langfuse_source_metadata(self) -> None:
        prompt = PromptObject(
            name="agent/support",
            content="Prompt from Langfuse",
            source="langfuse",
            label="local",
        )

        self.assertEqual(prompt.name, "agent/support")
        self.assertEqual(prompt.source, "langfuse")
        self.assertEqual(prompt.label, "local")
