"""Defuse32 rev 0 mechanical CAD (entry point).

Run from anywhere:   freecad.cmd hardware/defuse32/cad/build.py
Options (environment):
  D32_LID_DEG=100   lid opening angle about the back hinge (0 = closed)
  D32_NO_GUI=1      skip the offscreen GUI (no view colours in the FCStd, no renders)

Generates cad/defuse32.FCStd, cad/out/* (DXF, STL, STEP, GLB, reports) and
renders/cad_*.png. It never deletes or writes any other file in renders/ (the
KiCad side owns renders/carrier-*.png) or outside cad/. Re-running picks up cad/carrier.step when the KiCad side
has written it. All dimensions come from data/parts.json and layout.py.
"""
import math
import os
import sys
import json
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

OUT = os.path.join(HERE, "out")
RENDERS = os.path.join(ROOT, "renders")
RENDER_PREFIX = "cad_"      # the only files this script may write in renders/


def render_path(fname):
    """Path for one of OUR renders; refuses anything else in the shared renders/ folder."""
    if not (fname.startswith(RENDER_PREFIX) and fname.endswith(".png") and os.sep not in fname):
        raise ValueError("build.py only writes renders/%s*.png, not %r" % (RENDER_PREFIX, fname))
    return os.path.join(RENDERS, fname)

FCSTD = os.path.join(HERE, "defuse32.FCStd")
CARRIER_STEP = os.environ.get("D32_CARRIER_STEP", os.path.join(HERE, "carrier.step"))
LID_DEG = float(os.environ.get("D32_LID_DEG", "100"))

_LOG = []


def log(msg=""):
    _LOG.append(msg)
    try:
        sys.__stdout__.write(msg + "\n")
        sys.__stdout__.flush()
    except Exception:
        pass


# ---------------------------------------------------------------- GUI (offscreen)
GUI = False
if not os.environ.get("D32_NO_GUI"):
    try:
        import FreeCAD as _App
        if _App.GuiUp:
            GUI = True
        else:
            os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
            import FreeCADGui as _Gui
            _Gui.showMainWindow()
            GUI = True
    except Exception as e:  # pragma: no cover
        GUI = False
        log("note: offscreen GUI unavailable (%s); continuing headless" % e)

import FreeCAD as App
import Part

import d32lib as L
import layout as LY
from d32lib import V, C, Cut, Engrave

if GUI:
    import FreeCADGui as Gui

t_start = time.time()
os.makedirs(OUT, exist_ok=True)
os.makedirs(RENDERS, exist_ok=True)

with open(os.path.join(ROOT, "data", "parts.json")) as fh:
    PARTS = json.load(fh)
L.configure(PARTS)
Z = L.Z
MOD = PARTS["modules"]
CASE = PARTS["case"]
INT = CASE["interior"]
PAN = CASE["panel"]
FRM = CASE["panel_frame"]

FONT = next((f for f in LY.FONTS if os.path.exists(f)), None)
log("Defuse32 CAD build  (FreeCAD %s, GUI=%s, font=%s)" % (".".join(App.Version()[:3]), GUI, FONT))

# ------------------------------------------------------------------- document
for old in (FCSTD, FCSTD + "1", FCSTD.replace(".FCStd", ".FCBak")):
    if os.path.exists(old):
        os.remove(old)
doc = App.newDocument("Defuse32")
ITEMS = []        # every visible object: dict(obj, name, shape, colour, alpha, group, role, plate, module)
GROUPS = {}


def group(name):
    if name not in GROUPS:
        GROUPS[name] = doc.addObject("App::DocumentObjectGroup", name)
    return GROUPS[name]


def add(name, shape, colour, alpha=1.0, grp="Misc", role="misc", plate=None, module=None, export=True):
    nm = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    obj = doc.addObject("Part::Feature", nm)
    obj.Label = name
    obj.Shape = shape
    for prop, val in (("Colour", colour), ("Role", role), ("Plate", plate or ""), ("Module", module or "")):
        obj.addProperty("App::PropertyString", prop, "Defuse32")
        setattr(obj, prop, val)
    obj.addProperty("App::PropertyFloat", "Alpha", "Defuse32")
    obj.Alpha = alpha
    group(grp).addObject(obj)
    it = dict(obj=obj, name=obj.Name, shape=shape, colour=colour, alpha=alpha, group=grp, role=role,
              plate=plate, module=module, export=export)
    ITEMS.append(it)
    return it


# ======================================================================= CASE
WALL_T = 6.0                        # assumption: simplified uniform shell wall
SKIN_T = (CASE["exterior"]["h"] - INT["total_depth"]) / 2.0     # floor / lid skin, 8.75
R_IN = INT["corner_r"]
BASE_D = INT["base_depth"]
LID_D = INT["lid_depth"]


def interior_half(z):
    """Interior half-length / half-width at height z (linear wall draft floor -> rim)."""
    k = z / BASE_D
    return ((INT["floor_l"] + (INT["l"] - INT["floor_l"]) * k) / 2.0,
            (INT["floor_w"] + (INT["w"] - INT["floor_w"]) * k) / 2.0)


def base_shell():
    zt = BASE_D + 2.0
    hx0, hy0 = interior_half(0.0)
    hx1, hy1 = interior_half(zt)
    inner = Part.makeLoft([L.rrect_wire(0, 0, 2 * hx0, 2 * hy0, R_IN, 0.0),
                           L.rrect_wire(0, 0, 2 * hx1, 2 * hy1, R_IN, zt)], True, True)
    ex0, ey0 = interior_half(-SKIN_T)
    outer = Part.makeLoft([L.rrect_wire(0, 0, 2 * (ex0 + WALL_T), 2 * (ey0 + WALL_T), R_IN + WALL_T, -SKIN_T),
                           L.rrect_wire(0, 0, 2 * (INT["l"] / 2 + WALL_T), 2 * (INT["w"] / 2 + WALL_T),
                                        R_IN + WALL_T, BASE_D)], True, True)
    return outer.cut(inner)


def lid_shell():
    outer = L.rrect_face(0, 0, INT["l"] + 2 * WALL_T, INT["w"] + 2 * WALL_T, R_IN + WALL_T, BASE_D).extrude(
        V(0, 0, LID_D + SKIN_T))
    inner = L.rrect_face(0, 0, INT["l"], INT["w"], R_IN, BASE_D - 1.0).extrude(V(0, 0, LID_D + 1.0))
    return outer.cut(inner)


# Wall parts: key switch and USB-C on the right (+x) wall, z 40-100.
WALL_PARTS = [
    dict(id="KeySwitch", key="key_switch_19mm", y=60.0, z=70.0, inner_d=22.0, outer_d=28.0),
    dict(id="USBC", key="usbc_panel", y=-60.0, z=70.0, inner_d=21.5, outer_d=29.5),
]

base = base_shell()
wall_cuts = []
for wp in WALL_PARTS:
    m = MOD[wp["key"]]
    d = m["panel_hole"]["d"]
    x_in = interior_half(wp["z"] - d / 2)[0] - 1.0
    wall_cuts.append(Part.makeCylinder(d / 2, WALL_T + 10.0, V(x_in, wp["y"], wp["z"]), V(1, 0, 0)))
base = base.cut(wall_cuts)
add("Case_Base", base, C["case"], 0.35, "Case", "case")

lid = lid_shell()
lid_closed = lid.copy()
hinge_y = INT["w"] / 2 + WALL_T
if abs(LID_DEG) > 1e-6:
    lid.rotate(V(0, hinge_y, BASE_D), V(1, 0, 0), -LID_DEG)
add("Case_Lid", lid, C["case"], 0.35, "Case", "case")

for wp in WALL_PARTS:
    m = MOD[wp["key"]]
    r_in = wp["inner_d"] / 2
    x_in = interior_half(wp["z"] - r_in)[0]                 # innermost wall face over the body height
    x_out = interior_half(wp["z"] + wp["outer_d"] / 2)[0] + WALL_T
    inside = Part.makeCylinder(r_in, m["height_below_pcb"], V(x_in - m["height_below_pcb"], wp["y"], wp["z"]),
                               V(1, 0, 0))
    outside = Part.makeCylinder(wp["outer_d"] / 2, m["height_above_pcb"], V(x_out, wp["y"], wp["z"]), V(1, 0, 0))
    col = C["keyswitch"] if wp["id"] == "KeySwitch" else C["usbc"]
    add("Wall_%s_inside" % wp["id"], inside, col, 1.0, "Wall", "wall")
    add("Wall_%s_outside" % wp["id"], outside, col, 1.0, "Wall", "wall")

# ================================================================ PANEL FRAME
fz1 = Z["panel_bot"]
fz0 = fz1 - FRM["height"]
flange_t, skirt_t, boss_d, boss_h = 3.0, 2.5, 8.0, 10.0     # simplified frame (assumed section)
INSERTS = [(h["x"] - PAN["l"] / 2, h["y"] - PAN["w"] / 2) for h in PAN["screw_holes"]]
ring = L.rrect_face(0, 0, FRM["outer_l"], FRM["outer_w"], FRM["outer_corner_r"], fz1 - flange_t).cut(
    L.rrect_face(0, 0, FRM["inner_opening_l"], FRM["inner_opening_w"], 3.0, fz1 - flange_t)).extrude(V(0, 0, flange_t))
skirt = L.rrect_face(0, 0, FRM["outer_l"], FRM["outer_w"], FRM["outer_corner_r"], fz0).cut(
    L.rrect_face(0, 0, FRM["outer_l"] - 2 * skirt_t, FRM["outer_w"] - 2 * skirt_t, FRM["outer_corner_r"] - skirt_t,
                 fz0)).extrude(V(0, 0, FRM["height"] - flange_t))
bosses = [L.cyl(x, y, fz1 - flange_t - boss_h, boss_d, boss_h) for x, y in INSERTS]
frame = ring.fuse([skirt] + bosses).cut([L.cyl(x, y, fz0 - 1, FRM["insert_hole_d"], FRM["height"] + 2)
                                         for x, y in INSERTS]).removeSplitter()
add("Panel_Frame_1520PF", frame, C["frame"], 1.0, "Frame", "frame")

# ====================================================================== PLATES
PL = LY.PLATE
OP = LY.OPENING
SCREW_XY = [(sx * (PL["w"] / 2 - PL["screw_inset"]), sy * (PL["h"] / 2 - PL["screw_inset"]))
            for sx in (-1, 1) for sy in (-1, 1)]
PLATE_DATA = {}


def make_transform(at, anchor, rot):
    ca, sa = math.cos(math.radians(rot)), math.sin(math.radians(rot))

    def fn(x, y):
        dx, dy = x - anchor[0], y - anchor[1]
        return at[0] + ca * dx - sa * dy, at[1] + sa * dx + ca * dy

    def shp(s):
        s = s.copy()
        s.translate(V(-anchor[0], -anchor[1], 0))
        if rot:
            s.rotate(V(0, 0, 0), V(0, 0, 1), rot)
        s.translate(V(at[0], at[1], 0))
        return s

    return fn, shp


def build_item(pid, it):
    kind, iid = it["kind"], it["id"]
    tag = iid
    opt = it.get("opt", {})
    if kind == "module":
        spec = MOD[it["key"]]
        builder = {"ssd1306_096": L.b_oled, "sh1106_13": L.b_oled, "tm1637_056": L.b_tm1637, "ky040": L.b_ky040,
                   "keypad_4x4_hard": L.b_keypad, "pn532_v3": L.b_pn532, "buzzer_12mm": L.b_buzzer,
                   "banana_post_4mm": L.b_banana, "gl5528": L.b_ldr, "vs1838b": L.b_ir}[it["key"]]
        if it["key"] == "banana_post_4mm" and "colour" in opt:
            opt = dict(opt, colour=C[opt["colour"]])
        res = builder(spec, opt, tag)
        a = it.get("anchor")
        if a == "shaft":
            anchor = (spec["shaft"]["x"], spec["shaft"]["y"])
        elif a == "origin_centre":
            anchor = (0.0, 0.0)
        else:
            anchor = (spec["pcb"]["w"] / 2, spec["pcb"]["h"] / 2)
        res["key"] = it["key"]
    elif kind == "ws2812":
        res = L.b_ws2812(MOD["ws2812b"], opt, tag)
        anchor = (0.0, 0.0)
        res["key"] = "ws2812b"
    elif kind == "touchpad":
        res = L.b_touchpad(opt, tag)
        anchor = (0.0, 0.0)
        res["key"] = "touch pad (copper tape)"
    elif kind == "simon":
        sb = LY.EXTRA["simon_board"]
        res = L.b_simon(sb, dict(cap_hole_d=LY.OPT["tact_cap_hole_d"], cap_proud=LY.OPT["tact_cap_proud"]), tag,
                        MOD["tact_12mm"])
        anchor = (sb["w"] / 2, sb["h"] / 2)
        res["key"] = "simon_board + 4 x tact_12mm + 4 x ws2812b"
    elif kind == "probe":
        pb = LY.EXTRA["probe_perfboard"]
        ox, oy = it["at"][0] - pb["w"] / 2, it["at"][1] - pb["h"] / 2     # plate-local -> board coords

        def b(p):
            return (p[0] - ox, p[1] - oy)

        popt = dict(headers={k: (v[0] - ox, v[1] - oy, v[2]) for k, v in it["headers"].items()},
                    soic=b(it["soic"]), dip=b(it["dip"]), test_points=[b(p) for p in it["test_points"]],
                    tp_hole_d=LY.OPT["test_point_hole_d"])
        res = L.b_probe(pb, popt, tag, MOD["header_254"], MOD["dip8_socket"], MOD["soic8_breakout"])
        anchor = (pb["w"] / 2, pb["h"] / 2)
        res["key"] = "probe_perfboard + header_254 + dip8_socket + soic8_breakout"
    elif kind == "servo":
        res = L.b_sg90(MOD["sg90"], dict(y_flange=it["y_flange"]), tag)
        res["key"] = "sg90 + printed bracket"
        anchor = (0.0, 0.0)
        it = dict(it, at=(it["shaft_x"], 0.0))
    else:
        raise ValueError(kind)
    fn, shp = make_transform(it["at"], anchor, it.get("rot", 0.0))
    return dict(id=iid, key=res["key"], at=it["at"], mount=res["mount"],
                parts=[(sfx, shp(s), col, a) for sfx, s, col, a in res["parts"]],
                cuts=[c.moved(fn, it.get("rot", 0.0)) for c in res["cuts"]],
                engr=[e.moved(fn, it.get("rot", 0.0)) for e in res["engr"]])


for pid in LY.ORDER:
    spec = LY.PLATES[pid]
    cx, cy = LY.plate_centre(pid)
    items = [build_item(pid, it) for it in spec["items"]]
    items.append(build_item(pid, dict(kind="ws2812", id="StatusLED", at=LY.STATUS_LED_AT)))
    cuts = [Cut("plate M3 hole %d" % (i + 1), "circle", x, y, PL["screw_d"]) for i, (x, y) in enumerate(SCREW_XY)]
    engr = [Engrave("title", "text", LY.TITLE_AT[0], LY.TITLE_AT[1], depth=LY.ENGRAVE_DEPTH, text=spec["title"],
                    size=LY.TITLE_CAP)]
    for itm in items:
        cuts += itm["cuts"]
        engr += itm["engr"]
    outline = L.rrect_face(0, 0, PL["w"], PL["h"], PL["corner_r"])
    solid = outline.extrude(V(0, 0, PL["t"]))
    tools = []
    for c in cuts:
        f = c.face(-1.0)
        tools.append(f.extrude(V(0, 0, PL["t"] + 2)))
    for e in engr:
        for f in e.faces(FONT):
            f2 = f.copy()
            f2.translate(V(0, 0, PL["t"] - e.depth))
            tools.append(f2.extrude(V(0, 0, e.depth + 1.0)))
    solid = solid.cut(tools)
    world = solid.copy()
    world.translate(V(cx, cy, Z["plate_bot"]))
    add("Plate_%s" % pid, world, C["plate"], 1.0, pid, "plate", plate=pid)
    for itm in items:
        for sfx, s, col, a in itm["parts"]:
            s2 = s.copy()
            s2.translate(V(cx, cy, 0))
            add("%s_%s_%s" % (pid, itm["id"], sfx), s2, col, a, pid, "module", plate=pid, module=itm["id"])
    PLATE_DATA[pid] = dict(centre=(cx, cy), local=solid, outline=outline, cuts=cuts, engr=engr, items=items)
    log("plate %s: %d through-cuts, %d engravings, %d items" % (pid, len(cuts), len(engr), len(items)))

# ======================================================================= PANEL
panel_cuts = []
for i, (x, y) in enumerate(INSERTS):
    panel_cuts.append(Cut("frame hole %d" % (i + 1), "circle", x, y, PAN["screw_hole_d"]))
for pid in LY.ORDER:
    cx, cy = PLATE_DATA[pid]["centre"]
    panel_cuts.append(Cut("%s opening" % pid, "rect", cx, cy, OP["w"], OP["h"]))
    for i, (x, y) in enumerate(SCREW_XY):
        panel_cuts.append(Cut("%s plate screw %d" % (pid, i + 1), "circle", cx + x, cy + y, PL["screw_d"]))
panel_outline = L.rrect_face(0, 0, PAN["l"], PAN["w"], PAN["corner_r"])
panel_local = panel_outline.extrude(V(0, 0, PAN["thickness"])).cut(
    [c.face(-1).extrude(V(0, 0, PAN["thickness"] + 2)) for c in panel_cuts])
panel = panel_local.copy()
panel.translate(V(0, 0, Z["panel_bot"]))
add("Panel", panel, C["panel"], 1.0, "Panel", "panel")

# ===================================================================== CARRIER
SLED_T = 3.0
sled = L.rrect_face(0, 0, INT["floor_l"] - 2.0, INT["floor_w"] - 2.0, R_IN - 1.0).extrude(V(0, 0, SLED_T))
add("Floor_Sled", sled, C["sled"], 1.0, "Carrier", "sled")
CAR_L, CAR_W, CAR_T, CAR_Z = 190.0, 140.0, 1.6, 11.0
car_holes = [(sx * (CAR_L / 2 - 5.0), sy * (CAR_W / 2 - 5.0)) for sx in (-1, 1) for sy in (-1, 1)]
for i, (x, y) in enumerate(car_holes):
    s = L.hexprism(x, y, SLED_T, 5.5, CAR_Z - SLED_T).cut(L.cyl(x, y, 0, 2.5, CAR_Z + 1))
    add("Carrier_Standoff%d" % (i + 1), s, C["brass"], 1.0, "Carrier", "carrier_hw")

carrier_source = "placeholder"
carrier_items = []
if os.path.exists(CARRIER_STEP) and os.path.getsize(CARRIER_STEP) > 0:
    try:
        imp = Part.read(CARRIER_STEP)
        solids = imp.Solids
        cands = [s for s in solids if abs(s.BoundBox.ZLength - CAR_T) < 0.3 and s.BoundBox.XLength > 100]
        if cands:
            board = max(cands, key=lambda s: s.BoundBox.XLength * s.BoundBox.YLength)
        else:
            board = None
        ref = board.BoundBox if board else imp.BoundBox
        rot = 0.0
        if ref.YLength > ref.XLength * 1.05:
            rot = 90.0
        cxb, cyb = (ref.XMin + ref.XMax) / 2, (ref.YMin + ref.YMax) / 2
        mv = imp.copy()
        mv.translate(V(-cxb, -cyb, 0))
        if rot:
            mv.rotate(V(0, 0, 0), V(0, 0, 1), rot)
        zmin_board = ref.ZMin
        mv.translate(V(0, 0, CAR_Z - zmin_board))
        if board:
            bsh = board.copy()
            bsh.translate(V(-cxb, -cyb, 0))
            if rot:
                bsh.rotate(V(0, 0, 0), V(0, 0, 1), rot)
            bsh.translate(V(0, 0, CAR_Z - zmin_board))
            others = []
            for s in mv.Solids:
                bb = s.BoundBox
                if abs(bb.ZLength - CAR_T) < 0.3 and bb.XLength > 100:
                    continue
                others.append(s)
            carrier_items.append(add("Carrier_PCB", bsh, C["carrier"], 1.0, "Carrier", "carrier"))
            if others:
                carrier_items.append(add("Carrier_Components", Part.makeCompound(others), C["chip"], 1.0, "Carrier",
                                         "carrier"))
        else:
            carrier_items.append(add("Carrier_STEP", mv, C["carrier"], 1.0, "Carrier", "carrier"))
        carrier_source = "carrier.step (%d solids, board %s, rotated %d deg)" % (
            len(solids), "found" if board else "NOT identified: aligned by overall bbox", rot)
    except Exception as e:
        log("WARNING: could not import carrier.step (%s); using placeholder" % e)
        carrier_items = []
if not carrier_items:
    pcb = L.rrect_face(0, 0, CAR_L, CAR_W, 0.0, CAR_Z).extrude(V(0, 0, CAR_T)).cut(
        [L.cyl(x, y, CAR_Z - 1, 3.2, CAR_T + 2) for x, y in car_holes])
    carrier_items.append(add("Carrier_PCB", pcb, C["carrier"], 1.0, "Carrier", "carrier"))
log("carrier: %s" % carrier_source)
for c in carrier_items:
    cbb = c["shape"].BoundBox
    log("carrier: %s x %.1f..%.1f y %.1f..%.1f z %.1f..%.1f" % (c["name"], cbb.XMin, cbb.XMax, cbb.YMin, cbb.YMax,
                                                              cbb.ZMin, cbb.ZMax))
KEEP_Z = 40.0     # carrier component / harness-connector zone top (parts.json depth budget)
keepout = L.cbox(0, 0, CAR_Z + CAR_T, CAR_L, CAR_W, KEEP_Z - CAR_Z - CAR_T)
ko = add("Carrier_Keepout", keepout, C["keepout"], 0.25, "Carrier", "keepout", export=False)

doc.recompute()

# ================================================================= FIT CHECKS
log("")
log("=" * 72)
log("FIT CHECKS")
log("=" * 72)
FAILS = []
EPS = 1e-3


def check(ok, msg):
    log(("PASS  " if ok else "FAIL  ") + msg)
    if not ok:
        FAILS.append(msg)
    return ok


def bb_overlap(a, b, tol=0.0):
    return (a.XMin < b.XMax - tol and a.XMax > b.XMin + tol and a.YMin < b.YMax - tol and a.YMax > b.YMin + tol
            and a.ZMin < b.ZMax - tol and a.ZMax > b.ZMin + tol)


def common_vol(a, b):
    if not bb_overlap(a.BoundBox, b.BoundBox, 1e-6):
        return 0.0
    try:
        return a.common(b).Volume
    except Exception:
        return float("nan")


# 1. panel / plate heights
pbb = panel.optimalBoundingBox(False, False)
rim = base.optimalBoundingBox(False, False).ZMax
check(abs(pbb.ZMax - PAN["z_top"]) < EPS and abs(rim - PAN["z_top"]) < EPS,
      "panel top z = %.2f, base rim z = %.2f (flush at %.1f)" % (pbb.ZMax, rim, PAN["z_top"]))
for pid in LY.ORDER:
    sb = [i for i in ITEMS if i["role"] == "plate" and i["plate"] == pid][0]["shape"].BoundBox
    if abs(sb.ZMin - Z["plate_bot"]) > EPS or abs(sb.ZMax - Z["plate_top"]) > EPS:
        check(False, "plate %s z %.2f..%.2f" % (pid, sb.ZMin, sb.ZMax))
check(True, "plates z %.1f..%.1f on the panel" % (Z["plate_bot"], Z["plate_top"]))

# 2. plate openings inside the frame clear opening, plates inside the panel
cz_l, cz_w = FRM["inner_opening_l"] / 2, FRM["inner_opening_w"] / 2
worst = min(min(cz_l - (abs(PLATE_DATA[p]["centre"][0]) + OP["w"] / 2),
                cz_w - (abs(PLATE_DATA[p]["centre"][1]) + OP["h"] / 2)) for p in LY.ORDER)
check(worst >= 0, "panel openings inside the 1520PF clear opening (min margin %.1f mm)" % worst)

# 3. hanging modules inside the opening footprint and <= 40 mm below the plate
HANG_MIN_Z = Z["plate_bot"] - 40.0
CAP_Z = Z["plate_top"] + 35.0
below_box = L.box(-1000, -1000, -100, 2000, 2000, Z["plate_bot"] + 100)
for pid in LY.ORDER:
    cx, cy = PLATE_DATA[pid]["centre"]
    fx0, fx1, fy0, fy1 = cx - OP["w"] / 2, cx + OP["w"] / 2, cy - OP["h"] / 2, cy + OP["h"] / 2
    worst_m, worst_name, zlow, zhigh, bad = 1e9, "", 1e9, -1e9, []
    for it in ITEMS:
        if it["role"] != "module" or it["plate"] != pid:
            continue
        s = it["shape"]
        bb = s.optimalBoundingBox(False, False)
        zhigh = max(zhigh, bb.ZMax)
        if bb.ZMin >= Z["plate_bot"] - EPS:
            continue
        hb = bb if bb.ZMax <= Z["plate_bot"] + EPS else s.common(below_box).optimalBoundingBox(False, False)
        zlow = min(zlow, hb.ZMin)
        m = min(hb.XMin - fx0, fx1 - hb.XMax, hb.YMin - fy0, fy1 - hb.YMax)
        if m < worst_m:
            worst_m, worst_name = m, it["name"]
        if m < -EPS or hb.ZMin < HANG_MIN_Z - EPS:
            bad.append(it["name"])
    check(not bad, "%s hanging parts inside the %gx%g opening footprint (min margin %.2f mm at %s), lowest z %.1f "
          "(%.1f below plate, limit 40)%s" % (pid, OP["w"], OP["h"], worst_m, worst_name, zlow,
                                              Z["plate_bot"] - zlow, (" OFFENDERS: " + ", ".join(bad)) if bad else ""))
    check(zhigh <= CAP_Z + EPS, "%s tallest part z %.1f = %.1f above the plate top (cap 35)" % (
        pid, zhigh, zhigh - Z["plate_top"]))

# 4. nothing intersects its plate or the panel (everything passes through cut-outs)
for pid in LY.ORDER:
    plate_s = [i for i in ITEMS if i["role"] == "plate" and i["plate"] == pid][0]["shape"]
    hits = []
    for it in ITEMS:
        if it["role"] != "module" or it["plate"] != pid:
            continue
        for tgt, tname in ((plate_s, "plate"), (panel, "panel")):
            v = common_vol(it["shape"], tgt)
            if v > 0.01 or v != v:
                hits.append("%s/%s %.2f mm3" % (it["name"], tname, v))
    check(not hits, "%s modules clear of plate and panel material (through cut-outs only)%s" % (
        pid, (": " + "; ".join(hits)) if hits else ""))

# 5. module-to-module clashes on each plate
for pid in LY.ORDER:
    mods = [i for i in ITEMS if i["role"] == "module" and i["plate"] == pid]
    hits = []
    for a_i in range(len(mods)):
        for b_i in range(a_i + 1, len(mods)):
            a, b = mods[a_i], mods[b_i]
            if a["module"] == b["module"]:
                continue
            v = common_vol(a["shape"], b["shape"])
            if v > 0.01 or v != v:
                hits.append("%s x %s %.2f mm3" % (a["name"], b["name"], v))
    check(not hits, "%s no clashes between different modules%s" % (pid, (": " + "; ".join(hits)) if hits else ""))

# 6. carrier / sled / keep-out vs everything above
obst = [("sled", sled), ("keep-out z<=%.0f" % KEEP_Z, keepout)] + [(c["name"], c["shape"]) for c in carrier_items]
obst += [(i["name"], i["shape"]) for i in ITEMS if i["role"] == "carrier_hw"]
movers = [i for i in ITEMS if i["role"] in ("module", "wall", "plate", "panel", "frame")]
hits = []
mind, mind_name = 1e9, ""
for it in movers:
    for oname, osh in obst:
        v = common_vol(it["shape"], osh)
        if v > 0.01 or v != v:
            hits.append("%s x %s %.2f mm3" % (it["name"], oname, v))
    if it["role"] in ("module", "wall"):
        d = it["shape"].distToShape(keepout)[0]
        if d < mind:
            mind, mind_name = d, it["name"]
check(not hits, "nothing intersects the carrier PCB/components, its standoffs, the sled or the carrier keep-out "
      "(min clearance to keep-out %.1f mm at %s)%s" % (mind, mind_name, (": " + "; ".join(hits)) if hits else ""))

# 6b. the carrier's tallest parts (DevKit sockets + DevKit, 470 uF cap) stay under the keep-out top
car_top = max(c["shape"].BoundBox.ZMax for c in carrier_items)
low_mod = min((i["shape"].optimalBoundingBox(False, False).ZMin, i["name"]) for i in ITEMS if i["role"] == "module")
check(car_top <= KEEP_Z + EPS, "carrier tallest part z %.1f (%.1f above the board) <= keep-out top z %.0f; lowest "
      "module part z %.1f at %s (gap %.1f) [%s]" % (car_top, car_top - CAR_Z - CAR_T, KEEP_Z, low_mod[0], low_mod[1],
                                                   low_mod[0] - car_top, carrier_source))

# 7. wall parts: hole band z 40-100, clear of base shell material, frame and modules
for wp in WALL_PARTS:
    m = MOD[wp["key"]]
    z0, z1 = wp["z"] - wp["outer_d"] / 2, wp["z"] + wp["outer_d"] / 2
    check(z0 >= 40 - EPS and z1 <= 100 + EPS, "%s on the right wall: y %.0f, hole dia %.1f, flange z %.1f..%.1f "
          "(band 40..100)" % (wp["id"], wp["y"], m["panel_hole"]["d"], z0, z1))
hits = []
for it in [i for i in ITEMS if i["role"] == "wall"]:
    for tname, tgt in [("base", base), ("frame", frame)] + [(i["name"], i["shape"]) for i in ITEMS
                                                            if i["role"] == "module"]:
        v = common_vol(it["shape"], tgt)
        if v > 0.05 or v != v:
            hits.append("%s x %s %.2f mm3" % (it["name"], tname, v))
check(not hits, "wall parts clear of the shell, frame and plate modules%s" % ((": " + "; ".join(hits)) if hits else ""))

# 8. closed lid
tallest = max(i["shape"].optimalBoundingBox(False, False).ZMax for i in ITEMS if i["role"] in ("module", "plate"))
lid_in_top = BASE_D + LID_D
check(tallest < lid_in_top, "lid closed: tallest part z %.1f < lid inner skin z %.1f (margin %.1f)" % (
    tallest, lid_in_top, lid_in_top - tallest))
v = sum(common_vol(i["shape"], lid_closed) for i in ITEMS if i["role"] in ("module", "plate", "panel", "frame"))
check(v < 0.01, "closed lid shell intersects nothing (%.3f mm3)" % v)

# 9. webs >= 3 mm between through-cuts and to the edge
WEB_MIN = 3.0


def web_check(name, outline_face, cuts):
    faces = [(c.label, c.face()) for c in cuts]
    ow = outline_face.OuterWire
    worst = (1e9, "")
    fails = []
    for i, (la, fa) in enumerate(faces):
        inside = outline_face.common(fa).Area > fa.Area - 1e-6
        d = ow.distToShape(fa)[0] if inside else -1.0
        if d < worst[0]:
            worst = (d, "%s <-> edge" % la)
        if d < WEB_MIN - 1e-6:
            fails.append("%s <-> edge %.2f" % (la, d))
        for lb, fb in faces[i + 1:]:
            d = fa.distToShape(fb)[0]
            if d < worst[0]:
                worst = (d, "%s <-> %s" % (la, lb))
            if d < WEB_MIN - 1e-6:
                fails.append("%s <-> %s %.2f" % (la, lb, d))
    check(not fails, "%s webs >= %.0f mm (min %.2f: %s)%s" % (name, WEB_MIN, worst[0], worst[1],
                                                            (" UNDER: " + "; ".join(fails)) if fails else ""))
    return worst


for pid in LY.ORDER:
    web_check("plate %s" % pid, PLATE_DATA[pid]["outline"], PLATE_DATA[pid]["cuts"])
web_check("panel", panel_outline, panel_cuts)

log("-" * 72)
log("fit checks: %d failure(s)" % len(FAILS))

# ==================================================================== EXPORTS
log("")
log("EXPORTS")
dxf_n = {}
for pid in LY.ORDER:
    pd = PLATE_DATA[pid]
    cut_edges = list(pd["outline"].Edges)
    for c in pd["cuts"]:
        cut_edges += c.face().Edges
    eng_edges = []
    for e in pd["engr"]:
        for f in e.faces(FONT):
            eng_edges += f.Edges
    n = L.write_dxf(os.path.join(OUT, "plate_%s.dxf" % pid), [("CUT", 1, cut_edges), ("ENGRAVE_1MM", 5, eng_edges)],
                    dx=PL["w"] / 2, dy=PL["h"] / 2)
    dxf_n[pid] = n
    L.write_stl(os.path.join(OUT, "plate_%s.stl" % pid), pd["local"])
pe = list(panel_outline.Edges)
for c in panel_cuts:
    pe += c.face().Edges
dxf_n["panel"] = L.write_dxf(os.path.join(OUT, "panel.dxf"), [("CUT", 1, pe)], dx=PAN["l"] / 2, dy=PAN["w"] / 2)
L.write_stl(os.path.join(OUT, "panel.stl"), panel_local)
log("DXF entities: " + ", ".join("%s %d" % kv for kv in dxf_n.items()))

# verify DXFs parse back
try:
    import importDXF  # noqa: F401
    rd = App.newDocument("dxfcheck")
    import Import
    Import.readDXF(os.path.join(OUT, "plate_M1.dxf"))
    log("DXF read-back (Import.readDXF plate_M1.dxf): %d objects" % len(App.ActiveDocument.Objects))
    App.closeDocument(rd.Name)
    App.setActiveDocument(doc.Name)
except Exception as e:
    log("DXF read-back skipped: %s" % e)

# colours on view objects (GUI) before STEP so the STEP carries them
if GUI:
    gdoc = Gui.getDocument(doc.Name)
    for it in ITEMS:
        vo = it["obj"].ViewObject
        r, g, b = L.hex_rgb(it["colour"])
        vo.ShapeColor = (r / 255.0, g / 255.0, b / 255.0)
        vo.Transparency = int(round((1.0 - it["alpha"]) * 100))
        if it["role"] == "keepout":
            vo.Visibility = False

exp_objs = [i["obj"] for i in ITEMS if i["export"]]
step_path = os.path.join(OUT, "assembly.step")
try:
    if GUI:
        import ImportGui
        ImportGui.export(exp_objs, step_path)
    else:
        import Import
        Import.export(exp_objs, step_path)
except Exception as e:
    log("ImportGui STEP export failed (%s), retrying without colours" % e)
    import Import
    Import.export(exp_objs, step_path)
glb_items = [dict(name=i["obj"].Label, shape=i["shape"], colour=i["colour"], alpha=i["alpha"], group=i["group"],
                  tol=0.6 if i["role"] in ("case", "frame") else 0.15) for i in ITEMS if i["export"]]
nm, nt = L.write_glb(os.path.join(OUT, "assembly.glb"), glb_items)
log("assembly.step, assembly.glb (%d meshes, %d triangles)" % (nm, nt))

# cut-out table (markdown) for the README
md = ["| Plate | Cut-out | Type | Size (mm) | Centre x, y from plate centre | From plate bottom-left |",
      "|---|---|---|---|---|---|"]
for pid in LY.ORDER:
    pd = PLATE_DATA[pid]
    for c in pd["cuts"]:
        md.append("| %s | %s | through | %s | %.2f, %.2f | %.2f, %.2f |" % (
            pid, c.label, c.size_str(), c.x, c.y, c.x + PL["w"] / 2, c.y + PL["h"] / 2))
    for e in pd["engr"]:
        md.append("| %s | %s | engrave | %s | %.2f, %.2f%s | |" % (
            pid, e.label, e.size_str(FONT), e.x, e.y, " (text box bottom-left)" if e.align == "left" and e.kind == "text"
            else ""))
mods = ["", "| Plate | Item | Part | At (plate-local) | Mounting |", "|---|---|---|---|---|"]
for pid in LY.ORDER:
    for itm in PLATE_DATA[pid]["items"]:
        mods.append("| %s | %s | %s | %.2f, %.2f | %s |" % (pid, itm["id"], itm["key"], itm["at"][0], itm["at"][1],
                                                            itm["mount"]))
with open(os.path.join(OUT, "plate_cutouts.md"), "w") as fh:
    fh.write("\n".join(md + mods) + "\n")

# ==================================================================== RENDERS
if GUI:
    try:
        view = gdoc.ActiveView
        view.setAxisCross(False)
        try:
            view.setAnimationEnabled(False)
        except Exception:
            pass
        lid_obj = [i for i in ITEMS if i["obj"].Name == "Case_Lid"][0]["obj"]

        def shoot(fname, how, w=1600, h=1200):
            getattr(view, how)()
            view.fitAll()
            Gui.updateGui()
            view.saveImage(render_path(fname), w, h, "White")
            log("render: renders/%s" % fname)

        shoot("cad_iso.png", "viewIsometric")
        lid_obj.ViewObject.Visibility = False
        shoot("cad_top.png", "viewTop")
        # exploded: frame +60, panel +120, plates with their modules +200
        offs = {"frame": 60.0, "panel": 120.0, "plate": 200.0, "module": 200.0}
        saved = []
        for it in ITEMS:
            dz = offs.get(it["role"])
            if dz:
                o = it["obj"]
                saved.append((o, o.Placement.copy()))
                o.Placement = App.Placement(V(0, 0, dz), App.Rotation()).multiply(o.Placement)
        base_obj = [i for i in ITEMS if i["obj"].Name == "Case_Base"][0]["obj"]
        shoot("cad_exploded.png", "viewIsometric")
        for o, p in saved:
            o.Placement = p
        # underside: case, sled and carrier hidden, looking up at the hanging modules
        hidden = [i["obj"] for i in ITEMS if i["role"] in ("case", "sled", "carrier", "carrier_hw", "frame", "wall")]
        for o in hidden:
            o.ViewObject.Visibility = False
        view.viewIsometric()
        view.setCameraOrientation(App.Rotation(V(1, 0, 0), 180).multiply(view.getCameraOrientation()))
        view.fitAll()
        Gui.updateGui()
        view.saveImage(render_path("cad_underside.png"), 1600, 1200, "White")
        log("render: renders/cad_underside.png")
        for o in hidden:
            o.ViewObject.Visibility = True
        lid_obj.ViewObject.Visibility = True
        doc.recompute()
    except Exception as e:
        log("renders failed: %s" % e)
else:
    log("renders skipped (no GUI)")

doc.saveAs(FCSTD)
log("saved %s (%d objects)" % (os.path.relpath(FCSTD, ROOT), len(ITEMS)))

with open(os.path.join(OUT, "fit_report.txt"), "w") as fh:
    fh.write("\n".join(_LOG) + "\n")
log("done in %.0f s, %d fit failure(s)" % (time.time() - t_start, len(FAILS)))
try:
    sys.__stdout__.flush()
except Exception:
    pass
os._exit(1 if (FAILS and os.environ.get("D32_STRICT")) else 0)
