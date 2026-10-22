# Defuse32 firmware spec (v0)

Game engine + drivers for the Defuse32 training case. ESP-IDF v6.1, target `esp32` (classic). Hardware and pin map: `SPEC.md` (authoritative for pins). Reuses `components/ctf_core` from the repo root for key handling and HMAC derivation; does **not** use `ctf_platform` or the `track_*` components.

## Layout

```
hardware/defuse32/firmware/
  CMakeLists.txt          ESP-IDF project; EXTRA_COMPONENT_DIRS = ../../../components/ctf_core
  sdkconfig.defaults
  main/                   app_main: init board, load pack, start game task + console
  components/
    d32_engine/           portable C game engine (no IDF/FreeRTOS headers; builds on the host)
    d32_board/            pins, I2C bus, drivers (MCP23017, TM1637, OLED, WS2812, buzzer, servo, touch, IR, MPU-6050, SD), presence scan
    d32_pack/             pack loader (JSON on /sd/packs or built-in default)
    d32_modules/          module adapters: glue between engine and drivers, one file per plate
  test/host/              CMake + ctest for d32_engine and d32_pack parsing (links ctf_core)
```

## Game rules the engine implements

Words: a **round** is one game. Modules are **armed** until **disarmed**. The round ends **won** (correct wire pulled) or **lost** (time up, too many strikes, wrong wire). Use these words in code, logs and UI; this is a training game, keep wording neutral.

- **Phases**: `IDLE` → `ARMED` (timer running) → `FINAL` (all enabled modules disarmed, timer still running) → `WON` | `LOST`. `reset` returns to `IDLE` from any phase. A `TRAINING` flag disables the timer and strikes.
- **Timer**: duration from the pack (default 45 min). Deterministic `tick(dt_ms)`; each strike multiplies the clock rate by `strike_rate` (default 1.25, compounding). Time left is reported in ms and as MM:SS.
- **Strikes**: wrong code, a wire pulled before `FINAL`, or a tilt event (rate-limited: max one per 5 s). `max_strikes` from the pack (default 3); reaching it → `LOST`.
- **Codes**: at `arm` the engine draws a 32-bit round seed (caller supplies it; firmware uses `esp_random`). Each enabled module's code = 6 uppercase hex chars = first 3 bytes of `ctf_derive("D32:<seed 8 hex>:<module id>:<variant>")`. `submit_code(text)` accepts 6 hex chars (case-insensitive, spaces ignored); a match disarms that module, otherwise a strike. Already-disarmed codes: no strike, report "already".
- **Final wire**: 6 wires with fixed colours `RED BLUE YELLOW GREEN WHITE BLACK` (index 0–5). The target wire index = `ctf_derive_u32("D32:<seed>:wire") % 6`. Its colour name is split into fragments `"<pos>:<letter>"` (1-based) distributed over the enabled modules deterministically from the seed (a module can carry 0, 1 or 2 letters so every letter is covered). Disarming a module reveals its fragments. In `FINAL`, `wire_pulled(i)`: target → `WON`, other → `LOST`.
- **Events**: the engine queues events for the UI (phase change, module disarmed + fragments, strike + new rate, code rejected, second tick, round result). Poll API, no callbacks into IDF.
- **Score**: time left at `WON` (ms) and strikes used.
- Module slots: up to 6, ids `M1`…`M6` (`radio timer keypad wires probe sensors`), each `enabled` and a `variant` string from the pack.

## Packs

A pack is a JSON file (`/sd/packs/<name>.json`; a built-in default pack is compiled in). Packs hold **no flags or codes**; codes are derived on the box from its key + round seed, so reading the SD card gives nothing away.

```json
{ "format": 1, "id": "base", "title": "Base pack", "version": "0.1.0",
  "round": { "minutes": 45, "max_strikes": 3, "strike_rate": 1.25, "training": false },
  "modules": {
    "M1": { "enabled": true, "variant": "ble-read" },
    "M2": { "enabled": true, "variant": "buzzer-morse" },
    "M3": { "enabled": true, "variant": "menu" },
    "M4": { "enabled": true, "variant": "patch-a" },
    "M5": { "enabled": true, "variant": "uart-115200" },
    "M6": { "enabled": true, "variant": "touch-4" } } }
```

Unknown keys are ignored; invalid values fall back to defaults with a logged warning.

## Firmware behaviour (v0)

- Boot: init board, scan I2C and report which devices answered; missing devices are logged once and their module runs degraded (never crash or block).
- Key switch (U2 GPB4) turned to ARM starts a round; console `round start` does the same.
- UI: timer on the TM1637 (blinking colon while running), strike and status LEDs on the WS2812 chain (armed red, disarmed green, idle dim), keypad OLED shows code entry and results, buzzer beeps on key press / strike / disarm / result, servo opens the prize hatch on `WON`.
- Console (UART0, game master): `status`, `round start [minutes]`, `round reset`, `code <hex6>`, `wire <0-5>`, `strike`, `pack list`, `pack load <name>`, `hw scan`, `led test`, `buzz`, `servo open|close`, and a debug `round codes` that prints the current codes (game master only; document it as such).
- Keypad entry: all 16 keys (0–F) are digits. A code submits itself on the 6th key; holding any key for 800 ms clears the entry; an entry clears after 10 s idle. The M3 service menu opens with a 6-char service PIN (seed-derived, never equal to a module code, never a strike), hinted as `svc: <base64>` in the M5 UART2 banner.
- v0 module challenges are simple, so the loop can be played end to end: M3 keypad code entry, M4 wire patching, M5 UART boot banner on UART2 that reveals its code, M2 Morse on the buzzer, M6 touch-pad sequence, M1 BLE/Wi-Fi to come later (a console-revealed placeholder code in v0). Each adapter is one file so packs can add variants later.
