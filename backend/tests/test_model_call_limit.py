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

from services.runtime.model_call_limit import (
    MODEL_CALL_LIMIT_CONTEXT_KEY,
    ModelCallLimiter,
    ensure_model_call_limiter,
)
from services.runtime.tool_call_limit import (
    TOOL_CALL_LIMIT_CONTEXT_KEY,
    ToolCallLimiter,
    ensure_tool_call_limiter,
)

_CHAT_MODULE_PATH = BACKEND_ROOT / "services/runtime/nodes/types/llm/chat.py"
_CHAT_MODULE_SPEC = importlib.util.spec_from_file_location(
    "tests.runtime_chat_module",
    _CHAT_MODULE_PATH,
)
chat_module = importlib.util.module_from_spec(_CHAT_MODULE_SPEC)
assert _CHAT_MODULE_SPEC is not None and _CHAT_MODULE_SPEC.loader is not None
_CHAT_MODULE_SPEC.loader.exec_module(chat_module)
build_chat_llm_node = chat_module.build_chat_llm_node


class ModelCallLimitContextTests(unittest.TestCase):
    def test_shallow_copied_execution_context_reuses_same_limiter(self) -> None:
        limiter = ModelCallLimiter(run_limit=15)
        execution_context = {MODEL_CALL_LIMIT_CONTEXT_KEY: limiter}
        nested_execution_context = {
            **execution_context,
            "call_stack": [7],
        }

        self.assertIs(
            ensure_model_call_limiter(nested_execution_context),
            limiter,
        )


class ToolCallLimitContextTests(unittest.TestCase):
    def test_shallow_copied_execution_context_reuses_same_tool_limiter(self) -> None:
        limiter = ToolCallLimiter(run_limit=30)
        execution_context = {TOOL_CALL_LIMIT_CONTEXT_KEY: limiter}
        nested_execution_context = {
            **execution_context,
            "call_stack": [7],
        }

        self.assertIs(
            ensure_tool_call_limiter(nested_execution_context),
            limiter,
        )


class ChatNodeModelCallLimitTests(unittest.TestCase):
    def test_chat_llm_node_stops_invoking_provider_after_limit(self) -> None:
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
            execution_context={
                MODEL_CALL_LIMIT_CONTEXT_KEY: ModelCallLimiter(run_limit=1),
            },
            run_id="run-1",
            node_name="chat-node",
        )
        runtime_events = []

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
            "langfuse_callback_handler",
            return_value=None,
        ), patch.object(
            chat_module,
            "get_langfuse_metadata",
            return_value={},
        ), patch.object(
            chat_module,
            "_build_langchain_messages",
            side_effect=lambda messages: messages,
        ), patch.object(
            chat_module,
            "log_runtime_event",
            side_effect=lambda **kwargs: runtime_events.append(kwargs),
        ):
            first_result = node({"input": "hello"})
            second_result = node({"input": "again"})

        self.assertEqual(first_result["answer"], "ok")
        self.assertEqual(FakeAzureChatOpenAI.invoke_count, 1)
        self.assertIsNone(second_result["answer"])
        self.assertIn("Model call limit exceeded", second_result["_error"])
        self.assertEqual(
            [event["name"] for event in runtime_events],
            [
                "ModelCallLimitMiddleware.before_model",
                "ModelCallLimitMiddleware.after_model",
                "ToolCallLimitMiddleware.after_model",
                "ModelCallLimitMiddleware.before_model",
            ],
        )


if __name__ == "__main__":
    unittest.main()
