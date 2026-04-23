"""eval / exec / compile attack cases (~40).

None of eval, exec, compile are in restricted builtins.
All attempts should raise NameError → PythonTaskError.
Also tests attempts to reach them via __builtins__ attribute walks.
"""
from ._framework import AttackCase

CASES: list[AttackCase] = [
    # --- Direct calls (NameError expected) ---
    AttackCase(
        id="eval_direct_call",
        category="eval_exec",
        code='def run(state):\n    return {"x": eval("1+1")}\n',
        expected="blocked",
        notes="eval() not in restricted builtins",
    ),
    AttackCase(
        id="exec_direct_call",
        category="eval_exec",
        code='def run(state):\n    exec("x = 1")\n    return {"x": 1}\n',
        expected="blocked",
        notes="exec() not in restricted builtins",
    ),
    AttackCase(
        id="compile_direct_call",
        category="eval_exec",
        code='def run(state):\n    co = compile("1+1","<>","eval")\n    return {"x": 1}\n',
        expected="blocked",
        notes="compile() not in restricted builtins",
    ),
    AttackCase(
        id="eval_os_import",
        category="eval_exec",
        code='def run(state):\n    return {"x": eval("__import__(\'os\').getcwd()")}\n',
        expected="blocked",
        notes="eval() not available; even if it were, __import__ also not available",
    ),
    AttackCase(
        id="exec_code_string",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    code = "import os; result = os.getcwd()"\n'
            '    exec(code)\n'
            '    return {"x": result}\n'
        ),
        expected="blocked",
        notes="exec() not in restricted builtins",
    ),
    AttackCase(
        id="exec_compile_combination",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    co = compile("1+1", "<>", "eval")\n'
            '    return {"x": eval(co)}\n'
        ),
        expected="blocked",
        notes="compile() not available",
    ),
    AttackCase(
        id="eval_inside_try",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    try:\n'
            '        result = eval("__import__(\'os\')")\n'
            '    except Exception:\n'
            '        result = None\n'
            '    return {"result": str(result)}\n'
        ),
        expected="blocked",
        notes="eval() — RestrictedPython blocks eval calls at COMPILE TIME (not just runtime NameError)",
    ),
    AttackCase(
        id="exec_inside_lambda",
        category="eval_exec",
        code='f = lambda: exec("x=1")\ndef run(state):\n    f()\n    return {"x": 1}\n',
        expected="blocked",
        notes="exec() inside lambda — NameError when lambda is called",
    ),

    # --- Attempts to reach eval/exec via __builtins__ ---
    AttackCase(
        id="builtins_eval_via_dunder",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    bi = __builtins__\n'
            '    return {"x": str(bi["eval"])}\n'
        ),
        expected="blocked",
        notes="__builtins__ starts with _ — blocked by safer_getattr or NameError",
    ),
    AttackCase(
        id="builtins_dict_eval",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    ev = __builtins__["eval"]\n'
            '    return {"x": ev("1+1")}\n'
        ),
        expected="blocked",
        notes="__builtins__ not accessible",
    ),

    # --- Attempts via safe helper module attributes ---
    AttackCase(
        id="json_builtins_eval",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    ev = json.__builtins__["eval"]\n'
            '    return {"x": ev("1+1")}\n'
        ),
        expected="blocked",
        notes="json.__builtins__ starts with _ — blocked by safer_getattr",
    ),
    AttackCase(
        id="math_builtins_eval",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    ev = math.__builtins__["eval"]\n'
            '    return {"x": ev("1+1")}\n'
        ),
        expected="blocked",
        notes="math.__builtins__ starts with _ — blocked",
    ),
    AttackCase(
        id="re_builtins_eval",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    ev = re.__builtins__["eval"]\n'
            '    return {"x": ev("1+1")}\n'
        ),
        expected="blocked",
        notes="re.__builtins__ starts with _ — blocked",
    ),
    AttackCase(
        id="json_globals_eval",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    g = json.__loader__\n'
            '    return {"x": str(g)}\n'
        ),
        expected="blocked",
        notes="json.__loader__ starts with _ — blocked",
    ),

    # --- Type / class construction to get eval ---
    AttackCase(
        id="type_call_direct",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    T = type("Evil", (), {"run": lambda self: eval("1+1")})\n'
            '    return {"x": T().run()}\n'
        ),
        expected="blocked",
        notes="type() not in restricted builtins",
    ),
    AttackCase(
        id="build_class_with_exec",
        category="eval_exec",
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
        notes="exec in metaclass __new__ — exec not in builtins; also type/super may be restricted",
    ),

    # --- Trying exec via object / super tricks ---
    AttackCase(
        id="super_call_attempt",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    class A:\n'
            '        pass\n'
            '    class B(A):\n'
            '        def method(self):\n'
            '            return super()\n'
            '    return {"x": str(B().method())}\n'
        ),
        expected="blocked",
        notes="super() not in restricted builtins",
    ),
    AttackCase(
        id="object_subclasses_call",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    subs = object.__subclasses__()\n'
            '    return {"count": len(subs)}\n'
        ),
        expected="blocked",
        notes="object.__subclasses__ — __subclasses__ starts with _ (actually not), but object is not in builtins",
    ),

    # --- exec via code object ---
    AttackCase(
        id="exec_code_object",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    import types\n'
            '    co = types.CodeType(0, 0, 0, 0, 0, 0, b"", (), (), (), "<>", "<>", 0, b"", b"", (), ())\n'
            '    exec(co)\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import types blocked; exec blocked",
    ),

    # --- Reaching eval via sys.modules ---
    AttackCase(
        id="sys_modules_builtins_eval",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    import sys\n'
            '    bi = sys.modules["builtins"]\n'
            '    return {"x": bi.eval("1+1")}\n'
        ),
        expected="blocked",
        notes="import sys blocked",
    ),

    # --- Decode-based code injection ---
    AttackCase(
        id="base64_exec_attempt",
        category="eval_exec",
        code=(
            'import base64\n'
            'def run(state):\n'
            '    code = base64.b64decode(b"aW1wb3J0IG9z").decode()\n'
            '    exec(code)\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import base64 blocked",
    ),
    AttackCase(
        id="codecs_decode_exec",
        category="eval_exec",
        code=(
            'import codecs\n'
            'def run(state):\n'
            '    code = codecs.decode("aW1wb3J0IG9z", "base64").decode()\n'
            '    exec(code)\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import codecs blocked",
    ),

    # --- Unusual eval-like constructs ---
    AttackCase(
        id="timeit_exec_attempt",
        category="eval_exec",
        code=(
            'import timeit\n'
            'def run(state):\n'
            '    timeit.timeit("import os", number=1)\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import timeit blocked",
    ),
    AttackCase(
        id="json_object_hook_exec",
        category="eval_exec",
        code=(
            'def hook(d):\n'
            '    exec("import os")\n'
            '    return d\n'
            'def run(state):\n'
            '    result = json.loads(\'{"x": 1}\', object_hook=hook)\n'
            '    return result\n'
        ),
        expected="blocked",
        notes="exec() inside json object_hook — exec not in builtins",
    ),

    # --- Walrus operator with eval attempt ---
    AttackCase(
        id="walrus_eval",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    if x := eval("1+1"):\n'
            '        return {"x": x}\n'
            '    return {"x": 0}\n'
        ),
        expected="blocked",
        notes="eval() not in builtins — NameError",
    ),

    # --- Nested function exec ---
    AttackCase(
        id="nested_function_exec",
        category="eval_exec",
        code=(
            'def outer():\n'
            '    def inner():\n'
            '        exec("import os")\n'
            '    inner()\n'
            'def run(state):\n'
            '    outer()\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="exec() inside nested function — exec not in builtins",
    ),

    # --- Generator-based exec ---
    AttackCase(
        id="generator_eval_attempt",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    results = list(eval(expr) for expr in ["1+1", "2+2"])\n'
            '    return {"results": results}\n'
        ),
        expected="blocked",
        notes="eval() not in builtins — NameError in generator",
    ),

    # --- eval via __class__ cell reference trick ---
    AttackCase(
        id="class_cell_eval_trick",
        category="eval_exec",
        code=(
            'class Tricky:\n'
            '    _x = eval("1")\n'
            'def run(state):\n'
            '    return {"x": Tricky._x}\n'
        ),
        expected="blocked",
        notes="eval in class body — eval not in builtins; also _x starts with _ so access blocked",
    ),

    # --- input() as code injection vector ---
    AttackCase(
        id="input_not_in_builtins",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    val = input("Enter code: ")\n'
            '    return {"val": val}\n'
        ),
        expected="blocked",
        notes="input() not in restricted builtins — NameError",
    ),

    # --- open() for code reading/writing ---
    AttackCase(
        id="open_not_in_builtins",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    f = open("/etc/passwd", "r")\n'
            '    return {"content": f.read()}\n'
        ),
        expected="blocked",
        notes="open() not in restricted builtins — NameError",
    ),

    # --- memoryview / bytearray for code smuggling ---
    AttackCase(
        id="memoryview_not_in_builtins",
        category="eval_exec",
        code=(
            'def run(state):\n'
            '    mv = memoryview(b"import os")\n'
            '    return {"x": str(mv)}\n'
        ),
        expected="blocked",
        notes="memoryview() not in restricted builtins",
    ),
]
