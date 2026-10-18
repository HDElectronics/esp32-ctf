# Defuse32 hardware spec (rev 0)

Concept: a carry case with six module plates; each plate hides CTF challenges. Concept page: https://claude.ai/artifact/JsBaCiMT16YdQso2KsTbZf (private to the owner).

Guiding rule: **reuse, don't design from scratch.** Off-the-shelf carry case, off-the-shelf breakout modules on the plates, one carrier PCB in the bottom of the case. No custom module PCBs in rev 0.

## Physical architecture

- **Case**: a commercial hard case (chosen in `docs/parts.md`). We design only what goes inside: a flat **panel insert** resting on a ledge or standoffs near the top of the base, with 6 rectangular openings, and 6 **module plates** screwed onto the panel over those openings.
- **Module plates**: 3D-printed (PLA/PETG) or laser-cut 3 mm acrylic/plywood. Each plate carries off-the-shelf modules mounted from below (displays/keys showing through cut-outs) with M2/M2.5/M3 standoffs matching the modules' real mounting holes.
- **Carrier PCB**: on the case floor on standoffs. Off-the-shelf ESP32 DevKit plugs into female headers. Harness cables (JST-XH 2.5 mm) run up to each plate.
- **Front/side wall**: key switch (19 mm hole) and a panel-mount USB-C 5 V input (or a USB-C pass-through extension). Holes drilled into the case wall; the case itself is not modified otherwise.
- Prize drawer from the concept is **out of scope for rev 0**; the servo instead drives a small latch flap on the sensor plate (a "prize hatch"). Keep the servo header on the carrier.

## Rev 0 decisions (after `docs/parts.md`)

- **Case**: Pelican 1520 (1520NF) + **1520PF panel frame kit**. Numbers in `data/parts.json` → `case`. The CAD stays parametric so a cheaper case (Apache 4800) is a data change.
- **Panel**: 452 × 321 × 3 mm, R16.5 corners, 16 × Ø3.6 holes at the 1520PF insert positions, top flush with the rim (underside z = 122.2 from the floor). Laser-cut 3 mm acrylic or plywood (not metal: it would shield the DevKit antenna and the PN532).
- **Plate grid** (panel coordinates, origin at the panel centre, +y toward the lid hinge, top view): plates 134 × 138 × 3 mm, gap 4 mm, 3 columns × 2 rows → overall 410 × 280, centred. Column centres x = −138, 0, +138; row centres y = +71 (back), −71 (front). Back row left→right: M1 Radio, M2 Timer, M3 Keypad. Front row: M4 Wires, M5 Probe, M6 Sensors.
- **Panel openings** under each plate: 114 × 118, centred on the plate (all inside the frame's 422.6 × 291.2 clear opening). Each plate is held by 4 × M3 at 6 mm from its corners into the panel (panel holes Ø3.4, M3 nuts below or heat-set inserts in printed plates).
- **Height cap**: nothing more than 35 mm above a plate top (lid clearance). No external antenna; the DevKit's PCB antenna is used. Banana leads are unplugged and stored in the lid to close it.
- **Keypad**: common hard-key 4×4 (phone legends) + printed 0–F overlay.
- **Carrier PCB**: 190 × 140 mm, 1.6 mm, 4 × Ø3.2 mounting holes 5 mm from the corners, on M3 × 8 standoffs on a 3 mm floor sled (z: sled 0–3, PCB 11–12.6), centred on the floor, DevKit USB edge facing the case's right wall. Plate connectors J1–J3 on the back edge, J4–J6 on the front edge, in plate order left→right.
- **DevKit footprint**: 2 × 1×19 sockets at 25.40 mm (genuine DevKitC) plus an unpopulated third 1×19 row at 22.86 mm from row 1 for narrow clones, same nets.

## Electronics (carrier PCB)

THT-only, 2-layer, hand-solderable. Everything 3.3 V logic except the WS2812 chain, servo and buzzer (5 V).

| Ref | Part | Notes |
|-----|------|-------|
| U1 | ESP32-DevKitC-32E style board, 38 pin | Plugs into 2× 1×19 female headers. Row spacing per `docs/parts.md` (verify: 25.4 mm on DevKitC V4). |
| U2, U3 | MCP23017-E/SP (DIP-28) | I2C expanders, addresses 0x20 (U2) and 0x21 (U3). INTA/INTB mirrored, open-drain, wired-OR to GPIO35. |
| U4 | 74AHCT125 (DIP-14) | 3.3 → 5 V buffer for WS2812 data (one gate used, others tied off). |
| Q1 | 2N3904 | Low-side driver for the 5 V passive buzzer, 1 kΩ base, 1N4148 across buzzer. |
| D1 | SS34 / 1N5822 Schottky | 5 V rail → DevKit 5V pin, so USB on the DevKit can't back-feed the rail. |
| C | 470 µF/10 V bulk on 5 V near servo + LED connectors; 100 nF per IC; 10 µF on 3V3 | |
| R | I2C pull-ups 4.7 kΩ to 3V3 (SDA, SCL); 10 kΩ pull-ups on GPIO35, GPIO34; 10 kΩ GPIO36→GND (LDR divider, LDR on the plate goes 3V3→GPIO36); 330 Ω in series with WS2812 data out | |
| A1 | GY-521 MPU-6050 module | Female 1×8 header on the carrier (tilt anti-tamper sits on the carrier, not a plate). |
| J_PWR | 2-pin screw terminal, 5 V in | From the panel-mount USB-C 5 V module. |

### ESP32 pin map (fixed — do not change without updating this file)

| GPIO | Function | Notes |
|------|----------|-------|
| 21 / 22 | I2C SDA / SCL | Carrier bus to MCPs, MPU-6050 and every plate connector |
| 35 | MCP23017 INT (wired-OR, open-drain) | input-only, 10 k pull-up |
| 39 | MPU-6050 INT | input-only |
| 34 | IR receiver out | input-only, 10 k pull-up |
| 36 (VP) | LDR divider | ADC1_CH0 |
| 32 / 33 | TM1637 CLK / DIO | timer plate |
| 25 | WS2812 data (via U4) | one chain through all plates |
| 26 | Buzzer (via Q1) | LEDC PWM |
| 27 | Servo signal | 5 V servo header |
| 4 / 13 / 14 / 15 | Touch pads T0 / T4 / T6 / T3 | bare wires to copper pads on the sensor plate |
| 18 / 23 / 19 / 5 | SPI SCK / MOSI / MISO / CS | exposed SPI flash (W25Q32) on the probe plate |
| 17 / 16 | UART2 TX / RX | exposed header on the probe plate |
| 2, 12 | unused | strapping; leave unconnected |
| 0, 1, 3, 6–11 | reserved | boot / USB console / flash |

MCP23017 U2 (0x20): GPA0–3 keypad rows, GPA4–7 keypad columns, GPB0–3 Simon buttons, GPB4 key switch, GPB5–7 spare (to a 3-pin spare header).
MCP23017 U3 (0x21): GPA0–4 + GPA7 wire posts "A" WA1–5, WA6 (outputs), GPB0–5 wire posts "B" (inputs), GPA6/GPA5/GPB6 encoder A/B/SW, GPB7 spare. GPA7/GPB7 are **output-only** on current MCP23017 silicon, so they only carry outputs (WA6) or spares; U2 GPB7 (SPARE3) is output-only too.

WS2812 chain order (15 LEDs): radio link LEDs (2) → radio status → timer strikes (3) → timer status → keypad status → wires status → probe status → sensor Simon (4) → sensor status. The chain enters each plate on LDI and leaves on LDO.

### Plate connectors (JST-XH 2.5 mm on the carrier; harness to the plate)

Every plate gets the **common** connector `Jn_A` (7 pin): `5V, 3V3, GND, SDA, SCL, LDI, LDO`. Module-specific lines go on `Jn_B`:

| Plate | Jn_B pins |
|-------|-----------|
| M1 Radio | ENC_A, ENC_B, ENC_SW (3) |
| M2 Timer | TM_CLK, TM_DIO, BUZZ− (buzzer low side), BUZZ+ (5 V) (4) |
| M3 Keypad | ROW1–4, COL1–4 (8) |
| M4 Wires | WA1–6, WB1–6 (12) |
| M5 Probe | U2TX, U2RX, SCK, MOSI, MISO, CS (6) |
| M6 Sensors | T0, T4, T6, T3, LDR, IR, SIM1–4, SERVO_SIG (11) |

Plus on the carrier: `J_KEY` (2: GPB4, GND), `J_SERVO` (3, SG90 plug order: GND, 5V, SIG; the M6 SERVO_SIG pin is the same net, use either), `J_SPARE` (U2 GPB5–7), `J_PWR`.

KiCad references: Jn_A → `Jn1`, Jn_B → `Jn2`, J_PWR = J7, J_KEY = J8, J_SERVO = J9, J_SPARE = J10 (the SPEC name is in each Value and on the silkscreen).

### Off-the-shelf modules on the plates

| Plate | Modules |
|-------|---------|
| M1 Radio | SSD1306 0.96" I2C OLED (0x3C), KY-040 rotary encoder, 2 WS2812 (or a 2-LED strip piece), antenna lead from the DevKit (U.FL variant optional) |
| M2 Timer | TM1637 0.56" 4-digit module, 3 WS2812 strike LEDs, 12 mm passive buzzer |
| M3 Keypad | 4×4 keypad (hard-key PCB type) **mounted on top of the plate** (its 61 mm hole pattern is too close to its 60 mm key field to mount from below), header through a slot; printed 0–F overlay; SH1106 1.3" I2C OLED (0x3D) |
| M4 Wires | 12 × 4 mm banana binding posts, 6 coloured banana leads |
| M5 Probe | 2.54 mm headers (UART, I2C, SPI), DIP-8 socket with 24C32 EEPROM (on I2C, 0x50), W25Q32 on a SOIC-8 breakout, test-point loops |
| M6 Sensors | 4 copper tape/PCB pads, GL5528 LDR, VS1838B IR receiver, PN532 V3 NFC module (I2C, 0x24), 4 × 12 mm tactile buttons with WS2812 under translucent caps, SG90 servo latch |

## Deliverables (in this folder)

```
hardware/defuse32/
  SPEC.md                 this file
  README.md               how to open/regenerate, renders
  docs/parts.md           chosen case + module dimensions with sources
  data/parts.json         same numbers, machine readable (used by the FreeCAD scripts)
  kicad/                  KiCad 10 project: defuse32-carrier.kicad_pro/.kicad_sch/.kicad_pcb, local lib
  cad/                    FreeCAD scripts (*.py, run with `freecad.cmd`), generated .FCStd/.step/.stl
  renders/                PNGs from KiCad and FreeCAD
```

Tools on this machine: KiCad 10.0.7 (`kicad-cli`, official libs in /usr/share/kicad), FreeCAD 1.1.1 (snap: `freecad.cmd script.py` runs headless). The FreeCAD MCP/GUI bridge is not running; use scripts.
