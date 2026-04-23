"""Resource exhaustion attack cases (~80).

Tests that the runner properly limits CPU, memory, and time.
Dangerous cases (gated by RUN_DANGEROUS_TESTS=1) probe limits that
are NOT enforced (RLIMIT_NPROC, RLIMIT_NOFILE, RLIMIT_FSIZE).
"""
from ._framework import AttackCase

# Short config (2s) is used by the standalone runner; pytest uses 3s default.
# These cases use expected="timeout" or "blocked" depending on which limit fires first.

CASES: list[AttackCase] = [
    # --- Infinite CPU loops ---
    AttackCase(
        id="resource_infinite_while_true",
        category="resource_exhaustion",
        code='def run(state):\n    while True:\n        pass\n',
        expected="timeout",
        notes="Infinite CPU loop — wall-clock timeout fires",
    ),
    AttackCase(
        id="resource_infinite_for_count",
        category="resource_exhaustion",
        code='def run(state):\n    for i in range(10**18):\n        pass\n    return {"i": i}\n',
        expected="timeout",
        notes="for loop with astronomical range — wall-clock timeout fires",
    ),
    AttackCase(
        id="resource_cpu_fibonacci_recursive",
        category="resource_exhaustion",
        code=(
            'def fib(n):\n'
            '    if n <= 1: return n\n'
            '    return fib(n-1) + fib(n-2)\n'
            'def run(state):\n'
            '    return {"result": fib(45)}\n'
        ),
        expected="timeout",
        notes="Exponential-time recursive Fibonacci — exceeds timeout",
    ),
    AttackCase(
        id="resource_cpu_busy_sum",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    total = 0\n'
            '    while True:\n'
            '        total += 1\n'
            '    return {"total": total}\n'
        ),
        expected="timeout",
        notes="Busy accumulation loop",
    ),
    AttackCase(
        id="resource_cpu_list_sort_loop",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    data = list(range(10**6))\n'
            '    while True:\n'
            '        data.sort()\n'
            '        data.reverse()\n'
            '    return {"x": 1}\n'
        ),
        expected="timeout",
        notes="Repeated large sort",
    ),

    # --- Memory exhaustion ---
    AttackCase(
        id="resource_mem_huge_list",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    data = [0] * (10**10)\n'
            '    return {"len": len(data)}\n'
        ),
        expected="blocked",
        notes="Huge list allocation — RLIMIT_AS or OOM kill, or timeout",
    ),
    AttackCase(
        id="resource_mem_huge_string",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    s = "x" * (10**10)\n'
            '    return {"len": len(s)}\n'
        ),
        expected="blocked",
        notes="Huge string — memory limit",
    ),
    AttackCase(
        id="resource_mem_huge_bytes",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    b = b"x" * (10**10)\n'
            '    return {"len": len(b)}\n'
        ),
        expected="blocked",
        notes="Huge bytes object — memory limit",
    ),
    AttackCase(
        id="resource_mem_expanding_list",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    data = []\n'
            '    while True:\n'
            '        data.extend([0] * 10**6)\n'
            '    return {"len": len(data)}\n'
        ),
        expected="blocked",
        notes="Expanding list — memory limit or timeout",
    ),
    AttackCase(
        id="resource_mem_dict_key_explosion",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    d = {i: i for i in range(10**9)}\n'
            '    return {"len": len(d)}\n'
        ),
        expected="blocked",
        notes="Huge dict — memory limit or timeout",
    ),
    AttackCase(
        id="resource_mem_nested_list",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    data = []\n'
            '    node = data\n'
            '    for _ in range(10**7):\n'
            '        node.append([])\n'
            '        node = node[0]\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="Deeply nested list structure — memory exhaustion",
    ),
    AttackCase(
        id="resource_mem_bytes_accumulate",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    parts = []\n'
            '    while True:\n'
            '        parts.append(b"x" * 10**6)\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="Accumulating byte strings — memory exhaustion or timeout",
    ),
    AttackCase(
        id="resource_mem_set_explosion",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    s = set(range(10**9))\n'
            '    return {"len": len(s)}\n'
        ),
        expected="blocked",
        notes="Huge set — memory limit or timeout",
    ),

    # --- Using exposed math module for memory/CPU ---
    AttackCase(
        id="resource_math_factorial_huge",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    result = math.factorial(10**7)\n'
            '    return {"digits": len(str(result))}\n'
        ),
        expected="blocked",
        notes="math.factorial(10**7) — huge number, CPU + memory",
    ),
    AttackCase(
        id="resource_math_factorial_extreme",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    result = math.factorial(10**6)\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="math.factorial(10**6) — CPU intensive",
    ),
    AttackCase(
        id="resource_math_pow_huge",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    result = 2 ** (10**8)\n'
            '    return {"x": 1}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 1,
        notes="2^(10^8) computed in memory but result not returned — SANDBOX GAP: RLIMIT_AS may not catch pure-CPU big-int work; completes fast on modern hardware",
        xfail=True,
    ),

    # --- Using exposed re module for catastrophic backtracking ---
    AttackCase(
        id="resource_re_catastrophic_backtracking",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    result = re.match(r"(a+)+$", "a" * 30 + "!")\n'
            '    return {"match": str(result)}\n'
        ),
        expected="timeout",
        notes="Catastrophic backtracking regex via exposed re module — CPU-bound, hits timeout",
        xfail=True,
    ),
    AttackCase(
        id="resource_re_catastrophic_b",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    result = re.match(r"(x+x+)+y", "x" * 40)\n'
            '    return {"match": str(result)}\n'
        ),
        expected="timeout",
        notes="Catastrophic backtracking variant — may timeout",
        xfail=True,
    ),
    AttackCase(
        id="resource_re_many_groups",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    pattern = r"(" * 50 + r"a+" + r")" * 50\n'
            '    result = re.match(pattern, "a" * 100)\n'
            '    return {"match": str(result)[:50]}\n'
        ),
        expected="contained",
        output_predicate=lambda out: isinstance(out.get("match"), str),
        notes="50 nested groups regex on 'a'*100 — completes fast (no backtracking catastrophe here), contained",
    ),

    # --- Using exposed json module for deep nesting ---
    AttackCase(
        id="resource_json_deeply_nested",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    nested = "[" * 5000 + "]" * 5000\n'
            '    result = json.loads(nested)\n'
            '    return {"x": 1}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 1,
        notes="json.loads with 5000-deep nesting — C implementation handles without recursion limit; SANDBOX GAP: no depth limit",
        xfail=True,
    ),
    AttackCase(
        id="resource_json_huge_number",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    huge = json.loads("9" * 10**6)\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="json.loads('9'*10^6) — huge integer parse, memory or timeout",
    ),
    AttackCase(
        id="resource_json_large_array",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    big = json.loads("[" + ",".join(["1"] * 10**7) + "]")\n'
            '    return {"len": len(big)}\n'
        ),
        expected="contained",
        output_predicate=lambda out: isinstance(out.get("len"), int),
        notes="10M-element JSON array — completes on modern hardware; SANDBOX GAP: RLIMIT_AS 128MB may not catch it (each int ~28B but list header smaller in C)",
        xfail=True,
    ),

    # --- random module memory exhaustion ---
    AttackCase(
        id="resource_random_getrandbits_huge",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    n = random.getrandbits(10**8)\n'
            '    return {"x": 1}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 1,
        xfail=True,
        notes="SANDBOX GAP: random.getrandbits(10^8) completes on modern hardware; RLIMIT_AS not tight enough to OOM it",
    ),
    AttackCase(
        id="resource_random_choices_huge",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    result = random.choices(list(range(256)), k=10**8)\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="random.choices with huge k — memory exhaustion",
    ),

    # --- Deep recursion ---
    AttackCase(
        id="resource_deep_recursion",
        category="resource_exhaustion",
        code=(
            'def recurse(n):\n'
            '    return recurse(n + 1)\n'
            'def run(state):\n'
            '    return recurse(0)\n'
        ),
        expected="blocked",
        notes="Infinite recursion — RecursionError (caught as PythonTaskError)",
    ),
    AttackCase(
        id="resource_mutual_recursion",
        category="resource_exhaustion",
        code=(
            'def a(n): return b(n + 1)\n'
            'def b(n): return a(n + 1)\n'
            'def run(state):\n'
            '    return {"x": a(0)}\n'
        ),
        expected="blocked",
        notes="Mutual recursion — RecursionError",
    ),

    # --- CPU via Decimal ---
    AttackCase(
        id="resource_decimal_huge_precision",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    import decimal\n'
            '    decimal.getcontext().prec = 10**7\n'
            '    result = Decimal(2).sqrt()\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import decimal blocked; Decimal is a class but decimal module isn't directly importable",
    ),

    # --- Counter with huge input ---
    AttackCase(
        id="resource_counter_huge_input",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    c = Counter(range(10**8))\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="Counter with 100M elements — memory or timeout",
    ),

    # --- statistics module exhaustion ---
    AttackCase(
        id="resource_statistics_huge_data",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    data = list(range(10**7))\n'
            '    result = statistics.mean(data)\n'
            '    return {"mean": result}\n'
        ),
        expected="blocked",
        notes="statistics.mean with 10M elements — memory + CPU",
    ),

    # --- String concatenation bomb ---
    AttackCase(
        id="resource_string_concat_bomb",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    s = "a"\n'
            '    for _ in range(40):\n'
            '        s = s + s\n'
            '    return {"len": len(s)}\n'
        ),
        expected="blocked",
        notes="String doubling 40 times → 2^40 chars (1 TB) — memory limit",
    ),

    # --- Format string memory attack via exposed string module ---
    AttackCase(
        id="resource_string_template_huge",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    t = string.Template("$x" * 10**7)\n'
            '    result = t.safe_substitute(x="a")\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="string.Template removed — string is now constants-only; AttributeError closes this memory bomb",
    ),

    # --- DANGEROUS: Fork bomb (needs os.fork, blocked, but test the gate) ---
    AttackCase(
        id="resource_fork_bomb_via_os",
        category="resource_exhaustion",
        code=(
            'import os\n'
            'def run(state):\n'
            '    while True:\n'
            '        os.fork()\n'
        ),
        expected="blocked",
        notes="Fork bomb via os.fork — import os is blocked, but if it weren't, RLIMIT_NPROC is unset",
        dangerous=True,
    ),

    # --- DANGEROUS: FD exhaustion (needs open, blocked, but test the gate) ---
    AttackCase(
        id="resource_fd_exhaustion",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    fds = []\n'
            '    while True:\n'
            '        fds.append(open("/dev/null", "rb"))\n'
            '    return {"count": len(fds)}\n'
        ),
        expected="blocked",
        notes="FD exhaustion via open — open() not in builtins; if bypass existed, RLIMIT_NOFILE is unset",
        dangerous=True,
    ),

    # --- DANGEROUS: Huge file write (needs open, blocked) ---
    AttackCase(
        id="resource_huge_file_write",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    with open("/tmp/big_file.dat", "wb") as f:\n'
            '        while True:\n'
            '            f.write(b"x" * 10**6)\n'
        ),
        expected="blocked",
        notes="Large file write — open not in builtins; if bypass, RLIMIT_FSIZE is unset",
        dangerous=True,
    ),

    # --- DANGEROUS: SIGTERM evasion (infinite loop + signal block) ---
    AttackCase(
        id="resource_sigterm_evasion_c_loop",
        category="resource_exhaustion",
        code=(
            'import ctypes\n'
            'def run(state):\n'
            '    libc = ctypes.CDLL(None)\n'
            '    while True:\n'
            '        libc.getpid()\n'
        ),
        expected="blocked",
        notes="import ctypes blocked; if bypass, C loop could survive SIGTERM (no SIGKILL fallback)",
        dangerous=True,
    ),

    # --- sys.setrecursionlimit attempt ---
    AttackCase(
        id="resource_recursion_limit_bypass",
        category="resource_exhaustion",
        code=(
            'import sys\n'
            'def run(state):\n'
            '    sys.setrecursionlimit(10**9)\n'
            '    def r(n): return r(n+1)\n'
            '    r(0)\n'
        ),
        expected="blocked",
        notes="import sys blocked — can't raise recursion limit",
    ),

    # --- zip bomb equivalent ---
    AttackCase(
        id="resource_zip_bomb_equivalent",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    layers = [list(range(1000))] * 1000\n'
            '    expanded = [x for layer in layers for x in layer * 1000]\n'
            '    return {"len": len(expanded)}\n'
        ),
        expected="blocked",
        notes="Nested list comprehension explosion — memory or timeout",
    ),

    # --- CPU via repeated json serialization ---
    AttackCase(
        id="resource_json_serialize_loop",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    data = list(range(10**5))\n'
            '    while True:\n'
            '        json.dumps(data)\n'
        ),
        expected="timeout",
        notes="Repeated JSON serialization — CPU-bound, timeout",
    ),

    # --- uuid4 exhaustion ---
    AttackCase(
        id="resource_uuid4_generation_loop",
        category="resource_exhaustion",
        code=(
            'def run(state):\n'
            '    ids = []\n'
            '    while True:\n'
            '        ids.append(str(uuid4()))\n'
        ),
        expected="timeout",
        notes="Infinite uuid4 generation — timeout (and memory eventually)",
    ),
]
