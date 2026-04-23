"""File I/O attack cases (~40).

open(), io.open, pathlib, os.open — none exposed in restricted builtins.
All should raise NameError / blocked by import restriction.
"""
from ._framework import AttackCase

CASES: list[AttackCase] = [
    # --- open() not in builtins ---
    AttackCase(
        id="file_open_read_passwd",
        category="file_io",
        code=(
            'def run(state):\n'
            '    f = open("/etc/passwd", "r")\n'
            '    return {"data": f.read()}\n'
        ),
        expected="blocked",
        notes="open() not in restricted builtins",
    ),
    AttackCase(
        id="file_open_write_tmp",
        category="file_io",
        code=(
            'def run(state):\n'
            '    with open("/tmp/pwned.txt", "w") as f:\n'
            '        f.write("pwned")\n'
            '    return {"x": "wrote file"}\n'
        ),
        expected="blocked",
        notes="open() not in restricted builtins",
    ),
    AttackCase(
        id="file_open_read_env",
        category="file_io",
        code=(
            'def run(state):\n'
            '    with open("/proc/self/environ", "r") as f:\n'
            '        return {"env": f.read()}\n'
        ),
        expected="blocked",
        notes="open() not in builtins; also /proc/self/environ sensitive",
    ),
    AttackCase(
        id="file_open_append",
        category="file_io",
        code=(
            'def run(state):\n'
            '    with open("/tmp/evil.log", "a") as f:\n'
            '        f.write("evil")\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="open() not in restricted builtins",
    ),
    AttackCase(
        id="file_open_binary",
        category="file_io",
        code=(
            'def run(state):\n'
            '    data = open("/etc/shadow", "rb").read()\n'
            '    return {"data": str(data)}\n'
        ),
        expected="blocked",
        notes="open() not in restricted builtins; also /etc/shadow sensitive",
    ),

    # --- io module ---
    AttackCase(
        id="file_io_open",
        category="file_io",
        code=(
            'import io\n'
            'def run(state):\n'
            '    f = io.open("/etc/passwd", "r")\n'
            '    return {"data": f.read()}\n'
        ),
        expected="blocked",
        notes="import io blocked",
    ),
    AttackCase(
        id="file_io_FileIO",
        category="file_io",
        code=(
            'import io\n'
            'def run(state):\n'
            '    f = io.FileIO("/etc/passwd")\n'
            '    return {"data": str(f.read())}\n'
        ),
        expected="blocked",
        notes="import io blocked",
    ),
    AttackCase(
        id="file_io_BytesIO_content_write",
        category="file_io",
        code=(
            'import io\n'
            'def run(state):\n'
            '    buf = io.BytesIO()\n'
            '    buf.write(b"hello")\n'
            '    return {"data": buf.getvalue().decode()}\n'
        ),
        expected="blocked",
        notes="import io blocked",
    ),
    AttackCase(
        id="file_io_StringIO_exec",
        category="file_io",
        code=(
            'import io\n'
            'def run(state):\n'
            '    buf = io.StringIO("import os")\n'
            '    exec(buf.read())\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import io blocked; exec also blocked",
    ),

    # --- pathlib ---
    AttackCase(
        id="file_pathlib_read_text",
        category="file_io",
        code=(
            'import pathlib\n'
            'def run(state):\n'
            '    return {"data": pathlib.Path("/etc/passwd").read_text()}\n'
        ),
        expected="blocked",
        notes="import pathlib blocked",
    ),
    AttackCase(
        id="file_pathlib_write_text",
        category="file_io",
        code=(
            'import pathlib\n'
            'def run(state):\n'
            '    pathlib.Path("/tmp/evil.txt").write_text("evil")\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import pathlib blocked",
    ),
    AttackCase(
        id="file_pathlib_iterdir",
        category="file_io",
        code=(
            'import pathlib\n'
            'def run(state):\n'
            '    dirs = list(pathlib.Path("/").iterdir())\n'
            '    return {"dirs": [str(d) for d in dirs]}\n'
        ),
        expected="blocked",
        notes="import pathlib blocked",
    ),
    AttackCase(
        id="file_pathlib_glob",
        category="file_io",
        code=(
            'import pathlib\n'
            'def run(state):\n'
            '    files = list(pathlib.Path("/etc").glob("*.conf"))\n'
            '    return {"files": [str(f) for f in files]}\n'
        ),
        expected="blocked",
        notes="import pathlib blocked",
    ),

    # --- os.open / os.read ---
    AttackCase(
        id="file_os_open",
        category="file_io",
        code=(
            'import os\n'
            'def run(state):\n'
            '    fd = os.open("/etc/passwd", os.O_RDONLY)\n'
            '    data = os.read(fd, 100)\n'
            '    os.close(fd)\n'
            '    return {"data": data.decode()}\n'
        ),
        expected="blocked",
        notes="import os blocked",
    ),

    # --- shutil ---
    AttackCase(
        id="file_shutil_copy",
        category="file_io",
        code=(
            'import shutil\n'
            'def run(state):\n'
            '    shutil.copy("/etc/passwd", "/tmp/passwd_copy")\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import shutil blocked",
    ),
    AttackCase(
        id="file_shutil_rmtree",
        category="file_io",
        code=(
            'import shutil\n'
            'def run(state):\n'
            '    shutil.rmtree("/tmp/test_dir", ignore_errors=True)\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import shutil blocked",
    ),

    # --- tempfile ---
    AttackCase(
        id="file_tempfile_mkstemp",
        category="file_io",
        code=(
            'import tempfile\n'
            'def run(state):\n'
            '    fd, path = tempfile.mkstemp()\n'
            '    return {"path": path}\n'
        ),
        expected="blocked",
        notes="import tempfile blocked",
    ),
    AttackCase(
        id="file_tempfile_mkdtemp",
        category="file_io",
        code=(
            'import tempfile\n'
            'def run(state):\n'
            '    path = tempfile.mkdtemp()\n'
            '    return {"path": path}\n'
        ),
        expected="blocked",
        notes="import tempfile blocked",
    ),

    # --- Attribute walk attempts to reach file operations ---
    AttackCase(
        id="file_json_loader_open",
        category="file_io",
        code=(
            'def run(state):\n'
            '    loader = json.__loader__\n'
            '    return {"x": str(loader)}\n'
        ),
        expected="blocked",
        notes="json.__loader__ — __loader__ starts with _ — blocked",
    ),
    AttackCase(
        id="file_re_loader_exec_path",
        category="file_io",
        code=(
            'def run(state):\n'
            '    loader = re.__loader__\n'
            '    src = loader.get_source("re")\n'
            '    return {"x": str(src[:50])}\n'
        ),
        expected="blocked",
        notes="re.__loader__ — __loader__ starts with _ — blocked",
    ),
    AttackCase(
        id="file_math_file_attr",
        category="file_io",
        code=(
            'def run(state):\n'
            '    filepath = math.__file__\n'
            '    return {"path": filepath}\n'
        ),
        expected="blocked",
        notes="math.__file__ — __file__ starts with _ — blocked by safer_getattr",
    ),
    AttackCase(
        id="file_json_file_attr",
        category="file_io",
        code=(
            'def run(state):\n'
            '    filepath = json.__file__\n'
            '    return {"path": filepath}\n'
        ),
        expected="blocked",
        notes="json.__file__ starts with _ — blocked",
    ),
    AttackCase(
        id="file_statistics_spec_submodule_load",
        category="file_io",
        code=(
            'def run(state):\n'
            '    spec = statistics.__spec__\n'
            '    return {"x": str(spec)}\n'
        ),
        expected="blocked",
        notes="statistics.__spec__ — __spec__ starts with _ — blocked",
    ),

    # --- stdin/stdout/stderr via sys ---
    AttackCase(
        id="file_sys_stdin_read",
        category="file_io",
        code=(
            'import sys\n'
            'def run(state):\n'
            '    return {"data": sys.stdin.read(10)}\n'
        ),
        expected="blocked",
        notes="import sys blocked",
    ),
    AttackCase(
        id="file_sys_stdout_write",
        category="file_io",
        code=(
            'import sys\n'
            'def run(state):\n'
            '    sys.stdout.write("evil")\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import sys blocked",
    ),

    # --- /dev/urandom access ---
    AttackCase(
        id="file_dev_urandom_open",
        category="file_io",
        code=(
            'def run(state):\n'
            '    f = open("/dev/urandom", "rb")\n'
            '    return {"bytes": str(f.read(8))}\n'
        ),
        expected="blocked",
        notes="open() not in restricted builtins",
    ),

    # --- File descriptor via socket (indirect) ---
    AttackCase(
        id="file_socket_fileno",
        category="file_io",
        code=(
            'import socket\n'
            'def run(state):\n'
            '    s = socket.socket()\n'
            '    fd = s.fileno()\n'
            '    data = open(f"/proc/self/fd/{fd}", "rb").read()\n'
            '    return {"data": str(data)}\n'
        ),
        expected="blocked",
        notes="import socket blocked; open also blocked",
    ),

    # --- Reach file ops via json helper ---
    AttackCase(
        id="file_json_load_from_fileobj",
        category="file_io",
        code=(
            'def run(state):\n'
            '    f = open("/etc/passwd")\n'
            '    return {"data": json.load(f)}\n'
        ),
        expected="blocked",
        notes="open() not in builtins — NameError before json.load is called",
    ),

    # --- glob via os ---
    AttackCase(
        id="file_glob_module",
        category="file_io",
        code=(
            'import glob\n'
            'def run(state):\n'
            '    return {"files": glob.glob("/etc/*.conf")}\n'
        ),
        expected="blocked",
        notes="import glob blocked",
    ),

    # --- fnmatch via os ---
    AttackCase(
        id="file_fnmatch_module",
        category="file_io",
        code=(
            'import fnmatch\n'
            'def run(state):\n'
            '    return {"matches": fnmatch.filter(["a.conf", "b.txt"], "*.conf")}\n'
        ),
        expected="blocked",
        notes="import fnmatch blocked",
    ),

    # --- zipimport ---
    AttackCase(
        id="file_zipimport",
        category="file_io",
        code=(
            'import zipimport\n'
            'def run(state):\n'
            '    zi = zipimport.zipimporter("/tmp/evil.zip")\n'
            '    return {"x": str(zi)}\n'
        ),
        expected="blocked",
        notes="import zipimport blocked",
    ),

    # --- dbm (file-based key-value store) ---
    AttackCase(
        id="file_dbm_open",
        category="file_io",
        code=(
            'import dbm\n'
            'def run(state):\n'
            '    db = dbm.open("/tmp/test_db", "c")\n'
            '    db["key"] = "value"\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import dbm blocked",
    ),
    AttackCase(
        id="file_sqlite3_connect",
        category="file_io",
        code=(
            'import sqlite3\n'
            'def run(state):\n'
            '    conn = sqlite3.connect("/tmp/evil.db")\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import sqlite3 blocked",
    ),

    # --- csv read ---
    AttackCase(
        id="file_csv_read",
        category="file_io",
        code=(
            'import csv\n'
            'def run(state):\n'
            '    with open("/etc/passwd") as f:\n'
            '        reader = csv.reader(f, delimiter=":")\n'
            '        return {"rows": list(reader)}\n'
        ),
        expected="blocked",
        notes="import csv blocked; open also blocked",
    ),
]
