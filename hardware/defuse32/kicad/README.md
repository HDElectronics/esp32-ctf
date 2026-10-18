# Defuse32 carrier PCB, rev 0 (KiCad 10)

The carrier board sits on the case floor. It holds the ESP32-DevKitC socket, the two MCP23017 expanders, the WS2812 buffer, the buzzer driver and the on-board GY-521 IMU, plus the JST-XH harness connectors to the six plates. The source of truth is [`../SPEC.md`](../SPEC.md), sections "Rev 0 decisions" and "Electronics (carrier PCB)".

Status: **schematic complete, all parts placed, board unrouted (ratsnest only)**. ERC is clean, DRC reports only unconnected items, and the schematic and PCB match.

## Open it

Open `defuse32-carrier.kicad_pro` in KiCad 10. The project-local libraries are registered in `sym-lib-table` and `fp-lib-table` through `${KIPRJMOD}`:

- `defuse32.kicad_sym` holds two symbols. `ESP32-DevKitC-32E` has 38 pins: pins 1-19 are header J2 and pins 20-38 are header J3, both counted from the antenna end. `GY-521` has 8 pins: VCC GND SCL SDA XDA XCL AD0 INT.
- `defuse32.pretty` holds two footprints:
  - `ESP32-DevKitC_Socket`: two 1x19 rows 25.40 mm apart, plus an unpopulated third row 22.86 mm from row 1 for narrow clones. The third row reuses pad numbers 20-38, so it carries the same nets as row 2. The silkscreen shows the DevKit outline, the hatched antenna overhang, the USB arrow and a "clone row" label. The USB edge faces +X. Pin 19 (5V) is 1.29 mm from the USB edge, which is the verified value in `../data/parts.json`.
  - `GY-521_Socket`: a 1x8 female header, with the module outline and its pin names on the silkscreen.

Every other part uses the official KiCad symbols and footprints, so the 3D models come from `${KICAD10_3DMODEL_DIR}`.

## Files

| Path | What |
|---|---|
| `defuse32-carrier.kicad_pro/.kicad_sch/.kicad_pcb` | The project (one A3 schematic sheet; 190 x 140 mm board) |
| `defuse32.kicad_sym`, `defuse32.pretty/` | Local symbol and footprint libraries |
| `gen/design.py` | Single source of truth: parts, pin-to-net map, schematic and PCB placement |
| `gen/gen_lib.py` | Writes the local libraries (geometry from `../data/parts.json`) |
| `gen/gen_sch.py` | Writes the schematic: power symbols and global labels on short stubs at the pin ends |
| `gen/gen_pcb.py` | Writes the board: places the footprints, takes the nets from the schematic netlist, adds the GND pours and the antenna keepout, fills the zones |
| `gen/check_netlist.py` | Checks the schematic netlist (and the PCB pads) against `design.py` |
| `gen/sexp.py`, `gen/symlib.py` | S-expression reader/writer; symbol flattening (`extends`) |
| `out/defuse32-carrier.pdf` | Schematic PDF |
| `out/bom.csv` | BOM grouped by value and footprint (mounting holes excluded) |
| `out/defuse32-carrier.net` | Netlist exported by `gen_pcb.py` |
| `out/erc.rpt`, `out/drc.rpt` | Latest check reports |
| `../cad/carrier.step` | STEP of the board with components, for FreeCAD |
| `../renders/carrier-top.png`, `../renders/carrier-iso.png` | 3D renders |

## Regenerate

Run these from `hardware/defuse32/kicad/`. The PCB script needs KiCad's Python, which is `/usr/bin/python3`, not conda.

```sh
/usr/bin/python3 gen/gen_lib.py && kicad-cli sym upgrade --force defuse32.kicad_sym && kicad-cli fp upgrade --force defuse32.pretty
/usr/bin/python3 gen/gen_sch.py
/usr/bin/python3 gen/gen_pcb.py            # also exports out/defuse32-carrier.net

# checks
kicad-cli sch erc --severity-all -o out/erc.rpt defuse32-carrier.kicad_sch
kicad-cli pcb drc --schematic-parity --severity-all -o out/drc.rpt defuse32-carrier.kicad_pcb
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
```

`gen_sch.py` and `gen_pcb.py` overwrite the `.kicad_sch` and `.kicad_pcb` files. UUIDs are deterministic, so footprints stay linked to their symbols. Once routing starts in the GUI, stop running `gen_pcb.py`. Change the schematic (or `design.py` + `gen_sch.py`) and use *Tools > Update PCB from Schematic* instead.

Last results: `ERC messages: 0 Errors 0 Warnings 0`. DRC: `Found 0 DRC violations / Found 140 unconnected pads / Found 0 Footprint errors`, with 0 schematic parity issues. `check_netlist.py` returns `RESULT: OK` for 40 components and 65 named nets.

## Board

- The outline is 190 x 140 mm, with its top-left corner at page coordinates (50, 40). There are four Ø3.2 NPTH mounting holes (`MountingHole_3.2mm_M3`) 5 mm from the corners.
- The **back edge** (top of the board in KiCad, toward the lid hinge) carries J11/J12, J21/J22 and J31/J32 for plates M1, M2 and M3, left to right. The **front edge** carries J41/J42, J51/J52 and J61/J62 for M4, M5 and M6. Each connector has its SPEC name on the silkscreen (`J1_A  M1 RADIO`, `J1_B`, ...).
- U1 (the DevKit socket) has its USB edge facing the board's right edge, about 13 mm in from it. J7 (J_PWR, wire entry toward the right edge), J9 (J_SERVO) and J8 (J_KEY) sit along the right edge. C1 (470 µF) is near J_SERVO.
- The `ANTENNA_KEEPOUT` rule area covers x 104-129 mm, y 58-92 mm (board coordinates) on both copper layers. It allows no tracks, vias, pads or pour, and covers the overhang plus about 15 mm beyond it. A1 (GY-521) sits at the far left, away from the antenna.
- `GND_F` and `GND_B` pours cover the whole board (0.4 mm clearance, thermal reliefs) and are filled.

### Left to do

1. Route the board (no autorouter on this machine). Suggested order: 5V and GND power first (0.8-1 mm), then I2C, then the rest. Join the clone-row pads to row 2. The 19 clone-row links are part of the 140 unconnected items.
2. Refill the zones, run DRC again, then make the fab outputs (Gerbers and drill files).
3. Check the T (typical) dimensions against real parts, especially the GY-521 outline and the pin positions of narrow DevKit clones.
4. Settle the open questions below.

## Pin and connector table (cross-checked against SPEC.md)

KiCad's annotation check rejects references that don't end in a digit (`J1_A`, `J_PWR`), and *Update PCB* refuses an unannotated schematic. The connectors therefore use numeric references, and the SPEC name is the first word of each Value and appears on the silkscreen:

| SPEC | KiCad ref | Footprint | Pins (1 to n) |
|---|---|---|---|
| J1_A ... J6_A | J11, J21, J31, J41, J51, J61 | JST-XH B7B | 5V, 3V3, GND, SDA, SCL, LDI, LDO |
| J1_B (M1 Radio) | J12 | XH B3B | ENC_A, ENC_B, ENC_SW |
| J2_B (M2 Timer) | J22 | XH B4B | TM_CLK, TM_DIO, BUZZ-, BUZZ+ (= 5V) |
| J3_B (M3 Keypad) | J32 | XH B8B | ROW1-4, COL1-4 |
| J4_B (M4 Wires) | J42 | XH B12B | WA1-6, WB1-6 |
| J5_B (M5 Probe) | J52 | XH B6B | U2TX, U2RX, SCK, MOSI, MISO, CS |
| J6_B (M6 Sensors) | J62 | XH B11B | T0, T4, T6, T3, LDR, IR, SIM1-4, SERVO_SIG |
| J_PWR | J7 | Phoenix MKDS 5.08 2-pin | 5V, GND |
| J_KEY | J8 | XH B2B | KEY (U2 GPB4), GND |
| J_SERVO | J9 | 1x3 2.54 header | GND, 5V, SERVO_SIG (see question 2) |
| J_SPARE | J10 | 1x3 2.54 header | SPARE1-3 = U2 GPB5, GPB6, GPB7 |

WS2812 chain: U4 gate 1 (1A = WS_DATA from GPIO25, ~1OE to GND) → 1Y (WS_5V) → R1 330 Ω → `LDI` (J11 pin 6). After that, M1 LDO = `LDO1` → M2 LDI, and so on up to `LDO5` → M6 LDI. M6 LDO (J61 pin 7) is the end of the chain and carries a no-connect flag.

ESP32 (U1) pin numbers: J2 header = 1-19, J3 header = 20-38.

| GPIO | Net | U1 pin | | GPIO | Net | U1 pin |
|---|---|---|---|---|---|---|
| 21 | SDA | 25 (J3-6) | | 4 | T0 | 32 (J3-13) |
| 22 | SCL | 22 (J3-3) | | 13 | T4 | 15 (J2-15) |
| 35 | MCP_INT (10k pull-up R4) | 6 (J2-6) | | 14 | T6 | 12 (J2-12) |
| 39 | MPU_INT | 4 (J2-4) | | 15 | T3 | 35 (J3-16) |
| 34 | IR (10k pull-up R5) | 5 (J2-5) | | 18 | SCK | 28 (J3-9) |
| 36 | LDR (10k R6 to GND) | 3 (J2-3) | | 23 | MOSI | 21 (J3-2) |
| 32 | TM_CLK | 7 (J2-7) | | 19 | MISO | 27 (J3-8) |
| 33 | TM_DIO | 8 (J2-8) | | 5 | CS | 29 (J3-10) |
| 25 | WS_DATA (to U4) | 9 (J2-9) | | 17 | U2TX | 30 (J3-11) |
| 26 | BUZZ (R7 1k to Q1) | 10 (J2-10) | | 16 | U2RX | 31 (J3-12) |
| 27 | SERVO_SIG | 11 (J2-11) | | 3V3 / 5V / GND | 3V3 / DK_5V / GND | 1 / 19 / 14, 20, 26 |

GPIO 2 and 12 (strapping), EN, GPIO 0, 1, 3 and GPIO 6-11 have no-connect flags. D1 (1N5822) runs from the 5V rail (anode) to `DK_5V` (cathode, DevKit 5V pin). The DevKit's own LDO provides `3V3` for the carrier.

MCP23017:

- **U2 (0x20)**: A0-A2 to GND. GPA0-3 = ROW1-4, GPA4-7 = COL1-4, GPB0-3 = SIM1-4, GPB4 = KEY, GPB5-7 = SPARE1-3.
- **U3 (0x21)**: A0 to 3V3, A1-A2 to GND. GPA0-4 = WA1-5, GPA7 = WA6, GPA6 = ENC_A, GPA5 = ENC_B, GPB0-5 = WB1-6, GPB6 = ENC_SW, GPB7 = spare (no-connect flag). GPA7/GPB7 are output-only on current MCP23017 silicon, so they carry only an output (WA6) or nothing (`FIX_U3_GPA7 = True` in `gen/design.py`).
- **Both**: RESET is tied straight to 3V3. INTA and INTB go to MCP_INT, and firmware sets them to mirrored, open-drain.

Passives:

- **Decoupling**: C3 and C4 (100 nF, 3V3) for U2 and U3, C5 (100 nF, 5V) for U4, C2 (10 µF) on 3V3, C1 (470 µF/10 V) on 5V.
- **Pull-ups**: R2 and R3 (4.7 kΩ) pull SDA and SCL up to 3V3.
- **Unused U4 gates 2-4**: A inputs to GND, ~OE to 5V (outputs disabled).
- **Buzzer driver**: Q1 2N3904, emitter to GND, collector to BUZZ-. D2 1N4148 has its anode on BUZZ- and its cathode on 5V.

A1 (GY-521) takes VCC from 3V3. Its own LDO and I2C pull-ups still work at that voltage, and it never sees the 5 V rail. AD0 goes to GND, so the address is 0x68, and INT goes to MPU_INT. XDA and XCL have no-connect flags.

## Open questions and SPEC deviations

1. **MCP23017 GPA7/GPB7 output-only** (current datasheet DS20001952): resolved in SPEC and in the schematic. U3 GPA7 carries WA6 (an output), ENC_B is on GPA5, U3 GPB7 is a spare. On U2, COL4 on GPA7 works only if firmware drives the columns and reads the rows; SPARE3 (GPB7) is output-only.
2. **Servo pin order.** SPEC lists J_SERVO as "5V, GND, SIG". A standard SG90 plug is GND-5V-SIG, with V+ in the middle, so J9 uses GND, 5V, SIG to let the plug fit without swapping pins. Please confirm.
3. **References**: SPEC names map to numeric references, as shown in the connector table above.
4. J_SPARE follows SPEC: three signal pins, with no GND or 3V3. U3 GPB7, the second spare, carries a no-connect flag.
