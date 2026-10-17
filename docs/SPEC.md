# ESP32 Multi-Track CTF — Spec

Flash one classic ESP32 DevKit, play a self-contained CTF across radio, network,
serial, hardware-pin, firmware-reversing and crypto tracks. Inspired by
hackgnar/ble_ctf, broader in scope.

## Goals

- One prebuilt firmware image, flashed from the browser or `esptool.py`, then play.
- 40 challenges, mixed difficulty (easy → hard), self-scored on the board.
- Flags unique per board, so players cannot swap flags.
- Built-in hints that cost points.
- Every challenge is solvable with a laptop + phone; a few optional ones need
  extra kit (USB-UART adapter, logic analyzer, jumper wires).

## Non-goals (v1)

- ESP-NOW track (dropped), USB track, Zigbee/Thread, other chips (S3/C3/C6).
- Online / multi-board scoreboard. Scoring lives on the board only.
- Tamper-proofing. A player who reverses the firmware can recover the flag key
  and forge every flag. This is a learning CTF; we do not burn eFuses or enable
  flash encryption on players' boards.
- **Scope rule:** no challenge involves networks or devices other than the
  board itself.

## Stack

- Target: ESP32 (Xtensa LX6, dual core, 4 MB flash), e.g. ESP32-DevKitC / DOIT DevKit v1.
- ESP-IDF **v6.1** (installed at `~/esp/esp-idf`), C11, CMake via `idf.py`.
- Bluetooth: **Bluedroid** dual-mode (BLE GATT server + Classic SPP). NimBLE is
  BLE-only, so it is not used.
- Wi-Fi: SoftAP, `esp_http_server` (HTTP + WebSocket), `espressif/mdns` managed component.
- Console: `esp_console` REPL on UART0 (USB), 115200 baud.
- Storage: NVS (progress, `vault` namespace), SPIFFS data partition (web files, RE blob),
  raw `notes` data partition (RE-01).
- Host tests: plain CMake + C compiler on Linux for the `ctf_core` component (no IDF dependency).
- Player-side solvers: Python 3 (`bleak`, `pyserial`, `requests`).

## Architecture

```
main/                 boot: init NVS, load mode, start always-on tracks, start mode tracks
components/
  ctf_core/           portable C, no IDF includes: sha256/hmac, flag derivation,
                      challenge registry, submission check, scoring, hints, answer gates.
                      Storage via a small backend interface (NVS on device, memory on host).
  ctf_platform/       IDF glue: NVS storage backend, chip MAC, mode switch, console setup.
  track_serial/       SER-01..04 (always on)
  track_crypto/       CRY-01..03 (always on, console commands)
  track_hw/           HW-01..06 (always on)
  track_re/           RE-01..04 (always on; first-boot provisioning of RE artefacts)
  track_ble/          BLE-01..11 + BT controller/Bluedroid init (radio mode)
  track_btc/          BTC-01..03 (radio mode, needs track_ble's Bluedroid init)
  track_web/          WEB-01..09 (net mode)
test/host/            host build of ctf_core + unit tests
solvers/              one reference solver per challenge (proves solvability)
docs/players/         player-facing track guides and tool setup
web/flasher/          ESP Web Tools manifest + page (release)
```

### Modes

Running Wi-Fi + BLE + BT Classic together on the classic ESP32 is RAM-tight, so
radios are split into two modes. Mode is stored in NVS; `mode radio|net` on the
console saves it and reboots.

| Mode | Radios / services | Tracks |
|------|-------------------|--------|
| `radio` (default) | Bluedroid BLE + Classic | BLE, BTC |
| `net` | Wi-Fi SoftAP, HTTP/WS, mDNS, UDP | WEB |
| always | UART console, GPIO, touch, flash artefacts | SER, CRY, HW, RE |

### Flags

- `body = upper(hex(HMAC-SHA256(K, mac6 || challenge_id_ascii)))[0:12]`, 12 hex chars.
- `K`: 32-byte key compiled in, lightly obfuscated (XOR split). Accepted risk, see non-goals.
- Display form `ESP{<body>}`. Submission is case-insensitive and accepts either
  the wrapped form or the bare body. Morse and cipher challenges carry the bare body.
- Values a challenge needs (PIN, passkey, password, touch code, PWM frequency,
  SSID name) are derived the same way with a different label (e.g. `"BLE-10:pin"`),
  so they are also per board.
- **Answer gates:** challenges whose natural answer is a value (PWM frequency,
  touch code, …) register a validator; `answer <id> <value>` on the console
  returns the flag when correct.

### Scoring and hints

- Points: easy 100, medium 200, hard 300.
- `hint <id>` reveals the challenge's hint and deducts 25% of its points
  (once per challenge). Hint text is stored in firmware.
- Progress record in NVS namespace `ctf`: solved bitmap + hint-used bitmap,
  with an HMAC tag so casual NVS editing does not mark challenges solved.
- `reset` (with typed confirmation `reset yes`) wipes progress and RE artefacts
  are re-provisioned on next boot.

### Optional-kit challenges

SER-02, HW-01, HW-03, HW-04, HW-05 need extra hardware (USB-UART adapter, jumper
wire, logic analyzer). The registry marks them `needs_kit` with a short kit
label. `status` and the challenge list show the label and "skip if you don't
have it"; `status` reports both the full max score and the max score without kit.
Player docs say the same at the top of each affected challenge.

### Submission and scoreboard (all on the board)

- Console: `submit <flag>`, `status` (score, solved list per track), `hint`, `answer`.
- Radio mode: BLE "CTF control" service with a submit characteristic (write) and a
  score characteristic (read/notify).
- Net mode: `/score` page and `/submit` form on the board's web server.
- Any interface accepts any challenge's flag.

### Console commands (core set)

`help`, `status`, `submit`, `answer`, `hint`, `mode`, `reset`, `wifi` (net mode
clue), plus commands that tracks register (`oracle`, `unlock`, …).

### Pin map (DevKit v1, 38-pin)

| Use | Pins |
|-----|------|
| Onboard LED (HW-02) | GPIO2 |
| Jumper (HW-01) | GPIO26 (driven high) → GPIO33 (input, pull-down), read at boot |
| UART2 (SER-02) | TX GPIO17, RX GPIO16, 28800 8N1 |
| PWM (HW-03) | GPIO25 |
| Bit-banged I2C (HW-04) | SDA GPIO21, SCL GPIO22 |
| Bit-banged SPI (HW-05) | SCK GPIO18, MOSI GPIO23, CS GPIO5 |
| Touch keypad (HW-06) | T0 GPIO4, T4 GPIO13, T7 GPIO27, T9 GPIO32 |

Avoid strapping pins (0, 2 as input, 5 at boot is fine as output, 12, 15).

### Partitions (4 MB)

`nvs` 24K, `phy_init` 4K, `factory` app ≥ 2.5 MB (Bluedroid + Wi-Fi is large),
`notes` raw data 4K (RE-01), `storage` SPIFFS for the rest (web files, RE-04 blob).
If SPIFFS is unavailable in IDF 6.1, use `joltwallet/littlefs`.

## Challenge catalogue

Difficulty: E easy, M medium, H hard. Kit: extra hardware needed.

### BLE (radio mode)

| ID | Name | Lvl | Mechanism |
|----|------|-----|-----------|
| BLE-01 | Read the flag | E | Characteristic, read returns `ESP{…}` plain. |
| BLE-02 | Hex and friends | E | Read returns flag hex-encoded → base64 → bytes reversed. |
| BLE-03 | Notify me | E | Flag sent only as a notification after CCCD subscribe. |
| BLE-04 | Indicate and ack | M | Flag in indications; next fragment only after the client confirms the previous one. |
| BLE-05 | Write to unlock | E | Write a value (given in the characteristic's user description) to unlock a second readable characteristic. |
| BLE-06 | Descriptor hunt | M | Flag in a custom descriptor on an otherwise boring characteristic. |
| BLE-07 | Advertising payload | M | Flag split into 3 parts in manufacturer data; advert rotates parts every 2 s. |
| BLE-08 | Big MTU | M | Value is 200+ bytes; flag at the end, needs MTU exchange or long read. |
| BLE-09 | Passkey pairing | M | Characteristic needs encrypted + authenticated link; static per-board passkey printed on the console at boot. |
| BLE-10 | Rate-limited PIN | H | 4-digit per-board PIN written to a characteristic; 5 wrong tries → 3 s lockout. Brute force fits in minutes with scripting. |
| BLE-11 | Write-without-response sequence | H | Send 5 specific write-without-response values in order, each within 500 ms of the last. |

Also in radio mode: CTF control service (submit + score), see above.

### BT Classic (radio mode)

| ID | Name | Lvl | Mechanism |
|----|------|-----|-----------|
| BTC-01 | SPP console | E | Discoverable; pair, open RFCOMM SPP; banner shows the flag. |
| BTC-02 | Hidden menu | M | SPP shell has `help`; an undocumented command (hinted in banner) prints the flag. |
| BTC-03 | Device class clue | M | First half of flag body in device name suffix, second half encoded in the Class of Device minor bits + EIR manufacturer data. |

### Web (net mode, board's own SoftAP)

| ID | Name | Lvl | Mechanism |
|----|------|-----|-----------|
| WEB-01 | Hidden SSID | E | AP SSID is hidden. Console `wifi` prints SSID in base32 + WPA2 password. Landing page shows flag. |
| WEB-02 | View source | E | Flag split between an HTML comment and `/robots.txt` disallowed path. |
| WEB-03 | Cookie admin | E | `role=guest` cookie; `role=admin` reveals `/admin` flag. |
| WEB-04 | Header check | E | `/api/secret` answers only with `User-Agent: ESP32-CTF-Agent` and `X-CTF-Key: <value from page>`. |
| WEB-05 | Weak JWT | M | HS256 JWT login as `guest`; secret is a word from a 1000-word list served at `/wordlist.txt`; forge `admin`. |
| WEB-06 | Ping tool | M | "Diagnostics" form with a filename parameter; `../` traversal inside the SPIFFS mount reads `/storage/secret/flag.txt`. Confined to the board's own filesystem. |
| WEB-07 | WebSocket chatter | M | `/ws` sends noise frames; flag in a binary frame every 30 s. |
| WEB-08 | mDNS discovery | M | `_ctf._tcp` service advertised only via mDNS points to a second HTTP port with the flag. |
| WEB-09 | UDP knock | H | UDP to 3 per-board ports in order opens TCP port 31337 for 30 s, which prints the flag. Ports hinted on console. |

Net mode also serves `/score` and `/submit`.

### Serial (always)

| ID | Name | Lvl | Kit | Mechanism |
|----|------|-----|-----|-----------|
| SER-01 | Boot log | E | | Flag printed once in the boot banner, scrolled among log noise. |
| SER-02 | Wrong baud | M | USB-UART | UART2 at 28800 prints the flag every 5 s. |
| SER-03 | Debug login | H | | `login <pw>`: per-board 8-char password, compared char by char with ~30 ms delay per correct char. Timing attack recovers it. |
| SER-04 | Escape sequence | M | | Sending Ctrl-] then `d` `b` `g` within 1 s on the console opens a hidden prompt with the flag. |

### Hardware (always)

| ID | Name | Lvl | Kit | Mechanism |
|----|------|-----|-----|-----------|
| HW-01 | Jumper it | E | jumper | GPIO26↔GPIO33 bridged at boot → flag on console. |
| HW-02 | Blinky Morse | E | | GPIO2 LED blinks flag body in Morse in a loop (~12 WPM). |
| HW-03 | PWM frequency | M | logic analyzer | GPIO25 PWM at per-board frequency 1000–9999 Hz; `answer HW-03 <hz>` (±1%) returns flag. |
| HW-04 | I2C chatter | M | logic analyzer | Bit-banged I2C master writes flag to address 0x5A every 5 s, ignores NACK so data is on the wire without a slave. |
| HW-05 | SPI dump | M | logic analyzer | Bit-banged SPI mode 0, sends flag every 10 s. |
| HW-06 | Touch pad code | M | | 4 touch pads as keypad; enter per-board 6-touch sequence (hinted via console) → flag on console. |

### Firmware reversing (always)

| ID | Name | Lvl | Mechanism |
|----|------|-----|-----------|
| RE-01 | Strings in flash | E | At first boot, flag written in plain text into the raw `notes` partition. `esptool.py read_flash` + `strings`. |
| RE-02 | NVS secrets | M | Flag stored in NVS namespace `vault` key `k`, stored XOR'd with a single byte; parse the NVS partition. |
| RE-03 | Crackme | H | `unlock <key>` console command; key check is a small custom transform in the app image. Reverse it from the dumped `factory` partition in Ghidra (Xtensa). Correct key returns the flag. |
| RE-04 | XOR'd asset | H | SPIFFS file `blob.bin` = flag XOR'd with a keystream derived in code (simple LFSR seeded from MAC). |

### Crypto (always, console)

| ID | Name | Lvl | Mechanism |
|----|------|-----|-----------|
| CRY-01 | Classic cipher | E | Vigenère ciphertext of flag body on console `cipher`; key word split into fragments shown in other tracks' banners. |
| CRY-02 | ECB penguin | H | `oracle <hex>` returns AES-128-ECB(prefix_input || flag); byte-at-a-time recovery. |
| CRY-03 | Reused nonce | M | `msgs` prints two AES-CTR ciphertexts with the same nonce, one known plaintext; XOR recovers the flag. |

## Key flows

1. Flash → open serial at 115200 → banner, `help`, `status` (radio mode default).
2. Solve in radio mode, `mode net` → reboot → connect to hidden AP → web track.
3. Submit any flag from console, BLE control service or web form; `status` shows score.
4. `hint <id>` when stuck; `reset yes` to start over.

## Definition of done (MVP)

- `idf.py build` clean for target `esp32`; host tests pass.
- All 40 challenges implemented and registered; each has a reference solver in
  `solvers/` and is confirmed solved on real hardware (HW checklist in PLAN.md).
- Mode switch, submission from all three interfaces, hints, reset work on hardware.
- Two different boards produce different flags.
- Player docs per track + flash instructions; release build + ESP Web Tools manifest.
