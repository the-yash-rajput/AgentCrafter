import unittest
from types import SimpleNamespace

from services.session_history import (
    build_conversation_turn,
    flatten_conversation_history,
    normalize_conversation_history,
)
from services.runtime.nodes.types.llm.chat import _build_chat_messages


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

    def test_flatten_conversation_history_uses_stored_turn_when_available(self) -> None:
        runs = [
            SimpleNamespace(
                conversation_turn=[
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hello"},
                ],
                input_data={"message": "ignored"},
                output_data={"response": "ignored"},
                error=None,
            )
        ]

        self.assertEqual(
            flatten_conversation_history(runs),
            [
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello"},
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


if __name__ == "__main__":
    unittest.main()
