<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/img/banner-dark.png">
    <img src="docs/img/banner-light.png" alt="ESP32 Multi-Track CTF, v0.1.0: one board, 40 challenges, 7 tracks (BLE, BT Classic, Wi-Fi, UART, pins, firmware, crypto). Drawing of an ESP32 DevKit seen from above with radio waves off its antenna." width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://github.com/HDElectronics/esp32-ctf/releases/latest"><img src="https://img.shields.io/github/v/release/HDElectronics/esp32-ctf?color=4b2a7a" alt="Latest release"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-4b2a7a" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/ESP--IDF-v6.1-4b2a7a" alt="ESP-IDF v6.1">
  <img src="https://img.shields.io/badge/target-ESP32-4b2a7a" alt="Target: classic ESP32">
  <img src="https://img.shields.io/badge/challenges-40-a87414" alt="40 challenges">
</p>

Flash one classic ESP32 DevKit and play a self-contained capture-the-flag across
seven tracks, from Bluetooth to firmware reversing. 40 challenges from easy to hard,
scored on the board itself, with per-board flags and built-in hints that cost points.
Inspired by [hackgnar/ble_ctf](https://github.com/hackgnar/ble_ctf), broader in scope.

<p align="center">
  <img src="docs/img/console.png" alt="The board's serial console in tio: boot banner (ESP32 CTF, mode radio, board MAC), then status showing 0 / 7300 points per track, list SER showing four serial challenges, hint SER-03 asking to confirm a 75-point cost, and submit of a wrong flag answered with Wrong flag." width="100%">
</p>

## Quick start

1. Download `esp32-ctf-v0.1.0.bin` from the [latest release](https://github.com/HDElectronics/esp32-ctf/releases/latest).
2. Flash it with `esptool` (`pipx install esptool`); flashing again wipes your progress.
3. Open the console at 115200 8N1, press EN/RST, then type `help`, `status` and `list`.

```sh
# merged image (bootloader + partition table + app) at offset 0x0;
# the port may be /dev/ttyACM0, COM3 or /dev/cu.usbserial-*
esptool --chip esp32 -p /dev/ttyUSB0 write-flash 0x0 esp32-ctf-v0.1.0.bin
tio -b 115200 /dev/ttyUSB0
```

## Tracks

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/tracks-dark.png">
  <img src="docs/img/tracks-light.png" alt="Seven tracks: Bluetooth Low Energy 11 challenges 2000 pts (radio mode); Bluetooth Classic 3 challenges 500 pts (radio); Wi-Fi and web 9 challenges 1500 pts (net); Serial 4 challenges 800 pts (always on); Hardware pins 6 challenges 1000 pts (always on); Firmware reversing 4 challenges 900 pts (always on); Crypto 3 challenges 600 pts (always on). Total 40 challenges, 7300 pts; easy 100, medium 200, hard 300; 6400 without the optional kit." width="100%">
</picture>

Pick a track and read its spoiler-free guide in [docs/players/](docs/players/index.md).

## How it works

The classic ESP32 doesn't have the RAM to run Wi-Fi, BLE and Bluetooth Classic at
once, so the radios are split into two modes. `mode radio` / `mode net` saves the
choice and reboots, progress is kept; `mode` alone shows the current one.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/modes-dark.png">
  <img src="docs/img/modes-light.png" alt="Mode diagram. Mode radio (default): BLE GATT server and advertising, Bluetooth Classic inquiry and SPP; Wi-Fi off. Mode net: the board's own Wi-Fi access point, web server (HTTP, WebSocket), mDNS, UDP services; Bluetooth off. Typing mode radio or mode net switches between them, reboots and keeps progress. Always on in any mode: serial console, UART2, pins (GPIO, LED, touch pads), flash contents, crypto console commands." width="100%">
</picture>

- **Flags are unique per board** (derived from its MAC) and look like `ESP{0123456789AB}`; a few challenges take `answer <id> <value>` instead.
- **Hints cost 25%** of a challenge's points: `hint <id>` shows the cost, `hint <id> yes` reveals it.
- **Submit anywhere:** `submit <flag>` on the console, over BLE in radio mode (CTF control service) or on the board's `/submit` page in net mode; any interface accepts any challenge's flag.
- **Optional-kit challenges can be skipped:** max 7300 points, 6400 without the kit.

## Hardware

- **Required:** a classic ESP32 DevKit with 4 MB flash (ESP32-DevKitC, DOIT DevKit v1 38-pin or similar; not S2/S3/C3/C6), a USB cable, a laptop (Linux is easiest for the Bluetooth tracks) and a phone.
- **Optional kit** (5 challenges, 900 points): a logic analyzer such as a cheap 8-channel 24 MHz FX2 clone that works with sigrok (HW-03, HW-04, HW-05), a 3.3 V USB-UART adapter (SER-02), one jumper wire (HW-01). `status` and `list` mark these.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/img/i2c-dark.png">
  <img src="docs/img/i2c-light.png" alt="Logic analyzer view of HW-04 captured with a 10 dollar FX2 analyzer and sigrok: SCL and SDA traces with the I2C decoder showing Start, address write 0x5A, NACK, then data bytes 'E', 'S', 'P', '{' each followed by a NACK, and 13 more bytes not shown." width="100%">
</picture>

## Toolbox

**Serial** `tio` · **BLE / BT Classic** `bluetoothctl`, `bleak` · **Web** `curl` ·
**Hardware** `sigrok-cli` · **Firmware RE** `esptool`, Ghidra · **Crypto** CyberChef.
Every tool per track, with install commands: [docs/toolbox.md](docs/toolbox.md).

## Organizers & contributors

- [docs/development.md](docs/development.md): build from source, host tests, dev options (and why a dev image must never reach a player), release script, resetting boards.
- [solvers/README.md](solvers/README.md): one reference solver per challenge (full spoilers).
- [docs/SPEC.md](docs/SPEC.md): design and every challenge's mechanism (spoilers).
- [docs/PLAN.md](docs/PLAN.md): plan and status.

## Scope

Every challenge targets the board and nothing else; keep your tools pointed at your own board ([details](docs/players/index.md#scope)).

## License

[MIT](LICENSE). Built on ESP-IDF (Apache-2.0) and the espressif/mdns component (Apache-2.0).
