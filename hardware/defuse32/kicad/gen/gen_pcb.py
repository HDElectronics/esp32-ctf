#!/usr/bin/env python3
"""Generate the defuse32-carrier.kicad_pcb (outline, holes, every footprint with its nets,
placed after design.PCB, unrouted) and the project file (net classes, JLCPCB design rules).
Routing, GND pours and stitching are added afterwards by route_prep.py and polish.py (see their
docstrings).

Rev 3 (2026-10-23): 4 copper layers on JLCPCB's JLC04161H-7628 stack-up, placement, schematic
and netlist as rev 2. Stack-up option B of the pcb-layout-pro skill (references/four-layer.md):
F.Cu signals + power + GND pour, In1.Cu solid GND plane, In2.Cu solid GND plane, B.Cu signals +
power + GND pour (reasons in kicad/README.md "Rev 3"). The stack-up is written into the board
file (STACKUP), the JLCPCB 4-layer limits into the project rules and the .kicad_dru (RULES, DRU);
3D models that KiCad's library lacks come from gen/models3d.json (fetch_3d.py).

Needs KiCad's Python:  /usr/bin/python3 kicad/gen/gen_pcb.py [--force]
Footprint-to-symbol links use the same deterministic UUIDs as gen_sch.py (path /sheet/symbol).

Once the board is placed or routed by hand, this script would throw that work away, so it refuses
to run when the existing board has tracks or vias; --force overwrites anyway. Board changes then go
schematic -> KiCad "Update PCB from Schematic".
"""
import json
import os
import re
import subprocess
import sys

import pcbnew

import design as D
from gen_sch import PROJECT, sheet_path, uid

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(HERE, ".."))
SYS_FP = "/usr/share/kicad/footprints"
OX, OY = 50.0, 50.0          # board top-left corner on the page (mm)
mm = pcbnew.FromMM


def P(x, y):
    """Board mm -> page position in nm, rounded (no 113.539999 mm from float sums)."""
    return pcbnew.VECTOR2I(int(round((OX + x) * 1e6)), int(round((OY + y) * 1e6)))


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = os.path.join(KDIR, "defuse32.pretty") if lib == "defuse32" else os.path.join(SYS_FP, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit("footprint not found: " + fpid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def silk_text(board, txt, x, y, size=1.0, angle=0, layer=pcbnew.F_SilkS, bold=False):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetPosition(P(x, y))
    t.SetLayer(layer)
    t.SetTextSize(pcbnew.VECTOR2I(mm(size), mm(size)))
    t.SetTextThickness(mm(size * (0.2 if bold else 0.15)))
    if angle:
        t.SetTextAngleDegrees(angle)
    board.Add(t)
    return t


def read_netlist():
    """Export the schematic netlist with kicad-cli and return ({(ref, pin): net}, {ref: fields})."""
    from sexp import find, find1, parse
    out = os.path.join(KDIR, "out", PROJECT + ".net")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    subprocess.run(["kicad-cli", "sch", "export", "netlist", "-o", out,
                    os.path.join(KDIR, PROJECT + ".kicad_sch")], check=True, stdout=subprocess.DEVNULL)
    root = parse(open(out).read())
    padnet = {}
    for net in find(find1(root, "nets"), "net"):
        name = find1(net, "name")[1]
        for node in find(net, "node"):
            padnet[(find1(node, "ref")[1], find1(node, "pin")[1])] = name
    fields = {}
    for c in find(find1(root, "components"), "comp"):
        d = {}
        for fld in find(find1(c, "fields") or [], "field"):
            d[find1(fld, "name")[1]] = fld[2] if len(fld) > 2 and not isinstance(fld[2], list) else ""
        for pr in find(c, "property"):
            d[find1(pr, "name")[1]] = find1(pr, "value")[1] if find1(pr, "value") else ""
        fields[find1(c, "ref")[1]] = d
    return padnet, fields


# ---------------------------------------------------------------- project: net classes + rules
# JLCPCB 4-layer capabilities (https://jlcpcb.com/capabilities/pcb-capabilities, read 2026-10-23;
# summary in the pcb-layout-pro skill, references/jlcpcb.md). The board minimums are JLCPCB's
# limits at standard price (nothing here makes the order cost more):
#   trace / space 0.09 / 0.09 mm on 4 layers -> 0.1 / 0.1 (the net classes use 0.2 / 0.2 and 0.6 / 0.25);
#   drill 0.15 mm costs extra, 0.2 mm holes are free with a via diameter >= 0.45 mm -> holes >= 0.2,
#   vias >= 0.45 (stitching 0.45 / 0.2, signal and power 0.6 / 0.3), annular ring >= 0.1;
#   via hole to via hole 0.2 -> 0.25; pad hole to pad hole (different nets) 0.45 (DRU);
#   via hole to track 0.2 -> hole clearance 0.2; PTH hole to track 0.28 (DRU), inner-layer PTH
#   hole to copper 0.3 (DRU); copper to routed edge 0.2 -> 0.3;
#   silkscreen: line >= 0.15 mm, text height >= 1.0 mm, 0.15 mm from pads.
SILK_RULES = (0.15, 1.0, 0.15)       # silk clearance, min text height, min text stroke (mm)
RULES = {
    "min_clearance": 0.1,
    "min_track_width": 0.1,
    "min_through_hole_diameter": 0.2,
    "min_via_annular_width": 0.1,
    "min_via_diameter": 0.45,
    "min_hole_to_hole": 0.25,
    "min_copper_edge_clearance": 0.3,
}
HOLE_CLEARANCE = 0.2
VIAS = ((0.6, 0.3), (0.45, 0.2))     # signal / power vias; GND fan-out and stitching vias
BOARD_REV = "3"
LAYER_NAMES = {pcbnew.In1_Cu: "GND1", pcbnew.In2_Cu: "GND2"}
# JLC04161H-7628 (https://jlcpcb.com/impedance): 1 oz outer, 0.5 oz inner copper, 7628 prepreg
# 0.2104 mm (Er 4.4) between L1-L2 and L3-L4, 1.065 mm core (Er 4.6), 1.6 mm finished.
STACKUP = """		(stackup
			(layer "F.SilkS"
				(type "Top Silk Screen")
				(color "White")
			)
			(layer "F.Paste"
				(type "Top Solder Paste")
			)
			(layer "F.Mask"
				(type "Top Solder Mask")
				(color "Green")
				(thickness 0.01)
			)
			(layer "F.Cu"
				(type "copper")
				(thickness 0.035)
			)
			(layer "dielectric 1"
				(type "prepreg")
				(thickness 0.2104)
				(material "7628")
				(epsilon_r 4.4)
				(loss_tangent 0.02)
			)
			(layer "In1.Cu"
				(type "copper")
				(thickness 0.0152)
			)
			(layer "dielectric 2"
				(type "core")
				(thickness 1.065)
				(material "FR4")
				(epsilon_r 4.6)
				(loss_tangent 0.02)
			)
			(layer "In2.Cu"
				(type "copper")
				(thickness 0.0152)
			)
			(layer "dielectric 3"
				(type "prepreg")
				(thickness 0.2104)
				(material "7628")
				(epsilon_r 4.4)
				(loss_tangent 0.02)
			)
			(layer "B.Cu"
				(type "copper")
				(thickness 0.035)
			)
			(layer "B.Mask"
				(type "Bottom Solder Mask")
				(color "Green")
				(thickness 0.01)
			)
			(layer "B.Paste"
				(type "Bottom Solder Paste")
			)
			(layer "B.SilkS"
				(type "Bottom Silk Screen")
				(color "White")
			)
			(copper_finish "HAL lead-free")
			(dielectric_constraints no)
		)
"""
STACKUP_THICKNESS = 1.6062


def write_stackup(path):
    """pcbnew's Python has no stack-up API: put the JLC04161H-7628 stack-up into a saved board."""
    t = open(path).read()
    t = re.sub(r"\t\t\(stackup\n.*?\n\t\t\)\n", "", t, flags=re.S)
    if t.count("\t(setup\n") != 1:
        raise SystemExit("write_stackup: no (setup) block in " + path)
    t = t.replace("\t(setup\n", "\t(setup\n" + STACKUP, 1)
    t = re.sub(r"\(general\n\t\t\(thickness [0-9.]+\)", "(general\n\t\t(thickness %s)" % STACKUP_THICKNESS, t, count=1)
    open(path, "w").write(t)


def netclass(name, track, clearance, priority):
    return {"name": name, "track_width": track, "clearance": clearance, "via_diameter": 0.6, "via_drill": 0.3,
            "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.25,
            "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0,
            "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
            "priority": priority, "tuning_profile": ""}


# Custom rules: first the JLCPCB limits that KiCad's board setup has no field for. Then: the 0.5 mm pitch parts have 0.15-0.2 mm gaps between their own pads, below the
# Default (0.2) / Power (0.25) clearances. Inside their courtyards the clearance drops to 0.15 mm
# (JLCPCB minimum 0.127 mm), so the footprints themselves and the fan-out pass DRC. The USB-C GND
# pads sit between the VBUS pad and the shell legs, where a thermal relief keeps one spoke only:
# they join the pours solid (they are also tied to the shell legs by tracks). Through-hole GND pins
# (box headers) are connected on both layers; where tracks pass close by, one 0.5 mm spoke per
# layer is accepted instead of two (hand soldering keeps its thermal reliefs).
DRU = """(version 1)

(rule "JLCPCB: PTH hole to track 0.28 mm"
  (constraint hole_clearance (min 0.28mm))
  (condition "A.Type == 'Pad' && A.isPlated() && A.Pad_Type == 'Through-hole'"))

(rule "JLCPCB: inner-layer PTH hole to copper 0.3 mm"
  (layer inner)
  (constraint hole_clearance (min 0.3mm))
  (condition "A.Type == 'Pad' && A.isPlated() && A.Pad_Type == 'Through-hole'"))

(rule "JLCPCB: pad hole to pad hole 0.45 mm (different nets)"
  (constraint hole_to_hole (min 0.45mm))
  (condition "A.Type == 'Pad' && B.Type == 'Pad' && A.NetName != B.NetName"))

(rule "LIS3DH LGA-16 0.5 mm pitch"
  (constraint clearance (min 0.15mm))
  (condition "A.intersectsCourtyard('U8') && B.intersectsCourtyard('U8')"))

(rule "USB-C 16P 0.5 mm pitch"
  (constraint clearance (min 0.15mm))
  (condition "A.intersectsCourtyard('J7') && B.intersectsCourtyard('J7')"))

(rule "USB-C GND pads solid to the pour"
  (constraint zone_connection solid)
  (condition "A.Type == 'Pad' && A.memberOfFootprint('J7')"))

(rule "Through-hole GND pins: one thermal spoke is enough"
  (constraint min_resolved_spokes 1)
  (condition "A.Type == 'Pad' && A.Pad_Type == 'Through-hole' && A.NetName == 'GND'"))
"""


def write_project():
    with open(os.path.join(KDIR, PROJECT + ".kicad_dru"), "w") as f:
        f.write(DRU)
    tw_d, cl_d = D.NETCLASS["Default"]
    tw_p, cl_p = D.NETCLASS["Power"]
    pro = {
        "meta": {"filename": PROJECT + ".kicad_pro", "version": 3},
        "board": {
            "design_settings": {
                "meta": {"version": 2},
                "rules": dict(RULES, allow_blind_buried_vias=False, allow_microvias=False,
                              min_hole_clearance=HOLE_CLEARANCE, min_resolved_spokes=2, min_silk_clearance=SILK_RULES[0],
                              min_text_height=SILK_RULES[1], min_text_thickness=SILK_RULES[2], max_error=0.005),
                # silkscreen problems are errors (rev 2.1): text over pads / mask openings, text over
                # text or footprint silk, silk clipped by the board edge
                "rule_severities": {"silk_over_copper": "error", "silk_overlap": "error", "silk_edge_clearance": "error"},
                "track_widths": [0.0, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0],
                "via_dimensions": [{"diameter": 0.0, "drill": 0.0}] + [{"diameter": d, "drill": h} for d, h in VIAS],
                "diff_pair_dimensions": [],
            },
        },
        "net_settings": {
            "meta": {"version": 5},
            "classes": [netclass("Default", tw_d, cl_d, 2147483647), netclass("Power", tw_p, cl_p, 0)],
            "net_colors": None,
            "netclass_assignments": None,
            "netclass_patterns": [{"netclass": "Power", "pattern": n} for n in D.POWER_NETS],
        },
        "schematic": {},
        "sheets": [[uid("root"), "Root"]] + [[uid("sheet", k), v[0]] for k, v in D.SHEETS.items()],
        "text_variables": {},
    }
    with open(os.path.join(KDIR, PROJECT + ".kicad_pro"), "w") as f:
        json.dump(pro, f, indent=2)
        f.write("\n")


def build():
    board = pcbnew.CreateEmptyBoard()
    board.SetCopperLayerCount(4)
    for layer, name in LAYER_NAMES.items():
        board.SetLayerName(layer, name)
        board.SetLayerType(layer, pcbnew.LT_POWER)       # planes: Freerouting does not route on them
    tb = board.GetTitleBlock()
    tb.SetTitle("Defuse32 carrier")
    tb.SetRevision(BOARD_REV)
    tb.SetDate(D.DATE)
    tb.SetCompany("ESP32 CTF / Defuse32")
    tb.SetComment(0, "100 x 70 mm, 4 layers JLC04161H-7628 1.6 mm (sig+GND / GND / GND / sig+GND), SMD + THT headers")
    tb.SetComment(1, "rev 3: schematic rev 2, placed (design.py), routed with Freerouting + route_prep.py, polish.py")
    tb.SetComment(2, "Generated by kicad/gen/gen_pcb.py")
    ds = board.GetDesignSettings()
    ds.SetBoardThickness(mm(1.6))
    ds.m_CopperEdgeClearance = mm(RULES["min_copper_edge_clearance"])
    ds.m_MinClearance = mm(RULES["min_clearance"])
    ds.m_TrackMinWidth = mm(RULES["min_track_width"])
    ds.m_MinThroughDrill = mm(RULES["min_through_hole_diameter"])
    ds.m_HoleToHoleMin = mm(RULES["min_hole_to_hole"])
    ds.m_ViasMinAnnularWidth = mm(RULES["min_via_annular_width"])
    ds.m_ViasMinSize = mm(RULES["min_via_diameter"])
    ds.m_HoleClearance = mm(HOLE_CLEARANCE)
    # drill/place origin = board bottom-left corner: Gerbers, drill and the JLCPCB CPL use it
    ds.SetAuxOrigin(P(0, D.BOARD_H))

    # outline
    e = pcbnew.PCB_SHAPE(board)
    e.SetShape(pcbnew.SHAPE_T_RECT)
    e.SetStart(P(0, 0))
    e.SetEnd(P(D.BOARD_W, D.BOARD_H))
    e.SetLayer(pcbnew.Edge_Cuts)
    e.SetWidth(mm(0.1))
    board.Add(e)

    # nets: taken from the schematic netlist so names (incl. unconnected-*) match exactly
    padnet, fields = read_netlist()
    for p in D.PARTS:
        for pin, net in D.pad_nets(p).items():
            got = padnet.get((p["ref"], pin))
            if net and got != net:
                raise SystemExit("schematic netlist disagrees with design.py: %s.%s %s/%s" % (p["ref"], pin, net, got))
    nets = {}
    for n in sorted(set(padnet.values())):
        ni = pcbnew.NETINFO_ITEM(board, n)
        board.Add(ni)
        nets[n] = ni

    for p in D.PARTS:
        fp = load_fp(p["fp"])
        x, y, rot = p["pcb"]
        fp.SetReference(p["ref"])
        fp.SetValue(p["value"])
        fp.SetPosition(P(x, y))
        fp.SetOrientationDegrees(rot)
        fp.SetPath(pcbnew.KIID_PATH("%s/%s" % (sheet_path(p["sheet"]), uid("sym", p["ref"], 1))))
        f = fields[p["ref"]]
        fp.SetSheetname(f.get("Sheetname", ""))
        fp.SetSheetfile(f.get("Sheetfile", ""))
        for k in ("Datasheet", "Description", "LCSC", "MPN", "Manufacturer", "JLC"):
            if k in f:
                fp.SetField(k, f[k])
                if k not in ("Datasheet", "Description"):
                    fp.GetField(k).SetVisible(False)
                    fp.GetField(k).SetLayer(pcbnew.F_Fab)
        for pad in fp.Pads():
            net = padnet.get((p["ref"], pad.GetNumber()))
            if net:
                pad.SetNet(nets[net])
        board.Add(fp)

    import fetch_3d
    got = fetch_3d.apply(board)
    if got:
        print("3D models from gen/models3d.json:", " ".join(got))
    place_refs(board)
    silk_text(board, "U1 antenna region and keep-out beyond the board edge x = 0 (Espressif placement)",
              50, -3, 1.0, layer=pcbnew.F_Fab)

    out = os.path.join(KDIR, PROJECT + ".kicad_pcb")
    pcbnew.SaveBoard(out, board)
    write_stackup(out)
    write_project()      # after SaveBoard, which rewrites the .kicad_pro with defaults
    print("wrote", out, "footprints:", len(board.GetFootprints()), "nets:", len(nets))


# ---------------------------------------------------------------- silkscreen reference designators
REF_SIZE, REF_THICK = 1.0, 0.15      # mm (JLCPCB: 1.0 mm text height, 0.15 mm line);
                                     # the routed board's final references come from polish.py
SILK_GAP = 0.15                      # text box to pads, silk lines, other references
EDGE_GAP = 0.3


def _box(b, grow=0.0):
    return (pcbnew.ToMM(b.GetLeft()) - grow, pcbnew.ToMM(b.GetTop()) - grow,
            pcbnew.ToMM(b.GetRight()) + grow, pcbnew.ToMM(b.GetBottom()) + grow)


def _hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def place_refs(board):
    """Put every reference designator on F.Silkscreen next to its part, clear of pads, silk lines,
    other references and the board edge (DRC silk checks); mounting holes get none. A reference
    that fits nowhere is hidden (printed)."""
    fps = list(board.GetFootprints())
    pads, silk, crt = [], [], {}
    for fp in fps:
        ref = fp.GetReference()
        for pd in fp.Pads():
            pads.append((ref, _box(pd.GetBoundingBox(), SILK_GAP)))
        for g in fp.GraphicalItems():
            if g.GetLayer() == pcbnew.F_SilkS and g.GetClass() != "PCB_TEXT":
                silk.append((ref, _box(g.GetBoundingBox(), SILK_GAP)))
        c = fp.GetCourtyard(pcbnew.F_CrtYd)
        crt[ref] = _box(c.BBox()) if c.OutlineCount() else _box(fp.GetBoundingBox(False))
    x0, y0 = OX + EDGE_GAP, OY + EDGE_GAP
    x1, y1 = OX + D.BOARD_W - EDGE_GAP, OY + D.BOARD_H - EDGE_GAP
    placed, hidden = [], []
    # big parts first: they have the fewest good spots
    order = sorted(fps, key=lambda f: -(crt[f.GetReference()][2] - crt[f.GetReference()][0]) *
                   (crt[f.GetReference()][3] - crt[f.GetReference()][1]))
    for fp in order:
        ref = fp.GetReference()
        t = fp.Reference()
        if ref.startswith("H"):
            t.SetVisible(False)
            continue
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(mm(REF_SIZE), mm(REF_SIZE)))
        t.SetTextThickness(mm(REF_THICK))
        t.SetKeepUpright(True)
        cx0, cy0, cx1, cy1 = crt[ref]
        mx, my = (cx0 + cx1) / 2, (cy0 + cy1) / 2
        cands = []
        for gap in (0.5, 1.0, 1.6):
            for d in (0.0, 0.5, -0.5, 1.0, -1.0, 1.5, -1.5, 2.0, -2.0, 3.0, -3.0):
                cands += [(mx + d, cy0 - gap, 0), (mx + d, cy1 + gap, 0), (cx0 - gap, my + d, 90), (cx1 + gap, my + d, 90),
                          (cx0 - gap - 1.2, my + d, 0), (cx1 + gap + 1.2, my + d, 0)]
        cands += [(mx, my, 0), (mx, my, 90)]
        best = None
        for strict in (True, False):
            for x, y, ang in cands:
                t.SetTextAngleDegrees(ang)
                t.SetPosition(pcbnew.VECTOR2I(mm(x), mm(y)))
                b = _box(t.GetBoundingBox())
                if b[0] < x0 or b[1] < y0 or b[2] > x1 or b[3] > y1:
                    continue
                if any(_hit(b, o) for _, o in pads) or any(_hit(b, o) for r, o in silk) or any(_hit(b, o) for o in placed):
                    continue
                if strict and any(_hit(b, c) for r, c in crt.items() if r != ref and not r.startswith("H")):
                    continue
                best = (x, y, ang, b)
                break
            if best:
                break
        if best:
            t.SetTextAngleDegrees(best[2])
            t.SetPosition(pcbnew.VECTOR2I(mm(best[0]), mm(best[1])))
            placed.append(_box(t.GetBoundingBox(), SILK_GAP))
        else:
            t.SetVisible(False)
            hidden.append(ref)
    if hidden:
        print("references hidden (no free silkscreen spot):", " ".join(sorted(hidden)))


def refuse_routed_board():
    """Stop unless the existing board is unrouted (no segment/arc/via/copper zone) or --force was given."""
    path = os.path.join(KDIR, PROJECT + ".kicad_pcb")
    if "--force" in sys.argv[1:] or not os.path.exists(path):
        return
    text = open(path).read()
    n = len(re.findall(r"^\s*\((?:segment|arc|via)\b", text, re.M))
    z = len(re.findall(r"^\t\(zone\b", text, re.M))       # board-level zones (GND pours), not footprint keep-outs
    if n or z:
        raise SystemExit(
            "gen_pcb.py: %s is routed (%d tracks/vias, %d zones); refusing to overwrite it and %s.kicad_pro.\n"
            "Change the schematic and use KiCad's Tools > Update PCB from Schematic.\n"
            "Run with --force to regenerate the placed, unrouted board anyway (routing and hand edits are lost;\n"
            "re-route with gen/route_prep.py)." % (os.path.relpath(path), n, z, PROJECT))


if __name__ == "__main__":
    refuse_routed_board()
    build()
