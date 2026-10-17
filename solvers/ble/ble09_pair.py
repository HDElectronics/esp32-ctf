#!/usr/bin/env python3
"""BLE-09 Passkey pairing: the locker needs an encrypted + MITM-authenticated
link. The board prints its static passkey at boot ("ble passkey: NNNNNN"); we
reset it over the serial port to read that line (or take --passkey), register
a KeyboardOnly BlueZ agent that answers RequestPasskey, pair, read, and remove
the bond again so the solver can be rerun."""
import argparse
import asyncio

from dbus_fast import BusType, Message, MessageType
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, method

import _util as u

AGENT_PATH = "/ctf/ble09/agent"


class Agent(ServiceInterface):
    def __init__(self, passkey: int):
        super().__init__("org.bluez.Agent1")
        self.passkey = passkey

    @method()
    def Release(self):
        pass

    @method()
    def RequestPasskey(self, device: "o") -> "u":  # noqa: F821
        print(f"agent: RequestPasskey for {device} -> {self.passkey:06d}")
        return self.passkey

    @method()
    def RequestPinCode(self, device: "o") -> "s":  # noqa: F821
        return f"{self.passkey:06d}"

    @method()
    def DisplayPasskey(self, device: "o", passkey: "u", entered: "q"):  # noqa: F821
        pass

    @method()
    def DisplayPinCode(self, device: "o", pincode: "s"):  # noqa: F821
        pass

    @method()
    def RequestConfirmation(self, device: "o", passkey: "u"):  # noqa: F821
        pass

    @method()
    def RequestAuthorization(self, device: "o"):  # noqa: F821
        pass

    @method()
    def AuthorizeService(self, device: "o", uuid: "s"):  # noqa: F821
        pass

    @method()
    def Cancel(self):
        print("agent: Cancel")


async def call(bus, path, iface, member, signature="", body=()):
    reply = await bus.call(Message(destination="org.bluez", path=path, interface=iface,
                                   member=member, signature=signature, body=list(body)))
    if reply.message_type == MessageType.ERROR:
        raise RuntimeError(f"{member}: {reply.error_name} {reply.body}")
    return reply.body


async def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--passkey", type=int, help="skip the serial reset, use this passkey")
    a, _ = p.parse_known_args()
    via = u.args(__doc__).via

    if a.passkey is None:
        m = u.reset_and_capture(r"ble passkey: (\d{6})")
        a.passkey = int(m.group(1))
        print(f"passkey from boot log: {a.passkey:06d}")
        await asyncio.sleep(2.0)  # let the BLE stack come up

    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    bus.export(AGENT_PATH, Agent(a.passkey))
    await call(bus, "/org/bluez", "org.bluez.AgentManager1", "RegisterAgent", "os",
               [AGENT_PATH, "KeyboardOnly"])
    address = None
    try:
        client = await u.connect()
        address = client.address
        dev_path = client._backend._device_path  # BlueZ object path of the board
        # Pair from the bus that owns the agent, so BlueZ asks *our* agent.
        # (Reading first would also work: BlueZ answers "insufficient
        # authentication" by pairing on its own through the default agent.)
        try:
            await call(bus, dev_path, "org.bluez.Device1", "Pair")
        except RuntimeError as e:
            if "AlreadyExists" not in str(e):
                raise
        paired = (await call(bus, dev_path, "org.freedesktop.DBus.Properties", "Get", "ss",
                             ["org.bluez.Device1", "Paired"]))[0].value
        print(f"paired: {paired}")
        flag = bytes(await client.read_gatt_char(u.uuid(0x0109))).decode()
        await u.finish("BLE-09", flag, via, client)
        if client.is_connected:
            await client.disconnect()
    finally:
        await call(bus, "/org/bluez", "org.bluez.AgentManager1", "UnregisterAgent", "o",
                   [AGENT_PATH])
        bus.disconnect()
        if address:
            u.bluez_remove(address)
            print(f"bond removed ({address})")


asyncio.run(main())
