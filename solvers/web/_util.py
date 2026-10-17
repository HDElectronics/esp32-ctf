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

FLAG_RE = re.compile(r"ESP\{[0-9A-F]{12}\}")
PROMPT = b"ctf> "


def args(description: str, default_via: str = "console") -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--host", default="192.168.4.1", help="board address (default %(default)s)")
    p.add_argument("--serial", default=os.environ.get("CTF_PORT", "/dev/ttyACM0"),
                   help="board serial console (default %(default)s)")
    p.add_argument("--via", choices=["console", "web", "none"], default=default_via,
                   help="where to submit the flag (default %(default)s)")
    return p.parse_args()


def url(a, path: str) -> str:
    return f"http://{a.host}{path}"


# ---------------- serial console ----------------

def _open(port: str) -> serial.Serial:
    """Open the console without toggling the auto-reset lines (no reboot)."""
    s = serial.Serial()
    s.port = port
    s.baudrate = 115200
    s.timeout = 0.05
    s.dtr = False
    s.rts = False
    s.open()
    return s


def _read_until(s, marker: bytes, timeout: float) -> bytes:
    buf = b""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
            if marker in buf:
                break
    return buf


def console(port: str, line: str, timeout: float = 5.0) -> str:
    """Run one console command and return its output (log lines included)."""
    s = _open(port)
    try:
        s.reset_input_buffer()
        s.write(b"\x03")  # drop any half-typed line
        s.flush()
        _read_until(s, PROMPT, 1.0)
        s.reset_input_buffer()
        s.write(line.encode() + b"\r")
        s.flush()
        out = _read_until(s, PROMPT, timeout).decode(errors="replace").replace("\r", "")
    finally:
        s.close()
    if out.startswith(line):
        out = out[len(line):]
    if out.endswith(PROMPT.decode()):
        out = out[: -len(PROMPT)]
    return out.strip("\n")


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
    out = console(port, "submit " + flag)
    for line in out.splitlines():
        if line.startswith(("Correct!", "Already solved", "Wrong flag")):
            return line
    return out


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
