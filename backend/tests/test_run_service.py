import importlib.util
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


def _load_run_service_module():
    class _Column:
        def __init__(self, name: str) -> None:
            self.name = name

        def __eq__(self, other):
            return f"{self.name} == {other!r}"

        def isnot(self, other):
            return f"{self.name} IS NOT {other!r}"

        def desc(self):
            return f"{self.name} DESC"

    class _Run:
        session_id = _Column("session_id")
        completed_at = _Column("completed_at")
        started_at = _Column("started_at")
        id = _Column("id")

    fake_modules = {
        "sqlalchemy": types.SimpleNamespace(),
        "sqlalchemy.orm": types.SimpleNamespace(Session=object),
        "models": types.SimpleNamespace(Agent=type("Agent", (), {}), Run=_Run),
        "schemas.schemas": types.SimpleNamespace(RunCreate=object),
        "services.runtime.graph_runner": types.SimpleNamespace(GraphRunner=object),
    }

    module_path = BACKEND_ROOT / "services/run_service.py"
    module_spec = importlib.util.spec_from_file_location("tests.run_service_module", module_path)
    module = importlib.util.module_from_spec(module_spec)
    assert module_spec is not None and module_spec.loader is not None

    with patch.dict(sys.modules, fake_modules, clear=False):
        module_spec.loader.exec_module(module)

    return module, _Run


run_service_module, RunModel = _load_run_service_module()
RunService = run_service_module.RunService


class RunServiceTests(unittest.TestCase):
    def test_get_session_conversation_uses_shared_completed_session_history(self) -> None:
        db = MagicMock()
        query = db.query.return_value
        query.filter.return_value = query
        query.order_by.return_value = query
        query.limit.return_value = query
        query.all.return_value = [
            SimpleNamespace(
                agent_id=101,
                conversation_turn=[
                    {"role": "user", "content": "Hi"},
                    {"role": "assistant", "content": "Hello from agent A"},
                ],
                input_data={},
                output_data={},
                error=None,
            ),
            SimpleNamespace(
                agent_id=202,
                conversation_turn=[
                    {"role": "assistant", "content": "Agent B follow-up"},
                ],
                input_data={},
                output_data={},
                error=None,
            ),
        ]

        history = RunService(db)._get_session_conversation("thread-42")

        self.assertEqual(
            history,
            [
                {"role": "assistant", "content": "Agent B follow-up"},
                {"role": "user", "content": "Hi"},
                {"role": "assistant", "content": "Hello from agent A"},
            ],
        )
        db.query.assert_called_once_with(RunModel)
        query.filter.assert_called_once_with(
            "session_id == 'thread-42'",
            "completed_at IS NOT None",
        )
        query.order_by.assert_called_once_with("started_at DESC", "id DESC")
        query.limit.assert_called_once_with(RunService.session_history_limit)

    def test_get_session_conversation_skips_query_without_session_id(self) -> None:
        db = MagicMock()

        history = RunService(db)._get_session_conversation(None)

        self.assertEqual(history, [])
        db.query.assert_not_called()


if __name__ == "__main__":
    unittest.main()
