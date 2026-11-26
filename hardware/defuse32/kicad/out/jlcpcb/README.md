# Defuse32 carrier, rev 3.1 (4 layers): JLCPCB fabrication and assembly files

Written by `../../gen/gen_jlcpcb.py` from the routed and finished board (rev 3.1: `gen/route_prep.py` + `gen/polish.py` + `gen/std_fixes.py`, the standards pass of 2026-11-25; KiCad DRC clean against the JLCPCB rules in the project). The board and the Gerbers say **rev 3.1  2026-11**; do not mix these files with the rev 3 package (commit 2b482c1). Rev 2.1 (2 layers) files are in git (commit 7412eb7), rev 1b under tag `carrier-rev1b`.

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
| Surface finish | **ENIG** recommended (flat pads for the 0.5 mm-pitch LGA-16 LIS3DH that JLCPCB X-rays, and the USB-C); HASL lead-free works |
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
| PCBA type | **Standard**. JLCPCB lists U1 ESP32-WROOM-32E-N4 (C701341), U8 LIS3DHTR (C15134, X-ray inspection required) and C1 220 µF (C72494) as "Standard Only" (part pages read 2026-11-25). Economic PCBA cannot take this BOM |
| Assembly side | Top side |
| PCBA quantity | as ordered (min. 2) |
| Edge rails | **5 mm rails on the top and bottom (100 mm) edges only, added by JLCPCB**, joined by V-cut or stamp holes as JLCPCB prefers: the board is laid out for a V-cut on those two edges (every track, via and all four GND pours stay 0.5 mm or more inside them; JLCPCB asks for 0.4 mm from the cut line; the one exception is J11's four GND shell pads, 0.475 mm from the bottom edge, which cannot move). Keep the left and right edges free: U1's module body (antenna end) overhangs the left edge by 6.2 mm and the USB-C receptacle J7 overhangs the right edge by 0.6 mm (so a plug's body clears the board edge). Ask JLCPCB's engineers to confirm the overhang before production |
| Fiducials | On the rails, added by JLCPCB. The board also carries three global fiducials (1 mm copper, 2 mm mask opening; board-only footprints FID1-FID3, not in the BOM/CPL, no reference printed: a fiducial is not a part): FID1 (3.90, 48.70), FID2 (90.30, 65.20), FID3 (94.80, 8.60) mm from the bottom-left corner (centres). Each centre is 3.9 mm or more from every board edge (JLCPCB asks for 3.85 mm from the panel edge), with or without the rails |
| Tooling holes | Added by JLCPCB (on the rails) |
| Confirm parts placement | **Yes** |
| Files | BOM `defuse32-carrier-bom.csv`, CPL `defuse32-carrier-cpl.csv` |

All SMD parts are on the top side (single-sided assembly). Coordinates: origin at the board's bottom-left corner, x right, y up, mm; the Gerbers and drill files use the same origin. The BOM/CPL follow the KiCad **JLCPCB Tools** plugin (Bouni/kicad-jlcpcb-tools 2026.04.03): CPL position = centre of each part's pads, rotation = KiCad's plus a correction per part (`gen_jlcpcb.JLC_ROTATIONS`).

### CPL rotations

**JLCPCB's placement preview is the authority, and it has not been seen for this board.** The table below is the best prediction that can be made without it: for every polarised or multi-pin SMD part, the footprint JLCPCB / LCSC publish for that exact LCSC number (fetched 2026-11-25 with easyeda2kicad 1.0.1) was laid over the board's pads; the rotation, counter-clockwise seen from the top, that puts every pad of the LCSC footprint on the pad of the same name is the angle the CPL must carry (assumption: JLCPCB's 0° is that footprint as drawn; "high" below means the comparison is unambiguous and the plugin's table, which users built from JLCPCB previews, gives the same angle; "medium" means the comparison is unambiguous but a public table says otherwise). The plugin's package table gives the same angle for the SOIC, SOT-223, ESP32 and SOT-23-6 parts; it is wrong for the SOT-23 / SOT-23-5 parts and the USB-C receptacle of this BOM, and has no row for C1, so those go by rules on the reference.

| Part | LCSC | LCSC footprint | KiCad angle | CPL angle | Method: pads matched | Confidence |
|---|---|---|---|---|---|---|
| C1 220 µF | C72494 | CAP-SMD_BD6.3-L6.6-W6.6-FD | 0 | **0** | 2 of 2 by name, within 0.13 mm | medium: the comparison is unambiguous (pad 1 = + on the same side in both footprints), but the public rotation tables turn every `CP_Elec` by 180° (right for the 8 mm cans, whose LCSC footprint is mirrored: checked on C134502). A 180° error reverses the capacitor: check it first |
| J7 USB-C | C165948 | USB-C_SMD-TYPE-C-31-M-12_1 | 90 | **90** | 8 of 8 by name, 0.00 mm | medium: unambiguous comparison, against the plugin's row for this footprint name (+180, which gave 270 in rev 3 and in the first rev 3.1 file); LCSC's footprint carries a "_1" suffix, so it was probably redrawn since that row was written |
| Q1 SS8050 | C2150 | SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR | 0 | **180** | 3 of 3 by name, 0.12 mm | medium: unambiguous comparison; the public tables disagree for SOT-23 (-90 or 180); was 270 (plugin row -90) |
| Q2, Q3 MMBT3904 | C20526 | SOT-23-3_L2.9-W1.3-P1.90-LS2.4-BR | 0 | **180** | 3 of 3 by name, 0.12 mm | medium, as Q1; was 270 |
| U4 SN74AHCT1G125 | C7484 | SOT-23-5_L3.0-W1.7-P0.95-LS2.8-BR | 0 | **180** | 5 of 5 by name, 0.32 mm | medium, as Q1; was 270 |
| U9 USBLC6-2SC6 | C7519 | SOT-23-6_L2.9-W1.6-P0.95-LS2.8-BL | 0 | 270 | 6 of 6 by name, 0.01 mm | high (plugin row -90 agrees) |
| D1 1N4148WS | C2128 | SOD-323_L1.8-W1.3-LS2.5-RD | 90 | 90 | 2 of 2 by name, 0.12 mm | high (pad 1 = cathode in both) |
| U5, U6 AMS1117-3.3 | C6186 | SOT-223-3_L6.5-W3.4-P2.30-LS7.0-BR | 180 | 0 | pins 1 and 3 by name, 0.00 mm (KiCad names the tab "2" as well) | high (plugin row +180 agrees) |
| U7 CH340C | C84681 | SOP-16_L10.0-W3.9-P1.27-LS6.0-BL | 90 | 0 | 16 of 16 by name, 0.40 mm | high (plugin row +270 agrees) |
| U2, U3 MCP23017 | C47023 | SOIC-28_L18.0-W7.5-P1.27-LS10.3-BL | 90 | 0 | 28 of 28 by name, 0.41 mm | high (plugin row +270 agrees) |
| U8 LIS3DH | C15134 | LGA-16_L3.0-W3.0-P0.50-TL | 0 | 0 | 16 of 16 by name, 0.18 mm | high (no plugin row) |
| U1 ESP32-WROOM-32E | C701341 | WIFI-SMD_ESP32-WROOM-32E | 90 | 0 | 38 of 38 by name, 0.25 mm | high (plugin row +270 agrees) |
| J11 microSD | C114218 | SD-SMD_DM3AT-SF-PEJM5 | 0 | 0 | contacts 1-9 by name, 0.00 mm (the shell pads are named differently) | high (no plugin row) |
| SW1, SW2 TS-1187A | C318884 | SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5 | 0 | 0 | 4 of 4 by position, 0.02 mm | high; 0 and 180 are the same part (two joined pairs) |
| F1 PTC 1812 | C18198338 | F1812 | 270 | 270 | 2 of 2 by name, 0.29 mm | not polarised: 90 and 270 are the same part |
| resistors, ceramic capacitors | | 0603 / 0805 | | KiCad's | two pads, not polarised | any 180° turn is the same part |

Corrections applied by `gen_jlcpcb.py`: rules on the reference first (Q1-Q3 `+180`, U4 `+180`, J7 `+0`), then the plugin's package rows (U1 ESP32-WROOM `+270`, U2 / U3 / U7 SOIC `+270`, U5 / U6 SOT-223 `+180`, U9 SOT-23-6 `-90`); C1 and every other part go with KiCad's angle. The comparison script and the fetched footprints are not in the repository; to repeat the check, fetch each LCSC number with `easyeda2kicad --footprint --lcsc_id Cxxxx` and lay its pads over the board's.

**Parts closer to the edge than JLCPCB's 2.5 mm** (assembly terms §2.3), all on the left / right / bottom edges and by design: U1 (antenna end overhangs the left edge), C9 / C10 (module 3V3 decoupling at U1 pin 2, pads 0.55 / 0.77 mm from the left edge), J7 (receptacle face 0.6 mm past the right edge), J11 (microSD card slot 0.7 mm inside the bottom edge; courtyard 0.12 mm past it). With rails on the top and bottom edges only, the left and right edges stay free; J11 sits next to the bottom rail (its slot faces the rail until depanelling).

**U1 thermal pad (pad 39):** the footprint has twelve 0.3 mm plated holes in the exposed GND pad (Espressif's land pattern). They are pad openings, so "tented vias" does not cover them: solder can wick into them during reflow. Leave them open (as Espressif shows) and tell JLCPCB in the order remark; if JLCPCB recommends it, choose plugged/capped holes for that pad.

**Order remark (paste into the order):** "Standard PCBA, top side only. Please add 5 mm edge rails on the two long (100 mm) edges only, with fiducials and tooling holes on the rails. V-cut or stamp holes are both accepted on those two edges: all copper stays 0.5 mm or more inside them, except the four GND shell pads of the microSD socket J11, 0.475 mm from the bottom edge. No rail on the two short (70 mm) edges: the ESP32 module U1 overhangs the left edge by 6.2 mm (antenna) and the USB-C receptacle J7 overhangs the right edge by 0.6 mm, both on purpose. U1's centre pad has 12 open 0.3 mm thermal holes (manufacturer land pattern): please leave them as they are. Please check in the placement review: C1 with + (pad 1, 5V) toward the board's left edge; J7 with its opening toward the right board edge; pin 1 of Q1, Q2, Q3, U4 and U9."

**Placement preview, check in this order** (coordinates are mm from the board's top-left corner, as in the KiCad files):
1. **C1** 220 µF electrolytic, CPL angle 0: "+" (pad 1, net 5V) toward the board's **left** edge; pad 1 is at (49.2, 53.0), pad 2 (GND) at (54.8, 53.0). If the preview shows "+" on the right, the capacitor would sit reversed across 5V: turn it by 180° in the preview. This is the one error the preview does not show as misaligned pads.
2. **J7** USB-C, CPL angle 90: the receptacle opening at the right board edge, standing 0.6 mm past it, its contacts toward the inside of the board. At 270 the shell would face into the board and the contacts would hang over the edge.
3. **Q1, Q2, Q3** (SOT-23) and **U4** (SOT-23-5), CPL angle 180: each part's pads on the board's pads, pin 1 at the footprint's pin-1 mark (the two-pin side of Q1-Q3 and the three-pin side of U4 face left).
4. **U9** USBLC6-2SC6 (SOT-23-6), CPL angle 270: pin 1 at (86.66, 48.55); a 180° error puts the TVS across VBUS ahead of F1.
5. **U8** LIS3DH (LGA-16): pin 1 at (36.78, 33.50).
6. **D1** 1N4148WS: cathode (pad 1, 5V) at (59.6, 34.05).
7. **U2 / U3 / U7** pin-1 dots; **U1** (antenna toward the left edge, off the board); **U5 / U6** (tab toward the left); **J11** (card slot at the bottom edge); F1, SW1 / SW2 (any 180° turn is the same part).

**Extended parts** (feeder fee each line): U1 ESP32-WROOM-32E-N4 (C701341), U7 CH340C (C84681), U2/U3 MCP23017-E/SO (C47023), U8 LIS3DHTR (C15134), U4 SN74AHCT1G125DBVR (C7484), U9 USBLC6-2SC6 (C7519), C1 220 µF (C72494), F1 PTC (C18198338), J7 USB-C (C165948), J11 microSD (C114218). Everything else is Basic, including both AMS1117-3.3 (C6186) and Q1 SS8050 (C2150).

**Changes against the rev 3 package** (commit 2b482c1; schematic rev 2.1, owner-approved, and the rotation check above): BOM: Q1 SS8050 (C2150, Basic) on its own line, Q2 / Q3 stay MMBT3904 (C20526); R7 330 Ω joins R1 (C23138) and the 1 k line (C21190) is gone; the 10 k line (C25804) gains R21 and R22 (16 parts); 23 lines, 59 SMD parts. CPL: rotations J7 270 -> 90, Q1 / Q2 / Q3 270 -> 180, U4 270 -> 180 (C1 stays 0, as in rev 3: the first rev 3.1 file had turned it to 180, which was wrong); Q1 and R7 values; new rows R21 (44.30, 34.10, 270) and R22 (71.30, 5.50, 270). Every other row is unchanged, except J7's position: x 94.89 -> 95.49 (the receptacle moved 0.6 mm outward on 2026-11-26, after the first rev 3.1 package; that also changed the top copper, all pours, the top silkscreen and both drill files). The Gerbers differ from rev 3 in both outer copper layers (rev 3.1 routing), all four copper layers' pours (0.5 mm inside the two long edges), the top silkscreen and the drill files.

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

From `hardware/defuse32/kicad/`, after `gen/std_fixes.py` and a clean DRC:

```sh
/usr/bin/python3 gen/gen_jlcpcb.py      # [--corrections cpl_rotations_db.csv] for the plugin's full table
```

It runs `kicad-cli pcb export gerbers --subtract-soldermask --check-zones --use-drill-file-origin` (F.Cu, In1.Cu, In2.Cu, B.Cu, paste, silkscreen, mask, Edge.Cuts) and `kicad-cli pcb export drill --format excellon --drill-origin plot --excellon-units mm --excellon-separate-th`, zips `gerber/`, and writes the BOM and CPL from the board footprints and the LCSC numbers in `gen/design.py`.

## Bring-up notes (rev 3.1)

- **Supply:** a 5 V USB-C source of 2 A or more. The board only presents 5.1 kΩ Rd and cannot read what the source offers; a 500 mA PC port may brown out when the servo moves.
- **Flashing:** if esptool cannot enter download mode, take the microSD card out (GPIO2 = SD_CS has a 10 kΩ pull-down; some cards pull DAT3 up hard enough to lift it).
- **J7 shell stakes:** the four USB-C shell legs are plated slots with no paste; inspect them on arrival and hand-solder any that are dry.
- **LED chain:** the WS2812 data runs through every plate (pins 6 / 7 of each header); with a plate unplugged the LEDs after it stay dark. Use a loop-back plug (IDC socket with wires 6 and 7 joined) in place of a missing plate.
- **Servo header J9:** pins G / + / S (GND, 5V, signal) as printed, all three left of the header; a reversed plug puts the servo ground on GPIO27.
- **Buzzer and D1:** Q1 (SS8050) can switch about 310 mA into a 16 Ω magnetic buzzer; the flyback diode D1 (1N4148WS, a 150 mA part) carries that current for a moment at each turn-off. Fit a buzzer of 32 Ω or more, or check D1's temperature on the first board with a 16 Ω one at the loudest tone (final check N12; the 1N4148WS ratings were not re-read from its datasheet for this note).
- **First power-up:** before fitting the plates, look at C1 ("+" mark toward the board's left edge, as on the silkscreen), then check 5V on a box-header pin 1, 3V3P on pin 3 and 3V3 at C9.
- **Probe points:** 5V on any box-header pin 1 or J9 "+", GND on pin 2 / J9 "G" / J10 pin 5, 3V3P on pin 3, 3V3 on C9 / C10 / C12 / C13 pin 1, EN at SW1 ("EN"), IO0 at SW2 ("BOOT"), TXD0 / RXD0 at U7 pins 3 / 2 (no test pads on this board).
