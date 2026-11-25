# Defuse32 firmware

ESP-IDF v6.1 firmware for the Defuse32 training case, target `esp32` (classic). The specs are [`../FIRMWARE.md`](../FIRMWARE.md) (behaviour and packs) and [`../SPEC.md`](../SPEC.md) (pins, which win over anything here).

Status (v0): board drivers (SPEC rev 1b pin map, rev 2 LIS3DH tilt sensor), pack loader, game engine, module adapters with the simple v0 challenges, game task and game-master console. A full round can be played from the serial console alone, with no plate hardware attached. Nothing has run on hardware yet (see "Tested vs untested").

## Build

```sh
. ~/esp/esp-idf/export.sh
cd hardware/defuse32/firmware
idf.py set-target esp32     # first time only
idf.py build
idf.py -p /dev/ttyACM0 flash monitor   # console: UART0, 115200
```

The build only pulls in what `main` requires (`set(COMPONENTS main)` in `CMakeLists.txt`): `main` requires `d32_board`, `d32_pack`, `d32_engine` (which brings `ctf_core`) and `d32_modules`. Managed components (`espressif/led_strip` 3.0.3, `espressif/cjson` 1.7.19~2) are pinned in each component's `idf_component.yml` and recorded in `dependencies.lock`. `build/`, `managed_components/` and `sdkconfig` are git-ignored.

Board options live under `menuconfig` → *Defuse32 board*: I2C speed (100 kHz by default), key switch and SD DET polarity, SH1106 column offset, touch threshold, servo open/closed angles. Game options under *Defuse32 game*: tilt threshold (`CONFIG_D32_TILT_DEG`, 30° by default).

## Layout

```
CMakeLists.txt        project; EXTRA_COMPONENT_DIRS = ../../../components/ctf_core + ./components
sdkconfig.defaults    esp32, 4 MB, single-app-large partition table (packs live on SD), UART0 115200, FATFS long names
main/                 app_main (board init, banner, SD, boot pack, game task, console)
  game.c/.h           game task: engine tick, inputs, UI, round API for the console
  console_cmds.c      console commands
  Kconfig.projbuild   "Defuse32 game" options (tilt threshold)
components/d32_board/   pin map (board.h) and drivers
components/d32_pack/    pack parser + SD loader
components/d32_engine/  portable game engine (see its README)
components/d32_modules/ module adapters, one file per plate, + registry and pure logic
test/host/              host tests: engine, d32_mod_logic, tilt math, pack parser
```

## Boot sequence

1. `board_init()` brings up every driver. A missing device is logged once and its driver returns `ESP_ERR_INVALID_STATE` after that. Nothing blocks and nothing aborts.
2. Banner: firmware name and version, chip revision, MAC, then the device presence table.
3. microSD: mounted at `/sd` when DET says a card is inserted. If DET cannot be read (U2 missing), the mount is tried anyway.
4. Boot pack: `/sd/packs/default.json` if it exists, otherwise the first pack in alphabetical order, otherwise the built-in default.
5. The card is unmounted again (SPI bus freed, SD CS parked high) so the probe plate's SPI header is quiet during play. `pack list` / `pack load` mount it for the moment they need it, and refuse while a round runs.
6. Game task (`game_init()`: `ctf_init()` with the chip MAC and a RAM backend, engine and adapters configured from the boot pack; then `game_start()`), then the `esp_console` REPL (`d32> `).

## d32_board

`board.h` holds every GPIO, I2C address and MCP23017 pin from SPEC rev 1b (plus the rev 2 LIS3DH at 0x19) as named constants, plus `board_init()`/`board_deinit()` and the presence table. It includes all the driver headers.

| Driver | File | Notes |
|---|---|---|
| I2C bus | `board_i2c.c` | New `i2c_master` driver, I2C0 on 21/22, 20 ms timeout per transaction, `board_i2c_scan()`. Before creating the bus it checks that SDA and SCL idle high. The pull-ups are on 3V3P, so with only DevKit USB power the bus is reported down instead of timing out on every call. The internal pull-ups stay off so they do not back-feed 3V3P. |
| MCP23017 ×2 | `board_mcp.c` | U2 0x20 and U3 0x21 set up per SPEC rev 1b. IOCON MIRROR + ODR drive the INT line on GPIO35 (negative edge, semaphore); init runs in two passes, IOCON on both expanders first and everything else after, so the wired-together INT pins are open-drain before either expander can signal; interrupt-on-change is enabled on every input. GPA7 and GPB7 are output-only spares: never inputs, never strobes (`board_mcp_port()` masks them). Register access is shadowed and protected by a lock. |
| Keypad | `board_input.c` | Columns COL1-3 = U2 GPA4-6 and COL4 = U2 GPB6 strobe, rows GPA0-3 are read. During a scan one column is driven low and the other three are inputs (high impedance); between scans all four are driven low together. The 0-F overlay map is `1 2 3 A / 4 5 6 B / 7 8 9 C / 0 F E D`. |
| Wire matrix | `board_input.c` | Strobes WA1-5 = U3 GPA0-4 and WA6 = U3 GPB6 the same way (one driven, the rest inputs), reads WB1-6 = GPB0-5, and reports a bitmask of B posts for each A post. |
| Encoder, Simon, key switch, SD DET | `board_input.c` | Polled over I2C. The encoder A/B are U3 GPA6/GPA5 (quadrature table, 4 steps per detent on a KY-040); its switch is GPIO39 (rev 1b, 10 k pull-up on 3V3P, read as "not pressed" while the I2C bus / 3V3P rail is down). |
| TM1637 | `board_tm1637.c` | Bit-banged open drain on 32/33. Presence comes from the ACK bit. Covers digits, hex, colon and brightness. |
| OLED | `board_oled.c`, `board_font5x7.c` | SSD1306 at 0x3C and SH1106 at 0x3D (column offset 2). 128×64 framebuffer, 5×7 font in 8 lines × 21 columns, inverse lines, hardware invert, contrast. A flush sends only the pages that changed. |
| WS2812 ×15 | `board_leds.c` | `espressif/led_strip` RMT driver on GPIO25. LED names follow the SPEC chain order. Global brightness scale defaults to 64/255. |
| Buzzer, servo | `board_pwm.c` | LEDC. The buzzer plays a tone for a set time without blocking (an `esp_timer` stops it). The servo runs at 50 Hz over 0-180° (500-2500 µs) and sends no pulses until the first command. |
| Touch | `board_touch.c` | `driver/touch_sens.h` (touch V1) on T0/T4/T6/T3 with the software filter. Baselines are averaged at init. A pad counts as touched when its reading drops 15 % below baseline. |
| IR | `board_ir.c` | RMT RX on GPIO34 at 1 µs resolution. A background task decodes NEC frames (8-bit or extended 16-bit address, repeat codes) into a queue. |
| LDR | `board_ldr.c` | `adc_oneshot` on ADC1_CH0 (GPIO36), 12 dB attenuation, line-fitting calibration when the eFuse has it. |
| LIS3DH (rev 2) | `board_lis3dh.c`, `board_tilt.c` | Replaces the rev 1b GY-521 / MPU-6050 (driver removed, no Kconfig choice). 0x19 (SA0 high), I2C mode (CS high), WHO_AM_I must read 0x33 or the device counts as missing. Normal mode, 50 Hz, ±2 g (4 mg per digit), BDU on, polled over I2C (INT1/INT2 not connected). Tilt is the angle between gravity now and a reference captured at init and again at each round start (`board_lis3dh_set_reference()`), plus pitch and roll. The math (raw to g, reference, angle) is portable in `board_tilt.c` and host-tested. |
| microSD | `board_sd.c` | SDSPI on SPI3 (VSPI, 18/23/19), CS GPIO2, 4 MHz (long unterminated bus shared with the probe plate; packs are small files), FATFS at `/sd`. It never formats the card. After a failed mount the bus is freed and CS parked, as after an unmount. While unmounted, CS is driven high (the carrier's pull-down would otherwise leave the card selected on the shared bus). |
| UART2 | `board_uart2.c` | TX17/RX16, 8N1, init/read/write helpers for the probe plate. |
| PN532 | `board_nfc.c` | **Stub**: presence probe at 0x24 only (see the TODO in `board_nfc.h`). |

The OLED framebuffers have no lock: give each display a single owner task.

## d32_pack

- `d32_pack_parse.c` is the parse core. It uses only portable C11 and cJSON, so it can build on the host. `d32_pack_parse(json, len, &pack, warn_fn, ctx)` fills a plain `d32_pack_t` with the format, id/title/version, round minutes (1-180), max_strikes (1-9), strike_rate (1.0-4.0) and training, plus `enabled` and `variant` for each of the six slots. A missing or invalid value keeps its default and raises one warning. Unknown keys are ignored. The function returns the warning count, or -1 when the text is not a JSON object. `d32_pack_defaults()` returns the built-in pack, which matches the example in FIRMWARE.md (45 min, 3 strikes, ×1.25).
- `d32_pack.c` is the loader. `d32_pack_list("/sd/packs", names, max)` lists the packs in sorted order. `d32_pack_load(name, &pack)` reads `/sd/packs/<name>.json` (8 KB max, name `[A-Za-z0-9_-]{1,31}`); the name `builtin` returns the compiled-in default. `d32_pack_current()` and `d32_pack_select()` get and set the active pack.

## Console

| Command | What it does |
|---|---|
| `hw scan` | I2C scan with names for the known addresses, then the presence table |
| `led test` | Walks red, green and blue through each of the 15 LEDs (names printed), then all white, then off |
| `buzz [hz] [ms]` | Plays a tone, 2000 Hz for 200 ms by default |
| `servo open\|close\|<deg>` | Moves the prize-hatch servo |
| `keys` | Prints keypad presses for 10 s |
| `wires` | Prints the patch matrix (`WA1 -> WB3`) |
| `touch` | Prints the value, baseline and touched state of each pad |
| `ir` | Prints decoded NEC codes for 10 s |
| `tilt` | Prints acceleration, tilt from the reference, pitch and roll |
| `pack list` / `pack load <name>` / `pack show` | Lists packs, loads and selects one (used from the next round start), or shows the current one. Mounts the card only for the command; refused while a round runs |
| `status` | Round phase, time left, clock rate, strikes, each module's state and variant, revealed fragments |
| `round start [minutes]` | Arms a round (seed `esp_random()`), settings from the current pack; `minutes` (1-99) overrides the length. A won or lost round is reset first |
| `round reset` | Back to idle from any phase (closes the hatch if it was opened) |
| `round codes` | **Game master only**: every enabled module's code, the target wire, and the adapter extras (patch pattern, touch order, service PIN, Morse). Never show this to players |
| `code <hex6>` | Submits a code exactly like the keypad (spaces allowed, case ignored) |
| `wire <0-5>` | Pulls a wire: 0 RED, 1 BLUE, 2 YELLOW, 3 GREEN, 4 WHITE, 5 BLACK |
| `strike` | Adds a strike (game master) |

All round commands work with no plate hardware attached.

## Playing a round from the console only

No plate is needed; the carrier (or a bare DevKit) and the serial console are enough.

```
d32> round start 10        # 10-minute round; omit the number for the pack's length
d32> round codes           # game master: codes of M1..M6 + target wire
d32> code 1A2B3C           # one code per enabled module; each disarm logs its fragments
...                        # after the last one: "phase: final"
d32> status                # fragments collected so far, e.g. "1:B 2:L 3:U 4:E"
d32> wire 1                # pull the target wire (index from `round codes`): round won
d32> round reset
```

To lose: `strike` until `max_strikes`, a wrong code, `wire` with the wrong index in FINAL, or let the time run out. A `wire` before FINAL is a strike.

## Game task (`main/game.c`)

- One FreeRTOS task, 10 ms period. Each tick it takes the engine lock, calls `d32_tick()` with the real elapsed time, polls the key switch (every 50 ms) and the tilt (every 100 ms), runs every adapter's poll, drains `d32_poll_event()` into the UI and the adapters, and refreshes the LEDs and the TM1637 every 50 ms. Console commands take the same lock.
- Key switch (U2 GPB4): a turn to ARM (two equal reads 50 ms apart) starts a round like `round start`; a key already in ARM at boot does nothing until it is turned. Turning it back does nothing.
- Tilt: while a round runs, a tilt above `CONFIG_D32_TILT_DEG` from the orientation at arming calls `d32_tilt()` (the engine strikes at most once per 5 s).
- UI: TM1637 `----` when idle, MM:SS while running with the colon blinking once per second, frozen at the end. Module status LEDs: armed red, disarmed green, idle dim, disabled off; all green when won, all red when lost. Strike LEDs: one red per strike (first three). Buzzer: short tick each second, cues on arm, disarm, strike, FINAL and the result. Servo: hatch opens on WON, closes on reset.
- `ctf_init()` gets the chip MAC (`esp_read_mac(..., ESP_MAC_WIFI_STA)`) and a RAM backend (`load` reports nothing stored, `save` drops the record): Defuse32 uses only ctf_core's key and `ctf_derive`, not its catalogue or scoring.

## d32_modules (v0 adapters)

One file per plate, each with `configure(variant)`, `arm(seed)`, `poll()`, `event()`, `reset()` and a game-master line for `round codes`; `d32_modules.c` is the registry and the buzzer arbiter (cues over the second tick over Morse). Every adapter reads its own code with `d32_code_for()`. All challenges are **v0**: simple, so the loop can be played end to end. Seed-derived values come from `ctf_derive()` on `D32:<SEED>:patch`, `:touch` and `:menu` (`d32_mod_logic.h`), so they are board specific and unknown without the round seed.

| Slot | File | Variant | v0 challenge | Code shown |
|---|---|---|---|---|
| M1 radio | `mod_radio.c` | any (`ble-read`) | **Placeholder**: no challenge yet (TODO in the file: BLE / Wi-Fi from the board itself) | console `round codes` only |
| M2 timer | `mod_timer.c` | `buzzer-morse` | The M2 code plays in Morse on the buzzer (700 Hz, 100 ms per unit, 1.4 s pause between repeats) between the second ticks; a tick or cue interrupts an element, which then resumes for its remaining time | by ear |
| M3 keypad | `mod_keypad.c` | `menu` | Code entry for every module (runs even when M3 is disabled). Its own code: hidden service menu, see below | keypad OLED |
| M4 wires | `mod_wires.c` | `patch-a` | Patch each A post to its B post from the seed-derived pattern (hint in the M5 banner). Matching for two scans shows the code. In FINAL a pulled lead calls `d32_wire_pulled()` (any variant, also with M4 disabled) | keypad OLED |
| M5 probe | `mod_probe.c` | `uart-<baud>` (`uart-115200`) | On arm, a boot-style banner on UART2 (GPIO17 TX, 8N1, the variant's baud) with the M5 code, the M4 patch hint and `svc: <base64 of the M3 service PIN>`; Enter on UART2 RX sends it again | UART2 |
| M6 sensors | `mod_sensors.c` | `touch-4` | Touch pads 1-4 (T0, T4, T6, T3) in the seed-derived order; the four Simon LEDs blink that order (LED n = pad n). A wrong pad restarts the sequence (no strike) | keypad OLED |

An unknown variant makes the adapter a placeholder (logged at round start); its code is then only visible with `round codes`.

Wires: each coloured lead stays in its A post, which fixes its colour: WA1 red, WA2 blue, WA3 yellow, WA4 green, WA5 white, WA6 black (the engine's wire index = A post − 1). Players move the B ends. In FINAL, unplugging either end of a lead (its A post reads unconnected for 200 ms) is the pull. An A post that is unconnected when FINAL starts cannot be pulled; use `wire <n>` on the console in that case.

### Keypad key map (0-F overlay)

```
1 2 3 A
4 5 6 B
7 8 9 C
0 F E D
```

All 16 keys are hex digits; there is no enter or delete key.

| Input | Action |
|---|---|
| any key, short press | types its digit (on release, or when the next key is pressed while it is still down) |
| 6th digit | submits the entry at once (`d32_submit_code()`), then the entry starts over |
| any key held 0.8 s | clears the entry (short low beep, OLED "CLEARED"); that key types nothing |
| no key for 10 s | a partial entry clears itself (OLED "ENTER CODE") |

Every key press beeps. The keypad OLED shows: line 0 the phase, strikes and disarmed count; line 1 `CODE ______`; lines 3-4 messages (results, revealed codes, strikes); lines 5-6 the fragments revealed so far; line 7 `HOLD A KEY TO CLEAR`.

Service menu (M3's own code): the service PIN is 6 hex chars typed like a code. The adapter compares the 6th-digit entry with it before calling the engine, so the PIN opens the menu (`SERVICE MENU`, `M3 CODE xxxxxx`) and is never a strike. Derivation: the first 3 bytes of `ctf_derive("D32:<SEED>:menu")` as 6 upper hex; if that equals any module code of the round, `ctf_derive("D32:<SEED>:menu:<n>")` with n = 1, 2, … until it is unique. Players find it in the M5 UART2 banner as `svc: <base64 of the 6 PIN chars>` (e.g. `svc: M0U5RDAx` = `3E9D01`); the game master sees it in `round codes`. Typed on the console with `code`, the PIN goes straight to the engine and counts as a wrong code.

## Host tests

```sh
cmake -S hardware/defuse32/firmware/test/host -B build-d32-host
cmake --build build-d32-host
ctest --test-dir build-d32-host --output-on-failure
```

Groups: `config phase timer codes wires frags events` (engine), `tilt` (`board_tilt.c`: LIS3DH raw to g including full scale and negatives, reference capture and rejection of free fall / zero / NaN, tilt angle against vertical and non-vertical references, pitch and roll), `modlogic` (`d32_mod_logic.c`: Morse, patch pattern, touch order, service PIN and its collision counter, base64, debounce, key hold / rolled typing, entry buffer with auto-submit and idle timeout, and typing the PIN and every code of a round on the keypad model) and `pack` (`d32_pack_parse.c`: valid, defaults, invalid values, unknown keys, broken JSON, names). The `pack` group needs cJSON: `-DD32_CJSON_DIR=<dir>`, else the copy in `managed_components/espressif__cjson/cJSON` (present after one `idf.py build` or `idf.py reconfigure`), else a system cJSON (`libcjson-dev`); without any of them the group is skipped with a CMake warning. cJSON is built as its own static library, without our `-Werror`.

## Tested vs untested

Verified: the project builds with no warnings from our code (`idf.py build`, ESP-IDF 6.1), and the host tests pass (engine, `d32_mod_logic`, tilt math, pack parser).

**Nothing has run on hardware yet**: no board was flashed, so neither the drivers nor the game task, the console round commands or the adapters have been exercised on a device. Check on the bench, in particular:

- A console-only round on a bare DevKit (`round start`, `round codes`, `code`, `wire`, `strike`, `status`), then with the carrier.
- Game task timing: the keypad scan (every 20 ms), wire scan (100 ms) and OLED refreshes share the 100 kHz I2C bus; a full OLED redraw takes about 100 ms and delays the next ticks (the clock stays right, it uses real elapsed time).
- MCP23017 rev 1b: register setup, the open-drain strobe emulation over both ports (COL4 and WA6 on GPB6), and the interrupt line on GPIO35.
- Encoder switch on GPIO39 (note the ESP32 GPIO36/39 glitch erratum only affects interrupts; the switch is polled).
- Keypad timings (0.8 s hold to clear, 10 s idle clear, rolled typing with the 40 ms debounce) and the OLED layout on the real SH1106.
- Morse readability on the passive buzzer with the second ticks, and the tick loudness over a 45-minute round.
- UART2 banner at 115200 with a USB-UART adapter (code, patch hint, `svc:` line); Enter to repeat.
- Wire pull detection in FINAL with real banana leads (200 ms debounce), and the patch match.
- Touch sequence detection and the Simon hint LED order.
- Key switch arming, tilt strikes with the threshold, servo hatch on WON.
- SD unmount after the boot pack (CS parked high) and on-demand mounting for `pack list/load`.
- Keypad row/column orientation, and the key map against the printed overlay.
- Wire matrix settle time with long banana leads (20 µs per strobe).
- Encoder direction and steps per detent. I2C polling can miss fast turns.
- Key switch and SD DET polarity (Kconfig options).
- TM1637 timing (5 µs per half bit) and colon position. If the module is powered from 5 V, its pull-ups pull CLK/DIO up to 5 V.
- SH1106 init sequence and column offset on the real 1.3" module. SSD1306 contrast.
- WS2812 colour order (GRB) through the 74AHCT125.
- Buzzer loudness at 50 % duty, and the servo pulse range and the open/closed angles on the real hatch.
- Touch thresholds (15 %) with the real pads and wire lengths.
- NEC timing tolerance (±25 % + 100 µs) with the receiver in the case.
- LIS3DH (rev 2): never run on a device. Check WHO_AM_I 0x33 at 0x19, the register setup (CTRL_REG1 0x47, CTRL_REG4 0x80), the auto-increment burst read of OUT_X_L..OUT_Z_H (0x28 | 0x80), the axis orientation on the carrier (pitch/roll signs) and that the 4 mg / 50 Hz noise stays well below the tilt threshold.
- LDR range, and microSD at 4 MHz on the shared bus (scope SCK at the card slot; raise the speed only if the edges are clean).
- PN532: presence only; the driver comes later.
