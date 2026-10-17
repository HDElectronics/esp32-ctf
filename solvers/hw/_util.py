"""Shared helpers for the HW solvers: serial console + flag submission.

Needs pyserial (`pip install pyserial`, or use the ESP-IDF python env).
"""
import re
import sys
import time

FLAG_RE = re.compile(r"ESP\{[0-9A-Fa-f]{12}\}")
DEFAULT_PORT = "/dev/ttyACM0"


class Console:
    """Line-oriented access to the board's `ctf> ` console."""

    def __init__(self, port=DEFAULT_PORT, baud=115200, reset=False):
        import serial  # imported here so offline decoders run without pyserial

        self.ser = serial.Serial()
        self.ser.port = port
        self.ser.baudrate = baud
        self.ser.timeout = 0.1
        # Keep EN/IO0 released on boards with the usual DTR/RTS auto-reset.
        self.ser.dtr = False
        self.ser.rts = False
        self.ser.open()
        if reset:
            self.reset()
        else:
            self.sync()

    def sync(self):
        """Wait for a usable prompt. Opening the port can reboot some boards
        (DTR/RTS glitch), so if a boot log shows up wait for it to finish."""
        seen = self.read_until(r"rst:|ets ", timeout=0.7)
        if re.search(r"rst:|ets ", seen):
            self.read_until(r"ctf> ", timeout=15)
            time.sleep(1.0)
        self.ser.reset_input_buffer()
        self.ser.write(b"\r\n")
        self.read_until(r"ctf> ", timeout=2)
        time.sleep(0.2)
        self.ser.reset_input_buffer()

    def reset(self):
        """Pulse EN via RTS (board reboots, boot log follows)."""
        self.ser.rts = True
        time.sleep(0.1)
        self.ser.rts = False

    def read_until(self, pattern, timeout=5.0):
        """Read until regex `pattern` matches the accumulated text; returns it."""
        rx = re.compile(pattern) if isinstance(pattern, str) else pattern
        buf = ""
        end = time.time() + timeout
        while time.time() < end:
            data = self.ser.read(256)
            if data:
                buf += data.decode("utf-8", "replace")
                if rx.search(buf):
                    return buf
        return buf

    def cmd(self, line, wait=r"ctf> ", timeout=5.0):
        """Send a console command and return its output up to the next prompt."""
        self.ser.reset_input_buffer()
        self.ser.write((line + "\r\n").encode())
        out = self.read_until(wait, timeout)
        # Drop the echoed command line and the trailing prompt.
        out = out.replace("\r", "")
        if out.startswith(line):
            out = out[len(line):]
        return out.rsplit("ctf> ", 1)[0].strip("\n")

    def submit(self, flag):
        out = self.cmd("submit " + flag)
        print(out)
        return ("Correct!" in out) or ("Already solved" in out)

    def close(self):
        self.ser.close()


def submit_and_exit(flag, port=DEFAULT_PORT):
    print("flag:", flag)
    con = Console(port)
    ok = con.submit(flag)
    con.close()
    sys.exit(0 if ok else 1)


def wrap_flag(text):
    """Return ESP{...} from a decoded string (wrapped form or bare 12-hex body)."""
    m = FLAG_RE.search(text)
    if m:
        return m.group(0)
    m = re.search(r"[0-9A-Fa-f]{12}", text)
    return "ESP{%s}" % m.group(0).upper() if m else None


# ---------------------------------------------------------------- captures

def load_logic_csv(path):
    """Parse a sigrok/PulseView CSV export of logic channels.

    Accepts `sigrok-cli -O csv` (comment lines start with ';', header like
    `Time [s],D0,D1` or `D0,D1`) and PulseView's "Export as CSV".
    Returns (names, rows) where rows are lists of ints per channel, one row per
    sample (the time column, if present, is dropped).
    """
    names, rows, time_col = None, [], None
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith(";"):
                continue
            cells = [c.strip() for c in line.split(",")]
            if names is None:
                if all(re.fullmatch(r"[01]", c) for c in cells):
                    names = ["D%d" % i for i in range(len(cells))]
                else:
                    names = cells
                    time_col = next((i for i, c in enumerate(cells) if c.lower().startswith("time")), None)
                    if time_col is not None:
                        names = [c for i, c in enumerate(cells) if i != time_col]
                    continue
            vals = [c for i, c in enumerate(cells) if i != time_col]
            rows.append([int(float(v)) for v in vals])
    return names, rows


def channel_index(names, wanted):
    """Index of channel `wanted` (name like D3 or a plain number)."""
    if wanted in names:
        return names.index(wanted)
    if wanted.isdigit():
        for cand in ("D" + wanted, wanted):
            if cand in names:
                return names.index(cand)
        return int(wanted)
    raise SystemExit("channel %s not in %s" % (wanted, names))


def bytes_from_annotations(text, keyword):
    """Hex bytes from sigrok-cli annotation output lines containing `keyword`.

    e.g. `i2c-1: Data write: 45` or `spi-1: 45` lines.
    """
    out = []
    for line in text.splitlines():
        if keyword.lower() not in line.lower():
            continue
        m = re.search(r"([0-9A-Fa-f]{2})\s*$", line.strip())
        if m:
            out.append(int(m.group(1), 16))
    return bytes(out)
