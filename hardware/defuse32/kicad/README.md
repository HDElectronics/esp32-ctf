# Defuse32 carrier PCB, rev 3.1 (KiCad 10, 4 layers; schematic rev 2.1)

The carrier board sits on the case floor and connects to the six plates by ribbon cables. Rev 2 is an SMD board assembled by JLCPCB: ESP32-WROOM-32E module, USB-C programming port with a CH340C, two MCP23017 expanders, LIS3DH tilt sensor, push-push microSD, WS2812 buffer, buzzer driver and one keyed IDC box header per plate. The source of truth is [`../SPEC.md`](../SPEC.md), section "Rev 2 carrier (2026-10-23)", plus the sections it keeps: ESP32 pin map, MCP23017 allocation (rev 1b), WS2812 chain, I2C addresses and the plate signal sets (rev 1 Jn_B table).

**Status (2026-11-25): rev 3.1, the standards pass of rev 3 (section "Standards pass (2026-11-25)"), with schematic rev 2.1 (Q1 SS8050, R7 330 Ω, new R21 WS_DATA pull-down and R22 SD CMD pull-up, owner-approved). Not ordered yet. Rev 3 (2026-10-24, commit 2b482c1): re-routed on 4 layers (JLCPCB JLC04161H-7628) and finished: GND pours on both outer layers stitched into two solid GND planes, 1.0 mm silkscreen beside every part (nothing on the bottom), 3D models for every part; JLCPCB fabrication and assembly files in `out/jlcpcb/`.** Rev 3 changed copper and silkscreen only (section "Rev 3"); rev 3.1 also adds R21 / R22 to the routed board (no regeneration).

| Check | Result |
|---|---|
| `kicad-cli sch erc --severity-all` | 0 errors, 0 warnings |
| `kicad-cli pcb drc --severity-all --schematic-parity --refill-zones --all-track-errors` | 0 violations, 0 unconnected items, 0 schematic parity issues (JLCPCB 4-layer minimums and custom rules; silk_over_copper, silk_overlap, silk_edge_clearance are errors; silk clearance 0.15 mm, text >= 1.0 mm / 0.15 mm) |
| `gen/check_netlist.py` | OK: netlist and board pads match `design.py`, plus the SPEC pin map, MCP23017 allocation, IDC pinout rule, rails, AMS1117 capacitors, outline, holes, U1 antenna beyond the edge and net classes |
| `gen/pcb_audit.py` (finish audit, `out/audit.json`; routing checks tightened 2026-11-25) | silkscreen: 0 violations, 0 warnings, no hidden part reference (R16-R19 share the label "R16-19"; the fiducials FID1-FID3 are board-only and print no reference); 3D: every part has a model; routing: 0 right angles, **7 jogs**, 23 tight corners, 1 hairpin, 0 cap-only joins, 0 stray segments (rev 3 by the same count: 23 / 30 / 3 / 7 / 10; every one left has its measured reason under "Standards pass"); copper: 66 narrow voids (129.3 mm2), none can take a usable stitching via |
| `gen/std_audit.py` (standards measurements, `out/std_audit.json`) | 0 off-angle segments, 0 acute junctions, 0 vias in SMD pads, every fast-net layer change within 2 mm of a GND via, LCSC on all 68 fitted parts; copper 0.5 mm or more from the two long edges (J11's shell pads 0.475 mm); 5V F1 -> U5 / U6 34 / 48 mΩ (network solve) |

Rev 1b (THT, DevKitC socket, 190 x 140 mm, routed) is in git, tag `carrier-rev1b`.

Changes against SPEC "Rev 2 carrier" made on 2026-10-23 (SPEC.md not edited yet): **U5 (3V3P) is an AMS1117-3.3** instead of the AP2112K-3.3 (see Power), and the microSD card-detect level is now documented (**low = card present**; firmware `CONFIG_D32_SD_DET_ACTIVE_HIGH=n`).

## Rev 3: four layers (2026-10-23/24)

The owner reviewed rev 2.1 and asked for: no gaps left between tracks (grounded copper), no 90° corners, 3D models for every part, labels aligned and right next to their part (R4 with R6 R9 R5; C6 and R20 beside, not off a corner), 4 layers allowed, and JLCPCB's capabilities respected (with the JLCPCB Tools plugin's conventions). Rev 3 keeps placement, schematic, netlist and pin map, and re-routes the board on 4 layers.

| | rev 2.1 (2 layers) | rev 3 (4 layers) |
|---|---|---|
| Stack-up | 2 layers, 1.6 mm | JLC04161H-7628, 1.6 mm: signals + GND pour / GND plane / GND plane / signals + GND pour |
| Jogs (audit) | 49 | **9** (110 straight out of Freerouting) |
| 90° corners (audit) | 12 | **0** |
| Copper voids >= 0.5 mm2 (audit) | 83, 159 mm2 | 60, 137.8 mm2 |
| ... of which a stitching via fits | 0 | 2 by the audit's test, neither usable (below) |
| Silkscreen violations / warnings (rev 3 audit, text >= 1.0 mm) | 3 / 18 (two 45° labels, R4 out of its row; 11 ambiguous, 7 far) | **0 / 0** |
| Reference size | 0.8 mm / 0.15 mm | 1.0 mm / 0.15 mm (JLCPCB's minimum height) |
| Top-side parts labelled on the bottom silkscreen | 7 | **0** |
| Callouts (label + leader) | 3 | 10 |
| Hidden references | none | none (R16-R19 share one label, "R16-19") |
| Parts without a 3D model | 4 (J7, SW1, SW2, F1) | **0** |
| Vias | 427 (275 GND) | 524 (353 GND: 45 fan-out, 144 island, 138 grid, 11 return, 15 pre-route) |
| Track length | 5978 mm, 1272 segments | 6116 mm (F.Cu 3243, B.Cu 2873), 1442 segments |
| USB D+ / D- | 15.6 mm (2 vias) / 14.8 mm, 0.8 mm apart | 15.4 mm (2 vias) / 14.8 mm, 0.6 mm apart, no double bend |
| Decoupling (cap pad to supply pad) | table below | unchanged, every cap within 3 mm |
| KiCad DRC (all severities, parity, refill) / ERC / check_netlist | 0 / 0 / 0, 0, OK | 0 / 0 / 0 (JLCPCB rules), 0, OK |

**Stack-up (option B of the pcb-layout-pro skill, `references/four-layer.md`).** JLCPCB JLC04161H-7628, 1.6 mm: L1 F.Cu signals + power + GND pour, L2 In1.Cu solid GND plane, L3 In2.Cu solid GND plane, L4 B.Cu signals + power + GND pour; no tracks on L2/L3. Option A (power areas on L3) was the default; B was chosen because:

- the three rails (5V, 3V3, 3V3P) each reach the whole board and meet on adjacent pins of every box header (pin 1 = 5V, pin 3 = 3V3P), so L3 cannot be split into areas; it would become a layer of 0.6 mm power tracks that crossed each other and cut the plane under every L4 signal;
- in JLC04161H-7628 L2 and L3 are 1.065 mm apart (core), so a power plane on L3 would add only ~4 pF/cm2 of plane capacitance; the decoupling caps do that job anyway;
- with B every signal layer has an unbroken GND plane 0.21 mm away and a layer change stays GND-to-GND (a GND via next to it carries the return); power currents are small (≤ 1 A on 5V), 0.6 mm tracks are plenty.

**JLCPCB rules (no extra cost).** Board minimums and the `.kicad_dru` follow JLCPCB's 4-layer capability page (read 2026-10-23, numbers in the skill's `references/jlcpcb.md`), at values that stay inside the standard price: no hole under 0.2 mm, 0.2 mm holes only with ≥ 0.45 mm vias (GND fan-out and stitching vias 0.45/0.2; signal and power vias 0.6/0.3), via hole to via hole 0.25 mm, pad hole to pad hole 0.45 mm, PTH hole to track 0.28 mm, inner PTH hole to copper 0.3 mm, track/space ≥ 0.1 mm (the net classes keep 0.2/0.2 and 0.6/0.25), copper 0.3 mm from the edge, silkscreen text ≥ 1.0 mm / 0.15 mm. Order options: 4 layers, JLC04161H-7628, 1 oz / 0.5 oz, impedance control off, tented vias (`out/jlcpcb/README.md`).

**Routing.** Same pre-routes as rev 2 (USB, LIS3DH fan-out, U1 decoupling, box-header GND stubs), now with 45° corners everywhere, and D+/D- leaving U9 on the line of J7's pads, so the pair runs straight with no 0.2 mm double bend. GND fan-out: 45 pads, 0.45/0.2 vias into the planes. Freerouting 2.4.1 routes F.Cu and B.Cu (the DSN has GND planes on all four layers, In1/In2 as plane layers), with its optimizer off: in 2.4.1 the optimizer stage starts from an older, less routed board (rev 3 runs: 1 connection open after routing, 23 after the optimizer). The one connection it left open (the LIS3DH supply group to the rest of 3V3P) is routed by `route_prep.py maze` (two-layer octilinear A*, 5 segments, no via). Session: `out/defuse32-carrier.ses`.

**Finish (`gen/polish.py all`, extended for rev 3).**

1. *Jogs: 110 -> 9.* After the rev 2.1 moves (extend, slide, push aside, corridor re-route), every run that still has a jog is ripped up and re-routed in jog-free mode: route_prep's maze search may not turn back to the heading it had before a 45° run shorter than 2.2 mm (that return is the audit's jog: offset < 1.5 mm, slanted part < 3 mm), with no 90° turn, on its own layer or over both outer layers with at most two vias; runs with T-junctions take their branches along; a run with no jog-free path gets the runs of other nets beside it ripped up as well and all of them routed again the same way. GND fan-out vias in the way are rebuilt round their pad (GND reaches the planes from anywhere). A last local pass catches jogs the re-routes leave behind (BUZZ- next to the U2_GPA7 via, fixed by moving that via down); IR between C1's pads went with its neighbours MCP_INT, SCL, T4 and T6 ripped up. Each change is checked by the exact clearance model and by KiCad's DRC before it is kept.
2. *Corners: 0 left.* Every 90° corner becomes two 45° bends (cut back up to 1 mm, or merged into the next 45° segment); where a track joins the corner (T-junction, e.g. at SW1) the joining track slides onto the new 45° segment, or the run is re-routed without the turn.
3. *Copper.* GND pours on F.Cu and B.Cu, solid planes on In1/In2 (clearance 0.2 mm, minimum width 0.2 mm, thermal reliefs 0.3 / 0.5 mm, island removal always). Every outer-layer pour piece is stitched into the planes (144 island vias), a 5 mm grid adds 138 more, and 11 GND vias sit next to the layer changes of the fast nets (USB, SPI, WS2812 data; none fits next to the SCK via at (78.95, 55.84)). No floating copper. **60 voids remain (137.8 mm2)**, all strips between tracks too narrow for a via with its clearances; the audit's via-fit test passes two of them, neither usable: one lies under the C10 label (no via under text), the other is the gap between two U7 pins (0.73 mm), where the 0.2 mm pad clearances leave no room.
4. *Silkscreen.* One size, 1.0 mm / 0.15 mm, 0 or 90°, beside one side of the part (≥ 40 % overlap with its span, never off a corner), ≤ 1 mm away, outside every courtyard, never over a via; rows aligned in part order (R6 R9 R5 R4 on one line; C6 and R20 right beside their parts); none on the bottom silkscreen. Parts with no free spot beside them get a callout: label a short way off with a 0.15 mm leader to the part (U8, R14, R15, R11, C14, C19, C4, R8, C18, C2). R16-R19 (boxed in by U5, J5, C19/C1 and J11) share one label, "R16-19", beside their row. Header names are one line along the header's long side: "J1  M1 RADIO" ... "J6  M6 SENSORS" (J5 reads "M5 PROBE  J5": the space right of it is R16-19's). Board legend, revision and the JLCPCB order-number spot are kept.
5. *3D models.* J7 (HRO TYPE-C-31-M-12, C165948), SW1/SW2 (XKB TS-1187A, C318884) and F1 (1812 PTC, C18198338) had no model in KiCad's library: `gen/fetch_3d.py` fetches the LCSC/EasyEDA STEP models with easyeda2kicad 1.0.1 into `3d/` (git-ignored: licence unclear for this MIT repository) and works out where each sits on our footprint by matching the pad sets (drilled pegs and shell legs weigh 5x). easyeda2kicad 1.0.1 places STEP models wrongly whenever EasyEDA's model origin is off the footprint origin or the model is rotated (it bakes the offset into the VRML only, before KiCad's rotation): J7 came out 2.4 mm too far toward its pads; fetch_3d.py corrects it (offsets in `gen/models3d.json`, applied by `gen_pcb.py`). Checked on renders: USB-C opening flush with the right edge, microSD slot on the bottom edge, buttons and fuse on their pads. F1's EasyEDA land pattern has a 3.7 mm pad pitch against KiCad's 4.275 mm, so the body is centred on our pads.

**What is left and why.** The 9 jogs, each a single 45° pair (`/usr/bin/python3 gen/polish.py jogs` lists them with what keeps them):

| Net, layer | At (mm) | Step | Kept by |
|---|---|---|---|
| 5V, B.Cu | (6.09, 32.27) | 0.20 | the ENC_SW via beside it; a T-junction pins the run |
| 5V, B.Cu | (11.57, 47.83) | 0.42 | the IR and SERVO_SIG vias on either side |
| SCL, B.Cu | (15.16, 63.79) | 1.21 | J4 pads 3 and 4, the SDA track and a GND via |
| SCK, B.Cu | (39.87, 17.27) | 1.01 | the pads / vias it joins leave no straight line |
| SCK, B.Cu | (50.88, 45.06) | 1.32 | crosses the BUZZ, LDO3, SDA and U2_GPA7 runs |
| 3V3, F.Cu | (79.36, 42.74) | 0.67 | T-junction at U7's supply pins |
| SIM4, F.Cu | (67.33, 27.94) | 1.25 | C3's pads and the 3V3P / SD_DET tracks |
| U0RXD, F.Cu | (70.59, 44.25) | 0.60 | between C7 pad 2 and U6 pad 2 |
| U0RXD, F.Cu | (72.63, 46.74) | 0.32 | the U0TXD via and the 3V3 track |

Each was tried with the local moves, the jog-free maze (12 mm window, two layers) and the rip-up of up to eight neighbouring runs; removing them needs a hand re-route of the crossing runs. The copper voids are the narrow strips above; the one fast-net layer change without a GND via beside it is SCK at (78.95, 55.84) (the return current changes plane, GND1 to GND2, at the nearest stitching via instead).

## Standards pass (2026-11-25): board rev 3.1, schematic rev 2.1

The owner asked to check the board and correct every error "with the skills and the standard used on the AirQuality project" (its `docs/hw/layout.md` §15 / §15.1: an audit against IPC-2221B class 2, IPC-2152, JLCPCB's capabilities, USB 2.0 / Type-C and the vendor guides, then scripted fixes with no part moved). Checked: IPC-2221B spacing / edge / annular ring, IPC-2152 track current, JLCPCB 4-layer and PCBA rules (fiducials, rails, component-to-edge, overhang, Economic vs Standard, CPL rotations), a power budget against F1, both AMS1117 and the USB source, USB 2.0 / Type-C (CC, VBUS capacitance, D+/D-, ESD, shield), the ESP32-WROOM-32E datasheet and Espressif's hardware design guidelines, every IC against its datasheet, protection of the plate signals, return paths, routing quality, copper voids, silkscreen and markings, schematic hygiene, the kicad-happy analyzers, Codex's independent audit (D01-D22) and a second review (Fable, F01-F09). Measurements: `gen/std_audit.py` (new, read-only, port of AirQuality's `std_audit.py`) and `gen/pcb_audit.py`. Fixes: `gen/std_fixes.py` (new; runs after `gen/polish.py all`). No existing footprint moved, rotated or swapped. The spec side is in [`../SPEC.md`](../SPEC.md), section "Rev 3.1 carrier, schematic rev 2.1". A read-only final check of that pass (N01-N12) found errors in it; round 2, the same day, applies its fixes, counts jogs and corners honestly and removes what can be removed ("Round 2" below). The numbers in this section are the final ones.

**Schematic rev 2.1 (owner-approved, 2026-11-25; not the 2-layer *board* rev 2.1 of October).** Two changes, both from the review, everything else in the schematic unchanged:
- Buzzer driver: **Q1 MMBT3904 -> SS8050** (C2150, JSCJ, SOT-23, Basic; same pins 1 B / 2 E / 3 C, JSCJ datasheet p.1; 1.5 A, hFE 200-350) and **R7 1 k -> 330 Ω** (C23138, as R1): 7.6 mA base current saturates Q1 at the 120-310 mA a 16-42 Ω magnetic buzzer takes at 5 V (the MMBT3904 is rated 200 mA). Same footprints, positions and copper.
- **R21 10 k WS_DATA -> GND** (C25804) at (44.30, 35.90), below the GPIO25 -> U4 pin 2 track: GPIO25 is high-Z during reset and U4's OE is tied low, so the buffer input was undefined at power-up. **R22 10 k MOSI -> 3V3P** (C25804) at (71.30, 64.50), left of J11: Espressif's "SD pull-up requirements" ask for 10 k on CMD (MOSI) as on DAT0-2, also in SPI mode. Both spots come from a search (courtyard clear, pads clear of other-net copper, nearest copper of both nets); the review's spots were not usable after the 5V feed (R22) or took C15's label place (R21). Coordinates are board mm from the top-left corner. `gen/std_fixes.py` (`new_parts`) adds them to the routed board (no board regeneration): R21 pad 1 joins the WS_DATA track with one 45° segment that meets it at 90° (0.9 mm), pad 2 the GND track below it; R22 pad 1 drops to the B.Cu 3V3P track through a via beside the pad, pad 2 runs on F.Cu to the MOSI via at (67.81, 66.81) (4.1 mm). Both carry LCSC / MPN fields from `design.py`, KiCad 3D models and a 1.0 mm label placed by the silkscreen rules.

| Check | rev 3 (commit 2b482c1) | rev 3.1 before round 2 | rev 3.1 (final) |
|---|---|---|---|
| KiCad DRC (all severities, `--schematic-parity --refill-zones --all-track-errors`) | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| ERC / `check_netlist.py` | 0 / OK | 0 / OK | 0 / OK (section 8 checks the schematic rev 2.1 parts; fiducials are board-only, no net) |
| Jogs (`pcb_audit.py`, pieces under 0.1 mm merged first) | **23** (the old audit showed 9: a step behind a router ring was not seen) | 15 (the old audit showed 14) | **7** (table below) |
| Tight corners (a turn of 90° or more within 0.45 mm) / hairpins (135° or more) | 30 / 3 | 32 / 3 | **23 / 1** (below) |
| Track ends joined by their round cap only / stray segments inside a pad or via / overlapping segments | 7 / 10 / 1 | 9 / 11 / 0 | **0 / 0 / 0** |
| Tracks entering a pad through its corner or at its rim (warning) | 28 | 35 | 11 (SMD pads; the 21 track ends that stopped on the rim of a header pad now end 0.15 mm or more inside it) |
| Right angles / off-angle segments (> 1° off 0/45/90) / acute junctions (`std_audit.py`) | 0 / 32 / 6 (3 inside a pad) | 0 / 0 / 0 | **0 / 0 / 0** |
| Segments < 0.1 mm | 155 on 29 nets | 93 on 24 nets (13 hooks of 4-6 pieces left: 12 corner arcs and a ring on IR) | 65 on 19 nets |
| Vias in or touching SMD pads | 7 | 0 | **0** |
| Fast-net layer changes with no GND via within 2.0 mm | 6 | 0 | **0** (largest left: SCK 1.92 mm, LDO4 1.80 mm, CS 1.76 mm) |
| 5V copper from F1 pad 2, network solve (1 oz, 25 °C) | U5 224 mΩ, U6 268, C1 207, J9 165, J4 188, J5 219 | U5 35, U6 48, C1 45, J9 56, J4 66, J5 69 | **U5 34 mΩ, U6 48, C1 41, J9 54, J4 66, J5 69** |
| 5V tracks | 0.6 mm | 29 segments (119 mm) at 0.8-1.2 mm | the same, and the C1 - U5 run 1.0 mm (was 0.6) |
| Regulator tab copper (SOT-223 pin 4) | pad only | F.Cu areas on U6 (3V3, 27.8 mm²) and U5 (3V3P, 36.4 mm²) | U6's area reaches down to the IO0 track (28.4 mm²); U5's is 34.2 mm² now that C19 / C2 pad 1 (and C8 pad 1 at U6) join through thermal reliefs; the tab pads stay solid |
| Under U8 LIS3DH (TN0018 §2.3, secondary source) | GND pour and vias | rule area: no pour, no vias inside the land ring | the same |
| Copper to the two long (100 mm) edges | pours 0.30 mm | pours 0.30 mm | **0.50 mm** on all four layers (V-cut rails possible); J11's shell pads 0.475 mm |
| Silkscreen violations / warnings / hidden part references (`pcb_audit.py`) | 0 / 0 / none | 0 / 0 / none | **0 / 0 / none** |
| Markings | references only | + EN, BOOT, OUT, G / + / S at J9, "rev 3.1  2026-11" | "S" on the same side of J9 as "G" and "+"; R21's label 0.25 mm further from R1; a leader from J11's label to the socket |
| Global fiducials | 0 | 3, centres 3.5-4.8 mm from the edges | 3, centres 3.9 mm or more from every edge (JLCPCB: 3.85 mm) |
| Edge stitching (points 1.5 mm inside the edge > 3 mm from a GND via) | 111 | 94 | 91 (left edge under U1 and bottom edge under J11: no via fits) |
| Copper voids >= 0.5 mm², each counted once (the audit lists a void once per zone that could fill it) | 60, 137.8 mm² | 72, 150.8 mm² | **66, 129.3 mm²** (3 pass the audit's via-fit test, none usable: below) |
| Vias / track length | 524 / 6116 mm | 538 / 6173 mm | 536 / 6168 mm |
| BOM / CPL | | schematic rev 2.1 lines; C1 turned by 180° (wrong) | schematic rev 2.1 lines; rotations checked against each part's LCSC footprint: C1 0, J7 90, Q1-Q3 and U4 180 (`out/jlcpcb/README.md`) |

**What changed (copper, silkscreen and board-only items, `gen/std_fixes.py`; each step is checked with the exact clearance model and KiCad's DRC).**

- *5V feed (Codex D03).* F1 reached the regulators only round the board (267 mΩ to U6). A new 0.6 mm feed runs F1 pad 2 -> C6 / U5 (38 mm, 8 vias, through the gaps the relaxed maze found) and C6 -> C7 / U6 (16 mm, 4 vias, jog-free); the 5V tracks are then widened to 1.2 / 1.0 / 0.8 mm wherever clearances allow (never wider than the smallest SMD pad they meet). In the review's 1.5 A case the drop on the board path falls from ~0.4 V to ~0.08 V (U6 input ~4.6 V instead of ~4.3 V, above the AMS1117's 1.3 V maximum dropout).
- *Regulator tabs (D04).* Solid F.Cu areas on U6's (3V3) and U5's (3V3P) tab pads, priority over the GND pour, for heat spreading.
- *LIS3DH (D12).* A rule area under U8: no GND pour and no vias inside its land ring (ST's TN0018 §2.3 as cited by ST; TN0018 itself could not be fetched). Paste apertures unchanged (unverified guidance).
- *Routing.* The router's micro-loops (≥ 3 segments shorter than 0.3 mm folding back) collapse to the corner they stand for; that exposed 14 jogs the old audit had not counted. The polish jog tools then run with the pours lifted: 6 fixed for good; 7 maze re-routes only moved their step behind a new ring (collapsed again, see below). Two hand edits (SCL near J4, SCK bus near U2) replace runs the tools could not straighten. 32 off-angle segments (router remnants, 22.5° fan-out stubs) become 0/45/90; 6 acute junctions are rebuilt as 45° or square T's; the vias in or touching an SMD pad (GND fan-outs at C1, C2, C8, U2 pins 15 / 16, U3 pin 16; the MCP_INT via in R4 pad 2) move clear of the pad, with axial stubs; IR is re-routed round the moved R4 via.
- *Return vias (D17).* A GND via within 0.8-1.8 mm of each fast-net layer change that had none within 2 mm (CS x2, LDO2, LDO3, LDO4; LDI after the edits); the stitching vias in the way move.
- *Edge stitching.* 4 GND vias where the outer pours reach the edge more than 3 mm from a via.
- *Silkscreen (D21, D22).* EN beside SW1, BOOT beside SW2, OUT beside J10, G / + / S beside J9 pins 1-3, legend "rev 3.1  2026-11" (title block rev 3.1, 2026-11-25), JLCJLCJLCJLC kept. R21 / R22 labelled by the same rules (J11's label moves to the right of J11 to make room for R22's). Footprint silk widths unchanged (D20: widening them would make the DRC library-parity check report every footprint).
- *Fiducials (second review F02).* FID1 (3.9, 21.3), FID2 (90.3, 4.8), FID3 (94.8, 61.4) board mm from the top-left: KiCad `Fiducial_1mm_Mask2mm`, board-only (excluded from BOM and position files, no reference printed: a fiducial is not a part), centres 3.9 mm or more from every edge (JLCPCB asks for 3.85 mm from the panel edge), triangle across the board.
- *Order files.* Board-only footprints are skipped in the BOM / CPL. The CPL rotations were checked against the LCSC footprint of every polarised or multi-pin part (final check N01 / N02, table in `out/jlcpcb/README.md`): C1 (C72494) keeps KiCad's angle, 0, as in rev 3 (its LCSC footprint has "+" on the same side as KiCad's; the first rev 3.1 file had turned it by 180°, which would have reversed it); Q1-Q3 and U4 go out at 180 and J7 at 90 (rev 3 had 270 for all five).
- *Schematic rev 2.1* (above): Q1 / R7 values, R21 / R22 added and joined.

**Round 2 (final check N01-N12, 2026-11-25; `gen/std_fixes.py`, function `round2` and the list `R2`).** The first pass of this section was checked read-only by a second reviewer; round 2 applies that check and goes on from it.

- *The count (N04, N08).* `gen/pcb_audit.py` missed sideways steps behind pieces shorter than 0.1 mm (router rings, hooks, arcs of 0.05 mm steps). It now merges every connected group of such pieces into one point before it looks for jogs, and also reports tight corners (a turn of 90° or more made within 0.45 mm of track: a chamfer too short to see), hairpins (135° or more), track ends that reach a pad or a track only with their round cap, stray, duplicate and overlapping segments, and, as a warning, tracks that enter a pad through its corner or at its rim. Command line and JSON format are unchanged (new kinds in `routing_violations` / `routing_warnings`). By this count rev 3 had 23 jogs, 30 tight corners and 3 hairpins, not 9 / 0 / 0.
- *Jogs: 15 -> 7.* Eight went, each with the runs and vias round it, by hand-designed paths (`R2`): DTR's two and LDR's at Q3 (the IO0 via 0.30 mm right, the IR via 0.36 mm right, T6's 13 mm vertical 0.05 mm right, so DTR and LDR run straight between R13, the two vias and T6); U0RXD's second and 3V3's between U6 and U7 (the U0TXD via 0.47 mm right along its B.Cu track); KEY's at U3 (MCP_INT leaves its via straight, KEY runs on one line to a single 1.52 mm lane change, and U0RXD loses the two vias and the 1.1 mm of B.Cu that hid a 0.29 mm step); SDA's on B.Cu (SCL and SDA re-laid through their vias, the doubled SCL track and the half-joined SDA pieces gone); IR's hidden one between C1's pads (N04: no 45° track fits between the two pad corners, 0.56 mm free against 0.65 needed, so IR crosses the gap square for 2.15 mm). No footprint moved; five signal vias moved by 0.10-0.47 mm, two U0RXD vias were deleted.
- *Corners: 32 tight + 3 hairpins -> 23 + 1.* A rule widens a tight corner to one 45° chamfer of at least 0.45 mm where that keeps every clearance and makes no jog (7 corners); hand edits remove SCK's 0.07 mm piece on B.Cu (N05), the tip of WA6's detour (N05), and the two hairpins where a track left a header pin the wrong way (WB2 at J4 pin 15, SIM2 at J6 pin 15). The rest are listed below with what is in the way.
- *Joins (N07).* The 3V3 track between U7 pins 16 and 4 ended 0.2 mm outside pin 16 and met pin 4 at its corner: it now starts and ends on the pins' centre lines inside the pads. Looking for the same defect over the whole board found 9 cap-only joins (3V3 at R10 and SW1, 3V3P at the LIS3DH, SDA on B.Cu), 11 stray segments lying inside one pad or via and joining nothing, and 21 track ends that stopped on the rim of a header pad: all fixed (the last by letting each track run on 0.2-0.5 mm along its own line, so that it ends 0.15 mm or more inside the pad).
- *Gaps (N06).* The C1 - U5 5V run is 1.0 mm wide (was 0.6), its centre 0.2 mm higher, so the 15 x 0.8 mm bare strip above it is gone and its lower edge stays 0.25 mm above the IR via; the B.Cu 5V trunk moved 0.08 mm right (x 49.52), which closes the 15.6 x 0.75 mm strip beside SCK (x 49.94, as the check proposed, would touch the BUZZ via); U6's tab copper reaches down to the IO0 track; two B.Cu pour pieces that had one GND via have two again. The moved runs also closed the strips between KEY and U0RXD (5.1 mm²) and between SCL and SDA on B.Cu (2.6 mm²).
- *Edge copper (N03).* The four GND zones stop 0.5 mm inside the two long edges (0.3 mm before), so JLCPCB may join its rails there by V-cut (0.4 mm from the cut line asked); nothing else lies within 1.2 mm of those edges except J11's shell pads (0.475 mm). The fiducials' centres are 3.9 mm or more from every edge (FID1 was 3.80, FID3 3.50).
- *Reflow (N11).* C19, C2 and C8 pad 1 sit in the regulator tab copper: they now join it through thermal reliefs (0.3 mm gap, 0.5 mm spokes), like their GND pads, so both ends of each capacitor heat alike; the tab pads stay solid.
- *Silkscreen (N10).* "S" stands left of J9 pin 3, in line with "G" and "+" (the stitching via that held the spot moved 0.65 mm down); R21's label moved 0.25 mm down, away from R1's pads, still beside R21's lower pad; a 45° leader joins J11's label to the socket's outline (a level one read as a minus sign). FID1-FID3 print no reference (board-only fiducials).
- *Repeatable (N09).* `std_fixes.py` on rev 3's board gives this board exactly; a second run changes nothing and leaves the file untouched: stage 1 (the tool steps: maze re-routes, widening, stitching) is skipped on a board that already says rev 3.1, and round 2 checks its own geometry.

**Stays open, and why.**

- *7 jogs*, each a single 45° pair that something physical holds (measured on the board; coordinates in board mm):

| Net, layer | At | Step | What is in the way |
|---|---|---|---|
| 5V, B.Cu | (5.89, 32.47) | 0.20 | The lane between the U2RX track (x 5.24) and the ENC_SW track (x 6.54) is 1.30 mm wide: exactly the 0.6 mm 5V track with 0.25 mm on each side, at x 5.89. The U2RX via just above needs the track at x 6.09 or more. ENC_SW cannot move right (the IR via at (7.14, 42.44) is 0.20 mm from it). 0.20 mm missing |
| 5V, B.Cu | (11.15, 47.41) | 0.42 | The run loops over the SERVO_SIG via (12.00, 47.08), which needs it at x 11.15 or less, and 2.8 mm further down passes the IR via (10.72, 49.85), which needs x 11.57 or more. The loop's two legs are 1.30 mm apart, centre to centre, below the via (the MCP_INT track bounds the right leg); legs on both sides of a via need 1.70 |
| SCL, F.Cu | (19.51, 7.90) | 0.78 | Between J1 pins 4 and 6 (1.7 mm pads on a 2.54 mm pitch) only a vertical track fits: a 45° one would overlap both pads by 0.05 mm. The LDI track below limits that vertical to 1.99 mm, a 1.41 mm step where 1.50 would count as a lane change |
| MISO, F.Cu | (71.92, 53.17) | 0.65 | U5 pad 2 (lower edge y 52.75) needs MISO at y 53.10 or more; J11 pad 9 (upper edge y 52.87), 3.6 mm to the right, needs y 52.57 or less: a step of 0.53 mm at least, and it has to sit between the C6 GND via and the 5V feed via |
| T3, F.Cu | (10.65, 32.60) | 0.50 | U2RX track (y 31.857), SD_CS via (32.459), T3, U0TXD via (33.605), EN track (34.207): 2.35 mm for four 0.60 mm spacings: 0.05 mm missing, so T3 passes the SD_CS via at y 33.10 and the U0TXD via at y 32.60. U2RX cannot go up (its via would come within 0.17 mm of the 5V trunk), EN cannot go down (the CS via is 0.21 mm below it) |
| SIM4, F.Cu | (67.33, 27.94) | 1.25 | The left lane is held at y 29.03-29.22 (C3 pad 1 above, SIM2 below), the right lane at y 27.90-28.08 (SCL via above, SERVO_SIG via below): a step of 0.95 mm at least. SERVO_SIG runs on to the right on F.Cu, so SIM4 cannot stay below it |
| U0RXD, F.Cu | (70.59, 44.25) | 0.60 | The corners of U6 pad 2 and C7 pad 2 are 0.085 mm apart across a 45° line, so the track crosses between the pads (0.92 mm apart) square; the 3V3 track from U6 pad 2 ends that vertical after 1.07 mm |

- *23 tight corners and 1 hairpin.* A wider chamfer does not fit, or would turn the corner into the audit's jog (45° - short straight - 45°); most sit where a track threads the 2.54 mm pin grid of a header or leaves a pad:

| Net, layer | At | What is in the way |
|---|---|---|
| 3V3P, F.Cu | (41.05, 32.40), 90° in 0.42 mm | 0.25 mm supply fan-out inside the LIS3DH pad field: C15 pad 2 is in the way of a wider chamfer |
| 3V3P, F.Cu | (36.45, 33.50), 90° in 0.35 mm | the same fan-out: the two arms are 0.30 and 0.32 mm long, between LIS3DH pads |
| SCL, F.Cu | (32.06, 29.06), 90° in 0.10 mm | 0.1 mm tip of a 1.6 mm detour; a 0.5 mm tip moves the lower leg to 0.09 mm from R8 pad 1 |
| SD_CS, F.Cu | (83.28, 52.57), 90° in 0.21 mm | 0.21 mm chamfer; a 0.7 mm one would touch J11 pad 1 |
| SD_DET, B.Cu | (77.90, 49.34), 90° in 0.29 mm | tip of a V-shaped detour round a 3V3P via; a flat tip would make it shallower than 1.5 mm, a jog |
| 3V3, F.Cu | (81.29, 43.90), 90° in 0.10 mm | the 90° turn into U7 pin 4: pins 15 and 3 leave a 0.80 mm throat, the 0.6 mm track with its clearances needs 1.10, so no 45° run reaches pin 4; a 45° chamfer would pair with the 45° run before it into a 0.4 mm jog |
| 3V3, F.Cu | (29.92, 31.47), 90° in 0.31 mm | arc of router pieces below R11 pad 1; a 45° run in its place comes within 0.25 mm of the U0TXD vias at (31.00, 32.37) and (31.77, 30.73) |
| SDA, B.Cu | (96.36, 34.09), 90° in 0.31 mm | the run goes round J6 pins 5 / 7 / 9 between the pin rows; pad J6.5 is inside the corner |
| SDA, B.Cu | (96.26, 26.54), 90° in 0.31 mm | the same run; pad J6.9 is inside the corner |
| LDO1, F.Cu | (19.57, 3.70), 90° in 0.31 mm | the turn into the 0.84 mm gap between J1 pins 3 and 5 (pad J1.5 inside the corner); a chamfer would pair with the 45° exit 1.7 mm below into a jog |
| ENC_B, F.Cu | (16.78, 6.15), 90° in 0.31 mm | the turn out of the gap between J1 pins 7 and 9 (pad J1.8 inside the corner); a chamfer would make a jog with the 45° piece before the gap |
| U3_GPA7, B.Cu | (29.53, 19.77), 90° in 0.42 mm | the track leaves its via horizontally for 0.30 mm, then 45°: leaving at 45° would shorten the 2.2 mm straight beside the MCP_INT via to 1.9 mm, a jog |
| IR, F.Cu | (93.82, 26.46), 90° in 0.31 mm | the turn between J6 pins 11 and 12 into the channel between the pin rows (pad J6.12 inside the corner); a chamfer makes two jogs with the 45° pieces on either side |
| SIM2, F.Cu | (55.92, 24.52), 90° in 0.28 mm | 0.28 mm chamfer; a 0.7 mm one comes within 0.06 mm of U2 pad 3 |
| CS, F.Cu | (2.79, 50.30), 90° in 0.33 mm | 0.33 mm chamfer; J9 pad 1 is inside the corner |
| USB_DP, F.Cu | (93.55, 49.05), 90° in 0.40 mm | hand-drawn link between J7's two D+ pads, 1.0 mm apart: three bends 0.40-0.42 mm apart, kept as drawn (USB pair) |
| USB_DM, F.Cu | (91.10, 49.55), 90° in 0.42 mm | hand-drawn D- entry at U9, bends 0.42 mm apart, kept as drawn (USB pair) |
| TM_CLK, B.Cu | (38.42, 8.69), 90° in 0.31 mm | the turn into the gap between J2 pins (pad J2.12 inside the corner); a chamfer would pair with the 45° piece 1.7 mm above into a jog |
| WB3, B.Cu | (34.13, 47.80), 90° in 0.05 mm | 0.05 mm tip of a 1.6 mm detour; the U0TXD track runs 0.2 mm outside the tip, and a flat cut into the tip would leave it 1.35 mm deep, a jog |
| WB4, F.Cu | (37.70, 51.66), 90° in 0.14 mm | 0.14 mm chamfer; a 0.45 mm one would pair with the 45° piece 2.2 mm above into a jog |
| WB5, F.Cu | (39.00, 24.62), 90° in 0.44 mm | 0.44 mm chamfer, 0.01 mm short of the rule: U3 pad 7 is 0.2 mm from it |
| WA6, B.Cu | (31.99, 25.83), 135° in 0.24 mm | hairpin: the track wraps round the WB3 via (32.66, 27.60) with the U3 GND fan-out via (31.40, 27.25) 1.26 mm from it; a 45° pass between the two needs 1.18 mm between the centres across the line and has 1.14 |
| WA5, F.Cu | (31.08, 15.02), 90° in 0.37 mm | zig-zag between U3 pads 27 and 28, 0.2 mm from the pads |
| WA5, F.Cu | (31.35, 17.41), 90° in 0.41 mm | the same zig-zag (U3 pad 27) |

- *Fast-net vias:* SCK at (78.95, 55.84) 1.92 mm, LDO4 at (45.14, 64.62) 1.80 mm and CS at (10.28, 46.77) 1.76 mm from the nearest GND via (all within 2 mm): every closer spot is taken by pads, tracks or labels.
- *Copper voids:* 66 voids, 129.3 mm², each counted once (rev 3: 60, 137.8 mm²; before round 2: 72, 150.8 mm²). Round 2 closed 21.0 mm² (the strip above the C1 - U5 run, the strip beside the B.Cu 5V trunk, the strips between KEY / U0RXD and between SCL / SDA) and opened two small ones: 0.57 mm² between the DTR and IO0 runs into Q3 (a 0.38 mm pocket the straightened DTR lengthened past the 0.5 mm² threshold) and 0.55 mm² between U7 pins 3 and 4 (the 0.67 mm pin gap, bare now that the 3V3 track no longer runs along pin 4's edge). What is left are strips between tracks too narrow for a via with its clearances. The audit's via-fit test passes 3, none usable: (5.29, 46.09) lies under C10's label, (79.21, 46.04) is the 0.73 mm gap between U7 pins 1 and 2 (the only centre is in the GND pad), and (70.12, 48.68) is a 0.53 mm strip between U5 pin 3, the 5V feed and U0TXD, where the stitching pass (vias 0.15 mm clear of SMD pads, none under labels) finds no spot.
- *J5 label* stays "M5 PROBE  J5": "J5" on the left needs the space of the SCK / MOSI vias and C1's courtyard (searched: 163 spots blocked by signal vias, 394 by other items).
- *Edge stitching* along the left edge (U1's module body) and the bottom edge at J11 (card slot): no via fits under those parts.
- *Neck-downs:* 3V3P keeps 18 segments at 0.25-0.4 mm (LIS3DH pad field and between header pins, 18 mm in all, ≤ 0.45 A) and VBUS one 0.4 mm segment (1.2 mm) at J7's pins; IPC-2221B gives ~0.9 A at 10 °C rise for 0.25 mm on an outer layer (every track is on one), twice the 0.45 A design current.
- *Silk line width:* KiCad's footprints draw 0.12 mm silk (JLCPCB's minimum line is 0.15 mm; JLCPCB prints them, possibly thinner): left as is (D20).
- *Pad entries:* 11 tracks enter an SMD pad through its corner or along its edge (audit warning): the 5V feed stubs at F1 pad 2, C6 pad 1 and C7 pad 1 (placed that way on purpose, clear of the SD_CS track and the labels), 3V3 at U6 pin 2, C8, R10 and R11, MISO at J11 pin 7, KEY at U2 pin 5, SERVO_SIG at U1 pin 12. Off-axis pad entries (`std_audit.py`, informational) and tracks between adjacent pads of one part (all ≥ 0.2 mm clear): left.

**Needs a part move or a schematic / BOM change (proposals for a decision, not done).** IDs are Codex's (D) and the second review's (F); LCSC numbers as read 2026-11-25.

- D01 USB-C current: the board presents 5.1 kΩ Rd and never reads CC (Type-C R2.0 p.219), so it can draw up to 2.4 A from a source that offers 500 mA. Fix: CC1 / CC2 to two ADC inputs (no free ADC1 pin: needs a pin swap) or TUSB320LIRWBR (C2836598, Extended, Standard PCBA only) on I2C; until then the bring-up note "5 V source of 2 A or more" is the rule.
- D02 inrush: 240 µF sits on 5V behind F1, against USB 2.0's 10 µF attach limit (§7.2.4.1). Fix: AP22802AW5-7 (C211404, Extended, SOT-25, 2 A, soft start) between F1 pad 2 and the 5V bulk, with C1 behind it.
- D05 AMS1117 stability: the AMS datasheet (p.4 "Stability") specifies a 22 µF solid tantalum output capacitor and says nothing about ceramics; C2 / C8 are 22 µF X5R 0805 MLCC (a few mΩ ESR). Many boards run it; minimum: a load-step test on the first boards. Fix: TAJA226K010RNJ (22 µF 10 V tantalum, C11366, Extended; A case 3216, a footprint change at the same spot) or an LDO stable with ceramics in the same SOT-223 pinout (AP7361C-33ER, C3743528, Extended, low stock).
- D09 / D16 plate signal protection: 510 Ω (C23193, Basic) in series on the touch lines T0 / T3 / T4 / T6 near U1, SRV05-4 (C2985619, Extended, SOT-23-6) at J4 / J5 / J6, 100 Ω (C22775, Basic) on the J5 UART / SPI lines, 33 Ω (C23140, Basic) on SCK at U1: needs room at every header (part moves). Not approved.
- D10 fault isolation: a PTC per branch (JK-nSMD050-30, C720075, 0.5 A, 1206, Extended) on each header pin 1, J9 pin 2 and J5 pin 3: needs room at each header.
- D11 I2C pull-ups: 4.7 kΩ allows 251 pF at 100 kHz (UM10204 §7.1); the six ribbons and modules are estimated at 150-250 pF, so the firmware's 100 kHz is inside and 400 kHz is not. Fix if the measured rise time is long: R2 / R3 -> 2.2 kΩ (C4190, Basic, same spots).
- D18 U0TXD series resistor (Espressif checklist: 499 Ω): 499 Ω (C23065, Extended) or 470 Ω (C23179, Basic) near U1 pin 35; no free spot without moving parts.
- F03 ribbon pin order: not approved.
- F05 R8 (GPIO2 / SD_CS pull-down): 10 kΩ -> 2.2 kΩ (C4190, Basic) keeps GPIO2 below VIL with a card that pulls DAT3 up; until then the bring-up note (remove the card to flash) stays.

**Order (out/jlcpcb/README.md):** Standard PCBA (U1 ESP32-WROOM-32E C701341, U8 LIS3DHTR C15134 and C1 C72494 are "Standard Only" at JLCPCB; U8 needs X-ray), 5 mm edge rails on the top and bottom edges only (U1 overhangs the left edge by 6.2 mm, J7 is flush with the right edge; confirm with JLCPCB), fiducials FID1-FID3 on the board, U1's open thermal holes noted, C1 first in the placement preview ("+" toward the board's left).

**Bring-up access (no test points on this board).** 5V: any box-header pin 1, J9 pin 2. GND: box-header pin 2, J9 pin 1, J10 pin 5. 3V3P: box-header pin 3. 3V3: C9 / C10 / C12 / C13 pin 1 or U6's tab. EN: SW1 (label EN) pin 1 or C11 pin 1. IO0: SW2 (label BOOT) pin 1 or R11. TXD0 / RXD0: U7 pins 3 / 2 (SOIC clip) or U1 pins 35 / 34.

## Rev 2 overview

- **Board**: 100 x 70 mm, 4 layers (rev 3; rev 2/2.1 had 2), 1.6 mm, 4 x M3 (Ø3.2) non-plated holes 4 mm from the corners. SMD on the top side (JLCPCB assembly); the IDC box headers and the 2.54 mm pin headers are through-hole.
- **ESP32**: U1 ESP32-WROOM-32E-N4 at the left edge, turned 90° so the antenna end points left. The antenna region (footprint y < -6.56 mm) lies beyond the board edge x = 0. The footprint keeps KiCad's antenna keep-out zone (no tracks, vias, pads, pours or footprints) and the antenna outline on F.Fab. EN (SW1) and BOOT (SW2) buttons; EN RC 10 kΩ + 1 µF; GPIO0 10 kΩ pull-up.
- **USB-C** J7 (16-pin, HRO TYPE-C-31-M-12): power input and programming port only. CC1/CC2 5.1 kΩ to GND (5 V sink). VBUS -> F1 PTC (2 A hold, 4 A trip) -> `5V`. U9 USBLC6-2SC6 on D+/D-. Shield to GND.
- **USB-UART**: U7 CH340C at 3.3 V (V3 tied to VCC), no crystal, on UART0: CH340C TXD -> `U0RXD` (GPIO3), RXD <- `U0TXD` (GPIO1). Auto-reset with two MMBT3904 (Q2 DTR -> EN, Q3 RTS -> IO0, 10 kΩ base resistors).
- **Power**: C1 220 µF bulk on `5V`. Two AMS1117-3.3 (SOT-223, JLCPCB Basic C6186): U6 `5V` -> `3V3` for the ESP32 and the CH340C (C7 10 µF in, C8 22 µF out, C9 10 µF + C10 100 nF at the module's 3V3 pin); U5 `5V` -> `3V3P` for the plates, U2/U3, LIS3DH, microSD and all pull-ups (C6 10 µF in, C2 22 µF + C19 100 nF out). The AMS1117 datasheet asks for 10 µF on the input and 22 µF on the output for stability (it specifies tantalum; the 22 µF X5R ceramics here are the usual ESP32-board practice). U5 replaced the SPEC's AP2112K-3.3 (Extended) on 2026-10-23: one Basic part instead of an Extended one, 1 A instead of 600 mA, at the cost of a SOT-223 footprint, 1.1 V dropout (5 V in: fine) and ~5 mA quiescent current.
- **Expanders**: U2/U3 MCP23017-E/SO at 0x20/0x21, rev 1b allocation unchanged, 100 nF each (C3/C4). INTA/INTB mirrored, open-drain, wired-OR to GPIO35.
- **Tilt sensor**: U8 LIS3DH (LGA-16) in I2C mode (CS high) at 0x19: SA0 high through R20 (10 kΩ, keeps ERC clean: SDO is an output pin in the symbol). INT1/INT2 not connected (polled). C14/C16 100 nF on VDD/VDD_IO, C15 10 µF.
- **microSD**: J11 Hirose DM3AT-SF-PEJM5 push-push socket, SPI mode on SCK 18 / MOSI 23 / MISO 19, `SD_CS` = GPIO2 (R8 10 kΩ pull-down kept). DAT0/DAT1/DAT2 10 kΩ pull-ups (R16-R18). C17 100 nF + C18 10 µF.
- **Card detect** (checked 2026-10-23 against Hirose's DM3 catalog: "The card detection switch is Normally Open"; distributors list the DM3AT-SF-PEJM5 with an N/O detect switch): the switch between DET_A (pad 10) and DET_B (pad 9) is open without a card and closes when a card is inserted. DET_A goes to GND, DET_B -> `SD_DET` (U2 GPB5) with R19 10 kΩ pull-up to 3V3P. **`SD_DET` low = card present, high = no card.** Firmware: `CONFIG_D32_SD_DET_ACTIVE_HIGH` must be **n** for this board, which is the Kconfig default (`y` is for the rev 1 Adafruit-style breakout, whose DET is high with a card).
- **WS2812 buffer**: U4 74AHCT1G125 (SOT-23-5) at 5 V, OE low, R1 330 Ω in series -> `LDI`. Chain: LDI -> M1 -> LDO1 -> M2 -> LDO2 -> M3 -> LDO3 -> M4 -> LDO4 -> M5 -> LDO5 -> M6 (end).
- **Buzzer**: Q1 low side, R7 base resistor from GPIO26, D1 1N4148WS across the buzzer (BUZZ+ = 5V on J2 pin 11, BUZZ- on J2 pin 10). Schematic rev 2.1: Q1 SS8050 (was MMBT3904), R7 330 Ω (was 1 kΩ).
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

Checked 2026-10-23 on the JLCPCB parts API: every part in stock, package matches the footprint. 68 placed parts (59 SMD, 9 THT) plus 4 mounting holes and 3 board-only fiducials (schematic rev 2.1: + R21, R22); `out/bom.csv` has the grouped BOM with the same fields.

| Refs | Qty | Value | Footprint | LCSC | MPN | JLC |
|---|---|---|---|---|---|---|
| C3-C5, C10, C12-C14, C16, C17, C19 | 10 | 100 nF | C_0603 | C14663 | CC0603KRX7R9BB104 | Basic |
| C11 | 1 | 1 µF | C_0603 | C15849 | CL10A105KB8NNNC | Basic |
| C6, C7, C9, C15, C18 | 5 | 10 µF | C_0805 | C15850 | CL21A106KAYNNNE | Basic |
| C2, C8 | 2 | 22 µF | C_0805 | C45783 | CL21A226MAQNNNE | Basic |
| C1 | 1 | 220 µF 10 V | CP_Elec_6.3x5.4 | C72494 | RVT1A221M0605 | Extended |
| R4-R6, R8-R13, R16-R22 | 16 | 10 kΩ | R_0603 | C25804 | 0603WAF1002T5E | Basic |
| R14, R15 | 2 | 5.1 kΩ | R_0603 | C23186 | 0603WAF5101T5E | Basic |
| R2, R3 | 2 | 4.7 kΩ | R_0603 | C23162 | 0603WAF4701T5E | Basic |
| R1, R7 | 2 | 330 Ω | R_0603 | C23138 | 0603WAF3300T5E | Basic |
| Q2, Q3 | 2 | MMBT3904 | SOT-23 | C20526 | MMBT3904 | Basic |
| Q1 | 1 | SS8050 | SOT-23 | C2150 | SS8050(RANGE:200-350) | Basic |
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

All three are written by `gen/gen_lib.py` from the installed KiCad libraries. KiCad 10.0.7 here ships no 3D model for J7 (HRO USB-C), SW1/SW2 (XKB TS-1187A) and F1 (1812 fuse); since rev 3 `gen/fetch_3d.py` supplies them (LCSC/EasyEDA models, git-ignored `3d/`), so the renders and `../cad/carrier.step` show every part.

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

## Routing (rev 2 / 2.1, 2 layers)

Rev 3 re-routed the board on 4 layers with the same pre-routes and tools (section "Rev 3"); this section and the next describe the 2-layer board it replaced.

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

`out/jlcpcb/` holds the 4-layer Gerbers + drill (zip), the JLCPCB BOM (Comment, Designator, Footprint, LCSC, Quantity; 23 lines, 59 SMD parts) and the CPL (Designator, Val, Package, Mid X, Mid Y, Rotation, Layer; 59 top-side parts), written by `gen/gen_jlcpcb.py` with the conventions of the JLCPCB Tools plugin (Bouni/kicad-jlcpcb-tools 2026.04.03); [`out/jlcpcb/README.md`](out/jlcpcb/README.md) has the order settings.

- Single-sided SMD assembly, all on top. Coordinates: drill/place origin at the board's bottom-left corner (Gerbers, drill and CPL agree).
- **Rotations**: the CPL position is the centre of each footprint's pads and the rotation is KiCad's plus a correction per part: rules on the reference where the part's own LCSC footprint decides (Q1-Q3 and U4 +180, J7 +0), then the JLCPCB Tools plugin's package rows (U1 +270, U2 / U3 / U7 SOIC +270, U5 / U6 SOT-223 +180, U9 SOT-23-6 -90); C1 and every other part go with KiCad's angle. Every polarised or multi-pin part was compared with its LCSC footprint (table and method in `out/jlcpcb/README.md`). JLCPCB's placement preview remains the authority: check it in the order given there, C1 first ("+", pad 1, 5V, toward the board's left edge), then J7, Q1-Q3, U4, U9, U8, D1.
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
| `gen/pcb_audit.py` | Finish audit (the pcb-layout-pro skill's script, with the routing checks of 2026-11-25: pieces under 0.1 mm merged before jogs are counted; tight corners, hairpins, cap-only joins, stray, duplicate and overlapping segments, pad-corner entries): copper voids, jogs, corners, silkscreen problems DRC does not flag |
| `gen/std_fixes.py` | Rev 3.1 standards pass, run after `polish.py all` (section "Standards pass (2026-11-25)"): stage 1 (tool steps, once, on the rev 3 board) and round 2 (explicit edits; a second run changes nothing) |
| `gen/std_audit.py` | Standards measurements, read-only: IPC-2221B / IPC-2152 current, spacing, edge, USB pair, return vias, edge stitching, mask webs, rings, vias in pads, LCSC fields, silk strokes, off-angle segments, acute junctions, tracks between pads, pad entries, slivers (`out/std_audit.json`) |
| `gen/gen_jlcpcb.py` | JLCPCB Gerbers, drill, zip, BOM and CPL into `out/jlcpcb/` |
| `gen/check_netlist.py` | Rev 2 checks (see Status) |
| `gen/sexp.py`, `gen/symlib.py` | S-expression reader/writer; symbol flattening (`extends`) |
| `out/defuse32-carrier.pdf` | Schematic PDF (5 pages) |
| `out/bom.csv` | BOM grouped by value, footprint and LCSC number, with MPN, manufacturer and Basic/Extended |
| `out/defuse32-carrier.net` | Schematic netlist, input of `check_netlist.py` |
| `out/defuse32-carrier.ses` | The Freerouting session the board was built from |
| `out/erc.rpt`, `out/drc.rpt`, `out/audit.json`, `out/std_audit.json` | Latest check reports (DRC, ERC, finish audit, standards measurements) |
| `out/jlcpcb/` | JLCPCB fabrication and assembly files (rev 3.1, 4 layers) |
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
/usr/bin/python3 gen/std_fixes.py           # rev 3.1 standards pass + schematic rev 2.1 parts (after polish.py all; ~17 min, mostly the jog tools; a second run changes nothing)
# (D32_BOARD=/path/copy.kicad_pcb runs any of it on a copy with its own .kicad_pro/.kicad_dru)

# checks
kicad-cli sch export netlist -o out/defuse32-carrier.net defuse32-carrier.kicad_sch
kicad-cli sch erc --severity-all -o out/erc.rpt defuse32-carrier.kicad_sch
kicad-cli pcb drc --severity-all --schematic-parity --refill-zones --all-track-errors -o out/drc.rpt defuse32-carrier.kicad_pcb
/usr/bin/python3 gen/check_netlist.py out/defuse32-carrier.net defuse32-carrier.kicad_pcb
/usr/bin/python3 gen/pcb_audit.py defuse32-carrier.kicad_pcb --json out/audit.json   # exit 1 while violations remain
/usr/bin/python3 gen/std_audit.py defuse32-carrier.kicad_pcb --json out/std_audit.json   # standards measurements (read-only)

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
