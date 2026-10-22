#!/usr/bin/env python3
"""Rev 2 checks: the kicad-cli netlist (and optionally the .kicad_pcb) against design.py and SPEC.md.

Usage: python3 check_netlist.py NETLIST.net [BOARD.kicad_pcb]     (the board part needs /usr/bin/python3)
Exit code 0 when everything matches.

Checks
  - every pin of every part has the net design.py gives it (stacked pins expanded), same part set
  - ESP32 GPIO map (SPEC "ESP32 pin map"), resolved through the WROOM-32E symbol's pin names
  - MCP23017 allocation (SPEC, rev 1b) and the output-only GPA7/GPB7 rule; I2C addresses
  - plate IDC headers: sizes and the rev 2 pinout rule; WS2812 chain
  - rails (3V3 vs 3V3P consumers), USB-C / CH340C / auto-reset / LIS3DH / microSD wiring
  - board: footprint set and pad nets, outline 100 x 70, holes 4 mm from the corners, net classes,
    U1 antenna region beyond the board edge
"""
import sys

import design as D
from sexp import find, find1, parse
from symlib import flat, pins as lib_pins

BAD = []


def bad(msg):
    BAD.append(msg)
    print("FAIL", msg)


def netlist_map(path):
    root = parse(open(path).read())
    m, names = {}, []
    for net in find(find1(root, "nets"), "net"):
        name = find1(net, "name")[1]
        names.append(name)
        for node in find(net, "node"):
            m[(find1(node, "ref")[1], find1(node, "pin")[1])] = name
    comps = [find1(c, "ref")[1] for c in find(find1(root, "components"), "comp")]
    return m, names, comps


def is_nc(net):
    return net is None or net.startswith("unconnected-")


# SPEC "ESP32 pin map" (fixed): GPIO -> net. None = unused/NC.
SPEC_GPIO = {21: "SDA", 22: "SCL", 35: "MCP_INT", 39: "ENC_SW", 34: "IR", 36: "LDR", 32: "TM_CLK",
             33: "TM_DIO", 25: "WS_DATA", 26: "BUZZ", 27: "SERVO_SIG", 4: "T0", 13: "T4", 14: "T6", 15: "T3",
             18: "SCK", 23: "MOSI", 19: "MISO", 5: "CS", 17: "U2TX", 16: "U2RX", 2: "SD_CS", 12: None,
             0: "IO0", 1: "U0TXD", 3: "U0RXD"}     # 0/1/3: boot + UART0 to the CH340C (rev 2)
# SPEC MCP23017 allocation (rev 1b)
SPEC_U2 = {"GPA0": "ROW1", "GPA1": "ROW2", "GPA2": "ROW3", "GPA3": "ROW4", "GPA4": "COL1", "GPA5": "COL2",
           "GPA6": "COL3", "GPB6": "COL4", "GPB0": "SIM1", "GPB1": "SIM2", "GPB2": "SIM3", "GPB3": "SIM4",
           "GPB4": "KEY", "GPB5": "SD_DET", "GPA7": "U2_GPA7", "GPB7": "U2_GPB7"}
SPEC_U3 = {"GPA0": "WA1", "GPA1": "WA2", "GPA2": "WA3", "GPA3": "WA4", "GPA4": "WA5", "GPB6": "WA6",
           "GPB0": "WB1", "GPB1": "WB2", "GPB2": "WB3", "GPB3": "WB4", "GPB4": "WB5", "GPB5": "WB6",
           "GPA6": "ENC_A", "GPA5": "ENC_B", "GPA7": "U3_GPA7", "GPB7": "U3_GPB7"}
# SPEC rev 2 plate connector sizes (rows of the 2-row IDC header) and rev 1 Jn_B signal sets
SPEC_ROWS = {1: 5, 2: 6, 3: 8, 4: 10, 5: 7, 6: 10}
SPEC_SIGNALS = {
    1: ["ENC_A", "ENC_B", "ENC_SW"],
    2: ["TM_CLK", "TM_DIO", "BUZZ-", "5V"],
    3: ["ROW1", "ROW2", "ROW3", "ROW4", "COL1", "COL2", "COL3", "COL4"],
    4: ["WA1", "WA2", "WA3", "WA4", "WA5", "WA6", "WB1", "WB2", "WB3", "WB4", "WB5", "WB6"],
    5: ["U2TX", "U2RX", "SCK", "MOSI", "MISO", "CS"],
    6: ["T0", "T4", "T6", "T3", "LDR", "IR", "SIM1", "SIM2", "SIM3", "SIM4", "SERVO_SIG"],
}


def pin_by_name(lib, sym):
    """{pin name: pin number} of a library symbol."""
    return {p["name"]: p["num"] for p in lib_pins(flat(lib, sym))}


def gpio_pins():
    """GPIO number -> WROOM-32E pin number, from the official symbol's pin names."""
    out = {}
    for name, num in pin_by_name("RF_Module", "ESP32-WROOM-32E").items():
        n = name.split("/")[-1]
        if name == "SENSOR_VP":
            out[36] = num
        elif name == "SENSOR_VN":
            out[39] = num
        elif n.startswith("IO"):
            out[int(n[2:])] = num
    return out


def expect(got, ref, pin, net, what):
    g = got.get((ref, pin))
    if net is None:
        if not is_nc(g):
            bad("%s: %s.%s should be NC, is %s" % (what, ref, pin, g))
    elif g != net:
        bad("%s: %s.%s expected %s, got %s" % (what, ref, pin, net, g))


def check_schematic(got, names, comps):
    # 1. design.py
    for p in D.PARTS:
        for pin, net in D.pad_nets(p).items():
            expect(got, p["ref"], pin, net, "design.py")
    refs = sorted(p["ref"] for p in D.PARTS)
    if sorted(set(comps)) != refs:
        bad("component set differs: %s" % (set(comps) ^ set(refs)))

    # 2. ESP32 pin map
    gp = gpio_pins()
    for g, net in SPEC_GPIO.items():
        expect(got, "U1", gp[g], net, "SPEC GPIO%d" % g)
    for n in ("1", "15", "38", "39"):
        expect(got, "U1", n, "GND", "U1 GND pads")
    expect(got, "U1", "2", "3V3", "U1 VDD")
    expect(got, "U1", "3", "EN", "U1 EN")

    # 3. MCP23017 allocation + addresses + output-only rule
    mcp = pin_by_name("Interface_Expansion", "MCP23017x-x-SO")
    for ref, alloc in (("U2", SPEC_U2), ("U3", SPEC_U3)):
        for name, net in alloc.items():
            expect(got, ref, mcp[name], net, "SPEC %s %s" % (ref, name))
        for name in ("GPA7", "GPB7"):
            n = got.get((ref, mcp[name]))
            users = sorted(r for (r, _), v in got.items() if v == n and r not in (ref, "J10"))
            if users:
                bad("rev 1b: %s %s (output-only) also reaches %s" % (ref, name, users))
        expect(got, ref, mcp["SCK"], "SCL", ref + " SCL")
        expect(got, ref, mcp["SDA"], "SDA", ref + " SDA")
        expect(got, ref, mcp["INTA"], "MCP_INT", ref + " INTA")
        expect(got, ref, mcp["INTB"], "MCP_INT", ref + " INTB")
        expect(got, ref, mcp["~{RESET}"], "3V3P", ref + " RESET")
        expect(got, ref, mcp["V_{DD}"], "3V3P", ref + " VDD")
    for ref, a0 in (("U2", "GND"), ("U3", "3V3P")):          # 0x20, 0x21
        expect(got, ref, mcp["A0"], a0, ref + " A0")
        expect(got, ref, mcp["A1"], "GND", ref + " A1")
        expect(got, ref, mcp["A2"], "GND", ref + " A2")
    for i, net in enumerate(("U2_GPA7", "U2_GPB7", "U3_GPA7", "U3_GPB7", "GND")):
        expect(got, "J10", str(i + 1), net, "J_SPARE")
    expect(got, "J8", "1", "KEY", "J_KEY")
    expect(got, "J8", "2", "GND", "J_KEY")
    for i, net in enumerate(("GND", "5V", "SERVO_SIG")):
        expect(got, "J9", str(i + 1), net, "J_SERVO")

    # 4. plate connectors (rev 2 rule) + WS2812 chain
    chain_in = {1: "LDI", 2: "LDO1", 3: "LDO2", 4: "LDO3", 5: "LDO4", 6: "LDO5"}
    chain_out = {1: "LDO1", 2: "LDO2", 3: "LDO3", 4: "LDO4", 5: "LDO5", 6: None}
    for n, rows in SPEC_ROWS.items():
        ref = "J%d" % n
        pins = sorted(int(pp) for (r, pp) in got if r == ref)
        if pins != list(range(1, 2 * rows + 1)):
            bad("%s: expected a 2x%d header, pads %s" % (ref, rows, pins))
        want = ["5V", "GND", "3V3P", "SDA", "SCL", chain_in[n], chain_out[n]] + SPEC_SIGNALS[n]
        want += ["GND"] * (2 * rows - len(want))
        for i, net in enumerate(want):
            expect(got, ref, str(i + 1), net, "%s pinout rule" % ref)
    expect(got, "U4", "2", "WS_DATA", "WS2812 buffer in")
    expect(got, "U4", "4", "WS_5V", "WS2812 buffer out")
    expect(got, "U4", "1", "GND", "WS2812 buffer OE")
    expect(got, "U4", "5", "5V", "WS2812 buffer VCC")
    expect(got, "R1", "1", "WS_5V", "R1")
    expect(got, "R1", "2", "LDI", "R1")

    # 5. rails
    expect(got, "U6", "3", "5V", "AMS1117 in")
    expect(got, "U6", "2", "3V3", "AMS1117 out")
    expect(got, "U5", "1", "5V", "AP2112K in")
    expect(got, "U5", "3", "5V", "AP2112K EN")
    expect(got, "U5", "5", "3V3P", "AP2112K out")
    on3v3 = sorted({r for (r, _), v in got.items() if v == "3V3"})
    allowed = {"U1", "U6", "U7", "C8", "C9", "C10", "C12", "C13", "R10", "R11"}
    if set(on3v3) - allowed:
        bad("3V3 (ESP32 + CH340C only) also feeds %s" % sorted(set(on3v3) - allowed))
    for ref, pin in (("U8", "1"), ("U8", "14"), ("J11", "4"), ("U2", "9"), ("U3", "9"), ("R2", "1"), ("R3", "1"),
                     ("R4", "1"), ("R5", "1"), ("R9", "1")):
        expect(got, ref, pin, "3V3P", "3V3P consumer")
    expect(got, "C1", "1", "5V", "5V bulk")

    # 6. USB-C, ESD, fuse, CH340C, auto-reset
    for pin in ("A4", "A9", "B4", "B9"):
        expect(got, "J7", pin, "VBUS", "USB-C VBUS")
    for pin in ("A1", "A12", "B1", "B12", "SH"):
        expect(got, "J7", pin, "GND", "USB-C GND")
    for pin, net in (("A5", "CC1"), ("B5", "CC2"), ("A6", "USB_DP"), ("B6", "USB_DP"), ("A7", "USB_DM"),
                     ("B7", "USB_DM")):
        expect(got, "J7", pin, net, "USB-C")
    for r, cc in (("R14", "CC1"), ("R15", "CC2")):
        expect(got, r, "1", cc, "CC 5.1k")
        expect(got, r, "2", "GND", "CC 5.1k")
    expect(got, "F1", "1", "VBUS", "PTC")
    expect(got, "F1", "2", "5V", "PTC")
    for pin, net in (("1", "USB_DP"), ("6", "USB_DP"), ("3", "USB_DM"), ("4", "USB_DM"), ("5", "VBUS"), ("2", "GND")):
        expect(got, "U9", pin, net, "USBLC6")
    for pin, net in (("5", "USB_DP"), ("6", "USB_DM"), ("2", "U0RXD"), ("3", "U0TXD"), ("13", "DTR"), ("14", "RTS"),
                     ("16", "3V3"), ("4", "3V3"), ("1", "GND")):
        expect(got, "U7", pin, net, "CH340C")
    for q, b, e, c in (("Q2", "AR_DTR_B", "RTS", "EN"), ("Q3", "AR_RTS_B", "DTR", "IO0")):
        expect(got, q, "1", b, "auto-reset")
        expect(got, q, "2", e, "auto-reset")
        expect(got, q, "3", c, "auto-reset")
    expect(got, "R12", "1", "DTR", "auto-reset")
    expect(got, "R13", "1", "RTS", "auto-reset")

    # 7. LIS3DH (0x19, I2C), microSD
    for pin, net in (("4", "SCL"), ("6", "SDA"), ("7", "LIS_SA0"), ("8", "3V3P"), ("9", None), ("11", None)):
        expect(got, "U8", pin, net, "LIS3DH")
    expect(got, "R20", "1", "3V3P", "LIS3DH SA0 high")
    expect(got, "R20", "2", "LIS_SA0", "LIS3DH SA0 high")
    for pin, net in (("2", "SD_CS"), ("3", "MOSI"), ("5", "SCK"), ("7", "MISO"), ("9", "SD_DET"), ("10", "GND")):
        expect(got, "J11", pin, net, "microSD")
    for r, net in (("R16", "MISO"), ("R17", "SD_DAT1"), ("R18", "SD_DAT2"), ("R19", "SD_DET")):
        expect(got, r, "1", "3V3P", "microSD pull-up")
        expect(got, r, "2", net, "microSD pull-up")
    expect(got, "R8", "1", "SD_CS", "GPIO2 pull-down")
    expect(got, "R8", "2", "GND", "GPIO2 pull-down")

    for gone in ("DK_5V", "MPU_INT", "SPARE2", "SPARE3"):
        if gone in names:
            bad("old net %s still exists" % gone)
    named = sorted(n for n in set(names) if not n.startswith("unconnected-"))
    print("schematic nets (%d): %s" % (len(named), " ".join(named)))
    print("components: %d" % len(comps))
    return named


def check_board(path, got, named):
    import pcbnew  # noqa: E402  (only with /usr/bin/python3)
    b = pcbnew.LoadBoard(path)
    fps = {f.GetReference(): f for f in b.GetFootprints()}
    refs = sorted(p["ref"] for p in D.PARTS)
    if sorted(fps) != refs:
        bad("PCB footprint set differs: %s" % (set(fps) ^ set(refs)))
    for p in D.PARTS:
        f = fps.get(p["ref"])
        if f and f.GetFPIDAsString() != p["fp"]:
            bad("%s footprint %s, design.py %s" % (p["ref"], f.GetFPIDAsString(), p["fp"]))
    for (ref, pin), net in sorted(got.items()):
        f = fps.get(ref)
        if not f:
            continue
        for pad in f.Pads():
            if pad.GetNumber() == pin and pad.GetNetname() != net:
                bad("PCB %s.%s sch %s pcb %s" % (ref, pin, net, pad.GetNetname()))
    print("pcb footprints: %d, pads checked against the schematic netlist" % len(fps))

    # outline + holes
    bb = b.GetBoardEdgesBoundingBox()
    w, h = pcbnew.ToMM(bb.GetWidth()), pcbnew.ToMM(bb.GetHeight())
    if abs(w - D.BOARD_W) > 0.2 or abs(h - D.BOARD_H) > 0.2:      # bbox includes the 0.1 mm line width
        bad("board outline %.2f x %.2f mm" % (w, h))
    x0, y0 = pcbnew.ToMM(bb.GetLeft()) + 0.05, pcbnew.ToMM(bb.GetTop()) + 0.05
    i = D.HOLE_INSET
    for ref, (hx, hy) in (("H1", (i, i)), ("H2", (D.BOARD_W - i, i)), ("H3", (i, D.BOARD_H - i)),
                          ("H4", (D.BOARD_W - i, D.BOARD_H - i))):
        f = fps[ref]
        pos = f.GetPosition()
        dx, dy = pcbnew.ToMM(pos.x) - x0 - hx, pcbnew.ToMM(pos.y) - y0 - hy
        drill = pcbnew.ToMM(list(f.Pads())[0].GetDrillSize().x)
        if abs(dx) > 0.01 or abs(dy) > 0.01 or abs(drill - 3.2) > 0.01:
            bad("%s at offset (%.2f, %.2f), drill %.2f" % (ref, dx, dy, drill))
    # U1: antenna end toward -x, the antenna region (footprint y < -6.56) beyond the board edge x = 0
    u1 = fps["U1"]
    if round(u1.GetOrientationDegrees()) != 90:
        bad("U1 orientation %s (antenna must point to -x)" % u1.GetOrientationDegrees())
    edge = pcbnew.ToMM(u1.GetPosition().x) - 6.56 - x0
    if edge > 0.01:
        bad("U1 antenna-region boundary %.2f mm inside the board edge" % edge)

    # net classes
    ns = b.GetDesignSettings().m_NetSettings
    for cls, (tw, cl) in D.NETCLASS.items():
        nc = ns.GetNetClassByName(cls)
        g = (round(pcbnew.ToMM(nc.GetTrackWidth()), 3), round(pcbnew.ToMM(nc.GetClearance()), 3))
        if nc.GetName() != cls or g != (tw, cl):
            bad("netclass %s expected %s got %s %s" % (cls, (tw, cl), nc.GetName(), g))
    for n in D.POWER_NETS:
        if b.FindNet(n).GetNetClassName() != "Power":
            bad("net %s not in netclass Power" % n)
    power = sorted(n for n in named if b.FindNet(n) and b.FindNet(n).GetNetClassName() == "Power")
    print("netclass Power: %s; every other net: Default" % " ".join(power))
    print("board %.1f x %.1f mm, holes H1-H4 %.0f mm from the corners, U1 antenna beyond x = 0" % (w - 0.1, h - 0.1, i))


def main():
    got, names, comps = netlist_map(sys.argv[1])
    named = check_schematic(got, names, comps)
    if len(sys.argv) > 2:
        check_board(sys.argv[2], got, named)
    print("RESULT:", "OK" if not BAD else "%d problems" % len(BAD))
    sys.exit(1 if BAD else 0)


if __name__ == "__main__":
    main()
