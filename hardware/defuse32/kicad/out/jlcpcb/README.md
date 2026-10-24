# Defuse32 carrier, rev 3 (4 layers): JLCPCB fabrication and assembly files

Written by `../../gen/gen_jlcpcb.py` from the routed and finished board (rev 3: `gen/route_prep.py` + `gen/polish.py`; KiCad DRC clean against the JLCPCB rules in the project). Rev 2.1 (2 layers) files are in git (commit 7412eb7), rev 1b under tag `carrier-rev1b`.

| File | Use |
|---|---|
| `defuse32-carrier-jlcpcb.zip` | Gerbers + drill, zipped flat: upload at jlcpcb.com > Order now |
| `defuse32-carrier-bom.csv` | Assembly BOM (Comment, Designator, Footprint, LCSC, Quantity), SMD parts only |
| `defuse32-carrier-cpl.csv` | Pick-and-place (Designator, Val, Package, Mid X, Mid Y, Rotation, Layer), top-side SMD parts only |
| `gerber/` | The unzipped Gerbers (`-F_Cu.gtl`, `-GND1.g1` = In1.Cu, `-GND2.g2` = In2.Cu, `-B_Cu.gbl`, mask, paste, silkscreen, `-Edge_Cuts.gm1`), drill files and the Gerber job file (layer order and stack-up) |

## PCB order settings

| Setting | Value |
|---|---|
| Base material | FR-4 |
| Layers | **4** |
| Dimensions | 100 x 70 mm (detected from Edge.Cuts) |
| Different designs / delivery format | 1 / single PCB |
| PCB thickness | 1.6 mm |
| **Layer stack-up** | **JLC04161H-7628** (standard, no extra charge): L1 F.Cu 1 oz, 0.2104 mm 7628 prepreg, L2 In1.Cu 0.5 oz, 1.065 mm core, L3 In2.Cu 0.5 oz, 0.2104 mm prepreg, L4 B.Cu 1 oz. The board file carries the same stack-up (Board Setup > Physical Stackup) |
| Layer sequence (if asked) | L1 `-F_Cu.gtl`, L2 `-GND1.g1` (In1.Cu, GND plane), L3 `-GND2.g2` (In2.Cu, GND plane), L4 `-B_Cu.gbl` (KiCad names the inner Gerbers after the layers, GND1 / GND2) |
| Impedance control | **No** (USB full speed, SPI and WS2812 need none) |
| Solder mask / silkscreen | Green / white (any colour works); top silkscreen only carries references (the bottom has none) |
| Surface finish | HASL lead-free (ENIG is nicer for the 0.5 mm-pitch LIS3DH and USB-C, optional) |
| Outer / inner copper weight | 1 oz / 0.5 oz (standard) |
| Via covering | Tented |
| Min via hole / diameter | 0.2 / 0.45 mm (stitching vias) and 0.3 / 0.6 mm (signal vias): standard, no extra charge (JLCPCB charges for 0.15 mm holes, and for 0.2 mm holes only below 0.45 mm diameter) |
| Board outline tolerance | ±0.2 mm (regular) |
| Gold fingers, castellated holes, edge plating, blind/buried vias, via-in-pad | No |
| Mark on PCB (order number) | "Specify a location": the top silkscreen carries the placeholder `JLCJLCJLCJLC` next to the board name |

Design rules (project file + `defuse32-carrier.kicad_dru`, values from JLCPCB's capability page, 2026-10-23; summary in the pcb-layout-pro skill, `references/jlcpcb.md`): tracks 0.2 mm (signals) and 0.6 mm (5V, 3V3, 3V3P, VBUS; 0.25 mm inside the LIS3DH pad field), clearances 0.2 / 0.25 mm (0.15 mm only between items inside the LIS3DH and USB-C courtyards, as their own pads), board minimums 0.1 / 0.1 mm (JLCPCB 4-layer: 0.09 mm), smallest hole 0.2 mm with a 0.45 mm via, via hole to via hole 0.25 mm, pad hole to pad hole 0.45 mm, via hole to track 0.2 mm, PTH hole to track 0.28 mm, inner-layer PTH hole to copper 0.3 mm, copper 0.3 mm or more from the edge, silkscreen text 1.0 mm / 0.15 mm, 0.15 mm from pads. Nothing in the design needs a paid option.

## Assembly (PCBA) settings

| Setting | Value |
|---|---|
| PCBA type | Economic if the order page offers it for this 4-layer board, else Standard |
| Assembly side | Top side |
| PCBA quantity | as ordered (min. 2) |
| Tooling holes | Added by JLCPCB |
| Confirm parts placement | **Yes** |
| Files | BOM `defuse32-carrier-bom.csv`, CPL `defuse32-carrier-cpl.csv` |

All SMD parts are on the top side (single-sided assembly). Coordinates: origin at the board's bottom-left corner, x right, y up, mm; the Gerbers and drill files use the same origin. The BOM/CPL follow the KiCad **JLCPCB Tools** plugin (Bouni/kicad-jlcpcb-tools 2026.04.03): CPL position = centre of each part's pads, rotation = KiCad's plus the plugin's correction for the package. Corrections applied: U1 ESP32-WROOM `+270`, U2/U3/U7 SOIC `+270`, U5/U6 SOT-223 `+180`, Q1-Q3 SOT-23, U4 SOT-23-5 and U9 SOT-23-6 `-90`, J7 HRO TYPE-C-31-M-12 `+180` (the plugin's table, `gen_jlcpcb.JLC_ROTATIONS`).

**Still check the placement preview part by part**, above all the parts the table has no rule for: U8 LIS3DH (LGA-16, pin 1 corner), D1 SOD-323 (cathode = pad 1, to 5V), C1 electrolytic (+ = pad 1), J11 microSD (card slot at the bottom board edge), F1, SW1/SW2, and the corrected ones: U1 (antenna toward the left board edge, off the board), U2/U3/U7 (pin 1 dot), U4/U5/U6/U9, Q1-Q3, J7 (receptacle opening at the right board edge).

**Extended parts** (feeder fee each line): U1 ESP32-WROOM-32E-N4 (C701341), U7 CH340C (C84681), U2/U3 MCP23017-E/SO (C47023), U8 LIS3DHTR (C15134), U4 SN74AHCT1G125DBVR (C7484), U9 USBLC6-2SC6 (C7519), C1 220 µF (C72494), F1 PTC (C18198338), J7 USB-C (C165948), J11 microSD (C114218). Everything else is Basic, including both AMS1117-3.3 (C6186).

## Through-hole parts (not in the BOM/CPL)

Solder by hand, or add them to the JLCPCB order as THT assembly (hand-soldering service, extra cost per joint):

| Refs | Part | LCSC |
|---|---|---|
| J1 | IDC box header 2x5, 2.54 mm, keyed (M1 Radio) | C19193807 |
| J2 | IDC box header 2x6 (M2 Timer) | C18202143 |
| J3 | IDC box header 2x8 (M3 Keypad) | C18202144 |
| J4, J6 | IDC box header 2x10 (M4 Wires, M6 Sensors) | C18202145 |
| J5 | IDC box header 2x7 (M5 Probe) | C19193808 |
| J8 | pin header 1x2 (J_KEY) | C32713268 |
| J9 | pin header 1x3 (J_SERVO: GND, 5V, SIG) | C32713269 |
| J10 | pin header 1x5 (J_SPARE) | C32713271 |

The box-header keys face the nearest board edge (silkscreen outline and pin-1 marker on the edge side). Any keyed 2.54 mm box header with the KiCad IDC-Header footprint fits. Their GND pins connect to both inner planes through thermal reliefs (hand soldering stays easy).

## Regenerate

From `hardware/defuse32/kicad/`, after `gen/polish.py all` and a clean DRC:

```sh
/usr/bin/python3 gen/gen_jlcpcb.py      # [--corrections cpl_rotations_db.csv] for the plugin's full table
```

It runs `kicad-cli pcb export gerbers --subtract-soldermask --check-zones --use-drill-file-origin` (F.Cu, In1.Cu, In2.Cu, B.Cu, paste, silkscreen, mask, Edge.Cuts) and `kicad-cli pcb export drill --format excellon --drill-origin plot --excellon-units mm --excellon-separate-th`, zips `gerber/`, and writes the BOM and CPL from the board footprints and the LCSC numbers in `gen/design.py`.
