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
    print("RESULT:", "OK" if not bad else "%d problems" % bad)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
