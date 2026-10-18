# Toolbox

Moved here from the README; the [player guides](players/index.md) name the one
or two tools that fit each challenge best.

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
