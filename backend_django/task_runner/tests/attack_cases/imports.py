"""Import-blocking attack cases (~120).

Every import attempt should raise PythonTaskConfigurationError or PythonTaskError
because __import__ is not present in the restricted builtins.
"""
from ._framework import AttackCase

# (module_name, a_subattr_or_function_name)
_DANGEROUS_MODULES: list[tuple[str, str]] = [
    ("os", "getcwd"),
    ("sys", "executable"),
    ("subprocess", "run"),
    ("socket", "socket"),
    ("ctypes", "CDLL"),
    ("importlib", "import_module"),
    ("builtins", "eval"),
    ("pickle", "loads"),
    ("marshal", "loads"),
    ("code", "InteractiveConsole"),
    ("io", "open"),
    ("pathlib", "Path"),
    ("shutil", "copy"),
    ("tempfile", "mkstemp"),
    ("threading", "Thread"),
    ("multiprocessing", "Process"),
    ("signal", "signal"),
    ("resource", "getrlimit"),
    ("types", "FunctionType"),
    ("inspect", "getmembers"),
    ("ast", "parse"),
    ("gc", "get_objects"),
    ("weakref", "ref"),
    ("faulthandler", "dump_traceback"),
]


def _make_cases() -> list[AttackCase]:
    cases: list[AttackCase] = []

    for mod, attr in _DANGEROUS_MODULES:
        # Style 1: top-level import, use inside run()
        cases.append(AttackCase(
            id=f"import_{mod}_toplevel",
            category="imports",
            code=(
                f"import {mod}\n"
                f"def run(state):\n"
                f"    return {{'x': str({mod}.{attr})}}\n"
            ),
            expected="blocked",
            notes=f"top-level `import {mod}` — blocked because __import__ not in builtins",
        ))

        # Style 2: import with alias at top level
        cases.append(AttackCase(
            id=f"import_{mod}_alias",
            category="imports",
            code=(
                f"import {mod} as _alias_mod\n"
                f"def run(state):\n"
                f"    return {{'x': str(_alias_mod)}}\n"
            ),
            expected="blocked",
            notes=f"`import {mod} as alias` at top level",
        ))

        # Style 3: from-import at top level
        cases.append(AttackCase(
            id=f"from_{mod}_import_{attr}",
            category="imports",
            code=(
                f"from {mod} import {attr}\n"
                f"def run(state):\n"
                f"    return {{'x': str({attr})}}\n"
            ),
            expected="blocked",
            notes=f"`from {mod} import {attr}` at top level",
        ))

        # Style 4: import inside run() body
        cases.append(AttackCase(
            id=f"import_{mod}_inside_run",
            category="imports",
            code=(
                f"def run(state):\n"
                f"    import {mod}\n"
                f"    return {{'x': str({mod}.{attr})}}\n"
            ),
            expected="blocked",
            notes=f"deferred `import {mod}` inside run() body",
        ))

        # Style 5: from-star import at top level
        cases.append(AttackCase(
            id=f"from_{mod}_import_star",
            category="imports",
            code=(
                f"from {mod} import *\n"
                f"def run(state):\n"
                f"    return {{'x': 'attempted star import'}}\n"
            ),
            expected="blocked",
            notes=f"`from {mod} import *` at top level",
        ))

    # Extra: import inside try/except attempting to silence the error
    cases.append(AttackCase(
        id="import_os_try_except",
        category="imports",
        code=(
            "def run(state):\n"
            "    try:\n"
            "        import os\n"
            "        return {'escaped': True, 'cwd': os.getcwd()}\n"
            "    except Exception:\n"
            "        return {'escaped': False}\n"
        ),
        expected="contained",
        output_predicate=lambda out: out.get("escaped") is False,
        notes="import inside try/except — error should be caught, escaped=False",
    ))

    # Extra: import inside lambda (compile-time detection test)
    cases.append(AttackCase(
        id="import_inside_lambda",
        category="imports",
        code=(
            "f = lambda: __import__('os')\n"
            "def run(state):\n"
            "    return {'x': str(f())}\n"
        ),
        expected="blocked",
        notes="__import__ call in lambda — blocked at exec",
    ))

    # Extra: __import__ called directly
    cases.append(AttackCase(
        id="direct_dunder_import_os",
        category="imports",
        code=(
            "def run(state):\n"
            "    m = __import__('os')\n"
            "    return {'cwd': m.getcwd()}\n"
        ),
        expected="blocked",
        notes="direct __import__('os') call — __import__ not in builtins",
    ))

    # Extra: __import__ via builtins attribute walk (should also fail)
    cases.append(AttackCase(
        id="dunder_import_via_builtins",
        category="imports",
        code=(
            "def run(state):\n"
            "    bi = __builtins__\n"
            "    return {'x': str(bi)}\n"
        ),
        expected="blocked",
        notes="accessing __builtins__ directly — starts with _, blocked by safer_getattr or NameError",
    ))

    # Extra: import inside comprehension
    cases.append(AttackCase(
        id="import_os_in_comprehension",
        category="imports",
        code=(
            "def run(state):\n"
            "    result = [__import__('os').getcwd() for _ in range(1)]\n"
            "    return {'result': result}\n"
        ),
        expected="blocked",
        notes="__import__ inside list comprehension",
    ))

    # Extra: nested from-import
    cases.append(AttackCase(
        id="from_os_path_import_join",
        category="imports",
        code=(
            "from os.path import join\n"
            "def run(state):\n"
            "    return {'x': join('/tmp', 'x')}\n"
        ),
        expected="blocked",
        notes="from os.path import join",
    ))

    return cases


CASES: list[AttackCase] = _make_cases()
