"""Defuse32 CAD helpers: geometry primitives, cut/engrave records, module
placeholder builders and file writers (DXF R12, glTF binary, STL).

Runs inside FreeCAD's Python (freecad.cmd). Units: mm.
Module builders work in the module's own top-view frame (parts.json
convention: x, y from the PCB's bottom-left corner) with absolute case z.
"""
import json
import math
import os
import struct

import FreeCAD as App
import Part

V = App.Vector

# ---------------------------------------------------------------- z stack
# Filled in by configure() from parts.json -> case.panel.
Z = {}


def configure(parts):
    pan = parts["case"]["panel"]
    Z["panel_bot"] = pan["z_from_floor"]          # 122.2
    Z["panel_top"] = pan["z_top"]                 # 125.2
    Z["plate_bot"] = pan["z_top"]                 # plates sit on the panel
    Z["plate_t"] = 3.0
    Z["plate_top"] = pan["z_top"] + 3.0           # 128.2


# ------------------------------------------------------------- primitives
def box(x0, y0, z0, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x0, y0, z0))


def cbox(cx, cy, z0, dx, dy, dz):
    """Box centred on (cx, cy) in xy."""
    return Part.makeBox(dx, dy, dz, V(cx - dx / 2.0, cy - dy / 2.0, z0))


def cyl(cx, cy, z0, d, h):
    return Part.makeCylinder(d / 2.0, h, V(cx, cy, z0), V(0, 0, 1))


def hexprism(cx, cy, z0, af, h):
    r = af / math.sqrt(3.0)
    pts = [V(cx + r * math.cos(math.radians(60 * i)), cy + r * math.sin(math.radians(60 * i)), z0)
           for i in range(6)]
    pts.append(pts[0])
    return Part.Face(Part.makePolygon(pts)).extrude(V(0, 0, h))


def rrect_wire(cx, cy, l, w, r, z=0.0):
    """Rounded rectangle centred on (cx, cy), CCW, 8 edges (4 if r == 0)."""
    x0, x1, y0, y1 = cx - l / 2.0, cx + l / 2.0, cy - w / 2.0, cy + w / 2.0
    if r <= 1e-6:
        return Part.makePolygon([V(x0, y0, z), V(x1, y0, z), V(x1, y1, z), V(x0, y1, z), V(x0, y0, z)])
    r = min(r, l / 2.0 - 1e-3, w / 2.0 - 1e-3)
    zn = V(0, 0, 1)

    def arc(xc, yc, a0, a1):
        return Part.ArcOfCircle(Part.Circle(V(xc, yc, z), zn, r), math.radians(a0), math.radians(a1)).toShape()

    def seg(p, q):
        return Part.LineSegment(V(p[0], p[1], z), V(q[0], q[1], z)).toShape()

    e = [seg((x0 + r, y0), (x1 - r, y0)), arc(x1 - r, y0 + r, -90, 0),
         seg((x1, y0 + r), (x1, y1 - r)), arc(x1 - r, y1 - r, 0, 90),
         seg((x1 - r, y1), (x0 + r, y1)), arc(x0 + r, y1 - r, 90, 180),
         seg((x0, y1 - r), (x0, y0 + r)), arc(x0 + r, y0 + r, 180, 270)]
    return Part.Wire(e)


def rrect_face(cx, cy, l, w, r, z=0.0):
    return Part.Face(rrect_wire(cx, cy, l, w, r, z))


def circle_face(cx, cy, d, z=0.0):
    return Part.Face(Part.Wire(Part.makeCircle(d / 2.0, V(cx, cy, z))))


# ------------------------------------------------------- cut / engrave records
class Cut:
    """Through cut in a plate/panel: kind 'circle' (w = d) or 'rect' (w x h, corner r)."""

    def __init__(self, label, kind, x, y, w, h=None, r=0.0):
        self.label, self.kind, self.x, self.y, self.w = label, kind, x, y, w
        self.h = w if h is None else h
        self.r = r

    def face(self, z=0.0):
        if self.kind == "circle":
            return circle_face(self.x, self.y, self.w, z)
        return rrect_face(self.x, self.y, self.w, self.h, self.r, z)

    def size_str(self):
        if self.kind == "circle":
            return "dia %.2f" % self.w
        s = "%.2f x %.2f" % (self.w, self.h)
        return s + (" R%.1f" % self.r if self.r > 0 else "")

    def moved(self, fn, rot):
        x, y = fn(self.x, self.y)
        w, h = (self.h, self.w) if (self.kind == "rect" and int(round(rot)) % 180 == 90) else (self.w, self.h)
        return Cut(self.label, self.kind, x, y, w, h, self.r)


class Engrave:
    """Pocket from the plate top: kind 'text' (string, size) or 'rect' (w x h, r)."""

    def __init__(self, label, kind, x, y, depth=1.0, text=None, size=None, w=None, h=None, r=0.0,
                 align="left"):
        self.label, self.kind, self.x, self.y, self.depth = label, kind, x, y, depth
        self.text, self.size, self.w, self.h, self.r, self.align = text, size, w, h, r, align
        self._faces = None

    def moved(self, fn, rot):
        x, y = fn(self.x, self.y)
        e = Engrave(self.label, self.kind, x, y, self.depth, self.text, self.size, self.w, self.h, self.r,
                    self.align)
        if self.kind == "rect" and int(round(rot)) % 180 == 90:
            e.w, e.h = self.h, self.w
        return e

    def faces(self, font):
        """List of planar faces at z = 0 in plate-local coords (None if no font)."""
        if self._faces is not None:
            return self._faces
        if self.kind == "rect":
            self._faces = [rrect_face(self.x, self.y, self.w, self.h, self.r)]
            return self._faces
        if not font:
            self._faces = []
            return self._faces
        chars = Part.makeWireString(self.text, font, self.size * 1.4, 0)
        faces = []
        for wires in chars:
            if wires:
                faces.append(Part.makeFace(wires, "Part::FaceMakerBullseye"))
        comp = Part.Compound(faces)
        bb = comp.BoundBox
        k = self.size / bb.YLength if bb.YLength > 0 else 1.0     # self.size = cap height
        comp.scale(k, V(bb.XMin, bb.YMin, 0))
        bb = comp.BoundBox
        if self.align == "center":
            dx, dy = self.x - (bb.XMin + bb.XMax) / 2.0, self.y - (bb.YMin + bb.YMax) / 2.0
        else:  # left: (x, y) = bottom-left of the text box
            dx, dy = self.x - bb.XMin, self.y - bb.YMin
        comp.translate(V(dx, dy, 0))
        self._faces = list(comp.Faces)
        return self._faces

    def bbox_str(self, font):
        fs = self.faces(font)
        if not fs:
            return "skipped (no font)"
        bb = Part.Compound(fs).BoundBox
        return "%.1f x %.1f" % (bb.XLength, bb.YLength)

    def size_str(self, font):
        if self.kind == "rect":
            return "%.1f x %.1f x %.1f deep" % (self.w, self.h, self.depth)
        return "text '%s' cap %.1f, box %s, %.1f deep" % (self.text, self.size, self.bbox_str(font), self.depth)


def screw_clearance(hole_d):
    """Plate clearance hole for a module mounting hole (M2 / M2.5 / M3)."""
    if hole_d <= 2.3:
        return 2.4, "M2"
    if hole_d <= 2.8:
        return 2.9, "M2.5"
    return 3.4, "M3"


STANDOFF_OD = {"M2": 3.5, "M2.5": 4.5, "M3": 5.0}

# ---------------------------------------------------------------- colours
C = {
    "case": "#2C5FA8", "frame": "#3A3A3A", "panel": "#C9A66B", "plate": "#DCDCDC",
    "sled": "#A8834F", "carrier": "#1B7F3B", "pcb_blue": "#1F3F8F", "pcb_black": "#222222",
    "pcb_red": "#B3242B", "pcb_green": "#2E7D32", "perfboard": "#C8A165", "glass": "#0D0D0D",
    "led_disp": "#2A2A2A", "metal": "#B5B5B5", "knob": "#151515", "keypad": "#1C1C1C",
    "key": "#4A4A4A", "header": "#1A1A1A", "pin": "#D4AF37", "brass": "#C9A227",
    "nylon": "#EFEFEF", "ws2812": "#F5F5F5", "buzzer": "#141414", "post_red": "#D32F2F",
    "post_black": "#1A1A1A", "servo": "#2B6CB0", "horn": "#F2F2F2", "bracket": "#7A7A7A",
    "cap": "#F7F7F7", "ir": "#111111", "ldr": "#D2691E", "copper": "#C87533",
    "chip": "#111111", "keyswitch": "#C0C0C0", "usbc": "#202020", "keepout": "#FF5A36",
}


# ---------------------------------------------------------- module builders
# Each builder returns dict(parts=[(suffix, shape, colour, alpha)], cuts=[Cut],
# engr=[Engrave], mount=str, z=pcb_top) in module coords, absolute z.

def _pcb(spec, zt, colour, holes=True):
    w, h, t = spec["pcb"]["w"], spec["pcb"]["h"], spec["pcb"]["t"]
    s = box(0, 0, zt - t, w, h, t)
    if holes and spec.get("holes"):
        s = s.cut([cyl(o["x"], o["y"], zt - t - 1, o["d"], t + 2) for o in spec["holes"]])
    return ("PCB", s, colour, 1.0)


def _standoffs(spec, z0, z1, tag, nylon=False):
    parts, cuts = [], []
    for i, o in enumerate(spec.get("holes", [])):
        d_cl, size = screw_clearance(o["d"])
        cuts.append(Cut("%s %s hole %d" % (tag, size, i + 1), "circle", o["x"], o["y"], d_cl))
        if z1 - z0 > 0.05:
            od = STANDOFF_OD[size]
            s = cyl(o["x"], o["y"], z0, od, z1 - z0).cut(cyl(o["x"], o["y"], z0 - 1, o["d"] * 0.8, z1 - z0 + 2))
            parts.append(("Standoff%d" % (i + 1), s, C["nylon"] if nylon else C["brass"], 1.0))
    return parts, cuts


def _header_block(rows, z_top, depth, pitch=2.54):
    """Pin-header blocks hanging from z_top for header rows in parts.json form."""
    out = []
    for r in rows:
        n = r["n"]
        if r.get("dir", "+y") in ("+y", "-y"):
            x, y0 = r["x"], r["y0"]
            out.append(box(x - pitch / 2, y0 - pitch / 2, z_top - depth, pitch, n * pitch, depth))
        else:
            x0, y = r["x0"], r["y"]
            out.append(box(x0 - pitch / 2, y - pitch / 2, z_top - depth, n * pitch, pitch, depth))
    return out


def b_oled(spec, opt, tag):
    PB = Z["plate_bot"]
    above, gap = spec["height_above_pcb"], opt.get("gap", 0.2)
    zt = PB - above - gap
    t = spec["pcb"]["t"]
    g = spec["glass"]
    parts = [_pcb(spec, zt, C["pcb_blue"]),
             ("Glass", box(g["x"], g["y"], zt, g["w"], g["h"], above), C["glass"], 1.0)]
    for i, hb in enumerate(_header_block(spec["headers"]["rows"], zt - t, spec["height_below_pcb"])):
        parts.append(("Header%d" % (i + 1), hb, C["header"], 1.0))
    so, cuts = _standoffs(spec, zt, PB, tag)
    parts += so
    win, aa = spec["window"], spec["active_area"]
    m, eb = opt.get("window_margin", 0.5), opt.get("window_extra_bottom", 0.0)
    wcx, wcy = win["x"] + win["w"] / 2.0, win["y"] + win["h"] / 2.0
    cuts.insert(0, Cut("%s window" % tag, "rect", wcx, wcy - eb / 2.0, aa["w"] + 2 * m, aa["h"] + 2 * m + eb))
    return dict(parts=parts, cuts=cuts, engr=[], z=zt,
                mount="%d x %s standoffs %.1f long" % (len(spec["holes"]), screw_clearance(spec["holes"][0]["d"])[1],
                                                       PB - zt))


def b_tm1637(spec, opt, tag):
    PB = Z["plate_bot"]
    above, gap = spec["height_above_pcb"], opt.get("gap", 0.2)
    zt = PB - above - gap
    t = spec["pcb"]["t"]
    w = spec["window"]
    parts = [_pcb(spec, zt, C["pcb_blue"]),
             ("Display", box(w["x"], w["y"], zt, w["w"], w["h"], above), C["led_disp"], 1.0)]
    for i, hb in enumerate(_header_block(spec["headers"]["rows"], zt - t, spec["height_below_pcb"])):
        parts.append(("Header%d" % (i + 1), hb, C["header"], 1.0))
    so, cuts = _standoffs(spec, zt, PB, tag)
    parts += so
    cuts.insert(0, Cut("%s window" % tag, "rect", w["x"] + w["w"] / 2.0, w["y"] + w["h"] / 2.0, w["w"], w["h"]))
    return dict(parts=parts, cuts=cuts, engr=[], z=zt, mount="4 x M3 standoffs %.1f long" % (PB - zt))


def b_ky040(spec, opt, tag):
    PB, PT = Z["plate_bot"], Z["plate_top"]
    sh = spec["shaft"]
    body_h = sh["bushing_top_above_pcb"] - sh["bushing_len"]          # encoder body top above PCB
    zt = PB - opt.get("gap", 1.0) - body_h
    sx, sy = sh["x"], sh["y"]
    hdr = spec["headers"]["rows"][0]
    parts = [_pcb(spec, zt, C["pcb_black"]),
             ("Body", cbox(sx, sy, zt, 12.0, 12.0, body_h), C["metal"], 1.0),
             ("Bushing", cyl(sx, sy, zt + body_h, 7.0, sh["bushing_len"]), C["metal"], 1.0),
             ("Shaft", cyl(sx, sy, zt + sh["bushing_top_above_pcb"], sh["d"],
                           sh["tip_above_pcb"] - sh["bushing_top_above_pcb"]), C["metal"], 1.0),
             ("HeaderRA", box(hdr["x"] - 1.27, hdr["y0"] - 1.27, zt, spec["pcb"]["w"] - hdr["x"] + 1.27 + 6.0,
                              hdr["n"] * 2.54, 2.54), C["header"], 1.0),
             ("PinTails", box(hdr["x"] - 1.27, hdr["y0"] - 1.27, zt - spec["pcb"]["t"] - spec["height_below_pcb"],
                              2.54, hdr["n"] * 2.54, spec["height_below_pcb"]), C["pin"], 1.0),
             ("Nut", hexprism(sx, sy, PT, 10.0, 2.0).cut(cyl(sx, sy, PT - 1, 7.0, 4)), C["metal"], 1.0)]
    tip = zt + sh["tip_above_pcb"]
    kb = PT + 2.5
    parts.append(("Knob", cyl(sx, sy, kb, opt.get("knob_d", 15.0), tip + 1.0 - kb), C["knob"], 1.0))
    cuts = [Cut("%s shaft (M7 bushing)" % tag, "circle", sx, sy, spec["panel_hole"]["d"])]
    return dict(parts=parts, cuts=cuts, engr=[], z=zt,
                mount="by its M7 bushing + nut (PCB holes not used: positions unreliable)")


def b_keypad(spec, opt, tag):
    """Hard-key 4x4 keypad mounted ON TOP of the plate (SPEC M3 row).

    Its 61 mm hole pattern is too close to the 60 x 60 key field to mount it
    from below (1.5 mm web), so the frame sits on 4 short spacers on the plate
    top, M3 screws go through frame, spacers and plate at the real hole
    positions, and the plate only gets a slot under the pad tail's header for
    the cable. No key-field cut-out.
    """
    PT = Z["plate_top"]
    w, h = spec["pcb"]["w"], spec["pcb"]["h"]
    sp = opt.get("spacer_h", 3.0)              # spacer height between plate top and frame bottom
    back = opt.get("back_t", 4.0)              # frame back thickness (keys stand above it)
    key_h = spec["pcb"]["t"] - back
    zb = PT + sp                               # frame underside
    win = spec["window"]
    wcx, wcy = win["x"] + win["w"] / 2.0, win["y"] + win["h"] / 2.0
    frame = box(0, 0, zb, w, h, back).cut(
        [cyl(o["x"], o["y"], zb - 1, o["d"], back + 2) for o in spec["holes"]])
    parts = [("Frame", frame, C["keypad"], 1.0)]
    kp = spec["key_pitch"]
    keys = []
    for i in range(4):
        for j in range(4):
            keys.append(cbox(wcx + (i - 1.5) * kp["x"], wcy + (j - 1.5) * kp["y"], zb + back, 11.0, 11.5, key_h))
    parts.append(("Keys", Part.makeCompound(keys), C["key"], 1.0))
    # pad tail (PCB) off the frame's bottom edge, level with the frame underside
    parts.append(("Tail", box(w / 2.0 - 22.0, -4.0, zb, 44.0, 4.0, 1.6), C["pcb_green"], 1.0))
    # header on the tail, pins down; the plugged cable housing passes the plate slot
    r = spec["headers"]["rows"][0]
    pitch, n = spec["headers"]["pitch"], r["n"]
    hx0, hx1 = r["x0"] - pitch / 2.0, r["x0"] + (n - 0.5) * pitch
    plug_below = opt.get("plug_below", 8.0)    # cable housing hanging below the plate underside
    parts.append(("HeaderPlug", box(hx0, r["y"] - pitch / 2.0, Z["plate_bot"] - plug_below, hx1 - hx0, pitch,
                                    zb - Z["plate_bot"] + plug_below), C["header"], 1.0))
    so, cuts = [], []
    for i, o in enumerate(spec["holes"]):
        d_cl, size = screw_clearance(o["d"])
        cuts.append(Cut("%s %s hole %d" % (tag, size, i + 1), "circle", o["x"], o["y"], d_cl))
        od = STANDOFF_OD[size]
        s = cyl(o["x"], o["y"], PT, od, sp).cut(cyl(o["x"], o["y"], PT - 1, d_cl, sp + 2))
        so.append(("Spacer%d" % (i + 1), s, C["nylon"], 1.0))
    parts += so
    slot_w = opt.get("slot_w") or (n * pitch + 2.0)       # header length + 1 mm per side
    slot_h = opt.get("slot_h", 6.0)
    cuts.append(Cut("%s header/cable slot" % tag, "rect", (hx0 + hx1) / 2.0, r["y"], slot_w, slot_h))
    return dict(parts=parts, cuts=cuts, engr=[], z=zb,
                mount="on top of the plate: 4 x M3 x %.0f spacers, M3 screws through frame, spacers and plate "
                      "(61 mm pattern) + nuts below; cable through a %.1f x %.1f slot" % (sp, slot_w, slot_h))


def b_pn532(spec, opt, tag):
    PB = Z["plate_bot"]
    above, gap = spec["height_above_pcb"], opt.get("gap", 0.2)
    zt = PB - above - gap
    t = spec["pcb"]["t"]
    w, h = spec["pcb"]["w"], spec["pcb"]["h"]
    parts = [_pcb(spec, zt, C["pcb_red"]),
             ("Chip", box(14.0, 12.0, zt, 16.0, 16.0, above), C["chip"], 1.0)]
    r = spec["headers"]["rows"][0]
    parts.append(("HeaderI2C", box(r["x"] - 1.27, r["y0"] - 1.27, zt - t - spec["height_below_pcb"], 2.54,
                                   r["n"] * 2.54, spec["height_below_pcb"]), C["header"], 1.0))
    so, cuts = _standoffs(spec, zt, PB, tag, nylon=True)
    parts += so
    engr = [Engrave("%s NFC mark" % tag, "text", w / 2.0, h / 2.0, depth=1.0, text="NFC", size=8.0,
                    align="center")]
    return dict(parts=parts, cuts=cuts, engr=engr, z=zt,
                mount="2 x M3 NYLON standoffs %.1f long (no metal over the antenna)" % (PB - zt))


def b_ws2812(spec, opt, tag):
    PB = Z["plate_bot"]
    led_t = spec["pcb"]["t"]
    d_brk = opt.get("breakout_d", 10.0)
    parts = [("LED", cbox(0, 0, PB - led_t, 5.0, 5.0, led_t), C["ws2812"], 1.0),
             ("Breakout", cyl(0, 0, PB - led_t - 1.6, d_brk, 1.6), C["pcb_black"], 1.0)]
    cuts = [Cut("%s light hole" % tag, "circle", 0, 0, opt.get("hole_d", 5.0))]
    return dict(parts=parts, cuts=cuts, engr=[], z=PB - led_t,
                mount="round %.0f mm WS2812 breakout, LED face against the plate (hot glue / printed clip)" % d_brk)


def b_buzzer(spec, opt, tag):
    PB = Z["plate_bot"]
    d, hgt = spec["pcb"]["w"], spec["pcb"]["t"]
    parts = [("Body", cyl(0, 0, PB - hgt, d, hgt), C["buzzer"], 1.0),
             ("Pins", Part.makeCompound([cyl(-spec["pins"]["pitch"] / 2, 0, PB - hgt - spec["height_below_pcb"], 0.6,
                                             spec["height_below_pcb"]),
                                         cyl(spec["pins"]["pitch"] / 2, 0, PB - hgt - spec["height_below_pcb"], 0.6,
                                             spec["height_below_pcb"])]), C["pin"], 1.0)]
    cd = spec["panel_hole"]["d"]
    sd, sp = opt.get("side_hole_d", 2.0), opt.get("side_hole_x", 5.6)
    cuts = [Cut("%s sound hole" % tag, "circle", 0, 0, cd),
            Cut("%s sound hole L" % tag, "circle", -sp, 0, sd),
            Cut("%s sound hole R" % tag, "circle", sp, 0, sd)]
    return dict(parts=parts, cuts=cuts, engr=[], z=PB, mount="glued / printed clip against the plate underside")


def b_banana(spec, opt, tag):
    PB, PT = Z["plate_bot"], Z["plate_top"]
    col = opt.get("colour", C["post_red"])
    parts = [("Cap", cyl(0, 0, PT, spec["pcb"]["w"], spec["height_above_pcb"]), col, 1.0),
             ("Stud", cyl(0, 0, PB - spec["height_below_pcb"], 6.0, spec["height_below_pcb"] + Z["plate_t"]),
              C["brass"], 1.0),
             ("Nut", hexprism(0, 0, PB - 3.0, 10.0, 3.0).cut(cyl(0, 0, PB - 4, 6.0, 5)), C["brass"], 1.0)]
    cuts = [Cut("%s post" % tag, "circle", 0, 0, spec["panel_hole"]["d"])]
    return dict(parts=parts, cuts=cuts, engr=[], z=PB, mount="panel nut")


def b_ldr(spec, opt, tag):
    PT = Z["plate_top"]
    t = spec["pcb"]["t"]
    z0 = PT - 0.3 - t
    p = spec["pins"]["pitch"]
    parts = [("Body", cyl(0, 0, z0, spec["pcb"]["w"], t), C["ldr"], 1.0),
             ("Leads", Part.makeCompound([cyl(-p / 2, 0, z0 - 20.0, 0.5, 20.0), cyl(p / 2, 0, z0 - 20.0, 0.5, 20.0)]),
              C["metal"], 1.0)]
    cuts = [Cut("%s hole" % tag, "circle", 0, 0, spec["panel_hole"]["d"])]
    return dict(parts=parts, cuts=cuts, engr=[], z=z0, mount="press fit in the plate hole, face up")


def b_ir(spec, opt, tag):
    PB = Z["plate_bot"]
    w, h, t = spec["pcb"]["w"], spec["pcb"]["h"], spec["pcb"]["t"]
    parts = [("Body", box(0, 0, PB - t, w, h, t), C["ir"], 1.0),
             ("Leads", Part.makeCompound([cyl(x, 1.0, PB - t - 15.0, 0.5, 15.0) for x in spec["pins"]["x"]]),
              C["metal"], 1.0)]
    ww, wh = opt.get("window", (6.5, 7.5))
    cuts = [Cut("%s window" % tag, "rect", w / 2.0, h / 2.0, ww, wh)]
    return dict(parts=parts, cuts=cuts, engr=[], z=PB, mount="lens up behind the window (hot glue / printed clip)")


def b_simon(spec, opt, tag, tact):
    """Perfboard (assumed, see layout.EXTRA) with 2x2 12 mm tact switches + WS2812 beside each."""
    PB = Z["plate_bot"]
    bw, bh, bt = spec["w"], spec["h"], spec["t"]
    pitch = opt.get("pitch", 22.0)
    cap_top = Z["plate_top"] + opt.get("cap_proud", 3.0)
    cap_above = opt.get("cap_above_pcb", 12.0)
    zt = cap_top - cap_above
    parts = [("Board", box(0, 0, zt - bt, bw, bh, bt).cut(
        [cyl(x, y, zt - bt - 1, spec["hole_d"], bt + 2) for x, y in spec["holes"]]), C["pcb_green"], 1.0)]
    sw, caps, leds, cuts = [], [], [], []
    for i, (ix, iy) in enumerate([(-0.5, 0.5), (0.5, 0.5), (-0.5, -0.5), (0.5, -0.5)]):
        x, y = bw / 2.0 + ix * pitch, bh / 2.0 + iy * pitch
        sw.append(cbox(x, y, zt, tact["pcb"]["w"], tact["pcb"]["h"], tact["pcb"]["t"]))
        sw.append(cyl(x, y, zt + tact["pcb"]["t"], tact["actuator"]["stem_square"], tact["height_above_pcb"] - tact["pcb"]["t"]))
        caps.append(cyl(x, y, zt + 5.0, opt.get("cap_d", 11.6), cap_above - 5.0))
        leds.append(cbox(x + 9.0, y, zt, 5.0, 5.0, 1.6))
        cuts.append(Cut("%s button %d cap" % (tag, i + 1), "circle", x, y, opt.get("cap_hole_d", 12.5)))
    parts += [("Switches", Part.makeCompound(sw), C["header"], 1.0),
              ("Caps", Part.makeCompound(caps), C["cap"], 0.6),
              ("LEDs", Part.makeCompound(leds), C["ws2812"], 1.0)]
    for i, (x, y) in enumerate(spec["holes"]):
        cuts.append(Cut("%s M3 hole %d" % (tag, i + 1), "circle", x, y, 3.4))
        s = cyl(x, y, zt, 5.0, PB - zt).cut(cyl(x, y, zt - 1, 2.5, PB - zt + 2))
        parts.append(("Standoff%d" % (i + 1), s, C["brass"], 1.0))
    return dict(parts=parts, cuts=cuts, engr=[], z=zt, mount="4 x M3 standoffs %.1f long" % (PB - zt))


def b_probe(spec, opt, tag, hdr, dip, soic):
    """Probe perfboard (assumed) flush under the plate with headers, DIP-8 socket,
    SOIC-8 breakout and test-point loops. opt lists their positions in board coords."""
    PB = Z["plate_bot"]
    bw, bh, bt = spec["w"], spec["h"], spec["t"]
    pl = hdr["pcb"]["t"]  # header plastic 2.5
    pin_up = hdr["height_above_pcb"] - pl
    parts = [("Board", box(0, 0, PB - bt, bw, bh, bt).cut(
        [cyl(x, y, PB - bt - 1, spec["hole_d"], bt + 2) for x, y in spec["holes"]]), C["perfboard"], 1.0)]
    cuts = []
    plast, pins = [], []
    for name, (x, y, n) in opt["headers"].items():
        L = n * 2.54
        plast.append(cbox(x, y, PB, L, 2.54, pl))
        for k in range(n):
            px = x - L / 2.0 + 1.27 + k * 2.54
            pins.append(cbox(px, y, PB + pl, 0.64, 0.64, pin_up))
            pins.append(cbox(px, y, PB - bt - 3.0, 0.64, 0.64, 3.0))
        cuts.append(Cut("%s %s %d-pin header slot" % (tag, name, n), "rect", x, y, L + 0.6, 2.54 + 0.6))
    parts += [("HeaderPlastic", Part.makeCompound(plast), C["header"], 1.0),
              ("HeaderPins", Part.makeCompound(pins), C["pin"], 1.0)]
    m = opt.get("window_margin", 2.0)
    # DIP-8 socket + EEPROM
    x, y = opt["dip"]
    parts.append(("DIP8Socket", cbox(x, y, PB, dip["pcb"]["w"], dip["pcb"]["h"], dip["pcb"]["t"]), C["header"], 1.0))
    parts.append(("EEPROM", cbox(x, y, PB + dip["pcb"]["t"], 6.35, 9.8, 3.3), C["chip"], 1.0))
    cuts.append(Cut("%s DIP-8 socket window" % tag, "rect", x, y, dip["pcb"]["w"] + 2 * m, dip["pcb"]["h"] + 2 * m))
    # SOIC-8 breakout on 2 x 4 headers
    x, y = opt["soic"]
    sw, sh, st = soic["pcb"]["w"], soic["pcb"]["h"], soic["pcb"]["t"]
    rs = soic["pins"]["row_spacing"]
    parts.append(("SOICHeaders", Part.makeCompound([cbox(x - rs / 2.0, y, PB, 2.54, 4 * 2.54, pl),
                                                    cbox(x + rs / 2.0, y, PB, 2.54, 4 * 2.54, pl)]), C["header"], 1.0))
    parts.append(("SOICBreakout", cbox(x, y, PB + pl, sw, sh, st), C["pcb_blue"], 1.0))
    parts.append(("W25Q32", cbox(x, y, PB + pl + st, 5.0, 4.0, 1.75), C["chip"], 1.0))
    cuts.append(Cut("%s SOIC-8 breakout window" % tag, "rect", x, y, sw + 2 * m, sh + 2 * m))
    # test-point loops
    loops = []
    for i, (x, y) in enumerate(opt["test_points"]):
        loops.append(cbox(x, y, PB, 4.0, 1.0, opt.get("tp_h", 9.0)))
        cuts.append(Cut("%s test point %d" % (tag, i + 1), "circle", x, y, opt.get("tp_hole_d", 5.0)))
    parts.append(("TestLoops", Part.makeCompound(loops), C["metal"], 1.0))
    for i, (x, y) in enumerate(spec["holes"]):
        cuts.append(Cut("%s M3 hole %d" % (tag, i + 1), "circle", x, y, 3.4))
    return dict(parts=parts, cuts=cuts, engr=[], z=PB,
                mount="perfboard screwed flat under the plate (4 x M3 + nuts, no spacer)")


def b_touchpad(opt, tag):
    PT = Z["plate_top"]
    s, depth = opt.get("size", 18.0), opt.get("depth", 1.0)
    parts = [("Copper", cbox(0, 0, PT - depth, s - 0.4, s - 0.4, 0.2), C["copper"], 1.0)]
    cuts = [Cut("%s wire hole" % tag, "circle", 0, 0, opt.get("wire_hole_d", 2.0))]
    engr = [Engrave("%s recess" % tag, "rect", 0, 0, depth=depth, w=s, h=s)]
    return dict(parts=parts, cuts=cuts, engr=engr, z=PT - depth, mount="copper tape in a 1 mm recess, wire through")


def b_sg90(spec, opt, tag):
    """SG90 on a printed L-bracket under the plate, shaft horizontal along -y; the
    single-arm horn swings up through a slot in the plate (prize-hatch latch).
    Module coords: origin = shaft axis position in plate-local xy before placement
    (the builder places everything relative to (0, 0)); z absolute."""
    PB = Z["plate_bot"]
    leg_t = opt.get("leg_t", 3.0)
    flw, flh, flt = spec["pcb"]["w"], spec["pcb"]["h"], spec["pcb"]["t"]
    b = spec["body"]
    sx, sy = spec["shaft"]["x"], spec["shaft"]["y"]
    zc = PB - leg_t - flh / 2.0 - opt.get("gap", 0.5)        # shaft axis height
    arm_r, arm_w, arm_t = opt.get("arm_r", 20.0), opt.get("arm_w", 5.0), 1.5
    # servo in its own frame: x along flange, y across, z up (flange underside at z = 0)
    above_body = 11.0
    sv = [box(0, 0, 0, flw, flh, flt).cut([cyl(o["x"], o["y"], -1, o["d"], flt + 2) for o in spec["holes"]]),
          box(b["x"], b["y"], -b["below_flange"], b["w"], b["h"], b["below_flange"]),
          box(b["x"], b["y"], flt, b["w"], b["h"], above_body - flt),
          cyl(sx, sy, above_body, b["h"], 2.0),
          cyl(sx, sy, above_body + 2.0, 4.8, spec["height_above_pcb"] - above_body - 2.0)]
    horn = [cyl(sx, sy, 12.0, 7.0, 4.0),
            box(sx - arm_w / 2.0, sy, 14.5, arm_w, arm_r, arm_t)]          # arm along +y (-> world +z)

    def place(s):
        s = s.copy()
        s.translate(V(-sx, -sy, 0))
        s.rotate(V(0, 0, 0), V(1, 0, 0), 90)     # module +z -> world -y, module +y -> world +z
        s.translate(V(0, opt.get("y_flange", 0.0), zc))
        return s

    yf = opt.get("y_flange", 0.0)               # world y of the flange underside (local)
    parts = [("Servo", place(Part.makeCompound(sv)), C["servo"], 0.85),
             ("Horn", place(Part.makeCompound(horn)), C["horn"], 1.0)]
    # bracket: upright against the flange underside (body side, +y), top leg under the plate
    x0, x1 = -sx - 4.0, flw - sx + 4.0
    up_z0 = zc - flh / 2.0 - 4.0
    upright = box(x0, yf, up_z0, x1 - x0, 3.0, PB - leg_t - up_z0)
    bodycut = box(b["x"] - sx - 0.2, yf - 1, zc - b["h"] / 2.0 - 0.2, b["w"] + 0.4, 5.0, b["h"] + 0.4)
    ear = [Part.makeCylinder(o["d"] / 2.0, 5.0, V(o["x"] - sx, yf - 1, zc), V(0, 1, 0)) for o in spec["holes"]]
    leg_len = opt.get("leg_len", 16.0)
    leg = box(x0, yf, PB - leg_t, x1 - x0, leg_len, leg_t)
    holes_xy = [(x0 + 5.0, yf + leg_len - 5.0), (x1 - 5.0, yf + leg_len - 5.0)]
    br = upright.fuse(leg).cut([bodycut] + ear + [cyl(x, y, PB - leg_t - 1, 3.0, leg_t + 2) for x, y in holes_xy])
    parts.append(("Bracket", br.removeSplitter(), C["bracket"], 1.0))
    # slot for the arm: arm plane y in [yf-16, yf-14.5]
    y_arm = yf - 16.0 + arm_t / 2.0
    sl_w, x_lo, x_hi = opt.get("slot_w", 6.0), -arm_w / 2.0 - 1.0, math.sqrt(arm_r ** 2 - (PB - zc) ** 2) + arm_w / 2.0 + 0.5
    cuts = [Cut("%s latch slot" % tag, "rect", (x_lo + x_hi) / 2.0, y_arm, x_hi - x_lo, sl_w)]
    for i, (x, y) in enumerate(holes_xy):
        cuts.append(Cut("%s bracket M3 hole %d" % (tag, i + 1), "circle", x, y, 3.4))
    return dict(parts=parts, cuts=cuts, engr=[], z=zc,
                mount="printed L-bracket (2 x M3 to the plate), servo ears M2 into the bracket; horn shown latched (up)")


# ----------------------------------------------------------------- writers
def _dxf_edges(edges, layer, out, tol=0.02):
    for e in edges:
        c = e.Curve
        if isinstance(c, Part.Line) or c.__class__.__name__ in ("Line", "LineSegment"):
            p, q = e.Vertexes[0].Point, e.Vertexes[-1].Point
            out.append(("LINE", layer, (p.x, p.y, q.x, q.y)))
        elif isinstance(c, Part.Circle):
            cen, r = c.Center, c.Radius
            if e.isClosed():
                out.append(("CIRCLE", layer, (cen.x, cen.y, r)))
            else:
                p0, p1 = e.valueAt(e.FirstParameter), e.valueAt(e.LastParameter)
                a0 = math.degrees(math.atan2(p0.y - cen.y, p0.x - cen.x))
                a1 = math.degrees(math.atan2(p1.y - cen.y, p1.x - cen.x))
                if c.Axis.z < 0:
                    a0, a1 = a1, a0
                out.append(("ARC", layer, (cen.x, cen.y, r, a0 % 360.0, a1 % 360.0)))
        else:
            pts = e.discretize(Deflection=tol)
            for p, q in zip(pts[:-1], pts[1:]):
                out.append(("LINE", layer, (p.x, p.y, q.x, q.y)))


def write_dxf(path, layer_edges, dx=0.0, dy=0.0):
    """Minimal AutoCAD R12 DXF (LINE/CIRCLE/ARC), mm, shifted by (dx, dy).
    layer_edges: list of (layer, colour_index, [edges])."""
    ents = []
    for layer, _, edges in layer_edges:
        moved = []
        for e in edges:
            e2 = e.copy()
            e2.translate(V(dx, dy, 0))
            moved.append(e2)
        _dxf_edges(moved, layer, ents)
    L = ["0", "SECTION", "2", "HEADER", "9", "$ACADVER", "1", "AC1009", "9", "$INSUNITS", "70", "4",
         "0", "ENDSEC", "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", str(len(layer_edges))]
    for layer, col, _ in layer_edges:
        L += ["0", "LAYER", "2", layer, "70", "0", "62", str(col), "6", "CONTINUOUS"]
    L += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    f = lambda v: "%.4f" % v
    for kind, layer, d in ents:
        if kind == "LINE":
            L += ["0", "LINE", "8", layer, "10", f(d[0]), "20", f(d[1]), "30", "0.0", "11", f(d[2]), "21", f(d[3]),
                  "31", "0.0"]
        elif kind == "CIRCLE":
            L += ["0", "CIRCLE", "8", layer, "10", f(d[0]), "20", f(d[1]), "30", "0.0", "40", f(d[2])]
        else:
            L += ["0", "ARC", "8", layer, "10", f(d[0]), "20", f(d[1]), "30", "0.0", "40", f(d[2]), "50", f(d[3]),
                  "51", f(d[4])]
    L += ["0", "ENDSEC", "0", "EOF"]
    with open(path, "w") as fh:
        fh.write("\n".join(L) + "\n")
    return len(ents)


def write_stl(path, shape, lin=0.05, ang=0.25):
    import MeshPart
    m = MeshPart.meshFromShape(Shape=shape, LinearDeflection=lin, AngularDeflection=ang, Relative=False)
    m.write(path)
    return m.CountFacets


def _srgb_to_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def write_glb(path, items, tol=0.2):
    """Binary glTF 2.0. items: list of dict(name, shape, colour '#RRGGBB', alpha, group).
    Converts case coords (mm, z up) to glTF (metres, y up): (x, y, z) -> (x, z, -y) / 1000.
    One mesh per item, smooth normals within each B-rep face, double-sided materials."""
    buf = bytearray()
    views, accs, meshes, nodes, mats, matidx = [], [], [], [], [], {}
    groups = {}

    def add_view(data, target):
        while len(buf) % 4:
            buf.append(0)
        off = len(buf)
        buf.extend(data)
        views.append({"buffer": 0, "byteOffset": off, "byteLength": len(data), "target": target})
        return len(views) - 1

    ntri_total = 0
    for it in items:
        pos, nrm, idx = [], [], []
        tl = it.get("tol", tol)
        for face in it["shape"].Faces:
            try:
                pts, tris = face.tessellate(tl)
            except Exception:
                continue
            if not tris:
                continue
            base = len(pos)
            acc = [[0.0, 0.0, 0.0] for _ in pts]
            for (i, j, k) in tris:
                a, b, c = pts[i], pts[j], pts[k]
                n = (b - a).cross(c - a)
                for q in (i, j, k):
                    acc[q][0] += n.x
                    acc[q][1] += n.y
                    acc[q][2] += n.z
                idx.extend((base + i, base + j, base + k))
            for p, n in zip(pts, acc):
                L = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
                pos.append((p.x / 1000.0, p.z / 1000.0, -p.y / 1000.0))
                nrm.append((n[0] / L, n[2] / L, -n[1] / L))
        if not idx:
            continue
        ntri_total += len(idx) // 3
        pb = struct.pack("<%df" % (3 * len(pos)), *[v for p in pos for v in p])
        nb = struct.pack("<%df" % (3 * len(nrm)), *[v for p in nrm for v in p])
        ib = struct.pack("<%dI" % len(idx), *idx)
        mn = [min(p[k] for p in pos) for k in range(3)]
        mx = [max(p[k] for p in pos) for k in range(3)]
        vp = add_view(pb, 34962)
        accs.append({"bufferView": vp, "componentType": 5126, "count": len(pos), "type": "VEC3", "min": mn, "max": mx})
        ap = len(accs) - 1
        vn = add_view(nb, 34962)
        accs.append({"bufferView": vn, "componentType": 5126, "count": len(nrm), "type": "VEC3"})
        an = len(accs) - 1
        vi = add_view(ib, 34963)
        accs.append({"bufferView": vi, "componentType": 5125, "count": len(idx), "type": "SCALAR"})
        ai = len(accs) - 1
        key = (it["colour"], round(it.get("alpha", 1.0), 3))
        if key not in matidx:
            r, g, b = hex_rgb(it["colour"])
            a = it.get("alpha", 1.0)
            m = {"name": "%s_%d" % (it["colour"].lstrip("#"), int(a * 100)),
                 "pbrMetallicRoughness": {"baseColorFactor": [_srgb_to_lin(r), _srgb_to_lin(g), _srgb_to_lin(b), a],
                                          "metallicFactor": 0.0, "roughnessFactor": 0.65},
                 "doubleSided": True}
            if a < 0.999:
                m["alphaMode"] = "BLEND"
            mats.append(m)
            matidx[key] = len(mats) - 1
        meshes.append({"name": it["name"], "primitives": [{"attributes": {"POSITION": ap, "NORMAL": an},
                                                             "indices": ai, "material": matidx[key]}]})
        nodes.append({"name": it["name"], "mesh": len(meshes) - 1,
                      "extras": {"colour": it["colour"], "alpha": it.get("alpha", 1.0), "group": it.get("group", "")}})
        groups.setdefault(it.get("group", "Misc"), []).append(len(nodes) - 1)
    roots = []
    for g, kids in groups.items():
        nodes.append({"name": g, "children": kids})
        roots.append(len(nodes) - 1)
    while len(buf) % 4:
        buf.append(0)
    gltf = {"asset": {"version": "2.0", "generator": "Defuse32 cad/build.py (FreeCAD %s)" % ".".join(App.Version()[:3])},
            "scene": 0, "scenes": [{"name": "Defuse32", "nodes": roots}], "nodes": nodes, "meshes": meshes,
            "materials": mats, "accessors": accs, "bufferViews": views, "buffers": [{"byteLength": len(buf)}],
            "extras": {"units": "metres", "up": "+Y", "source_frame": "case mm, z up; gltf = (x, z, -y)/1000"}}
    js = json.dumps(gltf, separators=(",", ":")).encode("utf-8")
    while len(js) % 4:
        js += b" "
    total = 12 + 8 + len(js) + 8 + len(buf)
    with open(path, "wb") as fh:
        fh.write(struct.pack("<III", 0x46546C67, 2, total))
        fh.write(struct.pack("<II", len(js), 0x4E4F534A))
        fh.write(js)
        fh.write(struct.pack("<II", len(buf), 0x004E4942))
        fh.write(bytes(buf))
    return len(meshes), ntri_total
