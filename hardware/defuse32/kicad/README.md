# Defuse32 carrier PCB, rev 3 (KiCad 10, 4 layers)

The carrier board sits on the case floor and connects to the six plates by ribbon cables. Rev 2 is an SMD board assembled by JLCPCB: ESP32-WROOM-32E module, USB-C programming port with a CH340C, two MCP23017 expanders, LIS3DH tilt sensor, push-push microSD, WS2812 buffer, buzzer driver and one keyed IDC box header per plate. The source of truth is [`../SPEC.md`](../SPEC.md), section "Rev 2 carrier (2026-10-23)", plus the sections it keeps: ESP32 pin map, MCP23017 allocation (rev 1b), WS2812 chain, I2C addresses and the plate signal sets (rev 1 Jn_B table).

**Status (2026-10-23): placed, routed, finished (rev 2.1: straighter tracks, grounded GND pour, professional silkscreen) and DRC clean with the silkscreen rules on; JLCPCB fabrication and assembly files in `out/jlcpcb/`.** The owner approved the layout preview and delegated the routing; hand edits in KiCad are welcome from here on. Rev 2.1 changes copper and silkscreen only: same placement, schematic, netlist and pin map as rev 2.

| Check | Result |
|---|---|
| `kicad-cli sch erc --severity-all` | 0 errors, 0 warnings |
| `kicad-cli pcb drc --severity-all --schematic-parity --refill-zones` | 0 violations, 0 unconnected items, 0 schematic parity issues (silk_over_copper, silk_overlap, silk_edge_clearance are errors; silk clearance 0.15 mm, text >= 0.8 mm / 0.15 mm) |
| `gen/check_netlist.py` | OK: netlist and board pads match `design.py`, plus the SPEC pin map, MCP23017 allocation, IDC pinout rule, rails, AMS1117 capacitors, outline, holes, U1 antenna beyond the edge and net classes |
| `gen/pcb_audit.py` (finish audit, `out/audit.json`) | silkscreen: 0 violations, 0 warnings, no hidden reference; copper: 0 voids that can take a stitching via, 83 narrower or blocked voids (159 mm2); routing: 49 jogs left (110 in rev 2), each with its reason in `polish.py jogs` |

Rev 1b (THT, DevKitC socket, 190 x 140 mm, routed) is in git, tag `carrier-rev1b`.

Changes against SPEC "Rev 2 carrier" made on 2026-10-23 (SPEC.md not edited yet): **U5 (3V3P) is an AMS1117-3.3** instead of the AP2112K-3.3 (see Power), and the microSD card-detect level is now documented (**low = card present**; firmware `CONFIG_D32_SD_DET_ACTIVE_HIGH=n`).

## Rev 2 overview

- **Board**: 100 x 70 mm, 4 layers (rev 3; rev 2/2.1 had 2), 1.6 mm, 4 x M3 (Ø3.2) non-plated holes 4 mm from the corners. SMD on the top side (JLCPCB assembly); the IDC box headers and the 2.54 mm pin headers are through-hole.
- **ESP32**: U1 ESP32-WROOM-32E-N4 at the left edge, turned 90° so the antenna end points left. The antenna region (footprint y < -6.56 mm) lies beyond the board edge x = 0. The footprint keeps KiCad's antenna keep-out zone (no tracks, vias, pads, pours or footprints) and the antenna outline on F.Fab. EN (SW1) and BOOT (SW2) buttons; EN RC 10 kΩ + 1 µF; GPIO0 10 kΩ pull-up.
- **USB-C** J7 (16-pin, HRO TYPE-C-31-M-12): power input and programming port only. CC1/CC2 5.1 kΩ to GND (5 V sink). VBUS -> F1 PTC (2 A hold, 4 A trip) -> `5V`. U9 USBLC6-2SC6 on D+/D-. Shield to GND.
- **USB-UART**: U7 CH340C at 3.3 V (V3 tied to VCC), no crystal, on UART0: CH340C TXD -> `U0RXD` (GPIO3), RXD <- `U0TXD` (GPIO1). Auto-reset with two MMBT3904 (Q2 DTR -> EN, Q3 RTS -> IO0, 10 kΩ base resistors).
- **Power**: C1 220 µF bulk on `5V`. Two AMS1117-3.3 (SOT-223, JLCPCB Basic C6186): U6 `5V` -> `3V3` for the ESP32 and the CH340C (C7 10 µF in, C8 22 µF out, C9 10 µF + C10 100 nF at the module's 3V3 pin); U5 `5V` -> `3V3P` for the plates, U2/U3, LIS3DH, microSD and all pull-ups (C6 10 µF in, C2 22 µF + C19 100 nF out). The AMS1117 datasheet asks for 10 µF on the input and 22 µF on the output for stability (it specifies tantalum; the 22 µF X5R ceramics here are the usual ESP32-board practice). U5 replaced the SPEC's AP2112K-3.3 (Extended) on 2026-10-23: one Basic part instead of an Extended one, 1 A instead of 600 mA, at the cost of a SOT-223 footprint, 1.1 V dropout (5 V in: fine) and ~5 mA quiescent current.
- **Expanders**: U2/U3 MCP23017-E/SO at 0x20/0x21, rev 1b allocation unchanged, 100 nF each (C3/C4). INTA/INTB mirrored, open-drain, wired-OR to GPIO35.
- **Tilt sensor**: U8 LIS3DH (LGA-16) in I2C mode (CS high) at 0x19: SA0 high through R20 (10 kΩ, keeps ERC clean: SDO is an output pin in the symbol). INT1/INT2 not connected (polled). C14/C16 100 nF on VDD/VDD_IO, C15 10 µF.
- **microSD**: J11 Hirose DM3AT-SF-PEJM5 push-push socket, SPI mode on SCK 18 / MOSI 23 / MISO 19, `SD_CS` = GPIO2 (R8 10 kΩ pull-down kept). DAT0/DAT1/DAT2 10 kΩ pull-ups (R16-R18). C17 100 nF + C18 10 µF.
- **Card detect** (checked 2026-10-23 against Hirose's DM3 catalog: "The card detection switch is Normally Open"; distributors list the DM3AT-SF-PEJM5 with an N/O detect switch): the switch between DET_A (pad 10) and DET_B (pad 9) is open without a card and closes when a card is inserted. DET_A goes to GND, DET_B -> `SD_DET` (U2 GPB5) with R19 10 kΩ pull-up to 3V3P. **`SD_DET` low = card present, high = no card.** Firmware: `CONFIG_D32_SD_DET_ACTIVE_HIGH` must be **n** for this board (the Kconfig default `y` was written for the rev 1 Adafruit-style breakout, whose DET is high with a card).
- **WS2812 buffer**: U4 74AHCT1G125 (SOT-23-5) at 5 V, OE low, R1 330 Ω in series -> `LDI`. Chain: LDI -> M1 -> LDO1 -> M2 -> LDO2 -> M3 -> LDO3 -> M4 -> LDO4 -> M5 -> LDO5 -> M6 (end).
- **Buzzer**: Q1 MMBT3904 low side, R7 1 kΩ base from GPIO26, D1 1N4148WS across the buzzer (BUZZ+ = 5V on J2 pin 11, BUZZ- on J2 pin 10).
- **Pull-ups / pull-downs** (unchanged): R2/R3 4.7 kΩ I2C, R4 GPIO35, R5 GPIO34, R9 GPIO39 10 kΩ to 3V3P; R6 GPIO36 (LDR divider) and R8 GPIO2 10 kΩ to GND.

### ESP32 pin map (unchanged from SPEC)

GPIO21/22 SDA/SCL, 35 MCP_INT, 39 ENC_SW, 34 IR, 36 LDR, 32/33 TM_CLK/TM_DIO, 25 WS_DATA, 26 BUZZ, 27 SERVO_SIG, 4/13/14/15 T0/T4/T6/T3, 18/23/19/5 SCK/MOSI/MISO/CS, 17/16 U2TX/U2RX, 2 SD_CS, 12 NC. New in rev 2: GPIO0 = `IO0` (BOOT button + auto-reset), GPIO1/3 = `U0TXD`/`U0RXD` to the CH340C.

## Schematic

Root sheet (A4, sheet symbols and overview) plus four A3 sub-sheets. Nets cross sheets through global labels and power symbols. Every part carries the fields `LCSC`, `MPN`, `Manufacturer` and `JLC` (Basic/Extended).

| Page | File | Content |
|---|---|---|
| 1 | `defuse32-carrier.kicad_sch` | Root: sheet symbols, overview, I2C addresses |
| 2 | `power_usb.kicad_sch` | USB-C, CC resistors, USBLC6, PTC, bulk, 2x AMS1117 (3V3, 3V3P), power flags, CH340C, auto-reset |
| 3 | `esp32.kicad_sch` | WROOM-32E + decoupling, EN/BOOT, pull-ups/pull-downs, WS2812 buffer, buzzer driver |
| 4 | `io.kicad_sch` | MCP23017 x2, LIS3DH, microSD |
| 5 | `connectors.kicad_sch` | IDC headers J1-J6, J_KEY, J_SERVO, J_SPARE, mounting holes |

SPEC connector names -> references (the SPEC name starts the Value): plate `Jn` = Jn, `J_USB` = J7, `J_KEY` = J8, `J_SERVO` = J9, `J_SPARE` = J10, `J_SD` = J11.

## Plate connectors (2.54 mm keyed IDC box headers)

Rule (SPEC rev 2): pin 1 `5V`, pin 2 `GND`, pin 3 `3V3P`, pin 4 `SDA`, pin 5 `SCL`, pin 6 LDI, pin 7 LDO, then the plate's signals in the order of the rev 1 Jn_B table, spare positions `GND`. Pins are numbered as on the ribbon (odd row 1, 3, 5 ...; even row 2, 4, 6 ...), so ribbon wire n = pin n. LDI/LDO carry the chain nets: the LDI of plate n is the LDO of plate n-1.

**J1, M1 Radio**: 2x5 (10 pins), C19193807 XDFH-0254-2*5P

| Pin | Net | Pin | Net |
|---|---|---|---|
| 1 | 5V | 2 | GND |
| 3 | 3V3P | 4 | SDA |
| 5 | SCL | 6 | LDI (net `LDI`, from R1) |
| 7 | LDO (net `LDO1`) | 8 | ENC_A |
| 9 | ENC_B | 10 | ENC_SW |

**J2, M2 Timer**: 2x6 (12 pins), C18202143 XDFH-0254-2*6P. TM1637 powered from pin 3 (3V3P).

| Pin | Net | Pin | Net |
|---|---|---|---|
| 1 | 5V | 2 | GND |
| 3 | 3V3P | 4 | SDA |
| 5 | SCL | 6 | LDI (net `LDO1`) |
| 7 | LDO (net `LDO2`) | 8 | TM_CLK |
| 9 | TM_DIO | 10 | BUZZ- |
| 11 | BUZZ+ (5V) | 12 | GND (spare) |

**J3, M3 Keypad**: 2x8 (16 pins), C18202144 XDFH-0254-2*8P

| Pin | Net | Pin | Net |
|---|---|---|---|
| 1 | 5V | 2 | GND |
| 3 | 3V3P | 4 | SDA |
| 5 | SCL | 6 | LDI (net `LDO2`) |
| 7 | LDO (net `LDO3`) | 8 | ROW1 |
| 9 | ROW2 | 10 | ROW3 |
| 11 | ROW4 | 12 | COL1 |
| 13 | COL2 | 14 | COL3 |
| 15 | COL4 | 16 | GND (spare) |

**J4, M4 Wires**: 2x10 (20 pins), C18202145 XDFH-0254-2*10P

| Pin | Net | Pin | Net |
|---|---|---|---|
| 1 | 5V | 2 | GND |
| 3 | 3V3P | 4 | SDA |
| 5 | SCL | 6 | LDI (net `LDO3`) |
| 7 | LDO (net `LDO4`) | 8 | WA1 |
| 9 | WA2 | 10 | WA3 |
| 11 | WA4 | 12 | WA5 |
| 13 | WA6 | 14 | WB1 |
| 15 | WB2 | 16 | WB3 |
| 17 | WB4 | 18 | WB5 |
| 19 | WB6 | 20 | GND (spare) |

**J5, M5 Probe**: 2x7 (14 pins), C19193808 XDFH-0254-2*7P

| Pin | Net | Pin | Net |
|---|---|---|---|
| 1 | 5V | 2 | GND |
| 3 | 3V3P | 4 | SDA |
| 5 | SCL | 6 | LDI (net `LDO4`) |
| 7 | LDO (net `LDO5`) | 8 | U2TX |
| 9 | U2RX | 10 | SCK |
| 11 | MOSI | 12 | MISO |
| 13 | CS | 14 | GND (spare) |

**J6, M6 Sensors**: 2x10 (20 pins), C18202145 XDFH-0254-2*10P

| Pin | Net | Pin | Net |
|---|---|---|---|
| 1 | 5V | 2 | GND |
| 3 | 3V3P | 4 | SDA |
| 5 | SCL | 6 | LDI (net `LDO5`) |
| 7 | LDO (chain end, NC) | 8 | T0 |
| 9 | T4 | 10 | T6 |
| 11 | T3 | 12 | LDR |
| 13 | IR | 14 | SIM1 |
| 15 | SIM2 | 16 | SIM3 |
| 17 | SIM4 | 18 | SERVO_SIG |
| 19 | GND (spare) | 20 | GND (spare) |

**Carrier headers** (2.54 mm pin headers): J8 `J_KEY` 1x2: KEY (U2 GPB4), GND. J9 `J_SERVO` 1x3: GND, 5V, SERVO_SIG (SG90 order; same net as J6 pin 18). J10 `J_SPARE` 1x5: U2_GPA7, U2_GPB7, U3_GPA7, U3_GPB7, GND (output-only MCP pins).

## Parts (JLCPCB / LCSC)

Checked 2026-10-23 on the JLCPCB parts API: every part in stock, package matches the footprint. 66 placed parts (57 SMD, 9 THT) plus 4 mounting holes; `out/bom.csv` has the grouped BOM with the same fields.

| Refs | Qty | Value | Footprint | LCSC | MPN | JLC |
|---|---|---|---|---|---|---|
| C3-C5, C10, C12-C14, C16, C17, C19 | 10 | 100 nF | C_0603 | C14663 | CC0603KRX7R9BB104 | Basic |
| C11 | 1 | 1 µF | C_0603 | C15849 | CL10A105KB8NNNC | Basic |
| C6, C7, C9, C15, C18 | 5 | 10 µF | C_0805 | C15850 | CL21A106KAYNNNE | Basic |
| C2, C8 | 2 | 22 µF | C_0805 | C45783 | CL21A226MAQNNNE | Basic |
| C1 | 1 | 220 µF 10 V | CP_Elec_6.3x5.4 | C72494 | RVT1A221M0605 | Extended |
| R4-R6, R8-R13, R16-R20 | 14 | 10 kΩ | R_0603 | C25804 | 0603WAF1002T5E | Basic |
| R14, R15 | 2 | 5.1 kΩ | R_0603 | C23186 | 0603WAF5101T5E | Basic |
| R2, R3 | 2 | 4.7 kΩ | R_0603 | C23162 | 0603WAF4701T5E | Basic |
| R7 | 1 | 1 kΩ | R_0603 | C21190 | 0603WAF1001T5E | Basic |
| R1 | 1 | 330 Ω | R_0603 | C23138 | 0603WAF3300T5E | Basic |
| Q1-Q3 | 3 | MMBT3904 | SOT-23 | C20526 | MMBT3904 | Basic |
| D1 | 1 | 1N4148WS | SOD-323 | C2128 | 1N4148WS | Basic |
| SW1, SW2 | 2 | EN, BOOT | SW_Push_1P1T_XKB_TS-1187A | C318884 | TS-1187A-B-A-B | Basic |
| U5, U6 | 2 | AMS1117-3.3 | SOT-223-3_TabPin2 | C6186 | AMS1117-3.3 | Basic |
| U1 | 1 | ESP32-WROOM-32E-N4 | defuse32:ESP32-WROOM-32E_JLC | C701341 | ESP32-WROOM-32E-N4 | Extended |
| U7 | 1 | CH340C | SOIC-16 | C84681 | CH340C | Extended |
| U2, U3 | 2 | MCP23017-E/SO | SOIC-28W | C47023 | MCP23017-E/SO | Extended |
| U8 | 1 | LIS3DH | LGA-16 3x3 | C15134 | LIS3DHTR | Extended |
| U4 | 1 | 74AHCT1G125 | SOT-23-5 | C7484 | SN74AHCT1G125DBVR | Extended |
| U9 | 1 | USBLC6-2SC6 | SOT-23-6 | C7519 | USBLC6-2SC6 | Extended |
| F1 | 1 | PTC 2 A hold | Fuse_1812 | C18198338 | 1812L200/8GR | Extended |
| J7 | 1 | USB-C 16P | defuse32:USB_C_Receptacle_HRO_TYPE-C-31-M-12_Edge | C165948 | TYPE-C-31-M-12 | Extended |
| J11 | 1 | microSD push-push | microSD_HC_Hirose_DM3AT-SF-PEJM5 | C114218 | DM3AT-SF-PEJM5 | Extended |
| J1 | 1 | IDC 2x5 | IDC-Header_2x05 (THT) | C19193807 | XDFH-0254-2*5P | Extended |
| J2 | 1 | IDC 2x6 | IDC-Header_2x06 (THT) | C18202143 | XDFH-0254-2*6P | Extended |
| J5 | 1 | IDC 2x7 | IDC-Header_2x07 (THT) | C19193808 | XDFH-0254-2*7P | Extended |
| J3 | 1 | IDC 2x8 | IDC-Header_2x08 (THT) | C18202144 | XDFH-0254-2*8P | Extended |
| J4, J6 | 2 | IDC 2x10 | IDC-Header_2x10 (THT) | C18202145 | XDFH-0254-2*10P | Extended |
| J8 | 1 | 1x2 header | PinHeader_1x02 (THT) | C32713268 | HX PZ2.54-1x2P ZZ | Extended |
| J9 | 1 | 1x3 header | PinHeader_1x03 (THT) | C32713269 | HX PZ2.54-1x3P ZZ | Extended |
| J10 | 1 | 1x5 header | PinHeader_1x05 (THT) | C32713271 | HX PZ2.54-1x5P ZZ | Extended |

**Extended SMD parts (10 line items, after the 2026-10-23 regulator swap) and why**: the JLCPCB Basic library has no part of these kinds, so each is the SPEC part or the best-stocked match:

- C701341 ESP32-WROOM-32E-N4, C84681 CH340C, C47023 MCP23017-E/SO (x2), C15134 LIS3DHTR, C7484 SN74AHCT1G125DBVR, C7519 USBLC6-2SC6: the SPEC names these chips; no Basic part exists for any of them.
- C72494 220 µF 10 V electrolytic: no Basic aluminium or polymer capacitor; the Basic search finds 100 µF at most (C15008 ceramic, C16133 tantalum), below the SPEC's >= 220 µF.
- C18198338 1812L200/8GR PTC (2 A hold, 8 V): no Basic resettable fuse.
- C165948 HRO TYPE-C-31-M-12: no Basic USB-C receptacle; this one has an official KiCad footprint and 330 k in stock.
- C114218 Hirose DM3AT-SF-PEJM5: no Basic microSD socket; chosen over cheaper push-push sockets (e.g. C91145 TF-01A) because it has an official KiCad symbol (with card-detect pins) and footprint.

The 3V3P regulator is now a second AMS1117-3.3 (C6186, Basic) instead of the AP2112K-3.3 (C51118, Extended).

Lowest stock among the SMD parts: MCP23017-E/SO (2085), LIS3DHTR (8205), DM3AT (15953), 1812L200/8GR (17140). The THT box headers are low-stock (C19193807 2x5: 304); any keyed 2.54 mm box header with the KiCad IDC-Header footprint fits.

## Local library

Rev 2 uses official KiCad symbols and footprints except:

- `defuse32.kicad_sym` / `CH340C_3V3`: copy of `Interface_USB:CH340C` with pin 4 (V3) typed `power_in`. At 3.3 V the datasheet ties V3 to VCC; with the official `power_out` type ERC reports two power outputs on `3V3` (V3 and the AMS1117).
- `defuse32.pretty` / `ESP32-WROOM-32E_JLC`: copy of `RF_Module:ESP32-WROOM-32E` with the 12 GND thermal vias drilled 0.3 mm instead of 0.2 mm (0.6 mm pad, 0.15 mm ring), because JLCPCB's 2-layer minimum hole is 0.3 mm. Since rev 2.1 its pin-1 triangle is 0.38 mm instead of 0.5 mm and 0.07 mm further in, so it keeps 0.15 mm from the board edge (the antenna overhangs it) and from pad 1 (DRC `silk_edge_clearance` / `silk_over_copper`). Pads, antenna keep-out zone, outline and 3D model are unchanged.
- `defuse32.pretty` / `USB_C_Receptacle_HRO_TYPE-C-31-M-12_Edge`: copy of the official HRO footprint for a receptacle whose front face sits on the board edge: the silkscreen line drawn 0.25 mm in front of the face is removed and the two side lines end 0.35 mm behind it, so no silkscreen is clipped by the edge (DRC `silk_edge_clearance`). Pads, courtyard, fab outline and 3D model reference are unchanged.

All three are written by `gen/gen_lib.py` from the installed KiCad libraries. KiCad 10.0.7 here ships no 3D model for J7 (HRO USB-C), SW1/SW2 (XKB TS-1187A) and F1 (1812 fuse), so the renders and `../cad/carrier.step` show their pads only.

## Placement (rev 2)

Board coordinates: origin at the top-left corner of the outline, x right, y down, mm (KiCad page = board + (50, 50)). Positions live in `gen/design.py` (`PCB`); they follow the approved preview within its ±5 mm. All SMD parts are on the top side (single-sided assembly).

| Block | Parts and position |
|---|---|
| ESP32 | U1 at (6.56, 35), rotation 90: module body x -6.2 to 19.3, y 26 to 44; the antenna end points left and the whole antenna region (footprint y < -6.56) plus the footprint's antenna keep-out zone lie beyond the board edge x = 0 (Espressif's recommended placement). No copper, pour or via goes past the edge; the pours stop 0.3 mm inside it. C10 (100 nF) and C9 (10 µF) right under pin 2 (3V3), on short 0.6 mm tracks, with GND pin 1 next to them |
| Buttons | SW2 BOOT at (24.4, 29.6), next to module pin 25 (IO0), with R11; SW1 EN at (24.4, 40.4), with the EN RC R10/C11 |
| Top edge | J1 M1 2x5 x 8-28, J2 M2 2x6 x 32-55, J3 M3 2x8 x 59-87; key notch up (rotation 270), odd pins on the edge row (y 4.9) |
| Bottom edge | J4 M4 2x10 x 8-41, J5 M5 2x7 x 44-69, key notch down (rotation 90, odd row at y 65.1); J11 microSD x 73-87, card slot on the bottom edge (socket front 0.7 mm inside it) |
| Right edge | J6 M6 2x10 vertical, y 10-43, key notch right (rotation 180, pin 1 at the bottom); J7 USB-C, y 45-54, receptacle front face on the edge x = 100 |
| Left edge | J8 J_KEY 1x2 at (3.8, 13.3-15.8) above the module, J9 J_SERVO 1x3 at (3.8, 51.5-56.6) below it |
| Middle | U3 (MCP23017 0x21: wires, encoder) at (39, 21) and U2 (0x20: keypad, Simon, SD detect) at (61, 21), long axis horizontal, under the top connectors; C4/C3 under their VDD/VSS pins. U8 LIS3DH at (38, 34.5) with C14/C16/C15/R20 and the I2C pull-ups R3 (SCL) / R2 (SDA) at its SCL/SDA pads; U4 WS2812 buffer (47.5, 32.5) with C5/R1; Q1/R7/D1 buzzer driver at (56, 33) |
| Power | U6 (3V3) at (66, 44) and U5 (3V3P) at (66, 52), both AMS1117 SOT-223 with the pins toward the USB side: input caps C7/C6 right of the pins, output caps C8/C2/C19 left of the tabs; C1 220 µF at (52, 53); F1 PTC at (90, 59) under the USB-C |
| USB | J7 at (96.35, 49.5); U9 USBLC6 at (87.8, 49.5) between J7 and U7 CH340C at (82, 43) (long axis horizontal, D+/D- pins toward U9); C12/C13 at VCC/V3; auto-reset Q2/Q3 + R12/R13 above U7; CC resistors R15 above and R14 below the D+/D- lines |
| Lower middle | J10 J_SPARE 1x5 at x 31-41, y 50.3; module pull-ups R4/R5/R6/R9 below the module; microSD pull-ups R16-R19 at y 57 |

Differences from the preview's labels (same block positions): BOOT (SW2) is the upper button, next to module pin 25 (IO0), and EN (SW1) the lower one, near pin 3; U3 (wires J4 + encoder J1) takes the left expander position and U2 (keypad J3, Simon J6, SD detect J11) the right one. Both swaps shorten the routing; swap back by hand if the labels matter more.

## Routing

Routed with Freerouting 2.4.1 through `gen/route_prep.py` (its docstring has the exact commands), then GND pours and stitching; the session used is kept as `out/defuse32-carrier.ses`. Freerouting is not deterministic: a new run gives a different board, and the four `HAND_FIXES` in `route_prep.py` belong to this session only.

1. **Pre-routes (locked, by hand in `PREROUTE`)**: the whole USB section, the LIS3DH fan-out, the module 3V3/GND to C10/C9, and a GND stub + via for every box-header GND pin.
   - **USB D+/D-** (0.2 mm): CH340C pins 5/6 -> USBLC6 (flow-through tracks under its body join pins 1-6 and 3-4) -> USB-C. The CH340C's pin order (D+ left of D-) is the mirror of what the receptacle takes from the board side, so D+ crosses D- once on B.Cu next to the CH340C (2 vias); at the receptacle the B6-A6 D+ pads are joined by a loop under its body and A7-B7 (D-) on the board side. **USB_DP 15.6 mm (2 vias), USB_DM 14.8 mm (0 vias): 0.8 mm apart** (all branches included; USB full speed, 12 Mbit/s, needs no impedance control).
   - **VBUS** (0.6 mm): both receptacle VBUS pads and USBLC6 pin 5 meet on B.Cu and go to F1; CC1/CC2 straight to R14/R15. The receptacle's alignment pegs (NPTH) sit right of the VBUS pads, so VBUS leaves them on the board side.
   - **LIS3DH** (0.5 mm pitch): 0.25 mm supply and GND fan-out to C14/C16/C15/R20 and two GND vias, SA0 to R20, SCL/SDA to the I2C pull-ups R3/R2 placed at the chip.
2. **GND fan-out** (`gnd_fanout`): every other SMD GND pad gets a 0.4 mm stub and a via to the bottom pour, at the first spot that keeps 0.25 mm from other copper (45 pads).
3. **Freerouting** routes all other nets (Default 0.2 mm, Power 0.6 mm, vias 0.6/0.3 mm). The DSN has a GND plane on both layers so it routes no GND but keeps the Power-class clearance to GND pins; fully hand-routed nets are taken out of the DSN network, and each partly pre-routed group keeps one open pin (Freerouting 2.4.1 does not count locked tracks as connecting their pads). Options: no SMD fan-out stage, neck-down on, via cost 150, 40 passes, 10 optimizer passes; this session routed every connection.
4. **Hand fixes** after the session (`HAND_FIXES`): T4 rerouted under SW1 (the optimizer had looped it round both EN pads, crossing the EN jumper), SD_CS moved 0.15 mm away from R3 pad 1, a MOSI corner moved off U5 pin 3 (0.248 mm < 0.25 mm), and C14 pad 1 tied to the 3V3P track at C4 (the LIS3DH supply group had no open pin).
5. **GND pours** (rev 2; rebuilt in rev 2.1, see below) on F.Cu and B.Cu over the whole outline, thermal reliefs on pads (0.3 mm gap, 0.5 mm spokes; USB-C GND pads solid by a custom rule; through-hole GND pins may resolve with one spoke), islands stitched to the main pour and unconnected islands removed.
6. **Antenna**: the module's antenna region and its footprint keep-out zone are outside the outline; no track, via or pour reaches past the edge (copper-to-edge 0.3 mm). The pours run under the module body up to the board edge, as Espressif asks for a module whose antenna overhangs the base board.
7. **Rev 2.1 finish** (`gen/polish.py all`, next section): jogs straightened, pours rebuilt at 0.2 mm, every groundable island stitched, silkscreen placed again.

| Result (rev 2.1) | |
|---|---|
| Vias | **427**: 275 GND (60 fan-out and pre-route vias with their stubs, 107 island stitching vias, 108 grid stitching vias), 152 signal (incl. 6 USB/VBUS pre-route) |
| Track length | 5978 mm (F.Cu 3129, B.Cu 2849), 1272 segments |
| Power tracks | 5V, 3V3, 3V3P, VBUS 0.6 mm everywhere except the 0.25 mm LIS3DH fan-out (3V3P) and the 0.4 mm U9 VBUS stub; GND is the pours plus 0.25-0.6 mm stubs |
| Silkscreen | references 0.8 mm / 0.15 mm, 0 or 90 deg, placed by `gen/polish.py`; 3 callouts with a leader, 7 references on the bottom silkscreen (below); plate names after J1-J6; board legend and JLCPCB order-number placeholder |

Decoupling, cap pad to the IC supply pad (`route_prep.py report`; edge gap / centre distance, mm):

| IC pin | Cap | Gap | IC pin | Cap | Gap |
|---|---|---|---|---|---|
| U1.2 3V3 | C10 100 nF | 1.02 / 2.26 | U6.3 5V in | C7 10 µF | 0.93 / 2.65 |
| U1.2 3V3 | C9 10 µF | 2.88 / 4.37 | U6.2 3V3 out | C8 22 µF | 0.90 / 2.40 |
| U2.9 VDD | C3 100 nF | 1.05 / 2.55 | U7.16 VCC | C12 100 nF | 1.38 / 2.18 |
| U3.9 VDD | C4 100 nF | 1.05 / 2.55 | U7.4 V3 | C13 100 nF | 0.69 / 2.19 |
| U4.5 VCC | C5 100 nF | 0.82 / 1.99 | U8.14 VDD | C14 100 nF | 1.02 / 1.78 |
| U5.3 5V in | C6 10 µF | 0.93 / 2.65 | U8.1 VDD_IO | C16 100 nF | 1.35 / 2.00 |
| U5.2 3V3P out | C2 22 µF | 0.90 / 2.40 | U8.14 VDD | C15 10 µF | 2.56 / 3.57 |
| U5.2 3V3P out | C19 100 nF | 1.00 / 3.31 | J11.4 VDD | C17 100 nF / C18 10 µF | 1.10 / 2.20, 2.91 / 4.20 |

Every decoupling cap pad is within 3 mm (edge to edge) of its supply pad (unchanged in rev 2.1).

## Rev 2.1 finish (`gen/polish.py`)

The owner asked for the professional finish of the routed board: no empty copper between tracks (grounded, not floating), no via under a reference, clean label placement, and no "double angle changes" (jogs). `gen/polish.py all` does it on the current board, with the rules of the pcb-layout-pro skill, measured by `gen/pcb_audit.py` (a copy of the skill's audit). It does not re-route from scratch, move parts, re-apply `HAND_FIXES` or touch the pre-routes; every move keeps all clearances (exact geometry against the net-class rules) and every connection, and KiCad's DRC checks the result. Its docstring has the details.

| | rev 2 | rev 2.1 |
|---|---|---|
| Jogs (audit) | 110 | 49 |
| Copper voids >= 0.5 mm2 (audit) | 105, 251 mm2 | 83, 159 mm2 |
| ... of which a stitching via fits | 62 (86 with the old audit test) | **0** |
| Silkscreen violations / warnings (audit) | 100 / 1 (64 strokes 0.12 mm, 36 vias under or next to text; R6 in J9's courtyard) | **0 / 0** |
| Hidden references | R17, R18 | none |
| Vias | 320 (168 GND) | 427 (275 GND) |
| KiCad DRC (all severities, parity) | 0 / 0 / 0 | 0 / 0 / 0, silk rules on |

1. **Jogs.** Router stubs at vias removed (10 vias moved onto the end of their stub); 53 jogs straightened by extending the run after the jog back along its own line (or the run before it forward), by sliding the slanted part back to where the first run started, by pushing aside the via or track of another net that was in the way, or by re-routing a few segments around the jog (octilinear search, bend penalties). Collinear pieces merged. **47 jogs are left (49 counted by the audit, which also follows chains through track ends inside vias)**: 2 on the hand-routed USB pair (kept symmetric), 27 where the step passes between header or IC pads (J1, J3-J6, J8-J10 rows, U1, U4, U5, U7, Q3, J11, R4/R6/R9, C5/C8), 7 at T-junctions that a move would break, 10 locked between tracks and vias of other nets that cannot move without a real re-route (J4 WA/WB bus, SCL/SDA/SCK/MISO along the left side, LDO3, U3_GPA7), 1 (ROW3, 0.10 mm) with no straight alternative between the pads it joins. `/usr/bin/python3 gen/polish.py jogs` lists them with the reason. Removing these needs local hand re-routing (or a re-route of the J4 bus).
2. **Copper.** GND pours rebuilt on both layers: clearance 0.2 mm, minimum width 0.2 mm (net-class Power clearance 0.25 mm still applies), thermal reliefs 0.3 / 0.5 mm, island removal "always". 12 tracks were shifted (corners sliding, directions kept) to close narrow strips. Every GND piece that a legal via can join to the main pour got one (107 island vias; 8 of them after pushing a blocking track or via aside; 4 references moved off the only via spot), then a 5 mm stitching grid (108 vias) off the labels and the U1/J7/J11 courtyards. No floating copper. **83 voids remain (159 mm2), none can take a via**: strips between tracks narrower than via + clearances (81) or over a void on the other layer (2); the largest are a 0.64 mm strip between the IR and SCL diagonals on B.Cu (14 mm2) and strips along the top edge and under J4/J5 where the other layer has tracks. Closing them needs track moves the automatic pass could not make legally.
3. **Silkscreen.** One size for every reference: 0.8 mm / 0.15 mm (at 1.0 mm, 12 parts had no spot; at 0.8 mm, 9). 0 or 90 deg, keep-upright, outside every courtyard (mounting holes included), at most 2 mm from and nearer to its own part than any other, 0.15 mm from pads, mask openings and silk, 0.3 mm from the edge, never over a via (a via in the way of the only good spot was moved). Rows share a line (R12/R13, Q2/Q3, C4/C3, U3/U2, J1-J3, J4/J5, ...). Board legend `DEFUSE32 CARRIER` / `rev 2.1  2026-10` and the JLCPCB placeholder `JLCJLCJLCJLC` at the top left; plate names after the header references (`J1  M1 RADIO` ... `J6  M6 SENSORS`, from SPEC "Module plates"). U8, R11 and C11 are callouts: label a short way off with a 0.15 mm leader to the part. **7 references are on the bottom silkscreen, under their parts, because no top spot or leader path exists:** R16-R19 (row between U5's SOT-223 body above, J5's box header below, C19/C1 left and J11 right; printed as a row on the bottom), R14 and R15 (USB-C CC resistors between J7, U7/U9, F1 and J6) and C17 (between C18, C13, U9 and J11). The old bottom legend is gone. The pin-1 and key marks are kept; U1's pin-1 triangle is smaller and 0.07 mm further in (local library, `gen_lib.py`), so it clears the board edge and pad 1 by 0.15 mm.
4. **Rules.** `gen_pcb.write_project` now writes silk clearance 0.15 mm, text >= 0.8 mm / 0.15 mm and makes silk_over_copper, silk_overlap and silk_edge_clearance errors, so DRC enforces the silkscreen from now on.

What to look at in KiCad: the 7 bottom-side references and the 3 callouts (are they where you want them?), the remaining jogs in the J4 bus and along the left edge (hand re-route if they bother you), and the board title block (rev 2.1).

## Assembly (JLCPCB)

`out/jlcpcb/` holds the Gerbers + drill (zip), the JLCPCB BOM (Comment, Designator, Footprint, LCSC Part #; 23 lines, 57 SMD parts) and the CPL (Designator, Mid X, Mid Y, Layer, Rotation; 57 top-side parts), written by `gen/gen_jlcpcb.py`; [`out/jlcpcb/README.md`](out/jlcpcb/README.md) has the order settings.

- Single-sided SMD assembly, all on top. Coordinates: drill/place origin at the board's bottom-left corner (Gerbers, drill and CPL agree).
- **Check JLCPCB's rotation preview part by part**: the CPL carries KiCad's rotations, and JLCPCB's zero orientation differs per package (SOT-23/SOT-223/electrolytic often +180°, SOIC/LGA +-90°). Pin 1 of every IC, D1 (cathode to 5V), C1 (+) and the J7/J11 openings at the board edges are the ones to look at.
- **Through-hole, not assembled by default**: J1-J6 IDC box headers (2x5, 2x6, 2x8, 2x10, 2x7, 2x10), J8 1x2, J9 1x3, J10 1x5 pin headers. Solder by hand (keys toward the board edges, as on the silkscreen) or add them as JLCPCB THT assembly.
- Extended parts after the regulator swap: 10 line items (see "Parts").

## Board and design rules

- `defuse32-carrier.kicad_pcb`: 100 x 70 mm, 4 copper layers on JLCPCB's JLC04161H-7628 stack-up (written into the board's Physical Stackup by `gen_pcb.write_stackup`: 1 oz outer / 0.5 oz inner, 0.2104 mm 7628 prepreg, 1.065 mm core, 1.6 mm), In1.Cu named `GND1`, In2.Cu `GND2` (layer type "power": planes); H1-H4 (MountingHole_3.2mm_M3) 4 mm from the corners; placed (design.py `PCB`), routed, zones `GND_F` / `GND_B` (pours) and `GND_L2` / `GND_L3` (planes): whole outline, clearance 0.2 mm, minimum width 0.2 mm, thermal reliefs 0.3 / 0.5 mm, island removal always; title block rev 3.
- **Board minimums = JLCPCB 4-layer capabilities at standard price** (https://jlcpcb.com/capabilities/pcb-capabilities, read 2026-10-23; summary with every number in the pcb-layout-pro skill, `references/jlcpcb.md`): clearance and track 0.1 mm (JLCPCB 0.09), smallest hole 0.2 mm, smallest via 0.45 mm (JLCPCB charges extra for 0.15 mm holes and for 0.2 mm holes under 0.45 mm), via ring 0.1 mm, hole to hole 0.25 mm, hole clearance 0.2 mm, copper to edge 0.3 mm. Silkscreen: clearance 0.15 mm, text >= 1.0 mm (JLCPCB's minimum height) / 0.15 mm stroke; silk_over_copper, silk_overlap and silk_edge_clearance are errors.
- Net classes (in `defuse32-carrier.kicad_pro`): **Power** = `5V`, `3V3`, `3V3P`, `GND`, `VBUS`: 0.6 mm track, 0.25 mm clearance. **Default**: 0.2 mm track, 0.2 mm clearance. Vias 0.6/0.3 mm; GND fan-out and stitching vias 0.45/0.2 mm.
- Custom rules (`defuse32-carrier.kicad_dru`): JLCPCB PTH hole to track 0.28 mm, inner-layer PTH hole to copper 0.3 mm, pad hole to pad hole (different nets) 0.45 mm; clearance 0.15 mm between items inside the U8 (LIS3DH) and J7 (USB-C) courtyards (0.5 mm pitch: their own pad gaps are 0.15 / 0.2 mm); J7 GND pads join the pours solid; through-hole GND pins may resolve with one thermal spoke per layer (box headers, hand-soldered: thermal reliefs kept).
- 3D models: KiCad's library for everything except J7 (HRO TYPE-C-31-M-12), SW1/SW2 (XKB TS-1187A) and F1 (1812 PTC), which use the LCSC/EasyEDA STEP models fetched by `gen/fetch_3d.py` into `3d/` (git-ignored; see "3D models").

## Files

| Path | What |
|---|---|
| `defuse32-carrier.kicad_pro/.kicad_sch/.kicad_pcb/.kicad_dru` | The project: root sheet, net classes, rules, routed board |
| `power_usb.kicad_sch`, `esp32.kicad_sch`, `io.kicad_sch`, `connectors.kicad_sch` | Sub-sheets (pages 2-5) |
| `defuse32.kicad_sym`, `defuse32.pretty/` | Local library (CH340C_3V3, ESP32-WROOM-32E_JLC, USB_C_Receptacle_HRO_TYPE-C-31-M-12_Edge) |
| `3d/` | git-ignored: STEP models of J7, SW1/SW2, F1 from LCSC/EasyEDA, rebuilt by `gen/fetch_3d.py fetch` |
| `gen/design.py` | Single source of truth: parts, pin-to-net map, LCSC data, sheet layout, PCB placement, net classes |
| `gen/gen_lib.py` | Writes the local library from the installed KiCad libraries |
| `gen/gen_sch.py` | Writes the five schematic files: power symbols and global labels on short pin stubs |
| `gen/gen_pcb.py` | Writes the placed, unrouted 4-layer board (stack-up, outline, footprints, nets from the schematic netlist, LCSC fields, 3D models from `models3d.json`, silkscreen references), the `.kicad_pro` (JLCPCB rules) and the `.kicad_dru`. Refuses to overwrite a routed board (tracks, vias or zones; `--force` overrides) |
| `gen/route_prep.py` | Routing: pre-routes, GND fan-out, DSN export (GND planes), SES import, `maze` (A* for what Freerouting leaves open, with local rip-up), zones, report |
| `gen/polish.py` | Finish of the routed board (rev 2.1, extended for rev 3): jogs, 90 deg corners, GND pours + planes, stitching and return vias, narrow strips, silkscreen (references, callouts, legend, plate names), DRC, report |
| `gen/fetch_3d.py`, `gen/models3d.json` | Missing 3D models via easyeda2kicad, matched onto our footprints (offsets / rotations in the JSON, applied by `gen_pcb.py` or `fetch_3d.py apply`) |
| `gen/renders.py` | The `../renders/carrier-*.png` renders and 2D plots |
| `gen/pcb_audit.py` | Finish audit (copy of the pcb-layout-pro skill's script): copper voids, jogs, silkscreen problems DRC does not flag |
| `gen/gen_jlcpcb.py` | JLCPCB Gerbers, drill, zip, BOM and CPL into `out/jlcpcb/` |
| `gen/check_netlist.py` | Rev 2 checks (see Status) |
| `gen/sexp.py`, `gen/symlib.py` | S-expression reader/writer; symbol flattening (`extends`) |
| `out/defuse32-carrier.pdf` | Schematic PDF (5 pages) |
| `out/bom.csv` | BOM grouped by value, footprint and LCSC number, with MPN, manufacturer and Basic/Extended |
| `out/defuse32-carrier.net` | Schematic netlist, input of `check_netlist.py` |
| `out/defuse32-carrier.ses` | The Freerouting session the board was built from |
| `out/erc.rpt`, `out/drc.rpt`, `out/audit.json` | Latest check reports (DRC, ERC, finish audit) |
| `out/jlcpcb/` | JLCPCB fabrication and assembly files (rev 3, 4 layers) |
| `../renders/carrier-top.png`, `carrier-iso.png`, `carrier-bottom.png` | 3D renders (kicad-cli) |
| `../renders/carrier-f-cu.png`, `carrier-in1-cu.png`, `carrier-in2-cu.png`, `carrier-b-cu.png`, `carrier-silk.png` | 2D plots, 300 dpi: F.Cu + F.Silkscreen, In1.Cu, In2.Cu, B.Cu, F.Silkscreen + F.Mask + F.Fab (each with Edge.Cuts) |

## Regenerate

From `hardware/defuse32/kicad/`. Scripts that import `pcbnew` need KiCad's Python (`/usr/bin/python3`, not conda). Tools: KiCad 10.0.7, Freerouting 2.4.1 (`~/tools/freerouting-2.4.1`), easyeda2kicad 1.0.1 in its own venv (`~/tools/easyeda2kicad-1.0.1`, `pip install easyeda2kicad==1.0.1`; only for the 3D models).

```sh
python3 gen/gen_lib.py                      # local symbols + footprints
python3 gen/gen_sch.py                      # five schematic files
/usr/bin/python3 gen/fetch_3d.py fetch      # 3D models of J7, SW1/SW2, F1 into 3d/ (git-ignored) + gen/models3d.json

# rev 3 board from scratch (throws the routed board away): placement, routing, finish
/usr/bin/python3 gen/gen_pcb.py --force     # 4 layers, stack-up, JLCPCB rules, 3D models
/usr/bin/python3 gen/route_prep.py prep     # locked pre-routes + GND fan-out vias
/usr/bin/python3 gen/route_prep.py export /tmp/d32/r3.dsn
java -jar ~/tools/freerouting-2.4.1/freerouting-2.4.1.jar -de /tmp/d32/r3.dsn -do /tmp/d32/r3.ses -mp 60 -mt 1 \
     --gui.enabled=false --router.fanout.enabled=false --router.automatic_neckdown=true \
     --router.scoring.via_costs=150 --router.optimizer.enabled=false \
     --usage_and_diagnostic_data.disable_analytics=true --profile.allow_telemetry=false
/usr/bin/python3 gen/route_prep.py import /tmp/d32/r3.ses   # or out/defuse32-carrier.ses (this board's session)
/usr/bin/python3 gen/route_prep.py maze     # A* for the connections Freerouting left open
/usr/bin/python3 gen/route_prep.py finish   # zones, provisional references, report
/usr/bin/python3 gen/polish.py all          # finish: jogs, corners, pours + planes, stitching, silkscreen, DRC (~45 min)
# (D32_BOARD=/path/copy.kicad_pcb runs any of it on a copy with its own .kicad_pro/.kicad_dru)

# checks
kicad-cli sch export netlist -o out/defuse32-carrier.net defuse32-carrier.kicad_sch
kicad-cli sch erc --severity-all -o out/erc.rpt defuse32-carrier.kicad_sch
kicad-cli pcb drc --severity-all --schematic-parity --refill-zones -o out/drc.rpt defuse32-carrier.kicad_pcb
/usr/bin/python3 gen/check_netlist.py out/defuse32-carrier.net defuse32-carrier.kicad_pcb
/usr/bin/python3 gen/pcb_audit.py defuse32-carrier.kicad_pcb --json out/audit.json   # exit 1 while violations remain

# exports
kicad-cli sch export pdf -o out/defuse32-carrier.pdf defuse32-carrier.kicad_sch
kicad-cli sch export bom --fields 'Reference,Value,Footprint,${QUANTITY},LCSC,MPN,Manufacturer,JLC' \
  --labels 'Refs,Value,Footprint,Qty,LCSC,MPN,Manufacturer,JLC' --group-by 'Value,Footprint,LCSC' \
  --sort-field 'Reference' -o out/bom.csv defuse32-carrier.kicad_sch
/usr/bin/python3 gen/gen_jlcpcb.py          # out/jlcpcb/ (4-layer Gerbers, BOM, CPL with JLCPCB Tools rotations)
kicad-cli pcb export step --force --subst-models -o ../cad/carrier.step defuse32-carrier.kicad_pcb
/usr/bin/python3 gen/renders.py             # ../renders/carrier-*.png (3D renders, 2D layer plots)
```

The board is edited in KiCad from here: circuit changes go through `design.py` + `gen_sch.py`, then KiCad *Tools > Update PCB from Schematic*. `gen_pcb.py` stops on the routed board; `gen_pcb.py --force` followed by the `route_prep.py` steps and `polish.py all` rebuilds placement, routing and finish from scratch (and loses hand edits). `polish.py all` can be run again after hand edits: it rebuilds the pours, stitching and silkscreen and only moves tracks where a jog, a corner or a narrow strip is fixed.
