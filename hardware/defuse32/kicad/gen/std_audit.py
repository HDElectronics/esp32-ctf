#!/usr/bin/env python3
"""Standards measurements for the Defuse32 carrier (standards pass, kicad/README.md "Standards pass
(2026-11-25)"). Read-only: the board file is never written. Port of the AirQuality project's
hardware/pcb/tools/std_audit.py, with this board's nets, currents and rules.

  /usr/bin/python3 gen/std_audit.py [board.kicad_pcb] [--json out.json]

Run from hardware/defuse32/kicad/ with KiCad's Python. Coordinates are board mm (origin = top-left
corner of the outline, x right, y down), as in design.py and the README; pcb_audit.py prints page
coordinates (board + 50 mm). What it measures (and DRC does not print):

  current     IPC-2221B 6.2 formula (I = k dT^0.44 A^0.725, k 0.048 external / 0.024 internal; the
              internal curve is the conservative stand-in for the IPC-2152 base chart, which has no
              plane modifier here) for the narrowest track of every power net and of the 5 V feeds of
              the box headers, the servo header and the buzzer, at the design current of the power
              budget (DESIGN_I, README "Standards pass"): temperature rise, and the current for a
              10 C rise;
  spacing     smallest gap between copper of different nets per layer (routed copper; pad pairs of
              one footprint reported apart) against IPC-2221B Table 6-1 (0-15 V: B2 0.1 mm external
              uncoated, B4 0.05 mm external coated, A6 0.13 mm component lead uncoated) and the board
              minimum; smallest copper-to-edge distance (IPC-2221B 5.3.1 / JLCPCB 0.2 mm, rule 0.3 mm);
  usb         D+/D- length, vias, width and coupled length; distance from the USB-C contacts to the
              ESD array (U9) along the tracks and in a straight line;
  returns     every signal via: nearest GND via (both inner layers are GND: an F.Cu <-> B.Cu change
              moves the return from In1 to In2 through the nearest GND via), fast nets flagged;
  edge        GND vias along the board edge: largest distance from a point 1.5 mm inside the edge to
              the nearest GND via (stitching fence; lambda/10 at 2.4 GHz in FR-4 ~ 6 mm);
  mask        smallest mask web between pads per side (mask expansion from the board and the pads;
              JLCPCB: 0.1 mm green dam), PTH and via annular rings (IPC-2221B 9.1.1 / Table 9-1),
              via counts and sizes, vias inside SMD pads (untented holes in a pad opening);
  parts       fitted footprints without an LCSC field; silkscreen strokes thinner than 0.15 mm
              (JLCPCB minimum line width) per footprint, filled marks listed apart;
  geometry    off-angle segments (heading > 1 deg off a multiple of 45 deg, longer than 0.02 mm),
              acute junctions (two arms of one net on one layer meeting at < 90 deg, T-junctions
              included), tracks running between adjacent pads of one footprint (< 1.0 mm apart, pitch
              <= 1.3 mm), track ends that enter a rectangular SMD pad off its axes, Power-class tracks
              narrower than 0.6 mm (neck-downs), segments shorter than 0.1 mm (router slivers and
              micro-loops: a ring of them hides a step from pcb_audit.py's jog check), teardrops.
Exit code 0 always (it measures; the README says what is accepted).
"""
import json
import math
import os
import sys
from collections import defaultdict

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design as D  # noqa: E402

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
PCB = ARGS[0] if ARGS else os.environ.get("D32_BOARD") or os.path.join(HERE, "..", "defuse32-carrier.kicad_pcb")
OUT = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
OX, OY = 50.0, 50.0                    # board origin on the page (gen_pcb.OX/OY)
mm = pcbnew.ToMM
MM = pcbnew.FromMM
F, B = pcbnew.F_Cu, pcbnew.B_Cu

# Design currents (A) from the power budget (README "Standards pass (2026-11-25)", power budget):
#   3V3  ESP32-WROOM-32E Wi-Fi TX peak + CH340C; Espressif asks for a >= 500 mA supply
#   3V3P PN532 RF on, two OLEDs, TM1637 at full brightness, microSD write peak, flash, MCPs, pull-ups
#   5V   both LDO inputs + 15 WS2812 at the firmware's default scale (64/255) + SG90 stall + buzzer;
#        the input path (VBUS, 5V trunk, GND return) is rated at F1's hold current
DESIGN_I = {
    "VBUS": (2.0, "F1 hold current (input path; worst concurrent peak 2.0 A at the firmware LED scale)"),
    "5V": (2.0, "F1 hold current on the trunk; branches carry less (see FEEDS)"),
    "3V3": (0.5, "ESP32 Wi-Fi TX peak + CH340C; Espressif: supply >= 500 mA"),
    "3V3P": (0.45, "PN532 + 2 OLED + TM1637 + microSD write + flash + MCP23017 x2 + pull-ups"),
    "GND": (2.0, "return of the input path"),
    "BUZZ-": (0.05, "12 mm magnetic buzzer at 5 V through Q1"),
}
# 5 V feeds: (pad, current A, what): the track at that pad
FEEDS = [
    ("J9", "2", 0.8, "SG90 servo, stall current"),
    ("J1", "1", 0.18, "M1: 3 WS2812 at full white (3 x 60 mA) + OLED/encoder are on 3V3P"),
    ("J2", "1", 0.24, "M2: 4 WS2812 at full white"),
    ("J2", "11", 0.05, "M2: buzzer BUZZ+ (5V)"),
    ("J3", "1", 0.06, "M3: 1 WS2812"),
    ("J4", "1", 0.06, "M4: 1 WS2812"),
    ("J5", "1", 0.06, "M5: 1 WS2812"),
    ("J6", "1", 0.30, "M6: 5 WS2812 (Simon 4 + status)"),
]
CU_T = 0.035                           # mm, 1 oz outer copper (JLC04161H-7628)
FAST = ("USB_DP", "USB_DM", "SCK", "MOSI", "MISO", "SD_CS", "CS", "WS_DATA", "LDI", "LDO1", "LDO2", "LDO3", "LDO4", "LDO5")
POWER = set(D.POWER_NETS)
OFF_ANGLE_DEG, OFF_ANGLE_MIN_LEN = 1.0, 0.02
ACUTE_DEG, ARM_MIN_LEN = 89.5, 0.02
FINE_GAP = 1.0                         # mm, adjacent pads closer than this ...
FINE_PITCH = 1.3                       # mm, ... at a pitch up to this (SOIC 1.27, SOT-23, LGA / USB-C 0.5)
EDGE_INSET, EDGE_STEP = 1.5, 0.5       # mm


def P(v):
    return (mm(v.x) - OX, mm(v.y) - OY)


def r3(p):
    return [round(p[0], 3), round(p[1], 3)]


def ipc_amps(w, dT, k):
    a = (w / 0.0254) * (CU_T / 0.0254)
    return k * dT ** 0.44 * a ** 0.725


def ipc_rise(w, I, k):
    a = (w / 0.0254) * (CU_T / 0.0254)
    return (I / (k * a ** 0.725)) ** (1 / 0.44)


def d_pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def _ccw(a, b, c):
    return (c[1] - a[1]) * (b[0] - a[0]) - (b[1] - a[1]) * (c[0] - a[0])


def d_seg_seg(a, b, c, d):
    if ((_ccw(c, d, a) > 0) != (_ccw(c, d, b) > 0)) and ((_ccw(a, b, c) > 0) != (_ccw(a, b, d) > 0)):
        return 0.0
    return min(d_pt_seg(a, c, d), d_pt_seg(b, c, d), d_pt_seg(c, a, b), d_pt_seg(d, a, b))


def in_poly(p, poly):
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def d_seg_poly(a, b, poly):
    if in_poly(a, poly) or in_poly(b, poly):
        return 0.0
    return min(d_seg_seg(a, b, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly)))


def d_poly_poly(p, q):
    if in_poly(p[0], q) or in_poly(q[0], p):
        return 0.0
    return min(d_seg_poly(p[i], p[(i + 1) % len(p)], q) for i in range(len(p)))


def polys_of(s):
    out = []
    for i in range(s.OutlineCount()):
        o = s.Outline(i)
        out.append([(mm(o.CPoint(k).x) - OX, mm(o.CPoint(k).y) - OY) for k in range(o.PointCount())])
    return out


def bbox(g):
    if g[0] == "seg":
        r = g[3]
        return (min(g[1][0], g[2][0]) - r, min(g[1][1], g[2][1]) - r, max(g[1][0], g[2][0]) + r, max(g[1][1], g[2][1]) + r)
    if g[0] == "circ":
        return (g[1][0] - g[2], g[1][1] - g[2], g[1][0] + g[2], g[1][1] + g[2])
    xs = [p[0] for p in g[1]]
    ys = [p[1] for p in g[1]]
    return (min(xs), min(ys), max(xs), max(ys))


def gap(ga, gc):
    """edge-to-edge distance of two copper shapes ('seg', a, b, r) / ('circ', c, r) / ('poly', pts)"""
    if ga[0] == "seg" and gc[0] == "seg":
        return d_seg_seg(ga[1], ga[2], gc[1], gc[2]) - ga[3] - gc[3]
    if ga[0] == "seg" and gc[0] == "circ":
        return d_pt_seg(gc[1], ga[1], ga[2]) - ga[3] - gc[2]
    if ga[0] == "circ" and gc[0] == "circ":
        return math.hypot(ga[1][0] - gc[1][0], ga[1][1] - gc[1][1]) - ga[2] - gc[2]
    if ga[0] == "poly" and gc[0] == "seg":
        return d_seg_poly(gc[1], gc[2], ga[1]) - gc[3]
    if ga[0] == "poly" and gc[0] == "circ":
        if in_poly(gc[1], ga[1]):
            return -gc[2]
        p = ga[1]
        return min(d_pt_seg(gc[1], p[i], p[(i + 1) % len(p)]) for i in range(len(p))) - gc[2]
    if ga[0] == "poly" and gc[0] == "poly":
        return d_poly_poly(ga[1], gc[1])
    return gap(gc, ga)


class Grid:
    """bbox buckets for neighbour queries"""

    def __init__(self, items, cell=2.0):
        self.cell = cell
        self.items = items
        self.g = defaultdict(list)
        for i, it in enumerate(items):
            x0, y0, x1, y1 = it["bb"]
            for gx in range(int(math.floor(x0 / cell)), int(math.floor(x1 / cell)) + 1):
                for gy in range(int(math.floor(y0 / cell)), int(math.floor(y1 / cell)) + 1):
                    self.g[(gx, gy)].append(i)

    def near(self, bb, grow):
        out = set()
        for gx in range(int(math.floor((bb[0] - grow) / self.cell)), int(math.floor((bb[2] + grow) / self.cell)) + 1):
            for gy in range(int(math.floor((bb[1] - grow) / self.cell)), int(math.floor((bb[3] + grow) / self.cell)) + 1):
                out.update(self.g.get((gx, gy), ()))
        return out


def copper_items(b):
    """every copper item per outer/inner layer: tracks, via lands, pads (no zones)"""
    items = []
    for t in b.GetTracks():
        if t.GetClass() == "PCB_TRACK":
            g = ("seg", P(t.GetStart()), P(t.GetEnd()), mm(t.GetWidth()) / 2)
            items.append(dict(kind="track", net=t.GetNetname(), layer=t.GetLayer(), g=g, owner=None, bb=bbox(g)))
        elif t.GetClass() == "PCB_VIA":
            for l in (F, B):
                g = ("circ", P(t.GetPosition()), mm(t.GetWidth(l)) / 2)
                items.append(dict(kind="via", net=t.GetNetname(), layer=l, g=g, owner=None, bb=bbox(g)))
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for l in (F, B):
                if not p.IsOnLayer(l) or not p.IsOnCopperLayer():
                    continue
                for poly in polys_of(p.GetEffectivePolygon(l, pcbnew.ERROR_INSIDE)):
                    if len(poly) >= 3:
                        g = ("poly", poly)
                        items.append(dict(kind="pad", net=p.GetNetname(), layer=l, g=g, bb=bbox(g),
                                          owner="%s.%s" % (fp.GetReference(), p.GetNumber()), pad=p))
    return items


def track_geometry(b):
    """Off-angle straight segments and acute junctions of the routed copper (zones excluded)."""
    off = []
    arms = defaultdict(list)
    segs = defaultdict(list)
    for t in b.GetTracks():
        if t.GetClass() not in ("PCB_TRACK", "PCB_ARC"):
            continue
        net, lay = t.GetNetname(), b.GetLayerName(t.GetLayer())
        a, c = P(t.GetStart()), P(t.GetEnd())
        L = mm(t.GetLength())
        if t.GetClass() == "PCB_TRACK":
            d = (c[0] - a[0], c[1] - a[1])
            n = math.hypot(*d)
            if n < 1e-6:
                continue
            ang = math.degrees(math.atan2(d[1], d[0])) % 45.0
            dev = min(ang, 45.0 - ang)
            if dev > OFF_ANGLE_DEG and L > OFF_ANGLE_MIN_LEN:
                off.append(dict(net=net, layer=lay, a=r3(a), c=r3(c), length=round(L, 3), off_deg=round(dev, 1)))
            u = (d[0] / n, d[1] / n)
            arms[(net, lay, round(a[0] * 1000), round(a[1] * 1000))].append((u, L))
            arms[(net, lay, round(c[0] * 1000), round(c[1] * 1000))].append(((-u[0], -u[1]), L))
            segs[(net, lay)].append((a, c))
        else:
            o, m = P(t.GetCenter()), P(t.GetMid())
            for e in (a, c):
                r = (e[0] - o[0], e[1] - o[1])
                tg = (-r[1], r[0])
                if tg[0] * (m[0] - e[0]) + tg[1] * (m[1] - e[1]) < 0:
                    tg = (r[1], -r[0])
                n = math.hypot(*tg)
                arms[(net, lay, round(e[0] * 1000), round(e[1] * 1000))].append(((tg[0] / n, tg[1] / n), L))
    for k in list(arms):
        net, lay, xu, yu = k
        p = (xu / 1000.0, yu / 1000.0)
        for a, c in segs[(net, lay)]:
            if min(math.hypot(p[0] - a[0], p[1] - a[1]), math.hypot(p[0] - c[0], p[1] - c[1])) < 0.002:
                continue
            if d_pt_seg(p, a, c) < 0.002:
                d = (c[0] - a[0], c[1] - a[1])
                n = math.hypot(*d)
                arms[k].append(((d[0] / n, d[1] / n), math.hypot(c[0] - p[0], c[1] - p[1])))
                arms[k].append(((-d[0] / n, -d[1] / n), math.hypot(a[0] - p[0], a[1] - p[1])))
    pads = defaultdict(list)
    for fp in b.GetFootprints():
        for p in fp.Pads():
            for l in (F, B):
                if p.IsOnLayer(l):
                    pads[(p.GetNetname(), b.GetLayerName(l))].append((p, "%s.%s" % (fp.GetReference(), p.GetNumber())))
    acute = []
    for (net, lay, xu, yu), lst in arms.items():
        if len(lst) < 2:
            continue
        worst = None
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                (u, la), (w, lc) = lst[i], lst[j]
                if min(la, lc) < ARM_MIN_LEN:
                    continue
                ang = math.degrees(math.acos(max(-1.0, min(1.0, u[0] * w[0] + u[1] * w[1]))))
                if ang < ACUTE_DEG and (worst is None or ang < worst):
                    worst = ang
        if worst is None:
            continue
        p = (xu / 1000.0, yu / 1000.0)
        v = pcbnew.VECTOR2I(MM(p[0] + OX), MM(p[1] + OY))
        inpad = next((nm for pd, nm in pads[(net, lay)] if pd.HitTest(v)), None)
        acute.append(dict(net=net, layer=lay, at=r3(p), angle=round(worst, 1), in_pad=inpad))
    off.sort(key=lambda r: (r["net"], r["a"]))
    acute.sort(key=lambda r: r["angle"])
    return dict(off_angle=off, acute=acute)


def main():
    b = pcbnew.LoadBoard(PCB)
    res = {"board": os.path.abspath(PCB)}
    tracks = [t for t in b.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = [t for t in b.GetTracks() if t.GetClass() == "PCB_VIA"]
    fps = {fp.GetReference(): fp for fp in b.GetFootprints()}

    # ---- 1. current capacity --------------------------------------------------------------------
    rows = []
    for net, (I, why) in DESIGN_I.items():
        ts = [t for t in tracks if t.GetNetname() == net]
        if not ts:
            continue
        by_w = defaultdict(float)
        for t in ts:
            by_w[round(mm(t.GetWidth()), 3)] += mm(t.GetLength())
        wmin = min(by_w)
        tmin = [t for t in ts if round(mm(t.GetWidth()), 3) == wmin]
        rows.append(dict(net=net, I=I, basis=why, min_w=wmin, len_at_min=round(by_w[wmin], 2), at=r3(P(tmin[0].GetStart())),
                         layer=b.GetLayerName(tmin[0].GetLayer()), widths={str(k): round(v, 2) for k, v in sorted(by_w.items())},
                         rise_ext=round(ipc_rise(wmin, I, 0.048), 1), rise_int=round(ipc_rise(wmin, I, 0.024), 1),
                         amps10_ext=round(ipc_amps(wmin, 10, 0.048), 2), amps10_int=round(ipc_amps(wmin, 10, 0.024), 2)))
    res["current"] = rows
    feeds = []
    for ref, num, I, why in FEEDS:
        pd = next((p for p in fps[ref].Pads() if p.GetNumber() == num), None)
        ws = []
        for t in tracks:
            if t.GetNetname() != pd.GetNetname():
                continue
            for e in (t.GetStart(), t.GetEnd()):
                if pd.HitTest(e):
                    ws.append(round(mm(t.GetWidth()), 3))
        w = min(ws) if ws else None
        feeds.append(dict(pad="%s.%s" % (ref, num), net=pd.GetNetname(), I=I, basis=why, tracks_at_pad=sorted(ws), min_w=w,
                          rise_ext=round(ipc_rise(w, I, 0.048), 2) if w else None, rise_int=round(ipc_rise(w, I, 0.024), 2) if w else None))
    res["feeds"] = feeds
    neck = defaultdict(list)
    for t in tracks:
        if t.GetNetname() in POWER and t.GetNetname() != "GND" and mm(t.GetWidth()) < D.NETCLASS["Power"][0] - 1e-6:
            neck[t.GetNetname()].append(dict(w=round(mm(t.GetWidth()), 3), a=r3(P(t.GetStart())), c=r3(P(t.GetEnd())),
                                             layer=b.GetLayerName(t.GetLayer()), length=round(mm(t.GetLength()), 2)))
    res["neckdowns"] = neck

    # ---- 2. spacing --------------------------------------------------------------------------------
    items = copper_items(b)
    grid = Grid(items)
    best = {}
    for i, a in enumerate(items):
        for j in grid.near(a["bb"], 0.5):
            if j <= i:
                continue
            c = items[j]
            if c["layer"] != a["layer"] or c["net"] == a["net"]:
                continue
            g = gap(a["g"], c["g"])
            same_fp = a["kind"] == "pad" and c["kind"] == "pad" and a["owner"].split(".")[0] == c["owner"].split(".")[0]
            kind = "terminal-terminal" if same_fp else ("pad-pad" if a["kind"] == c["kind"] == "pad" else "routed")
            k = (b.GetLayerName(a["layer"]), kind)
            if k not in best or g < best[k][0]:
                best[k] = (g, a, c)
    spacing = []
    for (lay, kind), (g, a, c) in sorted(best.items()):
        spacing.append(dict(layer=lay, kind=kind, gap=round(g, 3), a="%s %s %s" % (a["kind"], a["owner"] or "", a["net"]),
                            b="%s %s %s" % (c["kind"], c["owner"] or "", c["net"]), at=r3(a["bb"][:2])))
    res["spacing"] = spacing
    x0, y0, x1, y1 = 0.0, 0.0, D.BOARD_W, D.BOARD_H
    ebest = None
    for it in items:
        bx0, by0, bx1, by1 = it["bb"]
        d = min(bx0 - x0, x1 - bx1, by0 - y0, y1 - by1)
        if it["kind"] == "pad" and it["owner"].startswith("U1."):
            pass
        if ebest is None or d < ebest[0]:
            ebest = (d, it)
    zedge = None
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        for l in (F, B, pcbnew.In1_Cu, pcbnew.In2_Cu):
            if not z.IsOnLayer(l):
                continue
            for poly in polys_of(z.GetFilledPolysList(l)):
                xs = [p[0] for p in poly]
                ys = [p[1] for p in poly]
                d = min(min(xs) - x0, x1 - max(xs), min(ys) - y0, y1 - max(ys))
                if zedge is None or d < zedge[0]:
                    zedge = (d, b.GetLayerName(l))
    res["edge_clearance"] = dict(item=round(ebest[0], 3), what="%s %s %s" % (ebest[1]["kind"], ebest[1]["owner"] or "", ebest[1]["net"]),
                                 at=r3(ebest[1]["bb"][:2]), zone_fill=round(zedge[0], 3) if zedge else None,
                                 zone_layer=zedge[1] if zedge else None)

    # ---- 3. USB ------------------------------------------------------------------------------------
    usb = {}
    for net in ("USB_DP", "USB_DM"):
        ts = [t for t in tracks if t.GetNetname() == net]
        usb[net] = dict(length=round(sum(mm(t.GetLength()) for t in ts), 3), vias=sum(1 for v in vias if v.GetNetname() == net),
                        width=sorted({round(mm(t.GetWidth()), 3) for t in ts}))
    dp = [t for t in tracks if t.GetNetname() == "USB_DP"]
    dm = [t for t in tracks if t.GetNetname() == "USB_DM"]
    coupled, gaps = 0.0, []
    for t in dp:
        a, c = P(t.GetStart()), P(t.GetEnd())
        L = math.hypot(c[0] - a[0], c[1] - a[1])
        n = max(1, int(L / 0.05))
        same = [u for u in dm if u.GetLayer() == t.GetLayer()]
        for k in range(n):
            q = (a[0] + (c[0] - a[0]) * (k + 0.5) / n, a[1] + (c[1] - a[1]) * (k + 0.5) / n)
            d = min((d_pt_seg(q, P(u.GetStart()), P(u.GetEnd())) - mm(u.GetWidth()) / 2 - mm(t.GetWidth()) / 2) for u in same) if same else 99
            gaps.append(d)
            if d <= 0.25:
                coupled += L / n
    usb["coupled_mm_gap_le_0.25"] = round(coupled, 2)
    usb["edge_gap_median"] = round(sorted(gaps)[len(gaps) // 2], 3) if gaps else None
    j7 = fps["J7"]
    u9 = fps["U9"]
    esd = []
    for pd in j7.Pads():
        if pd.GetNetname() in ("USB_DP", "USB_DM"):
            q = min((p for p in u9.Pads() if p.GetNetname() == pd.GetNetname()),
                    key=lambda p: (p.GetPosition() - pd.GetPosition()).EuclideanNorm())
            esd.append(dict(j7=pd.GetNumber(), u9=q.GetNumber(), net=pd.GetNetname(),
                            straight=round((q.GetPosition() - pd.GetPosition()).EuclideanNorm() / 1e6, 2)))
    usb["esd_distance"] = esd
    res["usb"] = usb

    # ---- 4. layer changes and return vias -----------------------------------------------------------
    gv = [P(v.GetPosition()) for v in vias if v.GetNetname() == "GND"]
    ends = defaultdict(list)
    for t in tracks:
        for q in (P(t.GetStart()), P(t.GetEnd())):
            ends[t.GetNetname()].append((q, b.GetLayerName(t.GetLayer())))
    lc = []
    for v in vias:
        n = v.GetNetname()
        if n == "GND":
            continue
        c = P(v.GetPosition())
        rv = mm(v.GetWidth(F)) / 2
        lays = sorted({l for q, l in ends[n] if math.hypot(q[0] - c[0], q[1] - c[1]) < rv})
        dg = min(math.hypot(c[0] - g[0], c[1] - g[1]) for g in gv)
        lc.append(dict(net=n, at=r3(c), layers=lays, gnd_via=round(dg, 2), fast=n in FAST, power=n in POWER))
    lc.sort(key=lambda r: (not r["fast"], -r["gnd_via"]))
    res["layer_changes"] = lc

    # ---- 5. GND vias along the edge ------------------------------------------------------------------
    pts = []
    s = EDGE_INSET
    x = s
    while x <= D.BOARD_W - s + 1e-9:
        pts += [(x, s), (x, D.BOARD_H - s)]
        x += EDGE_STEP
    y = s
    while y <= D.BOARD_H - s + 1e-9:
        pts += [(s, y), (D.BOARD_W - s, y)]
        y += EDGE_STEP
    far = []
    for p in pts:
        d = min(math.hypot(p[0] - g[0], p[1] - g[1]) for g in gv)
        far.append((round(d, 2), r3(p)))
    far.sort(reverse=True)
    res["edge_stitch"] = dict(points=len(pts), max_to_gnd_via=far[0][0], worst=far[:12],
                              over_3mm=sum(1 for d, p in far if d > 3.0))

    # ---- 6. mask webs, rings, vias in pads ------------------------------------------------------------
    webs = []
    for side, cu in ((pcbnew.F_Mask, F), (pcbnew.B_Mask, B)):
        its = []
        for fp in b.GetFootprints():
            for p in fp.Pads():
                if p.IsOnLayer(side) and p.IsOnLayer(cu):
                    exp = mm(p.GetSolderMaskExpansion(cu)) if hasattr(p, "GetSolderMaskExpansion") else 0.0
                    for poly in polys_of(p.GetEffectivePolygon(cu, pcbnew.ERROR_INSIDE)):
                        its.append(("%s.%s" % (fp.GetReference(), p.GetNumber()), poly, bbox(("poly", poly)), exp, p.GetNetname()))
        small = []
        for i in range(len(its)):
            for j in range(i + 1, len(its)):
                a, c = its[i], its[j]
                if a[4] == c[4]:
                    continue                           # same net (merged openings are harmless)
                if a[2][0] > c[2][2] + 0.3 or c[2][0] > a[2][2] + 0.3 or a[2][1] > c[2][3] + 0.3 or c[2][1] > a[2][3] + 0.3:
                    continue
                g = d_poly_poly(a[1], c[1]) - a[3] - c[3]
                if g < 0.2:
                    small.append((round(g, 3), a[0], c[0]))
        small.sort()
        webs.append(dict(side=b.GetLayerName(side), below_0_2=len(small), below_0_1=sum(1 for g in small if g[0] < 0.1),
                         smallest=small[:10]))
    res["mask_webs"] = webs
    rings = []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
                sz, dr = p.GetSize(F), p.GetDrillSize()
                rings.append((round(min(mm(sz.x) - mm(dr.x), mm(sz.y) - mm(dr.y)) / 2, 3), "%s.%s" % (fp.GetReference(), p.GetNumber()),
                              round(mm(dr.x), 2)))
    rings.sort()
    res["pth_ring_min"] = rings[:8]
    vs = defaultdict(int)
    for v in vias:
        vs[(round(mm(v.GetWidth(F)), 3), round(mm(v.GetDrillValue()), 3))] += 1
    res["via_sizes"] = {"%.2f/%.2f (ring %.3f)" % (k[0], k[1], (k[0] - k[1]) / 2): n for k, n in sorted(vs.items())}
    res["via_count"] = len(vias)
    per = defaultdict(int)
    for v in vias:
        per[v.GetNetname()] += 1
    res["vias_per_net"] = dict(sorted(per.items()))
    vip = []
    pads_smd = [(fp, p) for fp in b.GetFootprints() for p in fp.Pads() if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD]
    smd_polys = []
    for fp, p in pads_smd:
        for l in (F, B):
            if p.IsOnLayer(l):
                for poly in polys_of(p.GetEffectivePolygon(l, pcbnew.ERROR_INSIDE)):
                    smd_polys.append((fp, p, poly, bbox(("poly", poly))))
    for v in vias:
        c = P(v.GetPosition())
        r = mm(v.GetDrillValue()) / 2
        for fp, p, poly, pb in smd_polys:
            if c[0] < pb[0] - r or c[0] > pb[2] + r or c[1] < pb[1] - r or c[1] > pb[3] + r:
                continue
            if True:
                if True:
                    if in_poly(c, poly) or min(d_pt_seg(c, poly[i], poly[(i + 1) % len(poly)]) for i in range(len(poly))) < r:
                        vip.append(dict(via=r3(c), net=v.GetNetname(), pad="%s.%s" % (fp.GetReference(), p.GetNumber()),
                                        pad_net=p.GetNetname(), drill=round(2 * r, 2), centre_in_pad=in_poly(c, poly)))
    res["vias_in_pads"] = vip

    # ---- 7. LCSC fields, silk strokes -------------------------------------------------------------------
    miss, fitted = [], 0
    for fp in b.GetFootprints():
        if fp.GetAttributes() & (pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_DNP):
            continue
        if not len(fp.Pads()) or all(p.GetAttribute() == pcbnew.PAD_ATTRIB_NPTH for p in fp.Pads()):
            continue                                       # mounting holes: no part
        fitted += 1
        if not {f.GetName(): f.GetText() for f in fp.GetFields()}.get("LCSC", "").strip():
            miss.append(fp.GetReference())
    res["lcsc"] = dict(fitted=fitted, missing=miss)
    thin = {}
    filled = {}
    for fp in b.GetFootprints():
        for g in fp.GraphicalItems():
            if g.GetClass() != "PCB_SHAPE" or g.GetLayer() != pcbnew.F_SilkS:
                continue
            w = mm(g.GetWidth())
            if g.IsSolidFill() if hasattr(g, "IsSolidFill") else g.IsFilled():
                bb = g.GetBoundingBox()
                filled.setdefault(fp.GetReference(), []).append(round(max(mm(bb.GetWidth()), mm(bb.GetHeight())), 2))
            elif w < 0.15 - 1e-6:
                thin.setdefault(fp.GetReference(), set()).add(round(w, 3))
    res["silk_thin"] = {k: sorted(v) for k, v in sorted(thin.items())}
    res["silk_filled_marks"] = dict(sorted(filled.items()))

    # ---- 8. geometry ------------------------------------------------------------------------------------
    res["geometry"] = geo = track_geometry(b)
    between = []
    for fp in b.GetFootprints():
        pads = [p for p in fp.Pads() if p.GetAttribute() in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_PTH)]
        for l in (F, B):
            pp = []
            for p in pads:
                if p.IsOnLayer(l):
                    for poly in polys_of(p.GetEffectivePolygon(l, pcbnew.ERROR_INSIDE)):
                        pp.append((p, poly))
            for i in range(len(pp)):
                for j in range(i + 1, len(pp)):
                    (p, a), (q, c) = pp[i], pp[j]
                    pitch = (p.GetPosition() - q.GetPosition()).EuclideanNorm() / 1e6
                    if d_poly_poly(a, c) >= FINE_GAP or pitch > FINE_PITCH:
                        continue
                    hull = convex_hull(a + c)
                    hb = bbox(("poly", hull))
                    if any(d_poly_poly(o, hull) < 1e-6 for r_, o in pp if r_.GetNumber() not in (p.GetNumber(), q.GetNumber())
                           and r_.GetNetname() not in (p.GetNetname(), q.GetNetname())):
                        continue                       # another pad lies between them: not adjacent
                    for t in tracks:
                        if t.GetLayer() != l or t.GetNetname() in (p.GetNetname(), q.GetNetname()):
                            continue
                        s0, s1 = P(t.GetStart()), P(t.GetEnd())
                        if max(s0[0], s1[0]) < hb[0] or min(s0[0], s1[0]) > hb[2] or max(s0[1], s1[1]) < hb[1] or min(s0[1], s1[1]) > hb[3]:
                            continue
                        if d_seg_poly(s0, s1, hull) < 1e-6:
                            between.append(dict(fp=fp.GetReference(), pads=[p.GetNumber(), q.GetNumber()], net=t.GetNetname(),
                                                layer=b.GetLayerName(l), at=r3(s0), gap=round(d_poly_poly(a, c), 2)))
    seen = set()
    res["between_pads"] = [r for r in between if not ((r["fp"], tuple(r["pads"]), r["net"]) in seen or seen.add((r["fp"], tuple(r["pads"]), r["net"])))]
    offaxis = []
    for fp, p in pads_smd:
        if p.GetShape() not in (pcbnew.PAD_SHAPE_RECT, pcbnew.PAD_SHAPE_ROUNDRECT):
            continue
        rot = (p.GetOrientationDegrees()) % 90.0
        for t in tracks:
            if t.GetNetname() != p.GetNetname() or not p.IsOnLayer(t.GetLayer()):
                continue
            for e, o in ((t.GetStart(), t.GetEnd()), (t.GetEnd(), t.GetStart())):
                if p.HitTest(e) and not p.HitTest(o):
                    d = (mm(o.x - e.x), mm(o.y - e.y))
                    ang = (math.degrees(math.atan2(d[1], d[0])) - rot) % 90.0
                    dev = min(ang, 90.0 - ang)
                    if dev > 1.0:
                        offaxis.append(dict(pad="%s.%s" % (fp.GetReference(), p.GetNumber()), net=t.GetNetname(),
                                            layer=b.GetLayerName(t.GetLayer()), at=r3(P(e)), off_deg=round(dev, 1)))
    res["off_axis_pad_entries"] = offaxis
    res["teardrops"] = sum(1 for z in b.Zones() if z.IsTeardropArea())
    res["micro_segments"] = sorted([t.GetNetname(), b.GetLayerName(t.GetLayer()), r3(P(t.GetStart())), round(mm(t.GetLength()), 3)]
                                   for t in tracks if mm(t.GetLength()) < 0.1)

    # ---- print ------------------------------------------------------------------------------------------
    print("board:", res["board"])
    print("CURRENT (IPC-2221B formula, 1 oz; 'int' = internal curve, conservative stand-in for the IPC-2152 base chart)")
    for r in rows:
        print("  %-5s %.2f A  min w %.3f mm (%s, %.2f mm of it, at %s)  rise ext %.1f C / int %.1f C;  10 C: ext %.2f A / int %.2f A" % (
            r["net"], r["I"], r["min_w"], r["layer"], r["len_at_min"], tuple(r["at"]), r["rise_ext"], r["rise_int"], r["amps10_ext"], r["amps10_int"]))
    print("FEEDS (narrowest track at the pad):")
    for r in feeds:
        print("  %-6s %-5s %.2f A  w %s  rise ext %s C / int %s C   (%s)" % (r["pad"], r["net"], r["I"], r["min_w"], r["rise_ext"], r["rise_int"], r["basis"]))
    print("NECK-DOWNS (Power-class tracks < 0.6 mm):", {k: "%d seg, %.2f mm, widths %s" % (len(v), sum(x["length"] for x in v), sorted({x["w"] for x in v}))
                                                        for k, v in neck.items()} or "none")
    print("SPACING (smallest different-net gap per layer and kind; IPC-2221B T6-1 0-15 V: B2 0.10, B4 0.05, A6 0.13 mm):")
    for r in spacing:
        print("  %-5s %-17s %.3f  %s / %s  at %s" % (r["layer"], r["kind"], r["gap"], r["a"], r["b"], tuple(r["at"])))
    e = res["edge_clearance"]
    print("EDGE: nearest copper item %.3f mm (%s at %s); zone fill %.3f mm (%s)" % (e["item"], e["what"], tuple(e["at"]), e["zone_fill"] or -1, e["zone_layer"]))
    print("USB:", json.dumps(usb))
    fast = [r for r in lc if r["fast"]]
    print("LAYER CHANGES: %d signal/power vias; fast-net vias %d, nearest GND via > 2.0 mm: %s" % (
        len(lc), len(fast), [(r["net"], tuple(r["at"]), r["gnd_via"]) for r in fast if r["gnd_via"] > 2.0] or "none"))
    print("  fast-net vias:", [(r["net"], tuple(r["at"]), r["gnd_via"]) for r in fast])
    print("  other vias with no GND via within 3 mm:", [(r["net"], tuple(r["at"]), r["gnd_via"]) for r in lc if not r["fast"] and r["gnd_via"] > 3.0] or "none")
    es = res["edge_stitch"]
    print("EDGE STITCH: %d points %.1f mm inside the edge; farthest from a GND via %.2f mm; %d points > 3 mm: %s" % (
        es["points"], EDGE_INSET, es["max_to_gnd_via"], es["over_3mm"], es["worst"][:6]))
    print("MASK WEBS:", json.dumps(webs))
    print("PTH ring min:", rings[:5])
    print("VIAS:", res["via_count"], res["via_sizes"], " per net:", res["vias_per_net"])
    print("VIAS IN SMD PADS: %d" % len(vip), [(r["pad"], r["net"], tuple(r["via"]), "centre in pad" if r["centre_in_pad"] else "drill touches pad") for r in vip])
    print("LCSC: %d fitted parts, missing %s" % (fitted, miss or "none"))
    print("SILK strokes < 0.15 mm (JLCPCB line width) per footprint:", res["silk_thin"])
    print("SILK filled marks (size mm):", res["silk_filled_marks"])
    oa, ac = geo["off_angle"], geo["acute"]
    print("OFF-ANGLE SEGMENTS (> %.0f deg off 0/45/90, > %.2f mm): %d" % (OFF_ANGLE_DEG, OFF_ANGLE_MIN_LEN, len(oa)))
    for r in oa:
        print("  %-10s %-5s %s-%s len %.3f off %.1f deg" % (r["net"], r["layer"], tuple(r["a"]), tuple(r["c"]), r["length"], r["off_deg"]))
    print("ACUTE JUNCTIONS (< 90 deg): %d (%d inside a pad)" % (len(ac), sum(1 for r in ac if r["in_pad"])))
    for r in ac:
        print("  %-10s %-5s %s %.1f deg%s" % (r["net"], r["layer"], tuple(r["at"]), r["angle"], "  in pad " + r["in_pad"] if r["in_pad"] else ""))
    print("TRACKS BETWEEN ADJACENT PADS (< %.1f mm apart) of one footprint: %d" % (FINE_GAP, len(res["between_pads"])))
    for r in res["between_pads"]:
        print("  %s pads %s (gap %.2f) %s %s at %s" % (r["fp"], r["pads"], r["gap"], r["net"], r["layer"], tuple(r["at"])))
    print("OFF-AXIS PAD ENTRIES (track leaves a rectangular SMD pad off its axes): %d" % len(offaxis))
    for r in offaxis:
        print("  %-8s %-8s %-5s %s %.1f deg" % (r["pad"], r["net"], r["layer"], tuple(r["at"]), r["off_deg"]))
    print("TEARDROPS: %d" % res["teardrops"])
    ms = res["micro_segments"]
    print("SEGMENTS < 0.1 mm: %d on %d nets" % (len(ms), len({m[0] for m in ms})))
    if OUT:
        with open(OUT, "w") as f:
            json.dump(res, f, indent=1)
    sys.stdout.flush()
    os._exit(0)


def convex_hull(pts):
    pts = sorted(set((round(x, 6), round(y, 6)) for x, y in pts))
    if len(pts) < 3:
        return pts

    def half(seq):
        h = []
        for p in seq:
            while len(h) >= 2 and _ccw(h[-2], h[-1], p) <= 0:
                h.pop()
            h.append(p)
        return h
    lo, hi = half(pts), half(reversed(pts))
    return lo[:-1] + hi[:-1]


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
