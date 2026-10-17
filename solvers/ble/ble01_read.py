#!/usr/bin/env python3
"""BLE-01 Read the flag: read the characteristic, submit via the BLE control service."""
import asyncio

import _util as u


async def main():
    a = u.args(__doc__, default_via="ble")
    client = await u.connect()
    flag = bytes(await client.read_gatt_char(u.uuid(0x0101))).decode()
    await u.finish("BLE-01", flag, a.via, client)
    await client.disconnect()


asyncio.run(main())
