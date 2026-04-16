import unittest

from task_runner import (
    PythonTaskConfig,
    PythonTaskConfigurationError,
    PythonTaskRunner,
    PythonTaskTimeoutError,
)


class PythonTaskRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = PythonTaskRunner()
        self.config = PythonTaskConfig(timeout_seconds=1.0, max_memory_mb=256)

    def test_executes_inline_python_in_isolated_runner(self) -> None:
        result = self.runner.run(
            code=(
                "def run(state):\n"
                "    state['total'] = sum(state['items'])\n"
                "    return state\n"
            ),
            state={"items": [1, 2, 3]},
            config=self.config,
        )

        self.assertEqual(result.output["total"], 6)

    def test_exposes_safe_helpers_without_imports(self) -> None:
        result = self.runner.run(
            code=(
                "def run(state):\n"
                "    return {'root': math.sqrt(state['value']), 'encoded': json.dumps(state)}\n"
            ),
            state={"value": 4},
            config=self.config,
        )

        self.assertEqual(result.output, {"root": 2.0, "encoded": '{"value": 4}'})

    def test_blocks_unsafe_imports(self) -> None:
        with self.assertRaises(PythonTaskConfigurationError) as context:
            self.runner.run(
                code=(
                    "import os\n"
                    "def run(state):\n"
                    "    return {'cwd': os.getcwd()}\n"
                ),
                state={},
                config=self.config,
            )

        self.assertIn("Import statements are blocked", str(context.exception))

    def test_stops_long_running_tasks(self) -> None:
        with self.assertRaises(PythonTaskTimeoutError):
            self.runner.run(
                code=(
                    "def run(state):\n"
                    "    while True:\n"
                    "        pass\n"
                ),
                state={},
                config=PythonTaskConfig(timeout_seconds=0.2, max_memory_mb=256),
            )


if __name__ == "__main__":
    unittest.main()
