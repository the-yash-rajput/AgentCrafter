"""Helper-module attribute walk cases (~150).

The sandbox exposes live module objects: Counter, Decimal, date, datetime,
json, math, random, re, statistics, string, time, timedelta, uuid4.

safer_getattr blocks names starting with '_' and INSPECT_ATTRIBUTES.
All _-prefixed attribute access should be blocked.
Non-_ attributes that are modules or classes may be accessible but shouldn't
provide a path to dangerous capabilities.
"""
from ._framework import AttackCase

# Underscore-prefix attributes that all modules have but safer_getattr blocks
_COMMON_DUNDER_ATTRS = [
    "__loader__", "__spec__", "__package__", "__builtins__", "__dict__",
    "__doc__", "__name__", "__file__", "__cached__", "__path__",
    "__module__", "__qualname__",
]

# Helper globals exposed in the sandbox
_HELPER_NAMES = [
    "json", "math", "re", "random", "statistics", "string",
    "Counter", "Decimal", "datetime", "date", "time", "timedelta", "uuid4",
]


def _make_cases() -> list[AttackCase]:
    cases: list[AttackCase] = []

    # --- Dunder attribute access on every exposed helper ---
    for helper in _HELPER_NAMES:
        for attr in _COMMON_DUNDER_ATTRS:
            cases.append(AttackCase(
                id=f"helper_{helper}_{attr.strip('_')}_access",
                category="helper_module_walks",
                code=(
                    f"def run(state):\n"
                    f"    val = {helper}.{attr}\n"
                    f"    return {{'val': str(val)}}\n"
                ),
                expected="blocked",
                notes=f"{helper}.{attr} — starts with _ — blocked by safer_getattr",
            ))

    # --- json module specific ---
    cases += [
        AttackCase(
            id="helper_json_decoder_submodule",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    dec = json.decoder\n'
                '    return {"x": str(dec)}\n'
            ),
            expected="contained",
            output_predicate=lambda out: "json" in out.get("x", "").lower() or "module" in out.get("x", "").lower(),
            notes="json.decoder submodule — accessible but can't escape; type() not in builtins so use str()",
        ),
        AttackCase(
            id="helper_json_decoder_class_globals",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    dec = json.decoder\n'
                '    cls = dec.JSONDecoder\n'
                '    return {"x": str(cls)}\n'
            ),
            expected="contained",
            output_predicate=lambda out: isinstance(out.get("x"), str),
            notes="json.decoder.JSONDecoder class access — contained",
        ),
        AttackCase(
            id="helper_json_decoder_globals_via_method",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    dec = json.decoder\n'
                '    g = dec.JSONDecoder.__init__.__globals__\n'
                '    return {"x": str(g)}\n'
            ),
            expected="blocked",
            notes="JSONDecoder.__init__.__globals__ — __globals__ starts with _",
        ),
        AttackCase(
            id="helper_json_encoder_submodule",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    enc = json.encoder\n'
                '    return {"x": str(enc)}\n'
            ),
            expected="contained",
            output_predicate=lambda out: "json" in out.get("x", "").lower() or "module" in out.get("x", "").lower(),
            notes="json.encoder submodule — accessible, no escape; type() not in builtins so use str()",
        ),
        AttackCase(
            id="helper_json_encoder_os_via_builtins",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    enc = json.encoder\n'
                '    bi = enc.__builtins__\n'
                '    return {"x": str(bi)}\n'
            ),
            expected="blocked",
            notes="json.encoder.__builtins__ — starts with _",
        ),
        AttackCase(
            id="helper_json_dumps_globals",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    g = json.dumps.__globals__\n'
                '    return {"x": str(g)[:50]}\n'
            ),
            expected="blocked",
            notes="json.dumps.__globals__ — starts with _ — blocked",
        ),
        AttackCase(
            id="helper_json_loads_os_via_globals",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    g = json.loads.__globals__\n'
                '    os_mod = g["os"]\n'
                '    return {"cwd": os_mod.getcwd()}\n'
            ),
            expected="blocked",
            notes="json.loads.__globals__['os'] — __globals__ starts with _",
        ),
    ]

    # --- math module specific ---
    cases += [
        AttackCase(
            id="helper_math_sqrt_globals",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    g = math.sqrt.__globals__\n'
                '    return {"x": str(g)}\n'
            ),
            expected="blocked",
            notes="math.sqrt.__globals__ — starts with _",
        ),
        AttackCase(
            id="helper_math_inf_usage",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    return {"inf": math.inf, "nan": math.nan, "pi": math.pi}\n'
            ),
            expected="contained",
            output_predicate=lambda out: out.get("pi") is not None,
            notes="math.inf/nan/pi are safe float attributes",
        ),
        AttackCase(
            id="helper_math_e_attr",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    return {"e": math.e, "tau": math.tau}\n'
            ),
            expected="contained",
            output_predicate=lambda out: "e" in out,
            notes="math.e and math.tau are safe constants",
        ),
        AttackCase(
            id="helper_math_gcd_code_attr",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    co = math.gcd.__code__\n'
                '    return {"x": str(co)}\n'
            ),
            expected="blocked",
            notes="math.gcd.__code__ — starts with _",
        ),
    ]

    # --- re module specific ---
    cases += [
        AttackCase(
            id="helper_re_compile_safe",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    p = re.compile(r"\\d+")\n'
                '    return {"pattern": p.pattern, "flags": p.flags}\n'
            ),
            expected="contained",
            output_predicate=lambda out: out.get("pattern") == r"\d+",
            notes="re.compile is safe — Pattern.pattern and .flags are non-_ attrs",
        ),
        AttackCase(
            id="helper_re_pattern_scanner",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    p = re.compile(r"x")\n'
                '    s = p.scanner\n'
                '    return {"x": str(s)}\n'
            ),
            expected="contained",
            output_predicate=lambda out: isinstance(out.get("x"), str),
            xfail=True,
            notes="PARTIAL BYPASS: Pattern.scanner has no _ prefix — safer_getattr allows it; method is accessible but harmless",
        ),
        AttackCase(
            id="helper_re_compile_class_mro",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    p = re.compile(r"x")\n'
                '    mro = p.__class__.__mro__\n'
                '    return {"x": str(mro)}\n'
            ),
            expected="blocked",
            notes="Pattern.__class__.__mro__ — __class__ starts with _",
        ),
        AttackCase(
            id="helper_re_match_groupdict",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    m = re.match(r"(?P<name>\\w+)", "hello")\n'
                '    return {"groups": m.groupdict()}\n'
            ),
            expected="contained",
            output_predicate=lambda out: out.get("groups", {}).get("name") == "hello",
            notes="re.match().groupdict() is safe",
        ),
        AttackCase(
            id="helper_re_fullmatch_globals",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    g = re.fullmatch.__globals__\n'
                '    return {"x": str(g)[:20]}\n'
            ),
            expected="blocked",
            notes="re.fullmatch.__globals__ — starts with _",
        ),
    ]

    # --- random module specific ---
    cases += [
        AttackCase(
            id="helper_random_inst_access",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    inst = random._inst\n'
                '    return {"x": str(inst)}\n'
            ),
            expected="blocked",
            notes="random._inst — starts with _ — blocked by safer_getattr",
        ),
        AttackCase(
            id="helper_random_Random_class",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    cls = random.Random\n'
                '    return {"x": str(cls)}\n'
            ),
            expected="contained",
            output_predicate=lambda out: "Random" in out.get("x", ""),
            notes="random.Random class accessible — no escape from it",
        ),
        AttackCase(
            id="helper_random_Random_mro",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    cls = random.Random\n'
                '    mro = cls.__mro__\n'
                '    return {"x": str(mro)}\n'
            ),
            expected="blocked",
            notes="random.Random.__mro__ — starts with _",
        ),
        AttackCase(
            id="helper_random_Random_subclasses",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    cls = random.Random\n'
                '    subs = cls.__subclasses__()\n'
                '    return {"subs": str(subs)}\n'
            ),
            expected="blocked",
            notes="random.Random.__subclasses__ — starts with _",
        ),
        AttackCase(
            id="helper_random_seed_safe",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    random.seed(42)\n'
                '    val = random.randint(0, 100)\n'
                '    return {"val": val}\n'
            ),
            expected="contained",
            output_predicate=lambda out: isinstance(out.get("val"), int),
            notes="random.seed and random.randint — safe usage",
        ),
        AttackCase(
            id="helper_random_betavariate_globals",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    g = random.betavariate.__globals__\n'
                '    return {"x": str(g)[:20]}\n'
            ),
            expected="blocked",
            notes="random.betavariate.__globals__ — starts with _",
        ),
    ]

    # --- statistics module ---
    cases += [
        AttackCase(
            id="helper_statistics_NormalDist_class",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    nd = statistics.NormalDist\n'
                '    return {"x": str(nd)}\n'
            ),
            expected="contained",
            output_predicate=lambda out: "NormalDist" in out.get("x", ""),
            notes="statistics.NormalDist accessible but harmless",
        ),
        AttackCase(
            id="helper_statistics_NormalDist_mro",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    mro = statistics.NormalDist.__mro__\n'
                '    return {"x": str(mro)}\n'
            ),
            expected="blocked",
            notes="statistics.NormalDist.__mro__ — starts with _",
        ),
        AttackCase(
            id="helper_statistics_mean_safe",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    return {"mean": statistics.mean([1, 2, 3, 4, 5])}\n'
            ),
            expected="contained",
            output_predicate=lambda out: out.get("mean") == 3.0,
            notes="statistics.mean safe usage",
        ),
        AttackCase(
            id="helper_statistics_mean_globals",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    g = statistics.mean.__globals__\n'
                '    return {"x": str(g)[:20]}\n'
            ),
            expected="blocked",
            notes="statistics.mean.__globals__ — starts with _",
        ),
    ]

    # --- string module ---
    cases += [
        AttackCase(
            id="helper_string_Formatter_safe",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    sf = string.Formatter()\n'
                '    result = sf.format("Hello {name}!", name="World")\n'
                '    return {"result": result}\n'
            ),
            expected="blocked",
            notes="string.Formatter removed — string is now a constants-only SimpleNamespace",
        ),
        AttackCase(
            id="helper_string_Formatter_dunder_bypass_attempt",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    sf = string.Formatter()\n'
                '    result = sf.format("{0.__class__}", "")\n'
                '    return {"result": str(result)}\n'
            ),
            expected="blocked",
            notes="string.Formatter removed — class-info leak via Formatter.format is closed",
        ),
        AttackCase(
            id="helper_string_Formatter_mro_via_format",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    sf = string.Formatter()\n'
                '    result = sf.format("{0.__class__.__mro__}", "")\n'
                '    return {"result": str(result)}\n'
            ),
            expected="blocked",
            notes="string.Formatter removed — chained dunder leak via Formatter.format is closed",
        ),
        AttackCase(
            id="helper_string_Template_safe",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    t = string.Template("Hello $name!")\n'
                '    return {"result": t.substitute(name="World")}\n'
            ),
            expected="blocked",
            notes="string.Template removed — string is now a constants-only SimpleNamespace",
        ),
        AttackCase(
            id="helper_string_Template_pattern_attr",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    t = string.Template("$x")\n'
                '    return {"pattern": str(t.pattern)}\n'
            ),
            expected="blocked",
            notes="string.Template removed — string is now a constants-only SimpleNamespace",
        ),
        AttackCase(
            id="helper_string_ascii_letters",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    return {"letters": string.ascii_letters}\n'
            ),
            expected="contained",
            output_predicate=lambda out: out.get("letters") is not None,
            notes="string.ascii_letters is safe",
        ),
        AttackCase(
            id="helper_string_Formatter_globals",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    sf = string.Formatter()\n'
                '    g = sf.format.__globals__\n'
                '    return {"x": str(g)[:20]}\n'
            ),
            expected="blocked",
            notes="sf.format.__globals__ — starts with _",
        ),
    ]

    # --- datetime module objects ---
    cases += [
        AttackCase(
            id="helper_datetime_now_safe",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    now = datetime.now()\n'
                '    return {"year": now.year, "month": now.month}\n'
            ),
            expected="contained",
            output_predicate=lambda out: isinstance(out.get("year"), int),
            notes="datetime.now() is safe",
        ),
        AttackCase(
            id="helper_datetime_now_class_mro",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    now = datetime.now()\n'
                '    mro = now.__class__.__mro__\n'
                '    return {"x": str(mro)}\n'
            ),
            expected="blocked",
            notes="datetime()..__class__.__mro__ — __class__ starts with _",
        ),
        AttackCase(
            id="helper_datetime_fromtimestamp_chain",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    dt = datetime.fromtimestamp(0)\n'
                '    subs = dt.__class__.__subclasses__()\n'
                '    return {"x": str(subs)}\n'
            ),
            expected="blocked",
            notes="datetime.__subclasses__ walk — __class__ starts with _",
        ),
        AttackCase(
            id="helper_date_today_safe",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    today = date.today()\n'
                '    return {"day": today.day, "isoformat": today.isoformat()}\n'
            ),
            expected="blocked",
            notes="date.today() raises ImportError('__import__') in restricted context — use date(y, m, d) instead",
        ),
        AttackCase(
            id="helper_timedelta_total_seconds",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    td = timedelta(hours=1)\n'
                '    return {"seconds": td.total_seconds()}\n'
            ),
            expected="contained",
            output_predicate=lambda out: out.get("seconds") == 3600.0,
            notes="timedelta.total_seconds() is safe",
        ),
        AttackCase(
            id="helper_datetime_strptime_globals",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    g = datetime.strptime.__globals__\n'
                '    return {"x": str(g)[:20]}\n'
            ),
            expected="blocked",
            notes="datetime.strptime.__globals__ — starts with _",
        ),
    ]

    # --- uuid4 ---
    cases += [
        AttackCase(
            id="helper_uuid4_call_safe",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    uid = uuid4()\n'
                '    return {"uuid": str(uid)}\n'
            ),
            expected="contained",
            output_predicate=lambda out: len(out.get("uuid", "")) == 36,
            notes="uuid4() is safe",
        ),
        AttackCase(
            id="helper_uuid4_globals_attr",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    g = uuid4.__globals__\n'
                '    return {"x": str(g)[:20]}\n'
            ),
            expected="blocked",
            notes="uuid4.__globals__ — starts with _",
        ),
        AttackCase(
            id="helper_uuid4_os_via_globals",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    g = uuid4.__globals__\n'
                '    os_mod = g.get("os")\n'
                '    if os_mod:\n'
                '        return {"cwd": os_mod.getcwd()}\n'
                '    return {"os_found": False}\n'
            ),
            expected="blocked",
            notes="uuid4.__globals__['os'] — __globals__ blocked",
        ),
        AttackCase(
            id="helper_uuid4_module_attr",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    mod = uuid4.__module__\n'
                '    return {"x": str(mod)}\n'
            ),
            expected="blocked",
            notes="uuid4.__module__ — starts with _",
        ),
    ]

    # --- Counter (dict subclass) ---
    cases += [
        AttackCase(
            id="helper_Counter_safe_usage",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    c = Counter("hello world")\n'
                '    return {"most_common": c.most_common(3)}\n'
            ),
            expected="contained",
            output_predicate=lambda out: isinstance(out.get("most_common"), list),
            notes="Counter.most_common is safe",
        ),
        AttackCase(
            id="helper_Counter_class_mro",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    mro = Counter.__mro__\n'
                '    return {"x": str(mro)}\n'
            ),
            expected="blocked",
            notes="Counter.__mro__ — starts with _",
        ),
        AttackCase(
            id="helper_Counter_subclasses",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    subs = Counter.__subclasses__()\n'
                '    return {"subs": str(subs)}\n'
            ),
            expected="blocked",
            notes="Counter.__subclasses__ — starts with _",
        ),
    ]

    # --- Decimal ---
    cases += [
        AttackCase(
            id="helper_Decimal_safe_usage",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    d = Decimal("3.14159")\n'
                '    return {"val": str(d), "as_float": float(d)}\n'
            ),
            expected="contained",
            output_predicate=lambda out: out.get("val") == "3.14159",
            notes="Decimal safe usage",
        ),
        AttackCase(
            id="helper_Decimal_class_mro",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    mro = Decimal.__mro__\n'
                '    return {"x": str(mro)}\n'
            ),
            expected="blocked",
            notes="Decimal.__mro__ — starts with _",
        ),
        AttackCase(
            id="helper_Decimal_globals",
            category="helper_module_walks",
            code=(
                'def run(state):\n'
                '    g = Decimal.__init__.__globals__\n'
                '    return {"x": str(g)[:20]}\n'
            ),
            expected="blocked",
            notes="Decimal.__init__.__globals__ — __init__ starts with _",
        ),
    ]

    return cases


CASES: list[AttackCase] = _make_cases()
