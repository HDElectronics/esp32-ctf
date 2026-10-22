# Defuse32 carrier PCB, rev 2 (KiCad 10)

The carrier board sits on the case floor and connects to the six plates by ribbon cables. Rev 2 is an SMD board assembled by JLCPCB: ESP32-WROOM-32E module, USB-C programming port with a CH340C, two MCP23017 expanders, LIS3DH tilt sensor, push-push microSD, WS2812 buffer, buzzer driver and one keyed IDC box header per plate. The source of truth is [`../SPEC.md`](../SPEC.md), section "Rev 2 carrier (2026-10-23)", plus the sections it keeps: ESP32 pin map, MCP23017 allocation (rev 1b), WS2812 chain, I2C addresses and the plate signal sets (rev 1 Jn_B table).

**Status (2026-10-23): schematic, libraries, footprints and JLCPCB parts done; board outline, holes and all footprints in the PCB, roughly placed and unrouted.** Placement and routing are the next task.

| Check | Result |
|---|---|
| `kicad-cli sch erc --severity-all` | 0 errors, 0 warnings |
| `kicad-cli pcb drc --schematic-parity` | 0 parity issues; 262 unconnected (unrouted); 219 violations, all from the rough, stacked placement (58 courtyard overlap, 54 silk overlap, 47 silk over copper, 22 shorting, 19 clearance between neighbouring parts, 16 mask bridge, 2 silk to edge, 1 PTH in courtyard) |
| `gen/check_netlist.py` | OK: netlist and board pads match `design.py`, plus the SPEC pin map, MCP23017 allocation, IDC pinout rule, rails, outline, holes and net classes |

Rev 1b (THT, DevKitC socket, 190 x 140 mm, routed) is in git, tag `carrier-rev1b`. `gen/route_prep.py` and `out/jlcpcb/` still belong to rev 1b (the gerbers there are **not** rev 2).

## Rev 2 overview

- **Board**: 100 x 70 mm, 2 layers, 1.6 mm, 4 x M3 (Ø3.2) non-plated holes 4 mm from the corners. SMD on the top side (JLCPCB assembly); the IDC box headers and the 2.54 mm pin headers are through-hole.
- **ESP32**: U1 ESP32-WROOM-32E-N4 at the left edge, turned 90° so the antenna end points left. The antenna region (footprint y < -6.56 mm) lies beyond the board edge x = 0. The footprint keeps KiCad's antenna keep-out zone (no tracks, vias, pads, pours or footprints) and the antenna outline on F.Fab. EN (SW1) and BOOT (SW2) buttons; EN RC 10 kΩ + 1 µF; GPIO0 10 kΩ pull-up.
- **USB-C** J7 (16-pin, HRO TYPE-C-31-M-12): power input and programming port only. CC1/CC2 5.1 kΩ to GND (5 V sink). VBUS -> F1 PTC (2 A hold, 4 A trip) -> `5V`. U9 USBLC6-2SC6 on D+/D-. Shield to GND.
- **USB-UART**: U7 CH340C at 3.3 V (V3 tied to VCC), no crystal, on UART0: CH340C TXD -> `U0RXD` (GPIO3), RXD <- `U0TXD` (GPIO1). Auto-reset with two MMBT3904 (Q2 DTR -> EN, Q3 RTS -> IO0, 10 kΩ base resistors).
- **Power**: C1 220 µF bulk on `5V`. U6 AMS1117-3.3 (SOT-223) `5V` -> `3V3` for the ESP32 and the CH340C (C7 10 µF in, C8 22 µF out, C9 10 µF + C10 100 nF at the module's 3V3 pin). U5 AP2112K-3.3 (SOT-23-5, 600 mA) `5V` -> `3V3P` for the plates, U2/U3, LIS3DH, microSD and all pull-ups (C6 1 µF in, C2 10 µF + C19 100 nF out).
- **Expanders**: U2/U3 MCP23017-E/SO at 0x20/0x21, rev 1b allocation unchanged, 100 nF each (C3/C4). INTA/INTB mirrored, open-drain, wired-OR to GPIO35.
- **Tilt sensor**: U8 LIS3DH (LGA-16) in I2C mode (CS high) at 0x19: SA0 high through R20 (10 kΩ, keeps ERC clean: SDO is an output pin in the symbol). INT1/INT2 not connected (polled). C14/C16 100 nF on VDD/VDD_IO, C15 10 µF.
- **microSD**: J11 Hirose DM3AT push-push socket, SPI mode on SCK 18 / MOSI 23 / MISO 19, `SD_CS` = GPIO2 (R8 10 kΩ pull-down kept). DAT0/DAT1/DAT2 10 kΩ pull-ups (R16-R18). Card detect: DET_A to GND, DET_B -> `SD_DET` (U2 GPB5) with R19 10 kΩ pull-up, so a card pulls it low (`CONFIG_D32_SD_DET_ACTIVE_HIGH=n`). C17 100 nF + C18 10 µF.
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
| 2 | `power_usb.kicad_sch` | USB-C, CC resistors, USBLC6, PTC, bulk, AMS1117, AP2112K, power flags, CH340C, auto-reset |
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
| C6, C11 | 2 | 1 µF | C_0603 | C15849 | CL10A105KB8NNNC | Basic |
| C2, C7, C9, C15, C18 | 5 | 10 µF | C_0805 | C15850 | CL21A106KAYNNNE | Basic |
| C8 | 1 | 22 µF | C_0805 | C45783 | CL21A226MAQNNNE | Basic |
| C1 | 1 | 220 µF 10 V | CP_Elec_6.3x5.4 | C72494 | RVT1A221M0605 | Extended |
| R4-R6, R8-R13, R16-R20 | 14 | 10 kΩ | R_0603 | C25804 | 0603WAF1002T5E | Basic |
| R14, R15 | 2 | 5.1 kΩ | R_0603 | C23186 | 0603WAF5101T5E | Basic |
| R2, R3 | 2 | 4.7 kΩ | R_0603 | C23162 | 0603WAF4701T5E | Basic |
| R7 | 1 | 1 kΩ | R_0603 | C21190 | 0603WAF1001T5E | Basic |
| R1 | 1 | 330 Ω | R_0603 | C23138 | 0603WAF3300T5E | Basic |
| Q1-Q3 | 3 | MMBT3904 | SOT-23 | C20526 | MMBT3904 | Basic |
| D1 | 1 | 1N4148WS | SOD-323 | C2128 | 1N4148WS | Basic |
| SW1, SW2 | 2 | EN, BOOT | SW_Push_1P1T_XKB_TS-1187A | C318884 | TS-1187A-B-A-B | Basic |
| U6 | 1 | AMS1117-3.3 | SOT-223-3_TabPin2 | C6186 | AMS1117-3.3 | Basic |
| U5 | 1 | AP2112K-3.3 | SOT-23-5 | C51118 | AP2112K-3.3TRG1 | Extended |
| U1 | 1 | ESP32-WROOM-32E-N4 | defuse32:ESP32-WROOM-32E_JLC | C701341 | ESP32-WROOM-32E-N4 | Extended |
| U7 | 1 | CH340C | SOIC-16 | C84681 | CH340C | Extended |
| U2, U3 | 2 | MCP23017-E/SO | SOIC-28W | C47023 | MCP23017-E/SO | Extended |
| U8 | 1 | LIS3DH | LGA-16 3x3 | C15134 | LIS3DHTR | Extended |
| U4 | 1 | 74AHCT1G125 | SOT-23-5 | C7484 | SN74AHCT1G125DBVR | Extended |
| U9 | 1 | USBLC6-2SC6 | SOT-23-6 | C7519 | USBLC6-2SC6 | Extended |
| F1 | 1 | PTC 2 A hold | Fuse_1812 | C18198338 | 1812L200/8GR | Extended |
| J7 | 1 | USB-C 16P | USB_C_Receptacle_HRO_TYPE-C-31-M-12 | C165948 | TYPE-C-31-M-12 | Extended |
| J11 | 1 | microSD push-push | microSD_HC_Hirose_DM3AT-SF-PEJM5 | C114218 | DM3AT-SF-PEJM5 | Extended |
| J1 | 1 | IDC 2x5 | IDC-Header_2x05 (THT) | C19193807 | XDFH-0254-2*5P | Extended |
| J2 | 1 | IDC 2x6 | IDC-Header_2x06 (THT) | C18202143 | XDFH-0254-2*6P | Extended |
| J5 | 1 | IDC 2x7 | IDC-Header_2x07 (THT) | C19193808 | XDFH-0254-2*7P | Extended |
| J3 | 1 | IDC 2x8 | IDC-Header_2x08 (THT) | C18202144 | XDFH-0254-2*8P | Extended |
| J4, J6 | 2 | IDC 2x10 | IDC-Header_2x10 (THT) | C18202145 | XDFH-0254-2*10P | Extended |
| J8 | 1 | 1x2 header | PinHeader_1x02 (THT) | C32713268 | HX PZ2.54-1x2P ZZ | Extended |
| J9 | 1 | 1x3 header | PinHeader_1x03 (THT) | C32713269 | HX PZ2.54-1x3P ZZ | Extended |
| J10 | 1 | 1x5 header | PinHeader_1x05 (THT) | C32713271 | HX PZ2.54-1x5P ZZ | Extended |

**Extended SMD parts (11 line items) and why**: the JLCPCB Basic library has no part of these kinds, so each is the SPEC part or the best-stocked match:

- C701341 ESP32-WROOM-32E-N4, C84681 CH340C, C47023 MCP23017-E/SO, C15134 LIS3DHTR, C7484 SN74AHCT1G125DBVR, C7519 USBLC6-2SC6: the SPEC names these chips; no Basic part exists for any of them.
- C51118 AP2112K-3.3TRG1: named in SPEC. The Basic 3.3 V LDOs are XC6206 (200 mA) and HT7533 (100 mA), too small for the plates, and AMS1117-3.3 (SOT-223, C6186). A second AMS1117 on 3V3P would make U5 Basic too, at the cost of a SOT-223 footprint and the higher dropout/quiescent current; kept as SPEC says.
- C72494 220 µF 10 V electrolytic: no Basic aluminium or polymer capacitor; the Basic search finds 100 µF at most (C15008 ceramic, C16133 tantalum), below the SPEC's ≥ 220 µF.
- C18198338 1812L200/8GR PTC (2 A hold, 8 V): no Basic resettable fuse.
- C165948 HRO TYPE-C-31-M-12: no Basic USB-C receptacle; this one has an official KiCad footprint and 330 k in stock.
- C114218 Hirose DM3AT-SF-PEJM5: no Basic microSD socket; chosen over cheaper push-push sockets (e.g. C91145 TF-01A) because it has an official KiCad symbol (with card-detect pins) and footprint.

Lowest stock among the SMD parts: MCP23017-E/SO (2085), LIS3DHTR (8205), AP2112K (14983), DM3AT (15953), 1812L200/8GR (17140). The THT box headers are low-stock (C19193807 2x5: 304); any keyed 2.54 mm box header with the KiCad IDC-Header footprint fits.

## Local library

Rev 2 uses official KiCad symbols and footprints except:

- `defuse32.kicad_sym` / `CH340C_3V3`: copy of `Interface_USB:CH340C` with pin 4 (V3) typed `power_in`. At 3.3 V the datasheet ties V3 to VCC; with the official `power_out` type ERC reports two power outputs on `3V3` (V3 and the AMS1117).
- `defuse32.pretty` / `ESP32-WROOM-32E_JLC`: copy of `RF_Module:ESP32-WROOM-32E` with the 12 GND thermal vias drilled 0.3 mm instead of 0.2 mm (0.6 mm pad, 0.15 mm ring), because JLCPCB's 2-layer minimum hole is 0.3 mm. Pads, antenna keep-out zone, outline and 3D model are unchanged.

Both are written by `gen/gen_lib.py` from the installed KiCad libraries.

## Board and design rules

- `defuse32-carrier.kicad_pcb`: 100 x 70 mm Edge.Cuts rectangle, H1-H4 (MountingHole_3.2mm_M3) at 4 mm from the corners, all 70 footprints with their nets, rough placement after the approved preview (module left, expanders middle, CH340C + USB-C bottom right, regulators near the USB path, microSD bottom right), many footprints overlapping. Only U1 (antenna region beyond x = 0) and the holes are meant to stay. No tracks, no zones.
- Net classes (in `defuse32-carrier.kicad_pro`): **Power** = `5V`, `3V3`, `3V3P`, `GND`, `VBUS`: 0.6 mm track, 0.25 mm clearance. **Default**: 0.2 mm track, 0.2 mm clearance. Vias 0.6/0.3 mm.
- Board minimums = JLCPCB 2-layer standard: track/space 0.127 mm, hole 0.3 mm, via ring 0.13 mm, via 0.56 mm, hole-to-hole 0.5 mm, copper to edge 0.3 mm.
- Custom rules (`defuse32-carrier.kicad_dru`): clearance 0.15 mm between items inside the U8 (LIS3DH, 0.5 mm pitch) and J7 (USB-C, 0.5 mm pitch) courtyards. Their own pad gaps (0.15 mm and 0.2 mm) are below the Default/Power clearances.

## Files

| Path | What |
|---|---|
| `defuse32-carrier.kicad_pro/.kicad_sch/.kicad_pcb/.kicad_dru` | The project: root sheet, net classes, rules, board |
| `power_usb.kicad_sch`, `esp32.kicad_sch`, `io.kicad_sch`, `connectors.kicad_sch` | Sub-sheets (pages 2-5) |
| `defuse32.kicad_sym`, `defuse32.pretty/` | Local library (CH340C_3V3, ESP32-WROOM-32E_JLC) |
| `gen/design.py` | Single source of truth: parts, pin-to-net map, LCSC data, sheet layout, rough PCB placement, net classes |
| `gen/gen_lib.py` | Writes the local library from the installed KiCad libraries |
| `gen/gen_sch.py` | Writes the five schematic files: power symbols and global labels on short pin stubs |
| `gen/gen_pcb.py` | Writes the board (outline, footprints, nets from the schematic netlist, LCSC fields), the `.kicad_pro` and the `.kicad_dru`. Refuses to overwrite a routed board (`--force` overrides) |
| `gen/check_netlist.py` | Rev 2 checks (see Status) |
| `gen/route_prep.py` | Rev 1b autorouting record (Freerouting round trip); not used for rev 2 |
| `gen/sexp.py`, `gen/symlib.py` | S-expression reader/writer; symbol flattening (`extends`) |
| `out/defuse32-carrier.pdf` | Schematic PDF (5 pages) |
| `out/bom.csv` | BOM grouped by value, footprint and LCSC number, with MPN, manufacturer and Basic/Extended |
| `out/defuse32-carrier.net` | Schematic netlist, input of `check_netlist.py` |
| `out/erc.rpt`, `out/drc.rpt` | Latest check reports |
| `out/jlcpcb/` | **Rev 1b** fabrication files (stale until rev 2 is routed) |

## Regenerate

From `hardware/defuse32/kicad/`. Scripts that import `pcbnew` need KiCad's Python (`/usr/bin/python3`, not conda).

```sh
python3 gen/gen_lib.py                      # local symbol + footprint
python3 gen/gen_sch.py                      # five schematic files
/usr/bin/python3 gen/gen_pcb.py             # board + .kicad_pro + .kicad_dru (stops on a routed board)

# checks
kicad-cli sch export netlist -o out/defuse32-carrier.net defuse32-carrier.kicad_sch
kicad-cli sch erc --severity-all -o out/erc.rpt defuse32-carrier.kicad_sch
kicad-cli pcb drc --schematic-parity --severity-all -o out/drc.rpt defuse32-carrier.kicad_pcb
/usr/bin/python3 gen/check_netlist.py out/defuse32-carrier.net defuse32-carrier.kicad_pcb

# exports
kicad-cli sch export pdf -o out/defuse32-carrier.pdf defuse32-carrier.kicad_sch
kicad-cli sch export bom --fields 'Reference,Value,Footprint,${QUANTITY},LCSC,MPN,Manufacturer,JLC' \
  --labels 'Refs,Value,Footprint,Qty,LCSC,MPN,Manufacturer,JLC' --group-by 'Value,Footprint,LCSC' \
  --sort-field 'Reference' -o out/bom.csv defuse32-carrier.kicad_sch
```

Once the board is placed by hand, circuit changes go through `design.py` + `gen_sch.py`, then KiCad *Tools > Update PCB from Schematic*; do not rerun `gen_pcb.py` (it would reset the placement).

## Notes for the placement task

- U1 stays at (6.56, 35) rotation 90 (board coordinates, origin top-left): the footprint line y = -6.56 (antenna-region boundary) on the board edge. Keep copper out of the keep-out zone; it extends 15 mm beyond the module tip, all outside the board.
- Decoupling: C9/C10 at U1 pin 2; C3/C4 within 3 mm of the MCP23017 VDD pins (SPEC); C12/C13 at U7 pins 16/4; C14-C16 at U8; C5 at U4; C17/C18 at J11.
- SPEC placement: J1-J3 top edge, J4-J5 bottom edge, J6 vertical on the right edge above the USB-C, CH340C + USB-C bottom right, microSD bottom right edge, regulators near the USB path.
- GND pours on both layers are left to the routing task.
