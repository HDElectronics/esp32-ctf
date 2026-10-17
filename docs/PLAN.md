# Plan

Status legend: [ ] todo · [~] in progress · [x] accepted.
Each task references docs/SPEC.md. Workers update `filemap.md` when adding files.

## 1. [x] Scaffold — Medium — deps: none
ESP-IDF v6.1 project for target `esp32`: top-level CMakeLists, `main/`, empty
component dirs per SPEC Architecture (each builds as an empty component),
`sdkconfig.defaults` (Bluedroid dual-mode BLE + Classic + SPP, Wi-Fi/BT coexistence,
4 MB flash, custom partition table, console on UART0 115200), `partitions.csv`
per SPEC Partitions, `idf_component.yml` with `espressif/mdns`. `test/host/`
CMake project that will build `components/ctf_core` sources on Linux with a
minimal test runner (one placeholder passing test). Root `.gitignore`.
**Verify:** `idf.py set-target esp32 && idf.py build` succeeds; host tests build
and pass; app size fits the factory partition with Bluedroid + Wi-Fi linked in
(add a stub that references both stacks if needed to measure).

## 2. [x] Core engine — Careful — deps: 1
`components/ctf_core`, portable C, no IDF headers: SHA-256 + HMAC-SHA256,
flag derivation and derived values (SPEC Flags), challenge registry (id, track,
level, points, hint, optional answer validator), submission normalisation and
check, scoring, hint cost, progress record with HMAC tag, storage backend interface.
**Verify:** host tests: RFC 4231 HMAC vectors, flag derivation determinism and
MAC sensitivity, submit accepts wrapped/bare/any case and rejects others,
double-solve and hint-cost scoring, tampered progress record rejected.

## 3. [x] Platform + console + boot — Medium — deps: 2
`components/ctf_platform` + `main/`: NVS backend, MAC read, mode load/save,
`esp_console` REPL with core commands (`help status submit answer hint mode
reset`), track registration hooks, boot sequence per mode, SER-01 boot banner.
**Verify:** build; on hardware: banner + SER-01 flag visible, `status`, `mode net`
reboots into net mode and back.

## 4. [x] Serial + crypto tracks — Medium — deps: 3
`track_serial` SER-02..04, `track_crypto` CRY-01..03 per SPEC.
**Verify:** build; solvers in `solvers/serial/`, `solvers/crypto/` (CRY ones also
unit-testable on host against reference logic); hardware run.

## 5. [x] Hardware track — Medium — deps: 3
`track_hw` HW-01..06 per SPEC pin map.
**Verify:** build; solvers/notes in `solvers/hw/`; hardware run (logic analyzer
for HW-03..05 if available, otherwise scope the bit timing in code review).

## 6. [x] RE track — Careful — deps: 3
`track_re` RE-01..04: first-boot provisioning (notes partition, NVS vault,
SPIFFS blob), crackme transform + `unlock` command.
**Verify:** build; solvers in `solvers/re/` that work from a flash dump file
(`esptool.py read_flash`); hardware run.

## 7. [x] BLE track + control service — Careful — deps: 3
`track_ble`: BT controller + Bluedroid init (dual mode, shared with task 8),
GATT server for BLE-01..11, advertising rotation, pairing/passkey, CTF control
service (submit + score notify).
**Verify:** build; `solvers/ble/` with `bleak`; hardware run with nRF Connect or bleak.

## 8. [x] BT Classic track — Medium — deps: 7
`track_btc` BTC-01..03: SPP server, shell, device name / CoD / EIR.
**Verify:** build; `solvers/btc/`; hardware run (bluetoothctl + rfcomm).

## 9. [x] Web track core — Careful — deps: 3
`track_web` WEB-01..07 + `/score` `/submit`: hidden-SSID SoftAP, HTTP server,
cookie/header/JWT logic, confined traversal on SPIFFS, WebSocket.
**Verify:** build; `solvers/web/` with `requests`/`websockets`; hardware run.

## 10. [x] Web track network extras (merged into task 9) — Medium — deps: 9
WEB-08 mDNS service + second port, WEB-09 UDP knock → TCP 31337.
**Verify:** build; solvers; hardware run.

## 11. [x] Player docs + release — Medium — deps: 4–10
`docs/players/` per track + tool setup, README, release script producing merged
`.bin`, `web/flasher/` ESP Web Tools manifest and page. README and landing page
both carry the "Toolbox" section from SPEC "Player toolbox" (TUIs first, install
hints); verify each tool name and install command is current before writing it.
**Verify:** release script output flashes cleanly with `esptool.py write_flash 0x0`.

## 12. [~] Hardware acceptance — orchestrator + user — deps: all
Run every solver against a real board; check two boards give different flags;
check RAM headroom in both modes (`heap_caps` log at boot).

Parallelism after 3: tasks 4, 5, 6, 7, 9 can run in parallel (separate components).

### Task 12 status
- Done on hardware: SER-01,03,04 · CRY-01..03 · RE-01..04 · BLE-01..11 · BTC-01..03 · HW-02,03 (dev build) · WEB-01..09 (dev STA over LAN, 2026-10-18) · HW-06 (human taps, 2026-10-18).
- Pending (user): SER-02 (USB-UART), HW-01 (jumper), HW-04/05 (logic analyzer), second board for flag uniqueness.
