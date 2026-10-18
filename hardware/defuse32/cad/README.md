# Defuse32 rev 0 mechanical CAD

Scripted FreeCAD model of the Defuse32 case: a Pelican 1520 with the 1520PF panel frame, the panel, six module plates with placeholder modules, the floor sled, the carrier PCB, and the wall-mounted key switch and USB-C input. Every dimension comes from `../data/parts.json` and from the plate layouts in `layout.py`. The scripts write the outputs; nothing here is drawn by hand.

## Regenerate

```sh
cd hardware/defuse32
freecad.cmd cad/build.py            # about 10 s; writes every output below
```

- **Renders and colours.** The script starts FreeCAD's GUI offscreen (`QT_QPA_PLATFORM=offscreen`) inside `freecad.cmd`. That gives the view providers colours, so the FCStd and STEP files carry them, and lets the script save the PNG renders. No X server or xvfb is needed.
- **`D32_NO_GUI=1`** forces a pure headless run. You get the same geometry, checks and exports, but the FCStd and STEP have no colours and no renders are made. The GLB always has colours.
- **`D32_LID_DEG=0`** builds the closed-lid variant. The default is `100`: the lid swung back about the back hinge edge.
- **`D32_STRICT=1`** makes the script exit with 1 when a fit check fails. By default it exits with 0 and lists the failures.
- **`D32_CARRIER_STEP=path`** overrides the default `cad/carrier.step`.
- **File ownership.** The script writes only `cad/defuse32.FCStd`, `cad/out/*` and `renders/cad_*.png`. It never deletes or writes other files in `renders/`: `carrier-top.png` and `carrier-iso.png` belong to the KiCad side (`render_path()` in `build.py` refuses any other name).
- **Carrier STEP.** If `cad/carrier.step` exists (written by the KiCad side), it is imported and placed automatically. The board solid is the largest solid 1.6 mm thick. It is centred on the floor with its underside at z 11, and turned 90° if its long side is along y. The other solids become `Carrier_Components`. Without the file, a 190 x 140 x 1.6 green placeholder is used. Re-run the build after the STEP appears.

## Outputs

| File | What |
|---|---|
| `defuse32.FCStd` | Assembly, 153 named and coloured `Part::Feature` objects in groups (Case, Frame, Panel, M1 to M6, Carrier, Wall). Each object has `Defuse32` properties: `Colour`, `Alpha`, `Role`, `Plate`, `Module`. |
| `out/panel.dxf`, `out/plate_M1.dxf` to `out/plate_M6.dxf` | 2D laser files, 1:1 mm, AutoCAD R12 (LINE/CIRCLE/ARC). Origin is the part's bottom-left corner. Layers: `CUT` (outline and through-cuts, colour 1) and `ENGRAVE_1MM` (titles, NFC mark and touch-pad recesses, colour 5; text is flattened to 0.02 mm line segments). Written by our own writer and checked: every contour closes and the outline areas match the model. |
| `out/panel.stl`, `out/plate_M1.stl` to `out/plate_M6.stl` | Printable solids, including the 1 mm engravings. Plate bottom at z 0. |
| `out/assembly.step` | Whole assembly with colours. The carrier keep-out box is left out. |
| `out/assembly.glb` | glTF 2.0 binary for the web viewer: 152 meshes, about 697k triangles (most of them from the carrier STEP). Units are metres with +Y up; case (x, y, z) mm maps to glTF (x, z, -y)/1000. Each object is one node, named after the FCStd label and parented to a group node (Case, Frame, Panel, M1 to M6, Carrier, Wall). Node `extras` hold `colour`, `alpha` and `group`. Materials are double-sided PBR. The case shells are translucent (`BLEND`, alpha 0.35). |
| `out/fit_report.txt` | Full console log of the last run, including the fit checks. |
| `out/plate_cutouts.md` | The cut-out and module tables below, regenerated on every run. |
| `../renders/cad_iso.png`, `cad_top.png`, `cad_exploded.png`, `cad_underside.png` | 1600 x 1200 views. In order: isometric with the lid open; top view without the lid; exploded (frame +60, panel +120, plates with their modules +200); and looking up at the modules hanging under the plates. |

Source files: `build.py` (entry point: case, frame, panel, plates, carrier, checks, exports, renders), `d32lib.py` (primitives, cut and engrave records, module placeholder builders, DXF/GLB/STL writers) and `layout.py` (plate grid, plate contents, extra assumed parts, proposal values).

## Coordinates

- **Case frame.** Origin at the centre of the base's interior floor, z up, +x toward the right wall, +y toward the lid hinge (back). This is the same as the SPEC panel frame, offset by the panel centre.
- **z stack** (from `parts.json`):

| z (mm) | What |
|---|---|
| 0 to 3 | Sled |
| 3 to 11 | M3 standoffs |
| 11 to 12.6 | Carrier |
| 12.6 to 40 | Carrier keep-out: components, JST plugs, wire bends |
| 104.7 to 122.2 | Panel frame |
| 122.2 to 125.2 | Panel (top flush with the base rim) |
| 125.2 to 128.2 | Plates |
| up to 163.2 | 35 mm height cap |
| 170.7 | Lid inner skin |

- **Plate grid.** Plate centres are at x = -138 / 0 / +138 and y = +71 (M1 to M3) / -71 (M4 to M6).
- **Plate-local coordinates** (all tables below) have their origin at the plate centre, +y toward the back, top view. The DXFs use the plate's bottom-left corner instead: add (67, 69).

## Objects

| Object(s) | Description |
|---|---|
| `Case_Base`, `Case_Lid` | Simplified Pelican 1520 shells in training blue #2C5FA8, translucent. Interior 458.7 x 327.4 at the rim with R16.5 corners, drafting to a 445 x 314 floor. Base depth 125.2, lid depth 45.5, 6 mm walls, 8.75 mm floor and lid skins. The lid hinges about the back outer edge at the rim. The wall holes are cut in the base: key switch dia 19 at (y +60, z 70) and USB-C dia 22 at (y -60, z 70). |
| `Panel_Frame_1520PF` | Outline 454.6 x 323.9 R16.5, 17.5 tall (z 104.7 to 122.2). Clear opening 422.6 x 291.2. 16 insert bosses dia 8 with dia 5.2 holes at the insert pattern. The section is simplified: 3 mm top flange and 2.5 mm skirt. |
| `Panel` | 452 x 321 x 3, R16.5. 16 x dia 3.6 frame holes, 6 openings 114 x 118 centred under the plates, 24 x dia 3.4 plate-screw holes. |
| `Plate_M1` to `Plate_M6` | 134 x 138 x 3, light grey. 4 x dia 3.4 holes 6 mm from the corners. Module cut-outs as listed below, a dia 5 status LED hole at (49, 52) and a 1 mm deep title (DejaVu Sans Bold, cap height 5.5) at (-52, 55). |
| `Mn_<item>_<part>` | Placeholder bodies for each module (PCB, display glass, encoder, keys, headers, standoffs, nuts, knob, posts…), coloured roughly like the real parts. |
| `Floor_Sled` | 443 x 312 x 3 R15.5: the floor less 1 mm per side. |
| `Carrier_PCB` (+ `Carrier_Components` when the STEP is used) | 190 x 140 x 1.6 at z 11, 4 x dia 3.2 holes 5 mm from the corners. |
| `Carrier_Standoff1` to `Carrier_Standoff4` | M3 x 8 hex standoffs. |
| `Carrier_Keepout` | Hidden in the FCStd and not exported. Used by the fit checks. |
| `Wall_KeySwitch_*`, `Wall_USBC_*` | Outside bezels (dia 28 x 10, dia 29.5 x 4) and inside bodies (dia 22 x 51, dia 21.5 x 35) on the right wall. |

## Plate layouts

How each plate is mounted (the generated tables below give exact positions):

- **M1 Radio**
  - SSD1306 on 4 x M2 x 2 mm standoffs.
  - 2 link LEDs to the right of the OLED.
  - KY-040 held by its M7 bushing and nut. The knob top is 17 mm above the plate.
- **M2 Timer**
  - TM1637 on 4 x M3 x 8.2 standoffs, with the display just under the plate.
  - 3 strike LEDs.
  - Buzzer under three sound holes.
- **M3 Keypad**
  - SH1106 on 4 x M2 x 2.2 standoffs above the keypad.
  - Keypad **on top of the plate** (SPEC): its 61 mm hole pattern is too close to the 60 x 60 key field to mount it from below. The frame sits on 4 x M3 x 3 nylon spacers; M3 screws go through frame, spacers and plate at the real hole positions, with nuts below. The plate has no key-field cut-out, only a 27.4 x 6 slot under the 10-pad tail header for the cable (10 x 2.54 + 1 mm per side). Keys top out 13 mm above the plate.
- **M4 Wires**
  - 12 posts at 19.05 mm pitch: row A (red, outputs) at y +18 and row B (black, inputs) at y -22.
- **M5 Probe**
  - A 70 x 90 perfboard is screwed flat under the plate. It carries the 6-pin SPI, 4-pin I2C and 4-pin UART headers, the DIP-8 socket, the SOIC-8 breakout and 4 test loops.
  - The header plastic sits inside 0.3 mm-clearance slots, so the pins stand 5.5 mm proud. The windows leave 2 mm round the socket and the breakout for clips.
- **M6 Sensors**
  - 4 copper-tape touch recesses (2 x 2, top left), each with a dia 2 wire hole.
  - LDR press-fit and IR receiver behind a window, in the centre column.
  - PN532 on 2 nylon standoffs under a plain area with an engraved "NFC".
  - 2 x 2 Simon buttons on a 50 x 50 perfboard (6 mm standoffs). The caps stand 3 mm proud.
  - SG90 on a printed L-bracket with its shaft horizontal. Its 20 mm arm swings up through a 24 x 6 slot to act as the prize-hatch latch. It is shown latched; the hatch flap itself is not modelled. In the module table, the servo's "At" is the shaft x.

<!-- generated: out/plate_cutouts.md -->
| Plate | Cut-out | Type | Size (mm) | Centre x, y from plate centre | From plate bottom-left |
|---|---|---|---|---|---|
| M1 | plate M3 hole 1 | through | dia 3.40 | -61.00, -63.00 | 6.00, 6.00 |
| M1 | plate M3 hole 2 | through | dia 3.40 | -61.00, 63.00 | 6.00, 132.00 |
| M1 | plate M3 hole 3 | through | dia 3.40 | 61.00, -63.00 | 128.00, 6.00 |
| M1 | plate M3 hole 4 | through | dia 3.40 | 61.00, 63.00 | 128.00, 132.00 |
| M1 | OLED window | through | 22.74 x 13.36 | -20.00, 22.88 | 47.00, 91.88 |
| M1 | OLED M2 hole 1 | through | dia 2.40 | -31.65, 10.10 | 35.35, 79.10 |
| M1 | OLED M2 hole 2 | through | dia 2.40 | -8.35, 10.10 | 58.65, 79.10 |
| M1 | OLED M2 hole 3 | through | dia 2.40 | -31.65, 33.90 | 35.35, 102.90 |
| M1 | OLED M2 hole 4 | through | dia 2.40 | -8.35, 33.90 | 58.65, 102.90 |
| M1 | LinkLED1 light hole | through | dia 5.00 | 10.00, 22.00 | 77.00, 91.00 |
| M1 | LinkLED2 light hole | through | dia 5.00 | 24.00, 22.00 | 91.00, 91.00 |
| M1 | Encoder shaft (M7 bushing) | through | dia 7.50 | 0.00, -25.00 | 67.00, 44.00 |
| M1 | StatusLED light hole | through | dia 5.00 | 49.00, 52.00 | 116.00, 121.00 |
| M1 | title | engrave | text 'M1 RADIO' cap 5.5, box 40.0 x 5.5, 1.0 deep | -52.00, 55.00 (text box bottom-left) | |
| M2 | plate M3 hole 1 | through | dia 3.40 | -61.00, -63.00 | 6.00, 6.00 |
| M2 | plate M3 hole 2 | through | dia 3.40 | -61.00, 63.00 | 6.00, 132.00 |
| M2 | plate M3 hole 3 | through | dia 3.40 | 61.00, -63.00 | 128.00, 6.00 |
| M2 | plate M3 hole 4 | through | dia 3.40 | 61.00, 63.00 | 128.00, 132.00 |
| M2 | TM1637 window | through | 50.40 x 19.00 | 0.00, 18.25 | 67.00, 87.25 |
| M2 | TM1637 M3 hole 1 | through | dia 3.40 | -30.15, 7.25 | 36.85, 76.25 |
| M2 | TM1637 M3 hole 2 | through | dia 3.40 | 30.15, 7.25 | 97.15, 76.25 |
| M2 | TM1637 M3 hole 3 | through | dia 3.40 | -30.15, 28.75 | 36.85, 97.75 |
| M2 | TM1637 M3 hole 4 | through | dia 3.40 | 30.15, 28.75 | 97.15, 97.75 |
| M2 | Strike1 light hole | through | dia 5.00 | -20.00, -12.00 | 47.00, 57.00 |
| M2 | Strike2 light hole | through | dia 5.00 | 0.00, -12.00 | 67.00, 57.00 |
| M2 | Strike3 light hole | through | dia 5.00 | 20.00, -12.00 | 87.00, 57.00 |
| M2 | Buzzer sound hole | through | dia 3.00 | 0.00, -38.00 | 67.00, 31.00 |
| M2 | Buzzer sound hole L | through | dia 2.00 | -5.60, -38.00 | 61.40, 31.00 |
| M2 | Buzzer sound hole R | through | dia 2.00 | 5.60, -38.00 | 72.60, 31.00 |
| M2 | StatusLED light hole | through | dia 5.00 | 49.00, 52.00 | 116.00, 121.00 |
| M2 | title | engrave | text 'M2 TIMER' cap 5.5, box 40.3 x 5.5, 1.0 deep | -52.00, 55.00 (text box bottom-left) | |
| M3 | plate M3 hole 1 | through | dia 3.40 | -61.00, -63.00 | 6.00, 6.00 |
| M3 | plate M3 hole 2 | through | dia 3.40 | -61.00, 63.00 | 6.00, 132.00 |
| M3 | plate M3 hole 3 | through | dia 3.40 | 61.00, -63.00 | 128.00, 6.00 |
| M3 | plate M3 hole 4 | through | dia 3.40 | 61.00, 63.00 | 128.00, 132.00 |
| M3 | OLED window | through | 30.42 x 15.70 | 0.00, 36.25 | 67.00, 105.25 |
| M3 | OLED M2 hole 1 | through | dia 2.40 | -15.75, 20.00 | 51.25, 89.00 |
| M3 | OLED M2 hole 2 | through | dia 2.40 | 15.75, 20.00 | 82.75, 89.00 |
| M3 | OLED M2 hole 3 | through | dia 2.40 | -15.75, 48.70 | 51.25, 117.70 |
| M3 | OLED M2 hole 4 | through | dia 2.40 | 15.75, 48.70 | 82.75, 117.70 |
| M3 | Keypad M3 hole 1 | through | dia 3.40 | -30.50, -50.70 | 36.50, 18.30 |
| M3 | Keypad M3 hole 2 | through | dia 3.40 | 30.50, -50.70 | 97.50, 18.30 |
| M3 | Keypad M3 hole 3 | through | dia 3.40 | -30.50, 10.30 | 36.50, 79.30 |
| M3 | Keypad M3 hole 4 | through | dia 3.40 | 30.50, 10.30 | 97.50, 79.30 |
| M3 | Keypad header/cable slot | through | 27.40 x 6.00 | 0.00, -56.50 | 67.00, 12.50 |
| M3 | StatusLED light hole | through | dia 5.00 | 49.00, 52.00 | 116.00, 121.00 |
| M3 | title | engrave | text 'M3 KEYPAD' cap 5.5, box 46.0 x 5.5, 1.0 deep | -52.00, 55.00 (text box bottom-left) | |
| M4 | plate M3 hole 1 | through | dia 3.40 | -61.00, -63.00 | 6.00, 6.00 |
| M4 | plate M3 hole 2 | through | dia 3.40 | -61.00, 63.00 | 6.00, 132.00 |
| M4 | plate M3 hole 3 | through | dia 3.40 | 61.00, -63.00 | 128.00, 6.00 |
| M4 | plate M3 hole 4 | through | dia 3.40 | 61.00, 63.00 | 128.00, 132.00 |
| M4 | PostA1 post | through | dia 7.00 | -47.62, 18.00 | 19.38, 87.00 |
| M4 | PostA2 post | through | dia 7.00 | -28.58, 18.00 | 38.42, 87.00 |
| M4 | PostA3 post | through | dia 7.00 | -9.53, 18.00 | 57.48, 87.00 |
| M4 | PostA4 post | through | dia 7.00 | 9.53, 18.00 | 76.53, 87.00 |
| M4 | PostA5 post | through | dia 7.00 | 28.58, 18.00 | 95.58, 87.00 |
| M4 | PostA6 post | through | dia 7.00 | 47.62, 18.00 | 114.62, 87.00 |
| M4 | PostB1 post | through | dia 7.00 | -47.62, -22.00 | 19.38, 47.00 |
| M4 | PostB2 post | through | dia 7.00 | -28.58, -22.00 | 38.42, 47.00 |
| M4 | PostB3 post | through | dia 7.00 | -9.53, -22.00 | 57.48, 47.00 |
| M4 | PostB4 post | through | dia 7.00 | 9.53, -22.00 | 76.53, 47.00 |
| M4 | PostB5 post | through | dia 7.00 | 28.58, -22.00 | 95.58, 47.00 |
| M4 | PostB6 post | through | dia 7.00 | 47.62, -22.00 | 114.62, 47.00 |
| M4 | StatusLED light hole | through | dia 5.00 | 49.00, 52.00 | 116.00, 121.00 |
| M4 | title | engrave | text 'M4 WIRES' cap 5.5, box 40.2 x 5.5, 1.0 deep | -52.00, 55.00 (text box bottom-left) | |
| M5 | plate M3 hole 1 | through | dia 3.40 | -61.00, -63.00 | 6.00, 6.00 |
| M5 | plate M3 hole 2 | through | dia 3.40 | -61.00, 63.00 | 6.00, 132.00 |
| M5 | plate M3 hole 3 | through | dia 3.40 | 61.00, -63.00 | 128.00, 6.00 |
| M5 | plate M3 hole 4 | through | dia 3.40 | 61.00, 63.00 | 128.00, 132.00 |
| M5 | Probe SPI 6-pin header slot | through | 15.84 x 3.14 | -16.00, 30.00 | 51.00, 99.00 |
| M5 | Probe I2C 4-pin header slot | through | 10.76 x 3.14 | 16.00, 30.00 | 83.00, 99.00 |
| M5 | Probe UART 4-pin header slot | through | 10.76 x 3.14 | 0.00, -14.00 | 67.00, 55.00 |
| M5 | Probe DIP-8 socket window | through | 14.10 x 14.20 | 16.00, 8.00 | 83.00, 77.00 |
| M5 | Probe SOIC-8 breakout window | through | 16.00 x 14.00 | -16.00, 8.00 | 51.00, 77.00 |
| M5 | Probe test point 1 | through | dia 5.00 | -24.00, -34.00 | 43.00, 35.00 |
| M5 | Probe test point 2 | through | dia 5.00 | -8.00, -34.00 | 59.00, 35.00 |
| M5 | Probe test point 3 | through | dia 5.00 | 8.00, -34.00 | 75.00, 35.00 |
| M5 | Probe test point 4 | through | dia 5.00 | 24.00, -34.00 | 91.00, 35.00 |
| M5 | Probe M3 hole 1 | through | dia 3.40 | -32.50, -47.50 | 34.50, 21.50 |
| M5 | Probe M3 hole 2 | through | dia 3.40 | 32.50, -47.50 | 99.50, 21.50 |
| M5 | Probe M3 hole 3 | through | dia 3.40 | -32.50, 37.50 | 34.50, 106.50 |
| M5 | Probe M3 hole 4 | through | dia 3.40 | 32.50, 37.50 | 99.50, 106.50 |
| M5 | StatusLED light hole | through | dia 5.00 | 49.00, 52.00 | 116.00, 121.00 |
| M5 | title | engrave | text 'M5 PROBE' cap 5.5, box 41.3 x 5.5, 1.0 deep | -52.00, 55.00 (text box bottom-left) | |
| M6 | plate M3 hole 1 | through | dia 3.40 | -61.00, -63.00 | 6.00, 6.00 |
| M6 | plate M3 hole 2 | through | dia 3.40 | -61.00, 63.00 | 6.00, 132.00 |
| M6 | plate M3 hole 3 | through | dia 3.40 | 61.00, -63.00 | 128.00, 6.00 |
| M6 | plate M3 hole 4 | through | dia 3.40 | 61.00, 63.00 | 128.00, 132.00 |
| M6 | TouchT0 wire hole | through | dia 2.00 | -40.00, 40.00 | 27.00, 109.00 |
| M6 | TouchT4 wire hole | through | dia 2.00 | -18.00, 40.00 | 49.00, 109.00 |
| M6 | TouchT6 wire hole | through | dia 2.00 | -40.00, 18.00 | 27.00, 87.00 |
| M6 | TouchT3 wire hole | through | dia 2.00 | -18.00, 18.00 | 49.00, 87.00 |
| M6 | LDR hole | through | dia 5.40 | 0.00, 30.00 | 67.00, 99.00 |
| M6 | IR window | through | 6.50 x 7.50 | 0.00, 12.00 | 67.00, 81.00 |
| M6 | PN532 M3 hole 1 | through | dia 3.40 | 15.65, 34.90 | 82.65, 103.90 |
| M6 | PN532 M3 hole 2 | through | dia 3.40 | 44.25, 9.80 | 111.25, 78.80 |
| M6 | Simon button 1 cap | through | dia 12.50 | -40.00, -22.00 | 27.00, 47.00 |
| M6 | Simon button 2 cap | through | dia 12.50 | -18.00, -22.00 | 49.00, 47.00 |
| M6 | Simon button 3 cap | through | dia 12.50 | -40.00, -44.00 | 27.00, 25.00 |
| M6 | Simon button 4 cap | through | dia 12.50 | -18.00, -44.00 | 49.00, 25.00 |
| M6 | Simon M3 hole 1 | through | dia 3.40 | -51.00, -55.00 | 16.00, 14.00 |
| M6 | Simon M3 hole 2 | through | dia 3.40 | -7.00, -55.00 | 60.00, 14.00 |
| M6 | Simon M3 hole 3 | through | dia 3.40 | -51.00, -11.00 | 16.00, 58.00 |
| M6 | Simon M3 hole 4 | through | dia 3.40 | -7.00, -11.00 | 60.00, 58.00 |
| M6 | Servo latch slot | through | 24.15 x 6.00 | 38.58, -45.25 | 105.58, 23.75 |
| M6 | Servo bracket M3 hole 1 | through | dia 3.40 | 9.80, -19.00 | 76.80, 50.00 |
| M6 | Servo bracket M3 hole 2 | through | dia 3.40 | 40.00, -19.00 | 107.00, 50.00 |
| M6 | StatusLED light hole | through | dia 5.00 | 49.00, 52.00 | 116.00, 121.00 |
| M6 | title | engrave | text 'M6 SENSORS' cap 5.5, box 52.2 x 5.5, 1.0 deep | -52.00, 55.00 (text box bottom-left) | |
| M6 | TouchT0 recess | engrave | 18.0 x 18.0 x 1.0 deep | -40.00, 40.00 | |
| M6 | TouchT4 recess | engrave | 18.0 x 18.0 x 1.0 deep | -18.00, 40.00 | |
| M6 | TouchT6 recess | engrave | 18.0 x 18.0 x 1.0 deep | -40.00, 18.00 | |
| M6 | TouchT3 recess | engrave | 18.0 x 18.0 x 1.0 deep | -18.00, 18.00 | |
| M6 | PN532 NFC mark | engrave | text 'NFC' cap 8.0, box 22.2 x 8.0, 1.0 deep | 30.00, 22.00 | |

| Plate | Item | Part | At (plate-local) | Mounting |
|---|---|---|---|---|
| M1 | OLED | ssd1306_096 | -20.00, 22.00 | 4 x M2 standoffs 2.0 long |
| M1 | LinkLED1 | ws2812b | 10.00, 22.00 | round 10 mm WS2812 breakout, LED face against the plate (hot glue / printed clip) |
| M1 | LinkLED2 | ws2812b | 24.00, 22.00 | round 10 mm WS2812 breakout, LED face against the plate (hot glue / printed clip) |
| M1 | Encoder | ky040 | 0.00, -25.00 | by its M7 bushing + nut (PCB holes not used: positions unreliable) |
| M1 | StatusLED | ws2812b | 49.00, 52.00 | round 10 mm WS2812 breakout, LED face against the plate (hot glue / printed clip) |
| M2 | TM1637 | tm1637_056 | 0.00, 18.00 | 4 x M3 standoffs 8.2 long |
| M2 | Strike1 | ws2812b | -20.00, -12.00 | round 10 mm WS2812 breakout, LED face against the plate (hot glue / printed clip) |
| M2 | Strike2 | ws2812b | 0.00, -12.00 | round 10 mm WS2812 breakout, LED face against the plate (hot glue / printed clip) |
| M2 | Strike3 | ws2812b | 20.00, -12.00 | round 10 mm WS2812 breakout, LED face against the plate (hot glue / printed clip) |
| M2 | Buzzer | buzzer_12mm | 0.00, -38.00 | glued / printed clip against the plate underside |
| M2 | StatusLED | ws2812b | 49.00, 52.00 | round 10 mm WS2812 breakout, LED face against the plate (hot glue / printed clip) |
| M3 | OLED | sh1106_13 | 0.00, 34.85 | 4 x M2 standoffs 2.2 long |
| M3 | Keypad | keypad_4x4_hard | 0.00, -20.20 | on top of the plate: 4 x M3 x 3 spacers, M3 screws through frame, spacers and plate (61 mm pattern) + nuts below; cable through a 27.4 x 6.0 slot |
| M3 | StatusLED | ws2812b | 49.00, 52.00 | round 10 mm WS2812 breakout, LED face against the plate (hot glue / printed clip) |
| M4 | PostA1 | banana_post_4mm | -47.62, 18.00 | panel nut |
| M4 | PostA2 | banana_post_4mm | -28.58, 18.00 | panel nut |
| M4 | PostA3 | banana_post_4mm | -9.53, 18.00 | panel nut |
| M4 | PostA4 | banana_post_4mm | 9.53, 18.00 | panel nut |
| M4 | PostA5 | banana_post_4mm | 28.58, 18.00 | panel nut |
| M4 | PostA6 | banana_post_4mm | 47.62, 18.00 | panel nut |
| M4 | PostB1 | banana_post_4mm | -47.62, -22.00 | panel nut |
| M4 | PostB2 | banana_post_4mm | -28.58, -22.00 | panel nut |
| M4 | PostB3 | banana_post_4mm | -9.53, -22.00 | panel nut |
| M4 | PostB4 | banana_post_4mm | 9.53, -22.00 | panel nut |
| M4 | PostB5 | banana_post_4mm | 28.58, -22.00 | panel nut |
| M4 | PostB6 | banana_post_4mm | 47.62, -22.00 | panel nut |
| M4 | StatusLED | ws2812b | 49.00, 52.00 | round 10 mm WS2812 breakout, LED face against the plate (hot glue / printed clip) |
| M5 | Probe | probe_perfboard + header_254 + dip8_socket + soic8_breakout | 0.00, -5.00 | perfboard screwed flat under the plate (4 x M3 + nuts, no spacer) |
| M5 | StatusLED | ws2812b | 49.00, 52.00 | round 10 mm WS2812 breakout, LED face against the plate (hot glue / printed clip) |
| M6 | TouchT0 | touch pad (copper tape) | -40.00, 40.00 | copper tape in a 1 mm recess, wire through |
| M6 | TouchT4 | touch pad (copper tape) | -18.00, 40.00 | copper tape in a 1 mm recess, wire through |
| M6 | TouchT6 | touch pad (copper tape) | -40.00, 18.00 | copper tape in a 1 mm recess, wire through |
| M6 | TouchT3 | touch pad (copper tape) | -18.00, 18.00 | copper tape in a 1 mm recess, wire through |
| M6 | LDR | gl5528 | 0.00, 30.00 | press fit in the plate hole, face up |
| M6 | IR | vs1838b | 0.00, 12.00 | lens up behind the window (hot glue / printed clip) |
| M6 | PN532 | pn532_v3 | 30.00, 22.00 | 2 x M3 NYLON standoffs 2.6 long (no metal over the antenna) |
| M6 | Simon | simon_board + 4 x tact_12mm + 4 x ws2812b | -29.00, -33.00 | 4 x M3 standoffs 6.0 long |
| M6 | Servo | sg90 + printed bracket | 30.00, 0.00 | printed L-bracket (2 x M3 to the plate), servo ears M2 into the bracket; horn shown latched (up) |
| M6 | StatusLED | ws2812b | 49.00, 52.00 | round 10 mm WS2812 breakout, LED face against the plate (hot glue / printed clip) |

## Fit checks (last run, real `carrier.step`)

```
carrier: carrier.step (39 solids, board found, rotated 0 deg)
carrier: Carrier_PCB x -95.0..95.0 y -70.0..70.0 z 11.0..12.5
carrier: Carrier_Components x -83.5..91.6 y -66.4..64.8 z 9.1..26.4
PASS  panel top z = 125.20, base rim z = 125.20 (flush at 125.2)
PASS  plates z 125.2..128.2 on the panel
PASS  panel openings inside the 1520PF clear opening (min margin 15.6 mm)
PASS  M1 hanging parts inside the 114x118 opening footprint (min margin 2.00 mm at M1_StatusLED_Breakout), lowest z 113.1 (12.1 below plate, limit 40)
PASS  M1 tallest part z 145.2 = 17.0 above the plate top (cap 35)
PASS  M2 hanging parts inside the 114x118 opening footprint (min margin 2.00 mm at M2_StatusLED_Breakout), lowest z 106.9 (18.3 below plate, limit 40)
PASS  M2 tallest part z 125.2 = -3.0 above the plate top (cap 35)
PASS  M3 hanging parts inside the 114x118 opening footprint (min margin 1.23 mm at M3_Keypad_HeaderPlug), lowest z 113.3 (11.9 below plate, limit 40)
PASS  M3 tallest part z 141.2 = 13.0 above the plate top (cap 35)
PASS  M4 hanging parts inside the 114x118 opening footprint (min margin 2.00 mm at M4_StatusLED_Breakout), lowest z 107.2 (18.0 below plate, limit 40)
PASS  M4 tallest part z 158.2 = 30.0 above the plate top (cap 35)
PASS  M5 hanging parts inside the 114x118 opening footprint (min margin 2.00 mm at M5_StatusLED_Breakout), lowest z 120.6 (4.6 below plate, limit 40)
PASS  M5 tallest part z 134.2 = 6.0 above the plate top (cap 35)
PASS  M6 hanging parts inside the 114x118 opening footprint (min margin 1.00 mm at M6_Simon_Board), lowest z 105.1 (20.1 below plate, limit 40)
PASS  M6 tallest part z 135.8 = 7.6 above the plate top (cap 35)
PASS  M1 modules clear of plate and panel material (through cut-outs only)
PASS  M2 modules clear of plate and panel material (through cut-outs only)
PASS  M3 modules clear of plate and panel material (through cut-outs only)
PASS  M4 modules clear of plate and panel material (through cut-outs only)
PASS  M5 modules clear of plate and panel material (through cut-outs only)
PASS  M6 modules clear of plate and panel material (through cut-outs only)
PASS  M1 no clashes between different modules
PASS  M2 no clashes between different modules
PASS  M3 no clashes between different modules
PASS  M4 no clashes between different modules
PASS  M5 no clashes between different modules
PASS  M6 no clashes between different modules
PASS  nothing intersects the carrier PCB/components, its standoffs, the sled or the carrier keep-out (min clearance to keep-out 67.2 mm at M4_PostA6_Stud)
PASS  carrier tallest part z 26.4 (13.8 above the board) <= keep-out top z 40; lowest module part z 105.1 at M6_IR_Leads (gap 78.7) [carrier.step (39 solids, board found, rotated 0 deg)]
PASS  KeySwitch on the right wall: y 60, hole dia 19.0, flange z 56.0..84.0 (band 40..100)
PASS  USBC on the right wall: y -60, hole dia 22.0, flange z 55.2..84.8 (band 40..100)
PASS  wall parts clear of the shell, frame and plate modules
PASS  lid closed: tallest part z 158.2 < lid inner skin z 170.7 (margin 12.5)
PASS  closed lid shell intersects nothing (0.000 mm3)
PASS  plate M1 webs >= 3 mm (min 3.15: OLED window <-> OLED M2 hole 3)
PASS  plate M2 webs >= 3 mm (min 3.10: Buzzer sound hole <-> Buzzer sound hole L)
PASS  plate M3 webs >= 3 mm (min 3.43: OLED window <-> OLED M2 hole 3)
PASS  plate M4 webs >= 3 mm (min 4.30: plate M3 hole 1 <-> edge)
PASS  plate M5 webs >= 3 mm (min 4.30: plate M3 hole 1 <-> edge)
PASS  plate M6 webs >= 3 mm (min 4.30: plate M3 hole 1 <-> edge)
PASS  panel webs >= 3 mm (min 3.96: M5 opening <-> M5 plate screw 2)
------------------------------------------------------------------------
fit checks: 0 failure(s)
```

The carrier comes from the KiCad STEP (board plus all parts, centred on the floor, underside at z 11, USB edge toward the right wall). Its tallest parts (the DevKit sockets and the 470 µF capacitor) reach z 26.4; a plugged-in DevKit (about 5 mm of PCB and parts above the socket tops) is not in the STEP but stays far under the 40 mm keep-out top and the lowest plate module (z 105.1).

Other notes from the checks:
- M2 has nothing above its plate. The TM1637 display sits 0.2 mm under its window.
- The keypad cable plug under M3 has the smallest footprint margin: 1.23 mm to the opening edge.

## Assumptions to measure on real parts before cutting

**Case and frame**
- Wall: 6 mm uniform. The exterior is simplified: latches, handle, hinge, ribs and bumpers are not modelled, so the outside box is 470.7 x 339.4 rather than the published 502.4 x 400.6.
- Interior: R16.5 corners and a 445 x 314 floor with linear draft. Both are parts.json assumptions.
- Choose the flat spot for the key switch and USB-C on the real right wall.
- The 1520PF frame section is assumed: flange 3, skirt 2.5, bosses dia 8 x 10, opening corners R3. Only its outline, opening and insert positions are verified.
- The panel outline is derived. Test-fit it against the frame.

**Modules** (all `typical` in parts.json)
- **SSD1306:** the window's vertical position is uncertain by ±1.5 mm. To keep the 3 mm web to the M2 holes, the window is the active area plus 0.5 mm per side, extended 1.5 mm downward, not 2 mm taller as parts.json suggests. Check the batch, and its 4-pin hole pitch.
- **SH1106:** the hole pattern is 31.5 x 28.7 (ETT drawing); other sellers use 30.5 x 29 or 30 x 28. The window is the active area plus 0.5 mm.
- **TM1637:** hole centres and display position are scaled from a photo. The window is exactly the 50.4 x 19 display.
- **KY-040:** the shaft position (9.2, 10.8) is assumed, and so is the body height of 6.5 above the PCB, which sets the 1 mm gap under the plate and the bushing length above it. The PCB holes are deliberately not used.
- **Keypad:** the 4 mm frame back, the 6 mm key height, the hole diameter (3.0) and the tail header position (10 pads centred on the bottom edge) are assumed. Measure the header before cutting the 27.4 x 6 slot, and pick spacers so the tail pads clear the plate (3 mm assumed).
- **PN532:** the hole positions are scaled from a photo.
- **Banana posts:** the dia 7 hole fits Cliff TP6 posts. Heights are 30 above and 18 below the plate.
- **Buzzer:** dia 12 x 9.5. The sound holes are a dia 3 centre hole plus 2 x dia 2 at ±5.6.
- **SG90:** ear and shaft positions; the horn arm length of 20 mm sets the slot length.
- **Status LEDs and link/strike LEDs:** round 10 mm WS2812 breakouts behind dia 5 holes. The brief says dia 5; parts.json proposes 5.5.

**Proposals** (`layout.py` → `EXTRA` and `OPT`)
- Probe perfboard: 70 x 90, dia 3 holes 2.5 mm from the corners.
- Simon board: 50 x 50, holes 3 mm from the corners.
- Tact cap hole: dia 12.5, for a round A24 cap about dia 11.6. It depends on the caps bought.
- Test-point hole: dia 5.
- Header slot clearance: 0.3 mm per side.

**Wall parts**
- Inside body sizes: key switch dia 22 x 51, USB-C dia 21.5 x 35 (Adafruit 4218 estimate).
