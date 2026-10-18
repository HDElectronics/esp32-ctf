#!/usr/bin/env python3
"""Generate the project-local libraries: defuse32.kicad_sym and defuse32.pretty/.

Run from anywhere:  python3 kicad/gen/gen_lib.py
Geometry sources: ../../data/parts.json (devkitc_32e, gy521) and ../../docs/parts.md.
"""
import json
import os

from sexp import Sym as S, dump

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(HERE, ".."))
PARTS = json.load(open(os.path.join(KDIR, "..", "data", "parts.json")))["modules"]

# ---------------------------------------------------------------- DevKitC pinout
# Pin 1..19 = left header J2 (antenna end -> USB end, viewed from the top with the
# USB connector at the bottom); pin 20..38 = right header J3, same direction.
DEVKIT_LEFT = [
    ("3V3", "power_out"), ("EN", "input"), ("GPIO36/SVP", "input"), ("GPIO39/SVN", "input"),
    ("GPIO34", "input"), ("GPIO35", "input"), ("GPIO32", "bidirectional"), ("GPIO33", "bidirectional"),
    ("GPIO25", "bidirectional"), ("GPIO26", "bidirectional"), ("GPIO27", "bidirectional"),
    ("GPIO14", "bidirectional"), ("GPIO12", "bidirectional"), ("GND", "power_in"),
    ("GPIO13", "bidirectional"), ("SD2/GPIO9", "bidirectional"), ("SD3/GPIO10", "bidirectional"),
    ("CMD/GPIO11", "bidirectional"), ("5V", "power_in"),
]
DEVKIT_RIGHT = [
    ("GND", "power_in"), ("GPIO23", "bidirectional"), ("GPIO22", "bidirectional"),
    ("TXD0/GPIO1", "bidirectional"), ("RXD0/GPIO3", "bidirectional"), ("GPIO21", "bidirectional"),
    ("GND", "power_in"), ("GPIO19", "bidirectional"), ("GPIO18", "bidirectional"),
    ("GPIO5", "bidirectional"), ("GPIO17", "bidirectional"), ("GPIO16", "bidirectional"),
    ("GPIO4", "bidirectional"), ("GPIO0", "bidirectional"), ("GPIO2", "bidirectional"),
    ("GPIO15", "bidirectional"), ("SD1/GPIO8", "bidirectional"), ("SD0/GPIO7", "bidirectional"),
    ("CLK/GPIO6", "bidirectional"),
]
GY521_PINS = [("VCC", "power_in"), ("GND", "power_in"), ("SCL", "input"), ("SDA", "bidirectional"),
              ("XDA", "bidirectional"), ("XCL", "output"), ("AD0", "input"), ("INT", "output")]


def font(size=1.27, extra=None):
    f = [S("font"), [S("size"), size, size]]
    if extra:
        f += extra
    return [S("effects"), f]


def prop(name, value, x, y, hide=False, angle=0, justify=None):
    p = [S("property"), name, value, [S("at"), x, y, angle], [S("show_name"), S("no")],
         [S("do_not_autoplace"), S("no")]]
    if hide:
        p.append([S("hide"), S("yes")])
    e = font()
    if justify:
        e.append([S("justify"), S(justify)])
    p.append(e)
    return p


def pin(ptype, x, y, rot, name, num, length=2.54):
    return [S("pin"), S(ptype), S("line"), [S("at"), x, y, rot], [S("length"), length],
            [S("name"), name, font()], [S("number"), num, font()]]


def rect(x1, y1, x2, y2, w=0.254, fill="background"):
    return [S("rectangle"), [S("start"), x1, y1], [S("end"), x2, y2],
            [S("stroke"), [S("width"), w], [S("type"), S("default")]], [S("fill"), [S("type"), S(fill)]]]


def sym_header(name, ref, value, fp, ds, desc, kw, ref_xy, val_xy):
    return [S("symbol"), name,
            [S("pin_names"), [S("offset"), 1.016]],
            [S("exclude_from_sim"), S("no")], [S("in_bom"), S("yes")], [S("on_board"), S("yes")],
            [S("in_pos_files"), S("yes")], [S("duplicate_pin_numbers_are_jumpers"), S("no")],
            prop("Reference", ref, ref_xy[0], ref_xy[1]),
            prop("Value", value, val_xy[0], val_xy[1]),
            prop("Footprint", fp, 0, 0, hide=True),
            prop("Datasheet", ds, 0, 0, hide=True),
            prop("Description", desc, 0, 0, hide=True),
            prop("ki_keywords", kw, 0, 0, hide=True)]


def devkit_symbol():
    s = sym_header("ESP32-DevKitC-32E", "U", "ESP32-DevKitC-32E", "defuse32:ESP32-DevKitC_Socket",
                   "https://docs.espressif.com/projects/esp-dev-kits/en/latest/esp32/esp32-devkitc/user_guide.html",
                   "Espressif ESP32-DevKitC V4 (WROOM-32E), 38 pin, plugged into 2x 1x19 sockets. "
                   "Pins 1-19 = header J2, 20-38 = header J3 (antenna end first)",
                   "ESP32 DevKitC module", (-15.24, 27.94), (-15.24, -27.94))
    body = [S("symbol"), "ESP32-DevKitC-32E_0_1", rect(-15.24, 25.4, 15.24, -25.4)]
    pins = [S("symbol"), "ESP32-DevKitC-32E_1_1"]
    for i, (n, t) in enumerate(DEVKIT_LEFT):
        pins.append(pin(t, -17.78, 22.86 - 2.54 * i, 0, n, str(i + 1)))
    for i, (n, t) in enumerate(DEVKIT_RIGHT):
        pins.append(pin(t, 17.78, 22.86 - 2.54 * i, 180, n, str(i + 20)))
    s += [body, pins, [S("embedded_fonts"), S("no")]]
    return s


def gy521_symbol():
    s = sym_header("GY-521", "A", "GY-521", "defuse32:GY-521_Socket",
                   "https://components101.com/sensors/mpu6050-module",
                   "GY-521 MPU-6050 6-axis IMU breakout, plugs into a 1x8 female header (VCC first)",
                   "MPU6050 IMU accelerometer gyro module", (0, 12.7), (0, -15.24))
    body = [S("symbol"), "GY-521_0_1", rect(-5.08, 10.16, 7.62, -12.7)]
    pins = [S("symbol"), "GY-521_1_1"]
    for i, (n, t) in enumerate(GY521_PINS):
        pins.append(pin(t, -7.62, 8.89 - 2.54 * i, 0, n, str(i + 1)))
    s += [body, pins, [S("embedded_fonts"), S("no")]]
    return s


def write_symlib():
    lib = [S("kicad_symbol_lib"), [S("version"), 20251024], [S("generator"), "defuse32_gen_lib"],
           [S("generator_version"), "10.0"], devkit_symbol(), gy521_symbol()]
    with open(os.path.join(KDIR, "defuse32.kicad_sym"), "w") as f:
        f.write(dump(lib) + "\n")


# ---------------------------------------------------------------- footprints
def line(x1, y1, x2, y2, layer, w):
    return [S("fp_line"), [S("start"), x1, y1], [S("end"), x2, y2],
            [S("stroke"), [S("width"), w], [S("type"), S("solid")]], [S("layer"), layer]]


def box(x1, y1, x2, y2, layer, w):
    return [line(x1, y1, x2, y1, layer, w), line(x2, y1, x2, y2, layer, w),
            line(x2, y2, x1, y2, layer, w), line(x1, y2, x1, y1, layer, w)]


def poly(pts, layer, w):
    return [S("fp_poly"), [S("pts")] + [[S("xy"), x, y] for x, y in pts],
            [S("stroke"), [S("width"), w], [S("type"), S("solid")]], [S("fill"), S("no")], [S("layer"), layer]]


def circle(cx, cy, r, layer, w):
    return [S("fp_circle"), [S("center"), cx, cy], [S("end"), cx + r, cy],
            [S("stroke"), [S("width"), w], [S("type"), S("solid")]], [S("fill"), S("no")], [S("layer"), layer]]


def text(t, x, y, layer, size=1.0, justify=None, angle=0):
    eff = [S("effects"), [S("font"), [S("size"), size, size], [S("thickness"), round(size * 0.15, 3)]]]
    if justify:
        eff.append([S("justify"), S(justify)])
    return [S("fp_text"), S("user"), t, [S("at"), x, y, angle], [S("layer"), layer], eff]


def fprop(name, value, x, y, layer, hide=False):
    p = [S("property"), name, value, [S("at"), x, y, 0], [S("layer"), layer]]
    if hide:
        p.append([S("hide"), S("yes")])
    p.append([S("effects"), [S("font"), [S("size"), 1, 1], [S("thickness"), 0.15]]])
    return p


def pad(num, x, y, first=False):
    return [S("pad"), num, S("thru_hole"), S("rect" if first else "circle"), [S("at"), x, y],
            [S("size"), 1.7, 1.7], [S("drill"), 1], [S("layers"), "*.Cu", "*.Mask"],
            [S("remove_unused_layers"), S("no")]]


def model(path, x=0, y=0, rz=0):
    return [S("model"), path, [S("offset"), [S("xyz"), x, y, 0]], [S("scale"), [S("xyz"), 1, 1, 1]],
            [S("rotate"), [S("xyz"), 0, 0, rz]]]


SOCK = "${KICAD10_3DMODEL_DIR}/Connector_PinSocket_2.54mm.3dshapes/PinSocket_1x%02d_P2.54mm_Vertical.step"


def devkit_footprint():
    d = PARTS["devkitc_32e"]
    p0 = d["headers"]["rows"][0]
    pitch = d["headers"]["pitch"]
    n = p0["n"]
    w, h = d["pcb"]["w"], d["pcb"]["h"]
    span = (n - 1) * pitch                       # 45.72
    v1 = p0["y0"] + span                         # pin 1 distance from the USB edge (47.01)
    u1 = p0["x"]                                 # pin 1 distance from the left long edge (1.27)
    row2 = d["headers"]["row_spacing"]           # 25.40
    row3 = 22.86                                 # narrow-clone row
    # DevKit frame (u right, v up, USB at v=0) -> footprint (X right, Y down), USB facing +X:
    X = lambda v: round(v1 - v, 4)
    Y = lambda u: round(u1 - u, 4)
    ant = d["antenna_overhang"]
    pcb = (X(h), Y(w), X(0), Y(0))               # x1, y1(top), x2, y2(bottom)
    antr = (X(ant["y"] + ant["h"]), Y(ant["x"] + ant["w"]), X(ant["y"]), Y(ant["x"]))
    mid = (pcb[1] + pcb[3]) / 2
    fp = [S("footprint"), "ESP32-DevKitC_Socket", [S("version"), 20260206], [S("generator"), "defuse32_gen_lib"],
          [S("layer"), "F.Cu"],
          [S("descr"), "Socket for Espressif ESP32-DevKitC V4 (38 pin): 2x 1x19 female headers 25.40 mm apart, "
                       "plus an unpopulated third 1x19 row 22.86 mm from row 1 for narrow clones (same pad numbers/nets). "
                       "Pin 1 = 3V3 (antenna end). USB edge faces +X. Silk: DevKit outline, antenna overhang, USB arrow."],
          [S("tags"), "ESP32 DevKitC socket 38pin"],
          fprop("Reference", "REF**", 8, mid + 2.2, "F.SilkS"),
          fprop("Value", "ESP32-DevKitC_Socket", 22, mid - 3, "F.Fab"),
          fprop("Datasheet", "https://dl.espressif.com/dl/schematics/esp32_devkitc_v4_dimensions.pdf", 0, 0, "F.Fab", hide=True),
          fprop("Description", "ESP32-DevKitC socket, 25.40 + 22.86 mm rows", 0, 0, "F.Fab", hide=True),
          [S("attr"), S("through_hole")], [S("duplicate_pad_numbers_are_jumpers"), S("no")]]
    # silkscreen: DevKit PCB outline and antenna overhang (outline is >0.35 mm off every pad)
    fp += box(pcb[0], pcb[1], pcb[2], pcb[3], "F.SilkS", 0.12)
    fp.append(line(antr[0], antr[1], antr[2], antr[1], "F.SilkS", 0.12))
    fp.append(line(antr[0], antr[1], antr[0], antr[3], "F.SilkS", 0.12))
    fp.append(line(antr[0], antr[3], antr[2], antr[3], "F.SilkS", 0.12))
    # antenna hatch
    for k in range(1, 6):
        x = antr[0] + k * (antr[2] - antr[0]) / 6
        fp.append(line(round(x, 3), antr[1] + 0.6, round(x, 3), antr[3] - 0.6, "F.SilkS", 0.12))
    fp.append(text("ANT", (antr[0] + antr[2]) / 2, mid, "F.Fab", 1.0, angle=90))
    # USB arrow (between the rows, near the USB edge)
    ax2 = pcb[2] - 2.0
    fp.append(line(ax2 - 9, mid, ax2, mid, "F.SilkS", 0.3))
    fp.append(line(ax2, mid, ax2 - 2.2, mid - 1.6, "F.SilkS", 0.3))
    fp.append(line(ax2, mid, ax2 - 2.2, mid + 1.6, "F.SilkS", 0.3))
    fp.append(text("USB", ax2 - 5, mid - 2.6, "F.SilkS", 1.2))
    fp.append(text("ESP32-DevKitC", 20, mid + 5.5, "F.SilkS", 1.2))
    fp.append(text("clone row 22.86", 20, Y(u1 + row3) + 2.1, "F.SilkS", 0.8))
    # fab: outline, antenna, micro-USB connector
    fp += box(pcb[0], pcb[1], pcb[2], pcb[3], "F.Fab", 0.1)
    fp += box(antr[0], antr[1], antr[2], antr[3], "F.Fab", 0.1)
    fp += box(pcb[2] - 5.6, mid - 4, pcb[2] + 1.0, mid + 4, "F.Fab", 0.1)
    fp.append(text("${REFERENCE}", 30, mid + 5.5, "F.Fab", 1.0))
    # courtyard: PCB + antenna + USB plug lip
    c = 0.5
    fp.append(poly([(antr[0] - c, antr[1] - c), (pcb[0] - c, antr[1] - c), (pcb[0] - c, pcb[1] - c),
                    (pcb[2] + 1.0 + c, pcb[1] - c), (pcb[2] + 1.0 + c, pcb[3] + c), (pcb[0] - c, pcb[3] + c),
                    (pcb[0] - c, antr[3] + c), (antr[0] - c, antr[3] + c)], "F.CrtYd", 0.05))
    # pads
    for i in range(n):
        fp.append(pad(str(i + 1), round(i * pitch, 4), 0, first=(i == 0)))
    for i in range(n):
        fp.append(pad(str(i + 20), round(i * pitch, 4), Y(u1 + row2)))
    for i in range(n):
        fp.append(pad(str(i + 20), round(i * pitch, 4), Y(u1 + row3)))
    fp += [[S("embedded_fonts"), S("no")]]
    # 3D: the two populated sockets (model pins run along -Y in 3D; rotate -90 to +X)
    fp.append(model(SOCK % n, 0, 0, -90))
    fp.append(model(SOCK % n, 0, -Y(u1 + row2), -90))
    return fp


def gy521_footprint():
    d = PARTS["gy521"]
    hx = d["headers"]["rows"][0]["x"]
    y0 = d["headers"]["rows"][0]["y0"]
    w, h = d["pcb"]["w"], d["pcb"]["h"]
    top_pin_v = y0 + 7 * 2.54                     # VCC (pin 1) is the top pin
    X = lambda u: round(u - hx, 4)
    Y = lambda v: round(top_pin_v - v, 4)
    o = (X(0), Y(h), X(w), Y(0))
    fp = [S("footprint"), "GY-521_Socket", [S("version"), 20260206], [S("generator"), "defuse32_gen_lib"],
          [S("layer"), "F.Cu"],
          [S("descr"), "1x8 female header for a GY-521 MPU-6050 breakout (VCC GND SCL SDA XDA XCL AD0 INT); "
                       "silk shows the module outline (15.56 x 20.26, typical) overhanging to the right"],
          [S("tags"), "GY-521 MPU6050 socket"],
          fprop("Reference", "REF**", (o[0] + o[2]) / 2, o[1] - 1.5, "F.SilkS"),
          fprop("Value", "GY-521_Socket", (o[0] + o[2]) / 2, o[3] + 1.5, "F.Fab"),
          fprop("Datasheet", "", 0, 0, "F.Fab", hide=True),
          fprop("Description", "GY-521 module socket", 0, 0, "F.Fab", hide=True),
          [S("attr"), S("through_hole")], [S("duplicate_pad_numbers_are_jumpers"), S("no")]]
    fp += box(o[0], o[1], o[2], o[3], "F.SilkS", 0.12)
    for i, (n, _) in enumerate(GY521_PINS):
        fp.append(text(n, 1.6, round(i * 2.54, 3), "F.SilkS", 0.8, justify="left"))
    fp.append(text("GY-521", 8.6, 8.9, "F.SilkS", 1.0, angle=90))
    fp += box(o[0], o[1], o[2], o[3], "F.Fab", 0.1)
    for hole in d["holes"]:
        fp.append(circle(X(hole["x"]), Y(hole["y"]), hole["d"] / 2, "F.Fab", 0.1))
    fp.append(text("${REFERENCE}", 6, 4, "F.Fab", 1.0))
    c = 0.25
    fp += box(o[0] - c, o[1] - c, o[2] + c, o[3] + c, "F.CrtYd", 0.05)
    for i in range(8):
        fp.append(pad(str(i + 1), 0, round(i * 2.54, 4), first=(i == 0)))
    fp += [[S("embedded_fonts"), S("no")]]
    fp.append(model(SOCK % 8))
    return fp


def write_fplib():
    d = os.path.join(KDIR, "defuse32.pretty")
    os.makedirs(d, exist_ok=True)
    for fp in (devkit_footprint(), gy521_footprint()):
        with open(os.path.join(d, fp[1] + ".kicad_mod"), "w") as f:
            f.write(dump(fp) + "\n")


if __name__ == "__main__":
    write_symlib()
    write_fplib()
    print("wrote defuse32.kicad_sym and defuse32.pretty/")
