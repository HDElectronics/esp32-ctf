# Defuse32 carrier PCB, rev 1b (KiCad 10)

The carrier board sits on the case floor. It holds the ESP32-DevKitC socket, the two MCP23017 expanders, the WS2812 buffer, the buzzer driver, the on-board GY-521 IMU, the microSD socket and the peripheral 3.3 V regulator, plus the JST-XH harness connectors to the six plates. The source of truth is [`../SPEC.md`](../SPEC.md), sections "Rev 0 decisions", "Rev 1 changes (2026-10-22)", the "Rev 1b rule" and "Electronics (carrier PCB)".

Status: **rev 1b, routed (2026-10-22).** Autorouted with Freerouting, GND pours stitched, fabrication files in [`out/jlcpcb/`](out/jlcpcb/README.md). ERC is clean, DRC reports 0 violations and 0 unconnected items with the zones refilled, and the schematic and PCB match. The board is now edited by hand in KiCad: see [Routing](#routing-2026-10-22) and [Workflow](#workflow-since-routing).

## Routing (2026-10-22)

- **Router**: Freerouting 2.4.1, headless, through `gen/route_prep.py` (DSN export, Freerouting, SES import, clean-up; the docstring has the exact commands). KiCad 10.0.7 exports the GND pours as planes on the signal layers, so the script drops them from the DSN: Freerouting routes GND as an ordinary Power net, and the pours are refilled afterwards. The `ANTENNA_KEEPOUT` rule area stays a keepout for tracks and vias.
- **First pass**: all 194 connections (Freerouting's count) routed in 7 passes, then 8 optimizer passes (`--router.optimizer.improvement_threshold=0`), which cut the signal vias from 72 to 29.
- **Decoupling fix** (`route_prep.py decap`, after review): C3 and C4 moved next to the MCP23017 VDD/VSS pins 9/10 (pad 1 level with pin 9, pad 2 below), and C5 turned so its GND pad faces U4 pin 12. Each cap gets short, direct 0.8 mm tracks to the supply pins. The script ripped up only the two 3V3P segments the new copper hit and the 14 track pieces left dangling, locked everything else, and an incremental Freerouting pass reconnected 3V3P (7 tracks, 1 via). `gen/design.py` has the new positions.

  | Cap | Supply pin | Track length |
  |---|---|---|
  | C3 (U2) | VDD pin 9 / VSS pin 10 | 4.0 mm / 5.0 mm |
  | C4 (U3) | VDD pin 9 / VSS pin 10 | 5.4 mm / 6.4 mm |
  | C5 (U4) | VCC pin 14 / GND pin 7 | 4.4 mm / 19.8 mm (4.4 mm to GND pin 12, then pins 12-9-7) |

  On the DIP-14, VCC (14) and GND (7) are diagonal and 17 mm apart, so a 5 mm-pitch cap cannot sit within 5 mm of both. C5 stays at pin 14, with its GND pad next to pin 12 (an unused input tied to GND). The U5 caps (C2, C6-C8) were already next to U5.
- **Widths and length**: every Power track (5V, 3V3P, DK_5V, GND) is 0.8 mm and every signal track 0.25 mm. Track length: 3782 mm on F.Cu, 5343 mm on B.Cu, 846 segments.
- **GND**: GND is routed with 0.8 mm tracks and also poured on both layers. Before stitching the router left 71 (F.Cu) and 101 (B.Cu) pour islands that island removal deletes, plus 13 pour pieces held by a single pad. `route_prep.py finish` puts a stitching via (0.6/0.3 mm) in every island of 50 mm² or more and in every single-pad piece, where a via fits inside both that piece and a connected pour on the other layer: 37 in all. Islands left, deleted by island removal: 61 on F.Cu (466 mm² in all, largest 65 mm²) and 86 on B.Cu (580 mm² in all, largest 48 mm²).
- **Hand fix**: U1 pad 20 of the unpopulated clone row (GND) got a single thermal spoke on B.Cu (DRC `starved_thermal`). A 0.8 mm B.Cu stub from the pad and a via at (130, 70) (board coordinates) connect it to the pour (`HAND_FIXES` in `route_prep.py`).
- **Totals**: 68 vias (30 signal, 37 stitching, 1 hand fix). The antenna keepout holds no copper.

## Rev 1b changes (2026-10-22)

MCP23017 GPA7/GPB7 are output-only and cannot go high-impedance, so no keypad or wire-matrix line may use them (SPEC "Rev 1b rule"):

- **Keypad COL4**: U2 GPA7 -> **U2 GPB6** (pin 7).
- **Wire post WA6**: U3 GPA7 -> **U3 GPB6** (pin 7).
- **ENC_SW**: U3 GPB6 -> **ESP32 GPIO39** (U1 pin 4), with the new **R9** (10 kΩ) pull-up to 3V3P. J1_B pin 3 still carries `ENC_SW`. On the board R9 stands vertical at (137.6, 102.2), pad 2 (ENC_SW) 4 mm below U1 pin 4, pad 1 (3V3P) next to C8/C2.
- **MPU-6050 INT**: no longer connected (net `MPU_INT` removed). The GY-521 INT pin (A1 pin 8) has a no-connect flag; firmware polls the MPU over I2C.
- **J_SPARE (J10)**: now a 1x5 header with `U2_GPA7`, `U2_GPB7`, `U3_GPA7`, `U3_GPB7`, GND (nets `SPARE2`/`SPARE3` removed). The pin names and "OUTPUTS ONLY" are on the silkscreen. Same place, pins at y 52-62.2.
- **M2 note**: "TM1637: power from 3V3P" on F.Silkscreen and F.Fab under J2_A/J2_B (and in the schematic under the M2 connectors).
- **Rev and date**: title blocks and board silkscreen say rev 1b, 2026-10-22.

## Rev 1 changes (2026-10-22)

- **microSD (A2)**: a 1x7 female 2.54 mm socket for a 3.3 V-only microSD breakout (Adafruit 4682 style). Pin order `3V GND CLK SO SI CS DET`, with the names on the silkscreen. Nets: 3V3P, GND, SCK (GPIO18), MISO (GPIO19), MOSI (GPIO23), `SD_CS` (GPIO2, U1 pin 34) and `SD_DET` (U2 GPB5, was SPARE1). R8 (10 kΩ) pulls GPIO2 to GND, so the strapping stays valid. The footprint `defuse32:MicroSD_Breakout_Socket` draws the module (25.4 x 22.8 mm, typical) to the left of the header. It sits at the left board edge with the card slot facing outward.
- **Peripheral 3.3 V rail**: U5 LD1117V33 (TO-220 upright, official symbol and footprint) takes `5V` and makes the new net `3V3P`. Input: C6 10 µF + C7 100 nF. Output: C2 10 µF (reused, moved off the old `3V3` net) + C8 100 nF. Every peripheral 3.3 V pin is now on 3V3P:
  - plate connector pin 2 (Jn_A)
  - U2/U3 VDD and RESET, and U3 A0
  - GY-521 VCC and the SD socket
  - the I2C pull-ups R2/R3 and the GPIO35/34 pull-ups R4/R5

  The net `3V3` no longer exists, and the DevKit 3V3 pin (U1 pin 1) carries a no-connect flag. The LDR on M6 is fed from J6_A pin 2 (3V3P), and R6 (GPIO36 to GND) is unchanged. The modules run only when 5 V is on J_PWR.
- **J_SPARE (J10)** became a 1x2 header (SPARE2, SPARE3 = U2 GPB6-7); superseded by rev 1b.
- **Q1** now uses `TO-92_Inline_Wide` (2.54 mm pitch) instead of `TO-92_Inline`. The 1.27 mm pitch pads leave a 0.22 mm gap, which broke the 0.3 mm Power clearance of the GND pad.
- **Routing prep**: the net classes, via size and JLCPCB rules are in `defuse32-carrier.kicad_pro`, which `gen_pcb.py` writes. See [Design rules](#design-rules-for-hand-edits).
- **Rev and date**: title blocks and board silkscreen now say rev 1, 2026-10-22.

## Open it

Open `defuse32-carrier.kicad_pro` in KiCad 10. The project-local libraries are registered in `sym-lib-table` and `fp-lib-table` through `${KIPRJMOD}`:

- `defuse32.kicad_sym` holds three symbols:
  - `ESP32-DevKitC-32E` has 38 pins. Pins 1-19 are header J2 and pins 20-38 are header J3, both counted from the antenna end.
  - `GY-521` has 8 pins: VCC GND SCL SDA XDA XCL AD0 INT.
  - `MicroSD_Breakout_3V3` has 7 pins: 3V GND CLK SO SI CS DET.
- `defuse32.pretty` holds three footprints:
  - `ESP32-DevKitC_Socket`: two 1x19 rows 25.40 mm apart, plus an unpopulated third row 22.86 mm from row 1 for narrow clones. The third row reuses pad numbers 20-38, so it carries the same nets as row 2. The silkscreen shows the DevKit outline, the hatched antenna overhang, the USB arrow and a "clone row" label. The USB edge faces +X. Pin 19 (5V) is 1.29 mm from the USB edge, which is the verified value in `../data/parts.json`.
  - `GY-521_Socket`: a 1x8 female header, with the module outline and its pin names on the silkscreen.
  - `MicroSD_Breakout_Socket`: a 1x7 female header with pin 1 (3V) at the top. The pin names sit to the right of the pads, and the module outline (25.4 x 22.8 mm, typical) and a `CARD` arrow to the left. The courtyard covers the module.

Every other part uses the official KiCad symbols and footprints, so the 3D models come from `${KICAD10_3DMODEL_DIR}`.

## Files

| Path | What |
|---|---|
| `defuse32-carrier.kicad_pro/.kicad_sch/.kicad_pcb` | The project (one A3 schematic sheet; 190 x 140 mm board). The `.kicad_pro` holds the net classes and design rules |
| `defuse32.kicad_sym`, `defuse32.pretty/` | Local symbol and footprint libraries |
| `gen/design.py` | Single source of truth: parts, pin-to-net map, schematic and PCB placement |
| `gen/gen_lib.py` | Writes the local libraries (geometry from `../data/parts.json`) |
| `gen/gen_sch.py` | Writes the schematic: power symbols and global labels on short stubs at the pin ends |
| `gen/gen_pcb.py` | Wrote the project file (net classes, rules) and the unrouted board: footprints, nets from the schematic netlist, GND pours, antenna keepout. **Refuses to run on the routed board** (`--force` overrides and loses the routing) |
| `gen/route_prep.py` | The 2026-10-22 autorouting: DSN export with the KiCad 10.0.7 quirks fixed, SES import, decoupling-cap move with local rip-up, GND stitching vias, hand fix, island report |
| `gen/check_netlist.py` | Checks the schematic netlist (and the PCB pads) against `design.py`, plus the rev 1 rail and microSD nets, the rev 1b pin moves and the net classes |
| `gen/sexp.py`, `gen/symlib.py` | S-expression reader/writer; symbol flattening (`extends`) |
| `out/defuse32-carrier.pdf` | Schematic PDF |
| `out/bom.csv` | BOM grouped by value and footprint (mounting holes excluded) |
| `out/defuse32-carrier.net` | Schematic netlist (`kicad-cli sch export netlist`), input of `check_netlist.py` |
| `out/erc.rpt`, `out/drc.rpt` | Latest check reports |
| `out/jlcpcb/` | Gerbers + Excellon drill files (`gerber/`), the zip to upload, and the JLCPCB order settings ([README](out/jlcpcb/README.md)) |
| `../cad/carrier.step` | STEP of the board with components, for FreeCAD (git-ignored, regenerate) |
| `../renders/carrier-top.png`, `../renders/carrier-iso.png` | 3D renders |

## Workflow since routing

The board is routed and hand-editable, so the generators no longer touch it:

- **Board changes** (moves, track edits): in KiCad's PCB editor. Press `B` to refill the zones before checking.
- **Circuit changes**: edit the schematic (by hand, or `gen/design.py` + `gen_sch.py`), then *Tools > Update PCB from Schematic* in the PCB editor, then route the new connections by hand.
- **Generators**: `gen_lib.py` and `gen_sch.py` are for the library and the schematic only. `gen_pcb.py` stops with a message when the board has tracks; `--force` would regenerate an unrouted board and the default project file, and the routing would be lost. `route_prep.py` documents the autorouting run and starts from an unrouted board.

## Regenerate

Run these from `hardware/defuse32/kicad/`. Scripts that import `pcbnew` need KiCad's Python, which is `/usr/bin/python3`, not conda.

```sh
# library and schematic (only when design.py or parts.json change)
/usr/bin/python3 gen/gen_lib.py && kicad-cli sym upgrade --force defuse32.kicad_sym && kicad-cli fp upgrade --force defuse32.pretty
# fp upgrade gives every footprint new random UUIDs: restore (git) the ones whose geometry you did not change
/usr/bin/python3 gen/gen_sch.py
# then KiCad: Tools > Update PCB from Schematic (do not run gen_pcb.py on the routed board)

# checks
kicad-cli sch export netlist -o out/defuse32-carrier.net defuse32-carrier.kicad_sch
kicad-cli sch erc --severity-all -o out/erc.rpt defuse32-carrier.kicad_sch
kicad-cli pcb drc --schematic-parity --severity-all --refill-zones -o out/drc.rpt defuse32-carrier.kicad_pcb
/usr/bin/python3 gen/check_netlist.py out/defuse32-carrier.net defuse32-carrier.kicad_pcb

# exports
kicad-cli sch export pdf -o out/defuse32-carrier.pdf defuse32-carrier.kicad_sch
kicad-cli sch export bom --fields 'Reference,Value,Footprint,${QUANTITY},Description' \
  --labels 'Refs,Value,Footprint,Qty,Description' --group-by 'Value,Footprint' -o out/bom.csv defuse32-carrier.kicad_sch
kicad-cli pcb export step --force --subst-models -o ../cad/carrier.step defuse32-carrier.kicad_pcb
kicad-cli pcb render --side top --width 1600 --height 1200 --quality high --background opaque \
  -o ../renders/carrier-top.png defuse32-carrier.kicad_pcb
kicad-cli pcb render --perspective --rotate '-55,0,-25' --zoom 0.85 --width 1600 --height 1100 --quality high \
  --background opaque -o ../renders/carrier-iso.png defuse32-carrier.kicad_pcb
# fabrication files: commands in out/jlcpcb/README.md
```

`gen_sch.py` overwrites the `.kicad_sch` file. UUIDs are deterministic, so footprints stay linked to their symbols and *Update PCB from Schematic* matches them.

Last results (rev 1b, routed, zones refilled):

- ERC: `ERC messages: 0 Errors 0 Warnings 0`.
- DRC: `Found 0 violations / Found 0 unconnected items / Found 0 schematic parity issues`.
- `check_netlist.py`: `RESULT: OK` for 47 components and 67 named nets (`netclass Power: 3V3P 5V DK_5V GND`).

## Board

- The outline is 190 x 140 mm, with its top-left corner at page coordinates (50, 40). There are four Ø3.2 NPTH mounting holes (`MountingHole_3.2mm_M3`) 5 mm from the corners.
- The **back edge** (top of the board in KiCad, toward the lid hinge) carries J11/J12, J21/J22 and J31/J32 for plates M1, M2 and M3, left to right. The **front edge** carries J41/J42, J51/J52 and J61/J62 for M4, M5 and M6. Each connector has its SPEC name on the silkscreen (`J1_A  M1 RADIO`, `J1_B`, ...).
- U1 (the DevKit socket) has its USB edge facing the board's right edge, about 13 mm in from it. J7 (J_PWR, wire entry toward the right edge), J9 (J_SERVO) and J8 (J_KEY) sit along the right edge. C1 (470 µF) is near J_SERVO.
- U5 (LD1117V33) stands upright at (158, 100), with its tab toward U1, between U1 and D1 and about 15 mm from J_PWR. The input caps C6/C7 are on the J_PWR side (right) and the output caps C2/C8 on the left. R8 (GPIO2 pull-down) is just above U1 pin 34 (GPIO2).
- A2 (microSD socket) is at the left edge, below A1, with its header at x = 28 and pins at y 92-107. The module body covers about x 6-29, y 87-112. The card slot faces the left board edge, so a card goes in and out without removing anything. It is about 75 mm from the antenna keepout.
- The `ANTENNA_KEEPOUT` rule area covers x 104-129 mm, y 58-92 mm (board coordinates) on both copper layers. It allows no tracks, vias, pads or pour, and covers the overhang plus about 15 mm beyond it. A1 (GY-521) sits at the far left, away from the antenna.
- `GND_F` and `GND_B` pours cover the whole board (0.4 mm clearance, thermal reliefs, island removal "always"), tied together by the GND tracks, the GND pads, 37 stitching vias and the hand-fix via. They are **filled**. Refill them (`B`) after any edit.

### Left to do

1. Review the autorouted board and tweak by hand where wanted. Refill, run DRC, and regenerate `out/jlcpcb/` after any change.
2. Check the T (typical) dimensions against real parts, especially the GY-521 and microSD breakout outlines and the pin positions of narrow DevKit clones.
3. Settle the open questions below.

## Design rules (for hand edits)

Everything is set in `defuse32-carrier.kicad_pro` (*File > Board Setup*). Do not run `gen_pcb.py` again: it would rewrite both the board and the project file.

**Net classes** (*Board Setup > Net Classes*, assigned by pattern):

| Class | Nets | Track | Clearance | Via |
|---|---|---|---|---|
| Power | 5V, 3V3P, GND, DK_5V | 0.8 mm | 0.3 mm | 0.6 / 0.3 mm |
| Default | everything else | 0.25 mm | 0.2 mm | 0.6 / 0.3 mm |

**Design rules** (*Board Setup > Constraints*), matching JLCPCB 2-layer standard capabilities:

| Rule | Minimum |
|---|---|
| Track width | 0.127 mm |
| Clearance | 0.127 mm |
| Through-hole diameter | 0.3 mm |
| Annular ring | 0.13 mm (so the smallest via is 0.56 mm) |
| Hole to hole | 0.5 mm |
| Copper to board edge | 0.3 mm |

The net class values sit well above these minimums. Neck a track down only where a pad row forces it.

**Keepouts**

- The `ANTENNA_KEEPOUT` rule area (x 104-129, y 58-92 in board coordinates) allows no tracks, vias, pads or pour on either layer. Route around the left end of U1.
- Keep the A2 module area (silk outline) free of tall parts.

**Before ordering at JLCPCB**

- Press `B` to refill all zones. Then run DRC with *Refill all zones before performing DRC* and *Test for parity between PCB and schematic* turned on. The target is 0 violations, 0 unconnected items and 0 parity issues.
- Regenerate the Gerbers, drill files and zip with the commands in [`out/jlcpcb/README.md`](out/jlcpcb/README.md), which also lists the order settings (2 layers, 1.6 mm, 1 oz, lead-free HASL, tented vias).

## Pin and connector table (cross-checked against SPEC.md)

KiCad's annotation check rejects references that don't end in a digit (`J1_A`, `J_PWR`), and *Update PCB* refuses an unannotated schematic. The connectors therefore use numeric references, and the SPEC name is the first word of each Value and appears on the silkscreen:

| SPEC | KiCad ref | Footprint | Pins (1 to n) |
|---|---|---|---|
| J1_A ... J6_A | J11, J21, J31, J41, J51, J61 | JST-XH B7B | 5V, 3V3P, GND, SDA, SCL, LDI, LDO |
| J1_B (M1 Radio) | J12 | XH B3B | ENC_A, ENC_B, ENC_SW (GPIO39 since rev 1b) |
| J2_B (M2 Timer) | J22 | XH B4B | TM_CLK, TM_DIO, BUZZ-, BUZZ+ (= 5V) |
| J3_B (M3 Keypad) | J32 | XH B8B | ROW1-4, COL1-4 |
| J4_B (M4 Wires) | J42 | XH B12B | WA1-6, WB1-6 |
| J5_B (M5 Probe) | J52 | XH B6B | U2TX, U2RX, SCK, MOSI, MISO, CS |
| J6_B (M6 Sensors) | J62 | XH B11B | T0, T4, T6, T3, LDR, IR, SIM1-4, SERVO_SIG |
| J_PWR | J7 | Phoenix MKDS 5.08 2-pin | 5V, GND |
| J_KEY | J8 | XH B2B | KEY (U2 GPB4), GND |
| J_SERVO | J9 | 1x3 2.54 header | GND, 5V, SERVO_SIG (see question 2) |
| J_SPARE | J10 | 1x5 2.54 header | U2_GPA7, U2_GPB7, U3_GPA7, U3_GPB7, GND (rev 1b; outputs only) |
| microSD (rev 1) | A2 | 1x7 2.54 female socket | 3V (3V3P), GND, CLK (SCK), SO (MISO), SI (MOSI), CS (SD_CS), DET (SD_DET) |
| 3V3P regulator (rev 1) | U5 | TO-220-3 vertical | 1 GND, 2 VO (3V3P), 3 VI (5V) |

WS2812 chain: U4 gate 1 (1A = WS_DATA from GPIO25, ~1OE to GND) → 1Y (WS_5V) → R1 330 Ω → `LDI` (J11 pin 6). After that, M1 LDO = `LDO1` → M2 LDI, and so on up to `LDO5` → M6 LDI. M6 LDO (J61 pin 7) is the end of the chain and carries a no-connect flag.

ESP32 (U1) pin numbers: J2 header = 1-19, J3 header = 20-38.

| GPIO | Net | U1 pin | | GPIO | Net | U1 pin |
|---|---|---|---|---|---|---|
| 21 | SDA | 25 (J3-6) | | 4 | T0 | 32 (J3-13) |
| 22 | SCL | 22 (J3-3) | | 13 | T4 | 15 (J2-15) |
| 35 | MCP_INT (10k pull-up R4) | 6 (J2-6) | | 14 | T6 | 12 (J2-12) |
| 39 | ENC_SW (10k pull-up R9, rev 1b) | 4 (J2-4) | | 15 | T3 | 35 (J3-16) |
| 34 | IR (10k pull-up R5) | 5 (J2-5) | | 18 | SCK | 28 (J3-9) |
| 36 | LDR (10k R6 to GND) | 3 (J2-3) | | 23 | MOSI | 21 (J3-2) |
| 32 | TM_CLK | 7 (J2-7) | | 19 | MISO | 27 (J3-8) |
| 33 | TM_DIO | 8 (J2-8) | | 5 | CS | 29 (J3-10) |
| 25 | WS_DATA (to U4) | 9 (J2-9) | | 17 | U2TX | 30 (J3-11) |
| 26 | BUZZ (R7 1k to Q1) | 10 (J2-10) | | 16 | U2RX | 31 (J3-12) |
| 27 | SERVO_SIG | 11 (J2-11) | | 2 | SD_CS (10k pull-down R8) | 34 (J3-15) |
| | | | | 3V3 / 5V / GND | NC / DK_5V / GND | 1 / 19 / 14, 20, 26 |

These pins have no-connect flags: GPIO 12 (strapping), EN, GPIO 0, 1, 3, GPIO 6-11 and the DevKit 3V3 pin. GPIO2 is SD_CS with R8 to GND, so it is low at reset, as the strapping needs. D1 (1N5822) runs from the 5V rail (anode) to `DK_5V` (cathode, DevKit 5V pin). The DevKit's own LDO powers only the ESP32. U5 makes `3V3P` for everything else on the carrier and the plates.

MCP23017:

- **U2 (0x20)**: A0-A2 to GND. GPA0-3 = ROW1-4, GPA4-6 = COL1-3, GPB6 = COL4 (rev 1b), GPB0-3 = SIM1-4, GPB4 = KEY, GPB5 = SD_DET, GPA7 / GPB7 = `U2_GPA7` / `U2_GPB7` to J_SPARE.
- **U3 (0x21)**: A0 to 3V3P, A1-A2 to GND. GPA0-4 = WA1-5, GPB6 = WA6 (rev 1b), GPA6 = ENC_A, GPA5 = ENC_B, GPB0-5 = WB1-6, GPA7 / GPB7 = `U3_GPA7` / `U3_GPB7` to J_SPARE. ENC_SW is on GPIO39 since rev 1b.
- **Rev 1b rule**: GPA7/GPB7 are output-only on current MCP23017 silicon and cannot go high-impedance, so no keypad or wire-matrix line uses them; all four go to J_SPARE.
- **Both**: VDD and RESET are on 3V3P. INTA and INTB go to MCP_INT, and firmware sets them to mirrored, open-drain.

Passives:

- **Decoupling**: C3 and C4 (100 nF, 3V3P) for U2 and U3, C5 (100 nF, 5V) for U4, C1 (470 µF/10 V) on 5V.
- **U5 rail**: C6 (10 µF) + C7 (100 nF) on the 5V input, C2 (10 µF) + C8 (100 nF) on the 3V3P output.
- **Pull-ups and pull-downs**: R2 and R3 (4.7 kΩ) pull SDA and SCL up to 3V3P. R4, R5 and R9 (10 kΩ) pull MCP_INT (GPIO35), IR (GPIO34) and ENC_SW (GPIO39, rev 1b) up to 3V3P. R8 (10 kΩ) pulls SD_CS (GPIO2) down.
- **Unused U4 gates 2-4**: A inputs to GND, ~OE to 5V (outputs disabled).
- **Buzzer driver**: Q1 2N3904, emitter to GND, collector to BUZZ-. D2 1N4148 has its anode on BUZZ- and its cathode on 5V.

A1 (GY-521) takes VCC from 3V3P. Its own LDO and I2C pull-ups still work at that voltage, and it never sees the 5 V rail. AD0 goes to GND, so the address is 0x68. INT, XDA and XCL have no-connect flags (INT since rev 1b: firmware polls the MPU over I2C).

## Open questions and SPEC deviations

1. **MCP23017 GPA7/GPB7 output-only** (current datasheet DS20001952): resolved in rev 1b. No keypad or wire-matrix line uses GPA7/GPB7 (COL4 and WA6 on GPB6, ENC_SW on GPIO39); all four go to J_SPARE as outputs.
2. **Servo pin order.** SPEC lists J_SERVO as "5V, GND, SIG". A standard SG90 plug is GND-5V-SIG, with V+ in the middle, so J9 uses GND, 5V, SIG to let the plug fit without swapping pins. Please confirm.
3. **References**: SPEC names map to numeric references, as shown in the connector table above.
4. **J_SPARE**: since rev 1b, four output-only signals (U2/U3 GPA7, GPB7) plus GND, no 3V3P.
5. **DK_5V in the Power class (rev 1)**: SPEC lists 5V, 3V3P and GND. `DK_5V` (D1 cathode to the DevKit 5V pin) carries the whole ESP32 supply, so it is in `Power` too. To undo this, remove its pattern in *Board Setup > Net Classes*, or from `POWER_NETS` in `gen/gen_pcb.py`.
6. **microSD module outline (rev 1)**: the 25.4 x 22.8 mm size comes from a distributor listing for Adafruit 4682, not from Adafruit. Before ordering, check that the card slot is on the side away from the header. If it is not, turn A2 by 180° and move it so the slot still faces the edge.
7. **U5 heat (rev 1)**: U5 dissipates (5 - 3.3) V x the load current. At about 300 mA (PN532, two OLEDs, SD writes) that is about 0.5 W, which an upright TO-220 handles without a heatsink (about +25 °C).
