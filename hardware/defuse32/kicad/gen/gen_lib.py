#!/usr/bin/env python3
"""Generate the project-local libraries defuse32.kicad_sym and defuse32.pretty/ (rev 2).

Rev 2 uses official KiCad symbols and footprints everywhere except one symbol and two footprints.

Symbol:
  CH340C_3V3  copy of Interface_USB:CH340C with pin 4 (V3) typed power_in instead of power_out.
              At VCC = 3.3 V the datasheet ties V3 to VCC, so V3 is an input there; with the
              official pin type ERC reports two power outputs (V3 and the AMS1117 output) on 3V3.

Footprints:
  ESP32-WROOM-32E_JLC  copy of RF_Module:ESP32-WROOM-32E with the 12 thermal vias in the GND pad
              drilled 0.3 mm instead of 0.2 mm (0.6 mm pad, 0.15 mm ring): JLCPCB's 2-layer minimum
              hole is 0.3 mm. The pin-1 triangle is 0.38 mm instead of 0.5 mm and 0.07 mm further in,
              so it clears the board edge (the antenna overhangs it) and pad 1 by 0.15 mm (rev 2.1).
              Pads, antenna keep-out zone, outline and 3D model are unchanged.
  USB_C_Receptacle_HRO_TYPE-C-31-M-12_Edge  copy of Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12
              for a receptacle at the board edge, its front face design.USBC_OUT (0.6 mm) outside it:
              the silkscreen line across the front (0.25 mm in front of the face) is removed and the
              two side lines end 0.35 mm inside the edge (0.95 mm behind the face), so no silkscreen
              is clipped by the edge (DRC silk_edge_clearance). Pads, courtyard, fab outline and 3D
              model are unchanged.

(The rev 1b DevKitC/GY-521/microSD-breakout symbols and footprints are in git, tag carrier-rev1b.)

Run from anywhere:  python3 kicad/gen/gen_lib.py
"""
import os

import design as D
from sexp import Sym as S, dump, find, find1, parse
from symlib import flat

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(HERE, ".."))


def ch340c_3v3():
    s = flat("Interface_USB", "CH340C")
    old, new = "CH340C", "CH340C_3V3"
    s[1] = new
    for sub in find(s, "symbol"):
        sub[1] = new + sub[1][len(old):]
        for p in find(sub, "pin"):
            if find1(p, "number")[1] == "4":
                p[1] = S("power_in")
    for p in find(s, "property"):
        if p[1] == "Value":
            p[2] = new
        elif p[1] == "Description":
            p[2] = ("USB serial converter, UART, SOIC-16, internal oscillator, run from 3.3 V: "
                    "V3 (pin 4) tied to VCC, typed power_in (copy of Interface_USB:CH340C)")
    return s


def write_symlib():
    lib = [S("kicad_symbol_lib"), [S("version"), 20251024], [S("generator"), "kicad_symbol_editor"],
           [S("generator_version"), "10.0"], ch340c_3v3()]
    with open(os.path.join(KDIR, "defuse32.kicad_sym"), "w") as f:
        f.write(dump(lib) + "\n")


def write_fplib():
    src = open("/usr/share/kicad/footprints/RF_Module.pretty/ESP32-WROOM-32E.kicad_mod").read()
    n = src.count("(drill 0.2)")
    if n != 12 or src.count('(footprint "ESP32-WROOM-32E"') != 1:
        raise SystemExit("unexpected RF_Module:ESP32-WROOM-32E (%d 0.2 mm drills)" % n)
    out = src.replace('(footprint "ESP32-WROOM-32E"', '(footprint "ESP32-WROOM-32E_JLC"')
    out = out.replace("(drill 0.2)", "(drill 0.3)")
    # pin-1 mark: the 0.5 mm triangle at (-9.2, -6) sits on the line where the board edge runs when
    # the antenna overhangs the edge (rev 2 placement): 0.38 mm triangle, 0.07 mm in, so it keeps
    # 0.15 mm from the edge and from pad 1 (DRC silk_edge_clearance / silk_over_copper)
    mark = "(xy -9.2 -6) (xy -9.7 -6) (xy -9.2 -6.5) (xy -9.2 -6)"
    if out.count(mark) != 1:
        raise SystemExit("unexpected RF_Module:ESP32-WROOM-32E pin-1 mark")
    out = out.replace(mark, "(xy -9.2 -5.93) (xy -9.58 -5.93) (xy -9.2 -6.31) (xy -9.2 -5.93)")
    out = out.replace('(descr "', '(descr "RF_Module:ESP32-WROOM-32E with 0.3 mm thermal-via drills (JLCPCB 2-layer '
                                  'minimum hole) and a smaller pin-1 mark clear of the board edge. ', 1)
    d = os.path.join(KDIR, "defuse32.pretty")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, "ESP32-WROOM-32E_JLC.kicad_mod"), "w") as f:
        f.write(out)


USBC = "USB_C_Receptacle_HRO_TYPE-C-31-M-12"


def write_usbc():
    src = open("/usr/share/kicad/footprints/Connector_USB.pretty/%s.kicad_mod" % USBC).read()
    root = parse(src)
    keep, cut, short = [], 0, 0
    for it in root:
        if isinstance(it, list) and it and it[0] == S("fp_line") and find1(it, "layer")[1] == "F.SilkS":
            st, en = find1(it, "start"), find1(it, "end")
            if float(st[2]) == 3.9 and float(en[2]) == 3.9:   # front line
                cut += 1
                continue
            for pt in (st, en):
                if float(pt[2]) == 3.9:                  # side lines: stop 0.35 mm inside the board edge; the
                    pt[2] = round(3.65 - 0.35 - D.USBC_OUT, 3)   # face (3.65) stands USBC_OUT outside it
                    short += 1
        keep.append(it)
    if (cut, short) != (1, 2):
        raise SystemExit("unexpected %s silkscreen (%d front, %d side lines)" % (USBC, cut, short))
    keep[1] = USBC + "_Edge"
    for it in keep:
        if isinstance(it, list) and it and it[0] == S("descr"):
            it[1] = ("Connector_USB:%s, front face %.1f mm outside the board edge: front silkscreen line removed, "
                     "side lines shortened (no silkscreen clipped by the edge). " % (USBC, D.USBC_OUT)) + it[1]
        if isinstance(it, list) and it and it[0] == S("property") and it[1] == "Value":
            it[2] = USBC + "_Edge"
    with open(os.path.join(KDIR, "defuse32.pretty", USBC + "_Edge.kicad_mod"), "w") as f:
        f.write(dump(keep) + "\n")


if __name__ == "__main__":
    write_symlib()
    write_fplib()
    write_usbc()
    print("wrote defuse32.kicad_sym and defuse32.pretty/ESP32-WROOM-32E_JLC.kicad_mod, %s_Edge.kicad_mod" % USBC)
