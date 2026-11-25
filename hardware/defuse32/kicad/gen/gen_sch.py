#!/usr/bin/env python3
"""Generate the rev 2.1 schematic from design.py: defuse32-carrier.kicad_sch (root: sheet symbols
and notes) plus one A3 sub-sheet per function block (design.SHEETS).

Every connected pin gets a 2.54 mm wire stub ending in a power symbol (VBUS / 5V / 3V3 / 3V3P /
GND) or a global label (net name); no-connect flags on NC pins. Global labels and power symbols
connect across sheets. Stacked pins (hidden duplicates at the same spot) share one stub.
Each symbol carries the JLCPCB fields LCSC, MPN, Manufacturer and JLC (Basic/Extended).

Run:  python3 kicad/gen/gen_sch.py
"""
import math
import os
import uuid

import design as D
from sexp import Sym as S, dump, find
from symlib import flat, pins as lib_pins, prop as lib_prop

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(HERE, ".."))
PROJECT = "defuse32-carrier"
NS = uuid.UUID("6f1c3c2e-0d6a-4b8e-9a51-defe32c0ffee")
SCH_VERSION = 20260306


def uid(*key):
    return str(uuid.uuid5(NS, "/".join(str(k) for k in key)))


ROOT = uid("root")
IC_LIBS = ("RF_Module", "defuse32", "Sensor_Motion", "Interface_Expansion", "Power_Protection",
           "Regulator_Linear", "74xGxx", "Connector")
STUB = 2.54


def sheet_uuid(key):
    """UUID of the sheet symbol (instance) for sub-sheet `key`; part of every symbol path."""
    return uid("sheet", key)


def sheet_path(key):
    return "/" + sheet_uuid(key)


def rotv(x, y, a):
    """Rotate a screen vector (y down) counter-clockwise (visually) by a degrees."""
    r = math.radians(a)
    c, s = round(math.cos(r)), round(math.sin(r))
    return x * c + y * s, -x * s + y * c


def to_sheet(X, Y, lx, ly, a):
    dx, dy = rotv(lx, -ly, a)
    return round(X + dx, 4), round(Y + dy, 4)


def outward(pin_rot, a):
    r = math.radians(pin_rot)
    dx, dy = rotv(-round(math.cos(r)), round(math.sin(r)), a)
    return dx, dy


def vec_angle(dx, dy):
    return {(1, 0): 0, (0, -1): 90, (-1, 0): 180, (0, 1): 270}[(int(dx), int(dy))]


def font(size=1.27, bold=False):
    f = [S("font"), [S("size"), size, size]]
    if bold:
        f.append([S("bold"), S("yes")])
    return f


def eff(size=1.27, justify=None, hide=False, bold=False):
    e = [S("effects"), font(size, bold)]
    if justify:
        e.append([S("justify")] + [S(j) for j in justify.split()])
    if hide:
        e.append([S("hide"), S("yes")])
    return e


def iprop(name, value, x, y, angle=0, hide=False, justify=None):
    p = [S("property"), name, value, [S("at"), x, y, angle]]
    if hide:
        p.append([S("hide"), S("yes")])
    p += [[S("show_name"), S("no")], [S("do_not_autoplace"), S("no")], eff(justify=justify)]
    return p


class Counter:
    pwr = 0
    flg = 0


class Sheet:
    def __init__(self, key):
        self.key = key            # None = root
        self.items = []
        self.libs = {}
        self.pwr_vals = []        # (net, x, y) of shown power-symbol values
        self.direct = {}          # net -> stub ends, for design.DIRECT nets

    def inst_path(self):
        return "/" + ROOT + (sheet_path(self.key) if self.key else "")

    def lib(self, libname, sym):
        key = "%s:%s" % (libname, sym)
        if key not in self.libs:
            node = flat(libname, sym)
            node[1] = key
            self.libs[key] = node
        return self.libs[key]

    # -------------------------------------------------------------- primitives
    def wire(self, x1, y1, x2, y2):
        self.items.append([S("wire"), [S("pts"), [S("xy"), x1, y1], [S("xy"), x2, y2]],
                           [S("stroke"), [S("width"), 0], [S("type"), S("default")]],
                           [S("uuid"), uid("w", self.key, x1, y1, x2, y2)]])

    def noconnect(self, x, y):
        self.items.append([S("no_connect"), [S("at"), x, y], [S("uuid"), uid("nc", self.key, x, y)]])

    def glabel(self, name, x, y, angle):
        just = "left" if angle in (0, 90) else "right"
        self.items.append([S("global_label"), name, [S("shape"), S("passive")], [S("at"), x, y, angle],
                           eff(justify=just), [S("uuid"), uid("gl", self.key, name, x, y)],
                           [S("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [S("at"), x, y, angle],
                            [S("hide"), S("yes")], [S("show_name"), S("no")], [S("do_not_autoplace"), S("no")],
                            eff(justify=just)]])

    def text(self, t, x, y, size=1.27, bold=False):
        self.items.append([S("text"), t, [S("exclude_from_sim"), S("no")], [S("at"), x, y, 0],
                           eff(size, "left", bold=bold), [S("uuid"), uid("t", self.key, t, x, y)]])

    def box(self, x1, y1, x2, y2, title):
        self.items.append([S("rectangle"), [S("start"), x1, y1], [S("end"), x2, y2],
                           [S("stroke"), [S("width"), 0.254], [S("type"), S("dash")]],
                           [S("fill"), [S("type"), S("none")]], [S("uuid"), uid("box", self.key, title)]])
        self.text(title, x1 + 2.54, y1 + 3.81, 2.54, bold=True)

    def sheet_symbol(self, key, x, y, w, h):
        name, fname, page = D.SHEETS[key]
        self.items.append([
            S("sheet"), [S("at"), x, y], [S("size"), w, h], [S("exclude_from_sim"), S("no")],
            [S("in_bom"), S("yes")], [S("on_board"), S("yes")], [S("dnp"), S("no")],
            [S("stroke"), [S("width"), 0.1524], [S("type"), S("solid")]],
            [S("fill"), [S("color"), 0, 0, 0, 0.0]], [S("uuid"), sheet_uuid(key)],
            [S("property"), "Sheetname", name, [S("at"), x, round(y - 0.7116, 4), 0],
             [S("show_name"), S("no")], [S("do_not_autoplace"), S("no")], eff(justify="left bottom")],
            [S("property"), "Sheetfile", fname, [S("at"), x, round(y + h + 0.5874, 4), 0],
             [S("show_name"), S("no")], [S("do_not_autoplace"), S("no")], eff(justify="left top")],
            [S("instances"), [S("project"), PROJECT, [S("path"), "/" + ROOT, [S("page"), str(page)]]]]])

    # -------------------------------------------------------------- symbols
    def place(self, libname, sym, ref, value, x, y, rot=0, unit=1, footprint="", props=None, power=False,
              fields=None, in_bom=True):
        node = self.lib(libname, sym)
        key = node[1]
        u = uid("sym", ref, unit) if not power else uid("pwr", ref)
        s = [S("symbol"), [S("lib_id"), key], [S("at"), x, y, rot], [S("unit"), unit], [S("body_style"), 1],
             [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes" if in_bom and not power else "no")],
             [S("on_board"), S("no" if power else "yes")], [S("in_pos_files"), S("yes")], [S("dnp"), S("no")],
             [S("uuid"), u]]
        props = props or {}
        for pname in ("Reference", "Value", "Footprint", "Datasheet", "Description"):
            val = {"Reference": ref, "Value": value, "Footprint": footprint}.get(pname)
            if val is None:
                val = lib_prop(node, pname) or ""
            pang = 0
            if pname in props:
                px, py, pj, hide = props[pname][:4]
                if len(props[pname]) > 4:
                    pang = props[pname][4]
            else:
                px, py, pj, hide = x, y, None, pname not in ("Reference", "Value")
                for p in find(node, "property"):
                    if p[1] == pname:
                        at = [a for a in p if isinstance(a, list) and a[0] == "at"][0]
                        px, py = to_sheet(x, y, float(at[1]), float(at[2]), rot)
            if rot in (90, 270):      # field angles are relative to the symbol: 90 reads horizontal
                pang = (pang + 90) % 180
            if rot in (90, 180) and pj:   # KiCad flips the justification to keep the text readable
                pj = " ".join({"left": "right", "right": "left"}.get(j, j) for j in pj.split())
            s.append(iprop(pname, val, px, py, pang, hide=hide or power and pname == "Reference", justify=pj))
        for fname, fval in (fields or {}).items():
            s.append(iprop(fname, fval, x, y, 0, hide=True))
        for p in lib_pins(node):
            if p["unit"] in (0, unit):
                s.append([S("pin"), p["num"], [S("uuid"), uid("pin", ref, unit, p["num"])]])
        s.append([S("instances"), [S("project"), PROJECT, [S("path"), self.inst_path(), [S("reference"), ref],
                                                           [S("unit"), unit]]]])
        self.items.append(s)
        return node

    def power(self, net, x, y, ang):
        """Power symbol whose graphic points along screen angle `ang` from (x, y)."""
        if net == "GND":
            rot = (ang + 90) % 360
        else:
            rot = (ang - 90) % 360
        Counter.pwr += 1
        ref = "#PWR%03d" % Counter.pwr
        d = 3.81
        vx, vy = {0: (d + 1.27, 0), 90: (0, -d), 180: (-d - 1.27, 0), 270: (0, d + 0.6)}[ang]
        just = {0: "left", 180: "right"}.get(ang)
        tx, ty = round(x + vx, 3), round(y + vy, 3)
        # two symbols of the same net side by side (e.g. CH340C VCC + V3): show the name once
        dup = any(n == net and abs(tx - qx) < 4 and abs(ty - qy) < 2 for n, qx, qy in self.pwr_vals)
        if not dup:
            self.pwr_vals.append((net, tx, ty))
        self.place("power", D.PWR_SYM[net], ref, net, x, y, rot,
                   props={"Value": (tx, ty, just, dup), "Reference": (x, y, None, True)}, power=True)

    def pwr_flag(self, x, y):
        Counter.flg += 1
        ref = "#FLG%03d" % Counter.flg
        self.place("power", "PWR_FLAG", ref, "PWR_FLAG", x, y, 0,
                   props={"Value": (x, round(y - 3.81, 3), None, False), "Reference": (x, y, None, True)},
                   power=True)

    def part(self, p):
        x, y = p["sch"]
        node = self.lib(p["lib"], p["sym"])
        pins = lib_pins(node)
        props = None
        sym, rot = p["sym"], p["rot"]
        if sym in ("R", "C", "C_Polarized", "Polyfuse") and rot == 0:
            props = {"Reference": (x + 2.54, y - 1.27, "left", False),
                     "Value": (x + 2.54, y + 1.27, "left", False)}
        elif sym in ("R", "C") and rot in (90, 270):
            props = {"Reference": (x, y - 2.54, None, False), "Value": (x, y + 2.54, None, False)}
        elif sym == "1N4148WS" and rot in (90, 270):
            props = {"Reference": (x + 2.54, y - 1.27, "left", False),
                     "Value": (x + 2.54, y + 1.27, "left", False)}
        elif sym == "SW_Push" and rot in (90, 270):
            props = {"Reference": (x + 2.54, y - 1.27, "left", False),
                     "Value": (x + 2.54, y + 1.27, "left", False)}
        elif sym == "MMBT3904":
            props = {"Reference": (x + 5.08, y - 1.27, "left", False),
                     "Value": (x + 5.08, y + 1.27, "left", False)}
        elif p["lib"] in IC_LIBS:
            # Reference / Value under the body, right of the bottom pin's power symbol
            ymax = max(to_sheet(x, y, q["x"], q["y"], rot)[1] for q in pins)
            props = {"Reference": (x + 3.81, ymax + 3.81, "left", False),
                     "Value": (x + 3.81, ymax + 6.35, "left", False)}
        fields = {}
        if p["lcsc"]:
            lc, mpn, mfr, tier = p["lcsc"]
            fields = {"LCSC": lc, "MPN": mpn, "Manufacturer": mfr, "JLC": tier}
        self.place(p["lib"], sym, p["ref"], p["value"], x, y, rot, 1, p["fp"], props, fields=fields,
                   in_bom=not p["ref"].startswith("H"))
        used = set()
        done = {}
        for pin in pins:
            if pin["unit"] not in (0, 1):
                continue
            num = pin["num"]
            px, py = to_sheet(x, y, pin["x"], pin["y"], rot)
            if num not in p["nets"]:
                if pin["type"] != "no_connect" and (px, py) not in done:
                    raise SystemExit("%s pin %s (%s) has no net and no NC" % (p["ref"], num, pin["name"]))
                if (px, py) in done and pin["type"] != "no_connect":
                    raise SystemExit("%s pin %s: stacked pin needs a net entry" % (p["ref"], num))
                continue
            used.add(num)
            net = p["nets"][num]
            if (px, py) in done:          # stacked pin: shares the stub of the first pin there
                if done[(px, py)] != net:
                    raise SystemExit("%s pin %s stacked on a pin with net %s" % (p["ref"], num, done[(px, py)]))
                continue
            done[(px, py)] = net
            if net is D.NC:
                self.noconnect(px, py)
                continue
            dx, dy = outward(pin["rot"], rot)
            ex, ey = round(px + dx * STUB, 4), round(py + dy * STUB, 4)
            self.wire(px, py, ex, ey)
            ang = vec_angle(dx, dy)
            if net in D.POWER:
                self.power(net, ex, ey, ang)
            elif net in D.DIRECT:
                self.direct.setdefault(net, []).append((ex, ey))
            else:
                self.glabel(net, ex, ey, ang)
        missing = set(p["nets"]) - used
        if missing:
            raise SystemExit("%s: nets for unknown pins %s" % (p["ref"], sorted(missing)))

    def wire_direct(self):
        for net, ends in self.direct.items():
            if len(ends) != 2:
                raise SystemExit("direct net %s has %d ends on one sheet" % (net, len(ends)))
            (x1, y1), (x2, y2) = ends
            # a global label standing on the first segment names the net (else KiCad calls it
            # Net-(...); a local label would get the sheet path as prefix)
            if y1 == y2 or x1 != x2:
                self.glabel(net, round((x1 + x2) / 2 / 1.27) * 1.27, y1, 90)
            else:
                self.glabel(net, x1, round((y1 + y2) / 2 / 1.27) * 1.27, 0)
            if x1 == x2 or y1 == y2:
                self.wire(x1, y1, x2, y2)
            else:
                self.wire(x1, y1, x2, y1)
                self.wire(x2, y1, x2, y2)

    # -------------------------------------------------------------- file
    def write(self, fname, paper, comment):
        tb = [S("title_block"), [S("title"), D.TITLE], [S("date"), D.DATE], [S("rev"), D.REV],
              [S("company"), "ESP32 CTF / Defuse32"],
              [S("comment"), 1, "Spec: hardware/defuse32/SPEC.md, \"Rev 2 carrier (2026-10-23)\""],
              [S("comment"), 2, "Generated by kicad/gen/gen_sch.py from kicad/gen/design.py"],
              [S("comment"), 3, "SMD, 4 layers (board rev 3.1), 100 x 70 mm; JLCPCB fields LCSC / MPN / JLC on every part"],
              [S("comment"), 4, comment]]
        u = ROOT if self.key is None else uid("file", self.key)
        sch = [S("kicad_sch"), [S("version"), SCH_VERSION], [S("generator"), "eeschema"],
               [S("generator_version"), "10.0"], [S("uuid"), u], [S("paper"), paper], tb,
               [S("lib_symbols")] + list(self.libs.values())]
        sch += self.items
        if self.key is None:
            sch += [[S("sheet_instances"), [S("path"), "/", [S("page"), "1"]]]]
        sch += [[S("embedded_fonts"), S("no")]]
        with open(os.path.join(KDIR, fname), "w") as f:
            f.write(dump(sch) + "\n")
        n = sum(1 for i in self.items if i[0] == "symbol" and not find(i, "lib_id")[0][1].startswith("power:"))
        print("wrote", fname, "parts:", n)


ROOT_NOTES = [
    ("Defuse32 carrier, schematic rev 2.1 (2026-11-25), board rev 3.1: SMD, 100 x 70 mm, 4 layers, 1.6 mm, 4 x M3 holes 4 mm from the corners.", 2.0),
    ("ESP32-WROOM-32E (4 MB) at the left edge, antenna region outside the board outline. USB-C (power + programming)", 1.5),
    ("-> PTC -> 5V; CH340C on UART0 with DTR/RTS auto-reset. AMS1117-3.3 -> 3V3 (ESP32, CH340C); AMS1117-3.3 -> 3V3P", 1.5),
    ("(plates, MCP23017 x2, LIS3DH, microSD, pull-ups). One keyed IDC box header per plate (J1-J6).", 1.5),
    ("", 1.5),
    ("I2C (GPIO21 SDA / GPIO22 SCL): U2 MCP23017 0x20, U3 MCP23017 0x21, U8 LIS3DH 0x19; on the plates: SSD1306 0x3C,", 1.5),
    ("SH1106 0x3D, 24C32 0x50, PN532 0x24. ESP32 GPIO map, MCP23017 allocation and WS2812 chain unchanged from rev 1b.", 1.5),
    ("", 1.5),
    ("Nets cross sheets through global labels and power symbols. Every part carries LCSC / MPN / Manufacturer / JLC fields.", 1.5),
    ("SPEC connector names -> references: plate Jn = Jn, J_USB = J7, J_KEY = J8, J_SERVO = J9, J_SPARE = J10, J_SD = J11.", 1.5),
]
ROOT_SHEETS = [("power", 25.4, 33.02), ("mcu", 147.32, 33.02), ("io", 25.4, 68.58), ("conn", 147.32, 68.58)]
SHEET_W, SHEET_H = 116.84, 25.4
SHEET_TEXT = {
    "power": ["USB-C J7, CC 5.1k, USBLC6 U9, PTC F1, 220 uF bulk", "AMS1117 U6 -> 3V3, AMS1117 U5 -> 3V3P",
              "CH340C U7 (UART0), auto-reset Q2/Q3"],
    "mcu": ["ESP32-WROOM-32E U1 + decoupling, EN/BOOT SW1/SW2", "pull-ups / pull-downs (R2-R6, R8, R9)",
            "WS2812 buffer U4, buzzer driver Q1"],
    "io": ["MCP23017-E/SO U2 (0x20), U3 (0x21)", "LIS3DH U8 (0x19, I2C, polled)",
           "microSD J11 (push-push, SPI) + card detect"],
    "conn": ["IDC box headers J1-J6 (plates M1-M6)", "J_KEY J8, J_SERVO J9, J_SPARE J10",
             "mounting holes H1-H4"],
}


def build():
    sheets = {k: Sheet(k) for k in D.SHEETS}
    root = Sheet(None)
    for k, x, y in ROOT_SHEETS:
        root.sheet_symbol(k, x, y, SHEET_W, SHEET_H)
        for i, line in enumerate(SHEET_TEXT[k]):
            root.text(line, x + 2.54, y + 6.35 + i * 5.08, 1.27)
    y = 106.68
    for t, step in ROOT_NOTES:
        if t:
            root.text(t, 25.4, y, 1.27 if step < 2 else 1.778, bold=step >= 2)
        y += 5.08 if step >= 2 else 4.445
    root.text("Sheets: 2 Power, USB, UART  |  3 ESP32 module  |  4 Expanders, tilt, microSD  |  5 Plate connectors",
              25.4, 22.86, 1.27)

    for key, blocks in D.BLOCKS.items():
        sh = sheets[key]
        for x1, y1, x2, y2, title, notes in blocks:
            sh.box(x1, y1, x2, y2, title)
            for t, tx, ty in notes:
                sh.text(t, tx, ty, 1.0)
    # plate connector captions
    for n, (x, y) in D.PLATE_SCH.items():
        name, rows, _ = D.PLATES[n]
        sheets["conn"].text("J%d  M%d %s  (2x%d)" % (n, n, name, rows), x - 20.32, y - rows * 1.27 - 7.62, 1.778,
                            bold=True)
    sheets["conn"].text("pin 11 = BUZZ+ (5V)", D.PLATE_SCH[2][0] + 22.86, D.PLATE_SCH[2][1] + 10.16, 1.0)

    # power flags
    fkey, flags = D.PWR_FLAGS
    for net, x, y in flags:
        sh = sheets[fkey]
        sh.wire(x, y, x + 10.16, y)
        sh.power(net, x, y, 270 if net == "GND" else 90)
        sh.pwr_flag(x + 10.16, y)

    for p in D.PARTS:
        sheets[p["sheet"]].part(p)
    for sh in sheets.values():
        sh.wire_direct()

    root.write(PROJECT + ".kicad_sch", "A4", "Root: sheet symbols and overview")
    for key, sh in sheets.items():
        name, fname, page = D.SHEETS[key]
        sh.write(fname, "A3", "Sheet %d: %s" % (page, name))


if __name__ == "__main__":
    build()
