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

## 12. [x] Hardware acceptance — orchestrator + user — deps: all
Run every solver against a real board; check two boards give different flags;
check RAM headroom in both modes (`heap_caps` log at boot).

Parallelism after 3: tasks 4, 5, 6, 7, 9 can run in parallel (separate components).

### Task 12 status
- Done on hardware: SER-01,03,04 · CRY-01..03 · RE-01..04 · BLE-01..11 · BTC-01..03 · HW-02,03 (dev build) · WEB-01..09 (dev STA over LAN, 2026-10-18) · HW-06 (human taps) · HW-03/04/05 + SER-02 (fx2lafw logic analyzer, real capture) · HW-01 (jumper, 2026-10-18).
- Per-board flags verified 2026-10-18: second board (ESP32-D0WD rev 1.0) runs v0.1.0; its SER-01 flag is rejected by board 1 and accepted by board 2.

# v0.2.0: player app (SPEC "v0.2.0")

## 13. [x] Wallet, hint tiers, machine channel — Careful — deps: none
ctf_core: points model, record v2, 3 hint texts per challenge (existing hint
moves to tier 2, tiers 1/3 placeholders), prices. ctf_platform: `status`,
`hint` tiers, SOH machine channel and `api` commands. Host tests + hardware.

## 14. [ ] Hint and primer content — Careful — deps: 13 (hints), none (primers)
Write tiers 1–3 for all 40 challenges into `ctf_catalog.c` and the 7 primers
in `web/app/content/primers/`. Verified against SPEC + solvers for accuracy.

## 15. [ ] Player app — Careful — deps: none (builds against SPEC + demo board)
`web/app/` per mockup, Web Serial client, demo board, content build script.

## 16. [ ] Integration on hardware — orchestrator + user — deps: 13, 14, 15
App against a real board in Chrome; protocol test script in `solvers/common/`.

## 17. [ ] Docs, screenshots, release v0.2.0 — Medium — deps: 16
README (app section + screenshot), players docs (points/hints), development.md,
console screenshot re-render, landing page link, release.sh, tag + GitHub release.
