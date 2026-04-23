"""RestrictedPython edge-case / compile-time attack cases (~50).

Key sandbox constraints discovered:
- async def / await / match / nonlocal: blocked at compile time
- class definitions: blocked at runtime (__metaclass__ not in restricted exec)
- Module-level functions: defined in locals_dict; run()'s __globals__ is the
  restricted globals dict, so module-level user-defined functions are invisible
  inside run() — only functions defined INSIDE run() body are accessible
- Generators: work only when defined INSIDE run() body
"""
from ._framework import AttackCase

CASES: list[AttackCase] = [
    # --- Walrus operator (works inside run()) ---
    AttackCase(
        id="edge_walrus_operator",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    if (n := 10) > 5:\n'
            '        return {"n": n}\n'
            '    return {"n": 0}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("n") == 10,
        notes="Walrus operator := — works inside run()",
    ),
    AttackCase(
        id="edge_walrus_in_while",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    items = [1, 2, 3]\n'
            '    results = []\n'
            '    while items:\n'
            '        results.append(x := items.pop())\n'
            '    return {"results": results}\n'
        ),
        expected="contained",
        output_predicate=lambda out: isinstance(out.get("results"), list),
        notes="Walrus in while loop — valid",
    ),
    AttackCase(
        id="edge_walrus_eval_trick",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    if (x := eval("1+1")):\n'
            '        return {"x": x}\n'
            '    return {"x": 0}\n'
        ),
        expected="blocked",
        notes="Walrus with eval() — eval not in builtins → NameError",
    ),

    # --- match/case: blocked at compile time ---
    AttackCase(
        id="edge_match_case_blocked",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    command = state.get("cmd", "help")\n'
            '    match command:\n'
            '        case "help":\n'
            '            return {"result": "showing help"}\n'
            '        case _:\n'
            '            return {"result": "unknown"}\n'
        ),
        state={"cmd": "help"},
        expected="blocked",
        notes="match/case — RestrictedPython: Match statements are not allowed",
    ),
    AttackCase(
        id="edge_match_case_class_pattern_blocked",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    val = 42\n'
            '    match val:\n'
            '        case int(x) if x > 0:\n'
            '            return {"type": "positive int", "x": x}\n'
            '        case _:\n'
            '            return {"type": "other"}\n'
        ),
        expected="blocked",
        notes="match/case with class pattern — blocked at compile time",
    ),

    # --- async def: blocked at compile time ---
    AttackCase(
        id="edge_async_def_blocked",
        category="restricted_edge",
        code=(
            'async def compute(state):\n'
            '    return {"result": 42}\n'
            'def run(state):\n'
            '    return compute(state)\n'
        ),
        expected="blocked",
        notes="async def at module level — RestrictedPython: AsyncFunctionDef not allowed",
    ),
    AttackCase(
        id="edge_async_def_inside_run_blocked",
        category="restricted_edge",
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
        id="edge_async_def_import_inside_blocked",
        category="restricted_edge",
        code=(
            'async def run_async(state):\n'
            '    import os\n'
            '    return {"cwd": os.getcwd()}\n'
            'def run(state):\n'
            '    return run_async(state)\n'
        ),
        expected="blocked",
        notes="import os inside async def — blocked first by async def restriction",
    ),

    # --- nonlocal: blocked at compile time ---
    AttackCase(
        id="edge_nonlocal_blocked",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    x = 0\n'
            '    def inner():\n'
            '        nonlocal x\n'
            '        x += 1\n'
            '    inner()\n'
            '    return {"x": x}\n'
        ),
        expected="blocked",
        notes="nonlocal statement — RestrictedPython: Nonlocal statements are not allowed",
    ),

    # --- Generator inside run() body (works!) ---
    AttackCase(
        id="edge_generator_inside_run",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    def gen():\n'
            '        for i in range(5):\n'
            '            yield i\n'
            '    return {"values": list(gen())}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("values") == [0, 1, 2, 3, 4],
        notes="Generator defined INSIDE run() — works (local scope visible to nested function)",
    ),
    AttackCase(
        id="edge_generator_yield_from_inside_run",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    def inner():\n'
            '        yield from range(3)\n'
            '    def outer():\n'
            '        yield from inner()\n'
            '    return {"values": list(outer())}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("values") == [0, 1, 2],
        notes="yield from in nested generator inside run() — valid",
    ),

    # --- class definitions: blocked at runtime (__metaclass__) ---
    AttackCase(
        id="edge_class_def_blocked",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    class Point:\n'
            '        def __init__(self, x, y):\n'
            '            self.x = x\n'
            '            self.y = y\n'
            '    p = Point(1, 2)\n'
            '    return {"x": p.x, "y": p.y}\n'
        ),
        expected="blocked",
        notes="Class definition — blocked: __metaclass__ not in restricted exec namespace",
    ),
    AttackCase(
        id="edge_class_inheriting_blocked",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    class MyDict(dict):\n'
            '        def get_all(self):\n'
            '            return list(self.values())\n'
            '    d = MyDict({"a": 1})\n'
            '    return {"values": d.get_all()}\n'
        ),
        expected="blocked",
        notes="Class inheriting dict — blocked (__metaclass__)",
    ),
    AttackCase(
        id="edge_class_metaclass_exec_attempt",
        category="restricted_edge",
        code=(
            'class Meta(type):\n'
            '    def __new__(mcs, name, bases, ns):\n'
            '        exec("import os")\n'
            '        return super().__new__(mcs, name, bases, ns)\n'
            'class Evil(metaclass=Meta):\n'
            '    pass\n'
            'def run(state):\n'
            '    return {"x": str(Evil)}\n'
        ),
        expected="blocked",
        notes="Metaclass with exec — blocked: class fails, exec not in builtins, super not in builtins",
    ),
    AttackCase(
        id="edge_class_descriptor_blocked",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    class Descriptor:\n'
            '        def __get__(self, obj, objtype=None):\n'
            '            return 42\n'
            '    class MyClass:\n'
            '        value = Descriptor()\n'
            '    obj = MyClass()\n'
            '    return {"value": obj.value}\n'
        ),
        expected="blocked",
        notes="Descriptor class inside run — blocked (__metaclass__)",
    ),

    # --- Module-level functions not accessible from run() ---
    AttackCase(
        id="edge_module_level_function_not_accessible",
        category="restricted_edge",
        code=(
            'def helper(x):\n'
            '    return x * 2\n'
            'def run(state):\n'
            '    return {"result": helper(21)}\n'
        ),
        expected="blocked",
        notes="Module-level helper() — not accessible from run() (exec locals/globals separation)",
    ),
    AttackCase(
        id="edge_module_level_variable_not_accessible",
        category="restricted_edge",
        code=(
            'CONSTANT = 42\n'
            'def run(state):\n'
            '    return {"value": CONSTANT}\n'
        ),
        expected="blocked",
        notes="Module-level variable — not visible inside run() (exec locals vs globals)",
    ),

    # --- F-string edge cases ---
    AttackCase(
        id="edge_fstring_basic",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    name = state.get("name", "World")\n'
            '    return {"greeting": f"Hello, {name}!"}\n'
        ),
        state={"name": "Test"},
        expected="contained",
        output_predicate=lambda out: out.get("greeting") == "Hello, Test!",
        notes="f-string — basic valid usage",
    ),
    AttackCase(
        id="edge_fstring_format_spec",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    x = 3.14\n'
            '    fmt = f"{x:.2f}"\n'
            '    return {"fmt": fmt}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("fmt") == "3.14",
        notes="f-string with format spec",
    ),
    AttackCase(
        id="edge_fstring_nested_expression",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    data = [1, 2, 3]\n'
            '    result = f"sum={sum(data)}, max={max(data)}"\n'
            '    return {"result": result}\n'
        ),
        expected="contained",
        output_predicate=lambda out: "sum=6" in out.get("result", ""),
        notes="f-string with nested expressions",
    ),
    AttackCase(
        id="edge_fstring_dunder_access_blocked",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    s = "hello"\n'
            '    result = f"{s.__class__}"\n'
            '    return {"result": result}\n'
        ),
        expected="blocked",
        notes="f-string accessing .__class__ — transformer converts to _getattr_ which blocks _-prefix",
    ),

    # --- Decorator (non-class, inside run()) ---
    AttackCase(
        id="edge_decorator_inside_run",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    def my_decorator(func):\n'
            '        def wrapper(*args, **kwargs):\n'
            '            return func(*args, **kwargs)\n'
            '        return wrapper\n'
            '    @my_decorator\n'
            '    def helper(x):\n'
            '        return x * 2\n'
            '    return {"result": helper(21)}\n'
        ),
        expected="blocked",
        notes="Decorators with *args/**kwargs require _apply_() which is not in restricted globals — NameError",
    ),
    AttackCase(
        id="edge_decorator_exec_blocked",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    def evil_decorator(func):\n'
            '        exec("import os")\n'
            '        return func\n'
            '    @evil_decorator\n'
            '    def helper():\n'
            '        pass\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="Decorator calling exec() — exec not in builtins",
    ),

    # --- Lambda edge cases ---
    AttackCase(
        id="edge_lambda_nested",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    compose = lambda f, g: lambda x: f(g(x))\n'
            '    double = lambda x: x * 2\n'
            '    inc = lambda x: x + 1\n'
            '    double_then_inc = compose(inc, double)\n'
            '    return {"result": double_then_inc(5)}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("result") == 11,
        notes="Nested lambdas — valid (defined inside run)",
    ),
    AttackCase(
        id="edge_lambda_with_default_eval",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    f = lambda x, default=eval("1+1"): x + default\n'
            '    return {"result": f(40)}\n'
        ),
        expected="blocked",
        notes="Lambda default with eval() — eval not in builtins, evaluated at lambda creation",
    ),

    # --- Comprehension edge cases ---
    AttackCase(
        id="edge_list_comp_nested",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    matrix = [[1, 2, 3], [4, 5, 6]]\n'
            '    flat = [x for row in matrix for x in row]\n'
            '    return {"flat": flat}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("flat") == [1, 2, 3, 4, 5, 6],
        notes="Nested list comprehension — valid",
    ),
    AttackCase(
        id="edge_dict_comp_import_attempt",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    d = {k: __import__(k) for k in ["os", "sys"]}\n'
            '    return {"x": str(d)}\n'
        ),
        expected="blocked",
        notes="dict comprehension with __import__ — blocked (not in builtins)",
    ),
    AttackCase(
        id="edge_set_comp_valid",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    result = {x for x in range(10)}\n'
            '    return {"result": sorted(result)}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("result") == list(range(10)),
        notes="Set comprehension — valid",
    ),

    # --- Exception handling ---
    AttackCase(
        id="edge_raise_from_chain_blocked",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    try:\n'
            '        try:\n'
            '            raise ValueError("inner")\n'
            '        except ValueError as e:\n'
            '            raise RuntimeError("outer") from e\n'
            '    except RuntimeError as e:\n'
            '        return {"error": str(e), "cause": str(e.__cause__)}\n'
        ),
        expected="blocked",
        notes="e.__cause__ — __cause__ starts with _, blocked by transformer or safer_getattr",
    ),
    AttackCase(
        id="edge_exception_handling_valid",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    try:\n'
            '        x = 1 / 0\n'
            '    except ZeroDivisionError as e:\n'
            '        return {"error": str(e), "type": "ZeroDivisionError"}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("type") == "ZeroDivisionError",
        notes="Exception handling — valid",
    ),

    # --- Type annotations ---
    AttackCase(
        id="edge_type_annotations_on_run",
        category="restricted_edge",
        code=(
            'def run(state: dict) -> dict:\n'
            '    items = state.get("items", [1, 2, 3])\n'
            '    return {"result": [x * 2 for x in items]}\n'
        ),
        state={"items": [1, 2, 3]},
        expected="contained",
        output_predicate=lambda out: out.get("result") == [2, 4, 6],
        notes="Type annotations on run() — valid PEP 3107 syntax",
    ),

    # --- Star expressions ---
    AttackCase(
        id="edge_star_unpack",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    first, *rest = [1, 2, 3, 4, 5]\n'
            '    *init, last = [1, 2, 3, 4, 5]\n'
            '    return {"first": first, "rest": rest, "last": last}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("first") == 1 and out.get("last") == 5,
        notes="Star unpacking — valid",
    ),
    AttackCase(
        id="edge_double_star_dict_merge",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    a = {"x": 1}\n'
            '    b = {"y": 2}\n'
            '    merged = {**a, **b}\n'
            '    return merged\n'
        ),
        expected="contained",
        output_predicate=lambda out: out == {"x": 1, "y": 2},
        notes="Dict merge with ** — valid",
    ),

    # --- del statement ---
    AttackCase(
        id="edge_del_dict_key",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    d = {"a": 1, "b": 2}\n'
            '    del d["a"]\n'
            '    return d\n'
        ),
        expected="contained",
        output_predicate=lambda out: out == {"b": 2},
        notes="del dict key — valid",
    ),
    AttackCase(
        id="edge_del_variable",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    x = 42\n'
            '    del x\n'
            '    try:\n'
            '        return {"x": x}\n'
            '    except NameError:\n'
            '        return {"deleted": True}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("deleted") is True,
        notes="del variable — valid",
    ),

    # --- property, classmethod, staticmethod not in builtins ---
    AttackCase(
        id="edge_property_not_in_builtins",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    prop = property(lambda self: 42)\n'
            '    return {"x": str(prop)}\n'
        ),
        expected="blocked",
        notes="property() not in restricted builtins — NameError",
    ),
    AttackCase(
        id="edge_classmethod_not_in_builtins",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    cm = classmethod(lambda cls: cls)\n'
            '    return {"x": str(cm)}\n'
        ),
        expected="blocked",
        notes="classmethod() not in restricted builtins — NameError",
    ),
    AttackCase(
        id="edge_staticmethod_not_in_builtins",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    sm = staticmethod(lambda: 42)\n'
            '    return {"x": str(sm)}\n'
        ),
        expected="blocked",
        notes="staticmethod() not in restricted builtins — NameError",
    ),
    AttackCase(
        id="edge_super_not_in_builtins",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    s = super()\n'
            '    return {"x": str(s)}\n'
        ),
        expected="blocked",
        notes="super() not in restricted builtins — NameError",
    ),
    AttackCase(
        id="edge_type_not_in_builtins",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    t = type("hello")\n'
            '    return {"x": str(t)}\n'
        ),
        expected="blocked",
        notes="type() not in restricted builtins — NameError",
    ),

    # --- Import-adjacent edge cases ---
    AttackCase(
        id="edge_import_inside_lambda",
        category="restricted_edge",
        code=(
            'def run(state):\n'
            '    f = lambda: __import__("os")\n'
            '    return {"x": str(f())}\n'
        ),
        expected="blocked",
        notes="__import__ in lambda — not in builtins, NameError at lambda call time",
    ),
    AttackCase(
        id="edge_dataclass_import",
        category="restricted_edge",
        code=(
            'from dataclasses import dataclass\n'
            'def run(state):\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="from dataclasses import dataclass — blocked",
    ),

    # --- Encoding / BOM ---
    AttackCase(
        id="edge_encoding_declaration",
        category="restricted_edge",
        code=(
            '# -*- coding: utf-8 -*-\n'
            'def run(state):\n'
            '    return {"x": "hello ñoño"}\n'
        ),
        expected="contained",
        output_predicate=lambda out: "hello" in out.get("x", ""),
        notes="UTF-8 encoding declaration — valid",
    ),

    # --- Lots of variables (compiler test) ---
    AttackCase(
        id="edge_many_variables",
        category="restricted_edge",
        code=(
            "def run(state):\n"
            + "\n".join(f"    x{i} = {i}" for i in range(200))
            + "\n    return {\"total\": " + "+".join(f"x{i}" for i in range(200)) + "}\n"
        ),
        expected="contained",
        output_predicate=lambda out: out.get("total") == sum(range(200)),
        notes="200 variable assignments inside run() — compiler handles OK",
    ),
]
