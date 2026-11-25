#!/usr/bin/env python3
"""Standards pass (kicad/README.md "Standards pass (2026-11-25)"): the fixes the standards audit
(gen/std_audit.py, gen/pcb_audit.py, the AirQuality-style review) asked for, on the finished board.
Board rev 3 -> rev 3.1, schematic rev 2 -> 2.1. Runs after `gen/polish.py all`; no existing footprint
is moved, rotated or swapped; the only connection changes are the schematic rev 2.1 parts R21 / R22
(DRC parity against the regenerated schematic). Run from hardware/defuse32/kicad/ with KiCad's Python:

  /usr/bin/python3 gen/std_fixes.py            # all steps, refill, save, KiCad DRC (~15 min)
  /usr/bin/python3 gen/std_fixes.py --dry-run  # stage 1 only, nothing saved
(D32_BOARD=/path/copy.kicad_pcb works on a copy; D32_STAGE1_COPY=/path/out.kicad_pcb also keeps the board as stage 1
left it, the board the round-2 edits are written on.)

Every explicit edit looks for the exact geometry it replaces (board mm, 2 um) and does nothing when
that geometry is gone and the new one is there; rule steps act only on what is still wrong. Stage 1
(the steps up to "copper" below: maze re-routes, widening, stitching) runs once, on the rev 3 board: on a
board whose title block already says rev 3.1 it is skipped, because the maze tools are not repeatable on
their own output; round 2 (explicit edits and rules that check their own geometry) always runs, so a
second run changes nothing. Each
change is checked with polish.py's clearance model (net-class clearances, holes, edge); a GND
stitching via (no track on it) in the way is deleted and the pours are stitched again at the end
(polish.stitch_islands, with SMD pads kept free of vias). KiCad's DRC has the last word. The project
file is kept as it is (the board is saved with pcbnew.SaveBoard and the .kicad_pro restored byte for
byte).

Steps (in this order, see main()):
  tracks    explicit edits (EDITS): off-angle segments made octilinear (U1 3V3/GND to C10/C9, the
            USB-C GND legs, J6 pin 20, the LIS3DH GND via, LDR, RTS, T6, U3_GPA7), acute junctions
            removed (C12/U7 3V3, C2/C19 3V3P, C15 3V3P overlap), a router micro-loop (IO0 at C8),
            the jogs a group rip-up removed (JOG_EDITS);
  parts     schematic rev 2.1 (new_parts): Q1 / R7 values and fields from the netlist; R21 and R22
            added at their design.py spots and joined to their nets (join_pad, JOIN_PATHS);
  routing   router micro-loops collapsed (loops); the 5V feed F1 -> C6 / U5 -> C7 / U6 and the
            polish jog tools with the pours lifted (straighten); the rings their maze re-routes leave
            collapsed again and only local moves tried after that; 5V widened where legal (widen);
  fanouts   GND fan-outs (via + one stub from a GND SMD pad) whose stub is off-angle or whose via
            touches an SMD pad: rebuilt octilinear, the via >= 0.15 mm from every SMD pad;
            stitching vias that touch an SMD pad (solder wicking) are deleted; the MCP_INT via inside
            R4 pad 2 moves out of the pad (r4_via);
  silk      labels for the new parts (new_labels); J5's label as "J5  M5 PROBE" where a legal spot
            exists; legend and title block rev 3.1; three global fiducials (board-only, JLCPCB
            Standard PCBA, nearest free spot to FIDUCIALS); function labels (EN at SW1, BOOT at SW2,
            G + S at J9 pins 1-3, OUT at J10). (silk_strokes, widening the library's 0.12 mm
            footprint strokes to 0.15 mm, is off: WIDEN_SILK);
  returns   a GND via within RETURN_MAX of every layer change of a fast net (USB, SPI incl. the
            probe CS, WS2812 data chain LDI..LDO5), where one is legal;
  copper    3V3 / 3V3P copper on F.Cu round the AMS1117 tabs (U6, U5, D04); F.Cu pour / via
            keep-out under the LIS3DH package interior (ST: no copper or vias on the top side under
            the device; paste stays 1:1, no confirmed TN0018 aperture rule); edge stitching (GND vias
            within EDGE_MAX of every point 1.5 mm inside the edge, where legal), island stitching,
            prune, refill (islands removed), save, DRC;
  round 2   (final check of 2026-11-25, N03-N11, and the jog / corner / gap work; on the saved stage 1 board):
            stray segments inside one pad or via deleted (strays); tight corners widened to one 45 deg
            chamfer of at least 0.45 mm where that fits and makes no jog (corners); the explicit edits R2
            (hand-designed runs: jogs removed with their neighbours and vias, hairpins, cap-only joins, the
            bare strips of N06, second GND vias); track ends on the rim of a through-hole pad run on along
            their own line into the pad (pad_joins); the four GND zones 0.5 mm inside the two long edges, TAB_U6 down to IO0,
            thermal reliefs for C19 / C2 / C8 pad 1 in the tab copper (zone_edits); R21's label, "S" at J9,
            J11's leader (silk_edits); return vias, edge and island stitching again, refill, save, DRC.
"""
import math
import os
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import design as D  # noqa: E402
import polish as PL  # noqa: E402
from polish import MM, TOMM, F, B, IN1, IN2, uid, pt, V, norm, sub, add, mul, unit, dot, Ctx, Txn, Obstacles  # noqa: E402

R = PL.R
BOARD = R.BOARD
DRY = "--dry-run" in sys.argv
REVISION = "3.1"
TB_DATE = "2026-11-25"
LEGEND_OLD, LEGEND_NEW = "rev 3  2026-10", "rev 3.1  2026-11"
TOL = 0.002                                 # mm, geometry match
LOG = []


def log(s):
    LOG.append(s)
    print(s, flush=True)


def P(x, y):
    return pt(R.P(x, y))


def bm(p):
    return (round(TOMM(int(p[0])) - PL.OX, 3), round(TOMM(int(p[1])) - PL.OY, 3))


# ------------------------------------------------------------------------------ explicit track edits
# (id, net, layer, old [(a, b)], new [(a, b, width mm)], via moves [(old xy, new xy)], why); board mm
EDITS = [
    ("U1-3V3", "3V3", "F.Cu",
     [((2.57, 43.75), (2.78, 46.0)), ((2.78, 46.0), (2.95, 48.1)), ((6.124, 48.1), (2.95, 48.1))],
     [((2.78, 43.75), (2.78, 46.0), 0.6), ((2.78, 46.0), (2.78, 48.1), 0.6), ((6.124, 48.1), (2.78, 48.1), 0.6)], [],
     "U1 pin 2 - C10 - C9 was 4.6-5.3 deg off vertical: one vertical line x 2.78 through the three pads"),
    ("U1-GND", "GND", "F.Cu",
     [((1.3, 43.75), (1.22, 46.0)), ((1.22, 46.0), (1.05, 48.1)), ((1.05, 48.1), (1.1, 49.8))],
     [((1.1, 43.75), (1.1, 46.0), 0.6), ((1.1, 46.0), (1.1, 48.1), 0.6), ((1.1, 48.1), (1.1, 49.8), 0.6)], [],
     "U1 pin 1 - C10 - C9 - GND via was 1.7-4.6 deg off vertical: one vertical line x 1.1 to the via"),
    ("J7-GND-top", "GND", "F.Cu", [((92.31, 46.25), (93.22, 45.18))], [((92.15, 46.25), (93.22, 45.18), 0.4)], [],
     "USB-C A12/B1 to the shell leg: 49.6 deg -> 45 deg (start moved 0.16 mm inside the pad)"),
    ("J7-GND-bot", "GND", "F.Cu", [((92.31, 52.75), (93.22, 53.82))], [((92.15, 52.75), (93.22, 53.82), 0.4)], [],
     "USB-C A1/B12 to the shell leg: 49.6 deg -> 45 deg"),
    ("U9-GND", "GND", "F.Cu", [((86.66, 49.5), (85.6, 49.4))], [((86.66, 49.5), (85.6, 49.5), 0.4)],
     [((85.6, 49.4), (85.6, 49.5))], "U9 GND fan-out 5.4 deg off: via 0.1 mm down onto the pad's centre line"),
    ("U8-GND", "GND", "F.Cu", [((36.2, 35.5), (35.9, 36.0))], [((36.2, 35.5), (35.7, 36.0), 0.25)],
     [((35.9, 36.0), (35.7, 36.0))], "LIS3DH pin 5 GND via: 59 deg -> 45 deg (via 0.2 mm left)"),
    ("J6-20-GND", "GND", "F.Cu", [((92.56, 15.14), (93.83, 13.1))], [((92.56, 15.14), (92.56, 13.1), 0.4)],
     [((93.83, 13.1), (92.56, 13.1))], "J6 pin 20 GND stub: 58 deg against the pin-19 link and 13 deg off-angle -> straight up"),
    ("LDR", "LDR", "F.Cu", [((6.46, 45.6), (7.395, 45.624))], [((6.46, 45.6), (7.371, 45.6), 0.2)],
     [((7.395, 45.624), (7.371, 45.6))], "LDR 1.4 deg off horizontal: via 0.024 mm onto the line (B.Cu leg stays 45 deg)"),
    ("RTS", "RTS", "F.Cu", [((81.533, 34.858), (81.492, 36.858)), ((81.492, 36.858), (79.892, 38.458))],
     [((81.533, 34.858), (81.533, 36.817), 0.2), ((81.533, 36.817), (79.892, 38.458), 0.2)], [],
     "RTS 1.2 deg off vertical (and an 88.8 deg junction): vertical kept on x 81.533"),
    ("T6", "T6", "F.Cu", [((81.097, 38.12), (80.756, 38.481)), ((80.756, 38.481), (80.756, 41.678))],
     [((81.097, 38.12), (80.756, 38.461), 0.2), ((80.756, 38.461), (80.756, 41.678), 0.2)], [],
     "T6 1.6 deg off 45: corner 0.02 mm up"),
    ("U3_GPA7", "U3_GPA7", "B.Cu", [((28.932, 19.474), (29.382, 19.624)), ((29.382, 19.624), (29.532, 19.774))],
     [((28.932, 19.474), (29.232, 19.474), 0.2), ((29.232, 19.474), (29.532, 19.774), 0.2)], [],
     "U3_GPA7 18.4 deg off at its via: leaves the via horizontally, then the 45 deg piece it had"),
    ("C12-3V3", "3V3", "F.Cu", [((75.7, 40.525), (75.4, 40.825)), ((77.555, 40.525), (75.7, 40.525)),
                                ((75.4, 40.825), (76.59, 40.825)), ((76.59, 40.825), (77.563, 41.798))],
     [((75.4, 40.825), (77.555, 40.825), 0.6), ((77.563, 41.2), (77.563, 41.798), 0.6)], [],
     "C12 pin 1: two 3V3 tracks met at 45 deg in the pad: one straight track C12 - U7 pin 16, the branch leaves pin 16 downwards"),
    ("C2-3V3P", "3V3P", "F.Cu", [((60.575, 52.125), (60.45, 52.0)), ((60.575, 54.4), (60.575, 52.125))],
     [((60.575, 54.4), (60.575, 52.0), 0.6)], [],
     "C19 - C2 pin 1: 45 deg hop into the pad centre (acute junction): straight up to the C2 - U5 track (90 deg T)"),
    ("C15-3V3P", "3V3P", "F.Cu", [((40.825, 32.625), (41.075, 32.375)), ((41.4, 32.4), (41.5, 32.4)),
                                  ((41.5, 32.4), (41.85, 32.05)), ((41.075, 32.375), (41.075, 30.925)),
                                  ((41.05, 32.4), (41.4, 32.4))],
     [((41.075, 30.925), (41.075, 31.8), 0.6), ((41.075, 31.8), (41.325, 32.05), 0.6), ((41.325, 32.05), (41.85, 32.05), 0.6),
      ((41.05, 32.4), (41.5, 32.4), 0.25)], [],
     "C15 pin 1: a 0.6 mm 3V3P track ran back over the 0.25 mm LIS3DH supply (0 deg junctions): the 0.6 mm run turns into C15's"
     " centre, the 0.25 mm run ends in the pad"),
    ("IO0-loop", "IO0", "F.Cu", [((56.748, 45.154), (59.898, 45.154)), ((59.898, 45.154), (59.948, 45.104)),
                                 ((59.948, 45.104), (59.948, 45.054)), ((59.948, 45.054), (59.898, 45.004)),
                                 ((59.898, 45.004), (59.848, 45.004)), ((59.848, 45.004), (59.798, 45.054)),
                                 ((59.798, 45.054), (59.798, 45.104)), ((59.798, 45.104), (60.998, 46.304))],
     [((56.748, 45.154), (59.848, 45.154), 0.2), ((59.848, 45.154), (60.998, 46.304), 0.2)], [],
     "IO0 below C8: a 0.15 mm router loop of seven 0.05 mm segments -> one corner"),
]
# Jogs removed by the group rip-up search (scratch jogsearch.py, the jogged run and its nearest neighbouring
# runs ripped up and routed again jog-free by polish.route_run, every order tried): exact old / new geometry.
JOG_EDITS = [
    ("SCL-J4", [("MCP_INT", "B.Cu", (10.0937, 40.8248), (13.7262, 44.4573)), ("MCP_INT", "B.Cu", (13.7262, 44.4573), (13.7262, 49.5126)),
                ("MCP_INT", "B.Cu", (13.775, 49.7626), (13.775, 51.6126)), ("SCL", "B.Cu", (14.3821, 29.6647), (14.3821, 63.0123)),
                ("SCL", "B.Cu", (14.3821, 63.0123), (15.1645, 63.7947)), ("SCL", "B.Cu", (15.1645, 63.7947), (16.8747, 63.7947)),
                ("SCL", "B.Cu", (16.8747, 63.7947), (18.18, 65.1))],
     [("MCP_INT", "B.Cu", 0.2, [(10.2437, 41.0748), (13.5437, 44.3748), (13.5437, 49.2748)]),
      ("MCP_INT", "B.Cu", 0.2, [(13.7762, 49.7626), (13.7762, 51.3626)]),
      ("SCL", "B.Cu", 0.2, [(14.4736, 29.7631), (14.1736, 30.0631), (14.1736, 45.0131)]),
      ("SCL", "F.Cu", 0.2, [(14.1736, 45.0131), (15.4236, 45.0131)]),
      ("SCL", "B.Cu", 0.2, [(15.4236, 45.0131), (15.4236, 60.6631), (17.0236, 62.2631), (17.0236, 64.4631), (17.4236, 64.8631)])],
     [("SCL", (14.1736, 45.0131)), ("SCL", (15.4236, 45.0131))],
     "SCL 1.21 mm jog between J4 pins 3/4: SCL and the two MCP_INT runs beside it routed again jog-free (SCL hops to F.Cu below U1 for 1.25 mm, 2 vias)"),
    ("SCK-bus", [("SCK", "B.Cu", (34.142, 23.4281), (35.1474, 23.4281)), ("SCK", "B.Cu", (35.1474, 23.4281), (39.8748, 18.7007)),
                 ("SCK", "B.Cu", (39.8748, 17.2693), (39.8748, 18.7007)), ("SCK", "B.Cu", (39.8748, 17.2693), (43.5627, 13.5814)),
                 ("SCK", "B.Cu", (43.5627, 13.5814), (44.2485, 13.5814)), ("SCK", "B.Cu", (44.2485, 13.5814), (44.5985, 13.9315)),
                 ("SCK", "B.Cu", (44.5985, 13.9315), (44.5985, 16.3819)), ("SCK", "B.Cu", (44.5985, 16.3819), (52.1999, 23.9832)),
                 ("SCK", "B.Cu", (50.8828, 45.0556), (50.8828, 57.9513)), ("SCK", "B.Cu", (50.8828, 45.0556), (52.1999, 43.7385)),
                 ("SCK", "B.Cu", (52.1999, 23.9832), (52.1999, 43.7385)), ("U2_GPA7", "B.Cu", (52.6107, 20.4228), (52.6107, 44.4818))],
     [("SCK", "B.Cu", 0.2, [(34.392, 23.2781), (36.042, 23.2781), (39.892, 19.4281), (39.892, 17.2281), (43.792, 13.3281),
                            (45.092, 13.3281), (45.142, 13.3781), (45.142, 15.5781), (52.492, 22.9281), (52.492, 41.0781),
                            (50.892, 42.6781), (50.892, 57.6781)]),
      ("U2_GPA7", "B.Cu", 0.2, [(52.7432, 20.6728), (52.9932, 20.9228), (52.9932, 28.3228), (56.6932, 32.0228)]),
      ("U2_GPA7", "F.Cu", 0.2, [(56.6932, 32.0228), (55.6432, 33.0728), (55.2432, 33.0728)]),
      ("U2_GPA7", "B.Cu", 0.2, [(55.2432, 33.0728), (55.2432, 41.6728), (52.6432, 44.2728)])],
     [("U2_GPA7", (55.2432, 33.0728)), ("U2_GPA7", (56.6932, 32.0228))],
     "SCK jogs at (50.88, 45.06) and (39.87, 17.27): SCK and U2_GPA7 beside it routed again jog-free (U2_GPA7 hops to F.Cu under the buzzer driver, 2 vias)"),
]
TRUNK = []                                  # 5V trunk F1 -> U5/U6 inputs (D03)


def find_track(board, net, layer, a, b):
    for t in board.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetNetname() != net or board.GetLayerName(t.GetLayer()) != layer:
            continue
        s, e = bm(pt(t.GetStart())), bm(pt(t.GetEnd()))
        if (abs(s[0] - a[0]) < TOL and abs(s[1] - a[1]) < TOL and abs(e[0] - b[0]) < TOL and abs(e[1] - b[1]) < TOL) or \
                (abs(s[0] - b[0]) < TOL and abs(s[1] - b[1]) < TOL and abs(e[0] - a[0]) < TOL and abs(e[1] - a[1]) < TOL):
            return t
    return None


def find_via(board, net, p):
    for v in board.GetTracks():
        if v.GetClass() == "PCB_VIA" and v.GetNetname() == net:
            q = bm(pt(v.GetPosition()))
            if abs(q[0] - p[0]) < TOL and abs(q[1] - p[1]) < TOL:
                return v
    return None


def pure_stitch(board, v):
    """A GND via no track ends on (island / grid / return stitching): free to delete."""
    if v.GetClass() != "PCB_VIA" or v.GetNetname() != "GND":
        return False
    return not any(t.GetClass() == "PCB_TRACK" and t.GetNetname() == "GND" and (v.HitTest(t.GetStart(), 0) or v.HitTest(t.GetEnd(), 0))
                   for t in board.GetTracks())


def resolve(ctx, txn, mark, label):
    """Delete stitching vias the changes since mark run into; True if no other conflict is left."""
    for _ in range(8):
        bad = txn.conflicts(mark)
        if not bad:
            return True
        byuid = {uid(t): t for t in ctx.board.GetTracks() if t.GetClass() == "PCB_VIA"}
        gone = {uid(t) for t in txn.dele}

        def via_of(e):
            if e is None:
                return None
            if len(e) == 2:                                  # ("hole", uuid): hole to hole
                v = byuid.get(e[1])
            else:
                v = e[7] if e[6] == "via" else None
            return v if v is not None and uid(v) not in gone and pure_stitch(ctx.board, v) else None
        vias = {}
        others = []
        for it, e in bad:
            v = via_of(e)
            if v is not None:
                vias[uid(v)] = v
            else:
                others.append((it, e))
        if others:
            it, e = others[0]
            log("  %s: conflict with %s" % (label, PL.describe(e) if e is not None else "edge"))
            return False
        for v in vias.values():
            txn.apply([("del", v)])
            log("  %s: stitching via at %s deleted (in the way)" % (label, bm(pt(v.GetPosition()))))
    return False


def apply_edits(board, edits, kind):
    done = 0
    for eid, net, layer, old, new, vmoves, why in edits:
        ctx = Ctx(board)
        olds = [find_track(board, net, layer, a, b) for a, b in old]
        news = [find_track(board, net, layer, a, b) for a, b, w in new]
        vold = [find_via(board, net, a) for a, b in vmoves]
        if all(t is None for t in olds) and all(t is not None for t in news):
            log("  %s %s: already done" % (kind, eid))
            continue
        if any(t is None for t in olds) or any(v is None for v in vold):
            log("  %s %s: SKIPPED, the geometry it replaces is not on the board" % (kind, eid))
            continue
        lay = board.GetLayerID(layer)
        nc = board.FindNet(net).GetNetCode()
        txn = Txn(ctx)
        ch = [("del", t) for t in olds]
        ch += [("via", v, P(*b)) for v, (a, b) in zip(vold, vmoves)]
        ch += [("add", nc, lay, MM(w), P(*a), P(*b)) for a, b, w in new]
        txn.apply(ch)
        if not resolve(ctx, txn, 0, eid):
            txn.rollback()
            log("  %s %s: NOT applied (clearance)" % (kind, eid))
            continue
        txn.commit()
        done += 1
        log("  %s %s: %s" % (kind, eid, why))
    return done


def apply_routes(board, items, kind):
    """JOG_EDITS / TRUNK entries: (id, deletions [(net, layer, a, b)], additions [(net, layer, w, [points])],
    vias [(net, xy)], why). Idempotent like apply_edits."""
    done = 0
    for eid, dels, adds, vias, why in items:
        ctx = Ctx(board)
        olds = [find_track(board, n, l, a, b) for n, l, a, b in dels]
        news = [find_track(board, n, l, pts[k], pts[k + 1]) for n, l, w, pts in adds for k in range(len(pts) - 1)]
        if all(t is None for t in olds) and news and all(t is not None for t in news):
            log("  %s %s: already done" % (kind, eid))
            continue
        if any(t is None for t in olds):
            log("  %s %s: SKIPPED, the geometry it replaces is not on the board" % (kind, eid))
            continue
        txn = Txn(ctx)
        ch = [("del", t) for t in olds]
        for n, l, w, pts in adds:
            nc, lay = board.FindNet(n).GetNetCode(), board.GetLayerID(l)
            ch += [("add", nc, lay, MM(w), P(*pts[k]), P(*pts[k + 1])) for k in range(len(pts) - 1)]
        ch += [("addvia", board.FindNet(n).GetNetCode(), P(*xy)) for n, xy in vias if find_via(board, n, xy) is None]
        txn.apply(ch)
        if not resolve(ctx, txn, 0, eid):
            txn.rollback()
            log("  %s %s: NOT applied (clearance)" % (kind, eid))
            continue
        txn.commit()
        PL.merge_collinear(board)
        done += 1
        log("  %s %s: %s" % (kind, eid, why))
    return done


# ------------------------------------------------------------------------------ schematic rev 2.1 parts
NEW_PARTS = ("R21", "R22")                  # owner-approved 2026-11-25 (design.py), placed at design.PCB


def new_parts(board):
    """Schematic rev 2.1 on the routed board, without regenerating it: Value / LCSC fields of the changed
    parts (Q1 SS8050, R7 330R) synced from the schematic netlist, and the new footprints R21 / R22 added at
    their design.PCB spots with their nets, then joined to their nets: a same-net track that runs through
    a pad is split inside it (no new copper), else route_prep's maze search draws the short link; a GND pad
    gets an axial fan-out via. Idempotent (a part already on the board is only re-checked)."""
    import gen_pcb as GP
    padnet, fields = GP.read_netlist()
    parts = {p["ref"]: p for p in D.PARTS}
    n = 0
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        f = fields.get(ref)
        if f is None or ref not in parts:
            continue
        if fp.GetValue() != parts[ref]["value"]:
            log("  %s value %s -> %s (schematic rev 2.1)" % (ref, fp.GetValue(), parts[ref]["value"]))
            fp.SetValue(parts[ref]["value"])
            n += 1
        cur = {x.GetName(): x.GetText() for x in fp.GetFields()}
        for k in ("Datasheet", "Description", "LCSC", "MPN", "Manufacturer", "JLC"):
            if k in f and k in cur and cur[k] != f[k]:
                fp.SetField(k, f[k])
                n += 1
    have = {fp.GetReference() for fp in board.GetFootprints()}
    for ref in NEW_PARTS:
        if ref in have:
            continue
        p = parts[ref]
        fp = GP.load_fp(p["fp"])
        x, y, rot = p["pcb"]
        fp.SetReference(ref)
        fp.SetValue(p["value"])
        fp.SetPosition(GP.P(x, y))
        fp.SetOrientationDegrees(rot)
        fp.SetPath(pcbnew.KIID_PATH("%s/%s" % (GP.sheet_path(p["sheet"]), GP.uid("sym", ref, 1))))
        f = fields[ref]
        fp.SetSheetname(f.get("Sheetname", ""))
        fp.SetSheetfile(f.get("Sheetfile", ""))
        for k in ("Datasheet", "Description", "LCSC", "MPN", "Manufacturer", "JLC"):
            if k in f:
                fp.SetField(k, f[k])
                if k not in ("Datasheet", "Description"):
                    fp.GetField(k).SetVisible(False)
                    fp.GetField(k).SetLayer(pcbnew.F_Fab)
        for pad in fp.Pads():
            net = padnet.get((ref, pad.GetNumber()))
            if net:
                pad.SetNet(board.FindNet(net))
        PL.ref_setup(fp, PL.REF_SIZES[0])
        board.Add(fp)
        n += 1
        log("  %s added at (%.2f, %.2f) rot %d: %s" % (ref, x, y, rot, ", ".join("pad %s %s" % (q.GetNumber(), q.GetNetname()) for q in fp.Pads())))
        for pad in fp.Pads():
            join_pad(board, pad)
    return n


# Fixed joins for new pads, board mm (pad centre first). R22.2 (MOSI): west, then 45 deg down onto the MOSI
# via at (67.814, 66.809); a maze join ends on the 45 deg MOSI track in an acute T.
JOIN_PATHS = {
    "R22.2": [[(71.3, 65.325), (69.298, 65.325), (67.814, 66.809)]],
}


def join_pad(board, pad):
    """Connect a new pad to its net (see new_parts)."""
    net, nc = pad.GetNetname(), pad.GetNetCode()
    ctx = Ctx(board)
    c = pt(pad.GetPosition())
    sz = pad.GetSize(F)
    half = min(sz.x, sz.y) / 2
    # 1. a same-net F.Cu track crossing the pad: split it at its point nearest the pad centre
    for t in board.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetNetCode() != nc or t.GetLayer() != F:
            continue
        a, b = pt(t.GetStart()), pt(t.GetEnd())
        if PL.dist_point_seg(c, a, b) < half - MM(0.05) and pad.HitTest(V(PL.proj(c, a, unit(sub(b, a))))):
            X = PL.proj(c, a, unit(sub(b, a)))
            if norm(sub(X, a)) > MM(0.05) and norm(sub(X, b)) > MM(0.05):
                txn = Txn(ctx)
                txn.apply([("seg", t, a, X), ("add", nc, F, t.GetWidth(), X, b)])
                txn.commit()
                log("    %s.%s: %s track through the pad split inside it" % (pad.GetParentFootprint().GetReference(), pad.GetNumber(), net))
                return True
    if net == "GND":
        # 2. GND: an axial fan-out via (the F.Cu pour joins the pad as well)
        guard = PadGuard(board)
        boxes = PL.text_boxes(board)
        rv = R.GND_VIA_D / 2
        bb = pad.GetBoundingBox()
        for extra in (0.0, 0.1, 0.2, 0.35, 0.5):
            for d in ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)):
                reach = abs(d[0]) * bb.GetWidth() / 2 + abs(d[1]) * bb.GetHeight() / 2
                q = add(c, mul(d, reach + MM(0.25 + 0.05 + extra) + rv))
                q = (round(q[0] / 1000) * 1000.0, round(q[1] / 1000) * 1000.0)
                if guard.gap(q, rv)[0] < MM(PAD_VIA_GAP) or PL.near_box(q, boxes, rv + PL.LABEL_VIA_GAP):
                    continue
                txn = Txn(ctx)
                txn.apply([("addvia", nc, q), ("add", nc, F, MM(0.4), c, q)])
                if resolve(ctx, txn, 0, "fan-out %s.%s" % (pad.GetParentFootprint().GetReference(), pad.GetNumber())):
                    txn.commit()
                    log("    %s.%s: GND fan-out via at %s" % (pad.GetParentFootprint().GetReference(), pad.GetNumber(), bm(q)))
                    return True
                txn.rollback()
    # 3. the nearest same-net item on F.Cu, maze-routed on F.Cu; 4. else a via beside the pad (axial, clear of
    # SMD pads and labels) with a stub, and the maze on B.Cu from that via to the nearest B.Cu item of the net
    w = MM(0.2) if net not in D.POWER_NETS else MM(0.4)
    guard = PadGuard(board)
    boxes = PL.text_boxes(board)

    def nearest(layer, frm):
        best = None
        for it in list(board.GetTracks()) + [q for f_ in board.GetFootprints() for q in f_.Pads()]:
            if it.GetNetCode() != nc:
                continue
            if it.GetClass() == "PAD" and it.GetParentFootprint().GetReference() == pad.GetParentFootprint().GetReference():
                continue
            if it.GetClass() != "PCB_VIA" and not it.IsOnLayer(layer):
                continue
            d = PL.dist_point_seg(frm, pt(it.GetStart()), pt(it.GetEnd())) if it.GetClass() == "PCB_TRACK" else norm(sub(frm, pt(it.GetPosition())))
            if best is None or d < best[0]:
                best = (d, it)
        return best

    def try_maze(a_item, b_item, layer, extra=()):
        res = R.maze_route(board, net, a_item, b_item, 4.0, 0.05, b45=MM(0.8), b90=None, layers=[layer], width=w, nojog=True)
        if not res or res[1]:
            return None
        runs = [list(r) for r in res[0]]
        runs[-1][1] = PL.snap_end(runs[-1][1], b_item, False)
        return [("add", nc, L_, w, Q[m], Q[m + 1]) for L_, Q in runs for m in range(len(Q) - 1)], \
            sum(PL.chain_len(Q) for L_, Q in runs)
    tag = "%s.%s" % (pad.GetParentFootprint().GetReference(), pad.GetNumber())
    # 3a. a fixed octilinear path from the pad centre to a same-net via (JOIN_PATHS), so no 45 deg T is made
    for path in JOIN_PATHS.get(tag, ()):
        Q = [P(*q) for q in path]
        txn = Txn(ctx)
        txn.apply([("add", nc, F, w, Q[m], Q[m + 1]) for m in range(len(Q) - 1)])
        if resolve(ctx, txn, 0, "join " + tag):
            txn.commit()
            log("    %s: joined to %s on F.Cu by its fixed path to %s (%.2f mm)" % (tag, net, bm(Q[-1]), TOMM(int(PL.chain_len(Q)))))
            return True
        txn.rollback()
    # 3b. one octilinear segment from the pad centre square onto a nearby same-net F.Cu track (a 90 deg T)
    drops = []
    for t in board.GetTracks():
        if t.GetClass() != "PCB_TRACK" or t.GetNetCode() != nc or t.GetLayer() != F:
            continue
        a, b = pt(t.GetStart()), pt(t.GetEnd())
        u = unit(sub(b, a))
        X = PL.proj(c, a, u)
        s_ = dot(sub(X, a), u)
        if s_ < MM(0.1) or s_ > norm(sub(b, a)) - MM(0.1) or norm(sub(X, c)) > MM(3.0) or norm(sub(X, c)) < MM(0.1):
            continue
        if off_angle(c, X) > 0.5:
            continue
        drops.append((norm(sub(X, c)), X))
    for d_, X in sorted(drops):
        txn = Txn(ctx)
        txn.apply([("add", nc, F, w, c, X)])
        if resolve(ctx, txn, 0, "join " + tag):
            txn.commit()
            log("    %s: joined to %s on F.Cu, square onto its track (%.2f mm)" % (tag, net, TOMM(int(d_))))
            return True
        txn.rollback()
    tgt = nearest(F, c)
    if tgt and tgt[0] < MM(6):
        r = try_maze(pad, tgt[1], F)
        if r:
            txn = Txn(ctx)
            txn.apply(r[0])
            if resolve(ctx, txn, 0, "join " + tag):
                txn.commit()
                PL.merge_collinear(board)
                log("    %s: joined to %s on F.Cu (%.2f mm)" % (tag, net, TOMM(int(r[1]))))
                return True
            txn.rollback()
    rv = R.VIA_D / 2
    bb = pad.GetBoundingBox()
    for extra in (0.0, 0.1, 0.2, 0.35, 0.5, 0.7):
        for d in ((0.0, -1.0), (0.0, 1.0), (1.0, 0.0), (-1.0, 0.0)):
            reach = abs(d[0]) * bb.GetWidth() / 2 + abs(d[1]) * bb.GetHeight() / 2
            q = add(c, mul(d, reach + MM(PAD_VIA_GAP + extra) + rv))
            q = (round(q[0] / 1000) * 1000.0, round(q[1] / 1000) * 1000.0)
            if guard.gap(q, rv)[0] < MM(PAD_VIA_GAP) or PL.near_box(q, boxes, rv + PL.LABEL_VIA_GAP):
                continue
            txn = Txn(ctx)
            txn.apply([("addvia", nc, q), ("add", nc, F, w, c, q)])
            if not resolve(ctx, txn, 0, "via " + tag):
                txn.rollback()
                continue
            v = [x for x in txn.touched() if x.GetClass() == "PCB_VIA"][0]
            tb = nearest(B, q)
            r = try_maze(v, tb[1], B) if tb and tb[0] < MM(8) else None
            if r:
                txn.apply(r[0])
                if resolve(ctx, txn, 0, "join " + tag):
                    txn.commit()
                    PL.merge_collinear(board)
                    log("    %s: via at %s, joined to %s on B.Cu (%.2f mm)" % (tag, bm(q), net, TOMM(int(r[1]))))
                    return True
            txn.rollback()
    log("    %s: NOT joined to %s" % (tag, net))
    return False


def new_labels(board):
    """References of the rev 2.1 parts beside their parts (polish.best_single, the finish rules), and any
    reference the new parts now cover placed again; a callout with a leader when no spot is free."""
    news = [fp for fp in board.GetFootprints() if fp.GetReference() in NEW_PARTS]
    crts = [fp.GetCourtyard(pcbnew.F_CrtYd).BBox() for fp in news]
    redo = []
    for fp in board.GetFootprints():
        t = fp.Reference()
        if fp.GetReference() in NEW_PARTS or not t.IsVisible() or t.GetLayer() != pcbnew.F_SilkS:
            continue
        tb = t.GetBoundingBox()
        if any(tb.Intersects(c) for c in crts):
            redo.append(fp)
    n = 0
    for fp in redo + news:
        ref = fp.GetReference()
        t = fp.Reference()
        keep = (pt(t.GetPosition()), t.GetTextAngleDegrees())
        sm = PL.text_map(board, pcbnew.F_SilkS, exclude=(ref,))
        unit = PL.Unit([t])
        best = PL.best_single(sm, fp, unit)
        how = None
        if best is not None:
            sc, angle, c, b = best
            unit.place(angle, c)
            how = "beside its part at %s" % (bm(c),)
        if how is None:
            # spots that only pure stitching vias are in the way of: the vias go (stitched again later)
            stitch = {pt(v.GetPosition()): v for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and pure_stitch(board, v)}
            for sc, angle, c, b, vs in PL.via_blocked_spots(sm, fp, unit):
                if vs and all(q in stitch for q in vs):
                    unit.place(angle, c)
                    for q in vs:
                        board.Delete(stitch[q])
                    how = "beside its part at %s (%d stitching vias moved off)" % (bm(c), len(vs))
                    break
        if how is None:
            # a neighbour's reference in the way: place this label first with the neighbour's taken out,
            # then the neighbour's again (same rules); undone if the neighbour then has no spot
            pb = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
            near = []
            for f2 in board.GetFootprints():
                t2 = f2.Reference()
                if f2.GetReference() == ref or not t2.IsVisible() or t2.GetLayer() != pcbnew.F_SilkS:
                    continue
                tb = t2.GetBoundingBox()
                dx = max(pb.GetLeft() - tb.GetRight(), 0, tb.GetLeft() - pb.GetRight())
                dy = max(pb.GetTop() - tb.GetBottom(), 0, tb.GetTop() - pb.GetBottom())
                if math.hypot(dx, dy) < MM(3.0):
                    near.append(f2)
            for f2 in near:
                t2 = f2.Reference()
                keep2 = (pt(t2.GetPosition()), t2.GetTextAngleDegrees())
                sm = PL.text_map(board, pcbnew.F_SilkS, exclude=(ref, f2.GetReference()))
                best = PL.best_single(sm, fp, unit)
                if best is None:
                    t.SetTextAngleDegrees(keep[1])
                    t.SetPosition(V(keep[0]))
                    continue
                sc, angle, c, b = best
                unit.place(angle, c)
                sm2 = PL.text_map(board, pcbnew.F_SilkS, exclude=(f2.GetReference(),))
                u2 = PL.Unit([t2])
                best2 = PL.best_single(sm2, f2, u2)
                gone2 = []
                if best2 is None:
                    stitch = {pt(v.GetPosition()): v for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and pure_stitch(board, v)}
                    for sc2, a2, c2, b2, vs2 in PL.via_blocked_spots(sm2, f2, u2):
                        if vs2 and all(q in stitch for q in vs2):
                            best2 = (sc2, a2, c2, b2)
                            gone2 = [stitch[q] for q in vs2]
                            break
                if best2 is not None:
                    u2.place(best2[1], best2[2])
                    for v in gone2:
                        board.Delete(v)
                    how = "beside its part at %s (%s's label moved to %s)" % (bm(c), f2.GetReference(), bm(best2[2]))
                    break
                t2.SetTextAngleDegrees(keep2[1])
                t2.SetPosition(V(keep2[0]))
                t.SetTextAngleDegrees(keep[1])
                t.SetPosition(V(keep[0]))
        if how is None:
            sm = PL.text_map(board, pcbnew.F_SilkS, exclude=(ref,))
            if PL.place_callout(board, sm, fp, unit, ctx=Ctx(board)):
                how = "callout with a leader"
        if how is None:
            t.SetTextAngleDegrees(keep[1])
            t.SetPosition(V(keep[0]))
            if ref in NEW_PARTS:
                # last resort (pcb-layout-pro silkscreen rule): hidden, listed in the README
                t.SetVisible(False)
                log("  label %s: no legal spot beside it, by callout or after moving a neighbour's label: hidden" % ref)
            else:
                log("  label %s: NO legal spot (left where it was)" % ref)
            continue
        log("  label %s: %s" % (ref, how))
        n += 1
    return n


# ------------------------------------------------------------------------------ SMD pads and vias
PAD_VIA_GAP = 0.15                          # mm, via copper to any SMD pad (mask web; no via in a pad)


class PadGuard:
    def __init__(self, board):
        self.pads = []
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if p.GetAttribute() not in (pcbnew.PAD_ATTRIB_SMD, pcbnew.PAD_ATTRIB_CONN):
                    continue
                for lay in (F, B):
                    if p.IsOnLayer(lay):
                        s = pcbnew.SHAPE_POLY_SET()
                        p.TransformShapeToPolygon(s, lay, 0, PL.MAXERR, pcbnew.ERROR_OUTSIDE)
                        bb = s.BBox()
                        self.pads.append((s, (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom()), p, fp.GetReference()))

    def gap(self, q, r):
        """Smallest distance (nm) from a circle (centre q, radius r) to an SMD pad, with the pad."""
        best = (1e18, None)
        for s, bb, p, ref in self.pads:
            if q[0] < bb[0] - MM(2) or q[0] > bb[2] + MM(2) or q[1] < bb[1] - MM(2) or q[1] > bb[3] + MM(2):
                continue
            v = V(q)
            d = -r if s.Contains(v) else math.sqrt(s.SquaredDistance(v)) - r
            if d < best[0]:
                best = (d, (ref, p.GetNumber()))
        return best

    def boxes(self, grow=0):
        return [(bb[0] - grow, bb[1] - grow, bb[2] + grow, bb[3] + grow) for s, bb, p, ref in self.pads]


def off_angle(a, b):
    d = sub(b, a)
    if norm(d) < 1:
        return 0.0
    ang = math.degrees(math.atan2(d[1], d[0])) % 45.0
    return min(ang, 45.0 - ang)


def fanouts(board):
    """Rebuild off-angle / in-pad GND fan-outs; delete stitching vias that touch SMD pads."""
    gnd = board.FindNet("GND").GetNetCode()
    guard = PadGuard(board)
    rv = R.GND_VIA_D / 2
    dead = []
    for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gnd]:
        if pure_stitch(board, v) and guard.gap(pt(v.GetPosition()), rv)[0] < MM(0.05):
            dead.append(v)
    for v in dead:
        log("  stitching via at %s touched SMD pad %s.%s: deleted" % ((bm(pt(v.GetPosition())),) + guard.gap(pt(v.GetPosition()), rv)[1]))
        board.Delete(v)
    del dead
    boxes = PL.text_boxes(board)
    avoid = [board.FindFootprintByReference(r).GetCourtyard(pcbnew.F_CrtYd) for r in R.FAN_AVOID]
    n = 0
    for _ in range(3):
        ctx = Ctx(board)
        todo = []
        for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gnd]:
            tr = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == gnd
                  and (v.HitTest(t.GetStart(), 0) or v.HitTest(t.GetEnd(), 0))]
            if len(tr) != 1 or tr[0].GetLayer() != F:
                continue
            t = tr[0]
            far = pt(t.GetEnd()) if v.HitTest(t.GetStart(), 0) else pt(t.GetStart())
            pd = PL.pad_at(board, gnd, F, far)
            if pd is None or pd.HasHole():
                continue
            if any(a[0] in ("tee", "via") for a in ctx.anchors.get(uid(t), [])):
                continue                            # something else joins the stub: leave it
            bad_angle = off_angle(far, pt(v.GetPosition())) > 1.0
            bad_pad = guard.gap(pt(v.GetPosition()), rv)[0] < MM(0.05)
            if bad_angle or bad_pad:
                todo.append((v, t, pd, far, bad_angle, bad_pad))
        if not todo:
            break
        for v, t, pd, far, bad_angle, bad_pad in todo:
            ctx = Ctx(board)
            c = pt(pd.GetPosition())
            old_dir = unit(sub(pt(v.GetPosition()), c)) if norm(sub(pt(v.GetPosition()), c)) else (1.0, 0.0)
            bb = pd.GetBoundingBox()
            hw, hh = bb.GetWidth() / 2, bb.GetHeight() / 2
            axial = [(1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)]
            diag = [(math.sqrt(0.5) * sx, math.sqrt(0.5) * sy) for sx in (1, -1) for sy in (1, -1)]
            # tracks already ending in the pad centre: the stub must not meet them at < 90 deg
            arms = []
            for x in board.GetTracks():
                if x.GetClass() == "PCB_TRACK" and x.GetNetCode() == gnd and uid(x) != uid(t) and x.GetLayer() == F:
                    for e, o in ((pt(x.GetStart()), pt(x.GetEnd())), (pt(x.GetEnd()), pt(x.GetStart()))):
                        if norm(sub(e, c)) < MM(0.01) and norm(sub(o, e)) > 0:
                            arms.append(unit(sub(o, e)))
            dirs = sorted(axial, key=lambda d: -dot(d, old_dir)) + sorted(diag, key=lambda d: -dot(d, old_dir))
            dirs = [d for d in dirs if all(dot(d, a) <= 1e-6 for a in arms)]
            width = t.GetWidth()
            done = False
            for extra in (0.0, 0.1, 0.2, 0.35, 0.5, 0.7, 1.0):
                for d in dirs:
                    reach = abs(d[0]) * hw + abs(d[1]) * hh
                    q = add(c, mul(d, reach + MM(0.25 + 0.05 + extra) + rv))
                    q = (round(q[0] / 1000) * 1000.0, round(q[1] / 1000) * 1000.0)       # 1 um grid
                    if any(a.Contains(V(q)) for a in avoid):
                        continue
                    if guard.gap(q, rv)[0] < MM(PAD_VIA_GAP):
                        continue
                    if PL.near_box(q, boxes, rv + PL.LABEL_VIA_GAP):
                        continue
                    txn = Txn(ctx)
                    txn.apply([("del", t), ("del", v), ("addvia", gnd, q), ("add", gnd, F, width, c, q)])
                    if resolve(ctx, txn, 0, "fan-out %s.%s" % (pd.GetParentFootprint().GetReference(), pd.GetNumber())):
                        txn.commit()
                        done = True
                        n += 1
                        log("  fan-out of %s.%s rebuilt: via -> %s (%s)" % (
                            pd.GetParentFootprint().GetReference(), pd.GetNumber(), bm(q),
                            ", ".join(w_ for w_, f_ in (("stub was off-angle", bad_angle), ("via touched an SMD pad", bad_pad)) if f_)))
                        break
                    txn.rollback()
                if done:
                    break
            if not done and bad_angle and not bad_pad:
                # keep the via, make the stub octilinear with one bend: axial out of the pad, then 45 deg
                vq = pt(v.GetPosition())
                dv = sub(vq, c)
                for first in ((1.0, 0.0), (0.0, 1.0)):
                    along = dot(dv, first)
                    side = dv[0] * first[1] - dv[1] * first[0]
                    rest = abs(side)
                    if abs(along) <= rest:
                        continue
                    knee = add(c, mul(first, along - math.copysign(rest, along)))
                    if all(dot(unit(sub(knee, c)), a_) <= 1e-6 for a_ in arms) is False:
                        continue
                    txn = Txn(ctx)
                    txn.apply([("del", t), ("add", gnd, F, width, c, knee), ("add", gnd, F, width, knee, vq)])
                    if resolve(ctx, txn, 0, "fan-out %s.%s" % (pd.GetParentFootprint().GetReference(), pd.GetNumber())):
                        txn.commit()
                        done = True
                        n += 1
                        log("  fan-out of %s.%s: stub re-drawn octilinear (axial + 45 deg, via kept at %s)" % (
                            pd.GetParentFootprint().GetReference(), pd.GetNumber(), bm(vq)))
                        break
                    txn.rollback()
            if not done:
                log("  fan-out of %s.%s: no legal octilinear spot" % (pd.GetParentFootprint().GetReference(), pd.GetNumber()))
    return n


WIDE_NETS = ("5V",)                         # D03: the 5 V distribution runs F1 -> J6 -> ... -> C1 -> U5 -> U6
WIDE_W = (1.2, 1.0, 0.8)                    # mm, tried in turn on every 0.6 mm segment of WIDE_NETS


# D03: the 5V net was one 428 mm daisy chain F1 -> J6 -> J3 -> J2 -> J1 -> left edge -> J9 / C1 / U5 and
# U4 / D1 / U6: 267 / 317 mm (0.22 / 0.26 ohm) from the fuse to the regulators sitting 21 mm away.
# Two links feed the regulators from F1 first: F1.2 -> C6.1 (U5 input) and C6.1 -> C7.1 (U6 input).
# (via, stub start inside the pad): beside F1 pad 2 (an SD_CS track runs left of the pad's centre line,
# so the stub leaves the pad 0.54 mm above it, still inside the pad); right of C6 pad 1, clear of C6's
# label (no via under text), with a 45 deg stub from the pad's corner
FEED_VIA1 = [((87.75, 60.6), (88.8, 60.6)), ((87.8, 60.55), (88.8, 60.55))]
FEED_VIA2 = [((73.0, 50.3), (72.45, 49.75)), ((73.05, 50.35), (72.45, 49.75))]   # below C6's label, 45 deg stub
FEED_MAX = (60.0, 25.0)                     # mm of copper path above which a link is added


def copper_path(board, net, a, b):
    """Shortest copper path (mm of track; vias and pads free) between two pads of a net."""
    import heapq
    key = lambda v: (int(round(v.x / 1000.0)), int(round(v.y / 1000.0)))
    adj = {}
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == net]
    for t in tracks:
        u, v = (key(t.GetStart()), t.GetLayer()), (key(t.GetEnd()), t.GetLayer())
        L = TOMM(int(t.GetLength()))
        adj.setdefault(u, []).append((v, L))
        adj.setdefault(v, []).append((u, L))
    nodes = list(adj)
    for v in [x for x in board.GetTracks() if x.GetClass() == "PCB_VIA" and x.GetNetname() == net]:
        vn = ("via", key(v.GetPosition()))
        for n in nodes:
            if v.HitTest(pcbnew.VECTOR2I(n[0][0] * 1000, n[0][1] * 1000), 0):
                adj.setdefault(vn, []).append((n, 0.0))
                adj[n].append((vn, 0.0))
    pads = {}
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == net:
                pn = ("pad", "%s.%s" % (fp.GetReference(), p.GetNumber()))
                pads[pn[1]] = pn
                for n in nodes:
                    if p.IsOnLayer(n[1]) and p.HitTest(pcbnew.VECTOR2I(n[0][0] * 1000, n[0][1] * 1000)):
                        adj.setdefault(pn, []).append((n, 0.0))
                        adj[n].append((pn, 0.0))
    src, dst = pads.get(a), pads.get(b)
    if src is None or dst is None:
        return None
    dist = {src: 0.0}
    q = [(0.0, 0, src)]
    k = 0
    while q:
        d, _, u = heapq.heappop(q)
        if u == dst:
            return d
        if d > dist.get(u, 1e18):
            continue
        for v, w in adj.get(u, []):
            if d + w < dist.get(v, 1e18):
                dist[v] = d + w
                k += 1
                heapq.heappush(q, (d + w, k, v))
    return None


def feed_5v(board):
    """D03 links (run with the zones unfilled and the stitching vias lifted, inside straighten()):
    F1.2 -> C6.1 through a via beside each pad (vias >= 0.15 mm from every SMD pad, stubs along the pad
    axis) and route_prep's maze search between the two vias (both outer layers); C6.1 -> C7.1 by the
    jog-free maze. Kept only when every clearance holds; the jog tools run afterwards."""
    gnd = board.FindNet("GND").GetNetCode()
    nc = board.FindNet("5V").GetNetCode()
    W = MM(0.6)
    out = []
    pads = {"%s.%s" % (fp.GetReference(), p.GetNumber()): p for fp in board.GetFootprints() for p in fp.Pads()}
    guard = PadGuard(board)
    for (a, b), limit in zip((("F1.2", "C6.1"), ("C6.1", "C7.1")), FEED_MAX):
        before = copper_path(board, "5V", a, b)
        if before is not None and before <= limit:
            log("  5V feed %s -> %s: %.1f mm already, nothing to add" % (a, b, before))
            continue
        ctx = Ctx(board)
        txn = Txn(ctx)
        ends = []
        if a == "F1.2":
            for spots, pad in ((FEED_VIA1, pads["F1.2"]), (FEED_VIA2, pads["C6.1"])):
                ok = None
                for xy, st in spots:
                    q = P(*xy)
                    if guard.gap(q, R.VIA_D / 2)[0] < MM(PAD_VIA_GAP) or \
                            PL.near_box(q, PL.text_boxes(board), R.VIA_D / 2 + PL.LABEL_VIA_GAP):
                        continue
                    c = P(*st)
                    mk = txn.mark()
                    txn.apply([("addvia", nc, q), ("add", nc, F, W, c, q)])
                    if not txn.conflicts(mk, first=True):
                        ok = [x for x in txn.touched(mk) if x.GetClass() == "PCB_VIA"][0]
                        break
                    txn.rollback(mk)
                if ok is None:
                    break
                ends.append(ok)
            if len(ends) < 2:
                txn.rollback()
                log("  5V feed %s -> %s: no legal via beside the pads" % (a, b))
                continue
            res = R.maze_route(board, "5V", ends[0], ends[1], 12.0, 0.05, b45=MM(0.5), b90=MM(1.5), width=W,
                               nojog=False, via_cost=MM(1.5))
        else:
            res = R.maze_route(board, "5V", pads[a], pads[b], 12.0, 0.05, b45=MM(0.8), b90=None, width=W,
                               nojog=True, via_cost=MM(1.5))
        if not res:
            txn.rollback()
            log("  5V feed %s -> %s: no route" % (a, b))
            continue
        runs, vias = res[0], res[1]
        txn.apply([("add", nc, L_, W, Q[m], Q[m + 1]) for L_, Q in runs for m in range(len(Q) - 1)]
                  + [("addvia", nc, q) for q in vias])
        tb = PL.text_boxes(board)
        bad_pad = [q for q in vias if guard.gap(q, R.VIA_D / 2)[0] < MM(PAD_VIA_GAP)
                   or PL.near_box(q, tb, R.VIA_D / 2 + PL.LABEL_VIA_GAP)]
        if bad_pad or not resolve(ctx, txn, 0, "5V feed"):
            txn.rollback()
            log("  5V feed %s -> %s: route rejected (%s)" % (a, b, "via next to an SMD pad or under a label" if bad_pad else "clearance"))
            continue
        txn.commit()
        PL.merge_collinear(board)
        after = copper_path(board, "5V", a, b)
        L = sum(PL.chain_len(Q) for L_, Q in runs)
        log("  5V feed %s -> %s: %.1f mm of new 0.6 mm track, %d vias; path %.1f -> %.1f mm" % (
            a, b, TOMM(int(L)), len(vias) + (2 if a == "F1.2" else 0), before or -1, after or -1))
        out.append((a, b))
    return out


def straighten(board, maze=True):
    """The micro-loops hid small steps (the audit follows a chain only up to the loop). With the zones
    unfilled and the pure stitching vias lifted (as during polish.py's jog step), polish.py's own jog
    tools run again over the board: local moves (jog_pass), the jog-free maze re-route of a run
    (maze_jogs) and the rip-up with up to four neighbouring runs (ripup_jogs), then the 90 deg chamfer
    pass. The stitching vias go back where they are still legal (the rest is stitched again later)."""
    for z in board.Zones():
        if not z.GetIsRuleArea():
            z.UnFill()
    lifted = [pt(v.GetPosition()) for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and pure_stitch(board, v)]
    for v in [v for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and pure_stitch(board, v)]:
        board.Delete(v)
    quiet = lambda s_: None
    feed_5v(board)
    fixed, left = PL.jog_pass(board, set(), log=quiet)
    PL.merge_collinear(board)
    if maze:
        fixed += PL.maze_jogs(board, set(), log=quiet)
        PL.merge_collinear(board)
        fixed += PL.ripup_jogs(board, set(), log=quiet)
        PL.merge_collinear(board)
    cfix, cleft = PL.chamfer_pass(board, set(), log=quiet)
    PL.merge_collinear(board)
    gnd = board.FindNet("GND").GetNetCode()
    obs = Obstacles(board)
    guard = PadGuard(board)
    back = 0
    for q in lifted:
        if guard.gap(q, R.GND_VIA_D / 2)[0] >= MM(PAD_VIA_GAP) and \
                not obs.via_conflicts(q, R.GND_VIA_D, R.GND_VIA_DRILL, gnd, first=True):
            PL.new_via(board, obs, q)
            back += 1
    ctx = Ctx(board)
    left = [(ts[0].GetNetname(), board.GetLayerName(layer), PL.bmm(pts[j + 1])) for net, layer, pts, ts in ctx.chains
            for j, off in PL.find_jogs(pts)]
    log("  jog tools%s: %d jogs straightened, %d left; %d right angles chamfered, %d left; %d of %d stitching vias back" % (
        "" if maze else " (local moves only)", len(fixed), len(left), len(cfix), len(cleft), back, len(lifted)))
    for f in fixed:
        log("    %s %s at %s (%.2f mm): %s" % (f[0], f[1], f[2], f[3], f[4]))
    return len(fixed) + len(cfix)


def widen(board):
    """D03: every 0.6 mm 5V segment is widened to the widest of WIDE_W that keeps every clearance (same
    centre line, so directions and junctions stay); a segment ending in an SMD pad is never wider than
    that pad (tombstoning, pcb-layout-pro routing rule)."""
    n = 0
    added = 0.0
    ctx = Ctx(board)
    for t in [x for x in board.GetTracks() if x.GetClass() == "PCB_TRACK" and x.GetNetname() in WIDE_NETS]:
        if t.GetWidth() > MM(0.6) + 1 or t.GetWidth() < MM(0.6) - 1:
            continue
        cap = None
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if p.GetNetname() != t.GetNetname() or not p.IsOnLayer(t.GetLayer()):
                    continue
                if p.HitTest(t.GetStart()) or p.HitTest(t.GetEnd()):
                    if p.GetAttribute() == pcbnew.PAD_ATTRIB_SMD:
                        sz = p.GetSize(t.GetLayer())
                        cap = min(cap or 10 ** 9, min(sz.x, sz.y))
        for w in WIDE_W:
            if cap is not None and MM(w) > cap:
                continue
            a, b = pt(t.GetStart()), pt(t.GetEnd())
            if not ctx.obs.seg_conflicts(a, b, MM(w), t.GetLayer(), t.GetNetCode(), ignore=(uid(t),), first=True):
                txn = Txn(ctx)
                txn.apply([("seg", t, a, b, MM(w))])
                if resolve(ctx, txn, 0, "widen 5V"):
                    txn.commit()
                    n += 1
                    added += TOMM(int(t.GetLength()))
                    break
                txn.rollback()
    log("  5V: %d segments widened (%.0f mm of track now 0.8-1.2 mm)" % (n, added))
    return n


def loops(board):
    """Router micro-loops: three or more < 0.1 mm segments (Freerouting's neck-down leftovers: a ring or a
    hook of 0.05 / 0.07 mm pieces) that a track enters and leaves. They go and the two tracks meet where
    their lines cross (directions kept), when that point is within 0.3 mm of them, the turn there is 135 deg
    or straight, and no clearance changes."""
    n = 0
    for _ in range(80):
        ctx = Ctx(board)
        short = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLength() < MM(0.1)]
        groups = {}
        for t in short:
            groups.setdefault((t.GetNetCode(), t.GetLayer()), []).append(t)
        found = False
        for (net, layer), segs in groups.items():
            parent = {}

            def f(k):
                parent.setdefault(k, k)
                while parent[k] != k:
                    k = parent[k]
                return k
            for t in segs:
                a, b = PL.key(pt(t.GetStart())), PL.key(pt(t.GetEnd()))
                parent[f(a)] = f(b)
            comps = {}
            for t in segs:
                comps.setdefault(f(PL.key(pt(t.GetStart()))), []).append(t)
            for ring in comps.values():
                nodes = {PL.key(pt(t.GetStart())) for t in ring} | {PL.key(pt(t.GetEnd())) for t in ring}
                if len(ring) < 3:
                    continue                        # a single short piece (a chamfer, a pad hop): leave it
                ru = {uid(t) for t in ring}
                ext = []
                for t in board.GetTracks():
                    if t.GetClass() != "PCB_TRACK" or t.GetNetCode() != net or t.GetLayer() != layer or uid(t) in ru:
                        continue
                    for e, o in ((pt(t.GetStart()), pt(t.GetEnd())), (pt(t.GetEnd()), pt(t.GetStart()))):
                        if PL.key(e) in nodes:
                            ext.append((t, e, o))
                starts = [pt(t.GetStart()) for t in ring]
                cen = (sum(p[0] for p in starts) / len(starts), sum(p[1] for p in starts) / len(starts))
                if any(PL.via_at(board, net, pt(t.GetStart())) or PL.pad_at(board, net, layer, pt(t.GetStart())) for t in ring):
                    continue                        # a pad or via there: leave it
                if len(ext) != 2:
                    continue
                (t1, e1, o1), (t2, e2, o2) = ext
                X = PL.intersect(o1, unit(sub(e1, o1)), o2, unit(sub(e2, o2)))
                if X is None:
                    X = cen
                if norm(sub(X, cen)) > MM(0.3) or norm(sub(o1, X)) < MM(0.05) or norm(sub(o2, X)) < MM(0.05):
                    continue
                if dot(unit(sub(o1, X)), unit(sub(o2, X))) > -0.7071 + 1e-3:
                    continue                        # would leave a turn sharper than 135 deg: not a wiggle
                txn = Txn(ctx)
                ch = [("del", t) for t in ring]
                ch.append(("seg", t1, o1, X) if norm(sub(pt(t1.GetEnd()), o1)) > 1 else ("seg", t1, X, o1))
                ch.append(("seg", t2, o2, X) if norm(sub(pt(t2.GetEnd()), o2)) > 1 else ("seg", t2, X, o2))
                txn.apply(ch)
                if resolve(ctx, txn, 0, "loop"):
                    txn.commit()
                    n += 1
                    found = True
                    log("  micro-loop of %d segments on %s %s at %s removed" % (len(ring), t1.GetNetname(), board.GetLayerName(layer), bm(X)))
                    break
                txn.rollback()
            if found:
                break
        if not found:
            break
    return n


# ------------------------------------------------------------------------------ return vias
FAST = ("USB_DP", "USB_DM", "SCK", "MOSI", "MISO", "SD_CS", "CS", "WS_DATA", "LDI", "LDO1", "LDO2", "LDO3", "LDO4", "LDO5")
RETURN_MAX = 1.5                            # mm, a GND via this close to each fast-net layer change (else up to 2.0)


def return_vias(board):
    gnd = board.FindNet("GND").GetNetCode()
    guard = PadGuard(board)
    boxes = PL.text_boxes(board)
    obs = Obstacles(board)
    rv = R.GND_VIA_D / 2
    added, left = [], []
    for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() in FAST]:
        c = pt(v.GetPosition())
        gv = [pt(g.GetPosition()) for g in board.GetTracks() if g.GetClass() == "PCB_VIA" and g.GetNetCode() == gnd]
        have = min(norm(sub(q, c)) for q in gv)
        if have <= MM(RETURN_MAX):
            continue
        best = None
        for r in (0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0):
            if MM(r) >= have:
                break
            for k in range(32):
                a = 2 * math.pi * k / 32
                q = (c[0] + MM(r) * math.cos(a), c[1] + MM(r) * math.sin(a))
                q = (round(q[0] / 1000) * 1000.0, round(q[1] / 1000) * 1000.0)
                if guard.gap(q, rv)[0] < MM(PAD_VIA_GAP):
                    continue
                if PL.via_ok(obs, q, gnd, boxes, MM(0.6)):
                    best = q
                    break
            if best:
                break
        if best:
            PL.new_via(board, obs, best)
            added.append((v.GetNetname(), bm(c), round(TOMM(int(norm(sub(best, c)))), 2), round(TOMM(int(have)), 2)))
            log("  return via for %s at %s: GND via at %s, %.2f mm (nearest was %.2f mm)" % (
                v.GetNetname(), bm(c), bm(best), TOMM(int(norm(sub(best, c)))), TOMM(int(have))))
        else:
            left.append((v.GetNetname(), bm(c), round(TOMM(int(have)), 2)))
            log("  return via for %s at %s: none legal closer than %.2f mm" % (v.GetNetname(), bm(c), TOMM(int(have))))
    return added, left


# ------------------------------------------------------------------------------ R4 pad 2 via
def r4_via(board):
    """The MCP_INT via sits inside R4 pad 2 (13.775, 51.613): F.Cu IR runs 0.21 mm above the pad.
    The via goes 1.0 mm up on its B.Cu track (13.775, 50.613) with an F.Cu stub down into the pad,
    when the IR track can be moved up (re-routed jog-free by the maze search) to make room."""
    v = find_via(board, "MCP_INT", (13.775, 51.613))
    if v is None:
        log("  R4 via: not at (13.775, 51.613) any more (done or changed)")
        return 0
    ctx = Ctx(board)
    gnd_ignore = set()
    newp = P(13.775, 50.613)
    nc = board.FindNet("MCP_INT").GetNetCode()
    txn = Txn(ctx)
    bt = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == nc and t.GetLayer() == B
          and (v.HitTest(t.GetStart(), 0) or v.HitTest(t.GetEnd(), 0))]
    ch = [("via", v, newp)]
    for t in bt:
        s, e = pt(t.GetStart()), pt(t.GetEnd())
        if v.HitTest(t.GetStart(), 0):
            ch.append(("seg", t, newp, e))
        else:
            ch.append(("seg", t, s, newp))
    ch.append(("add", nc, F, MM(0.2), newp, P(13.775, 51.55)))
    txn.apply(ch)
    bad = [e for it, e in txn.conflicts() if e is not None and len(e) > 2]
    blockers = {uid(e[7]): e[7] for e in bad if e[6] == "track" and e[7].GetNetname() == "IR"}
    others = [e for e in bad if not (e[6] == "track" and e[7].GetNetname() == "IR") and not (e[6] == "via" and pure_stitch(board, e[7]))]
    if others:
        txn.rollback()
        log("  R4 via: blocked by %s" % ", ".join(sorted({PL.describe(e) for e in others})))
        return 0
    if blockers:
        # re-route the IR run that is in the way (its stops: R5 pad 2 and the IR via / pad it comes from)
        ci = {ctx.where[u][0] for u in blockers if u in ctx.where}
        ok = True
        for k in ci:
            net, layer, pts, ts = ctx.chains[k]
            a_it = PL.stop_item(ctx, net, layer, pts[0], {uid(t) for t in ts})
            b_it = PL.stop_item(ctx, net, layer, pts[-1], {uid(t) for t in ts})
            if a_it is None or b_it is None:
                ok = False
                break
            txn.apply([("del", t) for t in ts])
            r = PL.route_run(board, "IR", layer, a_it, b_it, ts[0].GetWidth(), PL.chain_len(pts), ignore={uid(t) for t in ts})
            if r is None:
                ok = False
                break
            runs, vias = r
            txn.apply([("add", net, L_, ts[0].GetWidth(), Q[m], Q[m + 1]) for L_, Q in runs for m in range(len(Q) - 1)]
                      + [("addvia", net, q) for q in vias])
        if not ok or not resolve(ctx, txn, 0, "R4 via"):
            txn.rollback()
            log("  R4 via: the IR track above R4 could not be moved; via stays in the pad (reported)")
            return 0
    elif not resolve(ctx, txn, 0, "R4 via"):
        txn.rollback()
        log("  R4 via: no room")
        return 0
    txn.commit()
    PL.merge_collinear(board)
    log("  R4 via: MCP_INT via moved out of R4 pad 2 to (13.775, 50.613), F.Cu stub into the pad%s" % (
        ", IR re-routed above it" if blockers else ""))
    return 1


# ------------------------------------------------------------------------------ regulator tab copper (D04)
# (net, regulator, polygon in board mm): F.Cu, priority 1 over the GND pour, solid pad connection;
# the filler keeps every clearance and drops what does not touch the net
TABS = [
    ("3V3", "U6", [(59.95, 40.6), (67.8, 40.6), (67.8, 45.95), (59.95, 45.95)]),
    ("3V3P", "U5", [(59.95, 49.95), (67.8, 49.95), (67.8, 55.8), (59.95, 55.8)]),
]


def tab_zones(board):
    names = {z.GetZoneName() for z in board.Zones()}
    n = 0
    for net, ref, poly in TABS:
        name = "TAB_%s" % ref
        if name in names:
            continue
        z = pcbnew.ZONE(board)
        z.SetLayer(F)
        z.SetNetCode(board.FindNet(net).GetNetCode())
        z.SetZoneName(name)
        o = z.Outline()
        o.NewOutline()
        for x, y in poly:
            p = R.P(x, y)
            o.Append(p.x, p.y)
        z.SetLocalClearance(MM(PL.ZONE_CLR))
        z.SetMinThickness(MM(PL.ZONE_MINW))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        z.SetAssignedPriority(1)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        board.Add(z)
        n += 1
        log("  tab copper: %s zone on F.Cu round %s's tab (net %s)" % (name, ref, net))
    # GND stitching vias inside the new areas would only punch holes in them
    gone = 0
    for net, ref, poly in TABS:
        xs, ys = [p[0] for p in poly], [p[1] for p in poly]
        for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and pure_stitch(board, t)]:
            q = bm(pt(v.GetPosition()))
            if min(xs) <= q[0] <= max(xs) and min(ys) <= q[1] <= max(ys):
                board.Delete(v)
                gone += 1
    if gone:
        log("  tab copper: %d stitching vias inside the tab areas removed" % gone)
    return n


# ------------------------------------------------------------------------------ LIS3DH (D12)
PASTE_AREA = None                           # TN0018 aperture rule not confirmed (st.com unreachable): paste left 1:1


def lis3dh(board):
    """Rule area (no pour, no via) on F.Cu under the package interior inside the land ring; optional
    paste reduction on the 16 lands (PASTE_AREA, off: TN0018's aperture rule could not be confirmed)."""
    fp = board.FindFootprintByReference("U8")
    n = 0
    if not any(z.GetIsRuleArea() and z.GetZoneName() == "U8_NO_POUR" for z in board.Zones()):
        # interior: the box between the inner edges of the four land rows
        xs0, xs1, ys0, ys1 = [], [], [], []
        c = pt(fp.GetPosition())
        for p in fp.Pads():
            bb = p.GetBoundingBox()
            q = pt(p.GetPosition())
            if abs(q[0] - c[0]) > abs(q[1] - c[1]):
                (xs0 if q[0] < c[0] else xs1).append(bb.GetRight() if q[0] < c[0] else bb.GetLeft())
            else:
                (ys0 if q[1] < c[1] else ys1).append(bb.GetBottom() if q[1] < c[1] else bb.GetTop())
        g = MM(0.2)
        x0, x1, y0, y1 = max(xs0) + g, min(xs1) - g, max(ys0) + g, min(ys1) - g
        z = pcbnew.ZONE(board)
        z.SetIsRuleArea(True)
        z.SetLayer(F)
        z.SetZoneName("U8_NO_POUR")
        z.SetDoNotAllowZoneFills(True)
        z.SetDoNotAllowTracks(False)
        z.SetDoNotAllowVias(True)
        z.SetDoNotAllowPads(False)
        z.SetDoNotAllowFootprints(False)
        o = z.Outline()
        o.NewOutline()
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            o.Append(int(x), int(y))
        board.Add(z)
        n += 1
        log("  LIS3DH: no-pour rule area on F.Cu under the package interior %s - %s" % (bm((x0, y0)), bm((x1, y1))))
    # KiCad: paste margin per side = ratio x pad size on each axis, so the aperture is (1 + 2 ratio)^2
    # of the land area: 80 % -> ratio = (sqrt(0.8) - 1) / 2
    if PASTE_AREA is None:
        return n
    ratio = round((math.sqrt(PASTE_AREA) - 1) / 2, 4)
    m = 0
    for p in fp.Pads():
        cur = p.GetLocalSolderPasteMarginRatio()
        if cur is None or abs(cur - ratio) > 1e-4:
            p.SetLocalSolderPasteMarginRatio(ratio)
            m += 1
    if m:
        log("  LIS3DH: paste aperture %.0f %% of each land (margin ratio %.4f) on %d pads" % (100 * PASTE_AREA, ratio, m))
    return n + m


# ------------------------------------------------------------------------------ silkscreen
WIDEN_SILK = False                          # D20 left as is (review: keep the library footprints untouched)


def silk_strokes(board):
    """Unfilled footprint silk strokes < 0.15 mm (KiCad's library uses 0.12) -> 0.15 mm, or the widest
    that keeps 0.15 mm to the board edge. KiCad's library-parity DRC check ignores stroke width (checked
    on a copy), so the footprints still match their libraries."""
    x0, y0, x1, y1 = MM(PL.OX), MM(PL.OY), MM(PL.OX + D.BOARD_W), MM(PL.OY + D.BOARD_H)
    n = clipped = 0
    for fp in board.GetFootprints():
        for g in fp.GraphicalItems():
            if g.GetClass() != "PCB_SHAPE" or g.GetLayer() != pcbnew.F_SilkS or g.IsSolidFill():
                continue
            if g.GetWidth() >= MM(0.15) - 1:
                continue
            bb = g.GetBoundingBox()           # includes the stroke
            hw = g.GetWidth() / 2
            dedge = min(bb.GetLeft() + hw - x0, x1 - bb.GetRight() + hw, bb.GetTop() + hw - y0, y1 - bb.GetBottom() + hw)
            w = MM(0.15)
            if dedge - w / 2 < MM(0.15):
                w = int((dedge - MM(0.15)) * 2 // MM(0.01)) * MM(0.01)
                clipped += 1
            if w > g.GetWidth():
                g.SetWidth(int(w))
                n += 1
    log("  silk: %d footprint strokes widened to 0.15 mm (%d of them limited by the board edge)" % (n, clipped))
    return n


def j5_label(board):
    """J5's label as the other five read: "J5  M5 PROBE" (reference first), on the same line as before."""
    fp = board.FindFootprintByReference("J5")
    t = fp.Reference()
    plate = [d for d in board.GetDrawings() if d.GetClass() == "PCB_TEXT" and d.GetText() == "M5 PROBE"]
    if not plate:
        log("  J5 label: no 'M5 PROBE' text")
        return 0
    p = plate[0]
    rb, pb = t.GetBoundingBox(), p.GetBoundingBox()
    if rb.GetRight() < pb.GetLeft():
        log("  J5 label: already reads 'J5  M5 PROBE'")
        return 0
    keep = (pt(t.GetPosition()), pt(p.GetPosition()))
    sm = PL.text_map(board, pcbnew.F_SilkS, exclude=("J5",))
    # take the plate text out of the map: rebuild it without that box
    pbox = PL.bbox_t(pb)
    for k, ents in sm.idx.items():
        ents[:] = [e for e in ents if not (e[0] == "text" and e[2] == pbox)]
    unit = PL.Unit([t, p])
    w, h, _ = unit.layout(0)
    cy = (pbox[1] + pbox[3]) / 2
    best = None
    stitch = {pt(v.GetPosition()): v for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and pure_stitch(board, v)}
    why = {}
    x = MM(PL.OX + 30.0)
    while x <= MM(PL.OX + 70.0):
        c = (x, cy)
        b = PL.unit_box(c, w, h)
        vs = []
        if not sm.ok(b, "J5", vs):
            why["blocked"] = why.get("blocked", 0) + 1
        elif any(q not in stitch for q in vs):
            why["signal via"] = why.get("signal via", 0) + 1
        elif not PL.ref_near(sm, "J5", unit, 0, c):
            why["J5 not beside its header"] = why.get("J5 not beside its header", 0) + 1
        else:
            rbx = PL.ref_box(unit, 0, c)
            if sm.d_own(rbx, "J5") < sm.nearest_other(rbx, "J5") - PL.AMBIG_MARGIN:
                sc = abs(x - (keep[1][0] + keep[0][0]) / 2) + MM(0.6) * min(sm.tracks_under(b), 4) + MM(1.0) * len(vs)
                if best is None or sc < best[0]:
                    best = (sc, c, vs)
            else:
                why["nearer another part"] = why.get("nearer another part", 0) + 1
        x += MM(0.05)
    if best is None:
        t.SetPosition(V(keep[0]))
        p.SetPosition(V(keep[1]))
        log("  J5 label: no legal spot for 'J5  M5 PROBE' on its line (%s); kept as 'M5 PROBE  J5'" % why)
        return 0
    unit.place(0, best[1])
    for q in best[2]:
        board.Delete(stitch[q])
    log("  J5 label: now 'J5  M5 PROBE' at %s%s" % (bm(best[1]), " (%d stitching vias moved off the spot)" % len(best[2]) if best[2] else ""))
    return 1


# function labels (D21): (text, part) placed beside the part (polish.plate_spot rules: within 3 mm, along a
# side, nearer the part than any other, clear of pads, vias, silk, courtyards and the edge)
MARKS = [("EN", "SW1"), ("BOOT", "SW2"), ("OUT", "J10")]
J9_NAMES = [("1", [("G", 0)]), ("2", [("+", 0)]), ("3", [("S", 0)])]     # servo plug: G(ND) + (5V) S(IG)


def marks(board):
    have = {d.GetText() for d in board.GetDrawings() if d.GetClass() == "PCB_TEXT"}
    out = []
    for text, ref in MARKS:
        if text in have:
            continue
        fp = board.FindFootprintByReference(ref)
        sm = PL.text_map(board, pcbnew.F_SilkS)
        tx = PL.plate_text(board, text, 1.0, PL.REF_STROKE)
        best = PL.plate_spot(sm, fp, PL.Unit([tx]))
        if best is None:
            log("  label %r at %s: no legal spot" % (text, ref))
            out.append((text, ref, None))
            continue
        s, angle, c, b = best
        PL.Unit([tx]).place(angle, c)
        board.Add(tx)
        out.append((text, ref, bm(c)))
        log("  label %r beside %s at %s" % (text, ref, bm(c)))
    # J9 (servo header, pins 1-3 top to bottom): each pin's name level with it, beside the header:
    # the full name read bottom to top (90 deg) if it fits, else a short one (G / 5V / S) at 0 deg
    fp = board.FindFootprintByReference("J9")
    pads = {p.GetNumber(): p for p in fp.Pads()}
    have = [d for d in board.GetDrawings() if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.F_SilkS
            and d.GetText() in [n for k, cand in J9_NAMES for n, a in cand]]
    if not have:
        placed, missing = [], []
        for num, cand in J9_NAMES:
            pad = pads[num]
            pc = pt(pad.GetPosition())
            pbb = pad.GetBoundingBox()
            sm = PL.text_map(board, pcbnew.F_SilkS)
            done = None
            for name, angle in cand:
                tx = PL.plate_text(board, name, 1.0, PL.REF_STROKE)
                w, h, _ = PL.Unit([tx]).layout(angle)
                crt = fp.GetCourtyard(pcbnew.F_CrtYd).BBox()
                stitch = {pt(v.GetPosition()): v for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and pure_stitch(board, v)}
                for side in ("right", "left"):
                    for gap in (0.05, 0.15, 0.3, 0.45):
                        x = crt.GetRight() + MM(gap) + w / 2 if side == "right" else crt.GetLeft() - MM(gap) - w / 2
                        c = (x, pc[1])
                        b = PL.unit_box(c, w, h)
                        vs = []
                        # a pure stitching via in the way may go (the pours are stitched again afterwards)
                        if sm.ok(b, None, vs) and all(q in stitch for q in vs) and sm.d_own(b, "J9") < sm.nearest_other(b, "J9"):
                            done = (tx, angle, c, name, [stitch[q] for q in vs])
                            break
                    if done:
                        break
                if done:
                    break
            if done:
                tx, angle, c, name, vs = done
                PL.Unit([tx]).place(angle, c)
                board.Add(tx)
                placed.append((tx, name, num, c, vs))
            else:
                missing.append(num)
        if missing:
            # all three or none: a lone pin name would read as a complete legend
            for tx, name, num, c, vs in placed:
                board.Delete(tx)
            log("  J9 pin names: no legal spot for pin %s (vias / R6 / board edge round the header); none added" % ", ".join(missing))
            out.append(("GND 5V SIG", "J9", None))
        else:
            gone = set()
            for tx, name, num, c, vs in placed:
                for v in vs:
                    if uid(v) not in gone:
                        gone.add(uid(v))
                        board.Delete(v)
                log("  label %r beside J9 pin %s at %s%s" % (name, num, bm(c), " (%d stitching via moved off)" % len(vs) if vs else ""))
                out.append((name, "J9.%s" % num, bm(c)))
    return out


def _ok_but_own(sm, b, own):
    """SilkMap.ok, except that the courtyard of `own` may be under the text."""
    e = sm.edge
    if b[0] < e[0] or b[1] < e[1] or b[2] > e[2] or b[3] > e[3]:
        return False
    for kind, data, bb, ref in sm.near(b):
        if kind == "crt" and ref == own:
            continue
        if kind == "text":
            if PL.rect_dist(b, bb) < PL.TEXT_GAP:
                return False
        elif kind == "via":
            (c, r) = data
            dx = max(b[0] - c[0], 0, c[0] - b[2])
            dy = max(b[1] - c[1], 0, c[1] - b[3])
            if math.hypot(dx, dy) < r + PL.VIA_TEXT_GAP:
                return False
        elif kind in ("pad", "silk"):
            if PL.poly_near_rect(data, bb, b, PL.SILK_GAP):
                return False
        elif kind == "crt":
            if PL.poly_near_rect(data, bb, b, MM(0.02)):
                return False
    return True


def legend(board):
    n = 0
    for d in board.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetText() == LEGEND_OLD:
            c = d.GetBoundingBox().Centre()
            d.SetText(LEGEND_NEW)
            nb = d.GetBoundingBox().Centre()
            d.SetPosition(pcbnew.VECTOR2I(d.GetPosition().x + c.x - nb.x, d.GetPosition().y))     # keep it centred
            n += 1
    tb = board.GetTitleBlock()
    if tb.GetRevision() != REVISION:
        tb.SetRevision(REVISION)
        tb.SetDate(TB_DATE)
        tb.SetComment(1, "rev 3.1: rev 3 + standards pass (gen/std_fixes.py, 2026-11-25); schematic rev 2.1")
        n += 1
    if n:
        log("  legend / title block: rev %s, %s" % (REVISION, TB_DATE))
    return n


# global fiducials (JLCPCB Standard PCBA: 1 mm copper, 2 mm mask opening; centre >= 3.85 mm from the panel edge,
# kept here from every board edge so the rule holds with or without rails: final check N03), board-only
FIDUCIALS = [("FID1", 3.8, 21.2), ("FID2", 90.3, 4.8), ("FID3", 90.5, 65.1)]


FID_CU, FID_CRT, FID_SILK, FID_EDGE, FID_SEARCH = 1.12, 1.27, 1.9, 3.9, 6.0     # mm from the fiducial centre
# (FID_SILK: the fiducial's 1.25 mm courtyard + 0.65 mm, so a label ≤ 0.5 mm from its own part stays nearer to
# that part than to the fiducial: the audit's "ambiguous" rule)


def fid_free(board, x0, y0):
    """A test for fiducial centres: F.Cu copper (tracks, vias, pads, holes) >= FID_CU, courtyards >= FID_CRT,
    visible top silkscreen >= FID_SILK, the edge >= FID_EDGE (JLCPCB: >= 3.85 mm)."""
    cu, crt, silk = [], [], []
    c0, reach = R.P(x0, y0), MM(FID_SEARCH + 3.0)

    def near(item):
        bb = item.GetBoundingBox()
        return bb.GetLeft() - reach < c0.x < bb.GetRight() + reach and bb.GetTop() - reach < c0.y < bb.GetBottom() + reach
    for t in board.GetTracks():
        if t.IsOnLayer(F) and near(t):
            s_ = pcbnew.SHAPE_POLY_SET()
            t.TransformShapeToPolygon(s_, F, 0, MM(0.005), pcbnew.ERROR_OUTSIDE)
            cu.append(s_)
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if (p.IsOnLayer(F) or p.HasHole()) and near(p):
                s_ = pcbnew.SHAPE_POLY_SET()
                p.TransformShapeToPolygon(s_, F, 0, MM(0.005), pcbnew.ERROR_OUTSIDE)
                if p.HasHole():
                    p.TransformHoleToPolygon(s_, 0, MM(0.005), pcbnew.ERROR_OUTSIDE)
                cu.append(s_)
        c = fp.GetCourtyard(pcbnew.F_CrtYd)
        if c.OutlineCount():
            crt.append(pcbnew.SHAPE_POLY_SET(c))
        for g in list(fp.GraphicalItems()) + [fp.Reference(), fp.Value()]:
            if g.GetLayer() == pcbnew.F_SilkS and (g.GetClass() != "PCB_FIELD" or g.IsVisible()):
                silk.append(g.GetBoundingBox())
    for d in board.GetDrawings():
        if d.GetLayer() == pcbnew.F_SilkS:
            silk.append(d.GetBoundingBox())

    def dist(s_, q):
        return 0.0 if s_.Contains(q) else math.sqrt(s_.SquaredDistance(q)) / 1e6

    def box_dist(bb, q):
        dx = max(bb.GetLeft() - q.x, 0, q.x - bb.GetRight())
        dy = max(bb.GetTop() - q.y, 0, q.y - bb.GetBottom())
        return math.hypot(dx, dy) / 1e6

    def free(x, y):
        if min(x, y, D.BOARD_W - x, D.BOARD_H - y) < FID_EDGE:
            return False
        q = R.P(x, y)
        return all(dist(s_, q) >= FID_CU for s_ in cu) and all(dist(s_, q) >= FID_CRT for s_ in crt) and \
            all(box_dist(bb, q) >= FID_SILK for bb in silk)
    return free


def fiducials(board):
    have = {fp.GetReference() for fp in board.GetFootprints()}
    n = 0
    for ref, x0, y0 in FIDUCIALS:
        if ref in have:
            continue
        free = fid_free(board, x0, y0)
        cand = sorted(((math.hypot(i * 0.1, j * 0.1), x0 + i * 0.1, y0 + j * 0.1)
                       for i in range(-int(FID_SEARCH * 10), int(FID_SEARCH * 10) + 1)
                       for j in range(-int(FID_SEARCH * 10), int(FID_SEARCH * 10) + 1)
                       if math.hypot(i, j) <= FID_SEARCH * 10))
        spot = next(((round(x, 2), round(y, 2)) for d_, x, y in cand if free(x, y)), None)
        if spot is None:
            log("  fiducial %s: no free spot within %.1f mm of (%.2f, %.2f)" % (ref, FID_SEARCH, x0, y0))
            continue
        x, y = spot
        fp = pcbnew.FootprintLoad("/usr/share/kicad/footprints/Fiducial.pretty", "Fiducial_1mm_Mask2mm")
        fp.SetFPID(pcbnew.LIB_ID("Fiducial", "Fiducial_1mm_Mask2mm"))
        fp.SetReference(ref)
        fp.SetValue("Fiducial")
        fp.SetPosition(R.P(x, y))
        fp.SetAttributes(fp.GetAttributes() | pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
        fp.Reference().SetVisible(False)
        board.Add(fp)
        n += 1
        log("  fiducial %s at (%.2f, %.2f) (board-only, not in BOM/CPL)" % (ref, x, y))
    return n


# ------------------------------------------------------------------------------ edge stitching
EDGE_INSET, EDGE_STEP, EDGE_MAX = 1.5, 0.5, 3.0       # mm


def edge_stitch(board, zones):
    """GND vias so that every point EDGE_INSET inside the edge has a GND via within EDGE_MAX, where a
    legal spot exists in solid main-component pour on both outer layers (polish.stitch_grid rules)."""
    gnd = board.FindNet("GND").GetNetCode()
    PL.fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    obs = Obstacles(board)
    guard = PadGuard(board)
    boxes = PL.text_boxes(board)
    cls, comps, main = R.gnd_components(board, zones)
    mains = {layer: [cls[layer][k[2]][1] for k in comps[main] if k[0] == "P" and k[1] == layer] for layer in cls}
    solid = {}
    for layer in (F, B):
        s = pcbnew.SHAPE_POLY_SET()
        for m in mains[layer]:
            s.Append(m)
        s.Deflate(R.VIA_R + MM(0.1), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, PL.MAXERR)
        solid[layer] = s
    avoid = [board.FindFootprintByReference(r).GetCourtyard(pcbnew.F_CrtYd) for r in PL.STITCH_AVOID]
    rv = R.GND_VIA_D / 2
    pts_ = []
    s = EDGE_INSET
    x = s
    while x <= D.BOARD_W - s + 1e-9:
        pts_ += [(x, s), (x, D.BOARD_H - s)]
        x += EDGE_STEP
    y = s
    while y <= D.BOARD_H - s + 1e-9:
        pts_ += [(s, y), (D.BOARD_W - s, y)]
        y += EDGE_STEP
    added = 0
    for ex, ey in pts_:
        c = P(ex, ey)
        gv = [pt(g.GetPosition()) for g in board.GetTracks() if g.GetClass() == "PCB_VIA" and g.GetNetCode() == gnd]
        if min(norm(sub(q, c)) for q in gv) <= MM(EDGE_MAX):
            continue
        cands = []
        for dx in range(-12, 13):
            for dy in range(-12, 13):
                q = (c[0] + MM(0.1 * dx), c[1] + MM(0.1 * dy))
                if norm(sub(q, c)) <= MM(1.2):
                    cands.append(q)
        cands.sort(key=lambda q: norm(sub(q, c)))
        for q in cands:
            v = V(q)
            if not (solid[F].Contains(v) and solid[B].Contains(v)):
                continue
            if any(a.Contains(v) for a in avoid):
                continue
            if guard.gap(q, rv)[0] < MM(PAD_VIA_GAP):
                continue
            if not PL.via_ok(obs, q, gnd, boxes, PL.STITCH_GAP):
                continue
            PL.new_via(board, obs, q)
            added += 1
            break
    log("  edge stitching: %d GND vias added" % added)
    return added


# ------------------------------------------------------------------------------ round 2
# Final check N03-N11 and the jog / corner / gap work, on the stage 1 board (what the steps above leave).
# R2: explicit edits, board mm: (id, why, [ops]); ops:
#   ("del", net, layer, a, b)                  one segment, by its end points
#   ("cut", net, layer, a, b)                  the run of segments from node a to node b (shortest way along the net)
#   ("box", net, layer, p0, p1)                every segment of the net with both ends inside the box (router rings)
#   ("add", net, layer, width, [p0, p1, ...])  a polyline
#   ("w", net, layer, a, b, width)             the width of one segment
#   ("via-", net, p)  ("via+", net, p)  ("via>", net, p, q)    delete / add / move a via
# An edit is done when everything it adds is on the board; it is skipped, and reported, when something it
# replaces is missing. Each is checked with the clearance model; a GND stitching via in the way is deleted
# and the pours are stitched again afterwards.
R2 = [
    ("DTR-LDR",
     "DTR's two jogs round R13 pad 2 and the IO0 via, and LDR's jog round the IR via: the IO0 via moves 0.30 mm right, the IR via"
     " 0.36 mm right and T6's long vertical 0.05 mm right, so DTR (x 86.54) and LDR (x 87.755) run straight between them",
     [("cut", "DTR", "F.Cu", (79.475, 30.975), (83.875, 36.175)),
      ("add", "DTR", "F.Cu", 0.2, [(79.475, 30.975), (86.19, 30.975), (86.54, 31.325), (86.54, 33.51), (83.875, 36.175)]),
      ("cut", "LDR", "F.Cu", (87.7547, 42.7), (92.1047, 26.0)),
      ("add", "LDR", "F.Cu", 0.2, [(87.7547, 42.7), (87.7547, 30.35), (92.1047, 26.0)]),
      ("via>", "IO0", (86.8464, 32.9109), (87.145, 32.9109)),
      ("del", "IO0", "B.Cu", (80.8824, 32.9109), (86.8464, 32.9109)),
      ("add", "IO0", "B.Cu", 0.2, [(80.8824, 32.9109), (87.145, 32.9109)]),
      ("cut", "IO0", "F.Cu", (85.9375, 35.5), (86.8464, 32.9109)),
      ("add", "IO0", "F.Cu", 0.2, [(85.9375, 35.5), (87.145, 34.2925), (87.145, 32.9109)]),
      ("via>", "IR", (88.0156, 32.274), (88.38, 32.274)),
      ("del", "IR", "B.Cu", (88.0156, 32.274), (79.3073, 32.274)),
      ("add", "IR", "B.Cu", 0.2, [(79.3073, 32.274), (88.38, 32.274)]),
      ("cut", "IR", "F.Cu", (92.2656, 26.46), (88.1156, 32.01)),
      ("add", "IR", "F.Cu", 0.2, [(92.2656, 26.46), (88.38, 30.3456), (88.38, 32.274)]),
      ("cut", "T6", "F.Cu", (92.2729, 27.84), (86.7737, 46.7785)),
      ("add", "T6", "F.Cu", 0.2, [(92.2729, 27.84), (89.0, 31.1129), (89.0, 44.5522), (86.7737, 46.7785)])]),
    ("U0RXD-3V3",
     "U0RXD's 0.32 mm jog and 3V3's 0.18 mm jog both dodged the U0TXD via at (73.23, 46.49): the via moves 0.47 mm right along"
     " its B.Cu track, U0RXD and 3V3 run straight at 45 deg past it",
     [("via>", "U0TXD", (73.2287, 46.4893), (73.7, 46.4893)),
      ("del", "U0TXD", "B.Cu", (73.2287, 46.4893), (73.2141, 46.4893)),
      ("add", "U0TXD", "B.Cu", 0.2, [(73.2141, 46.4893), (73.7, 46.4893)]),
      ("cut", "U0TXD", "F.Cu", (79.1201, 44.1076), (73.2287, 46.4893)),
      ("add", "U0TXD", "F.Cu", 0.2, [(79.1201, 44.1076), (76.0817, 44.1076), (73.7, 46.4893)]),
      ("cut", "U0RXD", "F.Cu", (70.5945, 44.2523), (77.6905, 47.091)),
      ("add", "U0RXD", "F.Cu", 0.2, [(70.5945, 44.2523), (73.4332, 47.091), (77.6905, 47.091)]),
      ("cut", "3V3", "F.Cu", (69.9, 44.7), (80.15, 47.75)),
      ("add", "3V3", "F.Cu", 0.6, [(69.9, 44.7), (72.95, 47.75), (80.15, 47.75)])]),
    ("KEY-U0RXD",
     "KEY's 0.50 mm jog below the MCP_INT via, and U0RXD's two-via hop to B.Cu that hid a 0.29 mm step (30.95, 21.42 / 22.54):"
     " MCP_INT leaves its via straight (y 20.68), KEY runs on y 21.3 to one 45 deg lane change (1.52 mm, to y 22.82 beside U0RXD),"
     " U0RXD runs on y 22.83 on F.Cu, both vias gone",
     [("cut", "MCP_INT", "F.Cu", (28.8955, 20.6768), (41.3666, 17.2589)),
      ("add", "MCP_INT", "F.Cu", 0.2, [(28.8955, 20.6768), (37.9487, 20.6768), (41.3666, 17.2589)]),
      ("cut", "KEY", "F.Cu", (57.6, 23.6), (11.8, 21.3)),
      ("add", "KEY", "F.Cu", 0.2, [(57.6, 23.6), (56.82, 22.82), (41.67, 22.82), (40.15, 21.3), (11.8, 21.3)]),
      ("via-", "U0RXD", (30.955, 22.5407)), ("via-", "U0RXD", (30.955, 21.4242)),
      ("del", "U0RXD", "B.Cu", (30.955, 22.5407), (30.955, 21.4242)),
      ("del", "U0RXD", "F.Cu", (30.955, 21.4242), (32.3572, 22.8264)),
      ("del", "U0RXD", "F.Cu", (41.0923, 22.8264), (32.3572, 22.8264)),
      ("del", "U0RXD", "F.Cu", (30.955, 22.5407), (7.8165, 22.5407)),
      ("del", "U0RXD", "F.Cu", (7.8165, 22.5407), (2.3568, 17.081)),
      ("add", "U0RXD", "F.Cu", 0.2, [(2.3568, 17.081), (8.1022, 22.8264), (41.0923, 22.8264)])]),
    ("SDA-SCL",
     "SDA's 0.40 mm jog on B.Cu beside the SCL via (14.62, 29.51), the doubled SCL track above that via, SDA's two half-joined"
     " pieces at y 40.2 and the 0.23 mm bare strip between SCL and SDA: SCL runs on x 14.416 through its upper via (moved 0.10 mm"
     " onto the track) to its lower via (moved 0.45 mm left, onto the x 14.17 lane it continues on); SDA runs on x 15.107 straight"
     " into its via (0.69 mm from SCL: no strip left), leaves it at 45 deg and runs straight down x 14.817 into J4 pin 4, which it"
     " only touched at the rim",
     [("via>", "SCL", (14.6236, 29.5131), (14.1736, 29.5131)),
      ("del", "SCL", "F.Cu", (14.6236, 29.5131), (6.0514, 29.5131)),
      ("add", "SCL", "F.Cu", 0.2, [(6.0514, 29.5131), (14.1736, 29.5131)]),
      ("via>", "SCL", (14.5119, 24.5142), (14.4156, 24.5142)),
      ("del", "SCL", "F.Cu", (15.2619, 23.8642), (14.7619, 24.3642)),
      ("add", "SCL", "F.Cu", 0.2, [(15.2619, 23.8642), (14.6119, 24.5142), (14.4156, 24.5142)]),
      ("del", "SCL", "B.Cu", (15.1136, 3.7435), (14.4391, 4.418)),
      ("del", "SCL", "B.Cu", (14.4391, 4.418), (14.4391, 29.4217)),
      ("del", "SCL", "B.Cu", (14.4391, 29.4217), (14.5321, 29.5147)),
      ("del", "SCL", "B.Cu", (14.5321, 29.5147), (14.622, 29.5147)),
      ("del", "SCL", "B.Cu", (14.5321, 29.5147), (14.3821, 29.6647)),
      ("del", "SCL", "B.Cu", (14.4698, 24.5563), (14.4698, 29.3593)),
      ("del", "SCL", "B.Cu", (14.4698, 29.3593), (14.6236, 29.5131)),
      ("del", "SCL", "B.Cu", (14.5119, 24.5142), (14.4698, 24.5563)),
      ("del", "SCL", "B.Cu", (14.4736, 29.7631), (14.1736, 30.0631)),
      ("del", "SCL", "B.Cu", (14.1736, 30.0631), (14.1736, 45.0131)),
      ("add", "SCL", "B.Cu", 0.2, [(15.1136, 3.7435), (14.4156, 4.4415), (14.4156, 24.5142)]),
      ("add", "SCL", "B.Cu", 0.2, [(14.4156, 24.5142), (14.4156, 29.2711), (14.1736, 29.5131)]),
      ("add", "SCL", "B.Cu", 0.2, [(14.1736, 29.5131), (14.1736, 45.0131)]),
      ("cut", "SDA", "B.Cu", (20.7, 7.44), (15.1067, 27.6115)),
      ("add", "SDA", "B.Cu", 0.2, [(20.7, 7.44), (15.1067, 13.0333), (15.1067, 27.6115)]),
      ("del", "SDA", "B.Cu", (15.2666, 29.8115), (15.2666, 27.8615)),
      ("del", "SDA", "B.Cu", (14.8666, 30.2115), (15.2666, 29.8115)),
      ("del", "SDA", "B.Cu", (14.8666, 40.2115), (14.8666, 30.2115)),
      ("del", "SDA", "B.Cu", (14.8166, 62.4115), (14.8166, 40.2615)),
      ("add", "SDA", "B.Cu", 0.2, [(15.1067, 27.6115), (14.8166, 27.9016), (14.8166, 61.7366), (15.64, 62.56)])]),
    ("IR-C1",
     "IR's 0.35 mm jog between C1's pads (N04): no 45 deg track fits between the two pad corners (0.56 mm free, 0.65 needed), so IR"
     " crosses the gap square for 2.15 mm, 0.35 mm from pad 1 (x 51.6: no bare strip on that side, the pour fills the other),"
     " and ends on its via's centre (it stopped 0.29 mm short)",
     [("cut", "IR", "F.Cu", (17.675, 54.3641), (54.975, 50.2641)),
      ("add", "IR", "F.Cu", 0.2, [(17.675, 54.3641), (51.1959, 54.3641), (51.6, 53.96), (51.6, 51.81), (53.2459, 50.1641), (55.2463, 50.1641)])]),
    ("SCK-roof",
     "SCK on B.Cu at (45.14, 13.38) (N05): a 90 deg turn through one 0.07 mm piece, then 2.2 mm down and 45 deg again: the run"
     " turns once, 0.5 mm after the 45 deg rise, and goes straight to the x 52.49 lane",
     [("cut", "SCK", "B.Cu", (43.792, 13.3281), (52.492, 22.9281)),
      ("add", "SCK", "B.Cu", 0.2, [(43.792, 13.3281), (44.3, 13.3281), (52.492, 21.5201), (52.492, 22.9281)])]),
    ("WA6",
     "WA6 on B.Cu (31.74, 60.03, N05): the 90 deg tip of its detour round the WB2 via becomes a 0.5 mm straight between two 45 deg"
     " bends (the detour stays 1.6 mm deep: a lane change, not a jog)",
     [("cut", "WA6", "B.Cu", (30.14, 29.3854), (29.54, 62.2354)),
      ("add", "WA6", "B.Cu", 0.2, [(30.14, 29.3854), (30.14, 57.9354), (31.74, 59.5354), (31.74, 60.0354), (29.54, 62.2354)])]),
    ("WB2-J4",
     "WB2 on B.Cu left J4 pin 15 at its rim, went 0.8 mm the wrong way and turned back 135 deg (32.23, 65.38): it leaves the pad"
     " centre at 45 deg and runs 2.2 mm straight up between the pins",
     [("cut", "WB2", "B.Cu", (31.68, 64.8279), (32.08, 61.9779)),
      ("add", "WB2", "B.Cu", 0.2, [(30.88, 65.1), (31.16, 65.1), (32.08, 64.18), (32.08, 61.9779)])]),
    ("SIM2-J6",
     "SIM2 on F.Cu left J6 pin 15 at its rim, went 0.85 mm the wrong way and turned back 135 deg (95.31, 21.57): it leaves the"
     " pad centre downwards and joins the run between the pin rows with one 45 deg bend",
     [("cut", "SIM2", "F.Cu", (94.715, 20.97), (91.965, 21.42)),
      ("add", "SIM2", "F.Cu", 0.2, [(95.1, 20.22), (95.1, 21.0), (94.68, 21.42), (91.965, 21.42)])]),
    ("U7-3V3",
     "3V3 between U7 pins 16 and 4 (N07): the track ended 0.2 mm outside pin 16 (joined by its round cap), a 0.05 mm stray piece"
     " lay beside it, and the other end met pin 4 at its corner through a ring of router pieces: the track starts on pin 16's"
     " centre line inside the pad and enters pin 4 on its centre line (the 90 deg turn above pin 4 stays: pins 15 and 3 leave a"
     " 0.80 mm throat, the 0.6 mm track with its clearances needs 1.10, so no 45 deg run reaches pin 4)",
     [("del", "3V3", "F.Cu", (77.805, 41.45), (77.805, 41.5)),
      ("del", "3V3", "F.Cu", (80.013, 43.9), (77.813, 41.7)),
      ("del", "3V3", "F.Cu", (81.213, 43.9), (80.013, 43.9)),
      ("box", "3V3", "F.Cu", (81.1, 43.7), (81.3, 43.95)),
      ("del", "3V3", "F.Cu", (81.113, 44.55), (81.113, 43.8)),
      ("del", "3V3", "F.Cu", (81.365, 44.7535), (81.365, 45.475)),
      ("add", "3V3", "F.Cu", 0.6, [(77.555, 40.825), (77.555, 41.442), (80.013, 43.9), (81.295, 43.9), (81.365, 43.97), (81.365, 45.475)])]),
    ("3V3-R10",
     "3V3 at R10 (cap-only joins): the y 40.32 run stopped 0.28 mm short of the track from R10 pad 1, and the 45 deg track from"
     " SW1 ended 0.29 mm beside it: the run reaches the first, the second drops square onto it",
     [("del", "3V3", "F.Cu", (44.5, 40.3163), (32.7, 40.3163)),
      ("add", "3V3", "F.Cu", 0.6, [(44.5, 40.3163), (32.425, 40.3163)]),
      ("add", "3V3", "F.Cu", 0.6, [(34.925, 40.025), (34.925, 40.3163)])]),
    ("3V3P-U8",
     "3V3P at the LIS3DH (cap-only joins): the 0.6 mm track from C15 ended 0.12 mm above the 0.25 mm supply track, and the 0.6 mm"
     " track from R20 0.28 mm beside it: a 0.25 mm piece drops each square onto the centre line of the track it feeds (the 0.6 mm"
     " track itself would come within 0.10 mm of LIS3DH pad 16; a 45 deg join would be an acute junction)",
     [("add", "3V3P", "F.Cu", 0.25, [(37.475, 32.475), (37.475, 32.6)]),
      ("add", "3V3P", "F.Cu", 0.25, [(40.75, 37.7), (40.55, 37.5)])]),
    ("5V-C1-U5",
     "the 15 x 0.8 mm bare strip between U0TXD (y 48.11) and the 5V run C1 - U5 (N06): the run is 1.0 mm wide now (was 0.6) and"
     " its centre moves 0.2 mm up to y 49.11, so its lower edge stays where it was (0.25 mm above the IR via) and no pour fits"
     " above it any more",
     [("del", "5V", "F.Cu", (49.2, 53.0), (52.8892, 49.3108)),
      ("del", "5V", "F.Cu", (52.8892, 49.3108), (68.7608, 49.3108)),
      ("del", "5V", "F.Cu", (68.7608, 49.3108), (69.15, 49.7)),
      ("add", "5V", "F.Cu", 1.0, [(49.2, 53.0), (53.09, 49.11), (68.56, 49.11)]),
      ("add", "5V", "F.Cu", 1.2, [(68.56, 49.11), (69.15, 49.7)])]),
    ("5V-trunk",
     "the 15.6 x 0.75 mm bare strip on B.Cu between the 1.2 mm 5V trunk and SCK (N06): the trunk moves 0.08 mm right to x 49.52"
     " (0.67 mm from SCK: less than a pour strip needs; x 49.94 as proposed would touch the BUZZ via at (50.86, 41.85), and beyond"
     " x 49.52 the trunk comes within 0.25 mm of the GND fan-out via at (50.60, 33.75))",
     [("del", "5V", "B.Cu", (43.5257, 64.3188), (49.4433, 58.4012)),
      ("del", "5V", "B.Cu", (49.4433, 58.4012), (49.4433, 32.4273)),
      ("add", "5V", "B.Cu", 0.6, [(43.5257, 64.3188), (49.52, 58.3245)]),
      ("add", "5V", "B.Cu", 1.2, [(49.52, 58.3245), (49.52, 32.504), (49.4433, 32.4273)])]),
    ("GND-vias",
     "a second GND via on the two B.Cu pour pieces the standards pass left with one (N06): 38.6 mm2 below U1 and 16.2 mm2 left of U8",
     [("via+", "GND", (9.46, 62.47)), ("via+", "GND", (43.33, 46.48))]),
    ("J9-S",
     "the stitching via at (1.75, 57.25) held the spot of J9's \"S\" label (N10): 0.65 mm down",
     [("via>", "GND", (1.75, 57.25), (1.75, 57.9))]),
]


def _pm(v):
    """Board mm of a KiCad point, unrounded."""
    return (TOMM(int(v.x)) - PL.OX, TOMM(int(v.y)) - PL.OY)


def _near(p, q, tol=TOL):
    return abs(p[0] - q[0]) < tol and abs(p[1] - q[1]) < tol


def _pt_seg(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    if L2 < 1e-18:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def net_tracks(board, net, layer):
    return [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == net
            and board.GetLayerName(t.GetLayer()) == layer]


def covered(board, net, layer, a, b):
    """A track of the net runs over the whole of a-b (merge_collinear may have joined it to its neighbour)."""
    return any(_pt_seg(a, _pm(t.GetStart()), _pm(t.GetEnd())) < TOL and _pt_seg(b, _pm(t.GetStart()), _pm(t.GetEnd())) < TOL
               for t in net_tracks(board, net, layer))


def cut_run(board, net, layer, a, b):
    """The segments on the shortest way (fewest pieces) from node a to node b along the net's tracks."""
    segs = net_tracks(board, net, layer)
    adj = {}
    for t in segs:
        ka, kb = PL.key(pt(t.GetStart())), PL.key(pt(t.GetEnd()))
        adj.setdefault(ka, []).append((kb, t))
        adj.setdefault(kb, []).append((ka, t))
    pos = {k: (TOMM(k[0] * 1000) - PL.OX, TOMM(k[1] * 1000) - PL.OY) for k in adj}
    src = [k for k in adj if _near(pos[k], a)]
    dst = [k for k in adj if _near(pos[k], b)]
    if not src or not dst:
        return None
    prev = {src[0]: None}
    queue = [src[0]]
    while queue:
        u = queue.pop(0)
        if u == dst[0]:
            break
        for v, t in adj[u]:
            if v not in prev:
                prev[v] = (u, t)
                queue.append(v)
    if dst[0] not in prev:
        return None
    out, u = [], dst[0]
    while prev[u] is not None:
        out.append(prev[u][1])
        u = prev[u][0]
    return out


def apply_r2(board, edits):
    done = skipped = 0
    for eid, why, ops in edits:
        adds = [(op[1], op[2], op[3], p, q) for op in ops if op[0] == "add" for p, q in zip(op[4], op[4][1:])]
        vnew = [(op[1], op[2] if op[0] == "via+" else op[3]) for op in ops if op[0] in ("via+", "via>")]
        wide = [op for op in ops if op[0] == "w"]
        gone = [op for op in ops if op[0] in ("del", "via-")]
        if all(covered(board, n, l, p, q) for n, l, w, p, q in adds) and all(find_via(board, n, p) is not None for n, p in vnew) and \
                all((lambda t: t is not None and abs(TOMM(t.GetWidth()) - op[5]) < 1e-4)(find_track(board, op[1], op[2], op[3], op[4])) for op in wide) and \
                ((adds or vnew or wide) or all((find_track(board, op[1], op[2], op[3], op[4]) if op[0] == "del" else find_via(board, op[1], op[2])) is None
                                               for op in gone)):
            log("  r2 %s: already done" % eid)
            continue
        ctx = Ctx(board)
        ch, missing = [], []
        for op in ops:
            if op[0] == "del":
                t = find_track(board, op[1], op[2], op[3], op[4])
                if t is None:
                    missing.append("segment %s %s %s-%s" % (op[1], op[2], op[3], op[4]))
                else:
                    ch.append(("del", t))
            elif op[0] == "cut":
                ts = cut_run(board, op[1], op[2], op[3], op[4])
                if ts is None:
                    missing.append("run %s %s %s..%s" % (op[1], op[2], op[3], op[4]))
                else:
                    ch += [("del", t) for t in ts]
            elif op[0] == "box":
                (xa, ya), (xb, yb) = op[3], op[4]
                for t in net_tracks(board, op[1], op[2]):
                    s, e = _pm(t.GetStart()), _pm(t.GetEnd())
                    if min(xa, xb) - TOL <= min(s[0], e[0]) and max(s[0], e[0]) <= max(xa, xb) + TOL and \
                            min(ya, yb) - TOL <= min(s[1], e[1]) and max(s[1], e[1]) <= max(ya, yb) + TOL:
                        ch.append(("del", t))
            elif op[0] in ("via-", "via>"):
                v = find_via(board, op[1], op[2])
                if v is None:
                    missing.append("via %s %s" % (op[1], op[2]))
                else:
                    ch.append(("del", v) if op[0] == "via-" else ("via", v, P(*op[3])))
            elif op[0] == "w":
                t = find_track(board, op[1], op[2], op[3], op[4])
                if t is None:
                    missing.append("segment %s %s %s-%s" % (op[1], op[2], op[3], op[4]))
                else:
                    ch.append(("seg", t, pt(t.GetStart()), pt(t.GetEnd()), MM(op[5])))
        if missing:
            skipped += 1
            log("  r2 %s: SKIPPED, not on the board: %s" % (eid, "; ".join(missing)))
            continue
        seen, uniq = set(), []
        for c in ch:                                 # a segment named twice (cut + box) is deleted once
            k = (c[0], uid(c[1]))
            if k not in seen:
                seen.add(k)
                uniq.append(c)
        for op in ops:
            if op[0] == "add":
                nc, lay = board.FindNet(op[1]).GetNetCode(), board.GetLayerID(op[2])
                uniq += [("add", nc, lay, MM(op[3]), P(*p), P(*q)) for p, q in zip(op[4], op[4][1:])]
            elif op[0] == "via+":
                uniq.append(("addvia", board.FindNet(op[1]).GetNetCode(), P(*op[2])))
        txn = Txn(ctx)
        txn.apply(uniq)
        if not resolve(ctx, txn, 0, eid):
            txn.rollback()
            skipped += 1
            log("  r2 %s: NOT applied (clearance)" % eid)
            continue
        txn.commit()
        PL.merge_collinear(board)
        done += 1
        log("  r2 %s: %s" % (eid, why))
    return done, skipped


def strays(board):
    """Segments that lie in one pad or via of their net and join nothing (both ends alone): router leftovers
    of pad entries that were moved. Deleted (N07). The same test as pcb_audit.py's 'orphan'."""
    n = 0
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
    vias = [v for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
    for _ in range(4):
        dead = []
        groups = PL.track_groups(board)
        for (net, layer), segs in groups.items():
            ends = {}
            for t in segs:
                ends.setdefault(PL.key(pt(t.GetStart())), []).append(t)
                ends.setdefault(PL.key(pt(t.GetEnd())), []).append(t)

            def host(v):
                for p in pads:
                    if p.GetNetCode() == net and p.IsOnLayer(layer) and p.HitTest(v):
                        return uid(p)
                for x in vias:
                    if x.GetNetCode() == net and x.HitTest(v, 0):
                        return uid(x)
                return None
            cand = []
            for t in segs:
                if len(ends[PL.key(pt(t.GetStart()))]) == 1 and len(ends[PL.key(pt(t.GetEnd()))]) == 1:
                    ha, hb = host(t.GetStart()), host(t.GetEnd())
                    if ha is not None and ha == hb:
                        cand.append(t)
            cu = {uid(t) for t in cand}
            for t in cand:
                # no other track (that is not such a piece itself) may sit on one of its ends
                alone = True
                for e in (t.GetStart(), t.GetEnd()):
                    for t2 in segs:
                        if uid(t2) != uid(t) and uid(t2) not in cu and pcbnew.SEG(t2.GetStart(), t2.GetEnd()).Distance(e) <= MM(0.01):
                            alone = False
                if alone:
                    dead.append(t)
        if not dead:
            break
        for t in dead:
            log("  stray segment of %s on %s at %s - %s (inside one pad / via, joins nothing): deleted" % (
                t.GetNetname(), board.GetLayerName(t.GetLayer()), bm(pt(t.GetStart())), bm(pt(t.GetEnd()))))
            board.Delete(t)
            n += 1
        del dead
    return n


PAD_DEPTH = 0.15                            # mm: a track end lies at least this far inside a through-hole pad


def pad_joins(board):
    """Track ends that stop on the rim of a round through-hole pad of their net (the router's pad entries, cut
    back by polish.py): the last segment runs on along its own line, inside the pad's copper, until its end
    lies PAD_DEPTH inside the pad, so the joint does not depend on the cap of the track (pcb_audit.py: 'meets
    through-hole pad at its rim'). No new segment, no new direction."""
    n = 0
    for (net, layer), segs in PL.track_groups(board).items():
        ends = {}
        for t in segs:
            ends.setdefault(PL.key(pt(t.GetStart())), []).append(t)
            ends.setdefault(PL.key(pt(t.GetEnd())), []).append(t)
        pads = [p for fp in board.GetFootprints() for p in fp.Pads()
                if p.GetNetCode() == net and p.HasHole() and p.IsOnLayer(layer) and p.GetSize(layer).x == p.GetSize(layer).y]
        for t in segs:
            for at_start in (True, False):
                e = pt(t.GetStart() if at_start else t.GetEnd())
                o = pt(t.GetEnd() if at_start else t.GetStart())
                if len(ends[PL.key(e)]) != 1:
                    continue
                for p in pads:
                    c = pt(p.GetPosition())
                    r = p.GetSize(layer).x / 2
                    if not p.HitTest(V(e)) or r - norm(sub(e, c)) >= t.GetWidth() / 2 - MM(0.01):
                        continue
                    u = unit(sub(e, o))
                    for ext in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7):
                        q = add(e, mul(u, MM(ext)))
                        q = (round(q[0] / 1000) * 1000.0, round(q[1] / 1000) * 1000.0)
                        if r - norm(sub(q, c)) >= MM(PAD_DEPTH):
                            if at_start:
                                t.SetStart(V(q))
                            else:
                                t.SetEnd(V(q))
                            n += 1
                            log("  %s on %s met %s pad %s at its rim (%s): the track runs on %.1f mm into the pad" % (
                                t.GetNetname(), board.GetLayerName(layer), p.GetParentFootprint().GetReference(), p.GetNumber(), bm(e), ext))
                            break
                    else:
                        log("  %s on %s meets %s pad %s at its rim (%s): its line does not lead into the pad, left" % (
                            t.GetNetname(), board.GetLayerName(layer), p.GetParentFootprint().GetReference(), p.GetNumber(), bm(e)))
                    break
    return n


CORNER_SPAN = 0.45                           # mm: a turn of 90 deg or more within this length is a tight corner
CORNER_CUTS = (1.0, 0.8, 0.6, 0.5, 0.45, 0.4, 0.35, 0.32)   # mm cut back from the corner point (chamfer = cut x 1.414)
TINY = 0.1


def tight_corners(pts):
    """[(i, j, turn deg)]: pieces i and j (both >= TINY) of a run with everything between them shorter than
    CORNER_SPAN in all, and a turn of 90 deg or more from i to j (pcb_audit.py's tight corner / hairpin)."""
    d = [sub(pts[k + 1], pts[k]) for k in range(len(pts) - 1)]
    L = [norm(x) for x in d]
    out = []
    for i in range(len(d)):
        if L[i] < MM(TINY):
            continue
        span = 0.0
        best = None
        for j in range(i + 1, len(d)):
            if L[j] < MM(TINY):
                span += L[j]
                if span >= MM(CORNER_SPAN):
                    break
                continue
            if j > i + 1:
                c = max(-1.0, min(1.0, dot(unit(d[i]), unit(d[j]))))
                turn = math.degrees(math.acos(c))
                if turn > 89.0 and (best is None or turn > best[2] + 1.0):
                    best = (i, j, turn)
            span += L[j]
            if span >= MM(CORNER_SPAN):
                break
        if best:
            out.append(best)
    return out


def run_jogs(pts):
    """Jogs in a run as pcb_audit.py counts them: pieces shorter than TINY merged into the point they stand for,
    collinear pieces joined, then every 45 deg step (one slanted piece, or merged pieces only) between two
    pieces of one heading that shifts the run sideways by less than polish.JOG_MAX_OFFSET."""
    segs = [(pts[k], pts[k + 1]) for k in range(len(pts) - 1) if norm(sub(pts[k + 1], pts[k])) >= MM(TINY)]
    q = []
    for a, b in segs:
        if q:
            u = unit(sub(q[-1][1], q[-1][0]))
            if dot(u, unit(sub(b, a))) > 0.99999 and abs(PL.cross(u, sub(a, q[-1][1]))) <= MM(0.005):
                q[-1] = (q[-1][0], b)
                continue
        q.append((a, b))
    n = 0
    for i in range(len(q) - 1):
        ua, uc = unit(sub(q[i][1], q[i][0])), unit(sub(q[i + 1][1], q[i + 1][0]))
        off = abs(PL.cross(ua, sub(q[i + 1][0], q[i][1])))
        if norm(sub(q[i + 1][0], q[i][1])) > 1 and dot(ua, uc) > 0.999 and MM(0.005) < off < MM(PL.JOG_MAX_OFFSET):
            n += 1
    for i in range(len(q) - 2):
        ua, ub, uc = [unit(sub(q[k][1], q[k][0])) for k in (i, i + 1, i + 2)]
        mid = norm(sub(q[i + 2][0], q[i][1]))
        off = abs(PL.cross(ua, sub(q[i + 2][0], q[i][1])))
        if dot(ua, uc) > 0.999 and abs(dot(ua, ub)) < 0.999 and mid < MM(PL.JOG_MAX_RUN) * 1.5 and \
                norm(sub(q[i + 1][1], q[i + 1][0])) < MM(PL.JOG_MAX_RUN) and MM(0.005) < off < MM(PL.JOG_MAX_OFFSET):
            n += 1
    return n


def corners(board):
    """Tight corners (a 90 deg turn made within CORNER_SPAN of track: a chamfer too short to see, or an arc
    of router pieces): the pieces between the two arms go and one 45 deg chamfer of at least 0.45 mm joins
    them, the longest of CORNER_CUTS that keeps every clearance, leaves both arms at least 0.3 mm long (or
    as long as they were) and detaches nothing. What it cannot widen is reported (hand edits in R2)."""
    fixed, left = 0, []
    tried = set()
    for _ in range(120):
        ctx = Ctx(board)
        todo = None
        for ci, (net, layer, pts, ts) in enumerate(ctx.chains):
            if ts[0].GetNetname() in PL.SKIP_NETS:
                continue
            for i, j, turn in tight_corners(pts):
                k = (net, layer, PL.key(pts[i + 1]))
                if k in tried:
                    continue
                tried.add(k)
                todo = (net, layer, pts, ts, i, j, turn)
                break
            if todo:
                break
        if not todo:
            break
        net, layer, pts, ts, i, j, turn = todo
        name = "%s %s at %s" % (ts[0].GetNetname(), board.GetLayerName(layer), bm(pts[i + 1]))
        if turn > 91.0:
            left.append((name, "%.0f deg turn (hairpin): needs a hand route" % turn))
            continue
        if ts[i].GetWidth() != ts[j].GetWidth():
            left.append((name, "the two arms have different widths"))
            continue
        ui, uj = unit(sub(pts[i + 1], pts[i])), unit(sub(pts[j + 1], pts[j]))
        K = PL.intersect(pts[i], ui, pts[j], uj)
        if K is None:
            continue
        la, lb = dot(sub(K, pts[i]), ui), dot(sub(pts[j + 1], K), uj)       # arm lengths measured from the corner point
        others = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == net and t.GetLayer() == layer
                  and uid(t) not in {uid(x) for x in ts[i:j + 1]}]
        ok = False
        why = "no room inside the corner"
        for c in CORNER_CUTS:
            cut = MM(c)
            keep_a, keep_b = la - cut, lb - cut
            if keep_a < min(MM(0.3), norm(sub(pts[i + 1], pts[i]))) - 1 or keep_b < min(MM(0.3), norm(sub(pts[j + 1], pts[j]))) - 1:
                why = "an arm is too short for a 0.45 mm chamfer"
                continue
            P1, P2 = sub(K, mul(ui, cut)), add(K, mul(uj, cut))
            P1 = (round(P1[0] / 1000) * 1000.0, round(P1[1] / 1000) * 1000.0)
            P2 = (round(P2[0] / 1000) * 1000.0, round(P2[1] / 1000) * 1000.0)
            # a branch that ends on a piece that goes would be cut off
            if any(PL.dist_point_seg(pt(e), P1, pts[i + 1]) < MM(0.01) or PL.dist_point_seg(pt(e), pts[j], P2) < MM(0.01) or
                   any(PL.dist_point_seg(pt(e), pts[m], pts[m + 1]) < MM(0.01) for m in range(i + 1, j))
                   for t in others for e in (t.GetStart(), t.GetEnd())):
                why = "a branch joins the corner"
                continue
            txn = Txn(ctx)
            ch = [("del", t) for t in ts[i + 1:j]]
            ch.append(("seg", ts[i], pts[i], P1) if norm(sub(pt(ts[i].GetStart()), pts[i])) < 2 else ("seg", ts[i], P1, pts[i]))
            ch.append(("seg", ts[j], P2, pts[j + 1]) if norm(sub(pt(ts[j].GetEnd()), pts[j + 1])) < 2 else ("seg", ts[j], pts[j + 1], P2))
            ch.append(("add", net, layer, ts[i].GetWidth(), P1, P2))
            txn.apply(ch)
            if resolve(ctx, txn, 0, "corner " + name):
                new = pts[:i + 1] + [P1, P2] + pts[j + 1:]
                if len(tight_corners(new)) < len(tight_corners(pts)) and run_jogs(new) <= run_jogs(pts):
                    txn.commit()
                    ok = True
                    fixed += 1
                    log("  corner %s: %d piece(s), %.2f mm -> one %.2f mm chamfer" % (
                        name, j - i - 1, TOMM(int(sum(norm(sub(pts[m + 1], pts[m])) for m in range(i + 1, j)))), c * math.sqrt(2)))
                    break
                why = "a wider chamfer makes another tight corner or a jog"
            txn.rollback()
        if ok:
            PL.merge_collinear(board)
        else:
            left.append((name, why))
    for name, why in left:
        log("  corner %s: left (%s)" % (name, why))
    return fixed, left


# N10 (silkscreen): R21's label 0.25 mm further from R1 (it sat 0.47 mm under R1's pads and read as R1's; it stays beside
# R21's lower pad); "S" beside J9 pin 3 on the same side as "G" and "+", right edges in line (the stitching via that
# held the spot moves 0.65 mm down: R2 "J9-S"); a 45 deg leader from J11's label to the socket's outline (the label
# stands 1.4 mm from it, below F1; a level leader would read as a minus sign). Positions are text anchors, board mm.
R2_TEXTS = [("ref", "R21", (46.752, 37.65)), ("text", "S", (1.336, 56.58))]
R2_LEADERS = [((88.35, 64.3), (87.35, 65.3))]


def silk_edits(board):
    n = 0
    for kind, name, pos in R2_TEXTS:
        if kind == "ref":
            t = board.FindFootprintByReference(name).Reference()
        else:
            t = next((d for d in board.GetDrawings() if d.GetClass() == "PCB_TEXT" and d.GetLayer() == pcbnew.F_SilkS and d.GetText() == name), None)
        if t is None:
            log("  silk %r: not on the board" % name)
            continue
        cur = _pm(t.GetPosition())
        if not _near(cur, pos, 0.005):
            t.SetPosition(R.P(*pos))
            n += 1
            log("  silk %r: moved (%.3f, %.3f) -> %s" % (name, cur[0], cur[1], pos))
    for a, b in R2_LEADERS:
        if any(d.GetClass() == "PCB_SHAPE" and d.GetLayer() == pcbnew.F_SilkS and _near(_pm(d.GetStart()), a) and _near(_pm(d.GetEnd()), b)
               for d in board.GetDrawings()):
            continue
        ln = pcbnew.PCB_SHAPE(board)
        ln.SetShape(pcbnew.SHAPE_T_SEGMENT)
        ln.SetStart(R.P(*a))
        ln.SetEnd(R.P(*b))
        ln.SetLayer(pcbnew.F_SilkS)
        ln.SetWidth(PL.LEADER_W)
        board.Add(ln)
        n += 1
        log("  silk leader %s - %s" % (a, b))
    return n


# N03: the four GND zones stay EDGE_LONG inside the two long (100 mm) edges, so JLCPCB can join its edge
# rails there by V-cut (copper >= 0.4 mm from the cut line); the short edges keep the 0.3 mm edge rule.
# N06: TAB_U6 reaches down to the IO0 track. N11: C19 / C2 / C8 pad 1 sit in the tab copper: thermal
# reliefs there (the regulator tab pads stay solid), so both pads of each capacitor heat alike in reflow.
EDGE_LONG = 0.5
_LONG = [(0.0, EDGE_LONG), (D.BOARD_W, EDGE_LONG), (D.BOARD_W, D.BOARD_H - EDGE_LONG), (0.0, D.BOARD_H - EDGE_LONG)]
R2_ZONES = {
    "GND_F": _LONG, "GND_B": _LONG, "GND_L2": _LONG, "GND_L3": _LONG,
    "TAB_U6": [(59.95, 40.6), (67.8, 40.6), (67.8, 46.75), (59.95, 46.75)],
}
TAB_RELIEF = (("C19", "1"), ("C2", "1"), ("C8", "1"))     # thermal relief in the tab copper
TAB_THERMAL = (0.3, 0.5)                    # mm gap / spoke, as the GND pours


def zone_edits(board):
    n = 0
    for z in board.Zones():
        if z.GetIsRuleArea():
            continue
        name = z.GetZoneName()
        want = R2_ZONES.get(name)
        if want is not None:
            o = z.Outline()
            have = [_pm(o.CVertex(k)) for k in range(o.TotalVertices())] if o.OutlineCount() == 1 else []
            if len(have) != len(want) or any(not _near(a, b) for a, b in zip(have, want)):
                o.RemoveAllContours()
                o.NewOutline()
                for x, y in want:
                    p = R.P(x, y)
                    o.Append(p.x, p.y)
                z.SetNeedRefill(True)
                n += 1
                log("  zone %s: outline now %s - %s" % (name, want[0], want[2]))
        if name.startswith("TAB_"):
            if z.GetThermalReliefGap() != MM(TAB_THERMAL[0]) or z.GetThermalReliefSpokeWidth() != MM(TAB_THERMAL[1]):
                z.SetThermalReliefGap(MM(TAB_THERMAL[0]))
                z.SetThermalReliefSpokeWidth(MM(TAB_THERMAL[1]))
                n += 1
    for ref, num in TAB_RELIEF:
        fp = board.FindFootprintByReference(ref)
        for p in fp.Pads():
            if p.GetNumber() == num and p.GetLocalZoneConnection() != pcbnew.ZONE_CONNECTION_THERMAL:
                p.SetLocalZoneConnection(pcbnew.ZONE_CONNECTION_THERMAL)
                n += 1
                log("  %s pad %s (%s): thermal relief in the tab copper" % (ref, num, p.GetNetname()))
    return n


# ------------------------------------------------------------------------------ main
def gnd_zones(board):
    out = {}
    for z in board.Zones():
        if not z.GetIsRuleArea() and z.GetNetname() == "GND":
            out[z.GetLayer()] = z
    return out


def save(board):
    pro = os.path.splitext(BOARD)[0] + ".kicad_pro"
    keep = open(pro, "rb").read() if os.path.exists(pro) else None
    pcbnew.SaveBoard(BOARD, board)
    if keep is not None:
        with open(pro, "wb") as f:
            f.write(keep)


def prune(board, zones):
    """route_prep.prune without its project-file rewrite: stitching vias KiCad's DRC finds unconnected
    or dangling are deleted, refill, save; repeated until none is left."""
    total = 0
    for _ in range(4):
        d = R.drc_json(BOARD)
        bad = {it["uuid"] for v in d.get("unconnected_items", []) + d.get("violations", [])
               if v["type"] in ("unconnected_items", "via_dangling") for it in v["items"]}
        dead = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"
                and t.m_Uuid.AsString() in bad and pure_stitch(board, t)]
        if not dead:
            break
        for t in dead:
            board.Delete(t)
        total += len(dead)
        del dead
        PL.fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        save(board)
    log("  prune: %d unconnected stitching vias removed" % total)


def main():
    board = R.load()
    log("std_fixes on %s" % BOARD)
    if board.GetTitleBlock().GetRevision() == REVISION:
        # the tool steps (maze re-routes, widening, stitching) are not repeatable on their own output:
        # they run once, on the rev 3 board; the explicit round-2 edits below check their own geometry
        log("stage 1: the board is already rev %s, skipped" % REVISION)
    else:
        stage1(board)
        if DRY:
            log("dry run: stage 1 not saved, round 2 not run")
            return
        if os.environ.get("D32_STAGE1_COPY"):
            import shutil
            shutil.copyfile(BOARD, os.environ["D32_STAGE1_COPY"])
        board = R.load()                    # round 2 always starts from the saved stage 1 board
    round2(board)


def stage1(board):
    log("tracks:")
    apply_edits(board, EDITS, "edit")
    apply_routes(board, JOG_EDITS, "jog")
    apply_routes(board, TRUNK, "5V trunk")
    log("schematic rev 2.1 parts:")
    new_parts(board)
    loops(board)
    straighten(board)
    # the jog tools' maze re-routes leave a new 0.05 mm ring where a re-routed run meets the rest, and the
    # step they were to remove sits behind it (moved, not gone): collapse the rings so the audit sees those
    # steps, and try the local moves only (a maze re-route would make another ring)
    if loops(board):
        straighten(board, maze=False)
        loops(board)
    widen(board)
    log("fan-outs and vias in pads:")
    fanouts(board)
    r4_via(board)
    loops(board)                            # the IR re-route round the moved R4 via leaves a ring too (N04)
    log("silkscreen:")
    if WIDEN_SILK:
        silk_strokes(board)
    new_labels(board)
    j5_label(board)
    legend(board)
    fiducials(board)                        # after the labels: each takes the free spot nearest its target
    marks(board)
    log("return vias:")
    return_vias(board)
    log("copper:")
    tab_zones(board)
    lis3dh(board)
    zones = gnd_zones(board)
    edge_stitch(board, zones)
    guard = PadGuard(board)
    boxes = PL.text_boxes(board) + guard.boxes(MM(PAD_VIA_GAP))
    nisl, left = PL.stitch_islands(board, zones, boxes, log)
    log("  island stitching: %d vias%s" % (nisl, "; left %s" % left if left else ""))
    nfl = PL.prune_floating_vias(board, zones)
    if nfl:
        log("  %d vias that joined only floating pieces removed" % nfl)
    PL.fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    if DRY:
        return
    save(board)
    prune(board, zones)


def round2(board):
    """Round 2 (final check N03-N11 and the jog / corner / gap work): explicit edits on the stage 1 board."""
    log("round 2:")
    for z in board.Zones():
        if not z.GetIsRuleArea():
            z.UnFill()
    n = strays(board)
    n += corners(board)[0]                  # the rule first: the explicit edits are written on what it leaves
    done, skipped = apply_r2(board, R2)
    n += done
    if done:
        n += strays(board)
        n += corners(board)[0]
    n += pad_joins(board)
    log("round 2 zones, silkscreen:")
    n += zone_edits(board)
    n += silk_edits(board)
    log("round 2 stitching:")
    n += len(return_vias(board)[0])
    zones = gnd_zones(board)
    n += edge_stitch(board, zones)
    guard = PadGuard(board)
    boxes = PL.text_boxes(board) + guard.boxes(MM(PAD_VIA_GAP))
    nisl, left = PL.stitch_islands(board, zones, boxes, log)
    log("  island stitching: %d vias%s" % (nisl, "; left %s" % left if left else ""))
    nfl = PL.prune_floating_vias(board, zones)
    if nfl:
        log("  %d vias that joined only floating pieces removed" % nfl)
    n += nisl + nfl
    if skipped:
        log("round 2: %d explicit edits NOT applied (see above)" % skipped)
    if n == 0:
        log("round 2: nothing to change; the board file is left as it is")
        return
    PL.fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    if DRY:
        log("dry run: not saved")
        return
    save(board)
    prune(board, zones)
    rep = R.drc_json(BOARD)
    bad = rep.get("violations", []) + rep.get("unconnected_items", []) + rep.get("schematic_parity", [])
    log("DRC (all severities): %d violations, %d unconnected" % (len(rep.get("violations", [])), len(rep.get("unconnected_items", []))))
    for v in bad[:20]:
        log("  %s: %s" % (v["type"], v["description"]))


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        sys.stdout.flush()
        os._exit(0 if e.code in (None, 0) else 1)
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
    sys.stdout.flush()
    os._exit(0)
