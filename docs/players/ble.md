# BLE track (Bluetooth Low Energy)

11 challenges, 2000 points. Radio mode.

## Reaching the track

1. On the serial console: `mode` shows the current mode. If it says `net`,
   run `mode radio` (the board reboots). Radio mode is the default.
2. Scan for BLE devices. The board advertises as `ESP32-CTF-XXXX`, where
   `XXXX` is the last two bytes of its MAC (shown in the boot banner).
   - Linux: `bluetoothctl`, then `scan le`. `bluetui` and `bluetuith` scan
     and pair, but they can't browse services, and bluetui always pairs
     before it connects (it asks for a passkey you don't have yet).
   - Phone: any BLE explorer app (e.g. nRF Connect)
3. Connect and list its services. The board accepts one connection at a time
   and advertises again when you disconnect.

The board also shows up a second time under its Bluetooth Classic address
(name `ESP32-CTF-XXXX:hhhhhh`, BTC track). For BLE, pick the entry named just
`ESP32-CTF-XXXX`; `ble` on the serial console prints its address. Connecting
to the Classic entry fails with `org.bluez.Error.BREDR.ProfileUnavailable`.

Linux tip: BlueZ caches a device's GATT database. If things look stale after
re-flashing, `bluetoothctl remove <address>` and scan again.

### Submitting over BLE

Besides the console, the board has a **CTF control** service
`e5320200-c7f0-4e5b-9a1d-3c54460b1e00`:

| Characteristic | UUID | Use |
|----------------|------|-----|
| CTF Submit Flag | `e5320201-c7f0-4e5b-9a1d-3c54460b1e00` | write a flag (any challenge) |
| CTF Submit Result | `e5320202-c7f0-4e5b-9a1d-3c54460b1e00` | read / notify: result of your last submission |
| CTF Score | `e5320203-c7f0-4e5b-9a1d-3c54460b1e00` | read / notify: current points |

## Challenges

### BLE-01 Read the flag (100)
The board's custom service is full of characteristics. Start by simply looking.
Tools: `bluetoothctl` (`menu gatt`), nRF Connect

### BLE-02 Hex and friends (100)
This value is readable, but not in a form you would want to submit.
Tools: `bluetoothctl`, CyberChef

### BLE-03 Notify me (100)
One characteristic refuses to be read. It has other ways of talking.
Tools: `bluetoothctl`, Python `bleak`

### BLE-04 Indicate and ack (200)
The flag arrives in pieces, and the board wants to know you got each one.
Tools: Python `bleak`, `btmon`

### BLE-05 Write to unlock (100)
A sealed hatch and a panel next to it. The panel tells you what it wants.
Tools: `bluetoothctl`, nRF Connect

### BLE-06 Descriptor hunt (200)
A characteristic so boring nobody looks twice at it.
Tools: `bluetoothctl`, Python `bleak`

### BLE-07 Advertising payload (200)
You don't always need to connect to learn something.
Tools: `btmon`, Python `bleak`

### BLE-08 Big MTU (200)
A long telemetry value. Is your client showing you all of it?
Tools: Python `bleak`, `btmon`

### BLE-09 Passkey pairing (200)
A locker that only opens for a properly paired client.
Tools: `bluetoothctl`, `bluetui`, `bluetuith`

### BLE-10 Rate-limited PIN (300)
A four-digit keypad that does not like being rushed. Needs scripting.
Tools: Python `bleak`, `btmon`

### BLE-11 Write-without-response sequence (300)
A sequencer that wants a short pattern, in order, and quickly. Needs scripting.
Tools: Python `bleak`, `btmon`
