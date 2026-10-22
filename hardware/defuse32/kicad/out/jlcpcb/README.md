# Defuse32 carrier, rev 1b: JLCPCB fabrication files

Upload `defuse32-carrier-jlcpcb.zip` (the files in `gerber/`, zipped flat) at jlcpcb.com > Order now.

## Order settings

| Setting | Value |
|---|---|
| Base material | FR-4 |
| Layers | 2 |
| Dimensions | 190 x 140 mm (detected from Edge.Cuts) |
| Different designs | 1 |
| Delivery format | Single PCB |
| PCB thickness | 1.6 mm |
| Solder mask / silkscreen | Green / white (any colour works) |
| Surface finish | HASL lead-free |
| Outer copper weight | 1 oz |
| Via covering | Tented (the Gerbers tent the vias) |
| Min via hole / diameter | 0.3 / 0.6 mm (standard, no extra charge) |
| Board outline tolerance | ±0.2 mm (regular) |
| Gold fingers, castellated holes, edge plating, impedance control | No |
| Assembly (PCBA), stencil | No: THT only, hand-soldered (the paste layers are empty) |

The design stays inside JLCPCB's standard 2-layer capabilities: tracks 0.25 mm (signals) and 0.8 mm (5V, 3V3P, DK_5V, GND), clearances 0.2 / 0.3 mm, smallest hole 0.3 mm (vias), smallest annular ring 0.15 mm, copper 0.3 mm or more from the board edge.

## Files

| File | Layer |
|---|---|
| `defuse32-carrier-F_Cu.gtl`, `-B_Cu.gbl` | Top / bottom copper (GND pours filled) |
| `defuse32-carrier-F_Mask.gts`, `-B_Mask.gbs` | Top / bottom solder mask |
| `defuse32-carrier-F_Silkscreen.gto`, `-B_Silkscreen.gbo` | Top / bottom silkscreen (mask subtracted) |
| `defuse32-carrier-F_Paste.gtp`, `-B_Paste.gbp` | Paste (empty, THT only) |
| `defuse32-carrier-Edge_Cuts.gm1` | Board outline |
| `defuse32-carrier-PTH.drl`, `-NPTH.drl` | Excellon drill, mm, absolute origin: plated holes and vias / the four 3.2 mm mounting holes |
| `defuse32-carrier-job.gbrjob` | Gerber job file |

## Regenerate

From `hardware/defuse32/kicad/`, after refilling the zones and a clean DRC (see `../../README.md`):

```sh
kicad-cli pcb export gerbers -o out/jlcpcb/gerber/ --subtract-soldermask --check-zones \
  --layers F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts defuse32-carrier.kicad_pcb
kicad-cli pcb export drill -o out/jlcpcb/gerber/ --format excellon --drill-origin absolute \
  --excellon-units mm --excellon-zeros-format decimal --excellon-separate-th defuse32-carrier.kicad_pcb
(cd out/jlcpcb/gerber && rm -f ../defuse32-carrier-jlcpcb.zip && zip -j -X ../defuse32-carrier-jlcpcb.zip *)
```
