#!/usr/bin/env python3
"""BLE-04 Indicate and ack: subscribe for indications; BlueZ confirms each one,
which releases the next fragment ("i/n:xxxx")."""
import asyncio

import _util as u


async def main():
    a = u.args(__doc__)
    client = await u.connect()
    frags = {}
    done = asyncio.Event()

    def cb(_, data):
        head, part = bytes(data).decode().split(":", 1)
        i, n = map(int, head.split("/"))
        frags[i] = part
        print(f"fragment {i}/{n}: {part}")
        if len(frags) == n:
            done.set()

    await client.start_notify(u.uuid(0x0104), cb)
    await asyncio.wait_for(done.wait(), 15)
    await client.stop_notify(u.uuid(0x0104))
    flag = "".join(frags[i] for i in sorted(frags))
    await u.finish("BLE-04", flag, a.via, client)


asyncio.run(main())
