"""Shared helpers for the serial/crypto solvers: talk to the board console.

Needs pyserial (the ESP-IDF python env has it, or `pip install pyserial`).
"""
import re
import sys
import time

import serial

PROMPT = b"ctf> "
FLAG_RE = re.compile(r"ESP\{[0-9A-F]{12}\}")


def open_console(port="/dev/ttyACM0", baud=115200):
    """Open the console without toggling the auto-reset lines (no reboot)."""
    s = serial.Serial()
    s.port = port
    s.baudrate = baud
    s.timeout = 0.05
    s.dtr = False
    s.rts = False
    s.open()
    return s


def read_until(s, marker, timeout=5.0):
    """Read until `marker` (bytes) appears or timeout; returns all bytes read."""
    buf = b""
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        chunk = s.read(4096)
        if chunk:
            buf += chunk
            if marker in buf:
                break
    return buf


def sync(s):
    """Get a fresh prompt and drop anything pending."""
    s.reset_input_buffer()
    s.write(b"\x03")  # Ctrl-C: drop any half-typed line
    s.flush()
    read_until(s, PROMPT, 1.0)
    s.reset_input_buffer()


def cmd(s, line, timeout=5.0):
    """Run one console command; returns its output (echo and prompt removed)."""
    s.write(line.encode() + b"\r")
    s.flush()
    out = read_until(s, PROMPT, timeout)
    text = out.decode(errors="replace").replace("\r", "")
    # strip echoed command line and trailing prompt
    if text.startswith(line):
        text = text[len(line):]
    if text.endswith(PROMPT.decode()):
        text = text[: -len(PROMPT)]
    return text.strip("\n")


def reset_and_capture(s, seconds=4.0):
    """Pulse EN via RTS (board reboots) and return the boot log as text."""
    s.reset_input_buffer()
    s.rts = True
    time.sleep(0.1)
    s.rts = False
    out = read_until(s, PROMPT, seconds + 6.0)
    # let the prompt settle
    out += read_until(s, b"\x00", 0.3)
    return out.decode(errors="replace").replace("\r", "")


def submit(s, flag):
    """Submit a flag; exit 0 on "Correct!"/"Already solved", 1 otherwise."""
    out = cmd(s, "submit " + flag)
    print(out)
    if "Correct!" in out or "Already solved" in out:
        return 0
    return 1


def port_arg(default="/dev/ttyACM0"):
    return sys.argv[1] if len(sys.argv) > 1 else default
