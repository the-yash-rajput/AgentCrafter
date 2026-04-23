import sys
from collections import defaultdict
from pathlib import Path

import pytest

# Ensure backend_django is on sys.path so `task_runner` is importable
_BACKEND_ROOT = str(Path(__file__).resolve().parents[3])
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from task_runner import PythonTaskConfig, PythonTaskRunner  # noqa: E402
from task_runner.tests.attack_cases._framework import SAFE_CONFIG  # noqa: E402


@pytest.fixture(scope="session")
def runner() -> PythonTaskRunner:
    return PythonTaskRunner()


@pytest.fixture(scope="session")
def short_config() -> PythonTaskConfig:
    return SAFE_CONFIG


# --- Per-category summary hook ---

_RESULTS: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when != "call":
        return
    # Extract category from nodeid: tests/test_security.py::test_attack_case[id]
    name = report.nodeid.split("[")[-1].rstrip("]")
    # The id encodes the category as the first segment before the first _
    category = name.split("_")[0] if "_" in name else name
    if report.passed:
        _RESULTS[category]["pass"] += 1
    elif report.failed:
        _RESULTS[category]["fail"] += 1
    elif report.skipped:
        _RESULTS[category]["skip"] += 1


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
    if not _RESULTS:
        return
    terminalreporter.write_sep("=", "Security Test Breach Report")
    header = f"{'Category':<30} {'Total':>6} {'Pass':>6} {'Fail':>6} {'Skip':>6}"
    terminalreporter.write_line(header)
    terminalreporter.write_line("-" * len(header))
    total_pass = total_fail = total_skip = 0
    for category in sorted(_RESULTS):
        p = _RESULTS[category]["pass"]
        f = _RESULTS[category]["fail"]
        s = _RESULTS[category]["skip"]
        total = p + f + s
        total_pass += p
        total_fail += f
        total_skip += s
        fail_marker = " *** BREACH ***" if f > 0 else ""
        terminalreporter.write_line(
            f"{category:<30} {total:>6} {p:>6} {f:>6} {s:>6}{fail_marker}"
        )
    grand_total = total_pass + total_fail + total_skip
    terminalreporter.write_line("-" * len(header))
    terminalreporter.write_line(
        f"{'TOTAL':<30} {grand_total:>6} {total_pass:>6} {total_fail:>6} {total_skip:>6}"
    )
    if total_fail > 0:
        terminalreporter.write_line(
            f"\n*** {total_fail} BREACH(ES) DETECTED — sandbox has real vulnerabilities! ***"
        )
    else:
        terminalreporter.write_line(
            f"\nAll {grand_total} cases: sandbox held. No breaches detected."
        )
