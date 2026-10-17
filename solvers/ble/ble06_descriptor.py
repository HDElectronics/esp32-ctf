#!/usr/bin/env python3
"""BLE-06 Descriptor hunt: list descriptors, read the one with a custom UUID."""
import asyncio

import _util as u

STANDARD = "-0000-1000-8000-00805f9b34fb"


async def main():
    a = u.args(__doc__)
    client = await u.connect()
    flag = None
    for svc in client.services:
        for ch in svc.characteristics:
            for d in ch.descriptors:
                if not d.uuid.endswith(STANDARD):
                    val = bytes(await client.read_gatt_descriptor(d.handle)).decode()
                    print(f"custom descriptor {d.uuid} on {ch.uuid}: {val}")
                    if u.FLAG_RE.fullmatch(val):
                        flag = val
    await u.finish("BLE-06", flag, a.via, client)


asyncio.run(main())
