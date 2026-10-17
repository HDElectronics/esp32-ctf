"""Shared helpers for the BLE reference solvers (see README.md).

Environment:
  CTF_PORT      serial console of the board (default /dev/ttyACM0; or --port)
  CTF_BLE_NAME  exact advertised name to pick (default: first "ESP32-CTF-*")
"""
import argparse
import asyncio
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from common.console import Console, add_port_arg, default_port  # noqa: E402
from bleak import BleakClient, BleakScanner

PORT = default_port()
NAME = os.environ.get("CTF_BLE_NAME")
NAME_PREFIX = "ESP32-CTF-"
COMPANY_ID = 0x02E5
FLAG_RE = re.compile(r"ESP\{[0-9A-F]{12}\}")
UDESC_UUID = "00002901-0000-1000-8000-00805f9b34fb"


def uuid(short: int) -> str:
    """Board UUID e532XXXX-c7f0-4e5b-9a1d-3c54460b1e00."""
    return f"e532{short:04x}-c7f0-4e5b-9a1d-3c54460b1e00"


SVC_CHALLENGE = uuid(0x0100)
SVC_CONTROL = uuid(0x0200)
CH_SUBMIT = uuid(0x0201)
CH_RESULT = uuid(0x0202)
CH_SCORE = uuid(0x0203)


def args(description: str, default_via: str = "console") -> argparse.Namespace:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--via", choices=["console", "ble", "none"], default=default_via,
                   help="where to submit the recovered flag (default %(default)s)")
    add_port_arg(p)
    return p.parse_known_args()[0]


def bluez_remove(address: str) -> None:
    """Forget the device in BlueZ (bond + GATT cache); ignore 'not available'."""
    subprocess.run(["bluetoothctl", "remove", address], capture_output=True, text=True,
                   timeout=10)


def _is_board(dev, adv) -> bool:
    name = adv.local_name or dev.name or ""
    return name == NAME if NAME else name.startswith(NAME_PREFIX)


async def find_board(timeout: float = 20.0):
    dev = await BleakScanner.find_device_by_filter(_is_board, timeout=timeout)
    if dev is None:
        sys.exit("board not found: is it in radio mode and advertising?")
    return dev


async def connect(fresh: bool = True) -> BleakClient:
    """Scan for the board and connect. fresh=True first drops BlueZ's cached copy
    of the device so a reflashed GATT layout is rediscovered."""
    dev = await find_board()
    if fresh:
        bluez_remove(dev.address)
        dev = await find_board()
    client = BleakClient(dev)
    for attempt in range(3):
        try:
            await client.connect(timeout=20.0)
            break
        except Exception as e:  # BlueZ sometimes needs a retry right after a scan
            if attempt == 2:
                raise
            print(f"connect failed ({e}), retrying")
            await asyncio.sleep(1.0)
    acquire = getattr(client._backend, "_acquire_mtu", None)  # BlueZ: learn the real MTU
    if acquire:
        try:
            await acquire()
        except Exception:
            pass
    print(f"connected to {dev.name} [{dev.address}], MTU {client.mtu_size}")
    return client


async def udesc(client: BleakClient, char_uuid: str) -> str:
    ch = client.services.get_characteristic(char_uuid)
    for d in ch.descriptors:
        if d.uuid == UDESC_UUID:
            return bytes(await client.read_gatt_descriptor(d.handle)).decode()
    return ""


# ---- serial console (solvers/common/console.py) ---------------------------

def open_serial() -> Console:
    """Open the console without rebooting the board."""
    return Console(PORT)


def console(cmd: str, until: str, timeout: float = 5.0) -> str:
    """Send one console line, return output up to and including a match of `until`."""
    with open_serial() as s:
        s.sync()
        s.send(cmd)
        buf = s.read_until_re(until, timeout)
        if re.search(until, buf):
            return buf
        raise TimeoutError(f"no {until!r} after {cmd!r}; got {buf!r}")


def reset_and_capture(pattern: str, timeout: float = 15.0) -> re.Match:
    """Reboot the board on purpose and wait for a boot line matching pattern."""
    with open_serial() as s:
        s.reset_board(wait_prompt=False)
        m = re.search(pattern, s.read_until_re(pattern, timeout))
        if m:
            return m
    raise TimeoutError(f"boot output never matched {pattern!r}")


def console_submit(flag: str) -> str:
    with open_serial() as s:
        return s.submit(flag)


async def ble_submit(client: BleakClient, flag: str) -> str:
    got = asyncio.get_running_loop().create_future()

    def on_result(_, data: bytearray):
        if not got.done():
            got.set_result(bytes(data).decode())

    await client.start_notify(CH_RESULT, on_result)
    await client.write_gatt_char(CH_SUBMIT, flag.encode(), response=True)
    try:
        res = await asyncio.wait_for(got, 5.0)
    except asyncio.TimeoutError:
        res = bytes(await client.read_gatt_char(CH_RESULT)).decode()
    await client.stop_notify(CH_RESULT)
    score = bytes(await client.read_gatt_char(CH_SCORE)).decode()
    return f"{res} (score {score})"


async def finish(challenge: str, flag: str, via: str, client: BleakClient = None) -> None:
    """Print the flag, submit it, exit non-zero on failure."""
    if not FLAG_RE.fullmatch(flag or ""):
        sys.exit(f"{challenge}: FAILED, got {flag!r}")
    print(f"{challenge} flag: {flag}")
    if via == "none":
        return
    if via == "ble":
        if client is None or not client.is_connected:
            client = await connect(fresh=False)
        res = await ble_submit(client, flag)
    else:
        if client is not None and client.is_connected:
            await client.disconnect()
            await asyncio.sleep(0.5)  # let the board's disconnect log line pass
        res = console_submit(flag)
    print(f"submit via {via}: {res}")
    if not (res.startswith("Correct!") or res.startswith("Already solved")):
        sys.exit(f"{challenge}: submission rejected")
