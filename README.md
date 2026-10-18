# ESP32 Multi-Track CTF

Flash one classic ESP32 DevKit and play a self-contained capture-the-flag across
seven tracks: Bluetooth Low Energy, Bluetooth Classic, Wi-Fi/web, serial,
hardware pins, firmware reversing and crypto. 40 challenges from easy to hard,
scored on the board itself, with flags unique to each board and built-in hints
that cost points. Inspired by [hackgnar/ble_ctf](https://github.com/hackgnar/ble_ctf),
broader in scope.

Player guides: [docs/players/](docs/players/index.md).

## Hardware

- **Required:** a classic ESP32 DevKit with 4 MB flash (ESP32-DevKitC, DOIT
  DevKit v1 38-pin or similar; not S2/S3/C3/C6), a USB cable, a laptop
  (Linux is easiest for the Bluetooth tracks) and a phone.
- **Optional kit** (for 5 challenges, 900 points; skip them if you don't have it):
  - USB-UART adapter, 3.3 V logic (SER-02)
  - one jumper wire (HW-01)
  - a logic analyzer, e.g. a cheap 8-channel 24 MHz FX2 clone that works with sigrok (HW-03, HW-04, HW-05)

## Quick start

1. **Flash** the release image, either
   - from the browser with the web flasher (desktop Chrome or Edge; Web Serial), or
   - with esptool: `esptool --chip esp32 -p /dev/ttyUSB0 write-flash 0x0 esp32-ctf-v0.1.0.bin`
     (`pipx install esptool`; the port may be `/dev/ttyACM0`, `COM3`, `/dev/cu.usbserial-*`).
     The merged `.bin` contains bootloader, partition table and app and goes at offset `0x0`.
2. **Open the serial console** at 115200 8N1, e.g. `tio -b 115200 /dev/ttyUSB0`.
   Press the board's EN/RST button to see the boot banner.
3. Type `help` for the command list, `status` for your score and `list` (or
   `list BLE`, `list HW`, …) for the challenges. Pick a track and read its guide.

Flags look like `ESP{0123456789AB}`. Submit with `submit <flag>` (the bare
12-character body works too, any case). Some challenges give you a value
instead of a flag: send it with `answer <id> <value>`.

## Modes

The classic ESP32 does not have the RAM to run Wi-Fi, BLE and Bluetooth Classic
at once, so the radios are split into two modes. `mode radio` or `mode net` on
the console saves the choice and reboots; `mode` alone shows the current one.

| Mode | Enables | Tracks |
|------|---------|--------|
| `radio` (default) | BLE GATT server + advertising, Bluetooth Classic | BLE, BTC |
| `net` | the board's own Wi-Fi access point, web server, WebSocket, mDNS, UDP services | WEB |
| always on | USB serial console, GPIO pins, touch pads, flash contents | SER, HW, RE, CRY |

Progress is kept across mode switches and reboots.

## Scoring and hints

- Easy 100, medium 200, hard 300 points. Maximum 7300, or 6400 without the optional kit.
- `hint <id>` shows what a hint would cost (25% of the challenge's points);
  `hint <id> yes` reveals it and deducts the cost, once per challenge.
- Flags can be submitted on the console (`submit`), over BLE in radio mode
  (CTF control service) or on the board's `/submit` page in net mode. Any
  interface accepts any challenge's flag.

## Tracks

| Track | Challenges | Points | Mode | Interface | Guide |
|-------|-----------:|-------:|------|-----------|-------|
| BLE: Bluetooth Low Energy | 11 | 2000 | radio | GATT, advertising | [ble.md](docs/players/ble.md) |
| BTC: Bluetooth Classic | 3 | 500 | radio | inquiry, SPP | [btc.md](docs/players/btc.md) |
| WEB: Wi-Fi and web | 9 | 1500 | net | SoftAP, HTTP, WebSocket, mDNS, UDP | [web.md](docs/players/web.md) |
| SER: Serial | 4 | 800 | always | USB console, UART2 | [serial.md](docs/players/serial.md) |
| HW: Hardware pins | 6 | 1000 | always | LED, GPIO, touch pads | [hw.md](docs/players/hw.md) |
| RE: Firmware reversing | 4 | 900 | always | flash dump, console | [re.md](docs/players/re.md) |
| CRY: Crypto | 3 | 600 | always | console | [crypto.md](docs/players/crypto.md) |

**Optional-kit challenges:** SER-02 (USB-UART adapter), HW-01 (jumper wire),
HW-03, HW-04, HW-05 (logic analyzer). `status` and `list` mark them with the
kit they need. Skip them if you don't have it; every other challenge needs only
a laptop and a phone.

## Toolbox

Terminal tools that fit each track, TUIs first. Install hints are for
Debian/Ubuntu (`apt`) or language package managers (`pipx`, `pip` in a venv,
`cargo`, `go install`). Use them against your own board only.

| Track | TUI | CLI and libraries |
|-------|-----|-------------------|
| General | `tmux` | `pwntools` (serial and TCP tubes for scripting), `jq` |
| BLE | `bluetui`, `bluetuith` | `bluetoothctl` (`menu gatt`), `btmon` (HCI trace), Python `bleak`, `ble-serial` |
| BT Classic | `bluetuith` | `bluetoothctl`, `picocom` / `tio` on an RFCOMM tty, Python `socket.AF_BLUETOOTH` |
| Wi-Fi / web | `nmtui` (joins hidden networks), `posting` (HTTP), `mitmproxy` | `nmcli`, `curl`, `xh` / `httpie`, `websocat`, `jwt-cli`, `hashcat -m 16500`, `avahi-browse`, `nmap` (the board's IP only), `ncat` / `socat`, `knock` |
| Serial | `tio`, `minicom` | `picocom`, `pyserial-miniterm`, `idf.py monitor` |
| Hardware | none (`PulseView` GUI for viewing traces) | `sigrok-cli -P i2c / spi / uart`, phone slow-motion video |
| Firmware RE | `hexyl` (hex view), `radare2` / `rizin` visual mode (Xtensa supported) | `esptool read-flash`, `parttool.py`, `nvs_tool.py` (ESP-IDF), `esp32_image_parser`, `binwalk`, `strings`; Ghidra 11+ (GUI, native Xtensa) |
| Crypto | none | `xortool`, `openssl enc`, Python `pycryptodome`; CyberChef (web) |
| Captures | `termshark` | `tshark`, `btmon -w` then Wireshark |

Install hints:

| Tool | Install |
|------|---------|
| `tmux`, `jq` | `apt install tmux jq` |
| `pwntools` | `pip install pwntools` (or `apt install python3-pwntools`) |
| `bluetui` | `cargo install bluetui` |
| `bluetuith` | `go install github.com/darkhz/bluetuith@latest` |
| `bluetoothctl`, `btmon` | `apt install bluez` |
| `bleak` | `pip install bleak` |
| `ble-serial` | `pipx install ble-serial` |
| `socket.AF_BLUETOOTH` | built into the distro's `python3` (conda/pyenv builds may lack it) |
| `nmtui`, `nmcli` | `apt install network-manager` |
| `posting` | `pipx install posting` |
| `mitmproxy` | `pipx install mitmproxy` |
| `curl` | `apt install curl` |
| `xh` | `apt install xh` or `cargo install xh` |
| `httpie` | `pipx install httpie` |
| `websocat` | `cargo install websocat` |
| `jwt-cli` | `cargo install jwt-cli` (command: `jwt`) |
| `hashcat` | `apt install hashcat` |
| `avahi-browse` | `apt install avahi-utils` |
| `nmap`, `ncat`, `socat` | `apt install nmap ncat socat` |
| `knock` | `apt install knockd` (ships the `knock` client) |
| `tio`, `minicom`, `picocom` | `apt install tio minicom picocom` |
| `pyserial-miniterm` | `pipx install pyserial` |
| `idf.py monitor` | part of [ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/get-started/) |
| `PulseView`, `sigrok-cli` | `apt install pulseview sigrok-cli` |
| `hexyl` | `apt install hexyl` or `cargo install hexyl` |
| `radare2` / `rizin` | `apt install radare2`; rizin from [rizin.re](https://rizin.re) releases |
| `esptool` | `pipx install esptool` |
| `parttool.py`, `nvs_tool.py` | in ESP-IDF: `components/partition_table/`, `components/nvs_flash/nvs_partition_tool/` |
| `esp32_image_parser` | `git clone https://github.com/tenable/esp32_image_parser` (community tool) |
| `binwalk`, `strings` | `apt install binwalk binutils` |
| Ghidra 11+ | [github.com/NationalSecurityAgency/ghidra/releases](https://github.com/NationalSecurityAgency/ghidra/releases) (needs a JDK 21) |
| `xortool` | `pipx install xortool` |
| `openssl` | `apt install openssl` |
| `pycryptodome` | `pip install pycryptodome` |
| CyberChef | [gchq.github.io/CyberChef](https://gchq.github.io/CyberChef/) |
| `termshark`, `tshark` | `apt install termshark tshark` |
| Wireshark | `apt install wireshark` |

BlueZ's old utilities `hcitool`, `gatttool`, `rfcomm` and `sdptool` still work
with this board but are **legacy, may be missing on new distros**; prefer
`bluetoothctl`, `btmon` and the tools above.

## Scope and ethics

Every challenge targets the board and nothing else. The board runs its own
access point and Bluetooth services; no challenge asks you to scan, join,
attack or affect any other network or device. Keep tools like `nmap` and
`hashcat` pointed at the board's own address and data. If you play in a room
with other boards, only touch your own.

## Building from source

Requires ESP-IDF v6.1 (target `esp32`).

```sh
. ~/esp/esp-idf/export.sh
idf.py build
idf.py -p /dev/ttyUSB0 flash monitor
```

Release image (clean build in `build-release/` from `sdkconfig.defaults` only,
merged `.bin`, ESP Web Tools manifest and a ready-to-host flasher site):

```sh
scripts/release.sh
# -> dist/esp32-ctf-v0.1.0.bin, dist/manifest.json, web/flasher/dist-site/
```

Host unit tests for the portable engine:

```sh
cmake -S test/host -B build-host && cmake --build build-host && ctest --test-dir build-host --output-on-failure
```

### Dev options

Never enable these in a build you hand to players; `scripts/release.sh`
refuses to package one.

- `CONFIG_CTF_HW_DEV` (`hwdev` command: derived HW values, touch/LED/bus self-tests)
- `CONFIG_CTF_CRYPTO_DEV` (prints the CRY-01 key shards at boot)
- `CONFIG_CTF_WEB_DEV_STA` (+ `_SSID`, `_PASS`): in net mode the board also
  joins a test network so a LAN host can reach the web track. Put the three
  options in a git-ignored overlay, e.g. `sdkconfig.dev.local`:

  ```
  CONFIG_CTF_WEB_DEV_STA=y
  CONFIG_CTF_WEB_DEV_STA_SSID="my-test-net"
  CONFIG_CTF_WEB_DEV_STA_PASS="..."
  ```

  and build it in its own directory:

  ```sh
  idf.py -B build-dev -DSDKCONFIG=build-dev/sdkconfig \
      -DSDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.dev.local" build
  ```

  **The dev image stores that Wi-Fi password in flash, and the RE track
  teaches players to dump flash.** Before a board goes to a player, wipe it
  and flash the release image:
  `esptool --chip esp32 -p <PORT> erase-flash`, then
  `esptool --chip esp32 -p <PORT> write-flash 0x0 dist/esp32-ctf-v0.1.0.bin`.

- `CONFIG_CTF_SIZE_PROBE` (links unused stack stubs to measure image size)

## For organizers

- `solvers/` holds one reference solver per challenge. They are full
  spoilers: do not hand them to players.
- `docs/SPEC.md` describes every challenge's mechanism, also a spoiler.
- `reset yes` on the console wipes all progress and used hints and reboots;
  the firmware-reversing artefacts are re-provisioned on the next boot.
  Flashing the merged image also wipes progress (it covers the NVS
  partition); a full chip erase (`esptool --chip esp32 erase-flash`) before
  flashing gives a completely fresh board.
- Flags are derived from each board's MAC, so two boards never share flags.

License: [MIT](LICENSE). Built on ESP-IDF (Apache-2.0) and the espressif/mdns component (Apache-2.0).
