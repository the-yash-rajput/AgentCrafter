"""Parameterized security test suite for the task runner sandbox.

Run from backend_django/:
    pytest task_runner/tests/test_security.py -v
    pytest task_runner/tests/test_security.py -q         # quiet + category summary
    RUN_DANGEROUS_TESTS=1 pytest task_runner/tests/test_security.py -v

Each test case tries to breach the sandbox in a specific way.
- PASS: sandbox held (attack blocked, contained, or timed out as expected)
- FAIL: sandbox was BREACHED (attack succeeded when it should not have)
- XFAIL: known weakness — expected to fail (documented but not fixed yet)
"""
import pytest

from task_runner.tests.attack_cases import ALL_CASES
from task_runner.tests.attack_cases._framework import AttackCase, assert_case


def _make_id(case: AttackCase) -> str:
    return case.id


def _parametrize_cases():
    """Build pytest.param list with xfail markers where needed."""
    params = []
    for case in ALL_CASES:
        marks = []
        if case.xfail:
            marks.append(
                pytest.mark.xfail(
                    strict=False,
                    reason=case.notes or "Known weakness",
                )
            )
        params.append(pytest.param(case, marks=marks, id=case.id))
    return params


@pytest.mark.parametrize("case", _parametrize_cases())
def test_attack_case(runner, short_config, case: AttackCase) -> None:
    assert_case(runner, short_config, case)
