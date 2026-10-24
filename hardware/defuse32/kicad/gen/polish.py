#!/usr/bin/env python3
"""The "professional finish" of the routed carrier (defuse32-carrier.kicad_pcb), in place.

Written for rev 2.1 (2 layers), extended for rev 3 (4 layers, stack-up option B: In1.Cu and In2.Cu
solid GND planes, signals + power + GND pours on F.Cu and B.Cu). Works on the CURRENT routed board:
no new routing run, footprints and schematic untouched, route_prep's HAND_FIXES not re-applied,
pre-routes (route_prep PREROUTE / PREVIAS) never moved and every connection kept. The rules come from the pcb-layout-pro skill; its audit (gen/pcb_audit.py,
a copy of the skill's script) measures the result. Run from hardware/defuse32/kicad/ with KiCad's
Python (/usr/bin/python3, not conda):

  /usr/bin/python3 gen/polish.py all           # every step below, KiCad DRC, report (~10 min)
  /usr/bin/python3 gen/polish.py all nojogs    # the same without the jog step (~1.5 min)
  /usr/bin/python3 gen/polish.py jogs          # the jogs left on the board and what keeps each
  /usr/bin/python3 gen/polish.py report        # route_prep's report (vias, lengths, decoupling, USB)

D32_BOARD=/path/to/copy.kicad_pcb runs on a copy (put the .kicad_pro/.kicad_dru next to it for the
DRC checks) and leaves the project file alone; otherwise saving rewrites the .kicad_pro with
gen_pcb.write_project(). Items are taken off with BOARD.Delete() and the script leaves with
os._exit() (KiCad 10.0.7 SWIG, see route_prep.main()).

Model. Tracks are grouped into chains (per net and layer, between pads, vias, branch points and
T-junctions). An obstacle index holds all copper with its net-class clearance, holes (0.25 mm,
hole-to-hole 0.3 mm), keep-outs and the 0.3 mm edge band; every move is a change list applied in a
transaction and accepted only if each changed item keeps its clearance (exact segment / polygon
distances). Moves keep directions: a moved run's corners slide along the neighbouring segments, a
moved via takes its tracks along the same way. A track that ends on the middle of another one
follows it (follow_anchors); segments over a via or through a pad must stay over it.

strip   The GND pours and every GND via without a track (old island and grid stitching) go; fan-out
        vias with their stubs stay. Vias with a router stub of < 0.15 mm move to the stub's end.
jogs    A jog is a track that steps sideways by < 1.5 mm with two bends and carries on in the same
        direction (pcb_audit.py's definition). For each one, in order: extend the run after it back
        along its own line until it meets the path before the jog (a crossing, a corner, the pad it
        starts in) or the other way round; slide the slanted part back to where the first run
        started (one bend instead of two); if only vias / tracks of other nets are in the way, push
        up to four of them aside by the smallest step that works; else re-route a window of the
        chain around the jog with an octilinear A* search (0.05 mm grid, start anywhere on the kept
        segment before, end anywhere on the line of the kept segment after, bend penalties, 50 %
        extra cost within 0.1 mm of the clearance limit). A fix must lower the jog count of every
        net it touches. A GND fan-out via (and its stub) in the way is rebuilt at another spot
        round its pad (GND reaches the planes from anywhere). What is still left: the whole run
        is ripped up and re-routed by route_prep's maze search (one layer, no 90 deg turn), kept
        when the net then has fewer jogs. USB_DP/USB_DM are kept as hand-routed (symmetric).
corners Every 90 deg corner becomes two 45 deg bends (chamfer_pass: the corner is cut back by up to
        1 mm along both legs; clearances, mid-segment connections and the jog count kept). KiCad's
        DRC then checks the copper; a fix that shows up in a violation is skipped and the step
        replayed.
voids   New GND zones: pours on F.Cu and B.Cu and solid planes on In1.Cu / In2.Cu (whole outline,
        clearance 0.2 mm, minimum width 0.2 mm, thermal reliefs 0.3 / 0.5 mm; net-class clearances
        above 0.2 mm still apply). Floating pour
        pieces too narrow for a via: each track bounding one is shifted toward it by the largest
        legal step (strip closes to minimum spacing); kept when, after a refill, the floating area
        within 3 mm has dropped by at least half the piece and no jog was added.
silk    References: one size for all, 1.0 mm / 0.15 mm (JLCPCB's minimum text height); 0 or 90 deg,
        keep-upright; outside every courtyard (mounting holes too); beside one side of its own part
        (overlapping its span by >= 40 %, never off a corner), at most 1 mm from it and at least
        0.05 mm nearer it than any other part; 0.15 mm from pads, mask openings and other silk,
        0.3 mm from the edge; never over a via (a via in the way of the only good spot is moved,
        plan_via_move, if it can); fewer tracks underneath preferred. Rows of like parts (GROUPS
        plus the rows pcb_audit.py finds: same footprint and rotation, in line, < 5 mm apart)
        share one side and line, in part order; a row of resistors / capacitors that finds no
        line gets one range label instead ("R16-19", beside the row, members' references hidden).
        No spot next to the part: a callout (label 1.15 - 10 mm off with a 0.15 mm leader that
        stops 0.2 mm short of the part and keeps clear of pads, silk, text and vias). Never on
        the bottom silkscreen (owner's review, rev 3). Plate names come after all references.
        Then the board legend (name, revision, date, JLCPCB order-number placeholder) in the
        clearest top-side spot, and the plate names after J1-J6's references (same line where it
        fits, else reference and name together elsewhere around the header).
        U1's pin-1 mark is synced with the local library (gen_lib.py: smaller, off the edge).
stitch  Every GND piece cut off from the main GND copper gets a via (0.45 / 0.2 mm) where one is
        legal on every layer, over the neighbouring GND plane and clear of silkscreen text; where
        text is the only thing in the way it moves (same rules, a row as a row); where tracks / vias
        of other nets are, they are pushed aside (as in `jogs`) if the via then joins the main GND.
        A GND via next to every layer change of a fast net (USB, SPI, WS2812 data: return path
        between the planes). Then a 5 mm grid of stitching vias (searching 1 mm around each point)
        where an outer pour is solid, off the labels and the U1/J7/J11 courtyards. Vias that only join floating pieces go; the final
        fill removes islands (ALWAYS), so no floating copper remains; route_prep.prune deletes
        stitching vias KiCad's DRC finds dangling.
After the steps: KiCad DRC (all severities) on the saved board, the jogs left with the reason for
each, and route_prep's report.
"""
import json
import math
import os
import subprocess
import sys

import pcbnew

import design as D
import route_prep as R
from gen_pcb import OX, OY

BOARD = R.BOARD
MM = pcbnew.FromMM
TOMM = pcbnew.ToMM
F, B = pcbnew.F_Cu, pcbnew.B_Cu
IN1, IN2 = R.IN1, R.IN2                     # solid GND planes (rev 3, stack-up option B)
MAXERR = MM(0.005)
UM = 1000                                   # nm per um

JOG_MAX_OFFSET = 1.5                        # mm, as pcb_audit.py
JOG_MAX_RUN = 3.0                           # mm, slanted middle part shorter than this
MINLEN = MM(0.05)                           # shortest segment a fix may leave
EDGE = 0.3                                  # mm, copper to board edge
HOLE_CLR = 0.28                             # mm, copper to a pad hole (JLCPCB PTH hole to track, DRU)
HOLE2HOLE = MM(0.3)                         # via hole to any hole (board minimum 0.25 mm, JLCPCB 0.2)
SKIP_NETS = ("USB_DP", "USB_DM")            # hand-routed differential pair: keep as drawn
REVISION = "3"                              # board title block (the schematic stays rev 2)


def bmm(v):
    return (round(TOMM(int(v[0])) - OX, 2), round(TOMM(int(v[1])) - OY, 2)) if isinstance(v, tuple) else R.bmm(v)


def save(board):
    R.save(board)


# ------------------------------------------------------------------------------ geometry helpers
def sub(a, b):
    return (a[0] - b[0], a[1] - b[1])


def add(a, b):
    return (a[0] + b[0], a[1] + b[1])


def mul(a, k):
    return (a[0] * k, a[1] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1]


def cross(a, b):
    return a[0] * b[1] - a[1] * b[0]


def norm(a):
    return math.hypot(a[0], a[1])


def unit(a):
    n = norm(a)
    return (a[0] / n, a[1] / n) if n else (0.0, 0.0)


def proj(p, o, d):
    """Projection of p onto the line through o with unit direction d."""
    return add(o, mul(d, dot(sub(p, o), d)))


def intersect(p, dp, q, dq):
    """Intersection of the lines p + s*dp and q + t*dq, or None when (nearly) parallel."""
    den = cross(dp, dq)
    if abs(den) < 1e-6:
        return None
    s = cross(sub(q, p), dq) / den
    return add(p, mul(dp, s))


def V(p):
    return pcbnew.VECTOR2I(int(round(p[0])), int(round(p[1])))


def key(p):
    return (int(round(p[0] / UM)), int(round(p[1] / UM)))


# ------------------------------------------------------------------------------ clearance model
CELL = MM(2.0)                              # obstacle index cell


def uid(it):
    return it.m_Uuid.AsString()


def item_poly(it, layer):
    s = pcbnew.SHAPE_POLY_SET()
    it.TransformShapeToPolygon(s, layer, 0, MAXERR, pcbnew.ERROR_OUTSIDE)
    return s


def pt(v):
    """Copy of a VECTOR2I as a float tuple (SWIG hands back references that follow the item)."""
    return (float(v.x), float(v.y))


class Obstacles:
    """Copper of the board per layer (pads, tracks, vias), holes and track keep-outs, in a coarse
    grid index, for clearance checks of new or moved tracks and vias. Entries:
    (layer, net, polygon, bbox, clearance, uuid, kind, item); net -1 = holes / keep-outs."""

    def __init__(self, board):
        self.board = board
        self.clr_cache = {}
        self.ents, self.grid, self.by_uid, self.holes = {}, {}, {}, {}
        self.next = 0
        for fp in board.GetFootprints():
            for pd in fp.Pads():
                u = uid(pd)
                for layer in (F, B):
                    if pd.IsOnLayer(layer):
                        s = item_poly(pd, layer)
                        if s.OutlineCount():
                            self._add(layer, pd.GetNetCode(), s, pd.GetOwnClearance(layer), u, "pad", pd)
                    elif pd.HasHole():
                        s = pcbnew.SHAPE_POLY_SET()
                        pd.TransformHoleToPolygon(s, 0, MAXERR, pcbnew.ERROR_OUTSIDE)
                        if s.OutlineCount():
                            self._add(layer, -1, s, MM(HOLE_CLR), u, "hole", pd)
                if pd.HasHole():
                    self.holes[u] = (pt(pd.GetPosition()), max(pd.GetDrillSizeX(), pd.GetDrillSizeY()) / 2)
            for z in fp.Zones():
                if z.GetIsRuleArea() and z.GetDoNotAllowTracks():
                    for layer in (F, B):
                        if z.IsOnLayer(layer):
                            self._add(layer, -1, pcbnew.SHAPE_POLY_SET(z.Outline()), 0, uid(z), "keepout", z)
        for t in board.GetTracks():
            self.add_track(t)

    def net_clearance(self, netcode):
        if netcode not in self.clr_cache:
            t = pcbnew.PCB_TRACK(self.board)
            t.SetNetCode(netcode)
            t.SetLayer(F)
            self.clr_cache[netcode] = t.GetOwnClearance(F)
        return self.clr_cache[netcode]

    @staticmethod
    def _cells(layer, x0, y0, x1, y1):
        for cx in range(int(x0 // CELL), int(x1 // CELL) + 1):
            for cy in range(int(y0 // CELL), int(y1 // CELL) + 1):
                yield (layer, cx, cy)

    def _add(self, layer, net, s, clr, u, kind, item):
        b = s.BBox()
        bb = (b.GetLeft(), b.GetTop(), b.GetRight(), b.GetBottom())
        eid = self.next
        self.next += 1
        self.ents[eid] = (layer, net, s, bb, clr, u, kind, item)
        for c in self._cells(layer, *bb):
            self.grid.setdefault(c, set()).add(eid)
        self.by_uid.setdefault(u, []).append(eid)

    def add_track(self, t):
        u = uid(t)
        if t.GetClass() == "PCB_VIA":
            for layer in (F, B):
                self._add(layer, t.GetNetCode(), item_poly(t, layer), t.GetOwnClearance(layer), u, "via", t)
            self.holes[u] = (pt(t.GetPosition()), t.GetDrillValue() / 2)
        else:
            self._add(t.GetLayer(), t.GetNetCode(), item_poly(t, t.GetLayer()), t.GetOwnClearance(t.GetLayer()), u, "track", t)

    def remove_track(self, t):
        u = uid(t)
        for eid in self.by_uid.pop(u, []):
            layer, net, s, bb, clr, uu, kind, item = self.ents.pop(eid)
            for c in self._cells(layer, *bb):
                self.grid[c].discard(eid)
        self.holes.pop(u, None)

    def near(self, layer, x0, y0, x1, y1):
        seen = set()
        for c in self._cells(layer, x0, y0, x1, y1):
            for eid in self.grid.get(c, ()):
                if eid not in seen:
                    seen.add(eid)
                    e = self.ents[eid]
                    bb = e[3]
                    if bb[2] >= x0 and bb[0] <= x1 and bb[3] >= y0 and bb[1] <= y1:
                        yield e

    @staticmethod
    def in_board(p, margin):
        return (MM(OX) + margin <= p[0] <= MM(OX + D.BOARD_W) - margin and
                MM(OY) + margin <= p[1] <= MM(OY + D.BOARD_H) - margin)

    def seg_conflicts(self, a, b, width, layer, netcode, ignore=(), first=False):
        """Entries a track a-b would come too close to (None = board edge)."""
        hw = width / 2
        out = []
        if not (self.in_board(a, MM(EDGE) + hw) and self.in_board(b, MM(EDGE) + hw)):
            out.append(None)
            if first:
                return out
        seg = pcbnew.SEG(V(a), V(b))
        own = self.net_clearance(netcode)
        r = hw + MM(0.6)
        for e in self.near(layer, min(a[0], b[0]) - r, min(a[1], b[1]) - r, max(a[0], b[0]) + r, max(a[1], b[1]) + r):
            net, s, clr, u = e[1], e[2], e[4], e[5]
            if (net == netcode and net >= 0) or u in ignore:
                continue
            need = hw + (clr if net < 0 else max(own, clr)) + UM
            if s.SquaredDistanceToSeg(seg) < need * need:
                out.append(e)
                if first:
                    return out
        return out

    def via_conflicts(self, p, diameter, drill, netcode, ignore=(), first=False):
        """Entries a via at p would come too close to (None = edge, ('hole', uuid) = hole to hole)."""
        r = diameter / 2
        out = []
        if not self.in_board(p, MM(EDGE) + r):
            out.append(None)
            if first:
                return out
        q = V(p)
        own = self.net_clearance(netcode)
        for layer in (F, B):
            for e in self.near(layer, p[0] - r - MM(0.6), p[1] - r - MM(0.6), p[0] + r + MM(0.6), p[1] + r + MM(0.6)):
                net, s, clr, u = e[1], e[2], e[4], e[5]
                if (net == netcode and net >= 0) or u in ignore:
                    continue
                need = r + (clr if net < 0 else max(own, clr)) + UM
                if s.SquaredDistance(q) < need * need:
                    out.append(e)
                    if first:
                        return out
        for u, (c, hr) in self.holes.items():
            if u in ignore:
                continue
            if norm(sub(c, p)) < hr + drill / 2 + HOLE2HOLE:
                out.append(("hole", u))
                if first:
                    return out
        return out


# ------------------------------------------------------------------------------ track chains
def track_groups(board, exclude=()):
    groups = {}
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetLength() > 0 and (not exclude or uid(t) not in exclude):
            groups.setdefault((t.GetNetCode(), t.GetLayer()), []).append(t)
    return groups


def count_jogs(pts):
    """Jogs in a point list once collinear pieces are joined (as pcb_audit.py counts them)."""
    q = [pts[0]]
    for p in pts[1:]:
        if len(q) >= 2:
            d1, d2 = unit(sub(q[-1], q[-2])), unit(sub(p, q[-1]))
            if dot(d1, d2) > 0.99999:
                q[-1] = p
                continue
        if norm(sub(p, q[-1])) > UM:
            q.append(p)
    return len(find_jogs(q))


def chains(board, nets=None, exclude=()):
    """[(netcode, layer, [points nm], [tracks])]: runs of segments joined end to end at points that
    are not pads, vias, branch points or T-junctions. Points are float tuples (nm). Tracks whose
    uuid is in exclude are left out."""
    vias = [v for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
    out = []
    for (net, layer), segs in track_groups(board, exclude).items():
        if nets is not None and net not in nets:
            continue
        adj, pos = {}, {}
        for t in segs:
            a, b = pt(t.GetStart()), pt(t.GetEnd())
            ka, kb = key(a), key(b)
            pos.setdefault(ka, a)
            pos.setdefault(kb, b)
            adj.setdefault(ka, []).append((kb, t))
            adj.setdefault(kb, []).append((ka, t))
        nvias = [v for v in vias if v.GetNetCode() == net]
        npads = [p for p in pads if p.GetNetCode() == net and p.IsOnLayer(layer)]
        stop = {}

        def is_stop(k):
            if k in stop:
                return stop[k]
            r = len(adj[k]) != 2
            if not r:
                v = V(pos[k])
                mine = (uid(adj[k][0][1]), uid(adj[k][1][1]))
                # a T-junction: the point lies on the centre line of another segment of the net
                r = any(x.HitTest(v, 0) for x in nvias) or any(p.HitTest(v) for p in npads) or \
                    any(pcbnew.SEG(t.GetStart(), t.GetEnd()).Distance(v) <= 2 * UM for t in segs if uid(t) not in mine)
            stop[k] = r
            return r
        seen = set()
        for start in adj:
            if not is_stop(start):
                continue
            for nxt, t in adj[start]:
                if uid(t) in seen:
                    continue
                seen.add(uid(t))
                ks, ts = [start, nxt], [t]
                cur = nxt
                while not is_stop(cur):
                    cand = [(n2, t2) for n2, t2 in adj[cur] if uid(t2) not in seen]
                    if not cand:
                        break
                    cur, t2 = cand[0]
                    seen.add(uid(t2))
                    ks.append(cur)
                    ts.append(t2)
                out.append((net, layer, [pos[k] for k in ks], ts))
    return out


def find_jogs(pts):
    """Indices i where segments i (A), i+1 (B), i+2 (C) form a jog, with the sideways offset (nm)."""
    res = []
    d = [sub(pts[i + 1], pts[i]) for i in range(len(pts) - 1)]
    for i in range(len(d) - 2):
        la, lb, lc = norm(d[i]), norm(d[i + 1]), norm(d[i + 2])
        if not (la and lb and lc):
            continue
        ua, ub, uc = unit(d[i]), unit(d[i + 1]), unit(d[i + 2])
        if dot(ua, uc) > 0.999 and abs(dot(ua, ub)) < 0.999 and lb < MM(JOG_MAX_RUN):
            off = abs(cross(ua, sub(pts[i + 2], pts[i + 1])))
            if MM(0.005) < off < MM(JOG_MAX_OFFSET):
                res.append((i, off))
    return res


def pad_at(board, netcode, layer, p):
    for fp in board.GetFootprints():
        for pd in fp.Pads():
            if pd.GetNetCode() == netcode and pd.IsOnLayer(layer) and pd.HitTest(V(p)):
                return pd
    return None


def via_at(board, netcode, p):
    for v in board.GetTracks():
        if v.GetClass() == "PCB_VIA" and v.GetNetCode() == netcode and v.HitTest(V(p), 0):
            return v
    return None


def inside_pad(pd, layer, p, margin):
    s = pcbnew.SHAPE_POLY_SET()
    pd.TransformShapeToPolygon(s, layer, 0, MAXERR, pcbnew.ERROR_INSIDE)
    q = V(p)
    if not s.Contains(q):
        return False
    e = nearest_on_poly(s, p)                   # distance to the outline (KiCad's outline-only
    return e is not None and norm(sub(e, p)) >= margin   # SquaredDistance is not implemented)


def preroute_uids(board):
    """UUIDs of the tracks and vias drawn by route_prep's PREROUTE / PREVIAS (kept as they are)."""
    want = set()
    for layer, net, w, pts in R.PREROUTE:
        for a, b in zip(pts, pts[1:]):
            want.add((net, layer, frozenset((key(pt(R.P(*a))), key(pt(R.P(*b)))))))
    vias = {(net, key(pt(R.P(x, y)))) for net, x, y in R.PREVIAS}
    out = set()
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            if (t.GetNetname(), key(pt(t.GetPosition()))) in vias:
                out.add(uid(t))
        elif (t.GetNetname(), t.GetLayer(), frozenset((key(pt(t.GetStart())), key(pt(t.GetEnd()))))) in want:
            out.add(uid(t))
    return out


class Ctx:
    """Board, obstacle index, track chains and the items that must stay where they are."""

    def __init__(self, board):
        self.board = board
        self.obs = Obstacles(board)
        self.fixed = preroute_uids(board)
        self.refresh()

    def refresh(self):
        self.chains = chains(self.board)
        self.where = {}
        for ci, (net, layer, pts, ts) in enumerate(self.chains):
            for i, t in enumerate(ts):
                self.where[uid(t)] = (ci, i)
        self.anchors = anchored_tracks(self.board, self.where)
        self.anchored = set(self.anchors)
        self.pinned = {u for u, al in self.anchors.items() if any(a[0] in ("pin",) for a in al)}

    def movable(self, it):
        return it.GetClass() in ("PCB_TRACK", "PCB_VIA") and uid(it) not in self.fixed and \
            uid(it) not in self.pinned and it.GetNetname() not in SKIP_NETS


def anchored_tracks(board, where=None):
    """{uuid: [anchors]} for track segments that carry a connection other than their chain
    neighbours. Anchors: ("tee", U, end) - end 0/1 of another track U of the net (not one of the
    next two segments of the same chain) lies on this segment; ("onto", S, end) - this track's end
    lies on segment S; ("via", v) - a via of the net sits on it away from its ends; ("pad", p) - it
    runs through a pad of the net without ending in it. A move must keep every one of them
    (follow_anchors); via and pad anchors pin the segment."""
    where = where or {}
    out = {}
    tracks = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"]
    vias = [v for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
    bynet = {}
    for t in tracks:
        bynet.setdefault(t.GetNetCode(), []).append(t)

    def near_in_chain(a, b):
        wa, wb = where.get(uid(a)), where.get(uid(b))
        return wa is not None and wb is not None and wa[0] == wb[0] and abs(wa[1] - wb[1]) <= 2
    for net, ts in bynet.items():
        ends = [(t, 0, pt(t.GetStart())) for t in ts] + [(t, 1, pt(t.GetEnd())) for t in ts]
        nvias = [v for v in vias if v.GetNetCode() == net]
        npads = [p for p in pads if p.GetNetCode() == net]
        # ends that sit in a pad or via of the net connect there, whatever track they overlap
        in_pad = set()
        for o, ei, p in ends:
            q = V(p)
            if any(pd.IsOnLayer(o.GetLayer()) and pd.HitTest(q) for pd in npads) or any(v.HitTest(q, 0) for v in nvias):
                in_pad.add((uid(o), ei))
        for t in ts:
            own = (key(pt(t.GetStart())), key(pt(t.GetEnd())))
            seg = pcbnew.SEG(t.GetStart(), t.GetEnd())
            hw = t.GetWidth() / 2
            for o, ei, p in ends:
                if o is t or key(p) in own or near_in_chain(o, t) or (uid(o), ei) in in_pad:
                    continue
                if seg.Distance(V(p)) < hw:
                    out.setdefault(uid(t), []).append(("tee", o, ei))
                    out.setdefault(uid(o), []).append(("onto", t, ei))
            for v in nvias:
                p = pt(v.GetPosition())
                if key(p) not in own and seg.Distance(V(p)) < hw and \
                        not (v.HitTest(t.GetStart(), 0) or v.HitTest(t.GetEnd(), 0)):
                    out.setdefault(uid(t), []).append(("via", v))
                    out.setdefault(uid(v), []).append(("pin", t))       # the via stays as well
            for pd in npads:
                if not pd.IsOnLayer(t.GetLayer()) or pd.HitTest(t.GetStart()) or pd.HitTest(t.GetEnd()):
                    continue
                s = item_poly(pd, t.GetLayer())
                if s.SquaredDistanceToSeg(seg) < hw ** 2:
                    out.setdefault(uid(t), []).append(("pad", pd))
    return out


FA_FAIL = []                                # last reason follow_anchors refused (line number)


def _fa_fail():
    FA_FAIL[:] = [sys._getframe(1).f_lineno]       # where follow_anchors refused (diagnostics)
    return None


def follow_anchors(ctx, ch, regone=False):
    """The change list ch extended so that every mid-segment connection survives: a track ending
    on a moved segment slides its end along its own direction onto the segment's new line; a
    track whose end sits on another segment may move that end only along that segment. None when
    a change would cut a connection (segments pinned by vias or pads, deletions of carriers,
    pre-routes)."""
    out = list(ch)
    geo = {}
    for c in ch:
        if c[0] == "seg":
            geo[uid(c[1])] = (c[2], c[3])
        elif c[0] == "del":
            geo[uid(c[1])] = None

    def cur(t):
        return geo.get(uid(t), (pt(t.GetStart()), pt(t.GetEnd())))
    i = 0
    while i < len(out):
        c = out[i]
        i += 1
        if c[0] in ("add", "addvia"):
            continue
        it = c[1]
        u = uid(it)
        if u in ctx.fixed:
            return _fa_fail()
        if c[0] == "via":
            if u in ctx.pinned:
                return _fa_fail()
            continue
        for a in ctx.anchors.get(u, []):
            kind = a[0]
            if kind in ("via", "pad"):
                # still over the via / through the pad after the move?
                if c[0] == "del":
                    return _fa_fail()
                seg = pcbnew.SEG(V(c[2]), V(c[3]))
                if kind == "via":
                    if seg.Distance(a[1].GetPosition()) > it.GetWidth() / 2 - UM:
                        return _fa_fail()
                elif item_poly(a[1], it.GetLayer()).SquaredDistanceToSeg(seg) > (it.GetWidth() / 2 - UM) ** 2:
                    return _fa_fail()
                continue
            if c[0] == "del" and kind == "tee":
                # the carrier goes: the track ending on it slides onto the new path of the chain
                U, ei = a[1], a[2]
                if regone and geo.get(uid(U), 0) is None:
                    continue                        # the branch goes too (maze_jogs routes it again)
                if uid(U) in geo or uid(U) in ctx.fixed:
                    return _fa_fail()
                s0, s1 = cur(U)
                e, o = (s0, s1) if ei == 0 else (s1, s0)
                dU = unit(sub(e, o))
                hit = None
                for c2 in out:
                    if c2[0] == "add" and c2[1] == it.GetNetCode() and c2[2] == it.GetLayer():
                        na, nb = c2[4], c2[5]
                    elif c2[0] == "seg" and c2[1].GetNetCode() == it.GetNetCode() and c2[1].GetLayer() == it.GetLayer():
                        na, nb = c2[2], c2[3]
                    else:
                        continue
                    dS = unit(sub(nb, na))
                    X = intersect(o, dU, na, dS)
                    if X is None:
                        continue
                    t = dot(sub(X, na), dS)
                    if 0 <= t <= norm(sub(nb, na)) and dot(sub(X, o), dU) >= MINLEN and \
                            (hit is None or norm(sub(X, e)) < norm(sub(hit, e))):
                        hit = X
                if hit is None:
                    return _fa_fail()
                newc = ("seg", U, hit, o) if ei == 0 else ("seg", U, o, hit)
                geo[uid(U)] = (newc[2], newc[3])
                out.append(newc)
                continue
            if c[0] == "del" and kind == "onto":
                # a deleted track that ended on S: some new segment must end on S instead
                S = a[1]
                g = cur(S)
                if g is None and regone:
                    continue                        # its carrier goes too (maze_jogs routes again)
                if g is None:
                    return _fa_fail()
                ok = False
                for c2 in out:
                    if c2[0] == "add":
                        ends = (c2[4], c2[5])
                    elif c2[0] == "seg" and c2[1].GetNetCode() == it.GetNetCode():
                        ends = (c2[2], c2[3])
                    else:
                        continue
                    if any(dist_point_seg(e2, g[0], g[1]) < S.GetWidth() / 2 - UM for e2 in ends):
                        ok = True
                        break
                if not ok:
                    return _fa_fail()
                continue
            if c[0] == "del":
                return _fa_fail()
            if kind == "tee":
                U, ei = a[1], a[2]
                ga = geo.get(uid(U))
                if ga is None and uid(U) in geo:
                    return _fa_fail()
                s0, s1 = cur(U)
                e, o = (s0, s1) if ei == 0 else (s1, s0)
                na, nb = c[2], c[3]
                dS = unit(sub(nb, na))
                if dist_point_seg(e, na, nb) < it.GetWidth() / 2 - UM:
                    continue                        # its end is still on the moved segment
                if uid(U) in geo:
                    return _fa_fail()
                dU = unit(sub(e, o))
                X = intersect(o, dU, na, dS)
                if X is None:
                    return _fa_fail()
                t = dot(sub(X, na), dS)
                if t < 0 or t > norm(sub(nb, na)) or dot(sub(X, o), dU) < MINLEN:
                    return _fa_fail()
                if uid(U) in ctx.fixed:
                    return _fa_fail()
                newc = ("seg", U, X, o) if ei == 0 else ("seg", U, o, X)
                geo[uid(U)] = (newc[2], newc[3])
                out.append(newc)
            elif kind == "onto":
                S, ei = a[1], a[2]
                g = cur(S)
                if g is None:
                    return _fa_fail()
                e = c[2] if ei == 0 else c[3]
                if dist_point_seg(e, g[0], g[1]) > S.GetWidth() / 2 - UM:
                    return _fa_fail()
    return out


def dist_point_seg(p, a, b):
    d = sub(b, a)
    L2 = dot(d, d)
    if L2 == 0:
        return norm(sub(p, a))
    t = max(0.0, min(1.0, dot(sub(p, a), d) / L2))
    return norm(sub(p, add(a, mul(d, t))))




class Txn:
    """Changes to tracks and vias, applied to the board and the obstacle index at once, with
    savepoints; deletions happen on commit."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.log = []
        self.dele = []

    def mark(self):
        return len(self.log)

    def apply(self, changes):
        obs = self.ctx.obs
        for ch in changes:
            kind, it = ch[0], ch[1]
            if kind == "seg":
                a, b = ch[2], ch[3]
                self.log.append(("seg", it, pt(it.GetStart()), pt(it.GetEnd()), it.GetWidth()))
                obs.remove_track(it)
                it.SetStart(V(a))
                it.SetEnd(V(b))
                if len(ch) > 4 and ch[4]:
                    it.SetWidth(int(ch[4]))
                obs.add_track(it)
            elif kind == "via":
                self.log.append(("via", it, pt(it.GetPosition())))
                obs.remove_track(it)
                it.SetPosition(V(ch[2]))
                obs.add_track(it)
            elif kind == "del":
                self.log.append(("del", it))
                obs.remove_track(it)
                self.dele.append(it)
            elif kind == "addvia":                  # ("addvia", netcode, position)
                v = pcbnew.PCB_VIA(self.ctx.board)
                v.SetPosition(V(ch[2]))
                small = ch[1] == self.ctx.board.FindNet("GND").GetNetCode()
                v.SetWidth(R.GND_VIA_D if small else R.VIA_D)
                v.SetDrill(R.GND_VIA_DRILL if small else R.VIA_DRILL)
                v.SetLayerPair(F, B)
                v.SetNetCode(ch[1])
                self.ctx.board.Add(v)
                obs.add_track(v)
                self.log.append(("add", v))
            elif kind == "add":                     # ("add", netcode, layer, width, a, b)
                t = pcbnew.PCB_TRACK(self.ctx.board)
                t.SetNetCode(ch[1])
                t.SetLayer(ch[2])
                t.SetWidth(int(ch[3]))
                t.SetStart(V(ch[4]))
                t.SetEnd(V(ch[5]))
                self.ctx.board.Add(t)
                obs.add_track(t)
                self.log.append(("add", t))

    def rollback(self, mark=0):
        obs = self.ctx.obs
        while len(self.log) > mark:
            ent = self.log.pop()
            it = ent[1]
            if ent[0] == "add":
                obs.remove_track(it)
                self.ctx.board.Delete(it)
                continue
            if ent[0] == "seg":
                obs.remove_track(it)
                it.SetStart(V(ent[2]))
                it.SetEnd(V(ent[3]))
                it.SetWidth(ent[4])
                obs.add_track(it)
            elif ent[0] == "via":
                obs.remove_track(it)
                it.SetPosition(V(ent[2]))
                obs.add_track(it)
            else:
                self.dele.pop()
                obs.add_track(it)

    def commit(self):
        for t in self.dele:
            self.ctx.board.Delete(t)
        self.log, self.dele = [], []

    def touched(self, mark=0):
        gone = {uid(t) for t in self.dele}
        out = {}
        for ent in self.log[mark:]:
            if ent[0] != "del" and uid(ent[1]) not in gone:
                out[uid(ent[1])] = ent[1]
        return list(out.values())

    def conflicts(self, mark=0, first=False):
        """[(changed item, entry it conflicts with)] for the items changed since mark."""
        obs = self.ctx.obs
        res = []
        for it in self.touched(mark):
            u = (uid(it),)
            if it.GetClass() == "PCB_VIA":
                c = obs.via_conflicts(pt(it.GetPosition()), it.GetWidth(F), it.GetDrillValue(), it.GetNetCode(), u, first)
            else:
                c = obs.seg_conflicts(pt(it.GetStart()), pt(it.GetEnd()), it.GetWidth(), it.GetLayer(), it.GetNetCode(), u, first)
            res += [(it, e) for e in c]
            if first and res:
                return res
        return res


# ------------------------------------------------------------------------------ moves
COS45 = math.cos(math.radians(45.5))


def plan_extend(board, P, T, j, layer, wide):
    """Jog at j (A = T[j], B = T[j+1], C = T[j+2]): extend C backwards along its own line until it
    meets the path before the jog: a segment it crosses (walking back from A; the segment just
    before A may also be lengthened), a corner it passes through (collinear runs merge) or the pad
    the chain starts in. Everything between that point and C goes. Turns stay 45 deg or less.
    Returns change lists (one per width choice)."""
    dC = unit(sub(P[j + 3], P[j + 2]))
    hit = None
    for k in range(j - 1, -1, -1):
        a, b = P[k], P[k + 1]
        uk = unit(sub(b, a))
        lk = norm(sub(b, a))
        X = intersect(a, uk, P[j + 2], dC)
        if X is None:
            if dot(uk, dC) > 0 and abs(cross(dC, sub(a, P[j + 2]))) < 2 * UM:
                hit = (k, b)                       # collinear with C: merge
                break
            continue
        s = dot(sub(X, a), uk)
        if dot(sub(X, P[j + 2]), dC) > -MINLEN:
            continue
        if k == j - 1 and s >= MINLEN:
            hit = (k, X)                           # corner before A slides along its segment
            break
        if MINLEN <= s <= lk - MINLEN and dot(uk, dC) >= COS45:
            hit = (k, X)
            break
        if abs(s - lk) < MINLEN and dot(uk, dC) >= COS45:
            hit = (k, b)
            break
        if abs(s) < MINLEN and k == 0:
            hit = (-1, P[0])                       # straight into the chain's start pad / via
            break
    if hit is None:
        pd = pad_at(board, T[0].GetNetCode(), layer, P[0])
        if pd is None or via_at(board, T[0].GetNetCode(), P[0]) is not None:
            return []
        X = proj(P[0], P[j + 2], dC)
        if dot(sub(X, P[j + 2]), dC) > -MINLEN / 2 or not inside_pad(pd, layer, X, MM(0.05)):
            return []
        hit = (-1, X)
    k, X = hit
    removed = T[k + 1:j + 2]
    wC = T[j + 2].GetWidth()
    widths = [wC]
    wmax = max([t.GetWidth() for t in removed] + [wC])
    if wide and wmax != wC:
        widths.insert(0, wmax)
    plans = []
    for w in widths:
        ch = []
        if k >= 0:
            ch.append(("seg", T[k], P[k], X))
        if norm(sub(P[j + 2], X)) >= UM:
            ch.append(("seg", removed[0], X, P[j + 2], w))
            ch += [("del", t) for t in removed[1:]]
        else:
            ch += [("del", t) for t in removed]
        plans.append(ch)
    return plans


def plan_bslide(board, P, T, j, layer, wide):
    """Jog at j: drop A and start the slanted part B right where A started (B keeps its angle),
    C is lengthened back to meet it: one bend instead of two. Allowed when A starts at a pad / via,
    or when the turn from the segment before A into B is 45 deg or less."""
    dB = unit(sub(P[j + 2], P[j + 1]))
    dC = unit(sub(P[j + 3], P[j + 2]))
    if j >= 1 and dot(unit(sub(P[j], P[j - 1])), dB) < COS45:
        return []
    X = intersect(P[j], dB, P[j + 2], dC)
    if X is None:
        return []
    if dot(sub(X, P[j]), dB) < MINLEN or dot(sub(P[j + 3], X), dC) < MINLEN:
        return []
    wB = T[j + 1].GetWidth()
    widths = [wB]
    wmax = max(T[j].GetWidth(), wB)
    if wide and wmax != wB:
        widths.insert(0, wmax)
    return [[("seg", T[j + 1], P[j], X, w), ("seg", T[j + 2], X, P[j + 3]), ("del", T[j])] for w in widths]


def jog_plans(board, pts, ts, j, layer):
    """Candidate fixes for the jog at j: [(label, changes)], preferred first."""
    n = len(ts)
    wide = ts[0].GetNetname() in D.POWER_NETS
    out = []
    for kind, fn in (("extend", plan_extend), ("slide", plan_bslide)):
        for rev in (False, True):
            P, T, jj = (pts[::-1], ts[::-1], n - 1 - (j + 2)) if rev else (pts, ts, j)
            for ch in fn(board, P, T, jj, layer, wide):
                out.append(("%s %s" % (kind, "back" if rev else "fwd"), ch))
    return out


def chain_end(ctx, t, p):
    """For track t with an end at p (a stop): (chain points, tracks) oriented to start at p."""
    ci, i = ctx.where[uid(t)]
    net, layer, P, T = ctx.chains[ci]
    if i == 0 and norm(sub(P[0], p)) < MM(0.4):
        return P, T
    if i == len(T) - 1 and norm(sub(P[-1], p)) < MM(0.4):
        return P[::-1], T[::-1]
    return None


def plan_via_move(ctx, v, m, skip=()):
    """Move via v by m (nm vector). Each track at the via keeps its direction: it gets longer or
    shorter when it points along m, otherwise it moves with the via and its far corner slides along
    the next segment. None when that does not work out. Tracks in skip are left to the caller."""
    p = pt(v.GetPosition())
    p2 = add(p, m)
    ch = [("via", v, p2)]
    attached = [t for t in ctx.board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == v.GetNetCode()
                and (v.HitTest(t.GetStart(), 0) or v.HitTest(t.GetEnd(), 0)) and uid(t) not in skip]
    mm = norm(m)
    for t in attached:
        if norm(sub(pt(t.GetStart()), p2)) < UM or norm(sub(pt(t.GetEnd()), p2)) < UM:
            continue                                # already ends where the via goes
        if uid(t) not in ctx.where:
            return None
        ce = chain_end(ctx, t, p)
        if ce is None:
            return None
        P, T = ce
        far = P[1]
        dS = unit(sub(far, P[0]))
        if abs(cross(dS, m)) < 1e-3 * mm:
            if dot(sub(far, p2), dS) < MINLEN:
                return None
            ch.append(("seg", T[0], p2, far))
            continue
        if len(T) < 2:
            return None
        dN = unit(sub(P[2], P[1]))
        Q = intersect(p2, dS, far, dN)
        if Q is None or dot(sub(Q, p2), dS) < MINLEN or dot(sub(P[2], Q), dN) < MINLEN:
            return None
        ch += [("seg", T[0], p2, Q), ("seg", T[1], Q, P[2])]
    return ch


def plan_shift(ctx, t, m):
    """Move track t sideways by m (perpendicular to it): the corners at both ends slide along the
    neighbouring segments, so every direction stays as it was. None when an end is a stop."""
    if uid(t) not in ctx.where:
        return None
    ci, i = ctx.where[uid(t)]
    net, layer, P, T = ctx.chains[ci]
    dS = unit(sub(P[i + 1], P[i]))
    a2 = add(P[i], m)
    ch = []
    ends = []
    for side in (0, 1):
        k = i if side == 0 else i + 1               # node index of this end
        last = (k == 0) if side == 0 else (k == len(T))
        if last:
            # a via at the end of the chain moves along with the track
            v = via_at(ctx.board, net, P[k])
            if v is None or not ctx.movable(v):
                return None
            sub_ch = plan_via_move(ctx, v, m, skip=(uid(t),))
            if sub_ch is None:
                return None
            ch += sub_ch
            ends.append(add(pt(v.GetPosition()), m))
            continue
        o = P[k - 1] if side == 0 else P[k + 1]     # far end of the neighbouring segment
        nb = T[k - 1] if side == 0 else T[k]
        dn = unit(sub(P[k], o))
        Q = intersect(o, dn, a2, dS)
        if Q is None or dot(sub(Q, o), dn) < MINLEN:
            return None
        ch.append(("seg", nb, o, Q) if side == 0 else ("seg", nb, Q, o))
        ends.append(Q)
    if dot(sub(ends[1], ends[0]), dS) < MINLEN:
        return None
    ch.append(("seg", t, ends[0], ends[1]))
    return ch


OCT = [(math.cos(k * math.pi / 4), math.sin(k * math.pi / 4)) for k in range(8)]
PUSH_STEPS = [MM(0.05 * k) for k in range(1, 31)]          # 0.05 .. 1.5 mm


def entry_center(e):
    bb = e[3]
    return ((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)


def fanout_of(ctx, it):
    """(via, stub, pad) when it is a GND fan-out via or its stub: a GND via with exactly one track,
    on F.Cu, whose other end lies in a GND SMD pad (route_prep.gnd_fanout); else None."""
    gnd = ctx.board.FindNet("GND").GetNetCode()
    if it.GetNetCode() != gnd or not ctx.movable(it):
        return None
    if it.GetClass() == "PCB_VIA":
        v = it
    else:
        v = None
        for q in (it.GetStart(), it.GetEnd()):
            v = v or via_at(ctx.board, gnd, pt(q))
        if v is None or not ctx.movable(v):
            return None
    tr = [t for t in ctx.board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == gnd
          and (v.HitTest(t.GetStart(), 0) or v.HitTest(t.GetEnd(), 0))]
    if len(tr) != 1 or tr[0].GetLayer() != F or not ctx.movable(tr[0]) or uid(tr[0]) in ctx.anchored:
        return None
    t = tr[0]
    far = pt(t.GetEnd()) if v.HitTest(t.GetStart(), 0) else pt(t.GetStart())
    pd = pad_at(ctx.board, gnd, F, far)
    if pd is None or pd.HasHole():
        return None
    return v, t, pd


def relocate_fanout(ctx, txn, fo, toward):
    """Rebuild a GND fan-out (via + stub from its pad) at another spot around the pad, preferring
    directions along `toward`, inside the open transaction. GND reaches the planes from anywhere,
    so fan-out vias are as free to move as stitching vias. True if done."""
    v, t, pd = fo
    gnd = v.GetNetCode()
    c = pt(pd.GetPosition())
    bb = pd.GetBoundingBox()
    hw, hh = bb.GetWidth() / 2, bb.GetHeight() / 2
    tw = unit(toward) if norm(toward) else (0.0, 0.0)
    dirs = sorted([(math.cos(a * math.pi / 8), math.sin(a * math.pi / 8)) for a in range(16)],
                  key=lambda d: -dot(d, tw))
    avoid = [ctx.board.FindFootprintByReference(r).GetCourtyard(pcbnew.F_CrtYd) for r in R.FAN_AVOID]
    width = t.GetWidth()
    for extra in (0.0, 0.2, 0.4, 0.7, 1.0):
        for d in dirs:
            reach = abs(d[0]) * hw + abs(d[1]) * hh
            dist = reach + MM(R.FAN_CLEAR + 0.05 + extra) + R.GND_VIA_D / 2
            q = add(c, mul(d, dist))
            if any(a.Contains(V(q)) for a in avoid):
                continue
            mk = txn.mark()
            txn.apply([("del", t), ("del", v), ("addvia", gnd, q), ("add", gnd, F, width, c, q)])
            if not txn.conflicts(mk, first=True):
                return True
            txn.rollback(mk)
    return False


def clear_blocker(ctx, txn, e, toward):
    """Move the via / track of entry e out of the way of the changes in txn (all clearances kept):
    the smallest push that works, preferring directions along `toward` (nm vector); a GND fan-out
    in the way is rebuilt elsewhere around its pad if pushing does not work. True if moved."""
    it = e[7]
    fo = fanout_of(ctx, it)
    if fo is not None and uid(fo[0]) not in {uid(x) for x in txn.touched()}:
        if relocate_fanout(ctx, txn, fo, toward):
            return True
    if e[6] == "via":
        p = pt(it.GetPosition())
        dirs = list(OCT)
        maker = lambda m: plan_via_move(ctx, it, m)
    else:
        if uid(it) not in ctx.where:
            return False
        ci, i = ctx.where[uid(it)]
        P = ctx.chains[ci][2]
        dS = unit(sub(P[i + 1], P[i]))
        dirs = [(-dS[1], dS[0]), (dS[1], -dS[0])]
        maker = lambda m: plan_shift(ctx, it, m)
    tw = unit(toward) if norm(toward) else (0.0, 0.0)
    dirs = sorted(dirs, key=lambda d: -dot(d, tw))
    dirs = [d for d in dirs if dot(d, tw) > -0.2]
    for step in PUSH_STEPS:
        for d in dirs:
            ch = maker(mul(d, step))
            ch = follow_anchors(ctx, ch) if ch is not None else None
            if ch is None or stale(ctx, txn, ch):
                continue
            mk = txn.mark()
            txn.apply(ch)
            if not txn.conflicts(mk, first=True):
                return True
            txn.rollback(mk)
    return False


def stale(ctx, txn, ch):
    """True when a change list was computed from chains that the open transaction has already
    changed (ctx.chains are refreshed only on commit, so its corner positions may be out of date)."""
    touched = {uid(x) for x in txn.touched()} | {uid(t) for t in txn.dele}
    if not touched:
        return False
    for c in ch:
        if c[0] in ("seg", "del", "via"):
            u = uid(c[1])
            if u in touched:
                return True
            w = ctx.where.get(u)
            if w is not None and any(uid(t) in touched for t in ctx.chains[w[0]][3]):
                return True
    return False


def touches_anchor(ctx, ch):
    """True when a change list cannot keep every mid-segment connection (see follow_anchors)."""
    return follow_anchors(ctx, ch) is None


def try_plan(ctx, label, ch, push=True):
    """Apply one change list; if it collides only with movable vias / tracks of other nets, push
    those out of the way (at most 3). Commits and returns a description, or rolls back (None)."""
    ch = follow_anchors(ctx, ch)
    if ch is None:
        return None
    txn = Txn(ctx)
    txn.apply(ch)
    bad = txn.conflicts()
    if not bad:
        if not fewer_jogs(ctx, txn):
            txn.rollback()
            return None
        LAST_TOUCHED[:] = [uid(i) for i in txn.touched()]
        txn.commit()
        return label
    if not push:
        txn.rollback()
        return None

    def pushable(e):
        return not (e is None or isinstance(e, tuple) and e[0] == "hole" or e[6] not in ("via", "track")
                    or not ctx.movable(e[7]))
    if not all(pushable(e) for it, e in bad) or len({e[5] for it, e in bad}) > 4:
        txn.rollback()
        return None
    names = []
    for _ in range(5):
        bad = txn.conflicts()
        if not bad:
            break
        it, e = bad[0]
        if not pushable(e):
            txn.rollback()
            return None
        # push away from the changed item it collides with
        if it.GetClass() == "PCB_VIA":
            q = pt(it.GetPosition())
        else:
            s = pcbnew.SEG(it.GetStart(), it.GetEnd())
            c = entry_center(e)
            q = pt(s.NearestPoint(V(c)))
        toward = sub(entry_center(e), q)
        if not clear_blocker(ctx, txn, e, toward):
            txn.rollback()
            return None
        names.append("%s %s" % (e[6], e[7].GetNetname()))
    if txn.conflicts(first=True) or not fewer_jogs(ctx, txn):
        txn.rollback()
        return None
    LAST_TOUCHED[:] = [uid(i) for i in txn.touched()]
    txn.commit()
    return label + (" (moved %s)" % ", ".join(names) if names else "")


def fewer_jogs(ctx, txn):
    """True when the nets a transaction touches have fewer jogs than before (deleted tracks are
    still on the board until commit: they are left out of the count)."""
    nets = {it.GetNetCode() for it in txn.touched()} | {t.GetNetCode() for t in txn.dele}
    gone = {uid(t) for t in txn.dele}
    before = sum(count_jogs(c[2]) for c in ctx.chains if c[0] in nets)
    after = 0
    for net, layer, pts, ts in chains(ctx.board, nets, exclude=gone):
        after += count_jogs(pts)
    return after < before


LAST_TOUCHED = []                           # uuids of the items the last committed fix changed


# ------------------------------------------------------------------------------ local re-route
RGRID = MM(0.05)                            # router grid pitch (adjusted per window, 0.033-0.067 mm)
TIGHT = MM(0.1)                             # nodes this much closer than needed to copper cost more
STEP8 = [(1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1), (0, -1), (1, -1)]
SQ2 = math.sqrt(2)
WIN_CORRIDORS = (1.0, 2.5, 4.0)             # mm around the old path
WIN_SLACK = MM(2.5)                         # extra length a re-routed window may take


def chain_len(P):
    return sum(norm(sub(P[i + 1], P[i])) for i in range(len(P) - 1))


def oct_index(d):
    """Index in STEP8 of an octilinear unit direction, or None."""
    for k, (sx, sy) in enumerate(STEP8):
        n = math.hypot(sx, sy)
        if abs(d[0] - sx / n) < 1e-4 and abs(d[1] - sy / n) < 1e-4:
            return k
    return None


def fill_poly(mask, pts, W, H):
    """Set mask nodes whose centre is inside polygon pts (node coordinates), even-odd rule."""
    import numpy as np
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    i0, i1 = max(0, int(math.floor(min(xs)))), min(W - 1, int(math.ceil(max(xs))))
    j0, j1 = max(0, int(math.floor(min(ys)))), min(H - 1, int(math.ceil(max(ys))))
    if i0 > i1 or j0 > j1:
        return
    I, J = np.meshgrid(np.arange(i0, i1 + 1, dtype=float), np.arange(j0, j1 + 1, dtype=float))
    inside = np.zeros(I.shape, dtype=bool)
    n = len(pts)
    for k in range(n):
        x1, y1 = pts[k]
        x2, y2 = pts[k - 1]
        if y1 == y2:
            continue
        cond = (y1 > J) != (y2 > J)
        xint = (x2 - x1) * (J - y1) / (y2 - y1) + x1
        inside ^= cond & (I < xint)
    mask[j0:j1 + 1, i0:i1 + 1] |= inside


def route_window(ctx, ci, a, b, corridor=1.5, bend45=MM(0.8), bend90=MM(2.5), slack=None):
    """Re-route segments a .. b-1 of chain ci (nodes P[a] .. P[b]) with an octilinear A* search.
    The new path leaves the kept segment before the window (a > 0) anywhere along it, in its own
    direction, and joins the line of the kept segment after it (b < n) anywhere along that line
    (exact: the grid pitch is chosen so that line runs through grid nodes), or ends in the end pad
    / at the end via or branch point. Cost: length, a penalty per 45 / 90 deg turn (nothing
    sharper), and 50 % extra per step closer than 0.1 mm beyond the clearance to other copper.
    Returns (new chain points, width) or None."""
    import heapq
    import numpy as np
    slack = WIN_SLACK if slack is None else slack
    net, layer, P, T = ctx.chains[ci]
    n = len(T)
    win = T[max(a - 1, 0):min(b + 1, n)]
    w = max(t.GetWidth() for t in T[a:b])
    if len({t.GetWidth() for t in win}) > 1 and ctx.board.FindNet(net).GetNetname() in D.POWER_NETS:
        return None
    # grid origin: P[a] (on the kept segment before the window) or the start stop
    org = P[a]
    ds = unit(sub(P[a], P[a - 1])) if a > 0 else None
    dsi = oct_index(ds) if ds else None
    if a > 0 and dsi is None:
        return None
    dg = unit(sub(P[b + 1], P[b])) if b < n else None
    dgi = oct_index(dg) if dg else None
    if b < n and dgi is None:
        return None
    g = RGRID
    if b < n:
        dx, dy = P[b][0] - org[0], P[b][1] - org[1]
        # lattice offset of the goal line: horizontal -> dy, vertical -> dx, diagonals -> dx -+ dy
        delta = {0: dy, 4: dy, 2: dx, 6: dx, 1: dx - dy, 5: dx - dy, 3: dx + dy, 7: dx + dy}[dgi]
        k = round(abs(delta) / RGRID)
        if abs(delta) < UM:
            pass
        elif k == 0:
            if abs(delta) < MM(0.03):
                return None
            g = abs(delta)
        else:
            g = abs(delta) / k
    Rr = MM(corridor)
    pts_old = P[max(a - 1, 0):min(b + 2, n + 1)]
    x0 = min(p[0] for p in pts_old) - Rr
    y0 = min(p[1] for p in pts_old) - Rr
    x1 = max(p[0] for p in pts_old) + Rr
    y1 = max(p[1] for p in pts_old) + Rr
    i0, j0 = int(math.ceil((org[0] - x0) / g)), int(math.ceil((org[1] - y0) / g))
    ox, oy = org[0] - i0 * g, org[1] - j0 * g
    W, H = int((x1 - ox) / g) + 2, int((y1 - oy) / g) + 2
    if W * H > 1_500_000:
        return None

    def nd(p):
        return ((p[0] - ox) / g, (p[1] - oy) / g)

    def node_pt(i, j):
        return (ox + i * g, oy + j * g)
    jj, ii = np.mgrid[0:H, 0:W]
    # corridor: nodes within Rr of the old path (window plus its neighbouring segments)
    inside = np.zeros((H, W), dtype=bool)
    for p, q in zip(pts_old, pts_old[1:]):
        (px_, py_), (qx, qy) = nd(p), nd(q)
        vx, vy = qx - px_, qy - py_
        L2 = vx * vx + vy * vy or 1.0
        t = np.clip(((ii - px_) * vx + (jj - py_) * vy) / L2, 0, 1)
        dxm, dym = ii - (px_ + t * vx), jj - (py_ + t * vy)
        inside |= dxm * dxm + dym * dym <= (Rr / g) ** 2
    blocked = np.zeros((H, W), dtype=bool)
    tight = np.zeros((H, W), dtype=bool)
    own = ctx.obs.net_clearance(net)
    mine = {uid(t) for t in T}
    for e in ctx.obs.near(layer, x0, y0, x1, y1):
        enet, s, clr, u = e[1], e[2], e[4], e[5]
        if (enet == net and enet >= 0) or u in mine:
            continue
        need = w / 2 + (clr if enet < 0 else max(own, clr))
        for mask, extra in ((blocked, 0), (tight, TIGHT)):
            s2 = pcbnew.SHAPE_POLY_SET(s)
            s2.Inflate(int(need + extra), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
            for kk in range(s2.OutlineCount()):
                o = s2.Outline(kk)
                fill_poly(mask, [nd((o.CPoint(m).x, o.CPoint(m).y)) for m in range(o.PointCount())], W, H)
    lo = MM(EDGE) + w / 2
    bx0, by0 = nd((MM(OX) + lo, MM(OY) + lo))
    bx1, by1 = nd((MM(OX + D.BOARD_W) - lo, MM(OY + D.BOARD_H) - lo))
    free = inside & ~blocked & (ii >= bx0) & (ii <= bx1) & (jj >= by0) & (jj <= by1)
    # sources: start stop (any direction) or nodes on the kept segment before the window
    sources = []
    if a == 0:
        sources.append((i0, j0, -1, 0.0))
    else:
        sx, sy = STEP8[dsi]
        stp = g * (SQ2 if dsi % 2 else 1.0)
        kmax = int((norm(sub(P[a], P[a - 1])) - MINLEN) / stp)
        for kk in range(0, kmax + 1):
            i, j = i0 - kk * sx, j0 - kk * sy
            if not (0 <= i < W and 0 <= j < H) or not free[j, i]:
                break
            sources.append((i, j, dsi, -kk * stp))
    if not sources:
        return None
    # goal
    goal = np.zeros((H, W), dtype=bool)
    end_kind = None
    if b < n:
        gx, gy = STEP8[dgi]
        stp = g * (SQ2 if dgi % 2 else 1.0)
        bi, bj = nd(P[b])
        bi, bj = int(round(bi)), int(round(bj))
        lb = norm(sub(P[b + 1], P[b]))
        for kk in range(-int(MM(3.0) / stp), int((lb - MINLEN) / stp) + 1):
            i, j = bi + kk * gx, bj + kk * gy
            if 0 <= i < W and 0 <= j < H:
                goal[j, i] = True
        end_kind = "line"
    else:
        E = P[n]
        pd = pad_at(ctx.board, net, layer, E)
        if pd is not None and via_at(ctx.board, net, E) is None:
            s = pcbnew.SHAPE_POLY_SET()
            pd.TransformShapeToPolygon(s, layer, 0, MAXERR, pcbnew.ERROR_INSIDE)
            s.Deflate(MM(0.05), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
            for kk in range(s.OutlineCount()):
                o = s.Outline(kk)
                fill_poly(goal, [nd((o.CPoint(m).x, o.CPoint(m).y)) for m in range(o.PointCount())], W, H)
            end_kind = ("pad", pd)
        else:
            ce = nd(E)
            for j in range(int(ce[1]) - 1, int(ce[1]) + 3):
                for i in range(int(ce[0]) - 1, int(ce[0]) + 3):
                    if 0 <= i < W and 0 <= j < H and math.hypot(i - ce[0], j - ce[1]) * g <= MM(0.03):
                        goal[j, i] = True
            end_kind = "point"
    goal &= free
    if os.environ.get("D32_ROUTE_DEBUG"):
        from PIL import Image
        dbg = np.zeros((H, W, 3), dtype=np.uint8)
        dbg[free] = (255, 255, 255)
        dbg[free & tight] = (200, 200, 255)
        dbg[goal] = (0, 200, 0)
        for i, j, _, _ in sources:
            dbg[j, i] = (255, 0, 0)
        Image.fromarray(dbg).save(os.environ["D32_ROUTE_DEBUG"])
    if not goal.any():
        return None
    target = P[b] if b < n else P[n]
    ge = nd(target)
    diag = g * SQ2

    def h(i, j):
        dx, dy = abs(i - ge[0]), abs(j - ge[1])
        return ((max(dx, dy) - min(dx, dy)) * g + min(dx, dy) * diag) * 0.999
    old_len = chain_len(P[max(a - 1, 0):min(b + 2, n + 1)])
    best, prev = {}, {}
    heap = []
    for i, j, dd, c0 in sources:
        best[(i, j, dd)] = c0
        prev[(i, j, dd)] = None
        heapq.heappush(heap, (c0 + h(i, j), c0, i, j, dd))
    found = None
    budget = old_len + slack + 4 * bend90
    while heap:
        f, cst, i, j, dd = heapq.heappop(heap)
        if best.get((i, j, dd), 1e30) < cst:
            continue
        if goal[j, i] and dd >= 0:
            ok = True
            if end_kind == "line":
                turn = (dgi - dd) % 8
                ok = turn in (0, 1, 7)
            if ok and prev[(i, j, dd)] is not None:
                found = (i, j, dd)
                break
        if f > budget:
            break
        for ndir in range(8):
            if dd >= 0:
                turn = (ndir - dd) % 8
                if turn in (3, 4, 5):
                    continue
                pen = 0 if turn == 0 else bend45 if turn in (1, 7) else bend90
            else:
                pen = 0
            di, dj = STEP8[ndir]
            ni, nj = i + di, j + dj
            if not (0 <= ni < W and 0 <= nj < H) or not free[nj, ni]:
                continue
            step = diag if ndir % 2 else g
            if tight[nj, ni]:
                step *= 1.5
            nc = cst + step + pen
            k2 = (ni, nj, ndir)
            if nc < best.get(k2, 1e30):
                best[k2] = nc
                prev[k2] = (i, j, dd)
                heapq.heappush(heap, (nc + h(ni, nj), nc, ni, nj, ndir))
    if found is None:
        return None
    nodes = []
    k = found
    while k is not None:
        nodes.append(k)
        k = prev[k]
    nodes.reverse()
    # polyline: vertices where the direction changes (incoming direction of the source counts)
    dirs = [nodes[0][2]] + [nodes[m][2] for m in range(1, len(nodes))]
    verts = [node_pt(nodes[0][0], nodes[0][1])]
    for m in range(1, len(nodes) - 1):
        if dirs[m] != dirs[m + 1]:
            verts.append(node_pt(nodes[m][0], nodes[m][1]))
    last = node_pt(nodes[-1][0], nodes[-1][1])
    if a == 0:
        verts[0] = P[0]
    if end_kind == "line":
        verts.append(last)                      # on segment b's line (collinear vertices go below)
        newP = list(P[:a]) + verts + list(P[b + 1:])
    else:
        if end_kind == "point":
            last = P[n]
        else:
            pd = end_kind[1]
            dl = unit(sub(last, verts[-1]))
            q = proj(P[n], verts[-1], dl)
            if dot(sub(q, verts[-1]), dl) > MINLEN and inside_pad(pd, layer, q, MM(0.05)):
                last = q
        verts.append(last)
        newP = list(P[:a]) + verts
    # clean: drop repeated points and collinear interior vertices
    clean = [newP[0]]
    for p in newP[1:]:
        if norm(sub(p, clean[-1])) > UM:
            clean.append(p)
    m = 1
    while m < len(clean) - 1:
        d1, d2 = unit(sub(clean[m], clean[m - 1])), unit(sub(clean[m + 1], clean[m]))
        if dot(d1, d2) > 0.99999:
            del clean[m]
        else:
            m += 1
    return clean, w


def chain_turns_ok(P):
    for m in range(1, len(P) - 1):
        d1, d2 = unit(sub(P[m], P[m - 1])), unit(sub(P[m + 1], P[m]))
        if dot(d1, d2) < -1e-3:
            return False
    return True


def try_window(ctx, ci, j, log=print):
    """Re-route a window around the jog at j (growing windows, then the whole chain); accepted
    when the chain then has fewer jogs, no turn sharper than 90 deg, no new segment shorter than
    0.05 mm, at most 1.5 mm more length, and every new segment passes the exact clearance check."""
    net, layer, P, T = ctx.chains[ci]
    n = len(T)
    if T[0].GetNetname() in SKIP_NETS or any(uid(t) in ctx.fixed for t in T):
        return None
    njog = count_jogs(P)
    wins = []
    for a, b in ((j, j + 3), (j - 1, j + 3), (j, j + 4), (j - 1, j + 4), (j - 2, j + 5), (j - 3, j + 6), (0, n)):
        a, b = max(a, 0), min(b, n)
        if (a, b) not in wins:
            wins.append((a, b))
    for a, b in wins:
        for corridor in WIN_CORRIDORS:
            r = route_window(ctx, ci, a, b, corridor)
            if r is None:
                continue
            newP, w = r
            if count_jogs(newP) >= njog or not chain_turns_ok(newP):
                continue
            if chain_len(newP) > chain_len(P) + WIN_SLACK:
                continue
            if any(norm(sub(newP[m + 1], newP[m])) < MINLEN for m in range(len(newP) - 1)):
                continue
            mine = {uid(t) for t in T}
            # widths: keep each old segment's width where the point list is unchanged, else w
            oldseg = {(key(P[m]), key(P[m + 1])): T[m] for m in range(n)}
            segs = []
            for m in range(len(newP) - 1):
                t = oldseg.get((key(newP[m]), key(newP[m + 1])))
                segs.append((newP[m], newP[m + 1], t.GetWidth() if t is not None else w, t))
            keep = {uid(t) for p, q, ww, t in segs if t is not None}
            if any(ctx.obs.seg_conflicts(p, q, ww, layer, net, mine, first=True) for p, q, ww, t in segs if t is None):
                continue
            # as a change list (new segments added, old ones deleted), so tracks ending on the old
            # path follow onto the new one (follow_anchors) and everything is checked once more
            ch = [("add", net, layer, ww, p, q) for p, q, ww, t in segs if t is None]
            ch += [("del", t) for t in T if uid(t) not in keep]
            ch = follow_anchors(ctx, ch)
            if ch is None:
                continue
            txn = Txn(ctx)
            txn.apply(ch)
            if txn.conflicts(first=True):
                txn.rollback()
                continue
            LAST_TOUCHED[:] = [uid(i) for i in txn.touched()]
            txn.commit()
            return "re-route window %d-%d (%d -> %d jogs)" % (a, b, njog, count_jogs(newP))
    return None


def merge_collinear(board, obs=None):
    """Join consecutive collinear segments of one width at points that are not stops (keeping the
    obstacle index obs up to date)."""
    n = 0
    for _ in range(10):
        dead = []
        for net, layer, pts, ts in chains(board):
            i = 0
            while i < len(ts) - 1:
                k = i
                while k + 1 < len(ts) and ts[k + 1].GetWidth() == ts[i].GetWidth():
                    d1, d2 = unit(sub(pts[i + 1], pts[i])), unit(sub(pts[k + 2], pts[k + 1]))
                    if dot(d1, d2) > 0.99999 and abs(cross(sub(pts[k + 2], pts[i]), d1)) < 2 * UM:
                        k += 1
                    else:
                        break
                if k > i:
                    if obs is not None:
                        obs.remove_track(ts[i])
                    ts[i].SetStart(V(pts[i]))
                    ts[i].SetEnd(V(pts[k + 1]))
                    if obs is not None:
                        obs.add_track(ts[i])
                    dead += ts[i + 1:k + 1]
                i = k + 1
        for t in dead:
            if obs is not None:
                obs.remove_track(t)
            board.Delete(t)
        n += len(dead)
        if not dead:
            break
        del dead
    return n


CHAMFERS = (1.0, 0.8, 0.6, 0.5, 0.4, 0.3, 0.25, 0.2, 0.15, 0.1, 0.07)   # mm, corner cut-back tried in order


def right_angles(ctx):
    """[(chain index, point index)] of 90 deg corners (both legs > 0.05 mm, as pcb_audit.py)."""
    out = []
    for ci, (net, layer, pts, ts) in enumerate(ctx.chains):
        for i in range(1, len(pts) - 1):
            d1, d2 = sub(pts[i], pts[i - 1]), sub(pts[i + 1], pts[i])
            if norm(d1) > MM(0.05) and norm(d2) > MM(0.05) and abs(dot(unit(d1), unit(d2))) < 1e-3:
                out.append((ci, i))
    return out


def chamfer_pass(board, skip=(), log=print):
    """Every 90 deg corner becomes two 45 deg bends: the corner point is cut back along both legs
    by the largest of CHAMFERS that leaves each leg >= MINLEN, keeps every clearance and every
    mid-segment connection (follow_anchors) and adds no jog. Pre-routes and the USB pair stay.
    Returns (fixed [(net, layer, at, cut mm, how, uuids)], left [(net, layer, at)])."""
    fixed = []
    ctx = Ctx(board)
    tried = set()
    while True:
        cand = None
        for ci, i in right_angles(ctx):
            net, layer, pts, ts = ctx.chains[ci]
            tag = (ts[0].GetNetname(), board.GetLayerName(layer), bmm(pts[i]))
            if tag in tried or tag in skip:
                continue
            cand = (ci, i, tag)
            break
        if cand is None:
            break
        ci, i, tag = cand
        tried.add(tag)
        net, layer, pts, ts = ctx.chains[ci]
        ta, tb = ts[i - 1], ts[i]
        if tag[0] in SKIP_NETS or not (ctx.movable(ta) and ctx.movable(tb)):
            continue
        a, c, b = pts[i - 1], pts[i], pts[i + 1]
        ua, ub = unit(sub(c, a)), unit(sub(b, c))
        room = min(norm(sub(c, a)), norm(sub(b, c))) - MINLEN
        w = min(ta.GetWidth(), tb.GetWidth())
        before = sum(count_jogs(c2[2]) for c2 in ctx.chains if c2[0] == net)
        done = None

        def segto(t, p_old, q_old, p_new, q_new):
            """Change track t (joining p_old, q_old) to join p_new, q_new, keeping its orientation."""
            return ("seg", t, p_new, q_new) if key(pt(t.GetStart())) == key(p_old) else ("seg", t, q_new, p_new)
        ud = unit(add(ua, ub))
        la, lb = norm(sub(c, a)), norm(sub(b, c))
        plans = []
        # the leg after the corner is followed by a 45 deg segment in the chamfer's direction: the
        # chamfer runs into it and the leg goes (a plain chamfer would leave a jog: 45, short leg, 45)
        if i + 1 < len(ts) and dot(unit(sub(pts[i + 2], pts[i + 1])), ud) > 0.9999 and la - lb >= MINLEN:
            c1 = sub(c, mul(ua, lb))
            plans.append((TOMM(int(lb)), [segto(ta, a, c, a, c1), ("del", tb), segto(ts[i + 1], b, pts[i + 2], c1, pts[i + 2])]))
        if i >= 2 and dot(unit(sub(pts[i - 1], pts[i - 2])), ud) > 0.9999 and lb - la >= MINLEN:
            c2 = add(c, mul(ub, la))
            plans.append((TOMM(int(la)), [("del", ta), segto(tb, c, b, c2, b), segto(ts[i - 2], pts[i - 2], a, pts[i - 2], c2)]))
        for k in CHAMFERS:
            k = MM(k)
            if k > room:
                continue
            c1, c2 = sub(c, mul(ua, k)), add(c, mul(ub, k))
            ka = ("seg", ta, a, c1) if key(pt(ta.GetStart())) == key(a) else ("seg", ta, c1, a)
            kb = ("seg", tb, c2, b) if key(pt(tb.GetEnd())) == key(b) else ("seg", tb, b, c2)
            plans.append((TOMM(int(k)), [ka, kb, ("add", net, layer, w, c1, c2)]))
        # a T-junction right at the corner (a branch U ends there): the chamfer is drawn and U's end
        # slides along U onto it (follow_anchors cannot, the corner point itself goes)
        tees = {}
        other_anchor = False
        for t_ in (ta, tb):
            for a_ in ctx.anchors.get(uid(t_), []):
                if a_[0] in ("tee", "onto") and uid(a_[1]) not in (uid(ta), uid(tb)):
                    tees[uid(a_[1])] = a_[1]
                else:
                    other_anchor = True
        special = []
        if tees and not other_anchor and all(uid(U) not in ctx.fixed for U in tees.values()):
            # every plan (merges and plain chamfers) once more with each branch U's end slid along
            # U onto the nearest new segment of the plan
            for kmm0, raw0 in plans:
                segs_new = [(c_[2], c_[3]) for c_ in raw0 if c_[0] == "seg"] + [(c_[4], c_[5]) for c_ in raw0 if c_[0] == "add"]
                raw = list(raw0)
                ok_ = True
                for U in tees.values():
                    s0, s1 = pt(U.GetStart()), pt(U.GetEnd())
                    if norm(sub(s0, c)) < U.GetWidth():
                        e_, o_, first = s0, s1, True
                    elif norm(sub(s1, c)) < U.GetWidth():
                        e_, o_, first = s1, s0, False
                    else:
                        ok_ = False
                        break
                    dU = unit(sub(e_, o_))
                    best_x = None
                    for p_, q_ in segs_new:
                        if norm(sub(q_, p_)) < UM:
                            continue
                        dd2 = unit(sub(q_, p_))
                        X = intersect(o_, dU, p_, dd2)
                        if X is None or not (0 <= dot(sub(X, p_), dd2) <= norm(sub(q_, p_))) or dot(sub(X, o_), dU) < MINLEN:
                            continue
                        if best_x is None or norm(sub(X, e_)) < norm(sub(best_x, e_)):
                            best_x = X
                    if best_x is None or norm(sub(best_x, e_)) > MM(1.0):
                        ok_ = False
                        break
                    raw.append(("seg", U, best_x, o_) if first else ("seg", U, o_, best_x))
                if ok_:
                    special.append((kmm0, raw))
        cdbg = (lambda m: log("    corner %s %s: %s" % (tag[0], tag[2], m))) if os.environ.get("D32_CHAMFER_DEBUG") else (lambda m: None)
        cdbg("%d T-junction plans, %d plans, tees %d other %s" % (len(special), len(plans), len(tees), other_anchor))
        for kmm, raw in special + plans:
            k = MM(kmm)
            sp = any(r_ is raw for k_, r_ in special)
            ch = raw if sp else follow_anchors(ctx, raw)
            if ch is None:
                cdbg("k %.2f anchors %s" % (kmm, FA_FAIL))
                continue                            # a connection sits on the cut-off part
            txn = Txn(ctx)
            txn.apply(ch)
            bad = txn.conflicts(first=True)
            if bad:
                cdbg("k %.2f%s conflict %s" % (kmm, " T" if sp else "", [describe(e) for it, e in bad]))
                txn.rollback()
                continue
            if sum(count_jogs(c3[2]) for c3 in chains(board, {net}, exclude={uid(t) for t in txn.dele})) > before:
                cdbg("k %.2f%s more jogs" % (kmm, " T" if sp else ""))
                txn.rollback()
                continue
            if sp:
                dd_ = drc_check(board, drop={uid(t) for t in txn.dele})
                if dd_:
                    cdbg("k %.2f T drc %s" % (kmm, [x[:2] for x in dd_[:2]]))
                    txn.rollback()                  # KiCad checks the T-junction slide
                    continue
            LAST_TOUCHED[:] = [uid(x) for x in txn.touched()]
            txn.commit()
            done = TOMM(int(k))
            break
        how = "45 deg chamfer"
        if done is None and tees and not other_anchor:
            # the "corner" is really a T-junction whose branch ends a few um off the vertex: weld
            # the branch onto the vertex (moved parallel when its far end stays in its pad / via),
            # so the junction is one point (a stop) and no corner is left
            for U in tees.values():
                s0, s1 = pt(U.GetStart()), pt(U.GetEnd())
                first = norm(sub(s0, c)) <= norm(sub(s1, c))
                e_, o_ = (s0, s1) if first else (s1, s0)
                dlt = sub(c, e_)
                if norm(dlt) > MM(0.1) or norm(dlt) < 1:
                    continue
                far = stop_item(ctx, net, layer, o_, {uid(U)})
                o2 = add(o_, dlt) if far is not None and far.GetClass() in ("PAD", "PCB_VIA") and \
                    far.HitTest(V(add(o_, dlt))) else o_
                txn = Txn(ctx)
                txn.apply([("seg", U, c, o2) if first else ("seg", U, o2, c)])
                if txn.conflicts(first=True) or drc_check(board):
                    txn.rollback()
                    continue
                txn.commit()
                done, how = 0.0, "T-junction welded onto the vertex"
                break
        if done is None:
            # re-route the run (from the stop before to the stop after) with 90 deg turns barred
            n = len(ts)
            for a0, b0 in ((max(i - 2, 0), min(i + 2, n)), (0, n)):
                for corridor in (1.0, 2.5):
                    r = route_window(ctx, ci, a0, b0, corridor, bend90=MM(1000.0))
                    if r is None:
                        continue
                    newP, w2 = r
                    if not chain_turns_ok(newP) or any(abs(dot(unit(sub(newP[m], newP[m - 1])), unit(sub(newP[m + 1], newP[m])))) < 1e-3
                                                       for m in range(1, len(newP) - 1)):
                        continue
                    if count_jogs(newP) > count_jogs(pts) or chain_len(newP) > chain_len(pts) + WIN_SLACK:
                        continue
                    if any(norm(sub(newP[m + 1], newP[m])) < MINLEN for m in range(len(newP) - 1)):
                        continue
                    oldseg = {(key(pts[m]), key(pts[m + 1])): ts[m] for m in range(n)}
                    segs = [(newP[m], newP[m + 1], oldseg.get((key(newP[m]), key(newP[m + 1])))) for m in range(len(newP) - 1)]
                    keep = {uid(t) for p_, q_, t in segs if t is not None}
                    ch = [("add", net, layer, w2, p_, q_) for p_, q_, t in segs if t is None]
                    ch += [("del", t) for t in ts if uid(t) not in keep]
                    ch = follow_anchors(ctx, ch)
                    if ch is None:
                        continue
                    txn = Txn(ctx)
                    txn.apply(ch)
                    if txn.conflicts(first=True):
                        txn.rollback()
                        continue
                    LAST_TOUCHED[:] = [uid(x) for x in txn.touched()]
                    txn.commit()
                    done, how = 0.0, "re-routed without the 90 deg turn"
                    break
                if done is not None:
                    break
        if done is None:
            continue
        fixed.append(tag + (round(done, 2), how, list(LAST_TOUCHED)))
        ctx.refresh()
    left = []
    for ci, i in right_angles(ctx):
        net, layer, pts, ts = ctx.chains[ci]
        left.append((ts[0].GetNetname(), board.GetLayerName(layer), bmm(pts[i])))
    return fixed, left


def stop_item(ctx, net, layer, p, mine):
    """The item a chain end at p connects to: a pad or via of the net there, else a track of the
    net (not in the chain) whose copper holds p (a T-junction or branch point)."""
    pd = pad_at(ctx.board, net, layer, p)
    if pd is not None:
        return pd
    v = via_at(ctx.board, net, p)
    if v is not None:
        return v
    for t in ctx.board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == net and t.GetLayer() == layer and uid(t) not in mine \
                and pcbnew.SEG(t.GetStart(), t.GetEnd()).Distance(V(p)) < t.GetWidth() / 2:
            return t
    return None


def snap_end(P, item, at_start):
    """A maze path ends anywhere inside its end item; when that item is a track, run the end
    segment on (along its own direction) to the track's centre line, so the joint is a clean
    T-junction (KiCad and follow_anchors both see the end on the track). Returns the points."""
    if item is None or item.GetClass() != "PCB_TRACK" or len(P) < 2:
        return P
    P = list(P)
    e, n = (P[0], P[1]) if at_start else (P[-1], P[-2])
    a, b = pt(item.GetStart()), pt(item.GetEnd())
    d = unit(sub(e, n))
    X = intersect(n, d, a, unit(sub(b, a)))
    if X is None:
        X = proj(e, a, unit(sub(b, a)))            # parallel: slide onto the line
    t = dot(sub(X, a), unit(sub(b, a)))
    if not (0 <= t <= norm(sub(b, a))) or norm(sub(X, e)) > MM(0.3) or dot(sub(X, n), d) < MINLEN:
        return P
    if at_start:
        P[0] = X
    else:
        P[-1] = X
    return P


def maze_jogs(board, skip=(), log=print, rounds=4):
    """Jogs the local moves and the corridor router could not fix: the whole run (from its stop to
    its stop) is ripped up and re-routed with route_prep's maze search in jog-free mode (no turn
    back to the heading before a 45 deg run shorter than 2.2 mm), anywhere within 6 / 12 mm, 45 deg
    bends 1 mm dearer than going straight, no 90 deg turn: on the run's own layer, else (not for
    the fast nets) on both outer layers with at most two vias. Kept when the net then has fewer
    jogs, no turn sharper than 90 deg, at most 20 % (2 mm at least, 4 mm with vias) more length,
    every clearance (checked again on the change list) and every connection. Repeated while it
    helps. Returns fixed [(net, layer, at, offset, how, uuids)]."""
    fixed = []
    for _ in range(rounds):
        n0 = len(fixed)
        _maze_jogs_round(board, skip, log, fixed)
        if len(fixed) == n0:
            break
    return fixed


def chain_corners(P):
    return sum(1 for m in range(1, len(P) - 1)
               if norm(sub(P[m], P[m - 1])) > MM(0.05) and norm(sub(P[m + 1], P[m])) > MM(0.05)
               and abs(dot(unit(sub(P[m], P[m - 1])), unit(sub(P[m + 1], P[m])))) < 1e-3)


def fewer_defects(ctx, txn):
    """Like fewer_jogs, counting 90 deg corners too."""
    nets = {it.GetNetCode() for it in txn.touched()} | {t.GetNetCode() for t in txn.dele}
    gone = {uid(t) for t in txn.dele}
    before = sum(count_jogs(c[2]) + chain_corners(c[2]) for c in ctx.chains if c[0] in nets)
    after = sum(count_jogs(P) + chain_corners(P) for net, layer, P, ts in chains(ctx.board, nets, exclude=gone))
    return after < before


def maze_corners(board, skip=(), log=print):
    """90 deg corners the chamfer could not cut (a T-junction sits on them): the run is re-routed
    like a jogged one (maze_jogs), kept when the net then has fewer jogs + corners."""
    fixed = []
    _maze_jogs_round(board, skip, log, fixed, corners=True)
    return fixed


def _maze_jogs_round(board, skip, log, fixed, corners=False):
    base = len(drc_check(board))                 # problems already there (none expected)
    tried = set()
    ctx = Ctx(board)
    fewer = fewer_defects if corners else fewer_jogs
    while True:
        cand = None
        for ci, (net, layer, pts, ts) in enumerate(ctx.chains):
            name = ts[0].GetNetname()
            if name in SKIP_NETS or any(uid(t) in ctx.fixed for t in ts):
                continue
            spots = [(m - 1, 0.0) for c2, m in right_angles(ctx) if c2 == ci] if corners else find_jogs(pts)
            for j, off in spots:
                tag = (name, board.GetLayerName(layer), bmm(pts[j + 1]))
                if tag in skip or tag in tried:
                    continue
                cand = (ci, j, off, tag)
                break
            if cand:
                break
        if cand is None:
            break
        ci, j, off, tag = cand
        tried.add(tag)
        net, layer, pts, ts = ctx.chains[ci]
        mine = {uid(t) for t in ts}
        dbg = (lambda why: log("    maze %s %s %s: %s" % (tag[0], tag[1], tag[2], why))) if os.environ.get("D32_MAZE_DEBUG") \
            else (lambda why: None)
        a_it = stop_item(ctx, net, layer, pts[0], mine)
        b_it = stop_item(ctx, net, layer, pts[-1], mine)
        if a_it is None or b_it is None:
            dbg("no end item")
            continue
        w = max(t.GetWidth() for t in ts)
        before = sum(count_jogs(c[2]) for c in ctx.chains if c[0] == net)
        old_len = chain_len(pts)
        res = None
        for margin in (6.0, 12.0):
            res = R.maze_route(board, ts[0].GetNetname(), a_it, b_it, margin, 0.05, b45=MM(1.0), b90=None,
                               layers=[layer], width=w, nojog=True)
            if res:
                break
        two = False
        if not res:
            # the other outer layer for part of the way (both planes are GND, so the reference
            # stays; return_vias adds a GND via next to a fast net's new vias)
            for margin in (6.0, 12.0):
                res = R.maze_route(board, ts[0].GetNetname(), a_it, b_it, margin, 0.05, b45=MM(1.0), b90=None,
                                   width=w, nojog=True, via_cost=MM(4.0))
                if res:
                    break
            two = bool(res) and 0 < len(res[1]) <= 2
            if res and not two and res[1]:
                res = None
        if not res or (res[1] and not two) or (not two and len(res[0]) != 1):
            dbg("no path")
            continue
        runs = [list(r) for r in res[0]]
        runs[0][1] = snap_end(runs[0][1], a_it, True)
        runs[-1][1] = snap_end(runs[-1][1], b_it, False)
        if any(not chain_turns_ok(P_) or count_jogs(P_) > 0 for L_, P_ in runs) or \
                (not two and not corners and count_jogs(runs[0][1]) >= count_jogs(pts)):
            dbg("path has jogs")
            continue
        newlen = sum(chain_len(P_) for L_, P_ in runs)
        if newlen > max(old_len * 1.2, old_len + (MM(4.0) if two else MM(2.0))):
            dbg("too long %.1f > %.1f" % (TOMM(int(newlen)), TOMM(int(old_len))))
            continue
        new = [("add", net, L_, w, P_[m], P_[m + 1]) for L_, P_ in runs for m in range(len(P_) - 1)]
        new += [("addvia", net, q) for q in res[1]]
        ch = follow_anchors(ctx, new + [("del", t) for t in ts])
        branches = []
        if ch is None:
            # tracks that end on the run (T-junctions): their runs go too and are routed again from
            # their far stop to the new run (jog-free as well)
            tees = {uid(a[1]): a[1] for t in ts for a in ctx.anchors.get(uid(t), []) if a[0] == "tee"}
            bch = []
            for u, U in tees.items():
                w2 = ctx.where.get(u)
                if w2 is None:
                    bch = None
                    break
                bnet, blayer, bP, bT = ctx.chains[w2[0]]
                if any(uid(x) in ctx.fixed for x in bT) or w2[0] == ci:
                    bch = None
                    break
                # the far end of the branch: the end that is not on the run
                far = bP[-1] if min(dist_point_seg(bP[0], pts[m], pts[m + 1]) for m in range(len(pts) - 1)) < MM(0.01) else bP[0]
                fi = stop_item(ctx, net, blayer, far, {uid(x) for x in bT})
                if fi is None:
                    bch = None
                    break
                branches.append((blayer, bT, fi, chain_len(bP)))
            if bch is None or not branches:
                dbg("anchors %s" % FA_FAIL)
                continue
            ch = follow_anchors(ctx, new + [("del", t) for t in ts] + [("del", x) for bl, bT, fi, bl0 in branches for x in bT],
                                regone=True)
            if ch is None:
                dbg("anchors (with branches) %s" % FA_FAIL)
                continue
        txn = Txn(ctx)
        txn.apply(ch)
        ok = True
        for blayer, bT, fi, bl0 in branches:
            # route the branch from its far stop to the nearest new track of the run
            tgt = [x for x in txn.touched() if x.GetClass() == "PCB_TRACK" and x.GetLayer() == blayer and x.GetNetCode() == net]
            if not tgt:
                ok = False
                break
            fp_ = pt(fi.GetPosition())
            tgt.sort(key=lambda x: dist_point_seg(fp_, pt(x.GetStart()), pt(x.GetEnd())))
            br = R.maze_route(board, ts[0].GetNetname(), fi, tgt[0], 6.0, 0.05, b45=MM(1.0), b90=None,
                              layers=[blayer], width=bT[0].GetWidth(), nojog=True)
            if not br or br[1] or len(br[0]) != 1 or count_jogs(br[0][0][1]) or not chain_turns_ok(br[0][0][1]) \
                    or chain_len(br[0][0][1]) > max(bl0 * 1.5, bl0 + MM(3.0)):
                ok = False
                break
            BP = snap_end(snap_end(br[0][0][1], tgt[0], False), fi, True)
            txn.apply([("add", net, blayer, bT[0].GetWidth(), BP[m], BP[m + 1]) for m in range(len(BP) - 1)])
        if not ok:
            dbg("branch could not be re-routed")
            txn.rollback()
            continue
        bad = txn.conflicts(first=True)
        if not bad and fewer(ctx, txn):
            bad = [(None, d) for d in drc_check(board, drop={uid(t) for t in txn.dele})][base:base + 1]  # KiCad has the last word
        if bad or not fewer(ctx, txn):
            dbg("conflict %s" % (bad[:1],) if bad else "net jogs not fewer")
            txn.rollback()
            continue
        LAST_TOUCHED[:] = [uid(x) for x in txn.touched()]
        txn.commit()
        merge_collinear(board, ctx.obs)
        ctx.refresh()
        how = "maze re-route of the run" + (" over both outer layers (%d vias)" % len(res[1]) if two else "")
        fixed.append(tag + (round(TOMM(int(off)), 2), how, list(LAST_TOUCHED)))
        log("  jog %s %s at %s (%.2f mm): %s (%d -> %d jogs on the net)" % (
            tag[0], tag[1], tag[2], TOMM(int(off)), how, before, sum(count_jogs(c[2]) for c in ctx.chains if c[0] == net)))


def route_run(board, name, layer, a_it, b_it, w, old_len, ignore=()):
    """A jog-free maze path for one run: its own layer first, else both outer layers with at most
    two vias. Returns ([(layer, points)], [via points]) or None."""
    res = None
    for margin in (6.0, 12.0):
        res = R.maze_route(board, name, a_it, b_it, margin, 0.05, b45=MM(1.0), b90=None, layers=[layer], width=w,
                           nojog=True, ignore=ignore)
        if res:
            break
    if not res:
        for margin in (6.0, 12.0):
            res = R.maze_route(board, name, a_it, b_it, margin, 0.05, b45=MM(1.0), b90=None, width=w, nojog=True,
                               via_cost=MM(4.0), ignore=ignore)
            if res:
                break
        if res and len(res[1]) > 2:
            res = None
    if not res:
        return None
    runs = [list(r) for r in res[0]]
    runs[0][1] = snap_end(runs[0][1], a_it, True)
    runs[-1][1] = snap_end(runs[-1][1], b_it, False)
    if any(not chain_turns_ok(P_) or count_jogs(P_) for L_, P_ in runs):
        return None
    if sum(chain_len(P_) for L_, P_ in runs) > max(old_len * 1.25, old_len + MM(4.0)):
        return None
    return runs, res[1]


def ripup_jogs(board, skip=(), log=print, max_nbrs=4):
    """Jogs with no jog-free path as the board stands: the run and up to four runs of other nets
    beside it (same layer, within 1 mm, no mid-segment connections, not pre-routed, not the USB
    pair or GND) are ripped up; the jogged run is routed first (route_run), then each ripped run
    (jog-free too). Kept when every run is routed, every clearance holds and the nets involved end
    up with fewer jogs in total. Returns fixed [(net, layer, at, offset, how, uuids)]."""
    fixed, tried = [], set()
    gnd = board.FindNet("GND").GetNetCode()
    base = len(drc_check(board))                 # problems already there (none expected)
    while True:
        ctx = Ctx(board)
        cand = None
        for ci, (net, layer, pts, ts) in enumerate(ctx.chains):
            name = ts[0].GetNetname()
            if name in SKIP_NETS or any(uid(t) in ctx.fixed for t in ts):
                continue
            for j, off in find_jogs(pts):
                tag = (name, board.GetLayerName(layer), bmm(pts[j + 1]))
                if tag not in skip and tag not in tried:
                    cand = (ci, j, off, tag)
                    break
            if cand:
                break
        if cand is None:
            break
        ci, j, off, tag = cand
        tried.add(tag)
        net, layer, pts, ts = ctx.chains[ci]
        name = ts[0].GetNetname()
        # a run whose own ends sit on other tracks ("onto") can go: its new ends are snapped back
        # onto them; tracks ending on it ("tee"), vias or pads along it pin it
        if any(a[0] != "onto" for t in ts for a in ctx.anchors.get(uid(t), [])):
            continue
        a_it = stop_item(ctx, net, layer, pts[0], {uid(t) for t in ts})
        b_it = stop_item(ctx, net, layer, pts[-1], {uid(t) for t in ts})
        if a_it is None or b_it is None:
            continue
        w = max(t.GetWidth() for t in ts)
        nbrs = []
        for cj, (n2, l2, P2, T2) in enumerate(ctx.chains):
            if n2 == net or l2 != layer or n2 == gnd or T2[0].GetNetname() in SKIP_NETS:
                continue
            if any(uid(t) in ctx.fixed or any(a[0] != "onto" for a in ctx.anchors.get(uid(t), [])) for t in T2):
                continue
            dmin = min(dist_point_seg(p, pts[m], pts[m + 1]) for p in P2 for m in range(len(pts) - 1))
            dmin = min(dmin, min(dist_point_seg(p, P2[m], P2[m + 1]) for p in pts for m in range(len(P2) - 1)))
            if dmin < MM(1.0) + w / 2 + T2[0].GetWidth() / 2:
                ia = stop_item(ctx, n2, l2, P2[0], {uid(t) for t in T2})
                ib = stop_item(ctx, n2, l2, P2[-1], {uid(t) for t in T2})
                if ia is not None and ib is not None:
                    nbrs.append((dmin, cj, ia, ib))
        nbrs.sort(key=lambda r: r[0])
        nbrs = nbrs[:max_nbrs]
        if not nbrs:
            continue
        gone = {uid(t) for t in ts} | {uid(t) for d_, cj, ia, ib in nbrs for t in ctx.chains[cj][3]}
        nbr_names = sorted({ctx.chains[cj][3][0].GetNetname() for d_, cj, ia, ib in nbrs})
        txn = Txn(ctx)
        txn.apply([("del", t) for t in ts] + [("del", t) for d_, cj, ia, ib in nbrs for t in ctx.chains[cj][3]])
        ok = True
        order = [(ci, a_it, b_it)] + [(cj, ia, ib) for d_, cj, ia, ib in nbrs]
        for k, it_a, it_b in order:
            n_, l_, P_, T_ = ctx.chains[k]
            r = route_run(board, T_[0].GetNetname(), l_, it_a, it_b, max(t.GetWidth() for t in T_), chain_len(P_), ignore=gone)
            if r is None:
                ok = False
                break
            runs, vias = r
            txn.apply([("add", n_, L_, max(t.GetWidth() for t in T_), Q[m], Q[m + 1]) for L_, Q in runs for m in range(len(Q) - 1)]
                      + [("addvia", n_, q) for q in vias])
        if not ok or txn.conflicts(first=True) or not fewer_jogs(ctx, txn) or \
                len(drc_check(board, drop={uid(t) for t in txn.dele})) > base:
            txn.rollback()
            continue
        names = nbr_names
        LAST_TOUCHED[:] = [uid(x) for x in txn.touched()]
        txn.commit()
        merge_collinear(board)
        how = "re-routed with its neighbours %s" % " ".join(names)
        fixed.append(tag + (round(TOMM(int(off)), 2), how, list(LAST_TOUCHED)))
        log("  jog %s %s at %s (%.2f mm): %s" % (tag[0], tag[1], tag[2], TOMM(int(off)), how))
    return fixed


def jog_pass(board, skip=(), push=True, log=print):
    """Straighten jogs until a whole pass fixes none. Returns (fixed [(net, layer, at, offset, how)],
    left {(net, layer name, at): offset})."""
    merge_collinear(board)
    ctx = Ctx(board)
    fixed = []
    for _ in range(12):
        progress = 0
        left = {}
        ci = 0
        while ci < len(ctx.chains):
            net, layer, pts, ts = ctx.chains[ci]
            name = ts[0].GetNetname()
            done = False
            if name not in SKIP_NETS and not any(uid(t) in ctx.fixed for t in ts):
                for j, off in find_jogs(pts):
                    at = bmm(pts[j + 1])
                    tag = (name, board.GetLayerName(layer), at)
                    if tag in skip:
                        left[tag] = round(TOMM(int(off)), 2)
                        continue
                    how = None
                    for label, ch in jog_plans(board, pts, ts, j, layer):
                        how = try_plan(ctx, label, ch, push)
                        if how:
                            break
                    if how:
                        fixed.append(tag + (round(TOMM(int(off)), 2), how, list(LAST_TOUCHED)))
                        log("  jog %s %s at %s (%.2f mm): %s" % (tag[0], tag[1], tag[2], TOMM(int(off)), how))
                        merge_collinear(board, ctx.obs)
                        ctx.refresh()
                        progress += 1
                        done = True
                        break
                    left[tag] = round(TOMM(int(off)), 2)
            if not done:
                ci += 1
        # jogs the local moves could not fix: re-route a window around them
        tried = set()
        while True:
            again = False
            for ci, (net, layer, pts, ts) in enumerate(ctx.chains):
                for j, off in find_jogs(pts):
                    tag = (ts[0].GetNetname(), board.GetLayerName(layer), bmm(pts[j + 1]))
                    sig = (frozenset(uid(t) for t in ts), j)
                    if sig in tried or tag in skip:
                        continue
                    tried.add(sig)
                    how = try_window(ctx, ci, j, log)
                    if how:
                        fixed.append(tag + (round(TOMM(int(off)), 2), how, list(LAST_TOUCHED)))
                        log("  jog %s %s at %s (%.2f mm): %s" % (tag[0], tag[1], tag[2], TOMM(int(off)), how))
                        merge_collinear(board, ctx.obs)
                        ctx.refresh()
                        progress += 1
                        again = True
                        break
                if again:
                    break
            if not again:
                break
        if not progress:
            break
    left = {}
    for net, layer, pts, ts in ctx.chains:
        for j, off in find_jogs(pts):
            left[(ts[0].GetNetname(), board.GetLayerName(layer), bmm(pts[j + 1]))] = round(TOMM(int(off)), 2)
    return fixed, left


TINY = MM(0.15)                            # router leftovers: segments this short at a via


def snap_tiny_stubs(board, log=print):
    """Freerouting leaves vias with a stub of a few tens of um before the real track starts (a
    tiny step that reads as a jog and blocks moves). The via moves to the end of its stub and the
    stub goes; the tracks on the other layer follow with plan_via_move (directions kept), all
    clearances checked. Returns the number of vias moved."""
    n = 0
    for _ in range(3):
        ctx = Ctx(board)
        done = 0
        for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]:
            if not ctx.movable(v):
                continue
            c = pt(v.GetPosition())
            stubs = [t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetCode() == v.GetNetCode()
                     and t.GetLength() < TINY and (v.HitTest(t.GetStart(), 0) or v.HitTest(t.GetEnd(), 0))]
            if len(stubs) != 1 or uid(stubs[0]) not in ctx.where:
                continue
            s = stubs[0]
            a, b = pt(s.GetStart()), pt(s.GetEnd())
            far = b if norm(sub(a, c)) < norm(sub(b, c)) else a
            m = sub(far, c)
            if norm(m) < UM:
                continue
            ch = plan_via_move(ctx, v, m, skip=(uid(s),))
            ch = follow_anchors(ctx, ch) if ch is not None else None
            if ch is None:
                continue
            txn = Txn(ctx)
            txn.apply(ch + [("del", s)])
            if txn.conflicts(first=True):
                txn.rollback()
                continue
            txn.commit()
            done += 1
            ctx.refresh()
        n += done
        if not done:
            break
    return n


MICRO = MM(0.03)                            # router slivers at the end of a run


def drop_micro_ends(board, log=print):
    """A run ending in a sliver (< 0.03 mm) whose inner end already lies in the pad, via or track
    the run ends on: the sliver goes (it reads as a jog and carries nothing). Returns how many."""
    n = 0
    ctx = Ctx(board)
    dead = []
    for net, layer, pts, ts in ctx.chains:
        if len(ts) < 2 or ts[0].GetNetname() in SKIP_NETS:
            continue
        for end, inner, t in ((pts[0], pts[1], ts[0]), (pts[-1], pts[-2], ts[-1])):
            if norm(sub(end, inner)) >= MICRO or uid(t) in ctx.fixed or uid(t) in ctx.anchored:
                continue
            it = stop_item(ctx, net, layer, end, {uid(x) for x in ts})
            if it is None:
                continue
            q = V(inner)
            if it.GetClass() == "PAD":
                inside = it.HitTest(q)
            elif it.GetClass() == "PCB_VIA":
                inside = it.HitTest(q, 0)
            else:
                inside = pcbnew.SEG(it.GetStart(), it.GetEnd()).Distance(q) < it.GetWidth() / 2 - UM
            if inside:
                dead.append(t)
    seen = set()
    for t in dead:
        if uid(t) not in seen:
            seen.add(uid(t))
            board.Delete(t)
            n += 1
    del dead
    return n


def strip_stitching(board):
    """Delete the GND pours and every GND via without a track attached (island / grid stitching).
    Returns the number of vias deleted."""
    for z in [z for z in board.Zones() if not z.GetIsRuleArea()]:
        board.Delete(z)
    ends = [(t.GetStart(), t.GetEnd()) for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "GND"]
    dead = [v for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and v.GetNetname() == "GND"
            and not any(v.HitTest(a, 0) or v.HitTest(b, 0) for a, b in ends)]
    n = len(dead)
    for v in dead:
        board.Delete(v)
    del dead
    return n


# ------------------------------------------------------------------------------ copper
ZONE_CLR, ZONE_MINW = 0.2, 0.2              # mm
THERMAL_GAP, THERMAL_SPOKE = 0.3, 0.5       # mm
STITCH_GRID = 5.0                           # mm
STITCH_GAP = MM(1.5)                        # grid via to any other via
ISLAND_GAP = MM(0.7)                        # island via to any other via (hole to hole 0.25 mm + margin)
STITCH_AVOID = ("U1", "J7", "J11")          # no grid vias in these courtyards
LABEL_VIA_GAP = MM(0.15)                    # via copper to silkscreen text box


def add_zones(board):
    """GND pours on F.Cu and B.Cu and the solid GND planes on In1.Cu / In2.Cu, each over the whole
    outline (replacing any old zones)."""
    for z in [z for z in board.Zones() if not z.GetIsRuleArea()]:
        board.Delete(z)
    gnd = board.FindNet("GND")
    zones = {}
    for layer, name in ((F, "GND_F"), (IN1, "GND_L2"), (IN2, "GND_L3"), (B, "GND_B")):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNetCode(gnd.GetNetCode())
        z.SetZoneName(name)
        o = z.Outline()
        o.NewOutline()
        for x, y in ((0, 0), (D.BOARD_W, 0), (D.BOARD_W, D.BOARD_H), (0, D.BOARD_H)):
            p = R.P(x, y)
            o.Append(p.x, p.y)
        z.SetLocalClearance(MM(ZONE_CLR))
        z.SetMinThickness(MM(ZONE_MINW))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(MM(THERMAL_GAP))
        z.SetThermalReliefSpokeWidth(MM(THERMAL_SPOKE))
        z.SetAssignedPriority(0)
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_NEVER)
        board.Add(z)
        zones[layer] = z
    return zones


# a stitching via in a pour piece lands in this layer's neighbouring GND plane (stack-up option B)
PLANE_UNDER = {F: IN1, B: IN2, IN1: IN2, IN2: IN1}


def fill(board, zones, mode):
    for z in zones.values():
        z.SetIslandRemovalMode(mode)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


def text_boxes(board):
    """Bounding boxes (nm: x0, y0, x1, y1) of every visible silkscreen text on either side."""
    out = []
    items = [fp.Reference() for fp in board.GetFootprints()] + [fp.Value() for fp in board.GetFootprints()]
    items += [g for fp in board.GetFootprints() for g in fp.GraphicalItems() if g.GetClass() == "PCB_TEXT"]
    items += [d for d in board.GetDrawings() if d.GetClass() in ("PCB_TEXT", "PCB_TEXTBOX")]
    for t in items:
        if t.IsVisible() and t.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and t.GetShownText(False).strip():
            b = t.GetBoundingBox()
            out.append((b.GetLeft(), b.GetTop(), b.GetRight(), b.GetBottom()))
    return out


def near_box(p, boxes, r):
    for x0, y0, x1, y1 in boxes:
        dx = max(x0 - p[0], 0, p[0] - x1)
        dy = max(y0 - p[1], 0, p[1] - y1)
        if dx * dx + dy * dy < r * r:
            return True
    return False


def new_via(board, obs, p):
    v = pcbnew.PCB_VIA(board)
    v.SetPosition(V(p))
    v.SetWidth(R.GND_VIA_D)
    v.SetDrill(R.GND_VIA_DRILL)
    v.SetLayerPair(F, B)
    v.SetNet(board.FindNet("GND"))
    board.Add(v)
    obs.add_track(v)
    return v


def via_ok(obs, p, gnd, boxes, near_vias=ISLAND_GAP):
    if near_box(p, boxes, R.GND_VIA_D / 2 + LABEL_VIA_GAP):
        return False
    for u, (c, hr) in obs.holes.items():
        if norm(sub(c, p)) < near_vias and hr < MM(0.2):
            return False
    return not obs.via_conflicts(p, R.GND_VIA_D, R.GND_VIA_DRILL, gnd, first=True)


def region_points(s, step=MM(0.1)):
    """Grid points inside polygon set s, nearest to its interior point first."""
    bb = s.BBox()
    c = R.interior_point(s)
    c = pt(c) if c is not None else pt(bb.Centre())
    pts = []
    x = bb.GetLeft()
    while x <= bb.GetRight():
        y = bb.GetTop()
        while y <= bb.GetBottom():
            q = pcbnew.VECTOR2I(int(x), int(y))
            if s.Contains(q):
                pts.append((float(x), float(y)))
            y += step
        x += step
    pts.sort(key=lambda q: norm(sub(q, c)))
    return pts


def circle_poly(c, r, n=24):
    s = pcbnew.SHAPE_POLY_SET()
    s.NewOutline()
    k = 1 / math.cos(math.pi / n)
    for i in range(n):
        a = 2 * math.pi * i / n
        s.Append(int(c[0] + r * k * math.cos(a)), int(c[1] + r * k * math.sin(a)))
    return s


def box_poly(b, grow):
    s = pcbnew.SHAPE_POLY_SET()
    s.NewOutline()
    x0, y0, x1, y1 = b[0] - grow, b[1] - grow, b[2] + grow, b[3] + grow
    for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
        s.Append(int(x), int(y))
    return s


def via_forbidden(obs, gnd, boxes):
    """Where a GND stitching via centre may not go: other-net copper on either layer grown by via
    radius + clearance, holes grown for hole-to-hole spacing, keep-outs, silkscreen text, edge."""
    vclr = obs.net_clearance(gnd)
    r = R.GND_VIA_D / 2
    forb = pcbnew.SHAPE_POLY_SET()
    for layer, net, s, bb, clr, u, kind, item in obs.ents.values():
        if net == gnd:
            continue
        g = pcbnew.SHAPE_POLY_SET(s)
        g.Inflate(int(r + (clr if net < 0 else max(vclr, clr))), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
        forb.Append(g)
    for u, (c, hr) in obs.holes.items():
        forb.Append(circle_poly(c, hr + R.GND_VIA_DRILL / 2 + HOLE2HOLE))
    for b in boxes:
        forb.Append(box_poly(b, r + LABEL_VIA_GAP))
    try:
        forb.Simplify()
    except TypeError:
        forb.Simplify(pcbnew.SHAPE_POLY_SET.PM_FAST)
    return forb


def board_inner(margin):
    s = pcbnew.SHAPE_POLY_SET()
    s.NewOutline()
    for x, y in ((0, 0), (D.BOARD_W, 0), (D.BOARD_W, D.BOARD_H), (0, D.BOARD_H)):
        p = R.P(x, y)
        s.Append(p.x, p.y)
    s.Deflate(int(margin), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
    return s


def stitch_islands(board, zones, boxes, log=print):
    """Join every GND component apart from the main one (largest pour) to the main one with a via:
    the most interior point of (one of its pour pieces) x (a main-component pour piece on the other
    layer) minus everything a via must keep clear of on both layers (other-net copper, holes,
    silkscreen text, edge). Repeats until nothing changes (a piece joined to the main one can then
    take others). Returns (vias added, pieces left over [(layer, area mm2, centre mm)])."""
    gnd = board.FindNet("GND").GetNetCode()
    added = 0
    left = []
    vin = board_inner(MM(EDGE) + R.GND_VIA_D / 2)
    for _ in range(10):
        fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
        obs = Obstacles(board)
        forb = via_forbidden(obs, gnd, boxes)
        cls, comps, main = R.gnd_components(board, zones)
        mains = {layer: [cls[layer][k[2]][1] for k in comps[main] if k[0] == "P" and k[1] == layer] for layer in cls}
        n = 0
        left = []
        for ci_, comp in enumerate(comps):
            if ci_ == main:
                continue
            pieces = sorted([(k[1], cls[k[1]][k[2]]) for k in comp if k[0] == "P"], key=lambda pc: -pc[1][2])
            done = False
            for layer, (i, poly, area, touch) in pieces:
                other = PLANE_UNDER[layer]
                for m in mains[other]:
                    if not poly.BBox().Intersects(m.BBox()):
                        continue
                    reg = pcbnew.SHAPE_POLY_SET(poly)
                    reg.BooleanIntersection(m)
                    if not R.outlines(reg):
                        continue
                    reg.BooleanIntersection(vin)
                    reg.BooleanSubtract(forb)
                    reg.Deflate(MM(0.005), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
                    if not R.outlines(reg):
                        continue
                    ip = R.interior_point(reg)
                    bb = reg.BBox()
                    step = max(MM(0.02), int(math.sqrt(bb.GetWidth() * bb.GetHeight() / 3000.0)))
                    cands = ([pt(ip)] if ip is not None else [])
                    if not cands or obs.via_conflicts(cands[0], R.GND_VIA_D, R.GND_VIA_DRILL, gnd, first=True):
                        cands += region_points(reg, step)[:120]
                    for q in cands:
                        if not obs.via_conflicts(q, R.GND_VIA_D, R.GND_VIA_DRILL, gnd, first=True):
                            new_via(board, obs, q)
                            forb.Append(circle_poly(q, R.GND_VIA_DRILL + HOLE2HOLE))
                            n += 1
                            done = True
                            break
                    if done:
                        break
                if done:
                    break
            if not done:
                for layer, (i, poly, area, touch) in pieces:
                    if not touch and area >= 0.05:
                        c = poly.BBox().Centre()
                        left.append((board.GetLayerName(layer), round(area, 2), bmm(c)))
        added += n
        if not n:
            break
    return added, left


def floating_pieces(board, zones):
    """Fill with islands kept; [(layer, polygon, area mm2)] of the GND pour pieces that are not part
    of the main GND component."""
    fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    cls, comps, main = R.gnd_components(board, zones)
    out = []
    for ci_, comp in enumerate(comps):
        if ci_ == main:
            continue
        for k in comp:
            if k[0] == "P":
                i, poly, area, touch = cls[k[1]][k[2]]
                out.append((k[1], poly, area))
    return out


def window_area(pieces, win):
    """Area (mm2) of the floating pieces without room for a via that reach into win."""
    x0, y0, x1, y1 = win
    tot = 0.0
    for layer, poly, area in pieces:
        bb = poly.BBox()
        if bb.GetRight() >= x0 and bb.GetLeft() <= x1 and bb.GetBottom() >= y0 and bb.GetTop() <= y1:
            if not via_room(poly):
                tot += area
    return tot


def via_room(poly):
    """True when a via could sit inside the piece at all (ignoring the other layer)."""
    a = pcbnew.SHAPE_POLY_SET(poly)
    a.Deflate(R.VIA_R + MM(0.25 - ZONE_CLR), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
    return bool(R.outlines(a))


def max_shift(ctx, it, nrm, limit=MM(1.0)):
    """Largest shift of track it along unit vector nrm (0.05 mm steps up to limit) that keeps every
    clearance, as a change list, or None. The board is left unchanged."""
    for k in range(int(limit / MM(0.05)), 0, -1):
        ch = plan_shift(ctx, it, mul(nrm, k * MM(0.05)))
        ch = follow_anchors(ctx, ch) if ch is not None else None
        if ch is None:
            continue
        txn = Txn(ctx)
        txn.apply(ch)
        bad = txn.conflicts(first=True)
        txn.rollback()
        if not bad:
            return ch
    return None


def void_pass(board, zones, log=print, rounds=3):
    """Close narrow strips of pour that can be neither grounded with a via nor filled: for each
    floating GND piece without room for a via, every movable track segment bounding it is tried,
    shifted toward the piece by the largest step (0.05 mm steps, up to 1 mm) that keeps all
    clearances, its corners sliding along the neighbouring segments. A move is kept only if, after
    a refill, the floating pour area within 3 mm of the piece has dropped by at least half the
    piece's area. Returns the number of moves kept."""
    kept = 0
    for _ in range(rounds):
        ctx = Ctx(board)
        pieces = floating_pieces(board, zones)
        todo = sorted([pc for pc in pieces if pc[2] >= 0.3 and not via_room(pc[1])], key=lambda pc: -pc[2])
        n = 0
        moved = set()
        for layer, poly, area in todo:
            bb = poly.BBox()
            win = (bb.GetLeft() - MM(3), bb.GetTop() - MM(3), bb.GetRight() + MM(3), bb.GetBottom() + MM(3))
            ip = R.interior_point(poly)
            if ip is None:
                continue
            c = pt(ip)
            cand = []
            for e in ctx.obs.near(layer, bb.GetLeft() - MM(0.6), bb.GetTop() - MM(0.6), bb.GetRight() + MM(0.6),
                                  bb.GetBottom() + MM(0.6)):
                it = e[7]
                if e[6] != "track" or not ctx.movable(it) or uid(it) in moved or uid(it) not in ctx.where:
                    continue
                seg = pcbnew.SEG(it.GetStart(), it.GetEnd())
                if poly.SquaredDistanceToSeg(seg) > (it.GetWidth() / 2 + MM(ZONE_CLR) + MM(0.08)) ** 2:
                    continue
                cand.append(it)
            before = None
            dbg = os.environ.get("D32_VOID_DEBUG")
            if dbg:
                log("  piece %s %.2f mm2 at %s: %d candidate tracks %s" % (board.GetLayerName(layer), area, bmm(c), len(cand),
                                                                        [x.GetNetname() for x in cand]))
            for it in cand:
                a, b = pt(it.GetStart()), pt(it.GetEnd())
                d = unit(sub(b, a))
                nrm = (-d[1], d[0])
                if dot(nrm, sub(c, a)) < 0:
                    nrm = (d[1], -d[0])
                ch = max_shift(ctx, it, nrm)
                if ch is None:
                    if dbg:
                        why = "no shift" if plan_shift(ctx, it, mul(nrm, MM(0.05))) is None else "conflicts"
                        if uid(it) in ctx.anchored:
                            why = "anchored"
                        log("    %s: %s" % (it.GetNetname(), why))
                    continue
                if before is None:
                    before = window_area(floating_pieces(board, zones), win)
                txn = Txn(ctx)
                txn.apply(ch)
                nets = {x.GetNetCode() for x in txn.touched()}
                if sum(count_jogs(c2[2]) for c2 in chains(board, nets)) > \
                        sum(count_jogs(c2[2]) for c2 in ctx.chains if c2[0] in nets):
                    txn.rollback()
                    continue
                after = window_area(floating_pieces(board, zones), win)
                if after <= before - 0.5 * area:
                    txn.commit()
                    moved.add(uid(it))
                    n += 1
                    log("  void %s %.2f mm2 at %s: moved %s, floating area nearby %.2f -> %.2f mm2" % (
                        board.GetLayerName(layer), area, bmm(c), it.GetNetname(), before, after))
                    ctx.refresh()
                    break
                txn.rollback()
        kept += n
        if not n:
            break
    fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    return kept


def stitch_push(board, zones, boxes, log=print, max_tries=24):
    """Floating GND pieces that no via fits as things stand: a via goes at a spot inside the piece
    (and over ground on the other layer) and the tracks or vias of other nets in its way, on either
    layer, are pushed aside (clear_blocker: tracks shift with corner sliding, vias move with their
    tracks; every clearance kept, no new jog, pre-routes and mid-segment connections kept), at most
    four of them. Returns the number of vias added."""
    gnd = board.FindNet("GND").GetNetCode()
    added = 0
    for rnd in range(3):
        fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
        ctx = Ctx(board)
        cls, comps, main = R.gnd_components(board, zones)
        mains = {layer: [cls[layer][k[2]][1] for k in comps[main] if k[0] == "P" and k[1] == layer] for layer in cls}
        n = 0
        for ci_, comp in enumerate(comps):
            if ci_ == main:
                continue
            pieces = sorted([(k[1], cls[k[1]][k[2]]) for k in comp if k[0] == "P"], key=lambda pc: -pc[1][2])
            if not pieces or sum(pc[1][2] for pc in pieces) < 0.3:
                continue
            done = False
            for layer, (i, poly, area, touch) in pieces[:2]:
                other = PLANE_UNDER[layer]
                inner = pcbnew.SHAPE_POLY_SET(poly)
                inner.Deflate(MM(0.05), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
                if not R.outlines(inner):
                    inner = poly
                ip = R.interior_point(inner)
                cands = ([pt(ip)] if ip is not None else []) + region_points(inner, MM(0.3))[:max_tries]
                for p in cands:
                    q = V(p)
                    if near_box(p, boxes, R.GND_VIA_D / 2 + LABEL_VIA_GAP):
                        continue
                    if not Obstacles.in_board(p, MM(EDGE) + R.GND_VIA_D / 2):
                        continue
                    # the other layer must be main ground here, or a track that can move away
                    on_main = any(m.Contains(q) for m in mains[other])
                    txn = Txn(ctx)
                    txn.apply([("addvia", gnd, p)])
                    bad = txn.conflicts()
                    if not on_main and not any(e is not None and len(e) > 2 and e[0] == other and e[6] == "track"
                                               for it, e in bad):
                        txn.rollback()
                        continue
                    ok = True
                    for _ in range(5):
                        bad = txn.conflicts()
                        if not bad:
                            break
                        it, e = bad[0]
                        if e is None or len(e) == 2 or e[6] not in ("via", "track") or not ctx.movable(e[7]):
                            ok = False
                            break
                        if not clear_blocker(ctx, txn, e, sub(entry_center(e), p)):
                            ok = False
                            break
                    if not ok or txn.conflicts(first=True):
                        txn.rollback()
                        continue
                    nets = {x.GetNetCode() for x in txn.touched()} - {gnd}
                    if sum(count_jogs(c[2]) for c in chains(board, nets)) > sum(count_jogs(c[2]) for c in ctx.chains if c[0] in nets):
                        txn.rollback()
                        continue
                    # the via must join the piece to the main GND copper
                    newv = [x for x in txn.touched() if x.GetClass() == "PCB_VIA" and x.GetNetCode() == gnd]
                    fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
                    cls2, comps2, main2 = R.gnd_components(board, zones)
                    if not newv or ("I", uid(newv[0])) not in comps2[main2]:
                        txn.rollback()
                        continue
                    txn.commit()
                    ctx.refresh()
                    n += 1
                    done = True
                    break
                if done:
                    break
        added += n
        if not n:
            break
    return added


def prune_floating_vias(board, zones):
    """GND vias without tracks that end up in a GND component other than the main one (they join
    only floating pieces to each other) are deleted. Returns how many."""
    fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    cls, comps, main = R.gnd_components(board, zones)
    ends = [(t.GetStart(), t.GetEnd()) for t in board.GetTracks() if t.GetClass() == "PCB_TRACK" and t.GetNetname() == "GND"]
    lost = set()
    for ci_, comp in enumerate(comps):
        if ci_ != main:
            lost |= {k[1] for k in comp if k[0] == "I"}
    dead = [v for v in board.GetTracks() if v.GetClass() == "PCB_VIA" and v.GetNetname() == "GND" and uid(v) in lost
            and not any(v.HitTest(a, 0) or v.HitTest(b, 0) for a, b in ends)]
    n = len(dead)
    for v in dead:
        board.Delete(v)
    del dead
    return n


def silk_text_items(board):
    """[(item, box, footprint or None)] for every visible silkscreen text (references, board texts)."""
    out = []
    for fp in board.GetFootprints():
        t = fp.Reference()
        if t.IsVisible() and t.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            out.append((t, bbox_t(t.GetBoundingBox()), fp))
    for d in board.GetDrawings():
        if d.GetClass() == "PCB_TEXT" and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            out.append((d, bbox_t(d.GetBoundingBox()), None))
    return out


def text_map(board, layer, exclude=()):
    """SilkMap of one side with every visible text on it already in, except the references of the
    footprints named in exclude."""
    sm = SilkMap(board, layer)
    for it, b, fp in silk_text_items(board):
        if it.GetLayer() == layer and not (fp is not None and fp.GetReference() in exclude):
            sm.add_text(b)
    return sm


def unblock_via_spots(board, zones, log=print):
    """Floating GND pieces that could take a via if it were not for silkscreen text over the spot:
    the reference in the way is placed again (same rules) with the via spot kept free. Returns the
    number of texts moved."""
    gnd = board.FindNet("GND").GetNetCode()
    fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    obs = Obstacles(board)
    forb = via_forbidden(obs, gnd, [])
    vin = board_inner(MM(EDGE) + R.GND_VIA_D / 2)
    cls, comps, main = R.gnd_components(board, zones)
    mains = {layer: [cls[layer][k[2]][1] for k in comps[main] if k[0] == "P" and k[1] == layer] for layer in cls}
    spots = []
    for ci_, comp in enumerate(comps):
        if ci_ == main:
            continue
        found = None
        for k in comp:
            if k[0] != "P" or found:
                continue
            layer, poly = k[1], cls[k[1]][k[2]][1]
            other = PLANE_UNDER[layer]
            for m in mains[other]:
                if not poly.BBox().Intersects(m.BBox()):
                    continue
                reg = pcbnew.SHAPE_POLY_SET(poly)
                reg.BooleanIntersection(m)
                reg.BooleanIntersection(vin)
                reg.BooleanSubtract(forb)
                reg.Deflate(MM(0.005), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
                if R.outlines(reg):
                    p = R.interior_point(reg)
                    if p is not None:
                        found = pt(p)
                        break
        if found:
            spots.append(found)
    if not spots:
        return 0
    rv = R.GND_VIA_D / 2 + LABEL_VIA_GAP
    moved = 0
    for p in spots:
        items = silk_text_items(board)
        for it, b, fp in items:
            dx = max(b[0] - p[0], 0, p[0] - b[2])
            dy = max(b[1] - p[1], 0, p[1] - b[3])
            if math.hypot(dx, dy) >= rv:
                continue
            if fp is None or fp.GetReference() in PLATES or fp.GetReference() in CALLOUT_REFS:
                continue                            # legend, plate names and the headers they follow stay
            ref = fp.GetReference()
            layer = it.GetLayer()
            # a label in a row moves with its row (same line kept), else alone
            grp = [g for g in all_groups(board) if ref in g]
            members = [r for r in grp[0]] if grp else [ref]
            fpl = [board.FindFootprintByReference(r) for r in members]
            members = [r for r, f in zip(members, fpl) if f is not None and f.Reference().IsVisible()
                       and f.Reference().GetLayer() == layer]
            fpl = [board.FindFootprintByReference(r) for r in members]
            keep = {r: (pt(f.Reference().GetPosition()), f.Reference().GetTextAngleDegrees()) for r, f in zip(members, fpl)}

            def restore(rs):
                for r in rs:
                    t = board.FindFootprintByReference(r).Reference()
                    t.SetTextAngleDegrees(keep[r][1])
                    t.SetPosition(V(keep[r][0]))

            def with_spots(sm):
                for q in spots:
                    sm._add("via", (q, R.GND_VIA_D / 2), (q[0] - rv, q[1] - rv, q[0] + rv, q[1] + rv), None)
                return sm
            if len(members) > 1:
                sm = with_spots(text_map(board, layer, exclude=members))
                res = best_group(sm, fpl, [Unit([f.Reference()]) for f in fpl])
                if res is not None:
                    for f, (angle, c, nb) in zip(fpl, res):
                        Unit([f.Reference()]).place(angle, c)
                    moved += len(fpl)
                    log("  labels %s moved off a stitching-via spot at %s" % (" ".join(members), bmm(p)))
                    continue
                restore(members)
            sm = with_spots(text_map(board, layer, exclude=(ref,)))
            best = best_single(sm, fp, Unit([fp.Reference()]))
            if best is None:
                restore([ref])
                continue
            s, angle, c, nb = best
            Unit([fp.Reference()]).place(angle, c)
            moved += 1
            log("  label %s moved off a stitching-via spot at %s" % (ref, bmm(p)))
    return moved


FAST_NETS = ("USB_DP", "USB_DM", "SCK", "MOSI", "MISO", "SD_CS", "WS_DATA")   # USB, SPI, WS2812 data
RETURN_VIA_MAX = MM(1.5)                    # a GND via this close to each layer change of a fast net


def return_vias(board, boxes, log=print):
    """A signal changing between F.Cu and B.Cu changes reference plane (In1 -> In2): a GND via next
    to each via of a fast net (FAST_NETS) carries the return current between the two planes. For a
    via with no GND via within RETURN_VIA_MAX, one is added at the nearest legal spot (rings of
    0.75 - 1.5 mm, clear of labels). Returns (added, [(net, at)] left without one)."""
    gnd = board.FindNet("GND").GetNetCode()
    obs = Obstacles(board)
    added, left = 0, []
    for v in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA" and t.GetNetname() in FAST_NETS]:
        c = pt(v.GetPosition())
        gv = [pt(g.GetPosition()) for g in board.GetTracks() if g.GetClass() == "PCB_VIA" and g.GetNetCode() == gnd]
        if any(norm(sub(q, c)) <= RETURN_VIA_MAX for q in gv):
            continue
        done = False
        for r in (0.75, 0.85, 1.0, 1.15, 1.3, 1.5):
            for k in range(24):
                a = 2 * math.pi * k / 24
                q = (c[0] + MM(r) * math.cos(a), c[1] + MM(r) * math.sin(a))
                if via_ok(obs, q, gnd, boxes, MM(0.6)):
                    new_via(board, obs, q)
                    added += 1
                    done = True
                    break
            if done:
                break
        if not done:
            left.append((v.GetNetname(), bmm(c)))
    return added, left


def stitch_grid(board, zones, boxes):
    """Stitching vias on a STITCH_GRID lattice (searching up to 1 mm around each lattice point)
    where an outer pour is solid and belongs to the main GND component (both outer pours preferred),
    clear of the labels and of the U1 / J7 / J11 courtyards. Every via joins the outer pours to the
    two GND planes."""
    fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_NEVER)
    gnd = board.FindNet("GND").GetNetCode()
    obs = Obstacles(board)
    cls, comps, main = R.gnd_components(board, zones)
    mains = {layer: [cls[layer][k[2]][1] for k in comps[main] if k[0] == "P" and k[1] == layer] for layer in cls}
    solid = {}
    for layer in (F, B):
        s = pcbnew.SHAPE_POLY_SET()
        for m in mains[layer]:
            s.Append(m)
        s.Deflate(R.VIA_R + MM(0.1), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, MAXERR)
        solid[layer] = s
    avoid = [board.FindFootprintByReference(r).GetCourtyard(pcbnew.F_CrtYd) for r in STITCH_AVOID]
    nx, ny = int(D.BOARD_W // STITCH_GRID), int(D.BOARD_H // STITCH_GRID)
    offs = [(0, 0)] + [(dx * 0.25, dy * 0.25) for r in range(1, 5) for dx in range(-r, r + 1) for dy in range(-r, r + 1)
                       if max(abs(dx), abs(dy)) == r]
    added = 0
    for i in range(nx):
        for j in range(ny):
            x = (i + 0.5) * STITCH_GRID + (D.BOARD_W - nx * STITCH_GRID) / 2
            y = (j + 0.5) * STITCH_GRID + (D.BOARD_H - ny * STITCH_GRID) / 2
            done = False
            for both in (True, False):
                for dx, dy in offs:
                    q = R.P(x + dx, y + dy)
                    p = pt(q)
                    inf, inb = solid[F].Contains(q), solid[B].Contains(q)
                    if not ((inf and inb) if both else (inf or inb)):
                        continue
                    if any(c.Contains(q) for c in avoid):
                        continue
                    if not via_ok(obs, p, gnd, boxes, STITCH_GAP):
                        continue
                    new_via(board, obs, p)
                    added += 1
                    done = True
                    break
                if done:
                    break
    return added
# ------------------------------------------------------------------------------ silkscreen
REF_SIZES = (1.0,)                          # mm text height (JLCPCB minimum 1.0 mm): one size for all
REF_STROKE = 0.15                           # mm
SILK_GAP = MM(0.15)                         # text box to pads, mask openings, other silk
TEXT_GAP = MM(0.15)                         # text box to another text box
VIA_TEXT_GAP = MM(0.15)                     # via copper to text box
TEXT_EDGE = MM(0.3)
MAX_FROM_PART = MM(1.0)                     # label box to its own courtyard (owner: <= 1 mm)
SIDE_OVERLAP = 0.4                          # a label overlaps its part's span by >= 40 % of its own size
                                            # (beside one side, never off a corner; pcb_audit.py: 20 %)
AMBIG_MARGIN = MM(0.05)                     # a label must be this much nearer its own part than any other
WORD_GAP = MM(0.7)                          # between a reference and the plate name after it
# rows / columns of like parts: one side, one line, labels in the order of the parts
GROUPS = [("R6", "R9", "R5", "R4"), ("R16", "R17", "R18", "R19"), ("C10", "C9"), ("J1", "J2", "J3"), ("J4", "J5"),
          ("R12", "R13"), ("Q2", "Q3"), ("C4", "C3"), ("U3", "U2"), ("U6", "U5"), ("SW2", "SW1"), ("R11", "R8"),
          ("C11", "R10"), ("C14", "C16")]
ROW_TOL, ROW_PITCH = 0.3, 5.0                # mm: rows of like parts as pcb_audit.py finds them


def auto_rows(board):
    """Rows / columns of 3+ like parts (same footprint, rotation and side, centres in line within
    ROW_TOL, neighbours closer than ROW_PITCH), in part order, as pcb_audit.py checks them."""
    out = []
    kinds = {}
    for f in board.GetFootprints():
        if len(list(f.Pads())) and not f.GetReference().startswith("H"):
            kinds.setdefault((f.GetFPIDAsString(), round(f.GetOrientationDegrees()) % 180, f.GetLayer()), []).append(f)
    for parts in kinds.values():
        if len(parts) < 3:
            continue
        for axis in (0, 1):
            other = 1 - axis
            pos = lambda f: (TOMM(f.GetPosition().x), TOMM(f.GetPosition().y))
            cur, rows = [], []
            for f in sorted(parts, key=lambda f: (round(pos(f)[other] / ROW_TOL), pos(f)[axis])):
                if cur and abs(pos(f)[other] - pos(cur[-1])[other]) <= ROW_TOL and pos(f)[axis] - pos(cur[-1])[axis] < ROW_PITCH:
                    cur.append(f)
                else:
                    if len(cur) >= 3:
                        rows.append(cur)
                    cur = [f]
            if len(cur) >= 3:
                rows.append(cur)
            out += [tuple(f.GetReference() for f in r) for r in rows]
    return out


def all_groups(board):
    """GROUPS plus the auto-detected rows no GROUPS entry already covers (auto rows first: the
    audit checks them)."""
    autos = [r for r in auto_rows(board) if not any(set(r) <= set(g) for g in GROUPS)]
    rest = [g for g in GROUPS if not any(set(g) & set(r) for r in autos)]
    return autos + rest


# plate names (SPEC.md "Module plates", rev 0 plate grid) printed after the header references
PLATES = {"J1": "M1 RADIO", "J2": "M2 TIMER", "J3": "M3 KEYPAD", "J4": "M4 WIRES", "J5": "M5 PROBE", "J6": "M6 SENSORS"}
LEGEND = [[("DEFUSE32 CARRIER", 1.5, 0.22), ("rev 3  2026-10", 1.0, 0.15)], [("JLCJLCJLCJLC", 1.0, 0.15)]]
SIDE_COST = {"top": 0.0, "left": 0.25, "right": 0.35, "bottom": 0.5}


def rect_dist(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    return math.hypot(dx, dy)


def rect_edges(b):
    p = [V((b[0], b[1])), V((b[2], b[1])), V((b[2], b[3])), V((b[0], b[3]))]
    return [pcbnew.SEG(p[i], p[(i + 1) % 4]) for i in range(4)]


def poly_near_rect(poly, pbb, b, gap):
    """True when polygon set poly (bbox pbb) comes within gap of rectangle b (all nm)."""
    if pbb[2] < b[0] - gap or pbb[0] > b[2] + gap or pbb[3] < b[1] - gap or pbb[1] > b[3] + gap:
        return False
    for e in rect_edges(b):
        if poly.SquaredDistanceToSeg(e) < gap * gap:
            return True
    # polygon entirely inside the rectangle
    o = poly.Outline(0)
    if o.PointCount():
        v = o.CPoint(0)
        if b[0] <= v.x <= b[2] and b[1] <= v.y <= b[3]:
            return True
    return False


def bbox_t(bb):
    return (bb.GetLeft(), bb.GetTop(), bb.GetRight(), bb.GetBottom())


def poly_rect_dist(poly, b):
    """Distance (nm) between a filled polygon set and rectangle b (0 when they overlap)."""
    best = min(poly.SquaredDistanceToSeg(e) for e in rect_edges(b))
    if best == 0:
        return 0.0
    o = poly.Outline(0)
    if o.PointCount():
        v = o.CPoint(0)
        if b[0] <= v.x <= b[2] and b[1] <= v.y <= b[3]:
            return 0.0
    return math.sqrt(best)


SCELL = MM(2.0)


class SilkMap:
    """Everything a silkscreen text must keep clear of, on one side of the board, in a grid index:
    pads and holes (mask openings), footprint silkscreen, courtyards, vias, placed texts; plus the
    tracks of that side for the "text over a track" penalty."""

    def __init__(self, board, side=pcbnew.F_SilkS):
        self.board = board
        self.side = side
        cu = F if side == pcbnew.F_SilkS else B
        crt_layer = pcbnew.F_CrtYd if side == pcbnew.F_SilkS else pcbnew.B_CrtYd
        self.idx = {}
        for fp in board.GetFootprints():
            for p in fp.Pads():
                if not (p.IsOnLayer(cu) or p.HasHole()):
                    continue
                s = pcbnew.SHAPE_POLY_SET()
                p.TransformShapeToPolygon(s, cu if p.IsOnLayer(cu) else F, 0, MAXERR, pcbnew.ERROR_OUTSIDE)
                if p.HasHole():
                    p.TransformHoleToPolygon(s, 0, MAXERR, pcbnew.ERROR_OUTSIDE)
                if s.OutlineCount():
                    self._add("pad", s, bbox_t(s.BBox()), fp.GetReference())
            for g in fp.GraphicalItems():
                if g.GetLayer() == side and g.GetClass() != "PCB_TEXT":
                    s = pcbnew.SHAPE_POLY_SET()
                    g.TransformShapeToPolygon(s, side, 0, MAXERR, pcbnew.ERROR_OUTSIDE)
                    if s.OutlineCount():
                        self._add("silk", s, bbox_t(s.BBox()), fp.GetReference())
        for g in board.GetDrawings():                   # board-level silk lines (callout leaders)
            if g.GetClass() == "PCB_SHAPE" and g.GetLayer() == side:
                s = pcbnew.SHAPE_POLY_SET()
                g.TransformShapeToPolygon(s, side, 0, MAXERR, pcbnew.ERROR_OUTSIDE)
                if s.OutlineCount():
                    self._add("silk", s, bbox_t(s.BBox()), None)
        self.crt, self.part = {}, {}
        inner = board_inner(MM(0.5))
        for fp in board.GetFootprints():
            c = fp.GetCourtyard(crt_layer)
            if not c.OutlineCount():
                continue
            ref = fp.GetReference()
            s = pcbnew.SHAPE_POLY_SET(c)
            self.crt[ref] = (s, bbox_t(s.BBox()))
            # the part as seen on the board (U1's antenna courtyard lies beyond the edge)
            onb = pcbnew.SHAPE_POLY_SET(c)
            onb.BooleanIntersection(inner)
            self.part[ref] = onb if onb.OutlineCount() else s
            # every courtyard, mounting holes too (a screw head would cover the text)
            self._add("crt", s, bbox_t(s.BBox()), ref)
        for v in board.GetTracks():
            if v.GetClass() == "PCB_VIA":
                c, r = pt(v.GetPosition()), v.GetWidth(F) / 2
                self._add("via", (c, r), (c[0] - r, c[1] - r, c[0] + r, c[1] + r), None)
            elif v.GetClass() == "PCB_TRACK" and v.GetLayer() == cu:
                self._add("track", (pcbnew.SEG(v.GetStart(), v.GetEnd()), v.GetWidth() / 2), bbox_t(v.GetBoundingBox()), None)
        self.edge = (MM(OX) + TEXT_EDGE, MM(OY) + TEXT_EDGE, MM(OX + D.BOARD_W) - TEXT_EDGE, MM(OY + D.BOARD_H) - TEXT_EDGE)

    def _add(self, kind, data, bb, ref):
        e = (kind, data, bb, ref)
        for cx in range(int(bb[0] // SCELL), int(bb[2] // SCELL) + 1):
            for cy in range(int(bb[1] // SCELL), int(bb[3] // SCELL) + 1):
                self.idx.setdefault((cx, cy), []).append(e)

    def add_text(self, b):
        self._add("text", None, b, None)

    def near(self, b, grow=MM(0.6)):
        seen = set()
        for cx in range(int((b[0] - grow) // SCELL), int((b[2] + grow) // SCELL) + 1):
            for cy in range(int((b[1] - grow) // SCELL), int((b[3] + grow) // SCELL) + 1):
                for e in self.idx.get((cx, cy), ()):
                    if id(e) not in seen:
                        seen.add(id(e))
                        yield e

    def ok(self, b, own=None, vias_out=None):
        """True when box b is a legal text spot. With vias_out (a list), vias are not a reason to
        refuse: the ones in the way are appended to it instead."""
        e = self.edge
        if b[0] < e[0] or b[1] < e[1] or b[2] > e[2] or b[3] > e[3]:
            return False
        for kind, data, bb, ref in self.near(b):
            if bb[2] < b[0] - SILK_GAP - MM(0.5) or bb[0] > b[2] + SILK_GAP + MM(0.5) or \
                    bb[3] < b[1] - SILK_GAP - MM(0.5) or bb[1] > b[3] + SILK_GAP + MM(0.5):
                continue
            if kind == "text":
                if rect_dist(b, bb) < TEXT_GAP:
                    return False
            elif kind == "via":
                (c, r) = data
                dx = max(b[0] - c[0], 0, c[0] - b[2])
                dy = max(b[1] - c[1], 0, c[1] - b[3])
                if math.hypot(dx, dy) < r + VIA_TEXT_GAP:
                    if vias_out is None:
                        return False
                    vias_out.append(c)
            elif kind in ("pad", "silk"):
                if poly_near_rect(data, bb, b, SILK_GAP):
                    return False
            elif kind == "crt":
                if poly_near_rect(data, bb, b, MM(0.02)):
                    return False
        return True

    def move_via(self, c_old, c_new, r):
        for key_, ents in self.idx.items():
            ents[:] = [e for e in ents if not (e[0] == "via" and e[1][0] == c_old)]
        self._add("via", (c_new, r), (c_new[0] - r, c_new[1] - r, c_new[0] + r, c_new[1] + r), None)

    def tracks_under(self, b):
        n = 0
        for kind, data, tbb, ref in self.near(b, 0):
            if kind != "track" or tbb[2] < b[0] or tbb[0] > b[2] or tbb[3] < b[1] or tbb[1] > b[3]:
                continue
            seg, hw = data
            if any(seg.Distance(e) < hw for e in rect_edges(b)) or (b[0] <= seg.A.x <= b[2] and b[1] <= seg.A.y <= b[3]):
                n += 1
        return n

    def d_own(self, b, ref):
        return poly_rect_dist(self.part[ref], b) if ref in self.part else 0.0

    def nearest_other(self, b, own):
        best = 1e12
        for ref, s in self.part.items():
            if ref == own or ref.startswith("H"):
                continue
            cbb = self.crt[ref][1]
            if rect_dist(b, cbb) >= best:
                continue
            best = min(best, poly_rect_dist(s, b))
        return best


class Unit:
    """One or more texts printed as a line (0 deg: left to right; 90 deg: bottom to top)."""

    def __init__(self, texts):
        self.texts = texts                      # PCB_TEXT / PCB_FIELD objects, sizes already set

    def layout(self, angle):
        """(w, h, [(text, dx, dy)]) where (dx, dy) moves the text position from the unit centre."""
        sizes = []
        for t in self.texts:
            t.SetTextAngleDegrees(angle)
            t.SetPosition(pcbnew.VECTOR2I(0, 0))
            bb = t.GetBoundingBox()
            sizes.append((bb.GetWidth(), bb.GetHeight(), (bb.GetLeft() + bb.GetRight()) / 2, (bb.GetTop() + bb.GetBottom()) / 2))
        out = []
        if angle == 0:
            w = sum(s[0] for s in sizes) + WORD_GAP * (len(sizes) - 1)
            h = max(s[1] for s in sizes)
            x = -w / 2
            for t, s in zip(self.texts, sizes):
                out.append((t, x + s[0] / 2 - s[2], -s[3]))
                x += s[0] + WORD_GAP
        else:
            h = sum(s[1] for s in sizes) + WORD_GAP * (len(sizes) - 1)
            w = max(s[0] for s in sizes)
            y = h / 2
            for t, s in zip(self.texts, sizes):
                out.append((t, -s[2], y - s[1] / 2 - s[3]))
                y -= s[1] + WORD_GAP
        return w, h, out

    def place(self, angle, c):
        w, h, items = self.layout(angle)
        for t, dx, dy in items:
            t.SetTextAngleDegrees(angle)
            t.SetPosition(V((c[0] + dx, c[1] + dy)))


def label_candidates(fp_box, w, h, angle):
    """(side, gap, offset, centre) spots for a w x h box around courtyard box fp_box."""
    x0, y0, x1, y1 = fp_box
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    out = []
    for gap in (0.15, 0.25, 0.4, 0.6, 0.9, 1.3, 1.8):
        g = MM(gap)
        for k in range(0, 13):
            for sgn in ((0,) if k == 0 else (1, -1)):
                off = sgn * k * MM(0.25)
                out.append(("top", gap, k * 0.25, (mx + off, y0 - g - h / 2)))
                out.append(("bottom", gap, k * 0.25, (mx + off, y1 + g + h / 2)))
                out.append(("left", gap, k * 0.25, (x0 - g - w / 2, my + off)))
                out.append(("right", gap, k * 0.25, (x1 + g + w / 2, my + off)))
    return out


def unit_box(c, w, h):
    return (c[0] - w / 2, c[1] - h / 2, c[0] + w / 2, c[1] + h / 2)


def beside(sm, ref, b):
    """True when label box b sits beside one side of its part (overlaps the part's x span or y span
    by SIDE_OVERLAP of its own width / height), not off a corner."""
    if ref not in sm.part:
        return True
    pb = bbox_t(sm.part[ref].BBox())
    ox = min(b[2], pb[2]) - max(b[0], pb[0])
    oy = min(b[3], pb[3]) - max(b[1], pb[1])
    return ox >= SIDE_OVERLAP * (b[2] - b[0]) or oy >= SIDE_OVERLAP * (b[3] - b[1])


def spot_score(sm, ref, b, side, gap, off, angle, part_long_h):
    d_own = sm.d_own(b, ref)
    if d_own > MAX_FROM_PART or not beside(sm, ref, b):
        return None
    if d_own > sm.nearest_other(b, ref) - AMBIG_MARGIN:
        return None
    s = 2.0 * TOMM(int(d_own)) + SIDE_COST[side] + 0.15 * off
    if (angle == 0) != part_long_h:
        s += 0.3
    s += 0.6 * min(sm.tracks_under(b), 4)
    return s


def part_box(sm, fp):
    ref = fp.GetReference()
    if ref in sm.part:
        return bbox_t(sm.part[ref].BBox())
    return bbox_t(fp.GetBoundingBox(False))


def ref_box(unit, angle, c):
    """Box of the first text (the reference) of a multi-text unit centred at c."""
    w, h, items = unit.layout(angle)
    t, dx, dy = items[0]
    t.SetTextAngleDegrees(angle)
    t.SetPosition(V((c[0] + dx, c[1] + dy)))
    return bbox_t(t.GetBoundingBox())


def ref_near(sm, ref, unit, angle, c):
    """For a reference printed with its plate name: the reference text itself beside the part and
    within MAX_FROM_PART (the plate name may run on past it)."""
    if len(unit.texts) < 2:
        return True
    rb = ref_box(unit, angle, c)
    return sm.d_own(rb, ref) <= MAX_FROM_PART and beside(sm, ref, rb)


def best_single(sm, fp, unit):
    ref = fp.GetReference()
    pb = part_box(sm, fp)
    long_h = (pb[2] - pb[0]) >= (pb[3] - pb[1])
    best = None
    for angle in (0, 90):
        w, h, _ = unit.layout(angle)
        for side, gap, off, c in label_candidates(pb, w, h, angle):
            b = unit_box(c, w, h)
            if best is not None and 2.0 * gap + SIDE_COST[side] > best[0]:
                continue
            if not sm.ok(b, ref):
                continue
            if len(unit.texts) > 1:
                if sm.d_own(b, ref) > MAX_FROM_PART or not ref_near(sm, ref, unit, angle, c):
                    continue
                s = 2.0 * TOMM(int(sm.d_own(b, ref))) + SIDE_COST[side] + 0.15 * off + 0.6 * min(sm.tracks_under(b), 4)
                if best is None or s < best[0]:
                    best = (s, angle, c, b)
                continue
            s = spot_score(sm, ref, b, side, gap, off, angle, long_h)
            if s is None:
                continue
            if best is None or s < best[0]:
                best = (s, angle, c, b)
    return best


def via_blocked_spots(sm, fp, unit):
    """Label spots that only vias are in the way of: [(score, angle, centre, box, [via centres])],
    best first."""
    ref = fp.GetReference()
    pb = part_box(sm, fp)
    long_h = (pb[2] - pb[0]) >= (pb[3] - pb[1])
    out = []
    for angle in (0, 90):
        w, h, _ = unit.layout(angle)
        for side, gap, off, c in label_candidates(pb, w, h, angle):
            b = unit_box(c, w, h)
            vs = []
            if not sm.ok(b, ref, vs) or not vs or len(vs) > 2:
                continue
            s = spot_score(sm, ref, b, side, gap, off, angle, long_h)
            if s is not None:
                out.append((s + 0.5 * len(vs), angle, c, b, vs))
    out.sort(key=lambda r: r[0])
    return out


def push_vias_off(ctx, sm, boxes, centres, segs=()):
    """Move the vias at centres out of the text boxes and off the silk segments segs (signal vias
    keep every track direction: see plan_via_move), keeping all clearances and staying off every
    placed text. True if done."""
    txn = Txn(ctx)
    moved = []

    def clear_of(q, r, bs):
        if any(pcbnew.SEG(V(a), V(b2)).Distance(V(q)) < r + SILK_GAP + LEADER_W / 2 + MM(0.01) for a, b2 in segs):
            return False
        return all(math.hypot(max(b[0] - q[0], 0, q[0] - b[2]), max(b[1] - q[1], 0, q[1] - b[3])) >= r + VIA_TEXT_GAP + MM(0.01)
                   for b in bs)
    for c in centres:
        v = None
        for t in ctx.board.GetTracks():
            if t.GetClass() == "PCB_VIA" and norm(sub(pt(t.GetPosition()), c)) < UM:
                v = t
                break
        if v is None or not ctx.movable(v):
            txn.rollback()
            return False
        r = v.GetWidth(F) / 2
        near_b = min(boxes, key=lambda b: rect_dist(b, (c[0], c[1], c[0], c[1])))
        away = sub(c, ((near_b[0] + near_b[2]) / 2, (near_b[1] + near_b[3]) / 2))
        dirs = sorted(OCT, key=lambda d: -dot(d, unit(away)))
        done = False
        fo = fanout_of(ctx, v)
        if fo is not None:
            # a GND fan-out: rebuilt at another spot round its pad, off the texts
            mk = txn.mark()
            if relocate_fanout(ctx, txn, fo, away):
                nv = [x for x in txn.touched(mk) if x.GetClass() == "PCB_VIA"]
                q = pt(nv[0].GetPosition()) if nv else None
                qb = (q[0] - r, q[1] - r, q[0] + r, q[1] + r) if q else None
                if q is not None and clear_of(q, r, boxes) and \
                        clear_of(q, r, [bb for k, dd, bb, rf in sm.near(qb) if k == "text"]):
                    moved.append((c, q, r))
                    continue
                txn.rollback(mk)
        for step in [MM(0.05 * k) for k in range(1, 25)]:
            for d in dirs[:5]:
                q = add(c, mul(d, step))
                if not clear_of(q, r, boxes):
                    continue
                qb = (q[0] - r, q[1] - r, q[0] + r, q[1] + r)
                if not clear_of(q, r, [bb for k, dd, bb, rf in sm.near(qb) if k == "text"]):
                    continue
                ch = plan_via_move(ctx, v, mul(d, step))
                ch = follow_anchors(ctx, ch) if ch is not None else None
                if ch is None or stale(ctx, txn, ch):
                    continue
                mk = txn.mark()
                txn.apply(ch)
                if txn.conflicts(mk, first=True):
                    txn.rollback(mk)
                    continue
                moved.append((c, q, r))
                done = True
                break
            if done:
                break
        if not done:
            txn.rollback()
            return False
    # no new jog on the nets whose vias moved
    nets = {it.GetNetCode() for it in txn.touched()}
    before = sum(count_jogs(c[2]) for c in ctx.chains if c[0] in nets)
    after = sum(count_jogs(c[2]) for c in chains(ctx.board, nets))
    if after > before:
        txn.rollback()
        return False
    txn.commit()
    for c, q, r in moved:
        sm.move_via(c, q, r)
    ctx.refresh()
    return True


def best_group(sm, fps, units, allow_vias=False):
    """One side, one line for a row/column of parts. Returns [(angle, centre, box)] or None; with
    allow_vias, [(score, [(angle, centre, box)], [via centres])] for lines that only vias (3 at
    most) are in the way of, best first."""
    boxes = [part_box(sm, fp) for fp in fps]
    xs = [((b[0] + b[2]) / 2, (b[1] + b[3]) / 2) for b in boxes]
    horizontal_row = (max(x for x, y in xs) - min(x for x, y in xs)) >= (max(y for x, y in xs) - min(y for x, y in xs))
    sides = ("top", "bottom") if horizontal_row else ("left", "right")
    best = None
    cands = []
    for side in sides:
        for angle in (0, 90):
            lay = [u.layout(angle) for u in units]
            for gap in (0.15, 0.25, 0.4, 0.6, 0.9, 1.3):
                g = MM(gap)
                if side == "top":
                    line = min(b[1] for b in boxes) - g
                    cs = [(xs[i][0], line - lay[i][1] / 2) for i in range(len(fps))]
                elif side == "bottom":
                    line = max(b[3] for b in boxes) + g
                    cs = [(xs[i][0], line + lay[i][1] / 2) for i in range(len(fps))]
                elif side == "left":
                    line = min(b[0] for b in boxes) - g
                    cs = [(line - lay[i][0] / 2, xs[i][1]) for i in range(len(fps))]
                else:
                    line = max(b[2] for b in boxes) + g
                    cs = [(line + lay[i][0] / 2, xs[i][1]) for i in range(len(fps))]
                total = 0.0
                ok = True
                placed = []
                vias = []
                for i, fp in enumerate(fps):
                    b = unit_box(cs[i], lay[i][0], lay[i][1])
                    if any(rect_dist(b, p) < SILK_GAP for p in placed) or \
                            not sm.ok(b, fp.GetReference(), vias if allow_vias else None):
                        ok = False
                        break
                    pb = boxes[i]
                    if len(units[i].texts) > 1:
                        if not ref_near(sm, fp.GetReference(), units[i], angle, cs[i]):
                            ok = False
                            break
                        s = 2.0 * gap + SIDE_COST[side]
                    else:
                        s = spot_score(sm, fp.GetReference(), b, side, gap, 0, angle, (pb[2] - pb[0]) >= (pb[3] - pb[1]))
                    if s is None:
                        ok = False
                        break
                    total += s
                    placed.append(b)
                if not ok:
                    continue
                conf = [(angle, cs[i], placed[i]) for i in range(len(fps))]
                if allow_vias:
                    if vias and len(set(vias)) <= 3:
                        cands.append((total + 0.5 * len(set(vias)), conf, sorted(set(vias))))
                elif best is None or total < best[0]:
                    best = (total, conf)
    if allow_vias:
        return sorted(cands, key=lambda c: c[0])
    return best[1] if best else None



U1_MARK_OLD = [(-9.2, -6.0), (-9.7, -6.0), (-9.2, -6.5)]
U1_MARK_NEW = [(-9.2, -5.93), (-9.58, -5.93), (-9.2, -6.31)]


def sync_u1_mark(board):
    """U1's pin-1 triangle as in the local library (gen_lib.py, rev 2.1): smaller and off the
    board edge. Returns True if the board's copy was changed."""
    fp = board.FindFootprintByReference("U1")
    a = math.radians(fp.GetOrientationDegrees())
    o = pt(fp.GetPosition())

    def to_board(lx, ly):
        lx, ly = MM(lx), MM(ly)
        return (o[0] + lx * math.cos(a) + ly * math.sin(a), o[1] - lx * math.sin(a) + ly * math.cos(a))
    old = [to_board(*p) for p in U1_MARK_OLD]
    for g in fp.GraphicalItems():
        if g.GetLayer() != pcbnew.F_SilkS or g.GetClass() != "PCB_SHAPE" or g.GetShape() != pcbnew.SHAPE_T_POLY:
            continue
        pts_ = [pt(g.GetPolyShape().COutline(0).CPoint(i)) for i in range(g.GetPolyShape().COutline(0).PointCount())]
        if len(pts_) >= 3 and all(any(norm(sub(p, q)) < MM(0.01) for p in pts_) for q in old):
            s = pcbnew.SHAPE_POLY_SET()
            s.NewOutline()
            for q in U1_MARK_NEW + U1_MARK_NEW[:1] * (len(pts_) - len(U1_MARK_NEW)):
                b = to_board(*q)
                s.Append(int(round(b[0])), int(round(b[1])))
            g.SetPolyShape(s)
            return True
    return False


def plate_text(board, name, h, stroke):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(name)
    t.SetLayer(pcbnew.F_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(MM(h), MM(h)))
    t.SetTextThickness(MM(stroke))
    t.SetKeepUpright(True)
    return t


def ref_setup(fp, size, layer=pcbnew.F_SilkS):
    t = fp.Reference()
    t.SetVisible(True)
    t.SetLayer(layer)
    t.SetMirrored(layer == pcbnew.B_SilkS)
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(REF_STROKE))
    t.SetKeepUpright(True)
    return t


def place_refs_top(board, fps, size, ctx=None):
    """Top-side references at one size: groups (whole row, else runs of it), then single parts,
    biggest first; the plate headers J1-J6 first try their reference and plate name as one line.
    With ctx, a part left without a spot may get one by moving one or two vias that are in the way
    (plan_via_move, all clearances kept). Returns (SilkMap, placed, missing, vias moved,
    {ref: plate text placed with it})."""
    sm = SilkMap(board)
    pushed = 0
    units, plates = {}, {}
    for ref, fp in fps.items():
        if ref.startswith("H"):
            fp.Reference().SetVisible(False)
            continue
        units[ref] = Unit([ref_setup(fp, size)])
        if ref in PLATES:
            plates[ref] = plate_text(board, PLATES[ref], size, REF_STROKE)
    with_plate = lambda r: Unit(units[r].texts + [plates[r]]) if r in plates else units[r]
    placed, used = {}, {}
    RANGES[:] = []
    for grp in all_groups(board):
        members = [r for r in grp if r in fps]
        runs = [members[i:i + n] for n in range(len(members), 1, -1) for i in range(len(members) - n + 1)]
        for run in runs:
            if any(r in placed for r in run):
                continue
            if len(run) < len(members) and len(members) >= 3 and not any(r in placed for r in members) \
                    and all(r[0] in "RC" for r in members):
                # the whole row found no line: one range label ("R16-19") for it rather than
                # scattered labels that cannot line up (and may find no spot at all)
                t = plate_text(board, range_label(members), size, REF_STROKE)
                best = best_range_spot(sm, [fps[r] for r in members], Unit([t]))
                if best is None and ctx is not None:
                    for sc, angle, c, b, vs in best_range_spot(sm, [fps[r] for r in members], Unit([t]), vias=True)[:10]:
                        if push_vias_off(ctx, sm, [b], vs):
                            pushed += len(vs)
                            best = (sc, angle, c, b)
                            break
                if best is not None:
                    sc, angle, c, b = best
                    Unit([t]).place(angle, c)
                    board.Add(t)
                    sm.add_text(b)
                    RANGES.append((t.GetText(), members))
                    for r in members:
                        fps[r].Reference().SetVisible(False)
                        placed[r] = b
                    break
            res, ulist = None, None
            # references alone first: plate names come last (place_labels), so they never take the
            # only spot of a small part's label
            for us in ([units[r] for r in run],):
                res = best_group(sm, [fps[r] for r in run], us)
                if res is None and ctx is not None and len(run) == len(members):
                    # the whole row, with one to three vias moved out of its line
                    for s, conf, vs in best_group(sm, [fps[r] for r in run], us, True)[:8]:
                        if push_vias_off(ctx, sm, [x[2] for x in conf], vs):
                            pushed += len(vs)
                            res = conf
                            break
                if res is not None:
                    ulist = us
                    break
            if res is None:
                continue
            for r, u, (angle, c, b) in zip(run, ulist, res):
                u.place(angle, c)
                sm.add_text(b)
                placed[r] = b
                if len(u.texts) > 1:
                    used[r] = plates[r]
    area = lambda r: (lambda b: (b[2] - b[0]) * (b[3] - b[1]))(part_box(sm, fps[r]))
    missing = []
    def n_spots(r):
        """Legal spots a part's label has on the map as it is now (fewest first: most constrained)."""
        fp = fps[r]
        pb = part_box(sm, fp)
        long_h = (pb[2] - pb[0]) >= (pb[3] - pb[1])
        n = 0
        for angle in (0, 90):
            w, h, _ = units[r].layout(angle)
            for side, gap, off, c in label_candidates(pb, w, h, angle):
                b = unit_box(c, w, h)
                if sm.ok(b, r) and spot_score(sm, r, b, side, gap, off, angle, long_h) is not None:
                    n += 1
        return n
    rest = [r for r in units if r not in placed]
    spots = {r: n_spots(r) for r in rest}
    # parts with no spot next to them get their callout first, before the other labels take the
    # free space a short way off
    EARLY_CALLOUTS[:] = []
    if ctx is not None:
        for ref in sorted([r for r in rest if spots[r] == 0], key=lambda r: -area(r)):
            if place_callout(board, sm, fps[ref], units[ref], ctx):
                placed[ref] = None
                EARLY_CALLOUTS.append(ref)
        rest = [r for r in rest if r not in placed]
    for ref in sorted(rest, key=lambda r: (spots[r] == 0, spots[r], -area(r))):
        best, u = None, None
        for cand in [units[ref]]:
            best = best_single(sm, fps[ref], cand)
            if best is None and ctx is not None:
                for s, angle, c, b, vs in via_blocked_spots(sm, fps[ref], cand)[:12]:
                    if push_vias_off(ctx, sm, [b], vs):
                        pushed += len(vs)
                        best = (s, angle, c, b)
                        break
            if best is not None:
                u = cand
                break
        if best is None:
            missing.append(ref)
            continue
        s, angle, c, b = best
        u.place(angle, c)
        sm.add_text(b)
        placed[ref] = b
        if len(u.texts) > 1:
            used[ref] = plates[ref]
    return sm, placed, missing, pushed, used




RANGES = []                                 # (range label text, members) placed by place_refs_top
EARLY_CALLOUTS = []                         # references place_refs_top gave a callout
LEADER_W = MM(0.15)                         # silk leader from a callout label to its part
LEADER_GAP = MM(0.2)                        # the leader stops this short of the part outline
CALLOUT_REFS = []                           # references placed as callouts (their label stays put)
CALLOUT_GAPS = (0.6, 0.9, 1.15, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 7.0, 8.0, 10.0)  # mm, label box to part


def nearest_on_poly(poly, p):
    """Nearest point to p on the outline of polygon set poly (float tuples, nm)."""
    best, bd = None, None
    for i in range(poly.OutlineCount()):
        o = poly.Outline(i)
        n = o.PointCount()
        for k in range(n):
            a, b = pt(o.CPoint(k)), pt(o.CPoint((k + 1) % n))
            d = sub(b, a)
            L2 = dot(d, d)
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, dot(sub(p, a), d) / L2))
            q = add(a, mul(d, t))
            dd = norm(sub(p, q))
            if bd is None or dd < bd:
                best, bd = q, dd
    return best


def leader_ok(sm, p0, p1, own, vias_out=None):
    """True when a leader p0-p1 keeps 0.15 mm from pads, silk, text and vias, stays off every
    courtyard but its own part's and inside the edge band (with vias_out, vias in the way are
    collected there instead)."""
    hw = LEADER_W / 2
    g = SILK_GAP + hw
    seg = pcbnew.SEG(V(p0), V(p1))
    e = sm.edge
    for p in (p0, p1):
        if not (e[0] <= p[0] <= e[2] and e[1] <= p[1] <= e[3]):
            return False
    lb = (min(p0[0], p1[0]), min(p0[1], p1[1]), max(p0[0], p1[0]), max(p0[1], p1[1]))
    for kind, data, bb, ref in sm.near(lb):
        if bb[2] < lb[0] - MM(0.6) or bb[0] > lb[2] + MM(0.6) or bb[3] < lb[1] - MM(0.6) or bb[1] > lb[3] + MM(0.6):
            continue
        if kind in ("pad", "silk"):
            if data.SquaredDistanceToSeg(seg) < g * g:
                return False
        elif kind == "crt":
            pass                                # a thin leader may cross another part's outline
        elif kind == "via":
            c, r = data
            if seg.Distance(V(c)) < r + g:
                if vias_out is None:
                    return False
                vias_out.append(c)
        elif kind == "text":
            if any(seg.Distance(x) < g for x in rect_edges(bb)) or \
                    (bb[0] <= p0[0] <= bb[2] and bb[1] <= p0[1] <= bb[3]):
                return False
    return True


def place_callout(board, sm, fp, lab, ctx=None, row=None):
    """A label a short way off (1 - 10 mm) in free space with a thin silk leader to its part, for a
    part with no free spot next to it; with ctx, up to two vias in the way of the label or the
    leader may be moved. With row (a list of footprints), the leader goes to the row's bounding
    box (range labels). Returns True if placed (label and leader added)."""
    if row:
        boxes = [part_box(sm, f) for f in row]
        pb = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
        part = box_poly(pb, 0)
        ref = tuple(f.GetReference() for f in row)
    else:
        ref = fp.GetReference()
        if ref not in sm.part:
            return False
        part = sm.part[ref]
        pb = bbox_t(part.BBox())
    best = callout_search(sm, part, pb, ref, lab, None)
    if best is None and ctx is not None:
        for cand in callout_search(sm, part, pb, ref, lab, ctx)[:10]:
            s, angle, c, b, p0, p1, vs = cand
            if push_vias_off(ctx, sm, [b], vs, [(p0, p1)]):
                best = cand[:6]
                break
    if best is None:
        return False
    s, angle, c, b, p0, p1 = best
    lab.place(angle, c)
    sm.add_text(b)
    ln = pcbnew.PCB_SHAPE(board)
    ln.SetShape(pcbnew.SHAPE_T_SEGMENT)
    ln.SetStart(V(p0))
    ln.SetEnd(V(p1))
    ln.SetLayer(pcbnew.F_SilkS)
    ln.SetWidth(LEADER_W)
    board.Add(ln)
    s2 = pcbnew.SHAPE_POLY_SET()
    ln.TransformShapeToPolygon(s2, pcbnew.F_SilkS, 0, MAXERR, pcbnew.ERROR_OUTSIDE)
    sm._add("silk", s2, bbox_t(s2.BBox()), None)
    return True


def callout_search(sm, part, pb, ref, lab, allow_vias):
    """Best callout (score, angle, centre, box, leader start, leader end), or with allow_vias the
    candidates that only vias (two at most) block, with their via centres, best first."""
    best = None
    cands = []
    for angle in (0, 90):
        w, h, _ = lab.layout(angle)
        x0, y0, x1, y1 = pb
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        for gap in CALLOUT_GAPS:
            g = MM(gap)
            for k in range(0, 21):
                for sgn in ((0,) if k == 0 else (1, -1)):
                    off = sgn * k * MM(0.5)
                    for side, c in (("top", (mx + off, y0 - g - h / 2)), ("bottom", (mx + off, y1 + g + h / 2)),
                                    ("left", (x0 - g - w / 2, my + off)), ("right", (x1 + g + w / 2, my + off))):
                        b = unit_box(c, w, h)
                        vs = []
                        if not sm.ok(b, ref, vs if allow_vias else None):
                            continue
                        if allow_vias is None and best is not None and TOMM(int(rect_dist(b, pb))) > best[0]:
                            continue
                        bc = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
                        # leader end: the nearest point of the part's courtyard, else a corner or
                        # side middle of it (whichever line is clear)
                        ends = [nearest_on_poly(part, bc), (x0, y0), (x1, y0), (x1, y1), (x0, y1),
                                (mx, y0), (mx, y1), (x0, my), (x1, my)]
                        for p1 in ends:
                            d = sub(p1, bc)
                            if norm(d) == 0:
                                continue
                            u = unit(d)
                            # leave the text box through its edge, 0.2 mm out
                            tx = ((b[2] - bc[0]) / abs(u[0])) if abs(u[0]) > 1e-9 else 1e18
                            ty = ((b[3] - bc[1]) / abs(u[1])) if abs(u[1]) > 1e-9 else 1e18
                            t0 = min(tx, ty) + MM(0.2)
                            p0 = add(bc, mul(u, t0))
                            p1 = sub(p1, mul(u, LEADER_GAP))       # stop short of the part outline
                            if dot(sub(p1, p0), u) < MM(0.3):
                                continue
                            lv = []
                            # pull the end back (up to 0.3 mm more) until it clears the part's
                            # own pads by the silk-to-mask gap too
                            ok = False
                            for k2 in range(7):
                                q1 = sub(p1, mul(u, MM(0.05) * k2))
                                if dot(sub(q1, p0), u) < MM(0.3):
                                    break
                                lv = []
                                if leader_ok(sm, p0, q1, ref, lv if allow_vias else None):
                                    ok, p1 = True, q1
                                    break
                            if not ok:
                                continue
                            s = TOMM(int(norm(sub(p1, p0)))) + 0.6 * min(sm.tracks_under(b), 4) + 0.1 * k
                            if allow_vias:
                                allv = sorted(set(vs + lv))
                                if 0 < len(allv) <= 3:
                                    cands.append((s + 0.5 * len(allv), angle, c, b, p0, p1, allv))
                                    break
                                continue
                            if best is None or s < best[0]:
                                best = (s, angle, c, b, p0, p1)
                            break
        if allow_vias is None and best is not None and best[0] < 2.5:
            break
    if allow_vias:
        return sorted(cands, key=lambda r: r[0])
    return best



def place_ref_bottom(board, smb, fp, size):
    """Last resort before hiding: the reference on the bottom silkscreen, at or next to the part
    (mirrored, reads from below). Returns True if placed."""
    t = ref_setup(fp, size, pcbnew.B_SilkS)
    u = Unit([t])
    ref = fp.GetReference()
    pb = part_box(smb, fp) if ref in smb.part else bbox_t(fp.GetBoundingBox(False))
    mx, my = (pb[0] + pb[2]) / 2, (pb[1] + pb[3]) / 2
    best = None
    for angle in (0, 90):
        w, h, _ = u.layout(angle)
        cands = [("top", 0.0, 0.0, (mx, my))] + label_candidates(pb, w, h, angle)
        for side, gap, off, c in cands:
            b = unit_box(c, w, h)
            if not smb.ok(b, ref):
                continue
            d = TOMM(int(rect_dist(b, pb)))
            if d > 2.0:
                continue
            s = 2 * d + 0.15 * off + 0.6 * min(smb.tracks_under(b), 4)
            if best is None or s < best[0]:
                best = (s, angle, c, b)
    if best is None:
        return False
    s, angle, c, b = best
    u.place(angle, c)
    smb.add_text(b)
    return True


def plate_spot(sm, fp, unit):
    """A spot for a plate name on its own: within 3 mm of the header, along one of its sides,
    nearer the header than any other part (plate names are text, not references)."""
    ref = fp.GetReference()
    pb = part_box(sm, fp)
    x0, y0, x1, y1 = pb
    mx, my = (x0 + x1) / 2, (y0 + y1) / 2
    best = None
    for angle in (0, 90):
        w, h, _ = unit.layout(angle)
        for gap in (0.15, 0.3, 0.5, 0.8, 1.2, 1.8, 2.5, 3.0):
            g = MM(gap)
            span_x, span_y = (x1 - x0) / 2, (y1 - y0) / 2
            for k in range(0, 41):
                for sgn in ((0,) if k == 0 else (1, -1)):
                    o = sgn * k * MM(0.5)
                    for side, c in (("top", (mx + o, y0 - g - h / 2)), ("bottom", (mx + o, y1 + g + h / 2)),
                                    ("left", (x0 - g - w / 2, my + o)), ("right", (x1 + g + w / 2, my + o))):
                        if side in ("top", "bottom") and abs(o) > span_x or side in ("left", "right") and abs(o) > span_y:
                            continue
                        b = unit_box(c, w, h)
                        if not sm.ok(b, ref):
                            continue
                        d = sm.d_own(b, ref)
                        if d > MM(3.0) or d > sm.nearest_other(b, ref):
                            continue
                        sc = TOMM(int(d)) + SIDE_COST[side] + 0.6 * min(sm.tracks_under(b), 4)
                        if best is None or sc < best[0]:
                            best = (sc, angle, c, b)
    return best


def range_label(refs):
    """'R16-19' for consecutive references of one prefix, 'C14,16' for others of one prefix, in
    part order (left to right / top to bottom as the row runs)."""
    import re
    parts = [re.match(r"([A-Z]+)(\d+)$", r) for r in refs]
    if all(parts) and len({m.group(1) for m in parts}) == 1:
        nums = [int(m.group(2)) for m in parts]
        if sorted(nums) == list(range(min(nums), min(nums) + len(nums))) and len(nums) > 2:
            return "%s%d-%d" % (parts[0].group(1), min(nums), max(nums))
        return parts[0].group(1) + ",".join(str(n) for n in nums)
    return ",".join(refs)


def best_range_spot(sm, fps, unit, vias=False):
    """Best spot for a range label of a row of parts: beside the row's bounding box (overlapping
    its span by SIDE_OVERLAP), within MAX_FROM_PART of the nearest member and nearer the row than
    any other part. With vias, the spots only one or two vias are in the way of, best first, as
    [(score, angle, centre, box, [via centres])]."""
    boxes = [part_box(sm, fp) for fp in fps]
    rb = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    refs = [fp.GetReference() for fp in fps]
    best, cands = None, []
    for angle in (0, 90):
        w, h, _ = unit.layout(angle)
        for side, gap, off, c in label_candidates(rb, w, h, angle):
            b = unit_box(c, w, h)
            vs = []
            if not sm.ok(b, None, vs if vias else None) or (vias and not 0 < len(vs) <= 2):
                continue
            ox = min(b[2], rb[2]) - max(b[0], rb[0])
            oy = min(b[3], rb[3]) - max(b[1], rb[1])
            # a range label is a board text, longer than its row is wide: 25 % overlap is enough
            if not (ox >= 0.25 * (b[2] - b[0]) or oy >= 0.25 * (b[3] - b[1])):
                continue
            d = min(sm.d_own(b, r) for r in refs)
            if d > MAX_FROM_PART:
                continue
            others = min([poly_rect_dist(s, b) for r, s in sm.part.items()
                          if r not in refs and not r.startswith("H") and rect_dist(b, sm.crt[r][1]) < MM(3)] + [MM(10)])
            if others < d + AMBIG_MARGIN:
                continue
            sc = 2.0 * TOMM(int(d)) + SIDE_COST[side] + 0.15 * off + 0.6 * min(sm.tracks_under(b), 4)
            if vias:
                cands.append((sc + 0.5 * len(vs), angle, c, b, vs))
            elif best is None or sc < best[0]:
                best = (sc, angle, c, b)
    if vias:
        return sorted(cands, key=lambda r: r[0])
    return best


def place_labels(board, log=print):
    """References (one size for all), plate names, legend. Returns a dict with the size used,
    references put on the bottom side, hidden references, plate names left out, legend spots."""
    # board-level silkscreen (old legend, plate names, callout leaders) is rebuilt
    for d in [d for d in board.GetDrawings() if d.GetClass() in ("PCB_TEXT", "PCB_SHAPE")
              and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]:
        board.Delete(d)
    if sync_u1_mark(board):
        log("  U1 pin-1 mark updated from the local library (clear of the board edge)")
    fps = {fp.GetReference(): fp for fp in board.GetFootprints()}
    ctx = Ctx(board)
    tries = []
    pushed = 0
    for size in REF_SIZES:
        sm, placed, missing, n, used = place_refs_top(board, fps, size, ctx)
        pushed += n
        tries.append((len(missing), -size, size))
        log("  %.1f mm references: %d on top%s" % (size, len(placed), ", no top spot for " + " ".join(missing) if missing else ""))
        if not missing:
            break
    size = min(tries)[2]
    if tries[-1][2] != size:
        sm, placed, missing, n, used = place_refs_top(board, fps, size, ctx)
        pushed += n
    # no free spot next to the part: a label a short way off with a leader to its part
    callouts = list(EARLY_CALLOUTS)
    for ref in list(missing):
        u = Unit([ref_setup(fps[ref], size)])
        if place_callout(board, sm, fps[ref], u, ctx):
            callouts.append(ref)
            missing.remove(ref)
    CALLOUT_REFS[:] = callouts
    if callouts:
        log("  callouts with a leader: %s" % " ".join(callouts))
    # a row of like parts whose members have no spot (boxed in by each other, the parts around them
    # and their silk, so not even a leader can reach them without crossing silk): one range label
    # ("R16-R19") beside the row, in part order, and the members' own references hidden
    grouped = {}
    for grp in all_groups(board):
        members = [r for r in grp if r in fps and r not in callouts]
        if len(members) < 2 or not any(r in missing for r in members) or not all(r[0] in "RC" for r in members):
            continue
        txt = range_label(members)
        t = plate_text(board, txt, size, REF_STROKE)
        was = {r: fps[r].Reference().IsVisible() for r in members}
        for r in members:                       # the members' own labels make room for it
            fps[r].Reference().SetVisible(False)
        sm2 = text_map(board, pcbnew.F_SilkS)
        best = best_range_spot(sm2, [fps[r] for r in members], Unit([t]))
        if best is None:
            for sc, angle, c, b, vs in best_range_spot(sm2, [fps[r] for r in members], Unit([t]), vias=True)[:10]:
                if push_vias_off(ctx, sm2, [b], vs):
                    pushed += len(vs)
                    best = (sc, angle, c, b)
                    break
        if best is not None:
            s, angle, c, b = best
            Unit([t]).place(angle, c)
            board.Add(t)
            sm = sm2
            sm.add_text(b)
        elif place_callout(board, sm2, None, Unit([t]), ctx, row=[fps[r] for r in members]):
            board.Add(t)
            sm = sm2
            callouts.append(txt)
        else:
            for r, v in was.items():
                fps[r].Reference().SetVisible(v)
            continue
        for r in members:
            fps[r].Reference().SetVisible(False)
            if r in missing:
                missing.remove(r)
        grouped[txt] = members
    if grouped:
        log("  range labels for rows without a spot per part: %s" % ", ".join(grouped))
    smb = SilkMap(board, pcbnew.B_SilkS)
    # rev 3: never on the bottom silkscreen for a top-side part (owner's review); what has neither
    # a spot nor a callout is hidden and reported
    bottom, hidden = [], []
    for ref in missing:
        fps[ref].Reference().SetVisible(False)
        hidden.append(ref)
    legend = place_legend(board, sm, smb, log)          # before the plate names: those are optional
    # plate names after the header references (same line), else anywhere next to the header
    no_plate = []
    for ref, p in used.items():                             # placed with the reference already
        board.Add(p)
    for ref, name in PLATES.items():
        if ref in used:
            continue
        fp = fps.get(ref)
        t = fp.Reference() if fp else None
        if t is None or not t.IsVisible() or t.GetLayer() != pcbnew.F_SilkS:
            no_plate.append(ref)
            continue
        p = plate_text(board, name, size, REF_STROKE)
        angle = int(round(t.GetDrawRotation().AsDegrees())) % 180
        rb = bbox_t(t.GetBoundingBox())
        p.SetTextAngleDegrees(angle)
        p.SetPosition(pcbnew.VECTOR2I(0, 0))
        pbb = p.GetBoundingBox()
        w, h = pbb.GetWidth(), pbb.GetHeight()
        off = ((pbb.GetLeft() + pbb.GetRight()) / 2, (pbb.GetTop() + pbb.GetBottom()) / 2)
        cy, cx = (rb[1] + rb[3]) / 2, (rb[0] + rb[2]) / 2
        if angle == 0:
            spots = [(rb[2] + WORD_GAP + w / 2, cy), (rb[0] - WORD_GAP - w / 2, cy)]
        else:
            spots = [(cx, rb[1] - WORD_GAP - h / 2), (cx, rb[3] + WORD_GAP + h / 2)]
        done = False
        for c in spots:
            b = unit_box(c, w, h)
            vs = []
            if not sm.ok(b, ref, vs) or sm.d_own(b, ref) > MAX_FROM_PART + MM(2) or len(vs) > 2:
                continue
            if vs and not push_vias_off(ctx, sm, [b], vs):
                continue
            pushed += len(vs)
            p.SetPosition(V((c[0] - off[0], c[1] - off[1])))
            sm.add_text(b)
            board.Add(p)
            done = True
            break
        if not done:
            # the reference and the plate name as one line somewhere else around the header
            keep = (pt(t.GetPosition()), t.GetTextAngleDegrees())
            sm2 = text_map(board, pcbnew.F_SilkS, exclude=(ref,))
            best = best_single(sm2, fp, Unit([t, p]))
            if best is None:
                for s, angle, c, b, vs in via_blocked_spots(sm2, fp, Unit([t, p]))[:8]:
                    if push_vias_off(ctx, sm2, [b], vs):
                        pushed += len(vs)
                        best = (s, angle, c, b)
                        break
            if best is not None:
                s, angle, c, b = best
                Unit([t, p]).place(angle, c)
                board.Add(p)
                sm = text_map(board, pcbnew.F_SilkS)
                done = True
            else:
                t.SetTextAngleDegrees(keep[1])
                t.SetPosition(V(keep[0]))
                # the plate name on its own next to the header (the reference stays where it is)
                sm2 = text_map(board, pcbnew.F_SilkS)
                best = plate_spot(sm2, fp, Unit([p]))
                if best is not None:
                    s, angle, c, b = best
                    Unit([p]).place(angle, c)
                    board.Add(p)
                    sm = text_map(board, pcbnew.F_SilkS)
                    done = True
        if not done:
            no_plate.append(ref)
    return {"size": size, "bottom": bottom, "hidden": hidden, "no_plate": no_plate, "legend": legend, "vias_moved": pushed, "callouts": callouts}


def place_legend(board, sm, smb, log=print):
    """Board name / revision / date and the JLCPCB order-number placeholder in clear space on the
    top silkscreen (spots with the fewest tracks underneath, away from parts), else on the bottom."""
    sides = [(pcbnew.F_SilkS, sm), (pcbnew.B_SilkS, smb)]
    where = []
    for block in LEGEND:
        done = False
        for layer, smap in sides:
            texts = []
            for s, h, w in block:
                t = pcbnew.PCB_TEXT(board)
                t.SetText(s)
                t.SetLayer(layer)
                t.SetTextSize(pcbnew.VECTOR2I(MM(h), MM(h)))
                t.SetTextThickness(MM(w))
                t.SetKeepUpright(True)
                if layer == pcbnew.B_SilkS:
                    t.SetMirrored(True)
                texts.append(t)
            # stacked lines, centred
            sizes = []
            for t in texts:
                t.SetPosition(pcbnew.VECTOR2I(0, 0))
                bb = t.GetBoundingBox()
                sizes.append((bb.GetWidth(), bb.GetHeight(), (bb.GetLeft() + bb.GetRight()) / 2, (bb.GetTop() + bb.GetBottom()) / 2))
            W = max(s[0] for s in sizes)
            H = sum(s[1] for s in sizes) + MM(0.3) * (len(sizes) - 1)
            best = None
            step = MM(0.5)
            y = MM(OY) + TEXT_EDGE + H / 2
            while y <= MM(OY + D.BOARD_H) - TEXT_EDGE - H / 2:
                x = MM(OX) + TEXT_EDGE + W / 2
                while x <= MM(OX + D.BOARD_W) - TEXT_EDGE - W / 2:
                    b = (x - W / 2, y - H / 2, x + W / 2, y + H / 2)
                    if smap.ok(b, None):
                        dmin = min([poly_rect_dist(s, b) for r, s in smap.part.items() if rect_dist(b, smap.crt[r][1]) < MM(5)] + [MM(5)])
                        sc = 1.0 * smap.tracks_under(b) - 0.3 * TOMM(int(dmin))
                        if best is None or sc < best[0]:
                            best = (sc, x, y, b)
                    x += step
                y += step
            if best is None:
                continue
            sc, x, y, b = best
            top = y - H / 2
            for t, s in zip(texts, sizes):
                t.SetPosition(V((x - s[2], top + s[1] / 2 - s[3])))
                top += s[1] + MM(0.3)
                board.Add(t)
            smap.add_text(b)
            where.append("%s at (%.1f, %.1f)" % (board.GetLayerName(layer), TOMM(int(x)) - OX, TOMM(int(y)) - OY))
            done = True
            break
        if not done:
            where.append("no room for %r" % block[0][0])
    return where


# ------------------------------------------------------------------------------ checks, steps
def drop_items(path, uuids):
    """Remove the track / via blocks with these uuids from a saved board file (a transaction's
    deletions only reach the board on commit: the DRC copy must not have them)."""
    if not uuids:
        return
    lines = open(path).read().split("\n")
    out, blk = [], None
    for ln in lines:
        if blk is None and (ln.startswith("\t(segment") or ln.startswith("\t(via") or ln.startswith("\t(arc")):
            blk = [ln]
            if ln.rstrip().endswith(")") and ln.count("(") == ln.count(")"):
                if not any('(uuid "%s")' % u in ln for u in uuids):
                    out.append(ln)
                blk = None
            continue
        if blk is not None:
            blk.append(ln)
            if ln == "\t)":
                text = "\n".join(blk)
                if not any('"%s"' % u in text for u in uuids):
                    out.extend(blk)
                blk = None
            continue
        out.append(ln)
    open(path, "w").write("\n".join(out))


def drc_check(board, ignore_gnd=True, drop=()):
    """KiCad DRC (all severities) on a temporary copy of the board with this project's rules.
    Returns ([(type, description, [uuids])], unconnected count); with ignore_gnd, missing GND
    connections and dangling GND vias are left out (the pours that make them come later)."""
    import shutil
    import tempfile
    d = tempfile.mkdtemp(prefix="d32polish")
    name = os.path.basename(BOARD)
    base = os.path.splitext(name)[0]
    src = os.path.dirname(os.path.abspath(BOARD))
    for ext in (".kicad_pro", ".kicad_dru"):
        if os.path.exists(os.path.join(src, base + ext)):
            shutil.copy(os.path.join(src, base + ext), d)
    path = os.path.join(d, name)
    pcbnew.SaveBoard(path, board)
    drop_items(path, set(drop))
    out = os.path.join(d, "drc.json")
    subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--format", "json", "-o", out, path],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rep = json.load(open(out))
    shutil.rmtree(d, ignore_errors=True)
    res = []
    for v in rep.get("violations", []) + rep.get("unconnected_items", []):
        gnd = all("[GND]" in i.get("description", "") for i in v["items"])
        if ignore_gnd and gnd and v["type"] in ("unconnected_items", "via_dangling", "track_dangling"):
            continue
        if ignore_gnd and v["type"].startswith(("silk", "text_", "courtyard", "lib_footprint")):
            continue                            # silkscreen is redone later; this check is for copper
        res.append((v["type"], v["description"], [i["uuid"] for i in v["items"]]))
    return res


def fix_fanout_shorts(board, log=print):
    """A GND fan-out via or stub that a router track runs into (the fan-out spots were chosen
    before routing; a session imported onto a board whose fan-out came out differently can hit
    one): the fan-out is rebuilt at another spot round its pad, away from the other item.
    Returns how many."""
    n = 0
    for _ in range(12):
        bad = [v for v in drc_check(board) if v[0] in ("shorting_items", "clearance", "hole_clearance", "hole_to_hole")]
        if not bad:
            break
        ctx = Ctx(board)
        byuid = {uid(t): t for t in board.GetTracks()}
        done = 0
        for typ, desc, uids in bad:
            items = [byuid[u] for u in uids if u in byuid]
            fo = None
            for it in items:
                fo = fanout_of(ctx, it)
                if fo is not None:
                    break
            if fo is None:
                continue
            other = [it for it in items if it.GetNetname() != "GND"]
            away = (0.0, 0.0)
            if other:
                o = other[0]
                oc = pt(o.GetPosition()) if o.GetClass() == "PCB_VIA" else \
                    pt(pcbnew.SEG(o.GetStart(), o.GetEnd()).NearestPoint(fo[0].GetPosition()))
                away = sub(pt(fo[0].GetPosition()), oc)
            txn = Txn(ctx)
            if relocate_fanout(ctx, txn, fo, away) and not txn.conflicts(first=True):
                txn.commit()
                done += 1
                log("  fan-out of %s.%s rebuilt clear of %s" % (fo[2].GetParentFootprint().GetReference(), fo[2].GetNumber(),
                                                                   other[0].GetNetname() if other else "?"))
                break                       # the DRC list now names deleted items: check again
            else:
                txn.rollback()
        n += done
        if not done:
            break
    return n


def fix_clearances(board, log=print):
    """Freerouting leaves a few tracks a few um inside a clearance (its 10 um grid against KiCad's
    exact pads, typically a 0.6 mm track on a SOT-223 pin next to the neighbouring pin). Each such
    track is narrowed by twice the deficit plus 5 um (rounded down to 10 um). Returns how many."""
    import re
    n = 0
    for _ in range(3):
        bad = [v for v in drc_check(board) if v[0] == "clearance"]
        if not bad:
            break
        byuid = {uid(t): t for t in board.GetTracks() if t.GetClass() == "PCB_TRACK"}
        done = 0
        for typ, desc, uids in bad:
            mn, ma = re.search(r"clearance ([0-9.]+) mm", desc), re.search(r"actual ([0-9.]+) mm", desc)
            if not (mn and ma):
                continue
            deficit = MM(float(mn.group(1)) - float(ma.group(1)))
            if deficit > MM(0.03):
                continue                            # not a rounding problem: leave it to DRC
            for u in uids:
                t = byuid.get(u)
                if t is None or t.GetNetname() in SKIP_NETS:
                    continue
                nw = int((t.GetWidth() - 2 * (deficit + MM(0.005))) // MM(0.01)) * MM(0.01)
                if nw < MM(0.2):
                    continue
                log("  clearance: %s track at %s narrowed %.3f -> %.2f mm (%.3f mm short)" % (
                    t.GetNetname(), bmm(t.GetStart()), TOMM(t.GetWidth()), TOMM(nw), TOMM(int(deficit))))
                t.SetWidth(nw)
                done += 1
                break
        n += done
        if not done:
            break
    return n


def jog_reason(ctx, net, layer, pts, ts, j):
    """Why a jog stays: what the candidate fixes would collide with."""
    if ts[0].GetNetname() in SKIP_NETS:
        return "hand-routed USB pair, kept symmetric"
    if any(uid(t) in ctx.fixed for t in ts):
        return "pre-route"
    seen = set()
    for label, ch in jog_plans(ctx.board, pts, ts, j, layer):
        if touches_anchor(ctx, ch):
            seen.add("a track joining it mid-segment")
            continue
        txn = Txn(ctx)
        txn.apply(ch)
        seen |= {describe(e) for it, e in txn.conflicts()}
        txn.rollback()
    if not seen:
        return "no straight alternative between the pads / vias it joins"
    pads = sorted(s[4:] for s in seen if s.startswith("pad "))
    other = sorted(s for s in seen if not s.startswith("pad "))
    parts = (["pads " + ", ".join(pads)] if pads else []) + other
    return "in the way: " + "; ".join(parts[:4])


def cmd_all(*opts):
    """Every step, then KiCad's DRC and the report (`all nojogs`: skip the jog step)."""
    import time
    t0 = time.time()
    log = lambda s: print(s, flush=True)
    skip = set()
    for attempt in range(4):
        board = R.load()
        board.GetDesignSettings().SetAuxOrigin(R.P(0, D.BOARD_H))
        nstrip = strip_stitching(board)
        nfo = fix_fanout_shorts(board, log)
        if nfo:
            log("fan-out: %d GND fan-outs rebuilt clear of router tracks" % nfo)
        nclr = fix_clearances(board, log)
        if nclr:
            log("clearance: %d tracks narrowed to their clearance (router rounding)" % nclr)
        nsnap = snap_tiny_stubs(board, log)
        nmicro = drop_micro_ends(board, log)
        if nmicro:
            log("slivers: %d router slivers at run ends removed" % nmicro)
        if "nojogs" in opts:
            fixed, left = [], {}
            break
        fixed, left = jog_pass(board, skip, log=log)
        merge_collinear(board)
        mfix = maze_jogs(board, skip, log=log)
        merge_collinear(board)
        rfix = ripup_jogs(board, skip, log=log)
        merge_collinear(board)
        if rfix:
            mfix += rfix + maze_jogs(board, skip, log=log)
            merge_collinear(board)
        log("maze: %d more jogs fixed by re-routing their run (%d with neighbouring runs ripped up)" % (len(mfix), len(rfix)))
        fixed += mfix
        cfix, cleft = chamfer_pass(board, skip, log=log)
        if cleft:
            cfix += maze_corners(board, skip, log=log)
            merge_collinear(board)
            cleft = chamfer_pass(board, skip, log=log)[1]
        merge_collinear(board)
        log("corners: %d right angles chamfered to 2 x 45 deg, %d left %s" % (len(cfix), len(cleft), cleft[:12]))
        fixed += cfix
        bad = drc_check(board)
        if not bad:
            break
        culprits = {f[:3] for f in fixed if set(f[-1]) & {u for v in bad for u in v[2]}}
        log("jogs: DRC found %d problems after the jog step; skipping %s and starting again" % (len(bad), sorted(culprits)))
        if not culprits:
            for v in bad[:10]:
                log("  %s: %s" % (v[0], v[1]))
            raise SystemExit("DRC problems after the jog step that no jog fix explains")
        skip |= culprits
    log("strip: %d stitching vias and the GND pours removed; %d vias moved onto the end of their stub; jogs: %d straightened, %d left (%.0f s)"
        % (nstrip, nsnap, len(fixed), len(left), time.time() - t0))
    zones = add_zones(board)
    nvoid = void_pass(board, zones, log=log)
    log("voids: %d tracks moved to close narrow strips (%.0f s)" % (nvoid, time.time() - t0))
    lab = place_labels(board, log=log)
    log("silk: references %.1f mm / %.2f mm on top; callouts with a leader %s; on the bottom side %s; hidden %s; plate names left out %s; "
        "legend %s; vias moved for labels %d" % (lab["size"], REF_STROKE, lab["callouts"] or "none", lab["bottom"] or "none", lab["hidden"] or "none",
                                                 lab["no_plate"] or "none", lab["legend"], lab["vias_moved"]))
    boxes = text_boxes(board)
    nisl, left_isl = stitch_islands(board, zones, boxes, log)
    nlab = unblock_via_spots(board, zones, log)
    if nlab:
        boxes = text_boxes(board)
        n2, left_isl = stitch_islands(board, zones, boxes, log)
        nisl += n2
    npush = stitch_push(board, zones, boxes, log)
    nret, ret_left = return_vias(board, boxes, log)
    log("return vias: %d GND vias added next to fast-signal layer changes%s" % (
        nret, "; none fits next to %s" % ret_left if ret_left else ""))
    ngrid = stitch_grid(board, zones, boxes)
    nfl = prune_floating_vias(board, zones)
    if nfl:
        log("stitch: %d vias that joined only floating pieces removed" % nfl)
    fill(board, zones, pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
    log("stitch: %d island vias (%d labels moved off via spots), %d vias after pushing tracks aside, %d grid vias (%.0f s)"
        % (nisl, nlab, npush, ngrid, time.time() - t0))
    tb = board.GetTitleBlock()
    tb.SetRevision(REVISION)
    tb.SetComment(1, "rev 2.1: rev 2 routing finished by gen/polish.py (jogs, GND pour + stitching, silkscreen)")
    save(board)
    R.prune(board, zones)
    rep = R.drc_json(BOARD)
    bad = rep.get("violations", []) + rep.get("unconnected_items", []) + rep.get("schematic_parity", [])
    log("DRC (all severities): %d violations, %d unconnected%s" % (
        len(rep.get("violations", [])), len(rep.get("unconnected_items", [])),
        "".join("\n  %s: %s" % (v["type"], v["description"]) for v in bad[:20])))
    ctx = Ctx(board)
    rows = []
    for net, layer, pts, ts in ctx.chains:
        for j, off in find_jogs(pts):
            rows.append((ts[0].GetNetname(), board.GetLayerName(layer), bmm(pts[j + 1]), TOMM(int(off)),
                         jog_reason(ctx, net, layer, pts, ts, j)))
    log("jogs left: %d" % len(rows))
    for r in sorted(rows):
        log("  %-10s %s at (%.2f, %.2f), %.2f mm: %s" % (r[0], r[1], r[2][0], r[2][1], r[3], r[4]))
    R.report(board)
    log("done in %.0f s" % (time.time() - t0))
    if bad:
        raise SystemExit("polish: KiCad's DRC is not clean (see above); the board was saved for inspection")


# ------------------------------------------------------------------------------ main
def describe(e):
    """Short name of an obstacle entry (for reasons and diagnostics)."""
    if e is None:
        return "edge"
    if len(e) == 2:
        return "hole2hole"
    it = e[7]
    if e[6] == "pad":
        return "pad %s.%s" % (it.GetParentFootprint().GetReference(), it.GetNumber())
    return "%s %s" % (e[6], it.GetNetname())


def cmd_jogs():
    """The jogs on the board, with what keeps each one."""
    board = R.load()
    strip_stitching(board)
    ctx = Ctx(board)
    rows = []
    for net, layer, pts, ts in ctx.chains:
        for j, off in find_jogs(pts):
            rows.append((ts[0].GetNetname(), board.GetLayerName(layer), bmm(pts[j + 1]), TOMM(int(off)),
                         jog_reason(ctx, net, layer, pts, ts, j)))
    print("jogs: %d" % len(rows))
    for r in sorted(rows):
        print("  %-10s %s at (%.2f, %.2f), %.2f mm: %s" % (r[0], r[1], r[2][0], r[2][1], r[3], r[4]))


def main():
    cmds = {"all": cmd_all, "jogs": cmd_jogs, "report": lambda: R.report()}
    if len(sys.argv) >= 2 and sys.argv[1] in cmds:
        cmds[sys.argv[1]](*sys.argv[2:])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
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
