#!/usr/bin/env python
"""Background launcher for the social-auto-upload dev stack.

Run with pythonw.exe so no console window ever appears:

    pythonw.exe scripts\\launcher.pyw            start both (default)
    pythonw.exe scripts\\launcher.pyw stop       stop both
    pythonw.exe scripts\\launcher.pyw status     show what is running

Backend  : Flask  sau_backend.py   -> http://localhost:5409   log: logs\\backend.log
Frontend : Vite   sau_frontend     -> http://localhost:5173   log: logs\\frontend.log

If a port is already serving, that service is skipped instead of being
started twice. Uses only the standard library; no extra dependencies.
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
ROOT = SCRIPTS_DIR.parent
LOGS = ROOT / "logs"
BACKEND_PORT = 5409
FRONTEND_PORT = 5173
CREATE_NO_WINDOW = 0x08000000
MAX_LOG_BYTES = 5 * 1024 * 1024


def say(message):
    """Write to logs\\launcher.log and, if a console exists, to stdout."""
    line = "[%s] %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), message)
    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        with open(LOGS / "launcher.log", "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    if sys.stdout is not None:
        try:
            print(line)
        except OSError:
            pass


def port_is_open(port):
    try:
        infos = socket.getaddrinfo("localhost", port, proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        return False
    for family, socktype, proto, _, addr in infos:
        sock = socket.socket(family, socktype, proto)
        try:
            sock.settimeout(0.4)
            if sock.connect_ex(addr) == 0:
                return True
        except OSError:
            continue
        finally:
            sock.close()
    return False


def rotate(path):
    try:
        if path.exists() and path.stat().st_size > MAX_LOG_BYTES:
            path.replace(path.with_name(path.name + ".1"))
    except OSError:
        pass


def load_config():
    config = {"node": "", "python": ""}
    try:
        # utf-8-sig tolerates a BOM written by PowerShell on older versions
        stored = json.loads((SCRIPTS_DIR / "paths.json").read_text(encoding="utf-8-sig"))
        config.update(stored)
    except (OSError, ValueError):
        pass
    return config


def python_exe(config):
    candidates = [config.get("python", ""), str(ROOT / ".venv" / "Scripts" / "python.exe")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    exe = Path(sys.executable)
    if exe.name.lower() == "pythonw.exe":
        sibling = exe.with_name("python.exe")
        if sibling.is_file():
            return sibling
    return exe


def node_exe(config):
    candidates = [
        config.get("node", ""),
        shutil.which("node") or "",
        r"C:\Program Files\nodejs\node.exe",
        str(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "nodejs" / "node.exe"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def spawn(command, cwd, log_path, env=None):
    rotate(log_path)
    with open(log_path, "a", encoding="utf-8", errors="replace") as out:
        out.write("\n[%s] start: %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), " ".join(command)))
        out.flush()
        subprocess.Popen(
            command,
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            stdout=out,
            stderr=subprocess.STDOUT,
            env=env,
            close_fds=True,
            creationflags=CREATE_NO_WINDOW,
        )


def start_backend(config):
    if port_is_open(BACKEND_PORT):
        say("backend: port %d already in use, skipped" % BACKEND_PORT)
        return True
    spawn(
        [str(python_exe(config)), "-u", "sau_backend.py"],
        ROOT,
        LOGS / "backend.log",
    )
    say("backend: started on http://localhost:%d" % BACKEND_PORT)
    return True


def start_frontend(config):
    if port_is_open(FRONTEND_PORT):
        say("frontend: port %d already in use, skipped" % FRONTEND_PORT)
        return True

    node = node_exe(config)
    if node is None:
        say("frontend: node.exe not found, reinstall Node.js or rerun install-autostart")
        return False

    vite_bin = ROOT / "sau_frontend" / "node_modules" / "vite" / "bin" / "vite.js"
    if not vite_bin.is_file():
        say("frontend: %s missing, run 'npm install' in sau_frontend" % vite_bin)
        return False

    env = os.environ.copy()
    env["BROWSER"] = "none"  # do not pop a browser at logon
    env["PATH"] = str(node.parent) + os.pathsep + env.get("PATH", "")
    spawn(
        [str(node), str(vite_bin), "--host", "0.0.0.0", "--port", str(FRONTEND_PORT)],
        ROOT / "sau_frontend",
        LOGS / "frontend.log",
        env=env,
    )
    say("frontend: started on http://localhost:%d" % FRONTEND_PORT)
    return True


def listening_pids(port):
    pids = set()
    try:
        result = subprocess.run(
            ["netstat", "-ano", "-p", "TCP"],
            capture_output=True,
            text=True,
            errors="ignore",
            creationflags=CREATE_NO_WINDOW,
        )
    except OSError:
        return pids
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[3] == "LISTENING" and parts[1].endswith(":%d" % port):
            if parts[4].isdigit():
                pids.add(int(parts[4]))
    return pids


def stop_all():
    for port, label in ((FRONTEND_PORT, "frontend"), (BACKEND_PORT, "backend")):
        pids = listening_pids(port)
        if not pids:
            say("%s: nothing listening on %d" % (label, port))
            continue
        for pid in sorted(pids):
            subprocess.run(
                ["taskkill", "/F", "/PID", str(pid)],
                capture_output=True,
                creationflags=CREATE_NO_WINDOW,
            )
            say("%s: killed pid %d on port %d" % (label, pid, port))


def show_status():
    for port, label in ((BACKEND_PORT, "backend"), (FRONTEND_PORT, "frontend")):
        state = "UP  " if port_is_open(port) else "down"
        say("%s %s :%d" % (state, label, port))


def main():
    action = (sys.argv[1] if len(sys.argv) > 1 else "start").lower()

    if action == "stop":
        stop_all()
    elif action == "status":
        show_status()
    elif action == "start":
        config = load_config()
        start_backend(config)
        start_frontend(config)
    else:
        say("unknown action %r (expected start, stop or status)" % action)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
