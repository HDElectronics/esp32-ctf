# BT Classic reference solvers

One solver per challenge (BTC-01..03). Each finds the board with a BR/EDR
inquiry, recovers the flag the way a player would, submits it on the serial
console (`submit`) and accepts "Correct!" or "Already solved". Pass
`--via none` to print the flag without submitting. With several boards in
range, set `CTF_BTC_ADDR` so the inquiry does not pick another board.

## Setup

```sh
/usr/bin/python3 -m venv .venv && .venv/bin/pip install dbus-fast pyserial
.venv/bin/python solvers/btc/btc01_banner.py
```

- Board in radio mode (`mode radio` on the console), Linux host with BlueZ.
- The Python must have Bluetooth sockets (`socket.AF_BLUETOOTH`): distro
  Python does, conda builds do not.
- `CTF_PORT` (default `/dev/ttyACM0`): serial console for submission.
- `CTF_BTC_ADDR`: board BR/EDR address, skips the inquiry (BTC-01/02).
- Pairing is SSP Just Works (board IO capability NoInputNoOutput): the RFCOMM
  `connect()` triggers it, no agent needed. Every solver ends with
  `bluetoothctl remove <addr>` so the bond is dropped and reruns pair afresh.

| Solver | Notes |
|--------|-------|
| `btc01_banner.py` | inquiry, SDP (`sdptool browse`, record "CTF Console"; falls back to channels 1..5), RFCOMM connect, flag in the banner line `link token:`. Also prints CRY-01 shard 3 |
| `btc02_hidden.py` | runs `help` (help, status, uptime, whoami, exit), takes the backticked verb from the banner that help does not list (`diag`) and runs it |
| `btc03_class.py` | BR/EDR-only discovery via BlueZ D-Bus, reads Name, Class and ManufacturerData, reassembles the body (below) |

## Board side

- BR/EDR address = base MAC + 2. BLE advertises from a separate static random
  address, so BlueZ lists two devices.
- SPP server "CTF Console", RFCOMM channel 1 (from SDP), requires an
  authenticated (paired) link. One session at a time.
- Banner: BTC-01 flag, the BTC-02 clue (old `diag` verb), `cipher shard 3/4: XY`,
  then the `spp> ` prompt. The shell echoes typed characters.

## BTC-03 encoding

Flag body = 12 hex digits `b0..b11`:

| Where | Carries | Example |
|-------|---------|---------|
| BR/EDR name `ESP32-CTF-XXXX:hhhhhh` (EIR + remote name) | `b0..b5` | `ESP32-CTF-3014:4898C0` |
| Class of Device minor field (bits 2..7), major = Uncategorized (0x1F), service = Information | `b6` (value 0..15) | class `0x801f14` → minor 5 |
| EIR manufacturer data, company `0xFFFF`, 3 bytes | `0 b7 b8 b9 b10 b11` (leading 0 nibble marks the CoD digit's slot) | `05 3d a8` |

Body = name suffix + hex(minor) + manufacturer hex without its leading `0`
→ `4898C0` + `5` + `53DA8`. With `bluetoothctl`: `scan bredr`, then
`info <addr>` shows Name, Class and ManufacturerData.

The BLE advertisement keeps the plain name `ESP32-CTF-XXXX` and its own company
0x02E5 data (BLE-07); BlueZ merges both transports into one device, so the
`Name` property may show either. The solver removes the device first and
scans BR/EDR only, so it reads the Classic values.
