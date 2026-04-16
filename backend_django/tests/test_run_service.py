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
    class _Run:
        pass

    class _AgentSession:
        pass

    fake_modules = {
        "sqlalchemy": types.SimpleNamespace(),
        "sqlalchemy.orm": types.SimpleNamespace(Session=object),
        "models": types.SimpleNamespace(Agent=type("Agent", (), {}), Run=_Run),
        "models.agent_session": types.SimpleNamespace(AgentSession=_AgentSession),
        "schemas.schemas": types.SimpleNamespace(SessionRunCreate=object),
        "services.runtime.graph_runner": types.SimpleNamespace(GraphRunner=object),
        "services.session_service": types.SimpleNamespace(SessionService=object),
        "services.session_history": types.SimpleNamespace(
            CONVERSATION_HISTORY_KEY="conversation_history",
            normalize_conversation_history=lambda h: h or [],
        ),
        "services.state_schema": types.SimpleNamespace(apply_state_schema_defaults=lambda data, schema: data),
        "services.exceptions": types.SimpleNamespace(
            NotFoundError=Exception,
            ServiceError=Exception,
            ValidationError=Exception,
        ),
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
    def test_get_run_returns_run(self) -> None:
        db = MagicMock()
        run = SimpleNamespace(id=1, status="success")
        db.query.return_value.filter.return_value.first.return_value = run

        result = RunService(db).get_run(1)
        self.assertEqual(result, run)

    def test_get_run_raises_not_found(self) -> None:
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None

        with self.assertRaises(Exception):
            RunService(db).get_run(999)


if __name__ == "__main__":
    unittest.main()
