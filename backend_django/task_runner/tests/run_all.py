"""Standalone security test runner for the task runner sandbox.

Usage:
    cd backend_django
    python -m task_runner.tests.run_all                  # safe cases only
    RUN_DANGEROUS_TESTS=1 python -m task_runner.tests.run_all  # include dangerous
    #.venv/bin/python -m task_runner.tests.run_all OR RUN_DANGEROUS_TESTS=1 .venv/bin/python -m task_runner.tests.run_all

Prints a per-category pass/fail/breach summary and exits with code 1 if any
non-xfail case breaches the sandbox.

Optional flags (env vars):
    VERBOSE=1          Show every case result, not just failures
    MAX_WORKERS=N      Run N cases in parallel (default: 4)
"""
from __future__ import annotations

import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Ensure backend_django is importable
_BACKEND_ROOT = str(Path(__file__).resolve().parents[3])
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from task_runner import PythonTaskRunner  # noqa: E402
from task_runner.tests.attack_cases import ALL_CASES  # noqa: E402
from task_runner.tests.attack_cases._framework import (  # noqa: E402
    SAFE_CONFIG,
    AttackCase,
    evaluate_case,
)

_VERBOSE = os.environ.get("VERBOSE") == "1"
_MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "4"))
_DANGEROUS = os.environ.get("RUN_DANGEROUS_TESTS") == "1"


def _run_one(runner: PythonTaskRunner, case: AttackCase) -> tuple[AttackCase, str, str]:
    status, detail = evaluate_case(runner, SAFE_CONFIG, case)
    return case, status, detail


def main() -> int:
    runner = PythonTaskRunner()

    cases = list(ALL_CASES)
    total = len(cases)
    dangerous_count = sum(1 for c in cases if c.dangerous)

    print(f"\n{'=' * 70}")
    print(f"  AgentCrafter Task Runner — Security Breach Test Suite")
    print(f"  Cases: {total}  |  Dangerous (gated): {dangerous_count}  |  Workers: {_MAX_WORKERS}")
    print(f"  RUN_DANGEROUS_TESTS={_DANGEROUS}")
    print(f"{'=' * 70}\n")

    category_stats: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    failures: list[tuple[AttackCase, str]] = []
    breaches: list[tuple[AttackCase, str]] = []
    done = 0
    start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
        futures = {pool.submit(_run_one, runner, case): case for case in cases}
        for future in as_completed(futures):
            case, status, detail = future.result()
            done += 1
            cat = case.category
            category_stats[cat][status] += 1

            if status == "FAIL":
                if case.xfail:
                    category_stats[cat]["xfail"] += 1
                    category_stats[cat]["FAIL"] -= 1
                    status = "XFAIL"
                else:
                    breaches.append((case, detail))
                    failures.append((case, detail))
            elif status == "ERROR":
                failures.append((case, detail))

            # Progress indicator
            progress = f"[{done:>4}/{total}]"
            marker = {
                "PASS": ".",
                "FAIL": "F",
                "XFAIL": "x",
                "ERROR": "E",
            }.get(status, "?")

            if _VERBOSE or status not in ("PASS", "XFAIL"):
                print(f"  {progress} {marker} {case.id:<50} {status}")
            elif done % 50 == 0 or done == total:
                elapsed = time.perf_counter() - start
                print(
                    f"  {progress} {done/elapsed:.1f} cases/s  "
                    f"pass={sum(category_stats[c]['PASS'] for c in category_stats)}"
                )

    elapsed = time.perf_counter() - start
    print(f"\n{'=' * 70}")
    print(f"  Results after {elapsed:.1f}s")
    print(f"{'=' * 70}\n")

    # Per-category table
    all_statuses = ["PASS", "FAIL", "XFAIL", "ERROR"]
    header = f"  {'Category':<30} {'Total':>6} {'Pass':>6} {'Fail':>6} {'Xfail':>6} {'Error':>6}"
    print(header)
    print(f"  {'-' * (len(header) - 2)}")

    grand = defaultdict(int)
    for cat in sorted(category_stats):
        stats = category_stats[cat]
        row_total = sum(stats[s] for s in all_statuses)
        p, f, x, e = stats["PASS"], stats["FAIL"], stats["XFAIL"], stats["ERROR"]
        grand["total"] += row_total
        grand["pass"] += p
        grand["fail"] += f
        grand["xfail"] += x
        grand["error"] += e
        breach_flag = " *** BREACH ***" if f > 0 else ""
        print(f"  {cat:<30} {row_total:>6} {p:>6} {f:>6} {x:>6} {e:>6}{breach_flag}")

    print(f"  {'-' * (len(header) - 2)}")
    print(
        f"  {'TOTAL':<30} {grand['total']:>6} {grand['pass']:>6} "
        f"{grand['fail']:>6} {grand['xfail']:>6} {grand['error']:>6}"
    )
    print()

    if breaches:
        print(f"\n{'!' * 70}")
        print(f"  *** {len(breaches)} REAL BREACH(ES) DETECTED — fix these! ***")
        print(f"{'!' * 70}\n")
        for case, detail in breaches:
            print(f"  BREACH [{case.id}]")
            print(f"    category : {case.category}")
            print(f"    notes    : {case.notes}")
            print(f"    detail   : {detail}")
            print(f"    code     :")
            for line in case.code.splitlines():
                print(f"      {line}")
            print()
        return 1

    print(
        f"  All {grand['total']} cases: sandbox held. "
        f"{grand['xfail']} known weakness(es) marked xfail. No breaches."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
