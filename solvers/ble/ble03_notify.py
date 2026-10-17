#!/usr/bin/env python3
"""BLE-03 Notify me: subscribe (CCCD) and wait for the notification."""
import asyncio

import _util as u


async def main():
    a = u.args(__doc__)
    client = await u.connect()
    got = asyncio.get_running_loop().create_future()

    def cb(_, data):
        if not got.done():
            got.set_result(bytes(data).decode())

    await client.start_notify(u.uuid(0x0103), cb)
    flag = await asyncio.wait_for(got, 10)
    await client.stop_notify(u.uuid(0x0103))
    await u.finish("BLE-03", flag, a.via, client)


asyncio.run(main())
