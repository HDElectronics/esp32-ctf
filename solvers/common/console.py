"""Board serial console shared by every solver track.

    from common.console import Console, default_port
    with Console() as c:          # opens WITHOUT rebooting the board
        print(c.cmd("help"))
        print(c.submit(flag))     # -> "Correct! ..." / "Already solved ..." / "Wrong flag ..."
        log = c.reset_board()     # explicit reboot, returns the boot log

Port: `--port PORT` on the command line, else $CTF_PORT, else /dev/ttyACM0.

Why the open sequence matters: the DevKit auto-reset circuit pulls EN low while
RTS is asserted and DTR is not (and IO0 low for the opposite). Linux asserts
both lines on open; clearing them one at a time (dtr=False, then rts=False)
passes through the EN-low state and reboots the board. Leaving both asserted
keeps EN and IO0 high, and the driver drops both together on close.
"""
import os
import re
import sys
import time

PROMPT = b"ctf> "
DEFAULT_PORT = "/dev/ttyACM0"
RESULT_RE = re.compile(r"(Correct!.*|Already solved.*|Wrong flag.*)")


def default_port() -> str:
    """`--port X` / `--port=X` from sys.argv, else $CTF_PORT, else /dev/ttyACM0."""
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--port" and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith("--port="):
            return a.split("=", 1)[1]
    return os.environ.get("CTF_PORT", DEFAULT_PORT)


def add_port_arg(parser) -> None:
    parser.add_argument("--port", default=default_port(),
                        help="board serial console (default: $CTF_PORT or %s)" % DEFAULT_PORT)


class Console:
    """The board's `ctf> ` console. Unknown attributes (write, read, flush,
    reset_input_buffer, ...) are forwarded to the underlying serial.Serial."""

    def __init__(self, port: str = None, baud: int = 115200, timeout: float = 0.05):
        import serial  # imported here so offline decoders run without pyserial

        self.port = port or default_port()
        s = serial.Serial()
        s.port = self.port
        s.baudrate = baud
        s.timeout = timeout
        s.dtr = True  # both asserted: EN and IO0 stay high (no reset)
        s.rts = True
        s.open()
        self.ser = s

    def __getattr__(self, name):
        return getattr(self.__dict__["ser"], name)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self) -> None:
        self.ser.close()

    # ---- reading -----------------------------------------------------------

    def read_until(self, marker: bytes = PROMPT, timeout: float = 5.0) -> bytes:
        """Read until `marker` (bytes) appears or timeout; returns all bytes read."""
        buf = b""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            chunk = self.ser.read(4096)
            if chunk:
                buf += chunk
                if marker in buf:
                    break
        return buf

    def read_until_re(self, pattern, timeout: float = 5.0) -> str:
        """Read until regex `pattern` matches the decoded text; returns the text."""
        rx = re.compile(pattern) if isinstance(pattern, str) else pattern
        buf = ""
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            chunk = self.ser.read(4096)
            if chunk:
                buf += chunk.decode(errors="replace")
                if rx.search(buf):
                    break
        return buf

    def drain(self, quiet: float = 0.3) -> str:
        """Read until the line has been silent for `quiet` seconds."""
        buf = b""
        last = time.monotonic()
        while time.monotonic() - last < quiet:
            chunk = self.ser.read(4096)
            if chunk:
                buf += chunk
                last = time.monotonic()
        return buf.decode(errors="replace")

    # ---- commands ----------------------------------------------------------

    def sync(self) -> None:
        """Get a fresh prompt and drop anything pending."""
        self.ser.reset_input_buffer()
        self.ser.write(b"\x03")  # Ctrl-C: drop any half-typed line
        self.ser.flush()
        self.read_until(PROMPT, 1.0)
        self.ser.reset_input_buffer()

    def send(self, line: str) -> None:
        self.ser.write(line.encode() + b"\r")
        self.ser.flush()

    def cmd(self, line: str, timeout: float = 5.0, sync: bool = True) -> str:
        """Run one console command; returns its output (echo and prompt removed)."""
        if sync:
            self.sync()
        self.send(line)
        text = self.read_until(PROMPT, timeout).decode(errors="replace").replace("\r", "")
        if text.startswith(line):
            text = text[len(line):]
        if text.endswith(PROMPT.decode()):
            text = text[: -len(PROMPT)]
        return text.strip("\n")

    def submit(self, flag: str) -> str:
        """Submit a flag; returns the result line (or the raw output if none)."""
        out = ""
        for _ in range(2):  # a log line can garble the echo: try once more
            out = self.cmd("submit " + flag)
            m = RESULT_RE.search(out)
            if m:
                return m.group(1).strip()
        return out

    # ---- reboot ------------------------------------------------------------

    def reset_board(self, wait_prompt: bool = True, timeout: float = 15.0) -> str:
        """Reboot the board on purpose (pulse EN) and return the boot log.

        Drops DTR alone (RTS still asserted -> EN low), then re-asserts it, so
        IO0 is never pulled low (normal boot, not download mode)."""
        self.ser.reset_input_buffer()
        self.ser.dtr = False
        time.sleep(0.1)
        self.ser.dtr = True
        if not wait_prompt:
            return ""
        out = self.read_until(PROMPT, timeout).decode(errors="replace")
        out += self.drain(0.5)
        return out.replace("\r", "")
