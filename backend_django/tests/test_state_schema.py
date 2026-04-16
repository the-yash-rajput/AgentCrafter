import unittest

from services.state_schema import apply_state_schema_defaults, get_state_schema_session_key


class StateSchemaTests(unittest.TestCase):
    def test_missing_values_use_state_schema_defaults(self) -> None:
        resolved = apply_state_schema_defaults(
            {"name": "Yash"},
            {
                "name": {"type": "str", "default": "Guest"},
                "attempts": {"type": "int", "default": "2"},
                "is_active": {"type": "bool", "default": "true"},
            },
        )

        self.assertEqual(
            resolved,
            {
                "name": "Yash",
                "attempts": 2,
                "is_active": True,
            },
        )

    def test_json_defaults_for_list_and_dict_are_parsed(self) -> None:
        resolved = apply_state_schema_defaults(
            {},
            {
                "tags": {"type": "list", "default": '["a", "b"]'},
                "filters": {"type": "dict", "default": '{"status":"open"}'},
            },
        )

        self.assertEqual(resolved["tags"], ["a", "b"])
        self.assertEqual(resolved["filters"], {"status": "open"})

    def test_session_key_is_discovered_from_state_schema(self) -> None:
        self.assertEqual(
            get_state_schema_session_key(
                {
                    "conversation_id": {"type": "str", "is_session_id": True},
                    "name": {"type": "str"},
                }
            ),
            "conversation_id",
        )


if __name__ == "__main__":
    unittest.main()
