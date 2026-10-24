#!/usr/bin/env python3
"""Fetch the JLCPCB/LCSC 3D models for the parts whose KiCad footprint has no model file, and
work out where each model sits on our footprint.

KiCad's library has no model for the HRO TYPE-C-31-M-12 (J7), the XKB TS-1187A buttons (SW1/SW2)
or the 1812 PTC fuse (F1). easyeda2kicad downloads EasyEDA's footprint + 3D model for an LCSC
number. The EasyEDA model licence is unclear for this MIT repository, so the model files are not
committed: kicad/3d/ is git-ignored and this script rebuilds it.

    /usr/bin/python3 kicad/gen/fetch_3d.py fetch            # download, match, write gen/models3d.json
    /usr/bin/python3 kicad/gen/fetch_3d.py apply [board]    # set the models on an existing board
    /usr/bin/python3 kicad/gen/fetch_3d.py check            # list footprints without a model file

easyeda2kicad lives in its own venv (E2K env var, default ~/tools/easyeda2kicad-1.0.1/bin/
easyeda2kicad; pip install easyeda2kicad==1.0.1). Which parts need a model is found automatically:
every part in design.py whose footprint's model file does not exist and that has an LCSC number.

Placement: EasyEDA's footprint and ours are the same land pattern drawn in different frames. The
script matches the two pad sets (rotation 0/90/180/270 + translation, pads and holes, residual
check) and carries EasyEDA's model offset/rotation over into our footprint frame. The result is
stored in gen/models3d.json (numbers only, committed) and applied by gen_pcb.py and `apply`.
KiCad's model offset is in 3D axes (y up), PCB coordinates have y down, and a model's z rotation
turns clockwise seen from the top: the conversion and easyeda2kicad's own placement bugs are
handled in fetch() (comments there).
"""
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

import pcbnew

import design as D

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(HERE, ".."))
MODEL_DIR = os.path.join(KDIR, "3d")
JSON = os.path.join(HERE, "models3d.json")
SYS_FP = "/usr/share/kicad/footprints"
SYS_3D = "/usr/share/kicad/3dmodels"
E2K = os.environ.get("E2K", os.path.expanduser("~/tools/easyeda2kicad-1.0.1/bin/easyeda2kicad"))
TOL = 0.2                       # mm: a pad matches when its centre is this close after the transform


def load_fp(fpid):
    lib, name = fpid.split(":")
    path = os.path.join(KDIR, "defuse32.pretty") if lib == "defuse32" else os.path.join(SYS_FP, lib + ".pretty")
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit("footprint not found: " + fpid)
    return fp


def resolve(path):
    for var, val in (("${KICAD10_3DMODEL_DIR}", SYS_3D), ("${KICAD9_3DMODEL_DIR}", SYS_3D),
                     ("${KICAD8_3DMODEL_DIR}", SYS_3D), ("${KIPRJMOD}", KDIR)):
        path = path.replace(var, val)
    return path


def has_model(fp):
    return any(os.path.exists(resolve(m.m_Filename)) for m in fp.Models())


def needed():
    """{fpid: (lcsc, [refs])} for every footprint without an existing model file."""
    out = {}
    for p in D.PARTS:
        if not p.get("lcsc"):
            continue
        fpid = p["fp"]
        if fpid in out:
            out[fpid][1].append(p["ref"])
            continue
        if not has_model(load_fp(fpid)):
            out[fpid] = (p["lcsc"][0], [p["ref"]])
    return out


def pads(fp):
    """[(x, y, w, h, drill)] in mm, footprint frame (PCB axes, y down), orientation 0."""
    res = []
    for pad in fp.Pads():
        pos = pad.GetFPRelativePosition()
        sz = pad.GetSize(pcbnew.F_Cu) if hasattr(pad, "GetSize") else pad.GetSize()
        try:
            dr = pad.GetDrillSize().x
        except Exception:
            dr = 0
        ang = pad.GetFPRelativeOrientation().AsDegrees() % 180
        w, h = sz.x / 1e6, sz.y / 1e6
        if abs(ang - 90) < 1:
            w, h = h, w
        res.append((pos.x / 1e6, pos.y / 1e6, w, h, dr / 1e6))
    return res


def rot(x, y, deg):
    """Rotate a PCB-axes point by a KiCad orientation (counter-clockwise on screen, y down)."""
    a = math.radians(deg)
    return x * math.cos(a) + y * math.sin(a), -x * math.sin(a) + y * math.cos(a)


def match(src, dst):
    """Best (theta, tx, ty, matched, maxerr) mapping src pads onto dst pads: for each rotation,
    start from every pad-on-pad alignment and from the centroid alignment, refine the translation
    by weighted least squares on the pads that are near (< 1 mm), keep the lowest residual.
    Drilled features (locating pegs, shell legs) weigh 5x: they sit on the part body, while SMD
    land patterns differ between libraries (pad length, toe/heel)."""
    def residuals(rs, tx, ty):
        out = []
        for (x, y, w, h, wt) in rs:
            q = min(dst, key=lambda e: math.hypot(e[0] - x - tx, e[1] - y - ty))
            out.append((q[0] - x - tx, q[1] - y - ty, abs(q[2] - w) + abs(q[3] - h), wt))
        return out

    best = None
    cdx, cdy = sum(d[0] for d in dst) / len(dst), sum(d[1] for d in dst) / len(dst)
    for theta in (0, 90, 180, 270):
        rs = [rot(p[0], p[1], theta) + ((p[3], p[2]) if theta in (90, 270) else (p[2], p[3]))
              + (5.0 if p[4] > 0 else 1.0,) for p in src]
        csx, csy = sum(r[0] for r in rs) / len(rs), sum(r[1] for r in rs) / len(rs)
        starts = [(cdx - csx, cdy - csy)] + [(d[0] - r[0], d[1] - r[1]) for r in rs for d in dst]
        for tx, ty in starts:
            for _ in range(3):
                res = [r for r in residuals(rs, tx, ty) if math.hypot(r[0], r[1]) < 1.0]
                if not res:
                    break
                wsum = sum(r[3] for r in res)
                tx += sum(r[0] * r[3] for r in res) / wsum
                ty += sum(r[1] * r[3] for r in res) / wsum
            res = residuals(rs, tx, ty)
            cost = sum(r[3] * min(math.hypot(r[0], r[1]), 1.0) ** 2 for r in res) + 0.01 * sum(r[2] for r in res)
            key = (round(cost, 6), min(theta, 360 - theta))
            if best is None or key < best[0]:
                best = (key, theta, tx, ty, res)
    _, theta, tx, ty, res = best
    errs = [math.hypot(r[0], r[1]) for r in res]
    return theta, tx, ty, sum(e <= TOL for e in errs), max(errs)


def rz(x, y, deg):
    """Rotate a point in 3D axes (x right, y up) counter-clockwise seen from the top."""
    a = math.radians(deg)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


def wrl_box(path):
    """(xmin, xmax, ymin, ymax, zmin, zmax) in mm of an easyeda2kicad VRML (units of 2.54 mm)."""
    xs, ys, zs = [], [], []
    for m in re.finditer(r"point\s*\[([^\]]*)\]", open(path).read()):
        v = [float(t) for t in m.group(1).replace(",", " ").split()]
        xs += v[0::3]
        ys += v[1::3]
        zs += v[2::3]
    return tuple(round(f(a) * 2.54, 4) for a in (xs, ys, zs) for f in (min, max))


def step_box(path):
    """Bounding box of a STEP model's B-rep vertices (mm). Vertices only: other CARTESIAN_POINTs
    are axis placements and spline poles that lie outside the part."""
    s = open(path, encoding="latin-1").read()
    if "ITEM_DEFINED_TRANSFORMATION" in s or "MILLI" not in s:
        raise SystemExit("%s: STEP assembly transforms or non-mm units, not handled" % path)
    pts = dict(re.findall(r"#(\d+)\s*=\s*CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(([^)]*)\)", s))
    ids = re.findall(r"VERTEX_POINT\s*\(\s*'[^']*'\s*,\s*#(\d+)", s)
    xs, ys, zs = zip(*[[float(v) for v in pts[i].split(",")] for i in ids])
    return tuple(round(f(a), 4) for a in (xs, ys, zs) for f in (min, max))


def fetch():
    if not os.path.exists(E2K):
        raise SystemExit("easyeda2kicad not found at %s (set E2K)" % E2K)
    todo = needed()
    if not todo:
        print("every footprint has a model file")
    data = json.load(open(JSON)) if os.path.exists(JSON) else {}
    os.makedirs(MODEL_DIR, exist_ok=True)
    for fpid, (lcsc, refs) in sorted(todo.items()):
        tmp = tempfile.mkdtemp(prefix="e2k-")
        subprocess.run([E2K, "--lcsc_id", lcsc, "--footprint", "--3d", "--overwrite",
                        "--output", os.path.join(tmp, "lcsc")], check=True, stdout=subprocess.DEVNULL)
        pretty = os.path.join(tmp, "lcsc.pretty")
        names = [f[:-10] for f in os.listdir(pretty) if f.endswith(".kicad_mod")]
        efp = pcbnew.FootprintLoad(pretty, names[0])
        m = list(efp.Models())[0]
        src = os.path.basename(m.m_Filename)
        step = os.path.join(tmp, "lcsc.3dshapes", os.path.splitext(src)[0] + ".step")
        if not os.path.exists(step):
            raise SystemExit("%s: easyeda2kicad gave no STEP model" % lcsc)
        if abs(m.m_Rotation.x) > 1e-6 or abs(m.m_Rotation.y) > 1e-6:
            raise SystemExit("%s: model is rotated about x/y, extend the transform" % lcsc)
        ours, theirs = pads(load_fp(fpid)), pads(efp)
        theta, tx, ty, n, maxerr = match(theirs, ours)
        # 1. Where the model belongs on EasyEDA's footprint. easyeda2kicad 1.0.1 bakes EasyEDA's
        #    placement (the model outline centre T) into the VRML before KiCad's model rotation,
        #    and copies the STEP untouched with offset 0: the STEP sits wrong whenever T != 0, and
        #    both sit wrong when the model is rotated (J7: 2.4 mm). So: centre of the VRML = T, the
        #    STEP's own vertex bounding box gives its centre c, and KiCad shows a model point p at
        #    offset + Rz(-rotate) p (model rotation is clockwise seen from the top, opposite to a
        #    footprint orientation; checked on a render). Offset on EasyEDA's footprint:
        #    T - Rz(-rotate) c; z: the STEP's lowest point goes where the VRML's is.
        wrl = os.path.join(tmp, "lcsc.3dshapes", os.path.splitext(src)[0] + ".wrl")
        w, b = wrl_box(wrl), step_box(step)
        cx, cy = rz((b[0] + b[1]) / 2, (b[2] + b[3]) / 2, -m.m_Rotation.z)
        ex, ey = (w[0] + w[1]) / 2 - cx, (w[2] + w[3]) / 2 - cy
        ez = w[4] - b[4]
        # 2. Our footprint = EasyEDA's rotated by theta (counter-clockwise) and moved by (tx, ty)
        #    in PCB axes (y down); 3D axes have y up.
        ox, oy = rz(ex, ey, theta)
        off = [round(ox + tx, 4) + 0.0, round(oy - ty, 4) + 0.0, round(ez, 4) + 0.0]
        rzz = (m.m_Rotation.z - theta + 180) % 360 - 180
        name = "%s_%s.step" % (lcsc, os.path.splitext(src)[0])
        shutil.copy(step, os.path.join(MODEL_DIR, name))
        data[fpid] = {"lcsc": lcsc, "refs": refs, "file": "${KIPRJMOD}/3d/" + name,
                      "offset": off, "rotate": [0, 0, round(rzz, 3)],
                      "step_size_mm": [round(b[1] - b[0], 3), round(b[3] - b[2], 3), round(b[5] - b[4], 3)],
                      "easyeda_footprint": names[0],
                      "match": {"pads_matched": n, "pads_easyeda": len(theirs), "pads_ours": len(ours),
                                "theta": theta, "max_err_mm": round(maxerr, 3)}}
        print("%-50s %-10s %-8s pads %d/%d (ours %d) theta %3d err %.3f -> offset %s rot %s" % (
            fpid, lcsc, ",".join(refs), n, len(theirs), len(ours), theta, maxerr, off, round(rzz, 3)))
        shutil.rmtree(tmp, ignore_errors=True)
    with open(JSON, "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")
    print("wrote", JSON)


def apply(board):
    """Point each matching footprint of a board at its fetched model. Returns the refs changed."""
    if not os.path.exists(JSON):
        return []
    data = json.load(open(JSON))
    done = []
    for fp in board.GetFootprints():
        fpid = "%s:%s" % (fp.GetFPID().GetLibNickname(), fp.GetFPID().GetLibItemName())
        e = data.get(fpid)
        if not e:
            continue
        models = fp.Models()
        mdl = models[0] if len(models) else pcbnew.FP_3DMODEL()
        mdl.m_Filename = e["file"]
        mdl.m_Offset = pcbnew.VECTOR3D(*e["offset"])
        mdl.m_Rotation = pcbnew.VECTOR3D(*e["rotate"])
        mdl.m_Scale = pcbnew.VECTOR3D(1, 1, 1)
        mdl.m_Show = True
        if not len(models):
            models.append(mdl)
        while len(fp.Models()) > 1:
            fp.Models().pop()
        done.append(fp.GetReference())
    return sorted(done)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "fetch":
        fetch()
    elif cmd == "apply":
        path = sys.argv[2] if len(sys.argv) > 2 else os.path.join(KDIR, "defuse32-carrier.kicad_pcb")
        b = pcbnew.LoadBoard(path)
        print("models set on:", " ".join(apply(b)) or "nothing")
        pcbnew.SaveBoard(path, b)
    elif cmd == "check":
        for fpid, (lcsc, refs) in sorted(needed().items()):
            print("no model file: %-50s %s %s" % (fpid, lcsc, ",".join(refs)))
    else:
        raise SystemExit(__doc__)
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
