# BLE reference solvers

One solver per challenge (BLE-01..11). Each recovers the flag over BLE the way a
player would, then submits it: `ble01_read.py` through the BLE "CTF control"
service, the others through the serial console `submit` (override with
`--via console|ble|none`).

## Setup

```sh
python3 -m venv .venv && .venv/bin/pip install bleak pyserial   # dbus-fast comes with bleak
.venv/bin/python solvers/ble/ble01_read.py
```

- Board in radio mode (`mode radio` on the console), Linux host with BlueZ.
- `CTF_PORT` (default `/dev/ttyACM0`): serial console, used for console
  submission and by BLE-09 to read the boot-time passkey.
- `CTF_BLE_NAME`: exact advertised name if several boards are around
  (default: first `ESP32-CTF-*`).
- Each solver first runs `bluetoothctl remove <addr>` so BlueZ drops its cached
  GATT database (handles change between firmware builds).

| Solver | Notes |
|--------|-------|
| `ble01_read.py` | plain read; submits via the control service |
| `ble02_decode.py` | reverse bytes → base64 decode → hex decode |
| `ble03_notify.py` | subscribe, flag arrives as a notification (repeated every 1 s) |
| `ble04_indicate.py` | subscribe for indications; fragments `i/n:xxxx`, next one sent only after the confirm |
| `ble05_unlock.py` | read the panel's User Description, write the word it names, read the hatch |
| `ble06_descriptor.py` | read the descriptor with a non-SIG UUID |
| `ble07_advert.py` | passive: manufacturer data (company 0x02E5) `n:part`, rotates every 2 s. BlueZ reports a changed payload only when the controller duplicate filter resets (~10 s), so the solver restarts short 1.5 s scans |
| `ble08_long.py` | full read (big MTU / long read) plus an explicit offset-200 read (ATT Read Blob) via BlueZ D-Bus |
| `ble09_pair.py` | resets the board to read `ble passkey: NNNNNN`, registers a KeyboardOnly BlueZ agent (dbus-fast) that returns it, pairs, reads, removes the bond. `--passkey N` skips the reset |
| `ble10_bruteforce.py` | 0000–9999, pauses 3 s after every 5 wrong tries, retries on ATT error 0x80; `--start N`. ~0.63 s per try (lockout-bound): worst case ~105 min, average ~53 min |
| `ble11_sequence.py` | reads the 5 bytes from the input characteristic, sends them as write commands 50 ms apart |

## GATT layout

UUID base `e532XXXX-c7f0-4e5b-9a1d-3c54460b1e00` (XXXX below). Every
characteristic has a User Description (0x2901) with the name shown.

Advertising: connectable, ADV = flags + complete name `ESP32-CTF-XXXX` (last two
bytes of the board MAC) + manufacturer data (company 0x02E5) `"<n>:<part n/3 of
the BLE-07 flag>"`, rotating every 2 s; scan response = challenge service UUID.
One connection at a time; advertising restarts on disconnect.

### CTF challenge service `0100`

| UUID | Name (user description) | Props | Behaviour |
|------|------|-------|-----------|
| `0101` | [BLE-01] Welcome Note | read | flag |
| `0102` | [BLE-02] Scrambled Transmission | read | reverse(base64(hex(flag))) |
| `0103` | [BLE-03] Beacon Pulse | notify | no read; flag notified on subscribe and every 1 s |
| `0104` | [BLE-04] Relay Station | indicate | fragments `i/5:xxxx`, next after each confirm |
| `0105` | [BLE-05] Airlock Panel: write UNSEAL-XXXXXXXX to open the hatch | write | per-board word unlocks `0115` (until disconnect) |
| `0115` | [BLE-05] Airlock Hatch | read | `SEALED`, flag once unlocked |
| `0106` | [BLE-06] Firmware Revision | read | boring value; descriptor `0166` holds the flag |
| `0108` | [BLE-08] Telemetry Dump | read | 235 bytes, flag at the end; long reads with offset |
| `0109` | [BLE-09] Secure Locker | read (encrypted + MITM) | flag; static per-board passkey, board is display-only, bonding allowed |
| `010a` | [BLE-10] Vault Keypad: 4-digit PIN, 5 wrong tries lock it for 3 s | read, write, notify | write 4 ASCII digits. Wrong: accepted (counted). 5th wrong starts a 3 s lockout: writes fail with ATT error 0x80 (0x81 = not 4 digits). Correct: flag notified, read returns it (until disconnect); otherwise read = `LOCKED n tries left` / `LOCKOUT n ms`. Try counter and lockout are global |
| `010b` | [BLE-11] Sequencer Input | read, write-without-response | read = the 5 bytes to send; only 1-byte write commands count, each < 500 ms after the previous; a write request is refused (0x03) and resets |
| `011b` | [BLE-11] Sequencer Output | notify | flag notified when the sequence completes |
| `01c2` | Cipher Shard | read | `cipher shard 2/4: XY` (CRY-01) |

### CTF control service `0200`

| UUID | Name | Props | Behaviour |
|------|------|-------|-----------|
| `0201` | CTF Submit Flag | write, write-without-response | any challenge's flag (`ESP{…}` or bare body) |
| `0202` | CTF Submit Result | read, notify | `Correct! <id> +<pts>` / `Already solved` / `Wrong flag` |
| `0203` | CTF Score | read, notify | `score/max`, refreshed every 1 s (also after console/web submissions) |
