"""Asyncio / awaitable path attack cases (~20).

async def is blocked by RestrictedPython at compile time ("AsyncFunctionDef
statements are not allowed"). All attempts to create coroutines directly in
the sandbox are blocked. The asyncio.run() path in the task runner can only
be triggered if run() returns an awaitable — which is impossible in the sandbox
since async def is blocked.

Tests document the blocking behaviour and probe the few remaining avenues.
"""
from ._framework import AttackCase

CASES: list[AttackCase] = [
    # --- async def blocked at compile time ---
    AttackCase(
        id="asyncio_async_def_blocked",
        category="asyncio_tricks",
        code=(
            'async def compute(state):\n'
            '    return {"result": 42}\n'
            'def run(state):\n'
            '    return compute(state)\n'
        ),
        expected="blocked",
        notes="async def blocked: RestrictedPython transformer rejects AsyncFunctionDef",
    ),
    AttackCase(
        id="asyncio_async_def_with_await",
        category="asyncio_tricks",
        code=(
            'async def fetcher():\n'
            '    result = 1 + 1\n'
            '    return {"result": result}\n'
            'def run(state):\n'
            '    return fetcher()\n'
        ),
        expected="blocked",
        notes="async def blocked at compile time — no await needed to trigger the block",
    ),
    AttackCase(
        id="asyncio_nested_async_def",
        category="asyncio_tricks",
        code=(
            'def run(state):\n'
            '    async def inner():\n'
            '        return {"x": 1}\n'
            '    return inner()\n'
        ),
        expected="blocked",
        notes="async def inside run() body — also blocked at compile time",
    ),
    AttackCase(
        id="asyncio_async_def_import_os",
        category="asyncio_tricks",
        code=(
            'async def evil(state):\n'
            '    import os\n'
            '    return {"cwd": os.getcwd()}\n'
            'def run(state):\n'
            '    return evil(state)\n'
        ),
        expected="blocked",
        notes="async def blocked before import check even runs",
    ),
    AttackCase(
        id="asyncio_async_generator_blocked",
        category="asyncio_tricks",
        code=(
            'async def agen():\n'
            '    for i in range(3):\n'
            '        yield i\n'
            'def run(state):\n'
            '    return agen()\n'
        ),
        expected="blocked",
        notes="async generator — async def blocked at compile time",
    ),
    AttackCase(
        id="asyncio_async_for_blocked",
        category="asyncio_tricks",
        code=(
            'async def main():\n'
            '    results = []\n'
            '    async for item in aiter([1, 2, 3]):\n'
            '        results.append(item)\n'
            '    return {"results": results}\n'
            'def run(state):\n'
            '    return main()\n'
        ),
        expected="blocked",
        notes="async for + async def — both compile-time blocked",
    ),
    AttackCase(
        id="asyncio_async_with_blocked",
        category="asyncio_tricks",
        code=(
            'async def main():\n'
            '    async with some_context() as ctx:\n'
            '        return {"ctx": str(ctx)}\n'
            'def run(state):\n'
            '    return main()\n'
        ),
        expected="blocked",
        notes="async with + async def — compile-time blocked",
    ),
    AttackCase(
        id="asyncio_await_keyword_blocked",
        category="asyncio_tricks",
        code=(
            'async def main():\n'
            '    result = await some_coroutine()\n'
            '    return {"result": result}\n'
            'def run(state):\n'
            '    return main()\n'
        ),
        expected="blocked",
        notes="await keyword + async def — compile-time blocked",
    ),

    # --- Custom awaitable objects (class def also blocked) ---
    AttackCase(
        id="asyncio_custom_awaitable_class_blocked",
        category="asyncio_tricks",
        code=(
            'class MyAwaitable:\n'
            '    def __await__(self):\n'
            '        yield\n'
            '        return {"x": "custom_awaitable"}\n'
            'def run(state):\n'
            '    return MyAwaitable()\n'
        ),
        expected="blocked",
        notes="Class definition fails (__metaclass__ not found in restricted exec)",
    ),

    # --- Generator-based coroutine (using StopIteration) ---
    AttackCase(
        id="asyncio_generator_coroutine_manual",
        category="asyncio_tricks",
        code=(
            'def run(state):\n'
            '    def gen_coro():\n'
            '        yield\n'
            '        return {"x": 1}\n'
            '    g = gen_coro()\n'
            '    next(g)\n'
            '    try:\n'
            '        next(g)\n'
            '    except StopIteration as e:\n'
            '        return e.value\n'
        ),
        expected="blocked",
        notes="next() not in restricted builtins — NameError; generator-as-coroutine pattern blocked",
    ),

    # --- Normal sync computations (baseline, asyncio path is dead) ---
    AttackCase(
        id="asyncio_sync_with_json",
        category="asyncio_tricks",
        code=(
            'def run(state):\n'
            '    data = json.loads(state.get("json_str", "[]"))\n'
            '    return {"count": len(data) if isinstance(data, list) else 0}\n'
        ),
        state={"json_str": "[1, 2, 3]"},
        expected="contained",
        output_predicate=lambda out: out.get("count") == 3,
        notes="Sync usage of json — async path unreachable; confirms asyncio.run() code is dead code in the sandbox",
    ),
    AttackCase(
        id="asyncio_sync_with_math",
        category="asyncio_tricks",
        code=(
            'def run(state):\n'
            '    result = sum(math.sqrt(i) for i in range(1, 10))\n'
            '    return {"result": round(result, 4)}\n'
        ),
        expected="contained",
        output_predicate=lambda out: isinstance(out.get("result"), float),
        notes="Sync math computation — confirms no async path needed",
    ),
    AttackCase(
        id="asyncio_sync_regex",
        category="asyncio_tricks",
        code=(
            'def run(state):\n'
            '    m = re.match(r"(\\w+)-(\\d+)", "hello-42")\n'
            '    if m:\n'
            '        return {"word": m.group(1), "num": int(m.group(2))}\n'
            '    return {"match": False}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("word") == "hello" and out.get("num") == 42,
        notes="Sync re.match — normal execution path",
    ),
    AttackCase(
        id="asyncio_sync_uuid",
        category="asyncio_tricks",
        code=(
            'def run(state):\n'
            '    uid = uuid4()\n'
            '    return {"uuid": str(uid), "version": uid.version}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("version") == 4,
        notes="Sync uuid4 — confirms no async path needed",
    ),

    # --- asyncio module itself not in scope ---
    AttackCase(
        id="asyncio_module_not_in_scope",
        category="asyncio_tricks",
        code=(
            'def run(state):\n'
            '    loop = asyncio.get_event_loop()\n'
            '    return {"loop": str(loop)}\n'
        ),
        expected="blocked",
        notes="asyncio not in restricted globals — NameError",
    ),
    AttackCase(
        id="asyncio_new_event_loop",
        category="asyncio_tricks",
        code=(
            'def run(state):\n'
            '    loop = asyncio.new_event_loop()\n'
            '    return {"loop": str(loop)}\n'
        ),
        expected="blocked",
        notes="asyncio not in scope — NameError",
    ),
    AttackCase(
        id="asyncio_run_not_available",
        category="asyncio_tricks",
        code=(
            'def inner():\n'
            '    return {"x": 1}\n'
            'def run(state):\n'
            '    return asyncio.run(inner())\n'
        ),
        expected="blocked",
        notes="asyncio not in scope; also inner() not callable from run()",
    ),
    AttackCase(
        id="asyncio_gather_not_available",
        category="asyncio_tricks",
        code=(
            'def run(state):\n'
            '    return asyncio.gather()\n'
        ),
        expected="blocked",
        notes="asyncio not in scope — NameError",
    ),
]
