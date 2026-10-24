#!/usr/bin/env python3
"""JLCPCB fabrication and assembly files for the rev 3 carrier (4 layers), into out/jlcpcb/.

  gerber/                         Gerbers (F.Cu, In1.Cu, In2.Cu, B.Cu, mask, paste, silkscreen,
                                  outline), Excellon drill (plated / non-plated)
  defuse32-carrier-jlcpcb.zip     the files in gerber/, zipped flat (upload this)
  defuse32-carrier-bom.csv        JLCPCB BOM: Comment, Designator, Footprint, LCSC, Quantity (SMD parts)
  defuse32-carrier-cpl.csv        JLCPCB CPL: Designator, Val, Package, Mid X, Mid Y, Rotation, Layer

The BOM / CPL follow the conventions of the KiCad "JLCPCB Tools" plugin (Bouni/kicad-jlcpcb-tools,
version 2026.04.03, the one JLCPCB documents): CPL position = centre of the footprint's pad bounding
box, relative to the drill/place (aux) origin = the board's bottom-left corner (x right, y up, mm,
the same origin as the Gerbers and the drill file); rotation = KiCad's orientation plus the
plugin's correction for the package (JLC_ROTATIONS: the plugin's table rows that match this board,
first match on reference, then value, then footprint name, an exact match before a prefix match).
Parts without a rule (resistors, capacitors, SOD-323, LGA-16, 1812, TS-1187A, microSD) go with
KiCad's rotation: check them in JLCPCB's placement preview (out/jlcpcb/README.md).

Run from hardware/defuse32/kicad/ with KiCad's Python, after polish.py and a clean DRC:
  /usr/bin/python3 gen/gen_jlcpcb.py [--corrections cpl_rotations_db.csv]
--corrections uses a full copy of the plugin's table instead of JLC_ROTATIONS.
"""
import csv
import os
import re
import subprocess
import sys
import zipfile

import pcbnew

import design as D
from gen_pcb import OX, OY

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(HERE, ".."))
BOARD = os.path.join(KDIR, "defuse32-carrier.kicad_pcb")
OUT = os.path.join(KDIR, "out", "jlcpcb")
GERB = os.path.join(OUT, "gerber")
NAME = "defuse32-carrier"
LAYERS = "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"
# Rotation corrections from the JLCPCB Tools plugin's table (it downloads matthewlai/JLCKicadTools
# jlc_kicad_tools/cpl_rotations_db.csv; rows below as of commit 50ab537, 2026-10-23): only the rows
# that match a footprint of this board. (regex, degrees, offset x, offset y).
JLC_ROTATIONS = [
    ("^ESP32-W", 270, 0.0, 0.0),
    ("^SOIC-", 270, 0.0, 0.0),
    ("^SOT-223", 180, 0.0, 0.0),
    ("^SOT-23", -90, 0.0, 0.0),
    ("^USB_C_Receptacle_HRO_TYPE-C-31-M-12*", 180, 0.0, 0.0),
]


def run(*args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL)


def gerbers():
    os.makedirs(GERB, exist_ok=True)
    for f in os.listdir(GERB):
        os.remove(os.path.join(GERB, f))
    run("kicad-cli", "pcb", "export", "gerbers", "-o", GERB + "/", "--subtract-soldermask", "--check-zones",
        "--use-drill-file-origin", "--layers", LAYERS, BOARD)
    run("kicad-cli", "pcb", "export", "drill", "-o", GERB + "/", "--format", "excellon", "--drill-origin", "plot",
        "--excellon-units", "mm", "--excellon-zeros-format", "decimal", "--excellon-separate-th", BOARD)
    z = os.path.join(OUT, NAME + "-jlcpcb.zip")
    if os.path.exists(z):
        os.remove(z)
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(GERB)):
            zf.write(os.path.join(GERB, f), f)
    return sorted(os.listdir(GERB))


def is_smd(fp):
    return bool(fp.GetAttributes() & pcbnew.FP_SMD) and not fp.IsDNP()


def corrections():
    if "--corrections" in sys.argv:
        rows = list(csv.reader(open(sys.argv[sys.argv.index("--corrections") + 1])))[1:]
        table = [(r[0], int(r[1]), float(r[2]) if len(r) > 2 else 0.0, float(r[3]) if len(r) > 3 else 0.0)
                 for r in rows if len(r) >= 2]
    else:
        table = JLC_ROTATIONS
    return sorted(table)                     # the plugin reads its database ORDER BY regex


def find_correction(table, value):
    """The plugin's _find_correction: an anchored match (pattern + '$') first, then a prefix match."""
    for rgx, rot, ox, oy in table:
        if re.search("(?:%s)$" % rgx, value):
            return rot, ox, oy
    for rgx, rot, ox, oy in table:
        if re.search(rgx, value):
            return rot, ox, oy
    return None


def jlc_placement(fp, table, origin):
    """(x mm, y mm, rotation deg, rule) as the JLCPCB Tools plugin writes them for a top-side part."""
    bb = None
    for pad in fp.Pads():
        b = pad.GetBoundingBox()
        if bb is None:
            bb = b
        else:
            bb.Merge(b)
    c = bb.GetCenter() if bb is not None else fp.GetPosition()
    x, y = c.x - origin.x, c.y - origin.y
    rot = fp.GetOrientationDegrees() % 360
    for v in (fp.GetReference(), fp.GetValue(), str(fp.GetFPID().GetLibItemName())):
        m = find_correction(table, v)
        if m:
            r, ox, oy = m
            if ox or oy:
                import math
                a = math.radians(rot)
                x += pcbnew.FromMM(ox) * math.cos(a) + pcbnew.FromMM(oy) * math.sin(a)
                y += -pcbnew.FromMM(ox) * math.sin(a) + pcbnew.FromMM(oy) * math.cos(a)
            return pcbnew.ToMM(x), -pcbnew.ToMM(y), (rot + r) % 360, "%+d" % r
    return pcbnew.ToMM(x), -pcbnew.ToMM(y), rot, ""


def assembly():
    board = pcbnew.LoadBoard(BOARD)
    ox = board.GetDesignSettings().GetAuxOrigin()
    want = pcbnew.VECTOR2I(int(round(OX * 1e6)), int(round((OY + D.BOARD_H) * 1e6)))
    if (ox.x, ox.y) != (want.x, want.y):
        raise SystemExit("aux origin is not the board's bottom-left corner (run route_prep.py finish)")
    parts = {p["ref"]: p for p in D.PARTS}
    table = corrections()
    rows, groups, tht, fixed = [], {}, [], {}
    def refkey(f):
        r = f.GetReference()
        i = len(r.rstrip("0123456789"))
        return (r[:i], int(r[i:]))
    for fp in sorted(board.GetFootprints(), key=refkey):
        ref = fp.GetReference()
        p = parts[ref]
        if ref.startswith("H"):
            continue
        if not is_smd(fp):
            tht.append(ref)
            continue
        if fp.IsFlipped():
            raise SystemExit("%s is on the bottom side (single-sided assembly)" % ref)
        x, y, rot, rule = jlc_placement(fp, table, ox)
        fpn = fp.GetFPID().GetLibItemName().wx_str()
        rows.append([ref, fp.GetValue(), fpn, "%.4f" % x, "%.4f" % y, "%g" % rot, "top"])
        if rule:
            fixed.setdefault("%s %s" % (fpn, rule), []).append(ref)
        lcsc = p["lcsc"][0]
        key = (fpn, lcsc)
        groups.setdefault(key, []).append((ref, fp.GetValue(), p["lcsc"][1]))
    with open(os.path.join(OUT, NAME + "-cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Val", "Package", "Mid X", "Mid Y", "Rotation", "Layer"])
        w.writerows(rows)
    with open(os.path.join(OUT, NAME + "-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC", "Quantity"])
        # one line per LCSC part; parts that share it under different values (SW1 EN / SW2 BOOT,
        # U2 / U3 with their I2C addresses) are listed under the MPN
        for (fpn, lcsc), items in sorted(groups.items(), key=lambda kv: kv[1][0][0]):
            vals = {v for _, v, _ in items}
            comment = vals.pop() if len(vals) == 1 else items[0][2]
            w.writerow([comment, ",".join(r for r, _, _ in items), fpn, lcsc, len(items)])
    return len(rows), len(groups), tht, fixed


if __name__ == "__main__":
    files = gerbers()
    n, g, tht, fixed = assembly()
    print("gerber/: %s" % " ".join(files))
    print("BOM: %d lines (%d SMD parts), CPL: %d top-side SMD parts; THT (not in BOM/CPL): %s" % (g, n, n, " ".join(tht)))
    print("CPL rotation corrections (JLCPCB Tools table): %s" % "; ".join("%s: %s" % (k, " ".join(v)) for k, v in sorted(fixed.items())))
