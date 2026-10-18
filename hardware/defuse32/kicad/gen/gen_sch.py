#!/usr/bin/env python3
"""Generate defuse32-carrier.kicad_sch from design.py.

Every connected pin gets a 2.54 mm wire stub ending in a global label (net name)
or, on vertical stubs, a power symbol (5V / 3V3 / GND). No-connect flags on NC pins.
Run:  /usr/bin/python3 kicad/gen/gen_sch.py   (then `kicad-cli sch upgrade` is optional)
"""
import math
import os
import uuid

import design as D
from sexp import Sym as S, dump
from symlib import flat, pins as lib_pins, prop as lib_prop
from sexp import find

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(HERE, ".."))
PROJECT = "defuse32-carrier"
NS = uuid.UUID("6f1c3c2e-0d6a-4b8e-9a51-defe32c0ffee")


def uid(*key):
    return str(uuid.uuid5(NS, "/".join(str(k) for k in key)))


ROOT = uid("root")
STUB = 2.54
G = 1.27


def snap(v):
    return round(round(v / G) * G, 4)


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


class Sheet:
    def __init__(self):
        self.items = []
        self.libs = {}
        self.pwr_n = 0
        self.flg_n = 0

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
                           [S("uuid"), uid("w", x1, y1, x2, y2)]])

    def noconnect(self, x, y):
        self.items.append([S("no_connect"), [S("at"), x, y], [S("uuid"), uid("nc", x, y)]])

    def glabel(self, name, x, y, angle):
        just = "left" if angle in (0, 90) else "right"
        self.items.append([S("global_label"), name, [S("shape"), S("passive")], [S("at"), x, y, angle],
                           eff(justify=just), [S("uuid"), uid("gl", name, x, y)],
                           [S("property"), "Intersheetrefs", "${INTERSHEET_REFS}", [S("at"), x, y, angle],
                            [S("hide"), S("yes")], [S("show_name"), S("no")], [S("do_not_autoplace"), S("no")],
                            eff(justify=just)]])

    def text(self, t, x, y, size=1.27, bold=False):
        self.items.append([S("text"), t, [S("exclude_from_sim"), S("no")], [S("at"), x, y, 0],
                           eff(size, "left", bold=bold), [S("uuid"), uid("t", t, x, y)]])

    def box(self, x1, y1, x2, y2, title):
        self.items.append([S("rectangle"), [S("start"), x1, y1], [S("end"), x2, y2],
                           [S("stroke"), [S("width"), 0.254], [S("type"), S("dash")]],
                           [S("fill"), [S("type"), S("none")]], [S("uuid"), uid("box", title)]])
        self.text(title, x1 + 2.54, y1 + 3.81, 2.54, bold=True)

    # -------------------------------------------------------------- symbols
    def place(self, libname, sym, ref, value, x, y, rot=0, unit=1, footprint="", props=None, power=False):
        node = self.lib(libname, sym)
        key = node[1]
        u = uid("sym", ref, unit) if not power else uid("pwr", ref)
        s = [S("symbol"), [S("lib_id"), key], [S("at"), x, y, rot], [S("unit"), unit], [S("body_style"), 1],
             [S("exclude_from_sim"), S("no")], [S("in_bom"), S("no" if power or ref.startswith("H") else "yes")],
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
            s.append(iprop(pname, val, px, py, pang, hide=hide or power and pname == "Reference", justify=pj))
        for p in lib_pins(node):
            if p["unit"] in (0, unit):
                s.append([S("pin"), p["num"], [S("uuid"), uid("pin", ref, unit, p["num"])]])
        s.append([S("instances"), [S("project"), PROJECT, [S("path"), "/" + ROOT, [S("reference"), ref],
                                                           [S("unit"), unit]]]])
        self.items.append(s)
        return node

    def power(self, net, x, y, ang):
        """Power symbol whose graphic points along screen angle `ang` from (x, y)."""
        if net == "GND":
            libsym, rot = "GND", (ang + 90) % 360
        else:
            libsym, rot = {"5V": "+5V", "3V3": "+3V3", "DK_5V": "+5V"}[net], (ang - 90) % 360
        self.pwr_n += 1
        ref = "#PWR%03d" % self.pwr_n
        d = 3.81
        vx, vy = {0: (d, 0), 90: (0, -d), 180: (-d, 0), 270: (0, d + 0.6)}[ang]
        just = {0: "left", 180: "right"}.get(ang)
        self.place("power", libsym, ref, net, x, y, rot,
                   props={"Value": (round(x + vx, 3), round(y + vy, 3), just, False),
                          "Reference": (x, y, None, True)}, power=True)

    def pwr_flag(self, x, y):
        self.flg_n += 1
        ref = "#FLG%03d" % self.flg_n
        self.place("power", "PWR_FLAG", ref, "PWR_FLAG", x, y, 0,
                   props={"Value": (x, round(y - 3.81, 3), None, False), "Reference": (x, y, None, True)},
                   power=True)

    def part(self, p):
        units = p["unit_pos"] or {1: p["sch"]}
        node = self.lib(p["lib"], p["sym"])
        pins = lib_pins(node)
        used = set()
        for unit, (x, y) in units.items():
            props = None
            if p["sym"] in ("R", "C", "C_Polarized"):
                props = {"Reference": (x + 2.54, y - 1.27, "left", False),
                         "Value": (x + 2.54, y + 1.27, "left", False)}
            elif p["sym"] in ("1N5822", "1N4148") and p["rot"] in (90, 270):
                # field angles are relative to the symbol: 90 shows horizontal on a rotated part
                props = {"Reference": (x + 4.445, y - 1.27, None, False, 90),
                         "Value": (x + 5.715, y + 1.27, None, False, 90)}
            elif p["sym"].startswith("MCP23017"):
                props = {"Reference": (x + 2.54, y - 27.94, "left", False),
                         "Value": (x + 2.54, y + 29.21, "left", False)}
            elif p["sym"] == "2N3904":
                props = {"Reference": (x + 6.35, y - 1.27, "left", False),
                         "Value": (x + 6.35, y + 1.27, "left", False)}
            elif p["sym"] == "74AHCT125" and unit < 5:
                props = {"Reference": (x, y - 7.62, None, False), "Value": (x, y - 5.08, None, False)}
            elif p["sym"] in ("1N5822", "1N4148"):
                props = {"Reference": (x, y - 3.81, None, False), "Value": (x, y + 3.81, None, False)}
            self.place(p["lib"], p["sym"], p["ref"], p["value"], x, y, p["rot"], unit, p["fp"], props)
            for pin in pins:
                if pin["unit"] not in (0, unit):
                    continue
                num = pin["num"]
                px, py = to_sheet(x, y, pin["x"], pin["y"], p["rot"])
                if num not in p["nets"]:
                    if pin["type"] != "no_connect":
                        raise SystemExit("%s pin %s (%s) has no net and no NC" % (p["ref"], num, pin["name"]))
                    continue
                used.add(num)
                net = p["nets"][num]
                if net is D.NC:
                    self.noconnect(px, py)
                    continue
                dx, dy = outward(pin["rot"], p["rot"])
                ex, ey = round(px + dx * STUB, 4), round(py + dy * STUB, 4)
                self.wire(px, py, ex, ey)
                ang = vec_angle(dx, dy)
                if net in D.POWER and ang in (90, 270):
                    self.power(net, ex, ey, ang)
                else:
                    self.glabel(net, ex, ey, ang)
        missing = set(p["nets"]) - used
        if missing:
            raise SystemExit("%s: nets for unknown pins %s" % (p["ref"], sorted(missing)))


def build():
    sh = Sheet()
    # ---- block frames and notes (A3 sheet: 420 x 297)
    sh.box(15.24, 15.24, 119.38, 101.6, "POWER IN, BULK, DECOUPLING")
    sh.text("5 V from the panel USB-C module (J_PWR). D1: DevKit USB cannot back-feed the rail.", 17.78, 22.86, 1.0)
    sh.text("PWR_FLAGs (ERC)", 17.78, 48.26, 1.0)
    sh.text("C3: U2   C4: U3   C5: U4", 17.78, 68.58, 1.0)
    sh.box(124.46, 15.24, 236.22, 101.6, "ESP32-DevKitC-32E (U1)")
    sh.text("GPIO2, GPIO12: strapping, unused.  GPIO0/1/3/6-11: boot, console, flash.", 127.0, 88.9, 1.0)
    sh.text("Socket: 2x 1x19 at 25.40 mm + unpopulated clone row at 22.86 mm (same nets).", 127.0, 92.71, 1.0)
    sh.text("D1 feeds the DevKit 5V pin (DK_5V); the DevKit LDO makes 3V3 for the carrier.", 127.0, 96.52, 1.0)
    sh.box(241.3, 15.24, 332.74, 101.6, "PULL-UPS, IMU (A1 on carrier)")
    sh.text("R2/R3 I2C 4.7k; R4 GPIO35, R5 GPIO34 10k pull-ups.", 243.84, 81.28, 1.0)
    sh.text("LDR on M6: 3V3 -> GPIO36 (LDR); R6 is the low side.", 243.84, 85.09, 1.0)
    sh.text("A1 AD0 tied low: MPU-6050 at 0x68.", 243.84, 88.9, 1.0)
    sh.box(337.82, 15.24, 406.4, 101.6, "WS2812 BUFFER 3V3->5V")
    sh.text("Gates 2-4 unused: A to GND, ~{OE} high.", 340.36, 99.06, 1.0)
    sh.box(15.24, 106.68, 236.22, 195.58, "I2C EXPANDERS (U2 0x20, U3 0x21)")
    sh.text("INTA/INTB of both chips: mirrored, open-drain, wired-OR to GPIO35 (MCP_INT).", 17.78, 115.57, 1.0)
    sh.text("U2: keypad ROW/COL, Simon SIM1-4, KEY, spare GPB5-7 (J_SPARE).", 17.78, 119.38, 1.0)
    sh.text("U3: wire posts WA (outputs) / WB (inputs), encoder ENC_A/B/SW.", 119.38, 115.57, 1.0)
    sh.text("GPA7/GPB7 are output-only on current MCP23017 silicon: U3 GPA7 = WA6 (output),", 119.38, 119.38, 1.0)
    sh.text("ENC_B on GPA5, GPB7 spare (handled, as SPEC).", 119.38, 123.19, 1.0)
    sh.box(241.3, 106.68, 317.5, 195.58, "BUZZER DRIVER")
    sh.text("GPIO26 (BUZZ, LEDC PWM) -> R7 -> Q1.", 243.84, 182.88, 1.0)
    sh.text("Buzzer on M2: BUZZ+ = 5V, BUZZ- on J2_B.", 243.84, 186.69, 1.0)
    sh.box(322.58, 106.68, 406.4, 195.58, "CARRIER HEADERS")
    sh.text("J_KEY: key switch (case wall) -> U2 GPB4.", 325.12, 175.26, 1.0)
    sh.text("J_SERVO: SG90 order GND / 5V / SIG", 325.12, 179.07, 1.0)
    sh.text("(SERVO_SIG is also on J6_B; use either).", 325.12, 182.88, 1.0)
    sh.text("J_SPARE: U2 GPB5-7 (GPB7 output-only).", 325.12, 186.69, 1.0)
    sh.box(15.24, 198.12, 294.64, 284.48, "PLATE CONNECTORS (JST-XH 2.5 mm)")
    sh.text("Jn_A (all plates): 5V 3V3 GND SDA SCL LDI LDO.  WS2812 chain: U4 -> R1 -> LDI (M1) -> LDO1 -> M2 -> LDO2 -> M3 "
            "-> LDO3 -> M4 -> LDO4 -> M5 -> LDO5 -> M6 (end).", 17.78, 205.74, 1.0)
    sh.text("SPEC names -> references: Jn_A = Jn1, Jn_B = Jn2, J_PWR = J7, J_KEY = J8, J_SERVO = J9, J_SPARE = J10 "
            "(the SPEC name starts each Value).", 17.78, 209.55, 1.0)
    for n, (x, y) in D.PLATE_SCH.items():
        sh.text("M%d %s" % (n, D.PLATE_B[n][0]), x - 27.94, y - 12.7, 1.778, bold=True)

    # ---- power flags
    for net, x, y in (("5V", 20.32, 58.42), ("GND", 43.18, 58.42), ("DK_5V", 66.04, 58.42)):
        sh.wire(x, y, x + 10.16, y)
        sh.power(net, x, y, 270 if net == "GND" else 90)
        sh.pwr_flag(x + 10.16, y)

    for p in D.PARTS:
        sh.part(p)

    sch = [S("kicad_sch"), [S("version"), 20260306], [S("generator"), "eeschema"], [S("generator_version"), "10.0"],
           [S("uuid"), ROOT], [S("paper"), "A3"],
           [S("title_block"), [S("title"), "Defuse32 carrier"], [S("date"), "2026-10-19"], [S("rev"), "0"],
            [S("company"), "ESP32 CTF / Defuse32"],
            [S("comment"), 1, "Spec: hardware/defuse32/SPEC.md (Electronics, carrier PCB)"],
            [S("comment"), 2, "Generated by kicad/gen/gen_sch.py from kicad/gen/design.py"],
            [S("comment"), 3, "THT only, 2 layers, 190 x 140 mm"]],
           [S("lib_symbols")] + list(sh.libs.values())]
    sch += sh.items
    sch += [[S("sheet_instances"), [S("path"), "/", [S("page"), "1"]]], [S("embedded_fonts"), S("no")]]
    out = os.path.join(KDIR, PROJECT + ".kicad_sch")
    with open(out, "w") as f:
        f.write(dump(sch) + "\n")
    print("wrote", out, "symbols:", sum(1 for i in sh.items if i[0] == "symbol"))


if __name__ == "__main__":
    build()
