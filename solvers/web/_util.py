"""Shared helpers for the web reference solvers (see README.md).

Every solver takes:
  --host   board address (default 192.168.4.1, the board's SoftAP)
  --serial serial console of the board (default $CTF_PORT or /dev/ttyACM0)
  --via    where to submit the recovered flag: console, web (/submit form), none
"""
import argparse
import base64
import os
import re
import sys
import time

import requests
import serial

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.console import Console, default_port  # noqa: E402

FLAG_RE = re.compile(r"ESP\{[0-9A-F]{12}\}")


def args(description: str, default_via: str = "console") -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--host", default="192.168.4.1", help="board address (default %(default)s)")
    p.add_argument("--serial", "--port", dest="serial", default=default_port(),
                   help="board serial console (default %(default)s)")
    p.add_argument("--via", choices=["console", "web", "none"], default=default_via,
                   help="where to submit the flag (default %(default)s)")
    return p.parse_args()


def url(a, path: str) -> str:
    return f"http://{a.host}{path}"


# ---------------- serial console ----------------

_conn = {}


def _open(port: str) -> Console:
    """One console connection per process (solvers/common/console.py: no reset)."""
    if port not in _conn or not _conn[port].is_open:
        _conn[port] = Console(port)
    return _conn[port]


def console(port: str, line: str, timeout: float = 5.0) -> str:
    """Run one console command and return its output (log lines included)."""
    s = _open(port)
    try:
        return s.cmd(line, timeout)
    except serial.SerialException:
        s.close()
        raise


def wifi_info(port: str) -> dict:
    """Parse the `wifi` console clue: SSID (base32-decoded), password, knock ports."""
    for _ in range(3):  # retry if the board was mid-boot (output interleaved with the boot log)
        out = console(port, "wifi")
        if "ssid (base32)" in out:
            break
        time.sleep(3)
    info = {"raw": out}
    m = re.search(r"ssid \(base32\): ([A-Z2-7=]+)", out)
    if m:
        info["ssid"] = base64.b32decode(m.group(1)).decode()
    m = re.search(r"password:\s+(\S+)", out)
    if m:
        info["password"] = m.group(1)
    m = re.search(r"knock, knock, knock: ([0-9a-f]+) \. ([0-9a-f]+) \. ([0-9a-f]+).*door ([0-9a-f]+)", out)
    if m:
        info["knock"] = [int(m.group(i), 16) for i in (1, 2, 3)]
        info["door"] = int(m.group(4), 16)
    m = re.search(r"\(dev\) active AP ssid: (\S+), sta ip: (\S+)", out)
    if m:
        info["dev_ssid"], info["dev_ip"] = m.group(1), m.group(2)
    return info


# ---------------- submission ----------------

def submit_console(port: str, flag: str) -> str:
    return _open(port).submit(flag)


def submit_web(a, flag: str) -> str:
    r = requests.post(url(a, "/submit"), data={"flag": flag}, timeout=10)
    m = re.search(r'<p class="result">([^<]*)</p>', r.text)
    return m.group(1) if m else f"HTTP {r.status_code}: no result"


def finish(cid: str, flag, a) -> None:
    if not FLAG_RE.fullmatch(flag or ""):
        sys.exit(f"{cid}: FAILED, got {flag!r}")
    print(f"{cid} flag: {flag}")
    if a.via == "none":
        return
    res = submit_console(a.serial, flag) if a.via == "console" else submit_web(a, flag)
    print(f"submit via {a.via}: {res}")
    if not (res.startswith("Correct!") or res.startswith("Already solved")):
        sys.exit(f"{cid}: submission rejected")
