#!/usr/bin/env python3
"""BLE-02 Hex and friends: value = reverse(base64(hex(flag))); peel it."""
import asyncio
import base64

import _util as u


async def main():
    a = u.args(__doc__)
    client = await u.connect()
    raw = bytes(await client.read_gatt_char(u.uuid(0x0102)))
    print(f"raw: {raw.decode()}")
    flag = bytes.fromhex(base64.b64decode(raw[::-1]).decode()).decode()
    await u.finish("BLE-02", flag, a.via, client)


asyncio.run(main())
