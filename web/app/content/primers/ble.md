# Bluetooth Low Energy in three minutes

Bluetooth Low Energy (BLE) is the low-power side of Bluetooth. Fitness bands, smart bulbs, heart-rate straps, key finders and most "connect with the app" gadgets use it. It is built for small values sent now and then, not for audio or big files. The board speaks BLE only in radio mode: if `mode` on the console says `net`, run `mode radio` and let it reboot.

## How it works

A BLE device starts by **advertising**: several times a second it broadcasts a short packet that says "I'm here". The packet can carry a name, a list of services and a few bytes of extra data. Anyone nearby can hear it without connecting, which is how your phone finds a device before you tap it.

When you **connect**, the device becomes a small database you can browse. This database is called **GATT**, and it is a tree:

- A **service** groups related things, such as "battery" or "heart rate".
- Inside each service sit **characteristics**, the actual values.
- Each characteristic can carry **descriptors**: small extra attributes that describe or configure it.

Every item has a **UUID**, a long number that names it. Standard ones are short (`0x180F` is the battery service); custom ones are 128 bits long.

Each characteristic also lists its **properties**, which say what you may do with it: read it, write to it, write without waiting for a reply, or ask it to send you updates. Updates come in two flavours. A **notification** is pushed to you after you subscribe. An **indication** is the same, except your side has to confirm each one.

Values are raw bytes. Sometimes they are readable text, sometimes numbers, sometimes text that has been encoded. Tools usually show both a hex view and a text view, so look at both.

Some values are protected. Reading them needs an **encrypted** link, and some need the two devices to be **paired** first, often by typing a passkey.

## Words you'll meet

**Central**: the side that scans and connects (your laptop or phone).

**Peripheral**: the side that advertises and holds the data (the board).

**GATT**: the tree of services, characteristics and descriptors you browse after connecting.

**Handle**: a small number that identifies one item in the GATT tree during a connection.

**CCCD**: the descriptor you write to switch notifications or indications on.

**MTU**: the largest packet the link carries. Both sides agree on it after connecting.

**Pairing**: setting up encryption keys between two devices; bonding means keeping them for next time.

## Get set up

**bluetoothctl** (BlueZ's own shell): `sudo apt install bluez`

```sh
bluetoothctl
scan le
```

Then `connect <address>`, `menu gatt` and `list-attributes`. If things look stale after a re-flash, `remove <address>` and scan again.

**bluetui** (a friendlier terminal view): `cargo install bluetui`, then run `bluetui`.

**bleak** (Python, for scripting): `pip install bleak`, then a first scan:

```python
import asyncio
from bleak import BleakScanner

async def main():
    for d in await BleakScanner.discover():
        print(d.address, d.name)

asyncio.run(main())
```

On a phone, a BLE explorer app such as nRF Connect shows the same tree.

## Where to start

Start with **BLE-01 Read the flag**. Find `ESP32-CTF-XXXX` in a scan, connect, and look through the custom service's characteristics.
