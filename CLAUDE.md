# ESP32 CTF

Stack: ESP-IDF v6.1 (C11), target `esp32` (classic, Bluedroid dual-mode), Python 3 solvers.

## Commands

- Env (every shell): `. ~/esp/esp-idf/export.sh`
- Build: `idf.py build`
- Flash + monitor: `idf.py -p /dev/ttyACM0 flash monitor` (dev board on CH9102 bridge; BT adapter: TP-Link UB500 via BlueZ)
- Host tests (ctf_core): `cmake -S test/host -B build-host && cmake --build build-host && ctest --test-dir build-host --output-on-failure`

## Conventions

- `components/ctf_core` is portable C: never include IDF/FreeRTOS headers there; it must build in `test/host`.
- Never store a plaintext flag or derived secret as a literal; derive at runtime via ctf_core (SPEC "Flags"). Only RE-track provisioning writes flags to flash, on purpose.
- Challenge IDs are exactly as in SPEC (`BLE-01`, `WEB-06`, …); one solver per challenge in `solvers/<track>/`.
- Every challenge targets the board only. Nothing scans, connects to, or affects other networks or devices.
- Radio features belong to a mode (`radio` or `net`); do not start Wi-Fi in radio mode or Bluetooth in net mode.
- Update `filemap.md` when adding or moving files.
- Dev STA images (`build-dev`, `sdkconfig.dev.local`) embed the user's Wi-Fi password: never print that file, and after testing `erase-flash` + flash the release bin.

## Docs

- Spec: `docs/SPEC.md` · Plan/status: `docs/PLAN.md` · Navigation: `filemap.md`
