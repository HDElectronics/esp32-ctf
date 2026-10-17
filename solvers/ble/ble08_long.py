#!/usr/bin/env python3
"""BLE-08 Big MTU: the value is > 200 bytes with the flag at the end. BlueZ
negotiates a big MTU and/or does a long read; we also do an explicit offset
read (ATT Read Blob) through BlueZ's D-Bus API to show both paths work."""
import asyncio
import re

from dbus_fast import BusType, Message, MessageType, Variant
from dbus_fast.aio import MessageBus

import _util as u


async def read_at_offset(char_path: str, offset: int) -> bytes:
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    reply = await bus.call(Message(destination="org.bluez", path=char_path,
                                   interface="org.bluez.GattCharacteristic1", member="ReadValue",
                                   signature="a{sv}", body=[{"offset": Variant("q", offset)}]))
    bus.disconnect()
    if reply.message_type == MessageType.ERROR:
        raise RuntimeError(f"ReadValue offset {offset}: {reply.error_name} {reply.body}")
    return bytes(reply.body[0])


async def main():
    a = u.args(__doc__)
    client = await u.connect()
    ch = client.services.get_characteristic(u.uuid(0x0108))
    full = bytes(await client.read_gatt_char(ch))
    print(f"MTU {client.mtu_size}, value length {len(full)} bytes")
    print(f"tail: ...{full[-60:].decode()}")
    tail = await read_at_offset(ch.obj[0], 200)
    print(f"offset-200 read: {len(tail)} bytes, matches: {tail == full[200:]}")
    if tail != full[200:]:
        raise SystemExit("BLE-08: offset read mismatch")
    m = re.search(rb"ESP\{[0-9A-F]{12}\}$", full)
    await u.finish("BLE-08", m.group(0).decode() if m else "", a.via, client)


asyncio.run(main())
