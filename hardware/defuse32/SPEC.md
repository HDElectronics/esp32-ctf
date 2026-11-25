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

## Rev 2 carrier (2026-10-23, approved by the owner) — supersedes the rev 1b board

Preview the owner approved: https://claude.ai/artifact/G4984uR9xEvDVbf2QLoGjv (private). Rev 1b stays in git history (local tag `carrier-rev1b`). Everything below overrides the rev 0/1/1b board text where they conflict; the **ESP32 GPIO pin map, MCP23017 allocation (rev 1b), WS2812 chain and I2C addresses stay the same**.

- **Board**: 100 × 70 mm, 2 layers, 1.6 mm, 4 × M3 (Ø3.2) holes 4 mm from the corners. SMD everywhere except the IDC box headers and the small 2.54 mm headers. JLCPCB assembles the SMD side; prefer JLCPCB Basic parts, Extended only where no Basic part fits.
- **ESP32**: ESP32-WROOM-32E (4 MB) soldered at the **left edge**, rotated so the antenna end points left and the whole antenna region lies **outside** the board outline (Espressif's recommended placement). No copper under or around the antenna. EN and BOOT tactile switches next to the module.
- **USB-C** (16-pin receptacle, right edge): only power input and programming port. VBUS → PTC fuse (≈1.5–2 A hold) → `5V`; CC1/CC2 5.1 kΩ to GND; USBLC6-2SC6 ESD on D+/D−; **CH340C** (no crystal) USB-UART on UART0 (GPIO1/3); classic two-NPN (MMBT3904) DTR/RTS auto-reset driving EN and GPIO0; EN RC 10 kΩ + 1 µF; GPIO0 10 kΩ pull-up. In the case, a panel-mount USB-C extension runs from this port to the case wall. Firmware caps WS2812 brightness to stay within a 5 V / 2 A budget.
- **Power**: `5V` bulk ≥ 220 µF; AMS1117-3.3 (SOT-223) `5V` → `3V3` for the ESP32 and CH340C (10 µF + 100 nF at the module's 3V3 pin); a second AMS1117-3.3 (SOT-223, 1 A, JLCPCB Basic; replaced the AP2112K at routing time) `5V` → `3V3P` for the plates, expanders, LIS3DH and microSD. microSD card detect (Hirose DM3AT, normally open, pull-up on SD_DET): **low = card present**.
- **Expanders**: MCP23017-E/SO (SOIC-28) ×2, same addresses and allocation; 100 nF at each VDD pin (≤ 3 mm).
- **Tilt sensor**: **LIS3DH** (LGA-16) on I2C at 0x19 (SA0 high), CS high (I2C mode), INT pins not connected (polled). Replaces the GY-521 / MPU-6050.
- **microSD**: push-push microSD socket on the board edge, SPI mode on SCK18/MOSI23/MISO19, SD_CS GPIO2 (10 kΩ pull-down kept), card detect → U2 GPB5, 10 kΩ pull-ups on DAT0/DAT1/DAT2 to 3V3P.
- **WS2812 buffer**: 74AHCT1G125 (SOT-23-5) at 5 V, 330 Ω series out. **Buzzer**: MMBT3904 low side, 1 kΩ base, 1N4148WS across the buzzer pins.
- **Plate connectors**: one keyed 2.54 mm IDC box header per plate, ribbon cable to the plate. Sizes: J1 M1 2×5, J2 M2 2×6, J3 M3 2×8, J4 M4 2×10, J5 M5 2×7, J6 M6 2×10. Pinout rule: pin 1 = 5V, pin 2 = GND, then 3V3P, SDA, SCL, LDI, LDO, then the plate's signals (same signal sets as the rev 1 Jn_B table), spare positions = GND. Back-row plates (J1–J3) on the top edge, J4–J5 on the bottom edge, J6 vertical on the right edge above the USB-C. Small headers: J_KEY 1×2, J_SERVO 1×3 (GND, 5V, SIG), J_SPARE 1×5 (outputs only + GND).
- **Placement** follows the approved preview (positions ±5 mm): module left, expanders in the middle, CH340C + USB-C bottom right, regulators near the USB path, microSD bottom right edge.

## Rev 3 carrier (2026-10-23, after the owner's review of rev 2.1) — 4 layers

Same schematic, netlist, pin map and placement as rev 2 (the schematic stays rev 2; the board is rev 3). Rev 2.1 (2 layers) stays in git history (commit 7412eb7).

- **Board**: 100 × 70 mm, **4 layers**, 1.6 mm on JLCPCB's standard **JLC04161H-7628** stack-up (1 oz outer, 0.5 oz inner; 0.21 mm prepreg L1-L2 / L3-L4, 1.065 mm core), no impedance control.
- **Stack-up option B**: L1 signals + power + GND pour, **L2 solid GND plane**, **L3 solid GND plane**, L4 signals + power + GND pour; no tracks on L2/L3. Chosen over "power planes on L3" because the three rails (5V, 3V3, 3V3P) run over the whole board and meet on adjacent pins of every box header, so L3 could not be split into areas without becoming a layer of power tracks cutting the plane under L4; on this stack-up L3 is 1.065 mm from L2, so a power plane there would add almost no plane capacitance either. Power stays as 0.6 mm tracks on L1/L4.
- **Design rules = JLCPCB 4-layer capabilities at standard price** (project rules + `.kicad_dru`, numbers and source in the pcb-layout-pro skill `references/jlcpcb.md`): vias 0.6/0.3 mm (signals, power) and 0.45/0.2 mm (GND fan-out and stitching), no 0.15 mm holes, PTH hole to track 0.28 mm, inner PTH hole to copper 0.3 mm, pad hole to pad hole 0.45 mm, copper to edge 0.3 mm, silkscreen text ≥ 1.0 mm / 0.15 mm.
- **Finish**: no 90° corners, jogs straightened, every outer-layer GND pour piece stitched to the planes (no floating copper), a GND via next to each layer change of USB, SPI and WS2812 data, reference designators 1.0 mm beside their parts on the top side only (none on the bottom), rows aligned; a part with no free spot beside it gets a callout (label + 0.15 mm leader), and the boxed-in R16-R19 row one range label ("R16-19"); header names as one line along each header ("J1  M1 RADIO").
- **3D models** for J7, SW1/SW2 and F1 from LCSC/EasyEDA (`kicad/gen/fetch_3d.py`, files git-ignored); BOM/CPL in the JLCPCB Tools plugin's format with its rotation corrections.

## Rev 3.1 carrier, schematic rev 2.1 (2026-11-25, standards pass) — supersedes rev 3 where they differ

A standards pass (independent audit, review, fix, final check; record in `kicad/README.md`, section "Standards pass (2026-11-25)") on the rev 3 board. Same placement, pin map, MCP23017 allocation, connector pinouts and stack-up as rev 3. No part moved.

- **Schematic rev 2.1** (four changes, approved by the owner):
  - **Buzzer driver**: Q1 is an SS8050 (LCSC C2150, SOT-23, same pads) instead of the MMBT3904, base resistor R7 330 Ω instead of 1 kΩ, so a 16-42 Ω magnetic buzzer is driven saturated. 1N4148WS stays across the buzzer pins; with a 16 Ω buzzer check that diode's temperature at bring-up (a 32 Ω or higher buzzer is preferred).
  - **R21**, 10 kΩ pull-down on the WS2812 buffer input (WS_DATA, GPIO25 → U4 pin 2): the LED data line is defined while the ESP32 is in reset.
  - **R22**, 10 kΩ pull-up to 3V3P on the microSD CMD line (MOSI), completing the pull-ups on DAT0/DAT1/DAT2. SD_CS keeps its pull-down on GPIO2 (boot strapping).
- **Board rev 3.1** (copper and silkscreen):
  - **5 V feed**: a wide track from the fuse F1 straight to both regulators (U5, U6) and the bulk capacitor; the loop round the board now only feeds the plate headers. Each AMS1117 tab sits in a copper area on its own output net (3V3 at U6, 3V3P at U5).
  - No copper and no via under the LIS3DH body. A GND via within 2 mm of each layer change of USB, SPI and WS2812 data.
  - Silkscreen: `EN` at SW1, `BOOT` at SW2, `G + S` at the servo header J9 (pin 1 GND, pin 2 5V, pin 3 signal), `OUT` at J10, `rev 3.1 2026-11`. Three board-only fiducials (FID1-FID3) for JLCPCB's Standard assembly.
  - Track finish: the jogs, tight corners and copper gaps that remain are listed with their reasons in `kicad/README.md`. (Rev 3's "9 jogs" was an undercount by the audit tool; the corrected tool and the true numbers are in the same section.)
- **Ordering**: JLCPCB **Standard** PCBA (the ESP32 module, the LIS3DH and the 220 µF capacitor are Standard-only parts), handling rails on the two 100 mm edges only (the antenna overhangs the left edge, the USB-C receptacle is flush with the right edge). Settings, the order remark and the placement-preview checklist: `kicad/out/jlcpcb/README.md`.
- **Use**: supply 5 V from a source rated 2 A or more; a 500 mA PC port may sag when the servo moves. Plate wiring rules that protect the carrier (power the IR receiver, encoder, TM1637 and OLEDs from 3V3P, never 5 V; series resistors in the touch, probe, keypad and wire-post leads on the plates) belong in the plate build notes.

## Rev 1 changes (2026-10-22)

- **Challenge packs on microSD**: a 3.3 V-only microSD breakout (no level shifter; e.g. Adafruit 4682 style: 3V, GND, CLK, SO, SI, CS, DET) on a 1×7 female socket on the carrier, on the existing VSPI bus (SCK 18, MOSI 23, MISO 19) with **SD_CS = GPIO2** and a 10 kΩ pull-down on GPIO2 (keeps the boot/download strapping valid). Card detect DET → MCP U2 GPB5 (was SPARE1). Avoid 5 V "catalex" modules: their level shifter does not release MISO and would fight the probe plate's W25Q32. The SD sits on the carrier, under the panel: only the game master reaches it.
- **Separate 3.3 V rail for peripherals**: U5 LD1117V33 (TO-220) from the 5 V rail → net `3V3P`, 10 µF in, 10 µF out (+100 nF). All plate `3V3` pins, U2/U3, the GY-521, the SD card and the I2C/INT pull-ups move to `3V3P`. The DevKit's own regulator only powers the ESP32. Modules run only when the 5 V input is connected (DevKit USB alone powers the ESP32, not the modules).
- **Ready for hand routing** (the owner routes the board): net classes `Power` (5V, 3V3P, GND: 0.8 mm track, 0.3 mm clearance) and `Default` (0.25 mm track, 0.2 mm clearance), vias 0.6/0.3 mm, JLCPCB 2-layer capabilities as design rules. Board stays unrouted.

## Electronics (carrier PCB)

THT-only, 2-layer, hand-solderable. Everything 3.3 V logic except the WS2812 chain, servo and buzzer (5 V).

| Ref | Part | Notes |
|-----|------|-------|
| U1 | ESP32-DevKitC-32E style board, 38 pin | Plugs into 2× 1×19 female headers. Row spacing per `docs/parts.md` (verify: 25.4 mm on DevKitC V4). |
| U2, U3 | MCP23017-E/SP (DIP-28) | I2C expanders, addresses 0x20 (U2) and 0x21 (U3). INTA/INTB mirrored, open-drain, wired-OR to GPIO35. |
| U4 | 74AHCT125 (DIP-14) | 3.3 → 5 V buffer for WS2812 data (one gate used, others tied off). |
| Q1 | 2N3904 | Low-side driver for the 5 V passive buzzer, 1 kΩ base, 1N4148 across buzzer. |
| D1 | SS34 / 1N5822 Schottky | 5 V rail → DevKit 5V pin, so USB on the DevKit can't back-feed the rail. |
| C | 470 µF/10 V bulk on 5 V near servo + LED connectors; 100 nF per IC; 10 µF in + 10 µF out on U5 (3V3P, rev 1) | |
| R | I2C pull-ups 4.7 kΩ to 3V3P (SDA, SCL); 10 kΩ pull-ups to 3V3P on GPIO35, GPIO34; 10 kΩ pull-down on GPIO2 (SD_CS, rev 1); 10 kΩ GPIO36→GND (LDR divider, LDR on the plate goes 3V3P→GPIO36); 330 Ω in series with WS2812 data out | |
| A1 | GY-521 MPU-6050 module | Female 1×8 header on the carrier (tilt anti-tamper sits on the carrier, not a plate). |
| J_PWR | 2-pin screw terminal, 5 V in | From the panel-mount USB-C 5 V module. |

### ESP32 pin map (fixed — do not change without updating this file)

| GPIO | Function | Notes |
|------|----------|-------|
| 21 / 22 | I2C SDA / SCL | Carrier bus to MCPs, the tilt sensor (LIS3DH since rev 2) and every plate connector |
| 35 | MCP23017 INT (wired-OR, open-drain) | input-only, 10 k pull-up |
| 39 | Encoder switch ENC_SW (rev 1b) | input-only, 10 k pull-up to 3V3P. The tilt sensor's INT pins are not connected; the firmware polls it over I2C |
| 34 | IR receiver out | input-only, 10 k pull-up |
| 36 (VP) | LDR divider | ADC1_CH0 |
| 32 / 33 | TM1637 CLK / DIO | timer plate |
| 25 | WS2812 data (via U4) | one chain through all plates |
| 26 | Buzzer (via Q1) | LEDC PWM |
| 27 | Servo signal | 5 V servo header |
| 4 / 13 / 14 / 15 | Touch pads T0 / T4 / T6 / T3 | bare wires to copper pads on the sensor plate |
| 18 / 23 / 19 / 5 | SPI SCK / MOSI / MISO / CS | exposed SPI flash (W25Q32) on the probe plate |
| 17 / 16 | UART2 TX / RX | exposed header on the probe plate |
| 2 | SD_CS (rev 1) | strapping pin: 10 k pull-down keeps download mode working |
| 12 | unused | strapping; leave unconnected |
| 0, 1, 3, 6–11 | reserved | boot / USB console / flash |

MCP23017 U2 (0x20): GPA0–3 keypad rows ROW1–4, GPA4–6 keypad columns COL1–3, **GPB6 COL4** (rev 1b), GPB0–3 Simon buttons, GPB4 key switch, GPB5 SD_DET, GPA7 + GPB7 spare outputs.
MCP23017 U3 (0x21): GPA0–4 wire posts WA1–5, **GPB6 WA6** (rev 1b), GPB0–5 wire posts WB1–6, GPA6/GPA5 encoder A/B (ENC_SW moved to GPIO39), GPA7 + GPB7 spare outputs.

Rev 1b rule: GPA7/GPB7 are **output-only** on current MCP23017 silicon and cannot go high-impedance, so no keypad or wire-matrix line may use them (scanning drives one line at a time and leaves the others as inputs; an output-only line would short against the active one when two keys or two leads share a line). All four (U2 GPA7, U2 GPB7, U3 GPA7, U3 GPB7) go to `J_SPARE` as spare outputs.

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

Plus on the carrier: `J_KEY` (2: GPB4, GND), `J_SERVO` (3, SG90 plug order: GND, 5V, SIG; the M6 SERVO_SIG pin is the same net, use either), `J_SPARE` (4 + GND: U2 GPA7, U2 GPB7, U3 GPA7, U3 GPB7, all output-only), `J_PWR`.

KiCad references: Jn_A → `Jn1`, Jn_B → `Jn2`, J_PWR = J7, J_KEY = J8, J_SERVO = J9, J_SPARE = J10 (the SPEC name is in each Value and on the silkscreen).

### Off-the-shelf modules on the plates

| Plate | Modules |
|-------|---------|
| M1 Radio | SSD1306 0.96" I2C OLED (0x3C), KY-040 rotary encoder, 2 WS2812 (or a 2-LED strip piece), antenna lead from the DevKit (U.FL variant optional) |
| M2 Timer | TM1637 0.56" 4-digit module **powered from 3V3P** (its pull-ups would put 5 V on GPIO32/33 if powered from 5 V), 3 WS2812 strike LEDs, 12 mm passive buzzer |
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
