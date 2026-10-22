#!/usr/bin/env python3
"""Autoroute defuse32-carrier.kicad_pcb with Freerouting: KiCad 10.0.7 DSN/SES round trip.

Used once, for the rev 1b routing (2026-10-22); kept as a record and for a full re-route. It
starts from an unrouted board: the routed board is now edited by hand in KiCad. Run from
hardware/defuse32/kicad/ with KiCad's Python (/usr/bin/python3, not conda):

  /usr/bin/python3 gen/route_prep.py export /tmp/d32/prep.dsn
  java -jar ~/tools/freerouting-2.4.1/freerouting-2.4.1.jar -de /tmp/d32/prep.dsn -do /tmp/d32/prep.ses \
       -mp 100 -mt 1 --gui.enabled=false --router.optimizer.improvement_threshold=0 \
       --router.optimizer.max_passes=20 --usage_and_diagnostic_data.disable_analytics=true \
       --profile.allow_telemetry=false
  /usr/bin/python3 gen/route_prep.py import /tmp/d32/prep.ses
  /usr/bin/python3 gen/route_prep.py finish
  git checkout -- defuse32-carrier.kicad_pro

then the decoupling fix asked for in review (incremental: only the affected copper is re-routed):

  /usr/bin/python3 gen/route_prep.py decap
  /usr/bin/python3 gen/route_prep.py export /tmp/d32/dc.dsn
  java -jar ... -de /tmp/d32/dc.dsn -do /tmp/d32/dc.ses   (same options as above)
  /usr/bin/python3 gen/route_prep.py import /tmp/d32/dc.ses
  /usr/bin/python3 gen/route_prep.py finish
  git checkout -- defuse32-carrier.kicad_pro

(Freerouting 2.4.1 routed it in 7 passes; without the two optimizer options it skips the
optimizer, which here cut the vias from 72 to 29. `-mt 1`: the multi-threaded optimizer is
documented to break clearances. The settings options apply to this run only; the user's
~/.config/freerouting/freerouting.json is not written.)

pcbnew.SaveBoard() rewrites defuse32-carrier.kicad_pro with every default filled in and a
top-level sheet UUID of all zeros; the rules are unchanged, so the git version is restored.
D32_BOARD=/path/to/copy.kicad_pcb runs any step on a copy instead of the project board.

export  Writes the board as a Specctra DSN and fixes what KiCad 10.0.7's exporter gets wrong here
        (same quirks as AirQuality's tools/freerouting_prep.py):
          1. the GND_F / GND_B pours are exported as `plane GND` on the two signal layers, so
             Freerouting would treat each whole layer as a GND conduction area. Both planes are
             dropped: GND is routed as an ordinary Power-class net (0.8 mm) and the pours are
             refilled after import. (Freerouting's `router.ignore_net_classes` setting cannot be
             set from the command line, so GND cannot be left to the pours alone.)
          2. every rule area becomes a copper keepout. The only rule area on this board is
             ANTENNA_KEEPOUT, which must block tracks and vias anyway, so it is kept (the script
             checks that exactly that keepout is present on F.Cu and B.Cu).
import  Reads the Freerouting session into the board (unlocked tracks and vias are replaced, locked
        ones stay; the script stops if a footprint moved), refills the zones and saves.
decap   Moves the decoupling caps (DECAP) next to their IC supply pins and adds short 0.8 mm
        tracks to the pins (DECAP_TRACKS); removes the GND stitching vias and the hand fix
        (`finish` redoes them), every foreign track or via the moved pads and new tracks now hit
        (0.3 mm clearance) and every track left dangling; then locks all remaining copper, so
        the next Freerouting pass (exported as `type fix`) only adds the missing connections.
finish  Post-routing clean-up, then refill (island removal "always") and save:
          - unlocks all tracks and vias;
          - lists Power-class tracks (5V, 3V3P, DK_5V, GND) narrower than 0.8 mm (none here);
          - applies HAND_FIXES (below);
          - stitches the GND pours: a 0.6/0.3 via goes into every pour island of A_MIN or more
            (filled area touching no GND pad, track or via, which island removal would delete) and
            into every pour piece connected to one pad only (KiCad DRC reports its thermal as
            starved, "spokes connected to isolated island"), at a spot inside both that piece and
            a connected pour on the other layer, 1 mm or more from any other GND via;
          - prints the GND island counts before and after, the via count and track length per layer.
"""
import math
import os
import re
import sys

import pcbnew

HERE = os.path.dirname(os.path.abspath(__file__))
KDIR = os.path.normpath(os.path.join(HERE, ".."))
BOARD = os.environ.get("D32_BOARD") or os.path.join(KDIR, "defuse32-carrier.kicad_pcb")
POWER = {"5V", "3V3P", "DK_5V", "GND"}
POWER_W = pcbnew.FromMM(0.8)
VIA_D, VIA_DRILL = pcbnew.FromMM(0.6), pcbnew.FromMM(0.3)
MM = pcbnew.FromMM
MAXERR = MM(0.005)
# ANTENNA_KEEPOUT as exported (DSN um, y negated): board x 104-129, y 58-92 + page offset (50, 40)
KEEPOUT_DSN = "154000 -98000  179000 -98000  179000 -132000  154000 -132000"


def sexp_blocks(text, head):
    """Yield (start, end) of every '(head ...)' block in text."""
    i = 0
    while True:
        k = text.find("(" + head, i)
        if k < 0:
            return
        d, j = 0, k
        while True:
            c = text[j]
            if c == "(":
                d += 1
            elif c == ")":
                d -= 1
                if d == 0:
                    break
            j += 1
        yield k, j + 1
        i = j + 1


def drop(text, head, pred):
    out, last, n = [], 0, 0
    for k, e in sexp_blocks(text, head):
        if pred(text[k:e]):
            out.append(text[last:k])
            last = e
            n += 1
    out.append(text[last:])
    return "".join(out), n


def load():
    return pcbnew.LoadBoard(BOARD)


def fill_and_save(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(BOARD, board)


# ------------------------------------------------------------------------------------- export
def cmd_export(dst):
    board = load()
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    raw = dst + ".raw"
    if not pcbnew.ExportSpecctraDSN(board, raw):
        raise SystemExit("ExportSpecctraDSN failed")
    t = open(raw).read()
    t, n_f = drop(t, "plane GND (polygon F.Cu", lambda b: True)
    t, n_b = drop(t, "plane GND (polygon B.Cu", lambda b: True)
    if (n_f, n_b) != (1, 1):
        raise SystemExit("expected one GND plane per layer, got %d/%d" % (n_f, n_b))
    if "(plane" in t:
        raise SystemExit("unexpected plane left in the DSN")
    # board-level keepouts sit in (structure ...); footprint keepouts (mounting holes) are circles
    structure = t[t.index("(structure"):t.index("(placement")]
    kos = re.findall(r"\(keepout \"[^\"]*\" \(polygon (\S+) 0\s+([^)]*)\)", structure)
    want = " ".join(KEEPOUT_DSN.split())
    layers = sorted(l for l, pts in kos if want in " ".join(pts.split()))
    if layers != ["B.Cu", "F.Cu"] or len(kos) != 2:
        raise SystemExit("antenna keepout not found as expected: %r" % (kos,))
    open(dst, "w").write(t)
    os.remove(raw)
    print("wrote %s: dropped GND planes on F.Cu/B.Cu, kept ANTENNA_KEEPOUT on %s" % (dst, "/".join(layers)))


# ------------------------------------------------------------------------------------- import
def cmd_import(ses):
    board = load()
    pos = {fp.GetReference(): (fp.GetPosition().x, fp.GetPosition().y) for fp in board.GetFootprints()}
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise SystemExit("ImportSpecctraSES failed")
    moved = [r for r, p in pos.items() if board.FindFootprintByReference(r) and
             (board.FindFootprintByReference(r).GetPosition().x, board.FindFootprintByReference(r).GetPosition().y) != p]
    if moved:
        raise SystemExit("session moved footprints: %s" % moved)
    fill_and_save(board)
    tr = [t for t in board.GetTracks()]
    print("imported %s: %d tracks, %d vias" % (ses, sum(1 for t in tr if t.GetClass() == "PCB_TRACK"),
                                               sum(1 for t in tr if t.GetClass() == "PCB_VIA")))


# ------------------------------------------------------------------------------------- decap
# Decoupling fix (orchestrator review, 2026-10-22), page coordinates in mm. C3/C4 go next to the
# MCP23017 VDD/VSS pins 9/10 (left column), pad 1 (3V3P) level with pin 9 and pad 2 (GND) 5 mm
# below; C4 stays 0.55 mm clear of the B.Cu bus left of U3. C5 keeps pad 1 (5V) 4.4 mm from U4
# VCC pin 14 and turns so pad 2 (GND) is 4.4 mm from U4 pin 12 (an unused A input tied to GND,
# joined to GND pin 7 by tracks): VCC (14) and GND (7) are diagonal on the DIP-14, 17 mm apart.
DECAP = {
    # ref: (pad 1 position, orientation, reference text position)
    "C3": ((122.0, 100.32), 270, (119.6, 102.82)),
    "C4": ((84.6, 100.32), 270, (82.2, 102.82)),
    "C5": ((78.0, 62.0), 270, (80.4, 64.5)),
}
# short 0.8 mm tracks from the caps to the supply pins: (layer, net, points)
DECAP_TRACKS = [
    (pcbnew.B_Cu, "3V3P", [(122.0, 100.32), (126.0, 100.32)]),                     # C3.1 - U2.9
    (pcbnew.B_Cu, "GND", [(122.0, 105.32), (124.46, 102.86), (126.0, 102.86)]),    # C3.2 - U2.10
    (pcbnew.F_Cu, "3V3P", [(84.6, 100.32), (90.0, 100.32)]),                       # C4.1 - U3.9
    (pcbnew.F_Cu, "GND", [(84.6, 105.32), (87.06, 102.86), (90.0, 102.86)]),       # C4.2 - U3.10
    (pcbnew.F_Cu, "5V", [(78.0, 62.0), (73.62, 62.0)]),                            # C5.1 - U4.14
    (pcbnew.F_Cu, "GND", [(78.0, 67.0), (73.62, 67.0)]),                           # C5.2 - U4.12
]
CLEAR = MM(0.3)                   # Power-class clearance: every moved item is on a Power net


def P(x, y):
    return pcbnew.VECTOR2I(MM(x), MM(y))


def item_poly(it, layer, clearance=0):
    s = pcbnew.SHAPE_POLY_SET()
    it.TransformShapeToPolygon(s, layer, clearance, MAXERR, pcbnew.ERROR_OUTSIDE)
    return s


def collides(a, b):
    if not a.BBox().Intersects(b.BBox()):
        return False
    t = pcbnew.SHAPE_POLY_SET(a)
    t.BooleanIntersection(b)
    return t.OutlineCount() > 0


def connected_end(board, item, p, pads, tracks):
    """True if point p of track/via `item` touches another copper item of the same net."""
    net = item.GetNetCode()
    me = item.m_Uuid.AsString()       # SWIG hands out new proxies: compare UUIDs, not identity
    layers = [pcbnew.F_Cu, pcbnew.B_Cu] if item.GetClass() == "PCB_VIA" else [item.GetLayer()]
    for pad in pads.get(net, []):
        if any(pad.IsOnLayer(l) for l in layers) and pad.HitTest(p):
            return True
    for t in tracks.get(net, []):
        if t.m_Uuid.AsString() == me:
            continue
        if t.GetClass() == "PCB_VIA" or t.GetLayer() in layers:
            if t.HitTest(p, 0):
                return True
    return False


def remove_dangling(board):
    """Remove tracks with a free end and vias with fewer than two connections, until none is left."""
    n = 0
    while True:
        pads, tracks = {}, {}
        for fp in board.GetFootprints():
            for pad in fp.Pads():
                pads.setdefault(pad.GetNetCode(), []).append(pad)
        for t in board.GetTracks():
            tracks.setdefault(t.GetNetCode(), []).append(t)
        dead = []
        for t in board.GetTracks():
            if t.GetClass() == "PCB_VIA":
                links = [o for o in tracks.get(t.GetNetCode(), []) if o.GetClass() == "PCB_TRACK"
                         and (t.HitTest(o.GetStart(), 0) or t.HitTest(o.GetEnd(), 0))]
                links += [pd for pd in pads.get(t.GetNetCode(), []) if pd.HitTest(t.GetPosition())]
                if len(links) < 2:
                    dead.append(t)
            elif not (connected_end(board, t, t.GetStart(), pads, tracks) and
                      connected_end(board, t, t.GetEnd(), pads, tracks)):
                dead.append(t)
        if not dead:
            return n
        for t in dead:
            board.Remove(t)
        n += len(dead)


def cmd_decap():
    board = load()
    gnd = board.FindNet("GND")
    # 1. drop the GND stitching vias (no track ends on them) and the hand fix; `finish` redoes both
    tracks = list(board.GetTracks())
    ends = [(t.GetStart(), t.GetEnd()) for t in tracks if t.GetClass() == "PCB_TRACK"]
    stitch = [t for t in tracks if t.GetClass() == "PCB_VIA" and t.GetNetCode() == gnd.GetNetCode()
              and not any(t.HitTest(s, 0) or t.HitTest(e, 0) for s, e in ends)]
    fix = []
    for ref, padnum, pos, items in HAND_FIXES:
        for it in items:
            pts = [it[1]] if it[0] == "via" else [it[3], it[4]]
            for t in tracks:
                if t.GetNetCode() != gnd.GetNetCode():
                    continue
                if it[0] == "via" and t.GetClass() == "PCB_VIA" and t.GetPosition() == P(*pts[0]):
                    fix.append(t)
                if it[0] == "track" and t.GetClass() == "PCB_TRACK" and t.GetStart() == P(*pts[0]) and t.GetEnd() == P(*pts[1]):
                    fix.append(t)
    for t in stitch + fix:
        board.Remove(t)
    # 2. move the caps
    for ref, (pos, rot, refpos) in DECAP.items():
        fp = board.FindFootprintByReference(ref)
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(P(*pos))
        fp.Reference().SetPosition(P(*refpos))
        fp.Reference().SetTextAngleDegrees(90)
    # 3. new cap-to-pin tracks
    new = []
    for layer, net, pts in DECAP_TRACKS:
        for a, b in zip(pts, pts[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(P(*a))
            t.SetEnd(P(*b))
            t.SetWidth(POWER_W)
            t.SetLayer(layer)
            t.SetNet(board.FindNet(net))
            board.Add(t)
            new.append(t)
    # 4. rip up the foreign tracks/vias the moved pads and the new tracks now hit (0.3 mm clearance)
    obst = []
    for ref in DECAP:
        for pad in board.FindFootprintByReference(ref).Pads():
            for l in (pcbnew.F_Cu, pcbnew.B_Cu):
                obst.append((pad.GetNetCode(), l, item_poly(pad, l, CLEAR)))
    for t in new:
        obst.append((t.GetNetCode(), t.GetLayer(), item_poly(t, t.GetLayer(), CLEAR)))
    new_ids = {t.m_Uuid.AsString() for t in new}
    hit = {}
    for t in board.GetTracks():
        if t.m_Uuid.AsString() in new_ids:
            continue
        for net, l, s in obst:
            if t.GetNetCode() != net and t.IsOnLayer(l) and collides(s, item_poly(t, l)):
                hit[t.m_Uuid.AsString()] = t
                break
    ripped = sorted({t.GetNetname() for t in hit.values()})
    for t in hit.values():
        board.Remove(t)
    # 5. remove what is left dangling (old cap connections, broken branches)
    n_dang = remove_dangling(board)
    # 6. lock everything that stays, so the incremental Freerouting pass only adds tracks
    for t in board.GetTracks():
        t.SetLocked(True)
    fill_and_save(board)
    print("decap: removed %d stitching vias + %d hand-fix items; moved %s; %d new tracks; ripped %d "
          "colliding items (nets %s); removed %d dangling items; %d tracks/vias locked"
          % (len(stitch), len(fix), ", ".join(DECAP), len(new), len(hit), " ".join(ripped), n_dang,
             len(list(board.GetTracks()))))


# ------------------------------------------------------------------------------------- finish
A_MIN = 50.0                      # mm2: smaller GND islands are left to island removal
VIA_R = VIA_D // 2
VIA_GAP = MM(1.0)                 # stitch via to any other GND via, centre to centre


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
    """Indices of the non-degenerate outlines of s."""
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


def add_via(board, pos):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(pos)
    v.SetWidth(VIA_D)
    v.SetDrill(VIA_DRILL)
    v.SetLayerPair(pcbnew.F_Cu, pcbnew.B_Cu)
    v.SetNet(board.FindNet("GND"))
    board.Add(v)
    return v


def stitch_spot(poly, other_polys, vias):
    """Via centre inside poly and inside one of other_polys (both shrunk by the via radius), away from vias."""
    a = pcbnew.SHAPE_POLY_SET(poly)
    a.Deflate(VIA_R + MM(0.05), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
    if not a.OutlineCount():
        return None
    # keep away from existing GND vias (hole to hole)
    for v in vias:
        c = pcbnew.SHAPE_POLY_SET()
        c.NewOutline()
        for k in range(16):
            ang = 2 * math.pi * k / 16
            c.Append(int(v.x + VIA_GAP * math.cos(ang)), int(v.y + VIA_GAP * math.sin(ang)))
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
    pos = interior_point(best) if best is not None else None
    if pos is not None and not (poly.Contains(pos) and any(o.Contains(pos) for o in other_polys)):
        raise SystemExit("stitch_spot: bad via position %r" % ((pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y)),))
    return pos


def stitch(board, zones):
    """Stitch GND islands (>= A_MIN) and single-pad pour pieces to the other layer's connected pour."""
    added = []
    for _ in range(4):
        fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
        cls = classify(board, zones)
        vias = [t.GetPosition() for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() == "GND"]
        n = 0
        for layer, polys in cls.items():
            other = pcbnew.B_Cu if layer == pcbnew.F_Cu else pcbnew.F_Cu
            targets = [p for i, p, a, touch in cls[other] if touch]
            for i, p, a, touch in polys:
                single_pad = len(touch) == 1 and touch[0].GetClass() == "PAD"
                if (not touch and a >= A_MIN) or single_pad:
                    pos = stitch_spot(p, targets, vias)
                    if pos is not None:
                        add_via(board, pos)
                        vias.append(pos)
                        added.append((pcbnew.ToMM(pos.x), pcbnew.ToMM(pos.y), board.GetLayerName(layer),
                                      round(a, 1), "single-pad" if single_pad else "island"))
                        n += 1
        if not n:
            break
    return added


def report_islands(board, zones):
    fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    cls = classify(board, zones)
    for layer, polys in cls.items():
        isl = sorted((round(a, 1) for i, p, a, touch in polys if not touch), reverse=True)
        single = [round(a, 1) for i, p, a, touch in polys if len(touch) == 1 and touch[0].GetClass() == "PAD"]
        print("  %s: %d filled areas, %d islands removed by island removal (total %.0f mm2, largest %s mm2), "
              "%d single-pad areas %s" % (board.GetLayerName(layer), len(polys), len(isl), sum(isl), isl[:5],
                                          len(single), single))


# Fixes for the 2026-10-22 session, in page coordinates (mm). U1 pad 20 of the unpopulated clone
# row (GND, at 180, 105.14) gets a single B.Cu thermal spoke (DRC starved_thermal, min 2): the
# B.Cu pour strip between it and ANTENNA_KEEPOUT is an island. A 0.8 mm B.Cu stub from the pad
# into the strip plus a via to the F.Cu pour connects the strip and counts as the second spoke.
HAND_FIXES = [
    ("U1", "20", (180.0, 105.14), [("track", pcbnew.B_Cu, 0.8, (180.0, 105.14), (180.0, 110.0)),
                                   ("via", (180.0, 110.0))]),
]


def apply_hand_fixes(board):
    gnd = board.FindNet("GND")
    for ref, padnum, (px, py), items in HAND_FIXES:
        fp = board.FindFootprintByReference(ref)
        pads = [p for p in fp.Pads() if p.GetNumber() == padnum and p.GetNetname() == "GND"
                and abs(pcbnew.ToMM(p.GetPosition().x) - px) < 0.01 and abs(pcbnew.ToMM(p.GetPosition().y) - py) < 0.01]
        if not pads:
            print("hand fix %s-%s skipped: pad not found at (%.2f, %.2f)" % (ref, padnum, px, py))
            continue
        for it in items:
            if it[0] == "via":
                pos = pcbnew.VECTOR2I(MM(it[1][0]), MM(it[1][1]))
                if any(t.GetClass() == "PCB_VIA" and t.GetPosition() == pos for t in board.GetTracks()):
                    continue
                add_via(board, pos)
            else:
                _, layer, w, a, b = it
                s, e = pcbnew.VECTOR2I(MM(a[0]), MM(a[1])), pcbnew.VECTOR2I(MM(b[0]), MM(b[1]))
                if any(t.GetClass() == "PCB_TRACK" and t.GetStart() == s and t.GetEnd() == e for t in board.GetTracks()):
                    continue
                t = pcbnew.PCB_TRACK(board)
                t.SetStart(s)
                t.SetEnd(e)
                t.SetWidth(MM(w))
                t.SetLayer(layer)
                t.SetNet(gnd)
                board.Add(t)
        print("hand fix %s-%s: %s" % (ref, padnum, items))


def cmd_finish():
    board = load()
    zones = gnd_zones(board)
    narrow = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() in POWER
              and t.GetWidth() < POWER_W]
    for t in narrow:
        print("narrow Power track: %s %.2f mm at (%.2f, %.2f)" % (t.GetNetname(), pcbnew.ToMM(t.GetWidth()),
                                                                   pcbnew.ToMM(t.GetStart().x), pcbnew.ToMM(t.GetStart().y)))
    print("Power tracks narrower than 0.8 mm:", len(narrow))
    locked = [t for t in board.GetTracks() if t.IsLocked()]
    for t in locked:                  # `decap` locks the kept routing for the incremental pass
        t.SetLocked(False)
    if locked:
        print("unlocked %d tracks/vias" % len(locked))
    apply_hand_fixes(board)
    print("GND before stitching:")
    report_islands(board, zones)
    added = stitch(board, zones)
    for a in added:
        print("  stitch via at (%.2f, %.2f): %s %s %.1f mm2" % (a[0], a[1], a[2], a[4], a[3]))
    print("GND after %d stitch vias:" % len(added))
    report_islands(board, zones)
    fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    pcbnew.SaveBoard(BOARD, board)
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    length = {}
    for t in tracks:
        length[board.GetLayerName(t.GetLayer())] = length.get(board.GetLayerName(t.GetLayer()), 0) + pcbnew.ToMM(t.GetLength())
    print("vias: %d, track segments: %d, length: %s mm, total %.0f mm" % (
        sum(1 for t in board.GetTracks() if t.GetClass() == "PCB_VIA"), len(tracks),
        {k: round(v) for k, v in sorted(length.items())}, sum(length.values())))


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("export", "import", "decap", "finish"):
        raise SystemExit(__doc__)
    if sys.argv[1] == "export":
        cmd_export(sys.argv[2])
    elif sys.argv[1] == "import":
        cmd_import(sys.argv[2])
    elif sys.argv[1] == "decap":
        cmd_decap()
    else:
        cmd_finish()
