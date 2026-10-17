# BTC track (Bluetooth Classic)

3 challenges, 500 points. Radio mode.

## Reaching the track

1. Make sure the board is in radio mode (`mode` on the console; `mode radio`
   if it says `net`).
2. Run a Bluetooth Classic (BR/EDR) inquiry. The board is discoverable as
   `ESP32-CTF-XXXX…`.
   - Linux: `bluetoothctl`, then `scan bredr` (or `bluetuith`)
   - Your laptop's Bluetooth settings also see it.
3. The board uses the same address for BLE and Classic, so BlueZ shows a single
   device for both. If you see stale data, `bluetoothctl remove <address>`
   and scan again.

You need a host with a working Bluetooth Classic adapter (most laptop adapters
and USB dongles do both BLE and Classic). On Linux, use the distro's
`python3` if you script with `socket.AF_BLUETOOTH`: conda and some pyenv builds
lack Bluetooth socket support.

## Challenges

### BTC-01 SPP console (100)
The board offers a serial-style console over Bluetooth Classic. Get a terminal on it.
Tools: `bluetuith`, `picocom` / `tio` on an RFCOMM tty (`rfcomm` is legacy) or Python `socket.AF_BLUETOOTH`

### BTC-02 Hidden menu (200)
The console's help is helpful, but not complete.
Tools: `tio`, Python `socket.AF_BLUETOOTH`

### BTC-03 Device class clue (200)
The board says more about itself than its name before you ever connect.
Tools: `bluetoothctl`, `btmon`
