import unittest
import importlib.util
import sys
from types import SimpleNamespace
from pathlib import Path

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


sys.modules.setdefault("jinja2", SimpleNamespace(Template=_TemplateStub))

from services.session_history import (
    build_conversation_turn,
    normalize_conversation_history,
)

_CHAT_MODULE_PATH = BACKEND_ROOT / "services/runtime/nodes/types/llm/chat.py"
_CHAT_MODULE_SPEC = importlib.util.spec_from_file_location(
    "tests.session_history_chat_module",
    _CHAT_MODULE_PATH,
)
chat_module = importlib.util.module_from_spec(_CHAT_MODULE_SPEC)
assert _CHAT_MODULE_SPEC is not None and _CHAT_MODULE_SPEC.loader is not None
_CHAT_MODULE_SPEC.loader.exec_module(chat_module)
_build_chat_messages = chat_module._build_chat_messages


class SessionHistoryTests(unittest.TestCase):
    def test_build_conversation_turn_prefers_human_friendly_keys(self) -> None:
        messages = build_conversation_turn(
            {"question": "What is the weather?", "conversation_history": [{"role": "user", "content": "old"}]},
            agent_output={"answer": "It is sunny."},
        )

        self.assertEqual(
            messages,
            [
                {"role": "user", "content": "What is the weather?"},
                {"role": "assistant", "content": "It is sunny."},
            ],
        )

    def test_build_chat_messages_includes_prior_conversation_before_current_prompt(self) -> None:
        messages = _build_chat_messages(
            "You are helpful.",
            "Current question",
            {
                "conversation_history": [
                    {"role": "user", "content": "Earlier question"},
                    {"role": "assistant", "content": "Earlier answer"},
                ]
            },
        )

        self.assertEqual(
            messages,
            [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "Earlier question"},
                {"role": "assistant", "content": "Earlier answer"},
                {"role": "user", "content": "Current question"},
            ],
        )

    def test_build_conversation_turn_extracts_messages_payload_and_final_answer(self) -> None:
        messages = build_conversation_turn(
            {
                "messages": [
                    {"type": "human", "content": "First"},
                    {"type": "ai", "content": "Old reply"},
                    {"type": "human", "content": "Latest question"},
                ]
            },
            agent_output={
                "structured_response": {
                    "final_answer": "Latest answer",
                    "ticket_status": "pending",
                }
            },
        )

        self.assertEqual(
            messages,
            [
                {"role": "user", "content": "Latest question"},
                {"role": "assistant", "content": "Latest answer"},
            ],
        )

    def test_normalize_conversation_history_ignores_invalid_items(self) -> None:
        history = normalize_conversation_history(
            [
                {"role": "user", "content": "Hello"},
                {"role": "tool", "content": "skip"},
                {"role": "assistant", "content": {"answer": "Hi"}},
                "bad item",
            ]
        )

        self.assertEqual(
            history,
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": '{"answer": "Hi"}'},
            ],
        )

    def test_normalize_conversation_history_supports_langchain_style_message_roles(self) -> None:
        history = normalize_conversation_history(
            [
                {"type": "human", "content": "Hello"},
                SimpleNamespace(type="ai", content="Hi there"),
                SimpleNamespace(type="system", content="Follow policy"),
            ]
        )

        self.assertEqual(
            history,
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
                {"role": "system", "content": "Follow policy"},
            ],
        )

    def test_build_conversation_turn_skips_non_conversational_state_payloads(self) -> None:
        messages = build_conversation_turn(
            {
                "customer_id": "cus_123",
                "ticket_status": "open",
                "conversation_history": [{"role": "user", "content": "old"}],
            },
            agent_output={"answer": "Working on it."},
        )

        self.assertEqual(
            messages,
            [
                {"role": "assistant", "content": "Working on it."},
            ],
        )


if __name__ == "__main__":
    unittest.main()
