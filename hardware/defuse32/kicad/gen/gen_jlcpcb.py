#!/usr/bin/env python3
"""JLCPCB fabrication and assembly files for the rev 2 carrier, into out/jlcpcb/.

  gerber/                         Gerbers (copper, mask, paste, silkscreen, outline), Excellon drill
  defuse32-carrier-jlcpcb.zip     the files in gerber/, zipped flat (upload this)
  defuse32-carrier-bom.csv        JLCPCB BOM: Comment, Designator, Footprint, LCSC Part # (SMD parts)
  defuse32-carrier-cpl.csv        JLCPCB CPL: Designator, Mid X, Mid Y, Layer, Rotation (top-side SMD)

Coordinates: the board's drill/place (aux) origin is its bottom-left corner; the Gerbers, the drill
file and the CPL all use it (x right, y up, mm), so the CPL lines up with the Gerbers. Rotations are
KiCad's (counter-clockwise, degrees); JLCPCB's zero orientation differs per package, so its
placement preview must be checked part by part (see out/jlcpcb/README.md).

Run from hardware/defuse32/kicad/ with KiCad's Python, after `route_prep.py finish` and a clean DRC:
  /usr/bin/python3 gen/gen_jlcpcb.py
"""
import csv
import os
import subprocess
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
LAYERS = "F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts"


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


def assembly():
    board = pcbnew.LoadBoard(BOARD)
    ox = board.GetDesignSettings().GetAuxOrigin()
    want = pcbnew.VECTOR2I(int(round(OX * 1e6)), int(round((OY + D.BOARD_H) * 1e6)))
    if (ox.x, ox.y) != (want.x, want.y):
        raise SystemExit("aux origin is not the board's bottom-left corner (run route_prep.py finish)")
    parts = {p["ref"]: p for p in D.PARTS}
    rows, groups, tht = [], {}, []
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
        pos = fp.GetPosition()
        x = pcbnew.ToMM(pos.x - ox.x)
        y = pcbnew.ToMM(ox.y - pos.y)
        rot = fp.GetOrientationDegrees() % 360
        rows.append([ref, "%.3f" % x, "%.3f" % y, "Top", "%g" % rot])
        lcsc = p["lcsc"][0]
        key = (fp.GetFPID().GetLibItemName().wx_str(), lcsc)
        groups.setdefault(key, []).append((ref, fp.GetValue(), p["lcsc"][1]))
    with open(os.path.join(OUT, NAME + "-cpl.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        w.writerows(rows)
    with open(os.path.join(OUT, NAME + "-bom.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
        # one line per LCSC part; parts that share it under different values (SW1 EN / SW2 BOOT,
        # U2 / U3 with their I2C addresses) are listed under the MPN
        for (fpn, lcsc), items in sorted(groups.items(), key=lambda kv: kv[1][0][0]):
            vals = {v for _, v, _ in items}
            comment = vals.pop() if len(vals) == 1 else items[0][2]
            w.writerow([comment, ",".join(r for r, _, _ in items), fpn, lcsc])
    return len(rows), len(groups), tht


if __name__ == "__main__":
    files = gerbers()
    n, g, tht = assembly()
    print("gerber/: %s" % " ".join(files))
    print("BOM: %d lines (%d SMD parts), CPL: %d top-side SMD parts; THT (not in BOM/CPL): %s" % (g, n, n, " ".join(tht)))
