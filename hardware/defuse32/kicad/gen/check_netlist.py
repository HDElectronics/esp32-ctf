#!/usr/bin/env python3
"""Compare a kicad-cli netlist (and optionally the .kicad_pcb pad nets) against design.py.

Usage: python3 check_netlist.py NETLIST.net [BOARD.kicad_pcb]
Exit code 0 when everything matches.
"""
import sys

import design as D
from sexp import find, find1, parse


def netlist_map(path):
    root = parse(open(path).read())
    m = {}
    names = []
    for net in find(find1(root, "nets"), "net"):
        name = find1(net, "name")[1]
        names.append(name)
        for node in find(net, "node"):
            m[(find1(node, "ref")[1], find1(node, "pin")[1])] = name
    comps = [find1(c, "ref")[1] for c in find(find1(root, "components"), "comp")]
    return m, names, comps


def expected():
    e = {}
    for p in D.PARTS:
        for pin, net in p["nets"].items():
            e[(p["ref"], pin)] = net
    return e


def main():
    got, names, comps = netlist_map(sys.argv[1])
    exp = expected()
    bad = 0
    for k, net in sorted(exp.items()):
        g = got.get(k)
        if net is None:
            if g is not None and not g.startswith("unconnected-"):
                print("NC pin connected:", k, g)
                bad += 1
        elif g != net:
            print("MISMATCH", k, "expected", net, "got", g)
            bad += 1
    refs = sorted(p["ref"] for p in D.PARTS)
    if sorted(set(comps)) != refs:
        print("component set differs:", set(comps) ^ set(refs))
        bad += 1
    # rev 1: peripheral rail and microSD
    if "3V3" in names:
        print("rev 1: net 3V3 still exists (all peripheral 3.3 V must be on 3V3P)")
        bad += 1
    if (got.get(("U1", "1")) or "unconnected-").startswith("unconnected-") is False:
        print("rev 1: DevKit 3V3 pin (U1.1) feeds", got.get(("U1", "1")))
        bad += 1
    rev1 = {("U5", "3"): "5V", ("U5", "2"): "3V3P", ("U5", "1"): "GND", ("U1", "34"): "SD_CS",
            ("R8", "1"): "SD_CS", ("R8", "2"): "GND", ("U2", "6"): "SD_DET", ("A2", "7"): "SD_DET",
            ("A2", "1"): "3V3P", ("A2", "3"): "SCK", ("A2", "4"): "MISO", ("A2", "5"): "MOSI", ("A2", "6"): "SD_CS",
            ("A1", "1"): "3V3P", ("U2", "9"): "3V3P", ("U3", "9"): "3V3P"}
    rev1.update({("J%d1" % n, "2"): "3V3P" for n in range(1, 7)})
    for k, net in sorted(rev1.items()):
        if got.get(k) != net:
            print("rev 1 MISMATCH", k, "expected", net, "got", got.get(k))
            bad += 1
    # rev 1b: no keypad/wire line on the output-only GPA7/GPB7; ENC_SW on GPIO39; MPU INT NC
    rev1b = {("U2", "7"): "COL4", ("J32", "8"): "COL4", ("U3", "7"): "WA6", ("J42", "6"): "WA6",
             ("U1", "4"): "ENC_SW", ("R9", "2"): "ENC_SW", ("R9", "1"): "3V3P", ("J12", "3"): "ENC_SW",
             ("U2", "28"): "U2_GPA7", ("U2", "8"): "U2_GPB7", ("U3", "28"): "U3_GPA7", ("U3", "8"): "U3_GPB7",
             ("J10", "1"): "U2_GPA7", ("J10", "2"): "U2_GPB7", ("J10", "3"): "U3_GPA7", ("J10", "4"): "U3_GPB7",
             ("J10", "5"): "GND"}
    for k, net in sorted(rev1b.items()):
        if got.get(k) != net:
            print("rev 1b MISMATCH", k, "expected", net, "got", got.get(k))
            bad += 1
    if not (got.get(("A1", "8")) or "unconnected-").startswith("unconnected-"):
        print("rev 1b: GY-521 INT (A1.8) is on", got.get(("A1", "8")))
        bad += 1
    for gone in ("MPU_INT", "SPARE2", "SPARE3"):
        if gone in names:
            print("rev 1b: net", gone, "still exists")
            bad += 1
    for ref in ("U2", "U3"):   # GPA7 = pin 28, GPB7 = pin 8: only their spare nets
        for pin in ("28", "8"):
            n = got.get((ref, pin)) or ""
            if n != "%s_GP%s7" % (ref, "A" if pin == "28" else "B"):
                print("rev 1b: %s.%s (output-only) carries %s" % (ref, pin, n))
                bad += 1
    named = sorted(n for n in set(names) if not n.startswith("unconnected-"))
    print("schematic nets (%d): %s" % (len(named), " ".join(named)))
    print("components: %d" % len(comps))
    if len(sys.argv) > 2:
        import pcbnew  # noqa: E402  (only with /usr/bin/python3)
        b = pcbnew.LoadBoard(sys.argv[2])
        fps = {f.GetReference(): f for f in b.GetFootprints()}
        if sorted(fps) != refs:
            print("PCB footprint set differs:", set(fps) ^ set(refs))
            bad += 1
        for (ref, pin), net in sorted(got.items()):
            f = fps.get(ref)
            if not f:
                continue
            for pad in f.Pads():
                if pad.GetNumber() == pin and pad.GetNetname() != net:
                    print("PCB MISMATCH", ref, pin, "sch", net, "pcb", pad.GetNetname())
                    bad += 1
        print("pcb footprints: %d, pads checked against the schematic netlist" % len(fps))
        ns = b.GetDesignSettings().m_NetSettings
        want = {"Power": (0.8, 0.3), "Default": (0.25, 0.2)}
        for cls, (tw, cl) in want.items():
            nc = ns.GetNetClassByName(cls)
            g = (round(pcbnew.ToMM(nc.GetTrackWidth()), 3), round(pcbnew.ToMM(nc.GetClearance()), 3))
            if nc.GetName() != cls or g != (tw, cl):
                print("netclass", cls, "expected", (tw, cl), "got", nc.GetName(), g)
                bad += 1
        for n in ("5V", "3V3P", "GND"):
            if b.FindNet(n).GetNetClassName() != "Power":
                print("net", n, "not in netclass Power")
                bad += 1
        power = sorted(n for n in named if b.FindNet(n) and b.FindNet(n).GetNetClassName() == "Power")
        print("netclass Power: %s; every other net: Default" % " ".join(power))
    print("RESULT:", "OK" if not bad else "%d problems" % bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
