#!/usr/bin/env python3
"""BLE-11 Write-without-response sequence: the input characteristic's value
lists 5 bytes; send them as write commands < 500 ms apart, flag is notified on
the output characteristic."""
import asyncio
import re

import _util as u


async def main():
    a = u.args(__doc__)
    client = await u.connect()
    info = bytes(await client.read_gatt_char(u.uuid(0x010B))).decode()
    print(f"input says: {info}")
    seq = [int(x, 16) for x in re.search(r"send ((?:[0-9A-F]{2},? ?){5})", info).group(1)
           .replace(",", " ").split()]
    got = asyncio.get_running_loop().create_future()

    def cb(_, data):
        if not got.done():
            got.set_result(bytes(data).decode())

    await client.start_notify(u.uuid(0x011B), cb)
    for b in seq:
        await client.write_gatt_char(u.uuid(0x010B), bytes([b]), response=False)
        await asyncio.sleep(0.05)
    flag = await asyncio.wait_for(got, 5)
    await u.finish("BLE-11", flag, a.via, client)


asyncio.run(main())
