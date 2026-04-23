"""Write guard / _write_ / _inplacevar_ attack cases (~40).

full_write_guard wraps attribute/item assignment on non-dict/list objects.
_apply_inplace_operator replaces in-place operators (bypasses __iadd__ etc.).
"""
from ._framework import AttackCase

CASES: list[AttackCase] = [
    # --- Safe dict and list mutations (allowed) ---
    AttackCase(
        id="write_dict_setitem",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    d = {}\n'
            '    d["key"] = "value"\n'
            '    return d\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("key") == "value",
        notes="dict[key] = value — allowed by full_write_guard",
    ),
    AttackCase(
        id="write_list_setitem",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    lst = [0, 0, 0]\n'
            '    lst[0] = 10\n'
            '    lst[1] = 20\n'
            '    return {"lst": lst}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("lst") == [10, 20, 0],
        notes="list[i] = value — allowed",
    ),
    AttackCase(
        id="write_list_append",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    lst = []\n'
            '    lst.append(1)\n'
            '    lst.append(2)\n'
            '    return {"lst": lst}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("lst") == [1, 2],
        notes="list.append — allowed (method call)",
    ),
    AttackCase(
        id="write_dict_update",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    d = {"a": 1}\n'
            '    d.update({"b": 2})\n'
            '    return d\n'
        ),
        expected="contained",
        output_predicate=lambda out: out == {"a": 1, "b": 2},
        notes="dict.update — allowed (method call)",
    ),

    # --- Attribute assignment on user-defined classes ---
    AttackCase(
        id="write_attr_on_custom_class",
        category="write_guard",
        code=(
            'class Foo:\n'
            '    pass\n'
            'def run(state):\n'
            '    f = Foo()\n'
            '    f.x = 42\n'
            '    return {"x": f.x}\n'
        ),
        expected="blocked",
        notes="f.x = value on user class — full_write_guard blocks non-dict/list attribute writes",
    ),
    AttackCase(
        id="write_attr_on_builtin_object",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    s = "hello"\n'
            '    s.custom = 42\n'
            '    return {"x": s.custom}\n'
        ),
        expected="blocked",
        notes="str.custom_attr = value — blocked by write guard",
    ),
    AttackCase(
        id="write_attr_on_int",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    n = 42\n'
            '    n.extra = "evil"\n'
            '    return {"x": n.extra}\n'
        ),
        expected="blocked",
        notes="int.attr = value — blocked by write guard",
    ),
    AttackCase(
        id="write_attr_on_list_subclass",
        category="write_guard",
        code=(
            'class MyList(list):\n'
            '    pass\n'
            'def run(state):\n'
            '    ml = MyList([1, 2, 3])\n'
            '    ml.extra = "value"\n'
            '    return {"extra": ml.extra}\n'
        ),
        expected="blocked",
        notes="list subclass attr write — full_write_guard only allows exact dict/list type",
    ),
    AttackCase(
        id="write_attr_on_dict_subclass",
        category="write_guard",
        code=(
            'class MyDict(dict):\n'
            '    pass\n'
            'def run(state):\n'
            '    md = MyDict({"a": 1})\n'
            '    md.extra = "value"\n'
            '    return {"extra": md.extra}\n'
        ),
        expected="blocked",
        notes="dict subclass attr write — blocked (not exact dict type)",
    ),

    # --- delattr ---
    AttackCase(
        id="write_delattr_custom",
        category="write_guard",
        code=(
            'class Foo:\n'
            '    x = 1\n'
            'def run(state):\n'
            '    delattr(Foo, "x")\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="delattr() not in restricted builtins — NameError",
    ),
    AttackCase(
        id="write_del_attr_syntax",
        category="write_guard",
        code=(
            'class Foo:\n'
            '    x = 1\n'
            'def run(state):\n'
            '    f = Foo()\n'
            '    del f.x\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="del f.x — write guard blocks attribute deletion on non-dict/list",
    ),
    AttackCase(
        id="write_del_dict_key_valid",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    d = {"a": 1, "b": 2}\n'
            '    del d["a"]\n'
            '    return d\n'
        ),
        expected="contained",
        output_predicate=lambda out: "a" not in out and out.get("b") == 2,
        notes="del d[key] on dict — allowed",
    ),
    AttackCase(
        id="write_del_list_item",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    lst = [1, 2, 3]\n'
            '    del lst[0]\n'
            '    return {"lst": lst}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("lst") == [2, 3],
        notes="del lst[i] — allowed",
    ),

    # --- setattr() ---
    AttackCase(
        id="write_setattr_builtin",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    setattr(int, "evil", lambda: None)\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="setattr on builtin type — guarded_setattr wraps via full_write_guard",
    ),
    AttackCase(
        id="write_setattr_custom_instance",
        category="write_guard",
        code=(
            'class Foo: pass\n'
            'def run(state):\n'
            '    f = Foo()\n'
            '    setattr(f, "x", 42)\n'
            '    return {"x": f.x}\n'
        ),
        expected="blocked",
        notes="setattr on custom instance — guarded_setattr uses full_write_guard",
    ),

    # --- In-place operators (_apply_inplace_operator behavior) ---
    AttackCase(
        id="write_inplace_int_plus_equals",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    x = 10\n'
            '    x += 5\n'
            '    return {"x": x}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 15,
        notes="+= on int — uses operator.add via _apply_inplace_operator",
    ),
    AttackCase(
        id="write_inplace_str_plus_equals",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    s = "hello"\n'
            '    s += " world"\n'
            '    return {"s": s}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("s") == "hello world",
        notes="+= on str — uses operator.add",
    ),
    AttackCase(
        id="write_inplace_list_plus_equals",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    lst = [1, 2]\n'
            '    lst += [3, 4]\n'
            '    return {"lst": lst}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("lst") == [1, 2, 3, 4],
        notes="+= on list — operator.add (creates new list, not list.extend!)",
    ),
    AttackCase(
        id="write_inplace_iadd_bypass_attempt",
        category="write_guard",
        code=(
            'class Evil:\n'
            '    def __iadd__(self, other):\n'
            '        import os  # would escape if iadd ran\n'
            '        return self\n'
            'def run(state):\n'
            '    e = Evil()\n'
            '    e += 1\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="__iadd__ with import attempt — _apply_inplace_operator uses operator.add not __iadd__",
    ),
    AttackCase(
        id="write_inplace_imul",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    x = 5\n'
            '    x *= 3\n'
            '    return {"x": x}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 15,
        notes="*= on int — operator.mul",
    ),
    AttackCase(
        id="write_inplace_idiv",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    x = 10.0\n'
            '    x /= 4\n'
            '    return {"x": x}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 2.5,
        notes="/= on float",
    ),
    AttackCase(
        id="write_inplace_imod",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    x = 17\n'
            '    x %= 5\n'
            '    return {"x": x}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 2,
        notes="%= on int",
    ),
    AttackCase(
        id="write_inplace_ipow",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    x = 2\n'
            '    x **= 10\n'
            '    return {"x": x}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 1024,
        notes="**= on int",
    ),
    AttackCase(
        id="write_inplace_ior",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    x = 0b1010\n'
            '    x |= 0b0101\n'
            '    return {"x": x}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 0b1111,
        notes="|= on int",
    ),
    AttackCase(
        id="write_inplace_iand",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    x = 0b1100\n'
            '    x &= 0b1010\n'
            '    return {"x": x}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 0b1000,
        notes="&= on int",
    ),
    AttackCase(
        id="write_inplace_ixor",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    x = 0b1010\n'
            '    x ^= 0b1100\n'
            '    return {"x": x}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 0b0110,
        notes="^= on int",
    ),
    AttackCase(
        id="write_inplace_ilshift",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    x = 1\n'
            '    x <<= 4\n'
            '    return {"x": x}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 16,
        notes="<<= on int",
    ),
    AttackCase(
        id="write_inplace_irshift",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    x = 256\n'
            '    x >>= 4\n'
            '    return {"x": x}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 16,
        notes=">>= on int",
    ),
    AttackCase(
        id="write_inplace_ifloordiv",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    x = 10\n'
            '    x //= 3\n'
            '    return {"x": x}\n'
        ),
        expected="contained",
        output_predicate=lambda out: out.get("x") == 3,
        notes="//= on int",
    ),
    AttackCase(
        id="write_inplace_unsupported_operator",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    x = 10\n'
            '    _inplacevar_("@=", x, 2)\n'
            '    return {"x": x}\n'
        ),
        expected="blocked",
        notes="_inplacevar_ called with unsupported @ operator — NameError (not in builtins) or TypeError",
    ),

    # --- Writing to module globals (attempt) ---
    AttackCase(
        id="write_module_attr_json",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    json.evil_attr = "evil"\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="Assigning attribute on module object — write guard blocks it",
    ),
    AttackCase(
        id="write_module_attr_math",
        category="write_guard",
        code=(
            'def run(state):\n'
            '    math.pi = 3\n'
            '    return {"pi": math.pi}\n'
        ),
        expected="blocked",
        notes="Overwriting math.pi — write guard blocks module attribute assignment",
    ),
    AttackCase(
        id="write_class_attr_via_instance",
        category="write_guard",
        code=(
            'class Config:\n'
            '    debug = False\n'
            'def run(state):\n'
            '    c = Config()\n'
            '    c.debug = True\n'
            '    return {"debug": Config.debug}\n'
        ),
        expected="blocked",
        notes="Instance attribute write on user class — write guard blocks",
    ),
]
