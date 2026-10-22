#!/usr/bin/env python3
"""Generate the rev 2 defuse32-carrier.kicad_pcb (outline, holes, every footprint with its nets,
roughly placed, unrouted) and the project file (net classes, JLCPCB 2-layer design rules).

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
    return pcbnew.VECTOR2I(mm(OX + x), mm(OY + y))


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
# JLCPCB 2-layer standard capabilities (mm): track/space 0.127, drill 0.3, annular ring 0.13,
# hole-to-hole 0.5, copper to board edge 0.3.
RULES = {
    "min_clearance": 0.127,
    "min_track_width": 0.127,
    "min_through_hole_diameter": 0.3,
    "min_via_annular_width": 0.13,
    "min_via_diameter": 0.56,
    "min_hole_to_hole": 0.5,
    "min_copper_edge_clearance": 0.3,
}


def netclass(name, track, clearance, priority):
    return {"name": name, "track_width": track, "clearance": clearance, "via_diameter": 0.6, "via_drill": 0.3,
            "microvia_diameter": 0.3, "microvia_drill": 0.1, "diff_pair_width": 0.2, "diff_pair_gap": 0.25,
            "diff_pair_via_gap": 0.25, "wire_width": 6, "bus_width": 12, "line_style": 0,
            "pcb_color": "rgba(0, 0, 0, 0.000)", "schematic_color": "rgba(0, 0, 0, 0.000)",
            "priority": priority, "tuning_profile": ""}


# Custom rules: the 0.5 mm pitch parts have 0.15-0.2 mm gaps between their own pads, below the
# Default (0.2) / Power (0.25) clearances. Inside their courtyards the clearance drops to 0.15 mm
# (JLCPCB minimum 0.127 mm), so the footprints themselves and the fan-out pass DRC.
DRU = """(version 1)

(rule "LIS3DH LGA-16 0.5 mm pitch"
  (constraint clearance (min 0.15mm))
  (condition "A.intersectsCourtyard('U8') && B.intersectsCourtyard('U8')"))

(rule "USB-C 16P 0.5 mm pitch"
  (constraint clearance (min 0.15mm))
  (condition "A.intersectsCourtyard('J7') && B.intersectsCourtyard('J7')"))
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
                              min_hole_clearance=0.25, min_resolved_spokes=2, min_silk_clearance=0.0,
                              min_text_height=0.8, min_text_thickness=0.12, max_error=0.005),
                "track_widths": [0.0, 0.2, 0.3, 0.4, 0.6, 0.8, 1.0],
                "via_dimensions": [{"diameter": 0.0, "drill": 0.0}, {"diameter": 0.6, "drill": 0.3}],
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
    tb = board.GetTitleBlock()
    tb.SetTitle(D.TITLE)
    tb.SetRevision(D.REV)
    tb.SetDate(D.DATE)
    tb.SetCompany("ESP32 CTF / Defuse32")
    tb.SetComment(0, "100 x 70 mm, 2 layers, 1.6 mm, SMD (JLCPCB assembly) + THT headers")
    tb.SetComment(1, "rev 2: footprints imported, rough placement, unrouted; net classes + JLCPCB rules in .kicad_pro")
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

    silk_text(board, "DEFUSE32 CARRIER  rev 2  2026-10-23", 50, 68.2, 1.2, bold=True, layer=pcbnew.B_SilkS).SetMirrored(True)
    silk_text(board, "rough placement: the placement task moves every part; U1 antenna region beyond x = 0",
              50, -3, 1.0, layer=pcbnew.F_Fab)

    out = os.path.join(KDIR, PROJECT + ".kicad_pcb")
    pcbnew.SaveBoard(out, board)
    write_project()      # after SaveBoard, which rewrites the .kicad_pro with defaults
    print("wrote", out, "footprints:", len(board.GetFootprints()), "nets:", len(nets))


def refuse_routed_board():
    """Stop unless the existing board is unrouted (no segment/arc/via) or --force was given."""
    path = os.path.join(KDIR, PROJECT + ".kicad_pcb")
    if "--force" in sys.argv[1:] or not os.path.exists(path):
        return
    n = len(re.findall(r"^\s*\((?:segment|arc|via)\b", open(path).read(), re.M))
    if n:
        raise SystemExit(
            "gen_pcb.py: %s is routed (%d tracks/vias); refusing to overwrite it and %s.kicad_pro.\n"
            "Change the schematic and use KiCad's Tools > Update PCB from Schematic.\n"
            "Run with --force to regenerate an unrouted board anyway (the routing is lost)."
            % (os.path.relpath(path), n, PROJECT))


if __name__ == "__main__":
    refuse_routed_board()
    build()
