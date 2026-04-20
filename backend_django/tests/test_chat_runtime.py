import importlib.util
import os
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


class _TemplateStub:
    def __init__(self, template: str) -> None:
        self.template = template

    def render(self, **state) -> str:
        rendered = self.template
        for key, value in state.items():
            rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
        return rendered


sys.modules.setdefault("jinja2", types.SimpleNamespace(Template=_TemplateStub))

_CHAT_MODULE_PATH = BACKEND_ROOT / "services/runtime/nodes/types/llm/chat.py"
_CHAT_MODULE_SPEC = importlib.util.spec_from_file_location(
    "tests.runtime_chat_module",
    _CHAT_MODULE_PATH,
)
chat_module = importlib.util.module_from_spec(_CHAT_MODULE_SPEC)
assert _CHAT_MODULE_SPEC is not None and _CHAT_MODULE_SPEC.loader is not None
_CHAT_MODULE_SPEC.loader.exec_module(chat_module)
build_chat_llm_node = chat_module.build_chat_llm_node


class ChatRuntimeTests(unittest.TestCase):
    def test_chat_llm_node_allows_repeated_provider_invocations(self) -> None:
        class FakeResponse:
            content = "ok"

        class FakeAzureChatOpenAI:
            invoke_count = 0

            def __init__(self, **_kwargs) -> None:
                pass

            def invoke(self, _messages, config=None):
                del config
                type(self).invoke_count += 1
                return FakeResponse()

        node = build_chat_llm_node(
            {
                "provider": "azure_openai",
                "model": "test-model",
                "user_prompt_template": "{{input}}",
                "output_key": "answer",
            },
            run_id="run-1",
            node_name="chat-node",
        )

        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_API_KEY": "test-key",
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            },
            clear=False,
        ), patch.dict(
            sys.modules,
            {
                "langchain_openai": types.SimpleNamespace(
                    AzureChatOpenAI=FakeAzureChatOpenAI
                ),
            },
        ), patch.object(
            chat_module,
            "_resolve_langfuse_handler",
            return_value=None,
        ), patch.object(
            chat_module,
            "get_langfuse_metadata",
            return_value={},
        ), patch.object(
            chat_module,
            "_build_langchain_messages",
            side_effect=lambda messages: messages,
        ):
            first_result = node({"input": "hello"})
            second_result = node({"input": "again"})

        self.assertEqual(first_result["answer"], "ok")
        self.assertEqual(second_result["answer"], "ok")
        self.assertEqual(FakeAzureChatOpenAI.invoke_count, 2)

    def test_chat_llm_node_prefers_shared_langfuse_handler_from_execution_context(self) -> None:
        class FakeResponse:
            content = "ok"

        class FakeAzureChatOpenAI:
            def __init__(self, **_kwargs) -> None:
                pass

            def invoke(self, _messages, config=None):
                self.config = config
                return FakeResponse()

        shared_handler = object()
        node = build_chat_llm_node(
            {
                "provider": "azure_openai",
                "model": "test-model",
                "user_prompt_template": "{{input}}",
                "output_key": "answer",
            },
            execution_context={
                "langfuse_handler": shared_handler,
                "langfuse_metadata": {"agent_name": "demo-agent"},
            },
            run_id="run-1",
            node_name="chat-node",
        )

        fake_llm = FakeAzureChatOpenAI()
        with patch.dict(
            os.environ,
            {
                "AZURE_OPENAI_API_KEY": "test-key",
                "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
            },
            clear=False,
        ), patch.dict(
            sys.modules,
            {
                "langchain_openai": types.SimpleNamespace(
                    AzureChatOpenAI=lambda **_kwargs: fake_llm
                ),
            },
        ), patch.object(
            chat_module,
            "_build_langchain_messages",
            side_effect=lambda messages: messages,
        ):
            result = node({"input": "hello"})

        self.assertEqual(result["answer"], "ok")
        self.assertEqual(fake_llm.config["callbacks"], [shared_handler])
        self.assertEqual(fake_llm.config["metadata"]["agent_name"], "demo-agent")


if __name__ == "__main__":
    unittest.main()
