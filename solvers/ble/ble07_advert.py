#!/usr/bin/env python3
"""BLE-07 Advertising payload: no connection; collect the 3 rotating parts of
the manufacturer data (company 0x02E5, payload "<n>:<part>")."""
import asyncio

from bleak import BleakScanner

import _util as u


async def main():
    a = u.args(__doc__)
    parts = {}
    done = asyncio.Event()

    def cb(dev, adv):
        if not u._is_board(dev, adv):
            return
        data = adv.manufacturer_data.get(u.COMPANY_ID)
        if not data:
            return
        idx, part = bytes(data).decode().split(":", 1)
        if parts.get(int(idx)) != part:
            print(f"part {idx}/3: {part}")
        parts[int(idx)] = part
        if len(parts) == 3:
            done.set()

    # The host controller filters duplicate adverts per address, so a long scan
    # only sees a changed payload when the filter resets (~10 s on BlueZ).
    # Short scans restarted back to back sample the current part each time.
    for _ in range(30):
        async with BleakScanner(cb, bluez={"filters": {"DuplicateData": True}}):
            try:
                await asyncio.wait_for(done.wait(), 1.5)
            except asyncio.TimeoutError:
                pass
        if done.is_set():
            break
    if not done.is_set():
        raise SystemExit(f"BLE-07: only saw parts {sorted(parts)}")
    flag = "".join(parts[i] for i in (1, 2, 3))
    await u.finish("BLE-07", flag, a.via)


asyncio.run(main())
