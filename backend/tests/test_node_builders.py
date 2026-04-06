import unittest

from backend.services.runtime.json_utils import parse_json_content


class NodeBuildersTests(unittest.TestCase):
    def test_parse_json_content_accepts_plain_json(self) -> None:
        parsed = parse_json_content('{"brand":"Triumph","model":"Speed 400"}')

        self.assertEqual(parsed, {"brand": "Triumph", "model": "Speed 400"})

    def test_parse_json_content_strips_markdown_fences(self) -> None:
        parsed = parse_json_content(
            '```json\n{"brand":"Triumph","model":"Speed 400"}\n```'
        )

        self.assertEqual(parsed, {"brand": "Triumph", "model": "Speed 400"})

    def test_parse_json_content_raises_clear_error_for_truncated_json(self) -> None:
        with self.assertRaises(ValueError) as context:
            parse_json_content(
                '{\n  "brand": "Triumph",\n  "cooling_system": "'
            )

        self.assertIn("Expected valid JSON response", str(context.exception))
        self.assertIn("increase max_tokens", str(context.exception))


if __name__ == "__main__":
    unittest.main()
