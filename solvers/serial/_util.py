"""Shared helpers for the serial/crypto solvers: thin wrappers over
solvers/common/console.py (opens the console without rebooting the board).

Needs pyserial (the ESP-IDF python env has it, or `pip install pyserial`).
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.console import PROMPT, Console, default_port  # noqa: E402

FLAG_RE = re.compile(r"ESP\{[0-9A-F]{12}\}")


def open_console(port=None, baud=115200):
    """Open the console without toggling the auto-reset lines (no reboot)."""
    return Console(port, baud)


def read_until(s, marker, timeout=5.0):
    """Read until `marker` (bytes) appears or timeout; returns all bytes read."""
    return s.read_until(marker, timeout)


def sync(s):
    """Get a fresh prompt and drop anything pending."""
    s.sync()


def cmd(s, line, timeout=5.0):
    """Run one console command; returns its output (echo and prompt removed)."""
    return s.cmd(line, timeout, sync=False)


def reset_and_capture(s, seconds=4.0):
    """Reboot the board on purpose and return the boot log as text."""
    return s.reset_board(timeout=seconds + 6.0)


def submit(s, flag):
    """Submit a flag; exit 0 on "Correct!"/"Already solved", 1 otherwise."""
    res = s.submit(flag)
    print(res)
    return 0 if res.startswith(("Correct!", "Already solved")) else 1


def port_arg(default=None):
    """Port from `--port X`, else first positional argument, else $CTF_PORT / default."""
    if "--port" in sys.argv or any(a.startswith("--port=") for a in sys.argv):
        return default_port()
    pos = [a for a in sys.argv[1:] if not a.startswith("-")]
    return pos[0] if pos else (default or default_port())
