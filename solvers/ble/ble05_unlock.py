#!/usr/bin/env python3
"""BLE-05 Write to unlock: the panel's User Description says what to write;
then the hatch characteristic holds the flag."""
import asyncio
import re

import _util as u


async def main():
    a = u.args(__doc__)
    client = await u.connect()
    desc = await u.udesc(client, u.uuid(0x0105))
    print(f"user description: {desc}")
    word = re.search(r"write (\S+)", desc).group(1)
    print(f"hatch before: {bytes(await client.read_gatt_char(u.uuid(0x0115))).decode()}")
    await client.write_gatt_char(u.uuid(0x0105), word.encode(), response=True)
    flag = bytes(await client.read_gatt_char(u.uuid(0x0115))).decode()
    await u.finish("BLE-05", flag, a.via, client)


asyncio.run(main())
