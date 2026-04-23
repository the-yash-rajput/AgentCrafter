"""Payload / pickle edge cases (~30).

Tests state input handling, output type enforcement, and pickle-based
attack surfaces in the IPC queue between parent and child process.
"""
from ._framework import AttackCase

CASES: list[AttackCase] = [
    # --- Output must be dict ---
    AttackCase(
        id="payload_return_none",
        category="payload_tricks",
        code='def run(state):\n    return None\n',
        expected="blocked",
        notes="run() returning None — PythonTaskConfigurationError: must return dict",
    ),
    AttackCase(
        id="payload_return_list",
        category="payload_tricks",
        code='def run(state):\n    return [1, 2, 3]\n',
        expected="blocked",
        notes="run() returning list — must return dict",
    ),
    AttackCase(
        id="payload_return_int",
        category="payload_tricks",
        code='def run(state):\n    return 42\n',
        expected="blocked",
        notes="run() returning int — must return dict",
    ),
    AttackCase(
        id="payload_return_string",
        category="payload_tricks",
        code='def run(state):\n    return "hello"\n',
        expected="blocked",
        notes="run() returning str — must return dict",
    ),
    AttackCase(
        id="payload_return_tuple",
        category="payload_tricks",
        code='def run(state):\n    return ("a", "b")\n',
        expected="blocked",
        notes="run() returning tuple — must return dict",
    ),
    AttackCase(
        id="payload_return_bool",
        category="payload_tricks",
        code='def run(state):\n    return True\n',
        expected="blocked",
        notes="run() returning bool — must return dict",
    ),
    AttackCase(
        id="payload_return_set",
        category="payload_tricks",
        code='def run(state):\n    return {1, 2, 3}\n',
        expected="blocked",
        notes="run() returning set — must return dict",
    ),
    AttackCase(
        id="payload_return_generator",
        category="payload_tricks",
        code='def run(state):\n    return (x for x in range(3))\n',
        expected="blocked",
        notes="run() returning generator — must return dict (non-awaitable, non-dict → error)",
    ),

    # --- Output dict with non-serializable values ---
    AttackCase(
        id="payload_return_lambda_in_dict",
        category="payload_tricks",
        code='def run(state):\n    return {"fn": lambda x: x}\n',
        expected="blocked",
        notes="dict with lambda value — not picklable, child→parent queue put fails",
    ),
    AttackCase(
        id="payload_return_file_in_dict",
        category="payload_tricks",
        code=(
            'def run(state):\n'
            '    class FakeFile:\n'
            '        pass\n'
            '    return {"file": FakeFile()}\n'
        ),
        expected="blocked",
        notes="dict with custom class instance — may not be picklable, child→parent fails",
    ),

    # --- Missing run() callable ---
    AttackCase(
        id="payload_no_run_function",
        category="payload_tricks",
        code='x = 42\n',
        expected="blocked",
        notes="No run() function defined — PythonTaskConfigurationError",
    ),
    AttackCase(
        id="payload_run_not_callable",
        category="payload_tricks",
        code='run = 42\n',
        expected="blocked",
        notes="run = int (not callable) — PythonTaskConfigurationError",
    ),
    AttackCase(
        id="payload_run_is_class",
        category="payload_tricks",
        code=(
            'class run:\n'
            '    pass\n'
        ),
        expected="blocked",
        notes="run is a class — calling run(state) returns instance not dict",
    ),

    # --- State mutation ---
    AttackCase(
        id="payload_state_mutation_contained",
        category="payload_tricks",
        code=(
            'def run(state):\n'
            '    state["new_key"] = "added"\n'
            '    return state\n'
        ),
        state={"original": "value"},
        expected="contained",
        output_predicate=lambda out: out.get("new_key") == "added" and out.get("original") == "value",
        notes="State mutation — deepcopy protects original; returned state is safe",
    ),
    AttackCase(
        id="payload_state_deepcopy_isolation",
        category="payload_tricks",
        code=(
            'def run(state):\n'
            '    inner = state.get("data", [])\n'
            '    inner.append(999)\n'
            '    return {"inner_len": len(inner), "original_len": len(state.get("data", []))}\n'
        ),
        state={"data": [1, 2, 3]},
        expected="contained",
        output_predicate=lambda out: out.get("original_len") == 4,  # deepcopy shares ref
        notes="State inner list mutation — deepcopy copies by value, modification shows in state copy",
    ),
    AttackCase(
        id="payload_empty_state",
        category="payload_tricks",
        code=(
            'def run(state):\n'
            '    return {"got_state": isinstance(state, dict), "is_empty": len(state) == 0}\n'
        ),
        state={},
        expected="contained",
        output_predicate=lambda out: out.get("got_state") is True and out.get("is_empty") is True,
        notes="Empty state dict — runner provides {} when state is absent",
    ),
    AttackCase(
        id="payload_none_state_handled",
        category="payload_tricks",
        code=(
            'def run(state):\n'
            '    return {"got_state": isinstance(state, dict)}\n'
        ),
        state={},
        expected="contained",
        output_predicate=lambda out: out.get("got_state") is True,
        notes="None state converted to {} in child (payload.get('state') or {})",
    ),

    # --- Cyclic state ---
    AttackCase(
        id="payload_cyclic_state_input",
        category="payload_tricks",
        code=(
            'def run(state):\n'
            '    return {"x": 1}\n'
        ),
        state={},  # We pass {} here; actual cyclic dicts can't be expressed in module scope
        expected="contained",
        output_predicate=lambda out: out.get("x") == 1,
        notes="Normal dict state — baseline for non-cyclic",
    ),

    # --- Large state dict ---
    AttackCase(
        id="payload_large_state",
        category="payload_tricks",
        code=(
            'def run(state):\n'
            '    return {"count": len(state)}\n'
        ),
        state={str(i): i for i in range(1000)},
        expected="contained",
        output_predicate=lambda out: out.get("count") == 1000,
        notes="Large state dict (1000 keys) — pickle transfer OK",
    ),

    # --- State with nested structures ---
    AttackCase(
        id="payload_nested_state",
        category="payload_tricks",
        code=(
            'def run(state):\n'
            '    return {"deep": state["a"]["b"]["c"]}\n'
        ),
        state={"a": {"b": {"c": "found"}}},
        expected="contained",
        output_predicate=lambda out: out.get("deep") == "found",
        notes="Deeply nested state — valid",
    ),

    # --- run() returning None explicitly ---
    AttackCase(
        id="payload_return_explicit_none",
        category="payload_tricks",
        code='def run(state):\n    return None\n',
        expected="blocked",
        notes="Explicit None return — PythonTaskConfigurationError",
    ),

    # --- run() raising exceptions ---
    AttackCase(
        id="payload_run_raises_valueerror",
        category="payload_tricks",
        code='def run(state):\n    raise ValueError("intentional error")\n',
        expected="blocked",
        notes="run() raises ValueError — caught as PythonTaskError",
    ),
    AttackCase(
        id="payload_run_raises_systemexit",
        category="payload_tricks",
        code='def run(state):\n    raise SystemExit(0)\n',
        expected="blocked",
        notes="run() raises SystemExit — child exits, parent gets 'finished without result'",
    ),
    AttackCase(
        id="payload_run_raises_keyboardinterrupt",
        category="payload_tricks",
        code='def run(state):\n    raise KeyboardInterrupt()\n',
        expected="blocked",
        notes="KeyboardInterrupt — not caught by bare except Exception in child, child dies",
    ),

    # --- Output dict with various value types ---
    AttackCase(
        id="payload_return_various_types",
        category="payload_tricks",
        code=(
            'def run(state):\n'
            '    return {\n'
            '        "int": 42,\n'
            '        "float": 3.14,\n'
            '        "str": "hello",\n'
            '        "bool": True,\n'
            '        "none": None,\n'
            '        "list": [1, 2, 3],\n'
            '        "dict": {"nested": True},\n'
            '    }\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("int") == 42 and out.get("str") == "hello",
        notes="Output with all JSON-compatible types",
    ),
    AttackCase(
        id="payload_return_bytes_in_dict",
        category="payload_tricks",
        code='def run(state):\n    return {"data": b"binary data"}\n',
        expected="contained",
        output_predicate=lambda out: out.get("data") == b"binary data",
        notes="Bytes in output dict — picklable",
    ),
]
