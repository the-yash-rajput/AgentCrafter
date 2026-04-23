import builtins
import datetime as datetime_module
import json
import math
import operator
import random
import re
import statistics
import string
import types
import uuid
from collections import Counter
from decimal import Decimal

from RestrictedPython import PrintCollector, safe_globals
from RestrictedPython.Eval import default_guarded_getitem, default_guarded_getiter
from RestrictedPython.Guards import (
    full_write_guard,
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safe_builtins,
    safer_getattr,
)


_EXTRA_SAFE_BUILTINS = {
    name: getattr(builtins, name)
    for name in (
        "all",
        "any",
        "dict",
        "enumerate",
        "filter",
        "float",
        "frozenset",
        "int",
        "len",
        "list",
        "map",
        "max",
        "min",
        "range",
        "reversed",
        "round",
        "set",
        "str",
        "sum",
    )
}

_INPLACE_OPERATORS = {
    "+=": operator.add,
    "-=": operator.sub,
    "*=": operator.mul,
    "/=": operator.truediv,
    "%=": operator.mod,
    "**=": operator.pow,
    "//=": operator.floordiv,
    "<<=": operator.lshift,
    ">>=": operator.rshift,
    "&=": operator.and_,
    "|=": operator.or_,
    "^=": operator.xor,
}

_string_constants = types.SimpleNamespace(
    ascii_letters=string.ascii_letters,
    ascii_lowercase=string.ascii_lowercase,
    ascii_uppercase=string.ascii_uppercase,
    digits=string.digits,
    hexdigits=string.hexdigits,
    octdigits=string.octdigits,
    punctuation=string.punctuation,
    printable=string.printable,
    whitespace=string.whitespace,
)

_SAFE_HELPERS = {
    "Counter": Counter,
    "Decimal": Decimal,
    "date": datetime_module.date,
    "datetime": datetime_module.datetime,
    "json": json,
    "math": math,
    "random": random,
    "re": re,
    "statistics": statistics,
    "string": _string_constants,
    "time": datetime_module.time,
    "timedelta": datetime_module.timedelta,
    "uuid4": uuid.uuid4,
}


def _apply_inplace_operator(operation: str, left, right):
    handler = _INPLACE_OPERATORS.get(operation)
    if handler is None:
        raise TypeError(f"Unsupported inplace operator '{operation}'")
    return handler(left, right)


def build_restricted_globals() -> dict:
    return {
        **safe_globals,
        "__builtins__": {**safe_builtins, **_EXTRA_SAFE_BUILTINS},
        "_getattr_": safer_getattr,
        "_getitem_": default_guarded_getitem,
        "_getiter_": default_guarded_getiter,
        "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
        "_unpack_sequence_": guarded_unpack_sequence,
        "_write_": full_write_guard,
        "_inplacevar_": _apply_inplace_operator,
        "_print_": PrintCollector,
        **_SAFE_HELPERS,
    }
