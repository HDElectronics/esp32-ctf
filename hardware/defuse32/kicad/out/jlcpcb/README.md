# Defuse32 carrier, rev 2.1: JLCPCB fabrication and assembly files

Written by `../../gen/gen_jlcpcb.py` from the routed and finished board (rev 2.1: `gen/polish.py`; DRC clean, silkscreen rules included). Rev 1b files are in git (tag `carrier-rev1b`).

| File | Use |
|---|---|
| `defuse32-carrier-jlcpcb.zip` | Gerbers + drill, zipped flat: upload at jlcpcb.com > Order now |
| `defuse32-carrier-bom.csv` | Assembly BOM (JLCPCB format: Comment, Designator, Footprint, LCSC Part #), SMD parts only |
| `defuse32-carrier-cpl.csv` | Pick-and-place (Designator, Mid X, Mid Y, Layer, Rotation), top-side SMD parts only |
| `gerber/` | The unzipped Gerbers and drill files |

## PCB order settings

| Setting | Value |
|---|---|
| Base material | FR-4 |
| Layers | 2 |
| Dimensions | 100 x 70 mm (detected from Edge.Cuts) |
| Different designs / delivery format | 1 / single PCB |
| PCB thickness | 1.6 mm |
| Solder mask / silkscreen | Green / white (any colour works); silkscreen on both sides (7 references are on the bottom) |
| Surface finish | HASL lead-free (ENIG is nicer for the 0.5 mm-pitch LIS3DH and USB-C, optional) |
| Outer copper weight | 1 oz |
| Via covering | Tented |
| Min via hole / diameter | 0.3 / 0.6 mm (standard, no extra charge) |
| Board outline tolerance | ±0.2 mm (regular) |
| Gold fingers, castellated holes, edge plating, impedance control | No |
| Mark on PCB (order number) | "Specify a location": the top silkscreen carries the placeholder `JLCJLCJLCJLC` (top left, above the board name); otherwise "Remove" if offered |

Design rules used: tracks 0.2 mm (signals) and 0.6 mm (5V, 3V3, 3V3P, VBUS, GND; 0.25 mm inside the LIS3DH pad field), clearances 0.2 / 0.25 mm (0.15 mm only between items inside the LIS3DH and USB-C courtyards, as their own pads), smallest hole 0.3 mm (vias), via ring 0.15 mm, copper 0.3 mm or more from the board edge. All inside JLCPCB's standard 2-layer capabilities.

## Assembly (PCBA) settings

| Setting | Value |
|---|---|
| PCBA type | Economic (or Standard) |
| Assembly side | Top side |
| PCBA quantity | as ordered (min. 2) |
| Tooling holes | Added by JLCPCB (or none needed for Economic) |
| Confirm parts placement | **Yes** |
| Files | BOM `defuse32-carrier-bom.csv`, CPL `defuse32-carrier-cpl.csv` |

All SMD parts are on the top side (single-sided assembly). Coordinates: origin at the board's bottom-left corner, x right, y up, mm; the Gerbers and drill files use the same origin.

**Check the rotation preview part by part.** The CPL rotations are KiCad's (counter-clockwise). JLCPCB's library models often have a different zero orientation, so some parts show up turned in the placement preview and need a correction there (typical: SOT-23 / SOT-23-5 / SOT-23-6 / SOT-223 and the electrolytic C1 +180°, SOIC / LGA +-90°, USB-C and microSD sometimes 180°). Check at least: pin 1 of U1 (WROOM-32E: antenna toward the left board edge, off the board), U2/U3/U7 (SOIC pin 1 dot), U8 (LIS3DH pin 1 corner), U4/U5/U6/U9, Q1-Q3, D1 (cathode = pad 1, to 5V), C1 (+ = pad 1), J7 (receptacle opening at the right board edge), J11 (card slot at the bottom board edge), F1, SW1/SW2.

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

The box-header keys face the nearest board edge (silkscreen outline and pin-1 marker on the edge side). Any keyed 2.54 mm box header with the KiCad IDC-Header footprint fits.

## Regenerate

From `hardware/defuse32/kicad/`, after `gen/polish.py all` (or `gen/route_prep.py finish`) and a clean DRC:

```sh
/usr/bin/python3 gen/gen_jlcpcb.py
```

It runs `kicad-cli pcb export gerbers --subtract-soldermask --check-zones --use-drill-file-origin` (F/B copper, paste, silkscreen, mask, Edge.Cuts) and `kicad-cli pcb export drill --format excellon --drill-origin plot --excellon-units mm --excellon-separate-th`, zips `gerber/`, and writes the BOM and CPL from the board footprints and the LCSC numbers in `gen/design.py`.
