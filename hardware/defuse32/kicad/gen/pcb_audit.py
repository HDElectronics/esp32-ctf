#!/usr/bin/env python3
"""Professional-finish audit for a routed KiCad board (KiCad 8-10, run with KiCad's Python).

  /usr/bin/python3 pcb_audit.py board.kicad_pcb [--json out.json] [--fill]

Checks what KiCad's DRC does not (or not by default):

  copper   voids: board area where a GND/zone pour would be legal but there is no copper on that
           layer, after a morphological opening by half the zone's minimum width (so thermal gaps,
           smoothing slivers and clearance rings are not counted). Each void says whether a
           stitching via fits in it (it can then be grounded) and how wide it is. "Fits" means a
           legal via centre exists in the void: clear of other-net copper on EVERY copper layer
           by the via's own net-class clearance (not just the zone clearance), hole-to-hole spacing
           kept, inside the edge clearance, and landing in ground copper of the zone's net on
           another layer (a via over a void on the other side grounds nothing).
  silk     every visible silkscreen text (references and free text):
           - over a via, a pad / mask opening, a hole, or off the board / within 0.3 mm of the edge
           - overlapping another text or another footprint's silk lines
           - under another footprint's courtyard (hidden after assembly)
           - height < 0.8 mm or stroke < 0.15 mm (or the board's own silk minimums if higher,
             e.g. JLCPCB's 1.0 mm), mixed reference sizes
           - reading direction other than left-to-right (0 deg) or bottom-to-top (90 deg)
           - far from its own part (> 2 mm) or closer to another part than to its own (unless a
             board-level silk leader joins label and part: a callout, listed as info)
           - over tracks (legibility, info only); hidden references (info; a board-level range
             label such as "R16-19" counts as printing the references it covers)
  routing  jogs: a track that steps sideways by < 1.5 mm with two bends and carries on in the same
           direction (ugly, and every bend is a small discontinuity on a fast line: keep it
           straight); a straight run split into collinear pieces counts as one segment, so a split
           does not hide a jog; turns sharper than 90 deg (acid traps); 90 deg corners (warning)

--fill refills the zones first (in memory; the file is never written).
Exit code 1 when there are violations (warnings and info do not count).
"""
import json
import math
import re
import sys

import pcbnew

MM = pcbnew.FromMM
TOMM = pcbnew.ToMM
ERR = MM(0.005)

TEXT_MIN_H, TEXT_MIN_W = 0.8, 0.15      # mm, legible minimum; raised to the board's own silk rules
                                        # (JLCPCB lists 1.0 mm text height) in board_rules()
EDGE_GAP = 0.3                          # mm, silk to board edge
SILK_PAD_GAP = 0.1                      # mm, silk to pad / mask opening (fab clips closer ink)
SILK_VIA_GAP = 0.1                      # mm, silk to via copper
NEAR = 1.0                              # mm, label box to own courtyard: more is a warning
FAR = 2.0                               # mm, ... more is a violation (unless a silk leader joins them)
ROW_TOL = 0.3                           # mm, parts whose centres line up within this form a row
ROW_PITCH = 5.0                         # mm, ... when neighbours are closer than this
VOID_MIN_AREA = 0.5                     # mm2, smaller voids are ignored
VIA_D, VIA_CLR = 0.6, 0.2               # mm, stitching via used for the "fits a via" test
VIA_DRILL = 0.3                         # mm (its hole counts for hole-to-hole spacing); both replaced
                                        # by the smallest via the board's rules allow (board_rules())


def board_rules(board):
    """Take the stitching-via size and the silk text minimum from the board's design rules: the via
    is the smallest the rules allow (min drill, min diameter, min drill + 2 x min annular ring), the
    text minimum the larger of TEXT_MIN_* and the board's min text height / stroke."""
    global VIA_D, VIA_DRILL, TEXT_MIN_H, TEXT_MIN_W
    ds = board.GetDesignSettings()
    try:
        drill = TOMM(ds.m_MinThroughDrill)
        dia = max(TOMM(ds.m_ViasMinSize), drill + 2 * TOMM(ds.m_ViasMinAnnularWidth))
        if 0.1 <= drill and 0.2 <= dia:
            VIA_D, VIA_DRILL = round(dia, 3), round(drill, 3)
    except Exception:
        pass
    try:
        TEXT_MIN_H = max(TEXT_MIN_H, round(TOMM(ds.m_MinSilkTextHeight), 3))
        TEXT_MIN_W = max(TEXT_MIN_W, round(TOMM(ds.m_MinSilkTextThickness), 3))
    except Exception:
        pass


def box(b, g=0.0):
    return (TOMM(b.GetLeft()) - g, TOMM(b.GetTop()) - g, TOMM(b.GetRight()) + g, TOMM(b.GetBottom()) + g)


def hit(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def box_dist(a, b):
    dx = max(b[0] - a[2], a[0] - b[2], 0)
    dy = max(b[1] - a[3], a[1] - b[3], 0)
    return math.hypot(dx, dy)


def box_circle(b, cx, cy):
    dx = max(b[0] - cx, 0, cx - b[2])
    dy = max(b[1] - cy, 0, cy - b[3])
    return math.hypot(dx, dy)


def rect(b):
    return pcbnew.BOX2I(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])), pcbnew.VECTOR2L(MM(b[2] - b[0]), MM(b[3] - b[1])))


def poly_hits_box(poly, b):
    """True when the courtyard polygon overlaps box b (None: fall back to the bbox test done before)."""
    if poly is None:
        return True
    r = pcbnew.SHAPE_POLY_SET()
    r.NewOutline()
    for x, y in ((b[0], b[1]), (b[2], b[1]), (b[2], b[3]), (b[0], b[3])):
        r.Append(MM(x), MM(y))
    r.BooleanIntersection(pcbnew.SHAPE_POLY_SET(poly))
    return r.OutlineCount() > 0 and area(r) > 0.01


def simplify(s):
    try:
        s.Simplify()
    except TypeError:
        s.Simplify(pcbnew.SHAPE_POLY_SET.PM_FAST)


def area(s):
    return sum(abs(s.Outline(i).Area()) for i in range(s.OutlineCount())) / 1e12


def piece(s, i):
    p = pcbnew.SHAPE_POLY_SET()
    p.AddOutline(s.Outline(i))
    for h in range(s.HoleCount(i)):
        p.AddHole(s.Hole(i, h), 0)
    return p


# ------------------------------------------------------------------------------------- copper
_VIA_FORBIDDEN = {}


def via_forbidden(board, zone):
    """Where the centre of a stitching via of the zone's net may NOT go: other-net copper on any
    copper layer grown by via radius + the via-to-item clearance (the larger of the via net's
    net-class clearance and the item's own), every hole grown by hole-to-hole spacing, keep-outs
    and the edge band. A via must clear all layers, not only the one with the void."""
    net = zone.GetNetCode()
    if net in _VIA_FORBIDDEN:
        return _VIA_FORBIDDEN[net]
    ds = board.GetDesignSettings()
    v = pcbnew.PCB_VIA(board)
    v.SetNetCode(net)
    v.SetWidth(MM(VIA_D))
    v.SetDrill(MM(VIA_DRILL))
    try:
        vclr = v.GetOwnClearance(pcbnew.F_Cu)
    except Exception:
        vclr = MM(VIA_CLR)
    vclr = max(vclr, MM(VIA_CLR))
    r = MM(VIA_D / 2)
    h2h = getattr(ds, "m_HoleToHoleMin", MM(0.25))
    forb = pcbnew.SHAPE_POLY_SET()
    cu = list(board.GetEnabledLayers().CuStack())
    for fp in board.GetFootprints():
        for p in fp.Pads():
            if p.HasHole():
                p.TransformHoleToPolygon(forb, MM(VIA_DRILL / 2) + h2h, ERR, pcbnew.ERROR_OUTSIDE)
            if p.GetNetCode() == net:
                continue
            for layer in cu:
                if p.IsOnLayer(layer):
                    p.TransformShapeToPolygon(forb, layer, r + max(vclr, p.GetOwnClearance(layer)), ERR, pcbnew.ERROR_OUTSIDE)
    for t in board.GetTracks():
        if t.GetClass() == "PCB_VIA":
            c = t.GetPosition()
            hole = pcbnew.SHAPE_POLY_SET()
            rr = t.GetDrillValue() // 2 + MM(VIA_DRILL / 2) + h2h
            hole.NewOutline()
            for k in range(24):
                a = 2 * math.pi * k / 24
                hole.Append(int(c.x + rr * math.cos(a) / math.cos(math.pi / 24)), int(c.y + rr * math.sin(a) / math.cos(math.pi / 24)))
            forb.Append(hole)
        if t.GetNetCode() == net:
            continue
        for layer in cu:
            if t.IsOnLayer(layer):
                t.TransformShapeToPolygon(forb, layer, r + max(vclr, t.GetOwnClearance(layer)), ERR, pcbnew.ERROR_OUTSIDE)
    for z in list(board.Zones()) + [z for fp in board.GetFootprints() for z in fp.Zones()]:
        if z.GetIsRuleArea() and (z.GetDoNotAllowVias() if hasattr(z, "GetDoNotAllowVias") else True):
            forb.Append(pcbnew.SHAPE_POLY_SET(z.Outline()))
        elif not z.GetIsRuleArea() and z.GetNetCode() != net:
            for layer in cu:
                if z.IsOnLayer(layer):
                    s = pcbnew.SHAPE_POLY_SET(z.GetFilledPolysList(layer))
                    s.Inflate(r + vclr, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
                    forb.Append(s)
    simplify(forb)
    _VIA_FORBIDDEN[net] = forb
    return forb


def copper_voids(board, layer, zone):
    net = zone.GetNetCode()
    clr = zone.GetLocalClearance()
    clr = MM(0.2) if clr is None else clr
    minw = zone.GetMinThickness()
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, True)
    edge = board.GetDesignSettings().m_CopperEdgeClearance
    outline.Deflate(edge, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)

    obs = pcbnew.SHAPE_POLY_SET()        # where the pour may not go
    own = pcbnew.SHAPE_POLY_SET()        # copper already on the zone's net
    items = [p for fp in board.GetFootprints() for p in fp.Pads()] + list(board.GetTracks())
    for it in items:
        if not it.IsOnLayer(layer) and not (it.GetClass() == "PAD" and it.HasHole()):
            continue
        if it.GetClass() == "PAD" and it.HasHole() and not it.IsOnLayer(layer):
            # NPTH: the hole itself is an obstacle on every layer
            it.TransformHoleToPolygon(obs, clr, ERR, pcbnew.ERROR_OUTSIDE)
            continue
        if it.GetNetCode() == net:
            # same net: the pour joins it (thermal gaps around it are not voids)
            it.TransformShapeToPolygon(own, layer, MM(0.35), ERR, pcbnew.ERROR_OUTSIDE)
        else:
            try:
                c = max(clr, it.GetOwnClearance(layer))
            except Exception:
                c = clr
            it.TransformShapeToPolygon(obs, layer, c, ERR, pcbnew.ERROR_OUTSIDE)
    for z in list(board.Zones()) + [z for fp in board.GetFootprints() for z in fp.Zones()]:
        if z.GetIsRuleArea() and z.IsOnLayer(layer) and (z.GetDoNotAllowZoneFills() if hasattr(z, "GetDoNotAllowZoneFills") else z.GetDoNotAllowCopperPour()):
            o = pcbnew.SHAPE_POLY_SET(z.Outline())
            obs.Append(o)
        elif not z.GetIsRuleArea() and z.IsOnLayer(layer):
            own.Append(z.GetFilledPolysList(layer))
    simplify(obs)
    simplify(own)
    free = pcbnew.SHAPE_POLY_SET(outline)
    free.BooleanSubtract(obs)
    free.BooleanSubtract(own)
    # opening: what survives half the minimum width shrink is a real void
    free.Deflate(minw // 2, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    free.Inflate(minw // 2, pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    forb = via_forbidden(board, zone)
    vin = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(vin, True)
    vin.Deflate(edge + MM(VIA_D / 2), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
    # copper of the zone's net on the other layers, where a stitching via would find ground
    ground = pcbnew.SHAPE_POLY_SET()
    for z in board.Zones():
        if not z.GetIsRuleArea() and z.GetNetCode() == net:
            for ol in z.GetLayerSet().CuStack():
                if ol != layer:
                    ground.Append(z.GetFilledPolysList(ol))
    simplify(ground)
    voids = []
    for i in range(free.OutlineCount()):
        p = piece(free, i)
        a = area(p)
        if a < VOID_MIN_AREA:
            continue
        # a stitching via fits when some point of the void is a legal via centre (all layers)
        # that also lands in ground copper on another layer (else the via grounds nothing)
        v = pcbnew.SHAPE_POLY_SET(p)
        v.BooleanIntersection(vin)
        v.BooleanSubtract(forb)
        v.Deflate(MM(0.005), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
        legal = v.OutlineCount() > 0
        if legal:
            v.BooleanIntersection(ground)
        why = "via fits" if v.OutlineCount() else ("no ground under it on the other layer" if legal else
                                                   "too narrow / blocked for a via")
        # width estimate: largest shrink that leaves something
        lo, hi = 0.0, 5.0
        for _ in range(10):
            mid = (lo + hi) / 2
            t = pcbnew.SHAPE_POLY_SET(p)
            t.Deflate(MM(mid), pcbnew.CORNER_STRATEGY_ROUND_ALL_CORNERS, ERR)
            lo, hi = (mid, hi) if t.OutlineCount() else (lo, mid)
        bb = p.BBox()
        voids.append({"layer": board.GetLayerName(layer), "area_mm2": round(a, 2),
                      "width_mm": round(2 * lo, 2), "via_fits": v.OutlineCount() > 0, "why": why,
                      "at": [round(TOMM(bb.Centre().x), 2), round(TOMM(bb.Centre().y), 2)],
                      "bbox": [round(x, 2) for x in box(bb)]})
    return sorted(voids, key=lambda v: -v["area_mm2"])


# --------------------------------------------------------------------------------------- silk
def silk_texts(board):
    out = []
    for fp in board.GetFootprints():
        for t in [fp.Reference(), fp.Value()] + [g for g in fp.GraphicalItems() if g.GetClass() == "PCB_TEXT"]:
            if t.IsVisible() and t.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and t.GetShownText(False).strip():
                # SWIG hands out a new proxy per call, so `t is fp.Reference()` is never true: compare by uuid
                kind = "ref" if t.m_Uuid.AsString() == fp.Reference().m_Uuid.AsString() or t.GetText() == "${REFERENCE}" else "text"
                out.append((fp, t, kind))
    for d in board.GetDrawings():
        if d.GetClass() in ("PCB_TEXT", "PCB_TEXTBOX") and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS) and d.IsVisible():
            out.append((None, d, "text"))
    return out


def group_alignment(board):
    """Rows (or columns) of 3+ like parts (same footprint and rotation, centres in line, neighbours
    closer than ROW_PITCH) must have their references at one angle and on one line, in part order."""
    out = []
    fps = [f for f in board.GetFootprints() if f.Reference().IsVisible() and len(list(f.Pads()))]
    groups = {}
    for f in fps:
        groups.setdefault((f.GetFPIDAsString(), round(f.GetOrientationDegrees()) % 180, f.GetLayer()), []).append(f)
    for parts in groups.values():
        if len(parts) < 3:
            continue
        for axis in (0, 1):                    # 0: horizontal row (same y), 1: vertical column (same x)
            other = 1 - axis
            pos = lambda f: (TOMM(f.GetPosition().x), TOMM(f.GetPosition().y))
            parts_s = sorted(parts, key=lambda f: (round(pos(f)[other] / ROW_TOL), pos(f)[axis]))
            rows, cur = [], []
            for f in parts_s:
                if cur and abs(pos(f)[other] - pos(cur[-1])[other]) <= ROW_TOL and pos(f)[axis] - pos(cur[-1])[axis] < ROW_PITCH:
                    cur.append(f)
                else:
                    if len(cur) >= 3:
                        rows.append(cur)
                    cur = [f]
            if len(cur) >= 3:
                rows.append(cur)
            for row in rows:
                names = " ".join(f.GetReference() for f in row)
                texts = [f.Reference() for f in row]
                angs = {round(t.GetDrawRotation().AsDegrees()) % 360 for t in texts}
                bxs = [box(t.GetBoundingBox()) for t in texts]
                if len(angs) > 1:
                    out.append(("group-align", names, "labels of this row use different directions"))
                    continue
                cy = [(b[1] + b[3]) / 2 for b in bxs] if axis == 0 else [(b[0] + b[2]) / 2 for b in bxs]
                if max(cy) - min(cy) > 0.2:
                    out.append(("group-align", names, "labels of this row are not on one line (spread %.2f mm)" % (max(cy) - min(cy))))
                order_parts = [pos(f)[axis] for f in row]
                order_lab = [((b[0] + b[2]) / 2 if axis == 0 else (b[1] + b[3]) / 2) for b in bxs]
                if sorted(range(len(row)), key=lambda i: order_parts[i]) != sorted(range(len(row)), key=lambda i: order_lab[i]):
                    out.append(("group-align", names, "labels are not in the same order as the parts"))
    return out


def silk_checks(board):
    viol, warn, info = [], [], []
    vias = [(TOMM(v.GetPosition().x), TOMM(v.GetPosition().y), TOMM(v.GetWidth(pcbnew.F_Cu)) / 2)
            for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
    tracks = [t for t in board.GetTracks() if t.GetClass() in ("PCB_TRACK", "PCB_ARC")]
    pads = []
    for fp in board.GetFootprints():
        for p in fp.Pads():
            pads.append((fp.GetReference(), p, box(p.GetBoundingBox())))
    crt, cpoly, fsilk = {}, {}, []
    for fp in board.GetFootprints():
        side = pcbnew.F_CrtYd if fp.GetLayer() == pcbnew.F_Cu else pcbnew.B_CrtYd
        c = fp.GetCourtyard(side)
        crt[fp.GetReference()] = (box(c.BBox()) if c.OutlineCount() else box(fp.GetBoundingBox(False, False)), fp.GetLayer())
        cpoly[fp.GetReference()] = c if c.OutlineCount() else None
        for g in fp.GraphicalItems():
            if g.GetClass() != "PCB_TEXT" and g.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
                fsilk.append((fp.GetReference(), g.GetLayer(), box(g.GetBoundingBox())))
    ob = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(ob, True)
    edge = box(ob.BBox())
    texts = silk_texts(board)
    leaders = [(d.GetLayer(), box(d.GetBoundingBox())) for d in board.GetDrawings()
               if d.GetClass() == "PCB_SHAPE" and d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS)]
    boxes = []
    sizes = {}
    for fp, t, kind in texts:
        ref = fp.GetReference() if fp else None
        name = ("%s %s" % (ref, kind)) if fp else "text '%s'" % t.GetShownText(False)[:20]
        b = box(t.GetBoundingBox())
        side_cu = pcbnew.F_Cu if t.GetLayer() == pcbnew.F_SilkS else pcbnew.B_Cu
        boxes.append((name, t.GetLayer(), b, ref))
        h, w = TOMM(t.GetTextHeight()), TOMM(t.GetTextThickness())
        if kind == "ref":
            sizes.setdefault((round(h, 2), round(w, 2)), []).append(ref)
        if h < TEXT_MIN_H - 1e-6 or w < TEXT_MIN_W - 1e-6:
            viol.append(("size", name, "%.2f mm high, %.2f mm stroke (min %.2f / %.2f)" % (h, w, TEXT_MIN_H, TEXT_MIN_W)))
        ang = round(t.GetDrawRotation().AsDegrees()) % 360
        if ang not in (0, 90):
            viol.append(("direction", name, "drawn at %d deg: reads %s" % (ang, "upside down" if ang == 180 else "top to bottom" if ang == 270 else "at an angle")))
        if b[0] < edge[0] + EDGE_GAP or b[1] < edge[1] + EDGE_GAP or b[2] > edge[2] - EDGE_GAP or b[3] > edge[3] - EDGE_GAP:
            viol.append(("edge", name, "within %.1f mm of (or past) the board edge" % EDGE_GAP))
        for x, y, r in vias:
            d = box_circle(b, x, y) - r
            if d < SILK_VIA_GAP:
                viol.append(("via", name, "via at (%.2f, %.2f) %s" % (x, y, "under the text" if d < 0 else "%.2f mm away" % d)))
        for pref, p, pb in pads:
            if not p.IsOnLayer(side_cu) and not p.HasHole():
                continue
            if box_dist(b, pb) < SILK_PAD_GAP:
                viol.append(("pad", name, "pad %s.%s" % (pref, p.GetNumber())))
        for r2, (cb, lay) in crt.items():
            if fp and r2 == ref:
                continue
            if (lay == pcbnew.F_Cu) == (t.GetLayer() == pcbnew.F_SilkS) and hit(b, cb) and not r2.startswith(("H", "MH")) \
                    and poly_hits_box(cpoly[r2], b):
                warn.append(("under-part", name, "inside the courtyard of %s (hidden after assembly)" % r2))
        for r2, lay, sb in fsilk:
            if lay == t.GetLayer() and hit(b, sb) and r2 != ref:
                viol.append(("silk-silk", name, "over silk lines of %s" % r2))
        if any(t2.IsOnLayer(side_cu) and hit(b, box(t2.GetBoundingBox())) and t2.HitTest(rect(b), False) for t2 in tracks):
            info.append(("over-track", name, "printed over a track (legible, but text on flat mask reads better)"))
        if fp and kind == "ref":
            own = crt[ref][0]
            d_own = box_dist(b, own)
            # a board-level silk line joining label and part is a leader: the label is a callout
            # (at any distance), so the far / off-a-corner / nearer-to-another-part rules do not apply
            own_g = (own[0] - 0.5, own[1] - 0.5, own[2] + 0.5, own[3] + 0.5)
            lab_g = (b[0] - 0.5, b[1] - 0.5, b[2] + 0.5, b[3] + 0.5)
            leader = any(lay == t.GetLayer() and hit(sb, own_g) and hit(sb, lab_g) for lay, sb in leaders)
            if leader:
                info.append(("callout", name, "%.1f mm from its part, with a leader line" % d_own))
            elif d_own > NEAR:
                if d_own > FAR:
                    viol.append(("far", name, "%.1f mm from its part (max %.1f): move it next to the part or add a leader" % (d_own, FAR)))
                else:
                    warn.append(("far", name, "%.1f mm from its part (aim for <= %.1f)" % (d_own, NEAR)))
            ox = min(b[2], own[2]) - max(b[0], own[0])      # overlap of label and part along x
            oy = min(b[3], own[3]) - max(b[1], own[1])
            if ox < 0.2 * (b[2] - b[0]) and oy < 0.2 * (b[3] - b[1]) and not any(k == "callout" and n == name for k, n, _ in info):
                viol.append(("diagonal", name, "off a corner of its part, not beside one side: put it directly above, below, left or right"))
            near = [(box_dist(b, cb), r2) for r2, (cb, lay) in crt.items() if r2 != ref and not r2.startswith(("H", "MH"))]
            if near:
                dn, rn = min(near)
                if dn + 0.2 < d_own and not any(k == "callout" and n == name for k, n, _ in info):   # a leader tells
                    warn.append(("ambiguous", name, "closer to %s (%.1f mm) than to its own part (%.1f mm)" % (rn, dn, d_own)))
            if hit(b, own) and box_dist((b[0] + 0.01, b[1] + 0.01, b[2] - 0.01, b[3] - 0.01), own) == 0 \
                    and b[0] >= own[0] and b[2] <= own[2] and b[1] >= own[1] and b[3] <= own[3]:
                info.append(("inside-own", name, "inside its own outline (hidden once the part is fitted unless the part is open/large)"))
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            if boxes[i][1] == boxes[j][1] and hit(boxes[i][2], boxes[j][2]):
                viol.append(("text-text", boxes[i][0], "overlaps %s" % boxes[j][0]))
    if len(sizes) > 1:
        warn.append(("sizes", "references", "%d different sizes: %s" % (len(sizes), {"%sx%s" % k: len(v) for k, v in sizes.items()})))
    viol += group_alignment(board)
    hidden = [fp.GetReference() for fp in board.GetFootprints() if not fp.Reference().IsVisible()
              and not fp.GetReference().startswith(("H", "MH")) and not fp.IsBoardOnly() if hasattr(fp, "IsBoardOnly")]
    # a row of like parts may carry one range label ("R16-19" / "R16-R19") on the board silkscreen
    # instead of a reference each: those references are printed, not hidden
    for d in board.GetDrawings():
        if d.GetClass() != "PCB_TEXT" or d.GetLayer() not in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            continue
        m = re.match(r"^([A-Z]+)(\d+)-\1?(\d+)$", d.GetText().strip())
        if not m:
            continue
        rng = ["%s%d" % (m.group(1), k) for k in range(int(m.group(2)), int(m.group(3)) + 1)]
        covered = [r for r in rng if r in hidden]
        if covered:
            info.append(("range", d.GetText().strip(), "range label for %s" % " ".join(covered)))
            hidden = [r for r in hidden if r not in covered]
    if hidden:
        info.append(("hidden", "references", " ".join(sorted(hidden))))
    return viol, warn, info


# ------------------------------------------------------------------------------------ routing
JOG_MAX_OFFSET = 1.5        # mm: a sideways shift smaller than this that comes back to the same heading is a jog
JOG_MAX_RUN = 3.0           # mm: ... when the slanted middle part is shorter than this


def _chains(board):
    """Polylines of tracks per (net, layer, width): segments joined end to end at points that are not
    pads, vias or branch points. Returns lists of points (mm)."""
    key = lambda p: (round(TOMM(p.x), 3), round(TOMM(p.y), 3))
    stops = set()
    for v in board.GetTracks():
        if v.GetClass() == "PCB_VIA":
            stops.add(key(v.GetPosition()))
    pads = [p for fp in board.GetFootprints() for p in fp.Pads()]
    vias = [v for v in board.GetTracks() if v.GetClass() == "PCB_VIA"]
    groups = {}
    for t in board.GetTracks():
        if t.GetClass() == "PCB_TRACK" and t.GetLength() > 0:
            groups.setdefault((t.GetNetname(), t.GetLayer()), []).append(t)
    out = []
    for (net, layer), segs in groups.items():
        adj = {}
        for t in segs:
            a, b = key(t.GetStart()), key(t.GetEnd())
            adj.setdefault(a, []).append((b, t))
            adj.setdefault(b, []).append((a, t))
        def is_stop(pt):
            if pt in stops or len(adj[pt]) != 2:
                return True
            v = pcbnew.VECTOR2I(MM(pt[0]), MM(pt[1]))
            # a track end inside a pad or a via of the net (not only at a via's centre) ends the
            # run there: a bend hidden in the via's copper is no corner
            return any(p.IsOnLayer(layer) and p.HitTest(v) for p in pads if p.GetNetname() == net) or \
                any(x.HitTest(v, 0) for x in vias if x.GetNetname() == net)
        seen = set()
        for start in adj:
            if not is_stop(start):
                continue
            for nxt, t in adj[start]:
                if id(t) in seen:
                    continue
                pts, cur, seg = [start], nxt, t
                seen.add(id(t))
                pts.append(cur)
                while not is_stop(cur):
                    cand = [(n2, t2) for n2, t2 in adj[cur] if id(t2) not in seen]
                    if not cand:
                        break
                    cur, seg = cand[0]
                    seen.add(id(seg))
                    pts.append(cur)
                out.append((net, board.GetLayerName(layer), pts))
    return out


def routing_checks(board):
    viol, warn = [], []
    for net, layer, pts in _chains(board):
        # a straight run split into collinear pieces counts as one segment (else a split slanted
        # part would hide the jog)
        q = [pts[0]]
        for k in range(1, len(pts)):
            if len(q) >= 2 and k < len(pts):
                ax, ay = q[-1][0] - q[-2][0], q[-1][1] - q[-2][1]
                bx, by = pts[k][0] - q[-1][0], pts[k][1] - q[-1][1]
                la, lb = math.hypot(ax, ay), math.hypot(bx, by)
                if la and lb and (ax * bx + ay * by) / (la * lb) > 0.99999:
                    q[-1] = pts[k]
                    continue
            if pts[k] != q[-1]:
                q.append(pts[k])
        pts = q
        segs = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
        dirs = []
        for a, b in segs:
            dx, dy = b[0] - a[0], b[1] - a[1]
            L = math.hypot(dx, dy)
            dirs.append((dx / L, dy / L, L) if L else (0, 0, 0))
        for i in range(len(segs) - 2):
            (ax, ay, la), (bx, by, lb), (cx, cy, lc) = dirs[i], dirs[i + 1], dirs[i + 2]
            if ax * cx + ay * cy > 0.999 and abs(ax * bx + ay * by) < 0.999 and lb < JOG_MAX_RUN:
                # A and C same heading, B slanted: sideways offset between the lines of A and C
                off = abs((segs[i + 2][0][0] - segs[i][1][0]) * -ay + (segs[i + 2][0][1] - segs[i][1][1]) * ax)
                if 0.005 < off < JOG_MAX_OFFSET:
                    m = segs[i + 1][0]
                    viol.append(("jog", "%s on %s" % (net, layer),
                                 "sideways %.2f mm double bend at (%.2f, %.2f): keep the track straight" % (off, m[0], m[1])))
        for i in range(len(segs) - 1):
            (ax, ay, la), (bx, by, lb) = dirs[i], dirs[i + 1]
            dot = ax * bx + ay * by
            if dot < -1e-3:
                viol.append(("acute", "%s on %s" % (net, layer), "turn sharper than 90 deg at (%.2f, %.2f)" % segs[i][1]))
            elif abs(dot) < 1e-3 and min(la, lb) > 0.05:
                viol.append(("right-angle", "%s on %s" % (net, layer), "90 deg corner at (%.2f, %.2f): use two 45 deg bends" % segs[i][1]))
    return viol, warn


# ---------------------------------------------------------------------------------- 3D models
def model_checks(board):
    """Every footprint with pads needs a visible 3D model whose file exists (otherwise the 3D view,
    the STEP export for the enclosure and the fab's assembly preview show a hole)."""
    import os
    base = os.environ.get("KICAD10_3DMODEL_DIR") or os.environ.get("KICAD9_3DMODEL_DIR") or "/usr/share/kicad/3dmodels"
    prj = os.path.dirname(os.path.abspath(board.GetFileName()))

    def resolve(fn):
        for v in ("KICAD10_3DMODEL_DIR", "KICAD9_3DMODEL_DIR", "KICAD8_3DMODEL_DIR", "KICAD7_3DMODEL_DIR", "KICAD6_3DMODEL_DIR"):
            fn = fn.replace("${%s}" % v, base)
        fn = fn.replace("${KIPRJMOD}", prj)
        return fn if os.path.isabs(fn) else os.path.join(prj, fn)

    viol = []
    for fp in board.GetFootprints():
        ref = fp.GetReference()
        if not len(list(fp.Pads())) or ref.startswith(("H", "MH", "FID", "LOGO", "TP")):
            continue
        models = [m for m in fp.Models() if m.m_Show]
        if not models:
            viol.append(("3d-missing", ref, "%s has no 3D model" % fp.GetFPIDAsString()))
            continue
        missing = [m.m_Filename for m in models if not os.path.isfile(resolve(m.m_Filename))]
        if len(missing) == len(models):
            viol.append(("3d-missing", ref, "model file not found: %s" % missing[0]))
    return viol


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    path = args[0]
    out_json = args[args.index("--json") + 1] if "--json" in args else None
    board = pcbnew.LoadBoard(path)
    board_rules(board)
    print("rules: stitching via %.2f / %.2f mm, silk text >= %.2f / %.2f mm, %d copper layers" % (
        VIA_D, VIA_DRILL, TEXT_MIN_H, TEXT_MIN_W, board.GetCopperLayerCount()))
    if "--fill" in args:
        pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    voids = []
    for z in board.Zones():
        if z.GetIsRuleArea():
            continue
        for layer in z.GetLayerSet().CuStack():
            voids += copper_voids(board, layer, z)
    viol, warn, info = silk_checks(board)
    rviol, rwarn = routing_checks(board)
    mviol = model_checks(board)
    fits = [v for v in voids if v["via_fits"]]
    noground = [v for v in voids if v["why"].startswith("no ground")]
    print("COPPER: %d voids >= %.1f mm2 (total %.1f mm2), %d can take a stitching via, %d cannot (%d too narrow or blocked, "
          "%d over a void on the other layer)"
          % (len(voids), VOID_MIN_AREA, sum(v["area_mm2"] for v in voids), len(fits), len(voids) - len(fits),
             len(voids) - len(fits) - len(noground), len(noground)))
    for v in sorted(voids, key=lambda v: (not v["via_fits"], -v["area_mm2"]))[:30]:
        print("  %-5s %6.2f mm2  w %.2f mm  at (%.1f, %.1f)  %s" % (v["layer"], v["area_mm2"], v["width_mm"], v["at"][0], v["at"][1],
                                                              v["why"]))
    for title, rows in (("ROUTING VIOLATIONS", rviol), ("ROUTING WARNINGS", rwarn), ("SILK VIOLATIONS", viol), ("SILK WARNINGS", warn),
                        ("3D MODEL VIOLATIONS", mviol), ("INFO", info)):
        kinds = {}
        for k, *_ in rows:
            kinds[k] = kinds.get(k, 0) + 1
        print("%s: %d %s" % (title, len(rows), kinds))
        for k, n, msg in rows[:60]:
            print("  [%s] %s: %s" % (k, n, msg))
    if out_json:
        json.dump({"voids": voids, "routing_violations": rviol, "routing_warnings": rwarn,
                   "violations": viol, "warnings": warn, "model_violations": mviol, "info": info}, open(out_json, "w"), indent=1)
    return 1 if viol or rviol or mviol else 0


if __name__ == "__main__":
    import os
    try:
        rc = main()
    except SystemExit as e:
        print(e.code, file=sys.stderr)
        rc = 2
    except BaseException:
        import traceback
        traceback.print_exc()
        rc = 2
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(rc)       # KiCad 10 SWIG: skip the final garbage collection (it can segfault)
