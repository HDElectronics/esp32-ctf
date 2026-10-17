# Reference solvers (organizer only)

**Spoilers.** These scripts solve every challenge end to end. They are for
organizers to verify a board or a firmware build; never ship them to players.

## Setup

Use the distro Python (`/usr/bin/python3`): BT Classic solvers need
`socket.AF_BLUETOOTH`, which conda and many pyenv builds lack.

```sh
/usr/bin/python3 -m venv .venv
.venv/bin/pip install bleak dbus-fast pyserial requests zeroconf
```

RE solvers also need esptool and `nvs_tool.py`: run them from the ESP-IDF
environment (`. ~/esp/esp-idf/export.sh`) or `pip install esptool` into the venv
and set `IDF_PATH`.

## Serial port

All tracks talk to the board console through `solvers/common/console.py`,
which opens the port without rebooting the board (DTR and RTS stay asserted
together; see the module docstring). Port selection:

- `--port /dev/ttyUSB0` (web solvers: `--serial` or `--port`; serial/crypto
  solvers also accept the port as first positional argument), else
- `CTF_PORT=/dev/ttyUSB0`, else
- `/dev/ttyACM0`.

Only solvers that need a reboot (CRY-01 boot shards, BLE-09 passkey, HW-01
jumper check, RE solvers reading the MAC banner) call `Console.reset_board()`.

## Running

One script per challenge in `solvers/<track>/`; each prints the flag and the
submit result and exits non-zero on failure. Track READMEs list prerequisites
(radio mode for BLE/BTC, Wi-Fi joined for web, logic captures or a dev build
for HW). Run a whole track, for example:

```sh
for f in solvers/ble/ble*.py; do .venv/bin/python "$f" || echo "FAIL $f"; done
```

Only one process can hold the serial port at a time: close `idf.py monitor`
first.
