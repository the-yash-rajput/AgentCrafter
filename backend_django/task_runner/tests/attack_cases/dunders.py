"""Dunder / attribute-walk attack cases (~200).

safer_getattr blocks names starting with '_' and INSPECT_ATTRIBUTES.
Every attempt to read a dunder attribute via obj.attr syntax should raise.
"""
from ._framework import AttackCase

# Base object expressions and their safe names
_OBJECTS: list[tuple[str, str]] = [
    ('""', "empty_string"),
    ("b''", "bytes"),
    ("()", "empty_tuple"),
    ("[]", "empty_list"),
    ("{}", "empty_dict"),
    ("0", "int_zero"),
    ("0.0", "float_zero"),
    ("True", "bool_true"),
    ("None", "none_val"),
    ("lambda: None", "lambda_val"),
]

# Dunder attribute names to try
_DUNDERS: list[str] = [
    "__class__",
    "__bases__",
    "__mro__",
    "__subclasses__",
    "__globals__",
    "__builtins__",
    "__dict__",
    "__code__",
    "__closure__",
    "__reduce__",
    "__reduce_ex__",
    "__init_subclass__",
    "__import__",
    "__loader__",
    "__spec__",
    "__module__",
    "__qualname__",
    "__doc__",
    "__init__",
    "__new__",
]


def _make_cases() -> list[AttackCase]:
    cases: list[AttackCase] = []

    # Direct dunder access: obj.__dunder__
    for obj_expr, obj_name in _OBJECTS:
        for dunder in _DUNDERS:
            cases.append(AttackCase(
                id=f"dunder_direct_{obj_name}_{dunder.strip('_')}",
                category="dunders",
                code=(
                    f"def run(state):\n"
                    f"    obj = {obj_expr}\n"
                    f"    val = obj.{dunder}\n"
                    f"    return {{'val': str(val)}}\n"
                ),
                expected="blocked",
                notes=f"Direct {obj_expr}.{dunder} — blocked by safer_getattr (_-prefix rule)",
            ))

    # Chained dunder access attempts
    _CHAINS = [
        ('""', "string_class_bases", '"".__class__.__bases__'),
        ('""', "string_class_mro", '"".__class__.__mro__'),
        ('""', "string_subclasses", '"".__class__.__subclasses__()'),
        ("[]", "list_class_bases", "[].__class__.__bases__"),
        ("0", "int_class_mro", "(0).__class__.__mro__"),
        ("lambda: None", "lambda_globals", "(lambda: None).__globals__"),
        ("lambda: None", "lambda_code", "(lambda: None).__code__"),
        ("lambda: None", "lambda_closure", "(lambda: None).__closure__"),
        ('""', "string_dict", '"".__dict__'),
        ("().__class__", "tuple_class_dict", "().__class__.__dict__"),
    ]
    for obj_expr, name, chain_expr in _CHAINS:
        cases.append(AttackCase(
            id=f"dunder_chain_{name}",
            category="dunders",
            code=(
                f"def run(state):\n"
                f"    val = {chain_expr}\n"
                f"    return {{'val': str(val)}}\n"
            ),
            expected="blocked",
            notes=f"Chained dunder walk: {chain_expr}",
        ))

    # Classic CPython sandbox escape: type(x).__mro__[-1].__subclasses__()
    _CLASSIC_ESCAPES = [
        (
            "classic_escape_via_mro_subclasses",
            "type(x).__mro__[-1].__subclasses__()",
            "x = ''\nval = type(x).__mro__[-1].__subclasses__()",
        ),
        (
            "classic_escape_via_bases",
            "().__class__.__bases__[0].__subclasses__()",
            "val = ().__class__.__bases__[0].__subclasses__()",
        ),
        (
            "escape_via_type_call",
            "type('').__mro__",
            "val = type('').__mro__",
        ),
        (
            "escape_string_class_dict_items",
            "str.__dict__.items()",
            "val = str.__dict__.items()",
        ),
        (
            "escape_via_object_class",
            "object.__subclasses__()",
            "val = object.__subclasses__()",
        ),
    ]
    for name, chain_desc, body in _CLASSIC_ESCAPES:
        cases.append(AttackCase(
            id=f"dunder_classic_{name}",
            category="dunders",
            code=(
                f"def run(state):\n"
                f"    {body}\n"
                f"    return {{'val': str(val)}}\n"
            ),
            expected="blocked",
            notes=f"Classic escape: {chain_desc} — type() not in builtins, or __mro__/__subclasses__ blocked",
        ))

    # Format string bypass attempts — str.format and str.format_map are blocked
    _FORMAT_ATTACKS = [
        (
            "format_class_via_str",
            '"{0.__class__}".format("")',
            "format/format_map blocked on str by safer_getattr",
        ),
        (
            "format_map_attack",
            '"{key.__class__}".format_map({"key": ""})',
            "format_map blocked on str by safer_getattr",
        ),
        (
            "format_mro_via_str",
            '"{0.__class__.__mro__}".format("")',
            "format blocked on str, also __mro__ is dunder",
        ),
        (
            "format_globals_via_lambda",
            '"{0.__globals__}".format(lambda: None)',
            "format blocked on str",
        ),
        (
            "format_subclasses_chain",
            '"{0.__class__.__bases__[0].__subclasses__()}".format("")',
            "format blocked on str",
        ),
    ]
    for name, expr, note in _FORMAT_ATTACKS:
        cases.append(AttackCase(
            id=f"dunder_format_{name}",
            category="dunders",
            code=(
                f"def run(state):\n"
                f"    val = {expr}\n"
                f"    return {{'val': str(val)}}\n"
            ),
            expected="blocked",
            notes=note,
        ))

    # string.Formatter bypass — previously a partial bypass (info leak).
    # CLOSED: string helper is now a SimpleNamespace of constants only;
    # string.Formatter no longer exists in the sandbox.
    _FORMATTER_ATTACKS = [
        (
            "formatter_class_via_string",
            'string.Formatter().format("{0.__class__}", "")',
            "string.Formatter removed — string helper is now constants-only SimpleNamespace",
        ),
        (
            "formatter_mro_via_string",
            'string.Formatter().format("{0.__class__.__mro__}", "")',
            "string.Formatter removed",
        ),
        (
            "formatter_subclasses",
            'string.Formatter().format("{0.__class__.__bases__}", "")',
            "string.Formatter removed",
        ),
        (
            "formatter_doc_via_math",
            'string.Formatter().format("{0.__doc__}", math)',
            "string.Formatter removed",
        ),
        (
            "formatter_class_of_json",
            'string.Formatter().format("{0.__class__.__name__}", json)',
            "string.Formatter removed",
        ),
    ]
    for name, expr, note in _FORMATTER_ATTACKS:
        cases.append(AttackCase(
            id=f"dunder_formatter_{name}",
            category="dunders",
            code=(
                f"def run(state):\n"
                f"    val = {expr}\n"
                f"    return {{'val': str(val)}}\n"
            ),
            expected="blocked",
            notes=note,
        ))

    # getattr() direct call — getattr is not in builtins
    _GETATTR_ATTACKS = [
        ("getattr_class", 'getattr("", "__class__")'),
        ("getattr_builtins", "getattr(run, '__globals__')"),
        ("getattr_module", "getattr(json, '__loader__')"),
        ("getattr_reduce", "getattr([], '__reduce__')"),
        ("getattr_dict", "getattr([], '__dict__')"),
    ]
    for name, expr in _GETATTR_ATTACKS:
        cases.append(AttackCase(
            id=f"dunder_getattr_{name}",
            category="dunders",
            code=(
                f"def run(state):\n"
                f"    val = {expr}\n"
                f"    return {{'val': str(val)}}\n"
            ),
            expected="blocked",
            notes="getattr() not in builtins — NameError",
        ))

    # vars() / dir() / locals() / globals() calls — not in builtins
    for builtin_name in ("vars", "dir", "locals", "globals", "input"):
        cases.append(AttackCase(
            id=f"dunder_builtin_{builtin_name}",
            category="dunders",
            code=(
                f"def run(state):\n"
                f"    val = {builtin_name}()\n"
                f"    return {{'val': str(val)}}\n"
            ),
            expected="blocked",
            notes=f"{builtin_name}() not in restricted builtins — NameError",
        ))

    # Accessing INSPECT_ATTRIBUTES via safe helpers
    _INSPECT_ATTR_ATTACKS = [
        ("gi_frame_via_gen", "gi_frame", "gen = (x for x in [1])\nval = gen.gi_frame"),
        ("gi_code_via_gen", "gi_code", "gen = (x for x in [1])\nval = gen.gi_code"),
        ("gi_yieldfrom_via_gen", "gi_yieldfrom", "gen = (x for x in [1])\nval = gen.gi_yieldfrom"),
        ("f_globals_via_frame", "f_globals", "def inner(): pass\nval = inner.f_globals"),
        ("cr_frame_via_coro", "cr_frame",
         "async def c(): pass\ncoro = c()\nval = coro.cr_frame"),
    ]
    for name, attr, body in _INSPECT_ATTR_ATTACKS:
        cases.append(AttackCase(
            id=f"dunder_inspect_{name}",
            category="dunders",
            code=(
                f"def run(state):\n"
                f"    {body}\n"
                f"    return {{'val': str(val)}}\n"
            ),
            expected="blocked",
            notes=f"INSPECT_ATTRIBUTES: .{attr} blocked by safer_getattr",
        ))

    return cases


CASES: list[AttackCase] = _make_cases()
