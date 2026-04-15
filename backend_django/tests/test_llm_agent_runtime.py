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

_AGENT_MODULE_PATH = BACKEND_ROOT / "services/runtime/nodes/types/llm/agent.py"
_AGENT_MODULE_SPEC = importlib.util.spec_from_file_location(
    "tests.runtime_agent_llm_module",
    _AGENT_MODULE_PATH,
)
agent_module = importlib.util.module_from_spec(_AGENT_MODULE_SPEC)
assert _AGENT_MODULE_SPEC is not None and _AGENT_MODULE_SPEC.loader is not None
_AGENT_MODULE_SPEC.loader.exec_module(agent_module)
build_agent_llm_node = agent_module.build_agent_llm_node


class _Message:
    def __init__(self, content=None, tool_call_id=None):
        self.content = content
        self.tool_call_id = tool_call_id


class HumanMessage(_Message):
    type = "human"


class AIMessage(_Message):
    type = "ai"


class SystemMessage(_Message):
    type = "system"


class ToolMessage(_Message):
    type = "tool"


class ToolCallLimitMiddleware:
    def __init__(self, *, run_limit):
        self.run_limit = run_limit


class ModelCallLimitMiddleware:
    def __init__(self, *, run_limit):
        self.run_limit = run_limit


def wrap_tool_call(fn):
    return fn


class AgentLLMRuntimeTests(unittest.TestCase):
    def test_agent_llm_node_uses_create_agent_with_middleware(self) -> None:
        captured: dict = {}

        class FakeAzureChatOpenAI:
            def __init__(self, **kwargs):
                captured["llm_kwargs"] = kwargs

        def fake_create_agent(**kwargs):
            captured["create_agent_kwargs"] = kwargs

            class FakeRuntimeAgent:
                def invoke(self, payload, config=None):
                    captured["invoke_payload"] = payload
                    captured["invoke_config"] = config
                    return {
                        "messages": [
                            HumanMessage(content="Earlier question"),
                            AIMessage(content="Agent answer"),
                        ]
                    }

            return FakeRuntimeAgent()

        shared_handler = object()
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
                "langchain.agents": types.SimpleNamespace(create_agent=fake_create_agent),
                "langchain.agents.middleware": types.SimpleNamespace(
                    ToolCallLimitMiddleware=ToolCallLimitMiddleware,
                    ModelCallLimitMiddleware=ModelCallLimitMiddleware,
                    wrap_tool_call=wrap_tool_call,
                ),
                "langchain_core.messages": types.SimpleNamespace(
                    HumanMessage=HumanMessage,
                    AIMessage=AIMessage,
                    SystemMessage=SystemMessage,
                    ToolMessage=ToolMessage,
                ),
                "langchain_openai": types.SimpleNamespace(
                    AzureChatOpenAI=FakeAzureChatOpenAI
                ),
            },
        ), patch.object(
            agent_module,
            "langfuse_callback_handler",
            side_effect=AssertionError("unexpected fallback handler creation"),
        ), patch.object(
            agent_module,
            "get_langfuse_metadata",
            return_value={},
        ):
            node = build_agent_llm_node(
                {
                    "provider": "azure_openai",
                    "model": "test-model",
                    "system_prompt": "You are a helpful assistant.",
                    "user_prompt_template": "Hello {{name}}",
                    "output_key": "answer",
                },
                execution_context={
                    "langfuse_handler": shared_handler,
                    "langfuse_metadata": {"agent_name": "demo-agent"},
                },
                run_id="run-1",
                node_name="chat-node",
            )
            result = node({
                "name": "Ada",
                "conversation_history": [
                    {"role": "assistant", "content": "Earlier answer"},
                ],
            })

        self.assertEqual(result["answer"], "Agent answer")
        self.assertEqual(captured["create_agent_kwargs"]["tools"], [])
        self.assertEqual(captured["create_agent_kwargs"]["system_prompt"], "You are a helpful assistant.")
        self.assertTrue(captured["create_agent_kwargs"]["debug"])
        self.assertEqual(captured["create_agent_kwargs"]["name"], "chat-node")
        self.assertEqual(len(captured["create_agent_kwargs"]["middleware"]), 3)
        self.assertEqual(
            [type(middleware).__name__ if not callable(middleware) else middleware.__name__ for middleware in captured["create_agent_kwargs"]["middleware"]],
            ["ToolCallLimitMiddleware", "handle_tool_errors", "ModelCallLimitMiddleware"],
        )
        self.assertEqual(captured["invoke_config"]["callbacks"], [shared_handler])
        self.assertEqual(captured["invoke_config"]["metadata"]["agent_name"], "demo-agent")
        self.assertEqual(len(captured["invoke_payload"]["messages"]), 2)

    def test_agent_llm_node_uses_structured_output_schema_when_configured(self) -> None:
        captured: dict = {}
        structured_response = {
            "summary": "Agent answer",
            "confidence": 0.98,
        }

        class FakeAzureChatOpenAI:
            def __init__(self, **kwargs):
                captured["llm_kwargs"] = kwargs

        def fake_create_agent(**kwargs):
            captured["create_agent_kwargs"] = kwargs

            class FakeRuntimeAgent:
                def invoke(self, payload, config=None):
                    captured["invoke_payload"] = payload
                    captured["invoke_config"] = config
                    return {
                        "messages": [
                            HumanMessage(content="Earlier question"),
                            AIMessage(content="This free-form answer should be ignored"),
                        ],
                        "structured_response": structured_response,
                    }

            return FakeRuntimeAgent()

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
                "langchain.agents": types.SimpleNamespace(create_agent=fake_create_agent),
                "langchain.agents.middleware": types.SimpleNamespace(
                    ToolCallLimitMiddleware=ToolCallLimitMiddleware,
                    ModelCallLimitMiddleware=ModelCallLimitMiddleware,
                    wrap_tool_call=wrap_tool_call,
                ),
                "langchain_core.messages": types.SimpleNamespace(
                    HumanMessage=HumanMessage,
                    AIMessage=AIMessage,
                    SystemMessage=SystemMessage,
                    ToolMessage=ToolMessage,
                ),
                "langchain_openai": types.SimpleNamespace(
                    AzureChatOpenAI=FakeAzureChatOpenAI
                ),
            },
        ), patch.object(
            agent_module,
            "get_langfuse_metadata",
            return_value={},
        ):
            node = build_agent_llm_node(
                {
                    "provider": "azure_openai",
                    "model": "test-model",
                    "system_prompt": "You are a helpful assistant.",
                    "user_prompt_template": "Hello {{name}}",
                    "output_key": "answer",
                    "structured_output_enabled": True,
                    "structured_output_schema": """
                    {
                      "title": "AgentAnswer",
                      "type": "object",
                      "properties": {
                        "summary": { "type": "string" },
                        "confidence": { "type": "number" }
                      },
                      "required": ["summary", "confidence"],
                      "additionalProperties": false
                    }
                    """,
                },
                run_id="run-1",
                node_name="chat-node",
            )
            result = node({"name": "Ada"})

        self.assertEqual(result["answer"], structured_response)
        self.assertEqual(
            captured["create_agent_kwargs"]["response_format"],
            {
                "title": "AgentAnswer",
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["summary", "confidence"],
                "additionalProperties": False,
            },
        )

    def test_agent_llm_node_returns_error_for_invalid_structured_output_schema(self) -> None:
        class FakeAzureChatOpenAI:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

        def fake_create_agent(**_kwargs):
            raise AssertionError("create_agent should not be called when schema is invalid")

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
                "langchain.agents": types.SimpleNamespace(create_agent=fake_create_agent),
                "langchain.agents.middleware": types.SimpleNamespace(
                    ToolCallLimitMiddleware=ToolCallLimitMiddleware,
                    ModelCallLimitMiddleware=ModelCallLimitMiddleware,
                    wrap_tool_call=wrap_tool_call,
                ),
                "langchain_openai": types.SimpleNamespace(
                    AzureChatOpenAI=FakeAzureChatOpenAI
                ),
            },
        ):
            node = build_agent_llm_node(
                {
                    "provider": "azure_openai",
                    "model": "test-model",
                    "system_prompt": "You are a helpful assistant.",
                    "user_prompt_template": "Hello {{name}}",
                    "output_key": "answer",
                    "structured_output_enabled": True,
                    "structured_output_schema": '{"type":"object"',
                },
                run_id="run-1",
                node_name="chat-node",
            )
            result = node({"name": "Ada"})

        self.assertIsNone(result["answer"])
        self.assertIn("Structured output schema must be valid JSON", result["_error"])

    def test_agent_llm_node_falls_back_to_chat_runtime_when_agent_api_is_unavailable(self) -> None:
        sentinel_runner = object()
        chat_stub = types.SimpleNamespace(
            build_chat_llm_node=lambda *args, **kwargs: sentinel_runner
        )

        with patch.dict(
            sys.modules,
            {"services.runtime.nodes.types.llm.chat": chat_stub},
            clear=False,
        ):
            runner = build_agent_llm_node(
                {"provider": "azure_openai", "model": "test-model"},
                run_id="run-1",
                node_name="chat-node",
            )

        self.assertIs(runner, sentinel_runner)

    def test_agent_llm_node_falls_back_to_chat_runtime_for_unsupported_provider(self) -> None:
        sentinel_runner = object()
        chat_stub = types.SimpleNamespace(
            build_chat_llm_node=lambda *args, **kwargs: sentinel_runner
        )

        with patch.dict(
            sys.modules,
            {"services.runtime.nodes.types.llm.chat": chat_stub},
            clear=False,
        ):
            runner = build_agent_llm_node(
                {"provider": "ollama", "model": "llama3.1"},
                run_id="run-1",
                node_name="chat-node",
            )

        self.assertIs(runner, sentinel_runner)


if __name__ == "__main__":
    unittest.main()
