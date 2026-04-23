from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Literal, Optional

# Ensure backend_django is importable
_BACKEND_ROOT = str(Path(__file__).resolve().parents[4])
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from task_runner import (  # noqa: E402
    PythonTaskConfig,
    PythonTaskConfigurationError,
    PythonTaskError,
    PythonTaskRunner,
    PythonTaskTimeoutError,
)

SAFE_CONFIG = PythonTaskConfig(timeout_seconds=3.0, max_memory_mb=128)


@dataclass
class AttackCase:
    id: str
    category: str
    code: str
    expected: Literal["blocked", "contained", "timeout"]
    state: dict = field(default_factory=dict)
    output_predicate: Optional[Callable[[dict], bool]] = None
    dangerous: bool = False
    xfail: bool = False
    notes: str = ""


def evaluate_case(
    runner: PythonTaskRunner,
    config: PythonTaskConfig,
    case: AttackCase,
) -> tuple[str, str]:
    """Run a single attack case and return (status, detail).

    status is one of: "PASS", "FAIL", "XFAIL", "ERROR"
    """
    try:
        result = runner.run(code=case.code, state=case.state, config=config)
    except PythonTaskTimeoutError as exc:
        if case.expected == "timeout":
            status = "XFAIL" if case.xfail else "PASS"
            return status, f"timeout (expected): {exc}"
        if case.expected == "blocked":
            status = "XFAIL" if case.xfail else "PASS"
            return status, f"timeout counts as blocked: {exc}"
        return "FAIL", f"unexpected timeout for expected={case.expected!r}: {exc}"
    except PythonTaskConfigurationError as exc:
        if case.expected in ("blocked", "timeout"):
            status = "XFAIL" if case.xfail else "PASS"
            return status, f"config error (blocked): {exc}"
        return "FAIL", f"unexpected config error for expected={case.expected!r}: {exc}"
    except PythonTaskError as exc:
        if case.expected in ("blocked", "timeout"):
            status = "XFAIL" if case.xfail else "PASS"
            return status, f"runtime error (blocked): {exc}"
        return "FAIL", f"unexpected runtime error for expected={case.expected!r}: {exc}"
    except Exception as exc:
        return "ERROR", f"unexpected exception {type(exc).__name__}: {exc}"
    else:
        # run() returned normally — no exception
        if case.expected in ("blocked", "timeout"):
            return "FAIL", (
                f"BREACH: attack succeeded, got output={result.output!r}"
            )
        # expected="contained"
        if case.output_predicate is not None and not case.output_predicate(result.output):
            return "FAIL", f"contained predicate failed, output={result.output!r}"
        status = "XFAIL" if case.xfail else "PASS"
        return status, f"contained safely, output={result.output!r}"


def assert_case(
    runner: PythonTaskRunner,
    config: PythonTaskConfig,
    case: AttackCase,
) -> None:
    """Assert version for pytest — raises AssertionError on FAIL/ERROR."""
    status, detail = evaluate_case(runner, config, case)
    if status == "FAIL":
        raise AssertionError(
            f"[{case.id}] {detail}\n"
            f"  category : {case.category}\n"
            f"  expected : {case.expected}\n"
            f"  notes    : {case.notes}\n"
            f"  code     :\n{_indent(case.code)}"
        )
    if status == "ERROR":
        raise AssertionError(f"[{case.id}] Test infrastructure error: {detail}")


def _indent(text: str, prefix: str = "    ") -> str:
    return "\n".join(prefix + line for line in text.splitlines())
