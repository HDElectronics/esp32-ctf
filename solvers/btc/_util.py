"""Shared helpers for the BT Classic reference solvers (see README.md).

Needs a Python built with Bluetooth sockets (socket.AF_BLUETOOTH; distro Python
on Linux has it, conda / some pyenv builds do not), dbus-fast and pyserial.

Environment:
  CTF_PORT      serial console of the board (default /dev/ttyACM0)
  CTF_BTC_ADDR  board BR/EDR address, skips the inquiry for BTC-01/02
"""
import asyncio
import os
import re
import socket
import subprocess
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.console import Console, default_port  # noqa: E402

PORT = default_port()
NAME_PREFIX = "ESP32-CTF-"
SPP_NAME = "CTF Console"
PROMPT = b"spp> "
FLAG_RE = re.compile(r"ESP\{[0-9A-F]{12}\}")
FALLBACK_CHANNELS = (1, 2, 3, 4, 5)


# ---- discovery (BlueZ D-Bus) --------------------------------------------

async def _inquiry(timeout: float, forget: bool):
    """BR/EDR-only discovery; returns (address, Device1 properties) of the board."""
    from dbus_fast import BusType, Variant
    from dbus_fast.aio import MessageBus

    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    root = bus.get_proxy_object("org.bluez", "/", await bus.introspect("org.bluez", "/"))
    om = root.get_interface("org.freedesktop.DBus.ObjectManager")

    def boards(objs):
        for path, ifaces in objs.items():
            d = ifaces.get("org.bluez.Device1")
            if d and str(d.get("Name", Variant("s", "")).value).startswith(NAME_PREFIX):
                yield path, d

    objs = await om.call_get_managed_objects()
    adapter_path = next(p for p, i in objs.items() if "org.bluez.Adapter1" in i)
    ad_obj = bus.get_proxy_object("org.bluez", adapter_path,
                                  await bus.introspect("org.bluez", adapter_path))
    adapter = ad_obj.get_interface("org.bluez.Adapter1")
    if forget:  # drop cached (possibly LE-sourced) properties and old bonds
        for path, _ in list(boards(objs)):
            try:
                await adapter.call_remove_device(path)
            except Exception:
                pass
    await adapter.call_set_discovery_filter({"Transport": Variant("s", "bredr")})
    await adapter.call_start_discovery()
    try:
        end = time.time() + timeout
        while time.time() < end:
            await asyncio.sleep(1.0)
            for path, d in boards(await om.call_get_managed_objects()):
                if "Class" in d:  # only BR/EDR inquiry results carry a Class
                    props = {k: v.value for k, v in d.items()}
                    return props["Address"], props
    finally:
        try:
            await adapter.call_stop_discovery()
        except Exception:
            pass
        bus.disconnect()
    sys.exit("board not found: is it in radio mode (`mode radio`) and powered?")


def inquiry(timeout: float = 30.0, forget: bool = True):
    return asyncio.run(_inquiry(timeout, forget))


def board_address() -> str:
    addr = os.environ.get("CTF_BTC_ADDR")
    if addr:
        return addr
    addr, props = inquiry()
    print(f"found {props.get('Name')} [{addr}] class 0x{props.get('Class', 0):06x}")
    return addr


def forget(addr: str) -> None:
    """Remove the device (and its bond) from BlueZ so the next run pairs afresh."""
    subprocess.run(["bluetoothctl", "remove", addr], capture_output=True, text=True,
                   timeout=10)


# ---- SDP + RFCOMM --------------------------------------------------------

def sdp_channel(addr: str):
    """RFCOMM channel of the "CTF Console" record via sdptool, or None."""
    try:
        out = subprocess.run(["sdptool", "browse", addr], capture_output=True, text=True,
                             timeout=30).stdout
    except (OSError, subprocess.TimeoutExpired):
        return None
    for rec in out.split("\n\n"):
        if SPP_NAME in rec:
            m = re.search(r"Channel:\s*(\d+)", rec)
            if m:
                return int(m.group(1))
    return None


class Spp:
    def __init__(self, sock: socket.socket, banner: str):
        self.sock = sock
        self.banner = banner

    def read_prompt(self, timeout: float = 5.0) -> str:
        buf = b""
        end = time.time() + timeout
        while time.time() < end and not buf.endswith(PROMPT):
            self.sock.settimeout(max(0.1, end - time.time()))
            try:
                d = self.sock.recv(1024)
            except socket.timeout:
                break
            if not d:
                break
            buf += d
        return buf.decode(errors="replace")

    def cmd(self, line: str) -> str:
        """Send a line, return the reply without the echo and the trailing prompt."""
        self.sock.send(line.encode() + b"\r\n")
        out = self.read_prompt().replace("\r", "")
        if out.startswith(line + "\n"):
            out = out[len(line) + 1:]
        if out.endswith(PROMPT.decode()):
            out = out[: -len(PROMPT)]
        return out

    def close(self):
        try:
            self.sock.send(b"exit\r\n")
            time.sleep(0.3)
        except OSError:
            pass
        self.sock.close()


def _try(addr: str, ch: int):
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    s.settimeout(25)
    s.connect((addr, ch))  # kernel + BlueZ pair on demand (SSP Just Works)
    spp = Spp(s, "")
    spp.banner = spp.read_prompt(8.0)
    if not spp.banner.endswith(PROMPT.decode()):
        s.close()
        raise OSError(f"channel {ch}: no {PROMPT!r} prompt")
    return spp


def open_console(addr: str) -> Spp:
    if not hasattr(socket, "AF_BLUETOOTH"):
        sys.exit("this Python has no Bluetooth sockets; use the distro python3")
    ch = sdp_channel(addr)
    chans = [ch] if ch else list(FALLBACK_CHANNELS)
    print(f"SDP: {'channel %d' % ch if ch else 'no answer, trying channels 1..5'}")
    last = None
    for c in chans:
        for attempt in range(2):
            try:
                spp = _try(addr, c)
                print(f"RFCOMM channel {c}: connected")
                return spp
            except OSError as e:
                last = e
                time.sleep(1.0)
    sys.exit(f"could not open the SPP console: {last}")


# ---- serial console submit ----------------------------------------------

def console_submit(flag: str) -> str:
    with Console(PORT) as s:
        return s.submit(flag)


def finish(challenge: str, flag: str) -> None:
    if not FLAG_RE.fullmatch(flag or ""):
        sys.exit(f"{challenge}: FAILED, got {flag!r}")
    print(f"{challenge} flag: {flag}")
    res = console_submit(flag)
    print(f"submit via console: {res}")
    if not (res.startswith("Correct!") or res.startswith("Already solved")):
        sys.exit(f"{challenge}: submission rejected")
