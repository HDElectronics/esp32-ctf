#!/usr/bin/env python3
"""Route the rev 2 carrier (defuse32-carrier.kicad_pcb) with Freerouting: KiCad 10.0.7 DSN/SES
round trip, then GND pours, stitching vias, silkscreen references and a report.

Used for the rev 2 routing (2026-10-23); kept as the record and for a full re-route. The rev 1b
version (DevKitC board, decoupling fix) is in git, tag carrier-rev1b. The routed board is edited
by hand in KiCad from now on; re-running this from `gen_pcb.py --force` throws that work away.
Run from hardware/defuse32/kicad/ with KiCad's Python (/usr/bin/python3, not conda):

  /usr/bin/python3 gen/gen_pcb.py --force            # placed, unrouted board (design.PCB)
  /usr/bin/python3 gen/route_prep.py prep            # locked pre-routes + GND fan-out vias
  /usr/bin/python3 gen/route_prep.py export /tmp/d32/r2.dsn
  java -jar ~/tools/freerouting-2.4.1/freerouting-2.4.1.jar -de /tmp/d32/r2.dsn -do /tmp/d32/r2.ses \\
       -mp 40 -mt 1 --gui.enabled=false --router.fanout.enabled=false --router.automatic_neckdown=true \\
       --router.scoring.via_costs=150 \\
       --router.optimizer.improvement_threshold=0 --router.optimizer.max_passes=10 \\
       --usage_and_diagnostic_data.disable_analytics=true --profile.allow_telemetry=false
  /usr/bin/python3 gen/route_prep.py import /tmp/d32/r2.ses
  /usr/bin/python3 gen/route_prep.py finish
  /usr/bin/python3 gen/route_prep.py report          # numbers only (also printed by finish)

Freerouting options: `-mt 1` because the multi-threaded optimizer is documented to break
clearances; without the two optimizer options Freerouting 2.4.1 skips the optimizer; its SMD
fan-out stage is off (it put a via on almost every SMD pin); neck-down lets Power-class tracks
narrow at fine-pitch pins; a via cost of 150 gave fewer vias than the default in test runs. The session the
board was built from is kept as out/defuse32-carrier.ses (`import` it after `prep` to rebuild the
same board); a new run differs and then needs its own HAND_FIXES. The settings options apply to this run only; the user's
~/.config/freerouting/freerouting.json is not written. One run takes about 10 minutes here.

Freerouting 2.4.1 does not count locked KiCad tracks (exported as `type fix` wiring) as connecting
their pads: it keeps trying to reach a pre-routed pad and reports it unrouted. So every net that is
completely hand-routed is taken out of the DSN network (HAND_NETS: its pins list is emptied; pads
and pre-routes stay as obstacles), and in partly pre-routed nets each pre-routed group keeps one
open pin and the others are taken out (PIN_EXCLUDE).

pcbnew.SaveBoard() rewrites defuse32-carrier.kicad_pro with every default filled in; every step
that saves rewrites it again with gen_pcb.write_project() (net classes, rules), so the project
file stays as generated. D32_BOARD=/path/to/copy.kicad_pcb runs any step on a copy (and leaves
the .kicad_pro alone). Items are taken off the board with BOARD.Delete() and the script exits with
os._exit(): see main() for the KiCad 10.0.7 SWIG problem this avoids.

prep    Adds PREROUTE / PREVIAS, all locked:
          - USB, completely by hand: CH340C - USBLC6 (flow-through under its body) - USB-C, D+
            crossing D- once on B.Cu next to the CH340C, the B6/A6 D+ jumper as a loop under the
            receptacle, CC1/CC2 to R14/R15, VBUS from both receptacle pads and U9 pin 5 to F1;
          - LIS3DH (U8, LGA-16, 0.5 mm pitch): 0.25 mm supply/GND fan-out to C14/C16/C15/R20 and
            two GND vias, SA0 to R20 (Freerouting would take the 0.6 mm Power width into 0.35 mm
            pads 0.15 mm apart);
          - U1 3V3 (pin 2) and GND (pin 1) to C10/C9, 0.6 mm, plus a GND via;
          - every GND pin of the box headers J1-J6: a 0.4 mm stub to a via 2 mm beyond the end of
            its row (under the header body);
        then the GND fan-out (gnd_fanout): every SMD GND pad not served above gets a 0.4 mm stub
        and a via to the bottom pour, at the first spot that keeps 0.25 mm from other copper,
        0.3 mm from the edge and stays out of the U1/J7/J11 courtyards and footprint keep-outs.
export  Writes the Specctra DSN with a temporary GND zone on each layer, so the DSN has a GND plane
        on F.Cu and B.Cu: Freerouting then takes every GND pin as connected (it routes no GND) but
        keeps the Power-class 0.25 mm clearance to them. (With GND pins simply left out of the
        network it treated them as netless and kept only 0.2 mm.) Checks the U1 antenna keep-out
        is in the DSN (footprint keep-out, all outside the outline), empties the HAND_NETS pin lists
        and takes the PIN_EXCLUDE pins out.
import  Reads the Freerouting session into the board (unlocked tracks and vias are replaced,
        locked ones stay; stops if a footprint moved by more than 1 um) and saves.
finish  Unlocks everything, removes Freerouting's sub-0.01 mm stubs, applies HAND_FIXES, sets the
        drill/place origin to the board's bottom-left corner, adds the GND pours on F.Cu and B.Cu
        (whole outline, 0.25 mm clearance, thermal reliefs) and stitches them:
          - the GND copper is split into connected components (pour pieces of both layers, pads,
            tracks, vias); every component apart from the main one (largest pour area) that has
            copper of its own, or a pour piece of A_MIN or more, gets a via at a spot inside one
            of its pieces and inside a main-component piece on the other layer (repeated until
            nothing changes; what cannot be joined is printed);
          - a grid of stitching vias (GRID mm) wherever both pours are solid, 1.5 mm from any
            other via, outside the U1/J7/J11 courtyards;
        refills with island removal, places the silkscreen references (gen_pcb.place_refs) and
        saves; then runs KiCad's DRC and deletes stitching vias it finds unconnected (a via that
        only joins two pour islands), refilling until none is left; prints the report.
report  Via count, track length per layer, Power tracks narrower than their class, decoupling
        distances (cap pad to IC supply pad, edge to edge and centre to centre), USB D+/D- lengths.
"""
import json
import math
import os
import re
import subprocess
import sys

import pcbnew

import design as D
from gen_pcb import OX, OY, place_refs, write_project

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(HERE, ".."))
BOARD = os.environ.get("D32_BOARD") or os.path.join(KDIR, "defuse32-carrier.kicad_pcb")
MM = pcbnew.FromMM
MAXERR = MM(0.005)
VIA_D, VIA_DRILL = MM(0.6), MM(0.3)
POWER_W = {n: D.NETCLASS["Power"][0] for n in D.POWER_NETS}


def P(x, y):
    """Board coordinates (mm, origin top-left of the outline) -> internal units (nm) on the page."""
    return pcbnew.VECTOR2I(int(round((OX + x) * 1e6)), int(round((OY + y) * 1e6)))


def bmm(v):
    return (round(pcbnew.ToMM(v.x) - OX, 3), round(pcbnew.ToMM(v.y) - OY, 3))


def load():
    return pcbnew.LoadBoard(BOARD)


def save(board):
    pcbnew.SaveBoard(BOARD, board)
    if not os.environ.get("D32_BOARD"):
        write_project()


def add_track(board, layer, net, w, a, b, locked=False):
    t = pcbnew.PCB_TRACK(board)
    t.SetStart(P(*a))
    t.SetEnd(P(*b))
    t.SetWidth(MM(w))
    t.SetLayer(layer)
    t.SetNet(board.FindNet(net))
    t.SetLocked(locked)
    board.Add(t)
    return t


def add_via(board, pos, net="GND", locked=False):
    """pos: VECTOR2I (page coordinates)."""
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pos)
    v.SetWidth(VIA_D)
    v.SetDrill(VIA_DRILL)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(board.FindNet(net))
    v.SetLocked(locked)
    board.Add(v)
    return v


# ------------------------------------------------------------------------------------- prep
F, B = pcbnew.F_Cu, pcbnew.B_Cu
# (layer, net, width mm, [points in board mm]); vias: (net, x, y). U8 at (38.0, 34.5), rotation 0:
# pads 1 VDD_IO (36.77, 33.5), 4 SCL (36.77, 35.0), 5 GND (36.77, 35.5), 6 SDA (37.5, 35.73),
# 7 SA0 (38.0, 35.73), 8 CS (38.5, 35.73), 10/12 GND (39.23, 35.0/34.0), 14 VDD (38.5, 33.27).
PREROUTE = [
    (F, "3V3P", 0.25, [(38.5, 33.27), (38.5, 31.5)]),                              # U8.14 - C14.1
    (F, "3V3P", 0.25, [(36.77, 33.5), (36.2, 33.5), (36.2, 32.6), (38.5, 32.6)]),  # U8.1 - U8.14
    (F, "3V3P", 0.25, [(36.78, 31.5), (36.78, 32.6)]),                              # C16.1
    (F, "3V3P", 0.25, [(38.5, 35.73), (38.5, 36.45), (39.62, 37.57)]),              # U8.8 (CS) - R20.1
    (F, "3V3P", 0.25, [(39.62, 37.7), (40.75, 37.7), (40.75, 32.4), (41.4, 32.4)]),  # R20.1 - C15.1
    (F, "GND", 0.25, [(39.23, 34.0), (40.06, 34.0)]),                               # U8.12
    (F, "GND", 0.25, [(39.23, 35.0), (40.06, 35.0)]),                               # U8.10
    (F, "GND", 0.25, [(40.06, 31.5), (40.06, 35.9)]),                               # C14.2 - via
    (F, "GND", 0.25, [(36.77, 35.5), (36.2, 35.5), (35.9, 36.0)]),                  # U8.5 - via
    (F, "LIS_SA0", 0.2, [(38.0, 35.73), (38.0, 37.7)]),                             # U8.7 - R20.2
    # I2C pull-ups R3 (SCL) / R2 (SDA) sit at the LIS3DH: its SCL/SDA pads are reached by hand and
    # Freerouting joins the bus at R3.2 / R2.2
    (F, "SCL", 0.2, [(36.77, 35.0), (35.4, 35.0), (35.0, 35.4)]),                    # U8.4 - R3.2
    (F, "SDA", 0.2, [(37.5, 35.73), (37.5, 36.4), (36.4, 37.5), (36.4, 37.68)]),     # U8.6 - R2.2
    (F, "3V3P", 0.25, [(34.6, 33.78), (35.2, 33.2), (36.2, 33.2)]),                  # R3.1 - U8.1 bridge
    # U1 pin 2 (3V3) -> C10.1 -> C9.1; pin 1 (GND) -> C10.2 -> C9.2 -> via
    (F, "3V3", 0.6, [(2.57, 43.75), (2.78, 46.0), (2.95, 48.1)]),
    (F, "GND", 0.6, [(1.3, 43.75), (1.22, 46.0), (1.05, 48.1), (1.1, 49.8)]),
    # USB, all hand-routed (HAND_NETS). U7 CH340C (82, 43) r90: UD+ pin 5 (82.635, 45.475), UD- pin 6
    # (83.905, 45.475). U9 USBLC6 (87.8, 49.5) r0: left 1 DP / 2 GND / 3 DM at x 86.66, right 6 DP / 5 VBUS /
    # 4 DM at x 88.94 (y 48.55 / 49.5 / 50.45); flow-through tracks under the body join 1-6 and 3-4.
    # J7 pads at x 92.31: B6 DP 48.75, A7 DM 49.25, A6 DP 49.75, B7 DM 50.25, CC2 47.75, CC1 50.75,
    # VBUS 47.05 / 51.95, GND 46.25 / 52.75. The CH340C pin order (D+ left of D-) is the mirror of what
    # J7 takes from the board side (D+ above D-), so D+ crosses D- once, on B.Cu between U7 and U9;
    # at J7, B6-A6 (D+) are joined by a loop under the receptacle and A7-B7 (D-) on the board side.
    (F, "USB_DP", 0.2, [(82.635, 45.475), (82.635, 47.4)]),                          # U7.5 - via
    (B, "USB_DP", 0.2, [(82.635, 47.4), (83.785, 48.55), (85.3, 48.55)]),            # under D-
    (F, "USB_DP", 0.2, [(85.3, 48.55), (86.66, 48.55), (88.94, 48.55), (90.5, 48.55), (90.7, 48.75),
                        (92.31, 48.75), (93.55, 48.75), (93.55, 49.75), (92.31, 49.75)]),  # U9.1-6, J7 B6, A6
    (F, "USB_DM", 0.2, [(83.905, 45.475), (83.905, 49.0), (85.355, 50.45), (86.66, 50.45), (88.94, 50.45),
                        (90.5, 50.45), (90.7, 50.25), (92.31, 50.25)]),               # U7.6 - U9.3-4 - J7 B7
    (F, "USB_DM", 0.2, [(92.31, 49.25), (91.1, 49.25), (91.1, 50.25)]),              # J7 A7 - B7
    (F, "CC2", 0.2, [(92.31, 47.75), (90.2, 47.75), (89.9, 47.45), (89.9, 46.02)]),  # J7 B5 - R15.1
    (F, "CC1", 0.2, [(92.31, 50.75), (91.45, 50.75), (91.0, 51.2), (90.2, 52.0), (90.2, 53.18)]),  # J7 A5 - R14.1
    # VBUS: both receptacle pads go to the board side (the alignment pegs, NPTH at (93.75, 46.61) and
    # (93.75, 52.39), sit right of them) and meet on B.Cu, with U9 pin 5, then up to F1 pad 1.
    (F, "VBUS", 0.6, [(92.31, 47.05), (90.8, 47.05)]),                               # J7 A9/B4
    (F, "VBUS", 0.6, [(92.31, 51.95), (91.3, 51.95), (91.0, 52.25)]),                # J7 A4/B9
    (B, "VBUS", 0.6, [(90.8, 47.05), (90.8, 49.5), (91.0, 49.7), (91.0, 52.25), (91.0, 55.45), (91.3, 55.75)]),
    (F, "VBUS", 0.6, [(91.3, 55.75), (91.3, 56.5)]),                                 # F1.1
    (F, "VBUS", 0.4, [(88.94, 49.5), (90.1, 49.5)]),                                 # U9.5
    (B, "VBUS", 0.6, [(90.1, 49.5), (90.8, 49.5)]),
    (F, "GND", 0.4, [(86.66, 49.5), (85.6, 49.4)]),                                  # U9.2 - via
    (F, "GND", 0.4, [(92.31, 46.25), (93.22, 45.18)]),                               # J7 A12/B1 - shield leg
    (F, "GND", 0.4, [(92.31, 52.75), (93.22, 53.82)]),                               # J7 A1/B12 - shield leg
    # Box-header GND pins: a stub along the row to a via 2 mm beyond the end pin (under the header
    # body), so the autorouter cannot close a pin in with signal tracks on both layers (it did with
    # J3 pin 16) and every GND pin has a via of its own.
    (F, "GND", 0.4, [(23.24, 7.44), (25.24, 7.44)]),                                 # J1.2
    (F, "GND", 0.4, [(49.8, 7.44), (51.8, 7.44)]),                                   # J2.2
    (F, "GND", 0.4, [(37.1, 7.44), (35.1, 7.44)]),                                   # J2.12
    (F, "GND", 0.4, [(81.8, 7.44), (83.8, 7.44)]),                                   # J3.2
    (F, "GND", 0.4, [(64.02, 7.44), (62.02, 7.44)]),                                 # J3.16
    (F, "GND", 0.4, [(13.1, 62.56), (11.1, 62.56)]),                                 # J4.2
    (F, "GND", 0.4, [(35.96, 62.56), (37.96, 62.56)]),                               # J4.20
    (F, "GND", 0.4, [(49.1, 62.56), (47.1, 62.56)]),                                 # J5.2
    (F, "GND", 0.4, [(64.34, 62.56), (66.34, 62.56)]),                               # J5.14
    (F, "GND", 0.4, [(92.56, 38.0), (92.56, 40.0)]),                                 # J6.2
    (F, "GND", 0.4, [(95.1, 15.14), (92.56, 15.14), (93.83, 13.1)]),                 # J6.19 - J6.20
]
PREVIAS = [("GND", 40.06, 35.9), ("GND", 35.9, 36.0), ("GND", 1.1, 49.8),
           ("USB_DP", 82.635, 47.4), ("USB_DP", 85.3, 48.55),
           ("VBUS", 90.8, 47.05), ("VBUS", 91.0, 52.25), ("VBUS", 91.3, 55.75), ("VBUS", 90.1, 49.5),
           ("GND", 85.6, 49.4),
           ("GND", 25.24, 7.44), ("GND", 51.8, 7.44), ("GND", 35.1, 7.44), ("GND", 83.8, 7.44), ("GND", 62.02, 7.44),
           ("GND", 11.1, 62.56), ("GND", 37.96, 62.56), ("GND", 47.1, 62.56), ("GND", 66.34, 62.56),
           ("GND", 92.56, 40.0), ("GND", 93.83, 13.1)]
# Nets Freerouting does not route because they are completely hand-routed (their pins are taken
# out of the DSN network; pads and pre-routes stay as obstacles). GND is not routed either: it is a
# plane on both layers in the DSN (see cmd_export) and made by the pours, the fan-out vias below
# and the stitching in `finish`.
HAND_NETS = ("VBUS", "USB_DP", "USB_DM", "CC1", "CC2", "LIS_SA0")
# Pins of partly pre-routed nets taken out of the DSN: each pre-routed group keeps one open pin
# (C15.1 for the LIS3DH 3V3P group, C9.1 for U1 3V3, R3.2 / R2.2 for SCL / SDA at the LIS3DH).
PIN_EXCLUDE = {
    "3V3P": ("U8-1", "U8-14", "U8-8", "C14-1", "C16-1", "R20-1", "R3-1"),
    "3V3": ("U1-2", "C10-1"),
    "SCL": ("U8-4",),
    "SDA": ("U8-6",),
}

# GND fan-out: a short stub and a via to the bottom pour next to every SMD GND pad that the
# pre-routes do not already serve (classic 2-layer practice: every return path one via long).
FAN_CLEAR = 0.25                  # Power-class clearance
FAN_STUB = 0.4
FAN_AVOID = ("J7", "J11", "U1")   # no fan-out via inside these courtyards (shells, module body)


def _obstacles(board):
    """[(net, layer, polygon, bbox, item)] for all copper: pads, tracks, vias."""
    obs = []
    for fp in board.GetFootprints():
        for pd in fp.Pads():
            for layer in (F, B):
                if pd.IsOnLayer(layer):
                    s = pcbnew.SHAPE_POLY_SET()
                    pd.TransformShapeToPolygon(s, layer, 0, MAXERR, pcbnew.ERROR_OUTSIDE)
                    if s.OutlineCount():
                        obs.append((pd.GetNetname(), layer, s, s.BBox(), pd))
    for t in board.GetTracks():
        for layer in ((F, B) if t.GetClass() == "PCB_VIA" else (t.GetLayer(),)):
            s = pcbnew.SHAPE_POLY_SET()
            t.TransformShapeToPolygon(s, layer, 0, MAXERR, pcbnew.ERROR_OUTSIDE)
            obs.append((t.GetNetname(), layer, s, s.BBox(), t))
    return obs


def _clear(obs, pts, r, layers, net):
    """True if every point keeps r + FAN_CLEAR from copper of other nets on the given layers."""
    d = MM(FAN_CLEAR) + r
    for onet, layer, s, bb, it in obs:
        if onet == net or layer not in layers:
            continue
        for p in pts:
            if p.x < bb.GetLeft() - d or p.x > bb.GetRight() + d or p.y < bb.GetTop() - d or p.y > bb.GetBottom() + d:
                continue
            if s.Collide(p, d):
                return False
    return True


def gnd_fanout(board):
    obs = _obstacles(board)
    gnd_tracks = [t for t in board.GetTracks() if t.GetNetname() == "GND"]
    holes = [(p.GetPosition(), max(p.GetDrillSizeX(), p.GetDrillSizeY()) // 2)
             for fp in board.GetFootprints() for p in fp.Pads() if p.HasHole()]
    vias = [t.GetPosition() for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    avoid = [board.FindFootprintByReference(r).GetCourtyard(pcbnew.F_CrtYd) for r in FAN_AVOID]
    keepouts = [z for fp in board.GetFootprints() for z in fp.Zones() if z.GetIsRuleArea()]
    lo, hi = P(0.7, 0.7), P(D.BOARD_W - 0.7, D.BOARD_H - 0.7)
    gnd = board.FindNet("GND")
    done, failed = [], []
    for fp in board.GetFootprints():
        fc = fp.GetPosition()
        for pd in fp.Pads():
            if pd.GetNetname() != "GND" or pd.HasHole() or not pd.IsOnLayer(F):
                continue
            if fp.GetReference() == "U1" and pd.GetNumber() == "39":
                continue                                  # thermal pad: has its own vias
            c = pd.GetPosition()
            if any(pd.HitTest(t.GetStart()) or pd.HitTest(t.GetEnd()) for t in gnd_tracks if t.GetClass() == "PCB_TRACK"):
                continue                                  # served by a pre-route
            bb = pd.GetBoundingBox()
            hw, hh = bb.GetWidth() / 2, bb.GetHeight() / 2
            out = (c.x - fc.x, c.y - fc.y)
            n0 = math.hypot(*out) or 1
            dirs = [(math.cos(a * math.pi / 8), math.sin(a * math.pi / 8)) for a in range(16)]
            dirs.sort(key=lambda v: -(v[0] * out[0] + v[1] * out[1]) / n0)
            best = None
            for extra in (0.0, 0.3, 0.6, 1.0):
                for vx, vy in dirs:
                    reach = abs(vx) * hw + abs(vy) * hh          # pad extent along the direction (rect approx.)
                    dist = reach + MM(FAN_CLEAR + 0.3 + 0.05 + extra)
                    p = pcbnew.VECTOR2I(int(c.x + vx * dist), int(c.y + vy * dist))
                    if not (lo.x <= p.x <= hi.x and lo.y <= p.y <= hi.y):
                        continue
                    if any(a.Contains(p) for a in avoid):
                        continue
                    if any(z.Outline().Collide(p, VIA_R + MM(0.1)) for z in keepouts):
                        continue
                    if any((p - q).EuclideanNorm() < MM(0.85) for q in vias):
                        continue
                    if any((p - hc).EuclideanNorm() < hr + VIA_R + MM(0.4) for hc, hr in holes):
                        continue
                    if not _clear(obs, [p], VIA_R, (F, B), "GND"):
                        continue
                    steps = max(2, int((p - c).EuclideanNorm() / MM(0.1)))
                    stub = [pcbnew.VECTOR2I(int(c.x + (p.x - c.x) * k / steps), int(c.y + (p.y - c.y) * k / steps))
                            for k in range(steps + 1)]
                    if not _clear(obs, stub, MM(FAN_STUB / 2), (F,), "GND"):
                        continue
                    best = p
                    break
                if best:
                    break
            label = "%s.%s" % (fp.GetReference(), pd.GetNumber())
            if best is None:
                failed.append(label)
                continue
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(c)
            t.SetEnd(best)
            t.SetWidth(MM(FAN_STUB))
            t.SetLayer(F)
            t.SetNet(gnd)
            t.SetLocked(True)
            board.Add(t)
            v = add_via(board, best, "GND", locked=True)
            vias.append(best)
            for item, layers in ((v, (F, B)), (t, (F,))):
                for layer in layers:
                    s = pcbnew.SHAPE_POLY_SET()
                    item.TransformShapeToPolygon(s, layer, 0, MAXERR, pcbnew.ERROR_OUTSIDE)
                    obs.append(("GND", layer, s, s.BBox(), item))
            gnd_tracks.append(t)
            done.append(label)
    return done, failed


def cmd_prep():
    board = load()
    if any(True for _ in board.GetTracks()):
        raise SystemExit("prep: the board already has tracks/vias (start from gen_pcb.py --force)")
    n = 0
    for layer, net, w, pts in PREROUTE:
        for a, b in zip(pts, pts[1:]):
            add_track(board, layer, net, w, a, b, locked=True)
            n += 1
    for net, x, y in PREVIAS:
        add_via(board, P(x, y), net, locked=True)
    done, failed = gnd_fanout(board)
    save(board)
    print("prep: %d locked track segments, %d locked vias; GND fan-out: %d pads (%s)"
          % (n, len(PREVIAS), len(done), " ".join(done)))
    if failed:
        print("prep: no fan-out spot for %s (left to the pours / stitching)" % " ".join(failed))


# ------------------------------------------------------------------------------------- export
def cmd_export(dst):
    board = load()
    if any(not z.GetIsRuleArea() for z in board.Zones()):
        raise SystemExit("export: the board has copper zones (export before `finish`)")
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    # temporary GND zones on both layers (not saved): exported as `plane GND`, so Freerouting takes
    # every GND pin as connected and routes no GND, but still knows those pins are GND (Power class,
    # 0.25 mm clearance). The real pours, fan-out vias and stitching come in `prep` / `finish`.
    for layer in (F, B):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNetCode(board.FindNet("GND").GetNetCode())
        o = z.Outline()
        o.NewOutline()
        for x, y in ((0, 0), (D.BOARD_W, 0), (D.BOARD_W, D.BOARD_H), (0, D.BOARD_H)):
            q = P(x, y)
            o.Append(q.x, q.y)
        board.Add(z)
    if not pcbnew.ExportSpecctraDSN(board, dst):
        raise SystemExit("ExportSpecctraDSN failed")
    t = open(dst).read()
    if t.count("(plane GND (polygon F.Cu") != 1 or t.count("(plane GND (polygon B.Cu") != 1 or t.count("(plane") != 2:
        raise SystemExit("expected exactly the two GND planes in the DSN")
    # U1 antenna keep-out (footprint local y -27.75 .. -6.56, x +-24) exported in the U1 image
    want = "-24000 27750  24000 27750  24000 6560  -24000 6560"
    n = sum(1 for line in t.splitlines() if "(keepout" in line and want in line)
    if n != 2:
        raise SystemExit("U1 antenna keep-out not found on F.Cu and B.Cu (%d)" % n)
    # HAND_NETS: empty pin lists, so Freerouting leaves them alone; their pads and pre-routes stay
    # in the DSN as obstacles
    for net in HAND_NETS:
        pat = re.compile(r'(\(net "?%s"?\s*\n\s*\(pins)[^)]*\)' % re.escape(net))
        t, k = pat.subn(r"\1)", t, count=1)
        if k != 1:
            raise SystemExit("export: net %s not found in the DSN network" % net)
    for net, pins in PIN_EXCLUDE.items():
        m = re.search(r'\(net "?%s"?\s*\n\s*\(pins([^)]*)\)' % re.escape(net), t)
        have = m.group(1).split()
        if any(p not in have for p in pins):
            raise SystemExit("export: %s pins %s not all in the DSN" % (net, pins))
        keep = " ".join(p for p in have if p not in pins)
        t = t[:m.start(1)] + " " + keep + t[m.end(1):]
    open(dst, "w").write(t)
    print("wrote %s: GND planes on F.Cu/B.Cu, U1 antenna keep-out, %d fixed wires; hand-routed nets left out: %s"
          % (dst, t.count("(type fix)") + t.count("(type protect)"), " ".join(HAND_NETS)))


# ------------------------------------------------------------------------------------- import
def cmd_import(ses):
    board = load()
    pos = {fp.GetReference(): (fp.GetPosition().x, fp.GetPosition().y) for fp in board.GetFootprints()}
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise SystemExit("ImportSpecctraSES failed")
    # the DSN/SES round trip rounds positions to 0.1 um: only real moves count
    moved = [r for r, p in pos.items() if abs(board.FindFootprintByReference(r).GetPosition().x - p[0]) > 1000 or
             abs(board.FindFootprintByReference(r).GetPosition().y - p[1]) > 1000]
    if moved:
        raise SystemExit("session moved footprints: %s" % moved)
    save(board)
    tr = list(board.GetTracks())
    print("imported %s: %d tracks, %d vias" % (ses, sum(1 for t in tr if t.GetClass() == "PCB_TRACK"),
                                               sum(1 for t in tr if t.GetClass() == "PCB_VIA")))


# ------------------------------------------------------------------------------------- finish
A_MIN = 4.0                       # mm2: smaller unconnected GND areas are left to island removal
GRID = 5.0                        # mm: stitching via grid
VIA_R = VIA_D // 2
VIA_GAP = MM(1.0)                 # island stitch via to any other via, centre to centre
GRID_GAP = MM(1.5)                # grid via to any other via
STITCH_AVOID = ("U1", "J7", "J11")   # no grid vias inside these courtyards
ZONE_CLEARANCE = 0.25

# Hand fixes after the Freerouting pass (session r12, see README "Routing"), board coordinates.
# ("delete", net, layer, (x0, y0, x1, y1)) removes that net's tracks on that layer with both ends in
# the box; (layer, net, width, [points]) adds tracks; ("via", net, x, y) adds a via.
HAND_FIXES = [
    # T4 looped round both EN pads of SW1 and crossed the EN jumper twice (Freerouting optimizer):
    # straight under the switch body between its pad rows instead
    ("delete", "T4", F, (19.0, 37.3, 28.65, 39.5)),
    (F, "T4", 0.2, [(19.06, 39.44), (20.11, 39.44), (20.35, 39.2), (28.03, 39.2), (28.6, 38.63), (28.6, 38.57)]),
    # SD_CS passed 0.22 mm from R3 pad 1 (3V3P, Power class 0.25 mm): 0.15 mm further left
    ("delete", "SD_CS", F, (31.3, 29.7, 35.8, 40.6)),
    (F, "SD_CS", 0.2, [(35.7, 40.52), (33.65, 38.47), (33.65, 32.08), (31.4, 29.83)]),
    # MOSI corner 0.248 mm from U5 pin 3 (5V): corner moved right
    ("delete", "MOSI", F, (70.0, 50.4, 72.5, 50.9)),
    (F, "MOSI", 0.2, [(72.42, 50.52), (70.65, 50.52), (70.37, 50.8), (70.07, 50.8)]),
    # the LIS3DH supply group (U8 pins 1/14, C14, C16, R3) has no open pin in the DSN: tie C14 pad 1
    # to the 3V3P track at C4
    (F, "3V3P", 0.25, [(38.5, 31.5), (40.6, 29.4)]),
]


def apply_hand_fixes(board):
    n_del = n_add = 0
    for it in HAND_FIXES:
        if it[0] == "delete":
            _, net, layer, (x0, y0, x1, y1) = it
            lo, hi = P(x0, y0), P(x1, y1)

            def inside(v):
                return lo.x <= v.x <= hi.x and lo.y <= v.y <= hi.y
            dead = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == net
                    and t.GetLayer() == layer and inside(t.GetStart()) and inside(t.GetEnd())]
            if not dead:
                raise SystemExit("hand fix: nothing to delete for %s in %r" % (net, it[3]))
            for t in dead:
                board.Delete(t)
            n_del += len(dead)
            del dead
        elif it[0] == "via":
            add_via(board, P(it[2], it[3]), it[1])
            n_add += 1
        else:
            layer, net, w, pts = it
            for a, b in zip(pts, pts[1:]):
                add_track(board, layer, net, w, a, b)
                n_add += 1
    if HAND_FIXES:
        print("hand fixes: %d segments deleted, %d items added" % (n_del, n_add))


def add_gnd_zones(board):
    for z in [z for z in board.Zones() if not z.GetIsRuleArea()]:
        board.Delete(z)
    gnd = board.FindNet("GND")
    zones = {}
    for layer, name in ((pcbnew.F_Cu, "GND_F"), (pcbnew.B_Cu, "GND_B")):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNetCode(gnd.GetNetCode())
        z.SetZoneName(name)
        o = z.Outline()
        o.NewOutline()
        for x, y in ((0, 0), (D.BOARD_W, 0), (D.BOARD_W, D.BOARD_H), (0, D.BOARD_H)):
            p = P(x, y)
            o.Append(p.x, p.y)
        z.SetLocalClearance(MM(ZONE_CLEARANCE))
        z.SetMinThickness(MM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(MM(0.3))
        z.SetThermalReliefSpokeWidth(MM(0.5))
        z.SetAssignedPriority(0)
        board.Add(z)
        zones[layer] = z
    return zones


def gnd_zones(board):
    return {z.GetFirstLayer(): z for z in board.Zones() if not z.GetIsRuleArea() and z.GetNetname() == "GND"}


def fill(board, zones, mode):
    for z in zones.values():
        z.SetIslandRemovalMode(mode)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def poly_of(fill_set, i):
    s = pcbnew.SHAPE_POLY_SET()
    s.AddOutline(fill_set.Outline(i))
    for h in range(fill_set.HoleCount(i)):
        s.AddHole(fill_set.Hole(i, h), 0)
    return s


def area_mm2(s):
    return sum(abs(s.Outline(i).Area()) for i in range(s.OutlineCount())) / 1e12


def gnd_items(board, layer):
    """GND pads, tracks and vias on a copper layer, as (item, polygon, bbox)."""
    out = []
    items = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname() == "GND" and p.IsOnLayer(layer)]
    items += [t for t in board.GetTracks() if t.GetNetname() == "GND" and t.IsOnLayer(layer)]
    for it in items:
        s = pcbnew.SHAPE_POLY_SET()
        it.TransformShapeToPolygon(s, layer, 0, MAXERR, pcbnew.ERROR_INSIDE)
        out.append((it, s, s.BBox()))
    return out


def classify(board, zones):
    """{layer: [(poly_index, polygon, area_mm2, touching GND items)]} for every filled GND polygon."""
    res = {}
    for layer, z in zones.items():
        fs = z.GetFilledPolysList(layer)
        items = gnd_items(board, layer)
        polys = []
        for i in range(fs.OutlineCount()):
            p = poly_of(fs, i)
            bb = p.BBox()
            touch = []
            for it, s, ibb in items:
                if not bb.Intersects(ibb):
                    continue
                t = pcbnew.SHAPE_POLY_SET(p)
                t.BooleanIntersection(s)
                if t.OutlineCount():
                    touch.append(it)
            polys.append((i, p, area_mm2(p), touch))
        res[layer] = polys
    return res


def outlines(s):
    return [i for i in range(s.OutlineCount()) if s.Outline(i).PointCount() >= 3 and abs(s.Outline(i).Area()) > 0]


def interior_point(s):
    """A point well inside s (deflate until it vanishes, keep the last non-empty shape), or None."""
    best = s
    for _ in range(40):
        nxt = pcbnew.SHAPE_POLY_SET(best)
        nxt.Deflate(MM(0.25), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
        if not outlines(nxt):
            break
        best = nxt
    idx = outlines(best)
    if not idx:
        return None
    o = best.Outline(max(idx, key=lambda i: abs(best.Outline(i).Area())))
    # SHAPE_LINE_CHAIN.Centre() overflows at board coordinates: try the bbox centre, then the vertices
    for c in [o.BBox().Centre()] + [o.CPoint(j) for j in range(o.PointCount())]:
        if s.Contains(c):
            return pcbnew.VECTOR2I(c.x, c.y)
    return None


def circle(c, r, n=16):
    s = pcbnew.SHAPE_POLY_SET()
    s.NewOutline()
    for k in range(n):
        a = 2 * math.pi * k / n
        s.Append(int(c.x + r * math.cos(a)), int(c.y + r * math.sin(a)))
    return s


def stitch_spot(poly, other_polys, vias):
    """Via centre inside poly and inside one of other_polys (both shrunk by the via radius), away from vias."""
    a = pcbnew.SHAPE_POLY_SET(poly)
    a.Deflate(VIA_R + MM(0.05), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
    if not a.OutlineCount():
        return None
    for v in vias:
        c = circle(v, VIA_GAP)
        if a.BBox().Intersects(c.BBox()):
            a.BooleanSubtract(c)
    best = None
    for o in other_polys:
        if not a.BBox().Intersects(o.BBox()):
            continue
        b = pcbnew.SHAPE_POLY_SET(o)
        b.Deflate(VIA_R + MM(0.05), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
        b.BooleanIntersection(a)
        if outlines(b) and (best is None or area_mm2(b) > area_mm2(best)):
            best = b
    if best is None:
        return None
    cands = [interior_point(best)]
    bb = best.BBox()
    step = MM(0.2)
    pts = [pcbnew.VECTOR2I(x, y) for x in range(bb.GetLeft(), bb.GetRight() + 1, step)
           for y in range(bb.GetTop(), bb.GetBottom() + 1, step)]
    c0 = bb.Centre()
    cands += sorted((q for q in pts if best.Contains(q)), key=lambda q: (q - c0).EuclideanNorm())
    for pos in cands[:400]:
        if pos is None:
            continue
        if not (poly.Contains(pos) and any(o.Contains(pos) for o in other_polys)):
            continue
        if _clear(OBS, [pos], VIA_R, (F, B), "GND"):
            return pos
    return None


def via_positions(board):
    return [t.GetPosition() for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]


def hole_positions(board):
    return [p.GetPosition() for fp in board.GetFootprints() for p in fp.Pads() if p.HasHole()]


def gnd_components(board, zones):
    """Connected components of the GND copper (pour pieces on both layers, pads, tracks, vias).
    Returns (polys {layer: [(poly, area, items)]}, list of components as sets of node keys, main
    component index). Node keys: ("P", layer, i) for pour pieces, ("I", uuid) for items."""
    cls = classify(board, zones)
    parent = {}

    def find(k):
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for layer, polys in cls.items():
        for i, p, a, touch in polys:
            find(("P", layer, i))
            for it in touch:
                union(("P", layer, i), ("I", it.m_Uuid.AsString()))
    # item-to-item: GND tracks to the pads / vias / tracks at their ends
    items = [p for fp in board.GetFootprints() for p in fp.Pads() if p.GetNetname() == "GND"]
    items += [t for t in board.GetTracks() if t.GetNetname() == "GND"]
    for t in [t for t in items if getattr(t, "GetClass", lambda: "")() == "PCB_TRACK"]:
        for o in items:
            if o is t:
                continue
            for e in (t.GetStart(), t.GetEnd()):
                if o.HitTest(e) if o.GetClass() == "PAD" else o.HitTest(e, 0):
                    union(("I", t.m_Uuid.AsString()), ("I", o.m_Uuid.AsString()))
    for it in items:
        find(("I", it.m_Uuid.AsString()))
    comps = {}
    for k in list(parent):
        comps.setdefault(find(k), set()).add(k)
    comps = list(comps.values())
    # main component: the one with the largest pour area
    area = [sum(cls[k[1]][k[2]][2] for k in c if k[0] == "P") for c in comps]
    main = max(range(len(comps)), key=lambda i: area[i])
    return cls, comps, main


OBS = []


def refresh_obstacles(board):
    OBS[:] = _obstacles(board)


def stitch_islands(board, zones):
    """Join every GND component that is not part of the main one (a pour piece without copper of
    its own of A_MIN or more, a pad whose pour piece touches nothing else, a fan-out via landing in
    two cut-off pieces, ...) to the main component with a via, at a spot inside one of its pour
    pieces and inside a main-component piece on the other layer."""
    added, stuck = [], []
    for _ in range(6):
        fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
        refresh_obstacles(board)
        cls, comps, main = gnd_components(board, zones)
        vias = via_positions(board) + hole_positions(board)
        targets = {layer: [cls[layer][k[2]][1] for k in comps[main] if k[0] == "P" and k[1] == layer]
                   for layer in cls}
        n = 0
        stuck = []
        for ci, comp in enumerate(comps):
            if ci == main:
                continue
            pieces = [(k[1], cls[k[1]][k[2]]) for k in comp if k[0] == "P"]
            has_items = any(k[0] == "I" for k in comp)
            if not pieces:
                stuck.append(comp)
                continue
            if not has_items and sum(pc[1][2] for pc in pieces) < A_MIN:
                continue                       # small empty piece: island removal deletes it
            pos = None
            for layer, (i, p, a, touch) in sorted(pieces, key=lambda pc: -pc[1][2]):
                other = pcbnew.B_Cu if layer == pcbnew.F_Cu else pcbnew.F_Cu
                pos = stitch_spot(p, targets[other], vias)
                if pos is not None:
                    add_via(board, pos)
                    vias.append(pos)
                    added.append((bmm(pos), board.GetLayerName(layer), round(sum(pc[1][2] for pc in pieces), 1),
                                  "with copper" if has_items else "empty piece"))
                    n += 1
                    break
            if pos is None and has_items:
                # a pad cut off on both layers (tracks all round its thermal reliefs): a short stub
                # to a via that lands in a main-component piece
                pads = [it for fp in board.GetFootprints() for it in fp.Pads()
                        if ("I", it.m_Uuid.AsString()) in comp]
                mains = [cls[k[1]][k[2]][1] for k in comps[main] if k[0] == "P"]
                done = False
                for pd in pads:
                    v = rescue_pad(board, pd, mains, vias)
                    if v is not None:
                        vias.append(v)
                        added.append((bmm(v), "pad %s.%s" % (pd.GetParentFootprint().GetReference(), pd.GetNumber()),
                                      0.0, "stub + via"))
                        n += 1
                        done = True
                        break
                if not done:
                    stuck.append(comp)
        if not n:
            break
    for comp in stuck:
        names = []
        for k in comp:
            if k[0] == "I":
                for fp in board.GetFootprints():
                    for p in fp.Pads():
                        if p.m_Uuid.AsString() == k[1]:
                            names.append("%s.%s" % (fp.GetReference(), p.GetNumber()))
        print("  GND component not joined to the main one: %d pieces, pads %s" %
              (sum(1 for k in comp if k[0] == "P"), names or "none"))
    return added


def rescue_pad(board, pd, mains, vias):
    """Stub (0.3 mm) from pad pd to a new GND via inside one of the main-component pour pieces,
    clear of other copper by the Power clearance. Returns the via position or None."""
    obs = _obstacles(board)
    c = pd.GetPosition()
    r0 = max(pd.GetBoundingBox().GetWidth(), pd.GetBoundingBox().GetHeight()) / 2
    holes = [(p.GetPosition(), max(p.GetDrillSizeX(), p.GetDrillSizeY()) // 2)
             for fp in board.GetFootprints() for p in fp.Pads() if p.HasHole() and p is not pd]
    for extra in (0.6, 0.9, 1.2, 1.6, 2.0):
        for k in range(24):
            a = 2 * math.pi * k / 24
            d = r0 + MM(extra)
            p = pcbnew.VECTOR2I(int(c.x + d * math.cos(a)), int(c.y + d * math.sin(a)))
            if not any(m.Contains(p) for m in mains):
                continue
            if any((p - q).EuclideanNorm() < MM(0.85) for q in vias):
                continue
            if any((p - hc).EuclideanNorm() < hr + VIA_R + MM(0.4) for hc, hr in holes):
                continue
            if not _clear(obs, [p], VIA_R, (F, B), "GND"):
                continue
            steps = max(2, int((p - c).EuclideanNorm() / MM(0.1)))
            stub = [pcbnew.VECTOR2I(int(c.x + (p.x - c.x) * j / steps), int(c.y + (p.y - c.y) * j / steps))
                    for j in range(steps + 1)]
            for layer in (F, B):
                if _clear(obs, stub, MM(0.15), (layer,), "GND"):
                    t = pcbnew.PCB_TRACK(board)
                    t.SetStart(c)
                    t.SetEnd(p)
                    t.SetWidth(MM(0.3))
                    t.SetLayer(layer)
                    t.SetNet(board.FindNet("GND"))
                    board.Add(t)
                    add_via(board, p)
                    return p
    return None


def stitch_grid(board, zones):
    """Stitching vias on a GRID mm lattice wherever both GND pours are solid around the via."""
    fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    fills = {}
    for layer, z in zones.items():
        s = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(layer))
        s.Deflate(VIA_R + MM(0.1), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
        fills[layer] = s
    avoid = []
    for ref in STITCH_AVOID:
        c = board.FindFootprintByReference(ref).GetCourtyard(pcbnew.F_CrtYd)
        avoid.append(c)
    taken = via_positions(board) + hole_positions(board)
    cls, comps, main = gnd_components(board, zones)
    mains = [cls[k[1]][k[2]][1] for k in comps[main] if k[0] == "P"]
    refresh_obstacles(board)
    added = []
    nx, ny = int(D.BOARD_W // GRID), int(D.BOARD_H // GRID)
    for i in range(1, nx + 1):
        for j in range(1, ny + 1):
            x, y = (i - 0.5) * GRID + (D.BOARD_W - nx * GRID) / 2, (j - 0.5) * GRID + (D.BOARD_H - ny * GRID) / 2
            p = P(x, y)
            if not all(f.Contains(p) for f in fills.values()):
                continue
            if any(c.Contains(p) for c in avoid):
                continue
            if any((p.x - q.x) ** 2 + (p.y - q.y) ** 2 < GRID_GAP ** 2 for q in taken):
                continue
            if not any(m.Contains(p) for m in mains):
                continue                       # would only join cut-off pieces to each other
            if not _clear(OBS, [p], VIA_R, (F, B), "GND"):
                continue
            add_via(board, p)
            taken.append(p)
            added.append((round(x, 2), round(y, 2)))
    return added


def report_islands(board, zones):
    fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    cls = classify(board, zones)
    for layer, polys in cls.items():
        isl = sorted((round(a, 1) for i, p, a, touch in polys if not touch), reverse=True)
        single = [round(a, 1) for i, p, a, touch in polys if len(touch) == 1 and touch[0].GetClass() == "PAD"]
        print("  %s: %d filled areas, %d unconnected (removed by island removal: total %.1f mm2, largest %s mm2), "
              "%d single-pad areas %s" % (board.GetLayerName(layer), len(polys), len(isl), sum(isl), isl[:5],
                                          len(single), single))


def cleanup(board):
    """Freerouting artefacts: segments shorter than 0.01 mm (its neck-down stubs at pad centres, some
    0.12 mm wide, below the 0.127 mm minimum) are removed; the track end stays inside the pad."""
    tiny = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetLength() < MM(0.01)]
    n = len(tiny)
    for t in tiny:
        board.Delete(t)       # Delete, not Remove: see main()
    del tiny, t
    narrow = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetWidth() < MM(0.127)]
    for t in narrow:
        print("  narrow track left: %s %.3f mm at %s" % (t.GetNetname(), pcbnew.ToMM(t.GetWidth()), bmm(t.GetStart())))
    print("cleanup: removed %d segments shorter than 0.01 mm" % n)


def cmd_finish():
    board = load()
    # Gerbers/drill/CPL origin (gen_jlcpcb.py). Before any Remove(): afterwards this KiCad 10.0.7 SWIG
    # build hands back GetDesignSettings() as an untyped SwigPyObject.
    board.GetDesignSettings().SetAuxOrigin(P(0, D.BOARD_H))
    locked = [t for t in board.GetTracks() if t.IsLocked()]
    for t in locked:
        t.SetLocked(False)
    print("unlocked %d tracks/vias" % len(locked))
    cleanup(board)
    apply_hand_fixes(board)
    zones = add_gnd_zones(board)
    print("GND before stitching:")
    report_islands(board, zones)
    isl = stitch_islands(board, zones)
    for a in isl:
        print("  stitch via at (%.2f, %.2f): %s, %s, %.1f mm2" % (a[0][0], a[0][1], a[1], a[3], a[2]))
    grid = stitch_grid(board, zones)
    print("GND after %d island/thermal vias and %d grid vias:" % (len(isl), len(grid)))
    report_islands(board, zones)
    fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    place_refs(board)
    save(board)
    prune(board, zones)
    report(board)


def drc_json(board_path):
    out = os.path.join(os.path.dirname(os.path.abspath(board_path)), ".route_prep_drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--format", "json", "-o", out, board_path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = json.load(open(out))
    os.remove(out)
    return d


def prune(board, zones):
    """Delete stitching vias that KiCad's DRC finds unconnected or dangling (a via joining two pour
    islands that touch nothing else), refill, save; repeat until none is left."""
    total = 0
    for _ in range(4):
        d = drc_json(BOARD)
        bad = {it["uuid"] for v in d.get("unconnected_items", []) + d.get("violations", [])
               if v["type"] in ("unconnected_items", "via_dangling") for it in v["items"]}
        ends = [(t.GetStart(), t.GetEnd()) for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
        dead = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"
                and t.m_Uuid.AsString() in bad and not any(t.HitTest(a, 0) or t.HitTest(b, 0) for a, b in ends)]
        if not dead:
            break
        for t in dead:
            board.Delete(t)
        total += len(dead)
        del dead, t
        fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        save(board)
    print("prune: removed %d unconnected stitching vias" % total)


# ------------------------------------------------------------------------------------- report
DECAP = [  # (IC, supply pad, cap, cap pad on the supply net)
    ("U1", "2", "C10", "1"), ("U1", "2", "C9", "1"),
    ("U2", "9", "C3", "1"), ("U3", "9", "C4", "1"),
    ("U4", "5", "C5", "1"),
    ("U5", "3", "C6", "1"), ("U5", "2", "C2", "1"), ("U5", "2", "C19", "1"),
    ("U6", "3", "C7", "1"), ("U6", "2", "C8", "1"),
    ("U7", "16", "C12", "1"), ("U7", "4", "C13", "1"),
    ("U8", "14", "C14", "1"), ("U8", "1", "C16", "1"), ("U8", "14", "C15", "1"),
    ("J11", "4", "C17", "1"), ("J11", "4", "C18", "1"),
]


def pad_poly(pad):
    s = pcbnew.SHAPE_POLY_SET()
    pad.TransformShapeToPolygon(s, pcbnew.F_Cu, 0, MAXERR, pcbnew.ERROR_INSIDE)
    return s


def poly_gap(a, b):
    """Smallest distance (mm) between two polygon sets (vertex-to-edge, both ways)."""
    best = None
    for s, t in ((a, b), (b, a)):
        for i in range(s.OutlineCount()):
            o = s.Outline(i)
            for j in range(o.PointCount()):
                pt = o.CPoint(j)
                d = t.SquaredDistance(pcbnew.VECTOR2I(pt.x, pt.y))
                best = d if best is None or d < best else best
    return math.sqrt(best) / 1e6


def net_length(board, net):
    return sum(pcbnew.ToMM(t.GetLength()) for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == net)


def report(board=None):
    board = board or load()
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]
    length = {}
    for t in tracks:
        k = board.GetLayerName(t.GetLayer())
        length[k] = length.get(k, 0) + pcbnew.ToMM(t.GetLength())
    gnd_stitch = [v for v in vias if v.GetNetname() == "GND"]
    print("vias: %d (%d GND), track segments: %d, length: %s mm, total %.0f mm" % (
        len(vias), len(gnd_stitch), len(tracks), {k: round(v) for k, v in sorted(length.items())}, sum(length.values())))
    narrow = {}
    for t in tracks:
        w = POWER_W.get(t.GetNetname())
        if w and pcbnew.ToMM(t.GetWidth()) < w - 1e-6:
            narrow.setdefault(t.GetNetname(), []).append(round(pcbnew.ToMM(t.GetWidth()), 2))
    print("Power-class tracks narrower than 0.6 mm: %s" % ({k: "%d x %s mm" % (len(v), sorted(set(v)))
                                                             for k, v in narrow.items()} or "none"))
    print("decoupling (cap pad to IC supply pad: edge gap / centre distance):")
    for ic, ipad, cap, cpad in DECAP:
        a = [p for p in board.FindFootprintByReference(ic).Pads() if p.GetNumber() == ipad]
        b = [p for p in board.FindFootprintByReference(cap).Pads() if p.GetNumber() == cpad][0]
        best = min(a, key=lambda p: (p.GetPosition() - b.GetPosition()).EuclideanNorm())
        cc = (best.GetPosition() - b.GetPosition()).EuclideanNorm() / 1e6
        print("  %-3s pad %-2s (%s) - %-3s: %.2f / %.2f mm" % (ic, ipad, best.GetNetname(), cap, poly_gap(pad_poly(best), pad_poly(b)), cc))
    dp, dm = net_length(board, "USB_DP"), net_length(board, "USB_DM")
    vdp = sum(1 for v in vias if v.GetNetname() == "USB_DP")
    vdm = sum(1 for v in vias if v.GetNetname() == "USB_DM")
    print("USB pair (J7 - U9 - U7, all branches): USB_DP %.1f mm (%d vias), USB_DM %.1f mm (%d vias), difference %.1f mm"
          % (dp, vdp, dm, vdm, abs(dp - dm)))


def main():
    cmds = {"prep": cmd_prep, "finish": cmd_finish, "report": report}
    if len(sys.argv) >= 2 and sys.argv[1] in cmds:
        cmds[sys.argv[1]]()
    elif len(sys.argv) == 3 and sys.argv[1] == "export":
        cmd_export(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "import":
        cmd_import(sys.argv[2])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    # KiCad 10.0.7 SWIG (Python 3.14): once the proxy of an item taken off the board with
    # BOARD.Remove() is garbage-collected, later calls return untyped SwigPyObjects and the final
    # collection segfaults. Items are taken off with BOARD.Delete(), and the script leaves with
    # os._exit() so no final collection runs (also on an exception).
    try:
        main()
    except SystemExit as e:
        if e.code not in (None, 0):
            print(e.code if isinstance(e.code, str) else "exit %s" % e.code, file=sys.stderr)
        sys.stdout.flush()
        os._exit(0 if e.code in (None, 0) else 1)
    except BaseException:
        import traceback
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
    sys.stdout.flush()
    os._exit(0)
