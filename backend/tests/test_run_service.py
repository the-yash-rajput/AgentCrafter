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

        def desc(self):
            return f"{self.name} DESC"

    class _Run:
        agent_id = _Column("agent_id")
        agent_version_id = _Column("agent_version_id")
        session_id = _Column("session_id")
        started_at = _Column("started_at")
        id = _Column("id")

    fake_modules = {
        "sqlalchemy": types.SimpleNamespace(),
        "sqlalchemy.orm": types.SimpleNamespace(Session=object),
        "models": types.SimpleNamespace(
            Agent=type("Agent", (), {"id": _Column("agent.id")}),
            AgentSession=type("AgentSession", (), {"id": _Column("session.id")}),
            AgentVersion=type("AgentVersion", (), {"id": _Column("version.id")}),
            Run=_Run,
        ),
        "schemas.schemas": types.SimpleNamespace(AgentSessionCreate=object, RunCreate=object),
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
    def test_run_response_uses_session_owned_conversation_payload(self) -> None:
        run = SimpleNamespace(
            id=99,
            agent_id=10,
            agent_version_id=21,
            session_id=42,
            parent_run_id=None,
            status="success",
            input_data={"input": "Hello"},
            output_data={"answer": "Hi"},
            state_snapshots=[],
            error=None,
            started_at="start",
            completed_at="done",
        )

        response = RunService(MagicMock())._run_response(
            run,
            conversation_history=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ],
            conversation_turn=[
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ],
        )

        self.assertEqual(response["session_id"], 42)
        self.assertEqual(response["agent_version_id"], 21)
        self.assertEqual(
            response["conversation_history"],
            [
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi"},
            ],
        )
        self.assertEqual(len(response["conversation_turn"]), 2)

    def test_list_runs_filters_by_agent_version_and_session(self) -> None:
        db = MagicMock()
        query = db.query.return_value
        query.filter.return_value = query
        query.order_by.return_value = query
        query.offset.return_value = query
        query.limit.return_value = query
        query.all.return_value = []

        service = RunService(db)
        service._get_agent_or_404 = MagicMock(return_value=object())

        runs = service.list_runs(10, agent_version_id=21, session_id=42, limit=500, offset=-1)

        self.assertEqual(runs, [])
        db.query.assert_called_once_with(RunModel)
        query.filter.assert_any_call("agent_id == 10")
        query.filter.assert_any_call("agent_version_id == 21")
        query.filter.assert_any_call("session_id == 42")
        query.limit.assert_called_once_with(200)
        query.offset.assert_called_once_with(0)


if __name__ == "__main__":
    unittest.main()
