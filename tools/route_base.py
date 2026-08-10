"""Finish the routing on base/base.kicad_pcb.

Additive and re-runnable. It removes only its own output -- every via and
every track on In1.Cu/In2.Cu -- and rebuilds them. Tracks on F.Cu and B.Cu are
left exactly as they are, so hand routing survives a rerun.

  <kicad python> tools/route_base.py            route, save, report
  <kicad python> tools/route_base.py --dry-run  report without saving

The connector escapes on the outer layers where there is room, and drops to an
inner layer for the nets whose J1 row faces away from their J2 pin. Six of the
seventeen are on the wrong side: IO1-IO4 sit on J1's odd row and land on the
right-hand DIP column, /WE and /CE sit on the even row and land on the left.
"""
import itertools
import math
import sys

import pcbnew

BOARD = '/Users/alex/bga67-to-dip48/base/base.kicad_pcb'

TRACK = 0.15
CLR = 0.10
VIA_PAD, VIA_DRILL = 0.45, 0.20

# Centre-to-centre minimums. JLC numbers via docs/jlc-rules.md; the copper
# figure binds in every case here, so the hole figures are only asserted.
T_T = TRACK + CLR                        # 0.25  track to track
T_PAD = TRACK / 2 + CLR                  # 0.175 track centreline to pad copper
T_VIA = VIA_PAD / 2 + TRACK / 2 + CLR    # 0.40  track to via
V_VIA = VIA_PAD + CLR                    # 0.55  via to via
V_PAD = VIA_PAD / 2 + CLR                # 0.325 via to pad copper
V_THT_HOLE = VIA_DRILL / 2 + 0.9 / 2 + 0.20   # 0.75 via drill to PTH drill
EDGE_T = 0.20 + TRACK / 2                # 0.275 track to board edge
EDGE_V = 0.20 + VIA_PAD / 2              # 0.425 via to board edge

# The GND pour has to reach a 0.4 mm-pitch connector, which KiCad's stock zone
# settings cannot do. These are the carrier's, which are known to work.
ZONE_CLEARANCE = 0.2
# 0.15, not 0.25. The pour reaches J1's GND pads through the 0.65 mm gaps
# between the signal escape stubs; at 0.25 it needs 0.25 + 2x0.2 = 0.65 exactly
# and every GND pad on the connector goes unconnected.
ZONE_MIN_THICKNESS = 0.15
ZONE_THERMAL_GAP = 0.3

IN1, IN2 = pcbnew.In1_Cu, pcbnew.In2_Cu
F_CU, B_CU = pcbnew.F_Cu, pcbnew.B_Cu

MM = pcbnew.FromMM
def mm(v):
    return pcbnew.ToMM(v)


# ------------------------------------------------------------------ geometry
def pt_seg(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    if L == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def seg_seg(a, b, c, d):
    def ccw(p, q, r):
        return (r[1] - p[1]) * (q[0] - p[0]) - (q[1] - p[1]) * (r[0] - p[0])
    if ((ccw(a, b, c) > 0) != (ccw(a, b, d) > 0)) and \
       ((ccw(c, d, a) > 0) != (ccw(c, d, b) > 0)):
        return 0.0
    return min(pt_seg(c, a, b), pt_seg(d, a, b), pt_seg(a, c, d), pt_seg(b, c, d))


def seg_rect(a, b, rect):
    """Distance from segment ab to an axis-aligned rect (x0,y0,x1,y1)."""
    x0, y0, x1, y1 = rect
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    inside = lambda p: x0 <= p[0] <= x1 and y0 <= p[1] <= y1
    if inside(a) or inside(b):
        return 0.0
    return min(seg_seg(a, b, corners[i], corners[(i + 1) % 4]) for i in range(4))


def pt_rect(p, rect):
    x0, y0, x1, y1 = rect
    dx = max(x0 - p[0], 0, p[0] - x1)
    dy = max(y0 - p[1], 0, p[1] - y1)
    return math.hypot(dx, dy)


def point_in_poly(p, pts):
    hit = False
    for a, b in zip(pts, pts[1:] + pts[:1]):
        if (a[1] > p[1]) != (b[1] > p[1]):
            xx = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if p[0] < xx:
                hit = not hit
    return hit


def polyline(pts):
    out = [pts[0]]
    for p in pts[1:]:
        if abs(p[0] - out[-1][0]) > 1e-9 or abs(p[1] - out[-1][1]) > 1e-9:
            out.append(p)
    return out


def segs(path):
    return list(zip(path, path[1:]))


def length(path):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in segs(path))


# --------------------------------------------------------------------- model
class Model(object):
    def __init__(self, board):
        self.b = board
        self.pads = []       # (rect, netcode, is_tht, centre, layers)
        for f in board.GetFootprints():
            for p in f.Pads():
                bb = p.GetBoundingBox()
                rect = (mm(bb.GetLeft()), mm(bb.GetTop()),
                        mm(bb.GetRight()), mm(bb.GetBottom()))
                c = p.GetPosition()
                tht = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH,
                                           pcbnew.PAD_ATTRIB_NPTH)
                # An SMD pad only obstructs its own layer. J1 is a B.Cu
                # footprint, so treating its pads as global obstacles walls off
                # both inner layers under the connector -- which is exactly the
                # space the crossing nets need.
                layers = frozenset(l for l in (F_CU, IN1, IN2, B_CU)
                                   if p.IsOnLayer(l))
                self.pads.append((rect, p.GetNetCode(), tht,
                                  (mm(c.x), mm(c.y)), layers))
        self.tracks = []     # (layer, a, b, netcode, width)
        self.vias = []       # (centre, netcode)
        for t in board.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                c = t.GetPosition()
                self.vias.append(((mm(c.x), mm(c.y)), t.GetNetCode()))
            else:
                self.tracks.append((t.GetLayer(),
                                    (mm(t.GetStart().x), mm(t.GetStart().y)),
                                    (mm(t.GetEnd().x), mm(t.GetEnd().y)),
                                    t.GetNetCode(), mm(t.GetWidth())))
        self.plan = []
        # The real outline, not its bounding box. base's Edge.Cuts rect
        # carries (radius 3), so the bounding box claims four 3 mm corners the
        # board does not have -- and stitching vias land in thin air there.
        poly = pcbnew.SHAPE_POLY_SET()
        board.GetBoardPolygonOutlines(poly, True)
        self.outline = []
        for oi in range(poly.OutlineCount()):
            o = poly.Outline(oi)
            self.outline.append([(mm(o.CPoint(i).x), mm(o.CPoint(i).y))
                                 for i in range(o.PointCount())])
        self.edge_segs = []
        for ring in self.outline:
            self.edge_segs += list(zip(ring, ring[1:] + ring[:1]))
        bb = board.GetBoardEdgesBoundingBox()
        self.edge = (mm(bb.GetLeft()), mm(bb.GetTop()),
                     mm(bb.GetRight()), mm(bb.GetBottom()))

    # The outline polygon carries a few hundred facets once the corner arcs
    # are flattened, and the router asks about tens of thousands of candidate
    # points. Anything comfortably in the interior skips the polygon entirely.
    SAFE = 6.0        # mm inside the bounding box where no outline detail lives

    def _core(self, p, margin):
        x0, y0, x1, y1 = self.edge
        d = self.SAFE + margin
        return x0 + d <= p[0] <= x1 - d and y0 + d <= p[1] <= y1 - d

    def inside(self, p, margin):
        """True if p is inside the outline by at least `margin`."""
        if self._core(p, margin):
            return True
        hit = False
        for a, b in self.edge_segs:
            if (a[1] > p[1]) != (b[1] > p[1]):
                xx = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                if p[0] < xx:
                    hit = not hit
            if pt_seg(p, a, b) < margin:
                return False
        return hit

    def seg_inside(self, a, b, margin):
        if self._core(a, margin) and self._core(b, margin):
            return True
        if not (self.inside(a, margin) and self.inside(b, margin)):
            return False
        for c, d in self.edge_segs:
            if seg_seg(a, b, c, d) < margin:
                return False
        return True

    # --- feasibility -------------------------------------------------------
    def track_ok(self, path, layer, net, allow_pads=()):
        for a, b in segs(path):
            if not self.seg_inside(a, b, EDGE_T):
                return False
            for (tl, ta, tb, tn, tw) in self.tracks:
                if tl != layer or tn == net:
                    continue
                if seg_seg(a, b, ta, tb) < TRACK / 2 + tw / 2 + CLR:
                    return False
            for (c, vn) in self.vias:
                if vn == net:
                    continue
                if pt_seg(c, a, b) < T_VIA:
                    return False
            for (rect, pn, tht, centre, layers) in self.pads:
                if pn == net or centre in allow_pads or layer not in layers:
                    continue
                if seg_rect(a, b, rect) < T_PAD:
                    return False
        return True

    def via_ok(self, c, net):
        if not self.inside(c, EDGE_V):
            return False
        for (vc, vn) in self.vias:
            # Same-net vias still need spacing. Letting them sit at zero
            # distance stacks stitching vias on top of escape vias, which reads
            # as 18 holes_co_located.
            if math.hypot(vc[0] - c[0], vc[1] - c[1]) < V_VIA:
                return False
        for (rect, pn, tht, centre, layers) in self.pads:
            # Hole-to-hole is a mechanical limit, so it applies even to pads on
            # this via's own net -- a GND stitching via next to a GND through
            # hole is still two drills in the same place.
            if tht and math.hypot(centre[0] - c[0], centre[1] - c[1]) < V_THT_HOLE:
                return False
            if pn == net:
                continue
            # a via spans every copper layer, so any pad is a candidate
            if pt_rect(c, rect) < V_PAD:
                return False
        for (tl, ta, tb, tn, tw) in self.tracks:
            if tn == net:
                continue
            if pt_seg(c, ta, tb) < VIA_PAD / 2 + tw / 2 + CLR:
                return False
        return True

    # --- planning ----------------------------------------------------------
    # Nothing here touches the board. A routing order that strands a net can be
    # thrown away and retried, which is the whole point: the failures are
    # contention, not geometry, so the fix is to try again with the stranded
    # net first rather than to hand-place corridors.
    def add_track(self, path, layer, net):
        for a, b in segs(path):
            self.tracks.append((layer, a, b, net, TRACK))
            self.plan.append(('track', (a, b), layer, net))

    def add_via(self, c, net):
        self.vias.append((c, net))
        self.plan.append(('via', c, None, net))

    def commit(self):
        for kind, geom, layer, net in self.plan:
            if kind == 'track':
                a, b = geom
                t = pcbnew.PCB_TRACK(self.b)
                t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
                t.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
                t.SetWidth(MM(TRACK))
                t.SetLayer(layer)
                t.SetNetCode(net)
                self.b.Add(t)
            else:
                v = pcbnew.PCB_VIA(self.b)
                v.SetPosition(pcbnew.VECTOR2I(MM(geom[0]), MM(geom[1])))
                v.SetWidth(MM(VIA_PAD))
                v.SetDrill(MM(VIA_DRILL))
                v.SetLayerPair(F_CU, B_CU)
                v.SetNetCode(net)
                self.b.Add(v)
        return len(self.plan)

    def commit_last(self):
        """Push just the most recent planned item onto the board."""
        item, self.plan = self.plan[-1:], self.plan[:-1]
        keep, self.plan = self.plan, item
        n = self.commit()
        self.plan = keep
        return n


# ---------------------------------------------------------------------- plan
# net name -> (J1 pad, J2 pad).  Straight out of docs/connector-pinout.md; the
# schematic is the authority and DRC cross-checks it.
LINKS = [
    ('/IO4',              '1',  '32'),
    ('/IO3',              '5',  '31'),
    ('/IO2',              '9',  '30'),
    ('/IO1',              '13', '29'),
    ('/{slash}RE',        '21', '8'),
    ('/ALE',              '25', '17'),
    ('/{slash}WP',        '29', '19'),
    ('/{slash}WE',        '24', '18'),
    ('/{slash}CE',        '28', '9'),
]
ODD_OUT, EVEN_OUT = -1, +1          # escape direction by J1 row
DIP_ROW_PITCH = 15.24               # 0.6 in between the J2 row centrelines
B_CU_PENALTY = 12.0                 # mm of notional cost; see escape_and_route


_REMOVED = []   # module-level so the references outlive the call


def strip(board):
    """Remove this script's own output: vias, and tracks on the inner layers.

    The list is kept alive deliberately. board.Remove() hands ownership back to
    Python, and if the last reference dies the C++ object is freed while the
    board still has stale handles -- after which GetArea() starts returning raw
    SwigPyObjects and anything downstream fails in a way that looks unrelated.
    """
    doomed = [t for t in board.GetTracks()
              if t.GetClass() == 'PCB_VIA' or t.GetLayer() in (IN1, IN2)]
    for t in doomed:
        board.Remove(t)
    _REMOVED.extend(doomed)
    return len(doomed)


def fix_zones(board):
    """KiCad's stock zone cannot reach a 0.4 mm-pitch connector.

    Default clearance is 0.5 mm and the gaps between J1's GND pads are 0.2 mm,
    so the pour cannot approach them from any direction and every GND pad ends
    up unconnected. These are the carrier's settings, which do work.
    """
    changed = []
    for i in range(board.GetAreaCount()):
        z = board.GetArea(i)
        before = (mm(z.GetLocalClearance()), mm(z.GetMinThickness()),
                  mm(z.GetThermalReliefGap()), z.GetPadConnection())
        z.SetLocalClearance(MM(ZONE_CLEARANCE))
        z.SetMinThickness(MM(ZONE_MIN_THICKNESS))
        z.SetThermalReliefGap(MM(ZONE_THERMAL_GAP))
        z.SetThermalReliefSpokeWidth(MM(ZONE_THERMAL_GAP))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        # Fill fragments the pour cannot join to the rest are noise, not
        # copper: DRC reports them as zone-to-zone unconnected.
        z.SetIslandRemovalMode(pcbnew.ISLAND_REMOVAL_MODE_ALWAYS)
        after = (ZONE_CLEARANCE, ZONE_MIN_THICKNESS, ZONE_THERMAL_GAP,
                 pcbnew.ZONE_CONNECTION_FULL)
        if before != after:
            changed.append((z.GetNetname(), before, after))
    return changed


def land_smd_field(board):
    """Give every used J2 pad a landing via on its row centreline.

    J2 is a pair of surface-mount socket strips, so its pads live on F.Cu only
    and their tails stagger +-1.65 mm either side of the row centreline. Every
    other net on this board arrives from B.Cu or an inner layer, so a bare SMD
    pad is unreachable.

    Each used pad therefore gets a 0.15 mm F.Cu stub back to its row
    centreline and a via there. The via sits exactly where the through-hole
    pad centre used to be, which is the coordinate the rest of the router --
    and all the surviving hand routing -- already targets. That is the whole
    point: the field goes surface-mount without moving a single destination.

    The 1.4 mm gap between the two staggered pad columns takes a 0.45/0.20 via
    with 0.475 mm of copper clearance to the nearest pad edge, comfortably
    over the 0.1 mm rule.

    Runs after strip(), which has just removed the previous run's vias.
    """
    j2 = board.FindFootprintByReference('J2')
    ox = mm(j2.GetPosition().x)
    made = []
    for p in j2.Pads():
        net = p.GetNetCode()
        if net == 0 or p.GetNetname().startswith('unconnected-'):
            continue
        px, py = mm(p.GetPosition().x), mm(p.GetPosition().y)
        cx = ox if abs(px - ox) < DIP_ROW_PITCH / 2 else ox + DIP_ROW_PITCH
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(MM(px), MM(py)))
        t.SetEnd(pcbnew.VECTOR2I(MM(cx), MM(py)))
        t.SetWidth(MM(TRACK))
        t.SetLayer(F_CU)
        board.Add(t)
        t.SetNetCode(net)          # must follow Add()
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(MM(cx), MM(py)))
        v.SetWidth(MM(VIA_PAD))
        v.SetDrill(MM(VIA_DRILL))
        v.SetLayerPair(F_CU, B_CU)
        board.Add(v)
        v.SetNetCode(net)
        made.append(p.GetNumber())
    return made


def escape_and_route(m, net, src_pad, dst_pad, layers, direction, cap=None):
    """Stub off the J1 pad, drop a via, then run an inner layer to the DIP pad.

    Returns (via, layer, path) or None. Search order is deliberate: shortest
    total copper wins, so nets take the direct diagonal when it is free and
    only detour around the connector when it is not.
    """
    sx, sy = src_pad
    tx, ty = dst_pad
    best = None
    limit = cap * (abs(tx - sx) + abs(ty - sy)) + B_CU_PENALTY if cap else None

    def shapes(start, sx_, sy_):
        out = []
        out += [polyline([start, (cx, sy_), (cx, ty), (tx, ty)])
                for cx in [110.0 + 0.25 * i for i in range(int(28 / 0.25))]]
        out += [polyline([start, (sx_, cy), (tx, cy), (tx, ty)])
                for cy in [47.0 + 0.5 * i for i in range(int(88 / 0.5))]]
        side = -1 if tx > sx_ else 1
        out += [polyline([start, (tx + side * k, ty), (tx, ty)])
                for k in (1.0, 1.4, 1.8, 2.4, 3.0, 4.0)]
        out.append(polyline([start, (tx, ty)]))
        return out

    # No via at all, if B.Cu happens to be open. J2 is through-hole so its pads
    # are reachable from the bottom, and the hand routing has left whole
    # regions of B.Cu free below the connector.
    for d in (0.65, 0.85, 1.05):
        for direction_ in (direction, -direction):
            ex = sx + direction_ * d
            lead = polyline([(sx, sy), (ex, sy)])
            if not m.track_ok(lead, B_CU, net, allow_pads=(src_pad,)):
                continue
            for path in shapes((ex, sy), ex, sy):
                if len(path) < 2:
                    continue
                # Penalise B.Cu. It is the only layer carrying hand routing,
                # so it is scarce, whereas In1/In2 are empty. Left un-penalised
                # a net takes B.Cu whenever it is a millimetre shorter and
                # walls off the next net that has no inner-layer option.
                cost = length(path) + d + B_CU_PENALTY
                if limit and cost > limit:
                    continue
                if best is not None and cost >= best[0]:
                    continue
                if not m.track_ok(path, B_CU, net, allow_pads=(dst_pad,)):
                    continue
                best = (cost, None, lead, B_CU, path)
    # Try the natural direction first, then the channel between the two pad
    # rows. Several odd-row pins cannot escape outward at all -- CLE's hand
    # route runs down x=122.0 and walls them in -- but the 2.38 mm channel
    # between the rows is open below the connector's midpoint.
    for direction in (direction, -direction):
      for d in (0.65, 0.85, 1.05, 1.25, 1.45, 1.65, 1.85):
        vx = sx + direction * d
        vc = (vx, sy)
        if not m.via_ok(vc, net):
            continue
        stub = polyline([(sx, sy), vc])
        if not m.track_ok(stub, B_CU, net, allow_pads=(src_pad,)):
            continue
        for layer in layers:
            cands = []
            # H-V-H: run out to a vertical corridor, along it, then in
            cands += [polyline([vc, (cx, sy), (cx, ty), (tx, ty)])
                      for cx in [110.0 + 0.25 * i for i in range(int(28 / 0.25))]]
            # V-H-V: over the top or under the bottom of the connector
            cands += [polyline([vc, (vx, cy), (tx, cy), (tx, ty)])
                      for cy in [47.0 + 0.5 * i for i in range(int(88 / 0.5))]]
            # Diagonal, then a short perpendicular run into the pad. A bare
            # straight shot approaches the DIP column at a shallow angle and
            # grazes the neighbouring pads 2.54 mm up the row; entering square
            # to the column keeps that clearance without the cost of a full
            # Manhattan detour.
            side = -1 if tx > vx else 1
            cands += [polyline([vc, (tx + side * k, ty), (tx, ty)])
                      for k in (1.0, 1.4, 1.8, 2.4, 3.0, 4.0)]
            cands.append(polyline([vc, (tx, ty)]))
            for path in cands:
                if len(path) < 2:
                    continue
                cost = length(path)
                if limit and cost > limit:
                    continue
                if best is not None and cost >= best[0]:
                    continue
                if not m.track_ok(path, layer, net, allow_pads=(dst_pad,)):
                    continue
                best = (cost, vc, stub, layer, path)
    if best is None:
        return None
    _, vc, stub, layer, path = best
    m.add_track(stub, B_CU, net)
    if vc is not None:
        m.add_via(vc, net)
    m.add_track(path, layer, net)
    return vc, layer, path


def plan(b, order):
    """Plan one full routing pass in the given net order. Nothing is committed."""
    j1 = b.FindFootprintByReference('J1')
    j2 = b.FindFootprintByReference('J2')
    r1 = b.FindFootprintByReference('R1')

    def pad(fp, num):
        for p in fp.Pads():
            if p.GetNumber() == num:
                return p
        raise KeyError('%s.%s' % (fp.GetReference(), num))

    def xy(p):
        q = p.GetPosition()
        return (round(mm(q.x), 4), round(mm(q.y), 4))

    j2_ox = mm(j2.GetPosition().x)

    def j2t(num):
        """Where a J2 connection actually lands: the landing via on the row
        centreline, not the staggered SMD pad itself."""
        q = pad(j2, num).GetPosition()
        px, py = mm(q.x), mm(q.y)
        cx = j2_ox if abs(px - j2_ox) < DIP_ROW_PITCH / 2 else j2_ox + DIP_ROW_PITCH
        return (round(cx, 4), round(py, 4))

    m = Model(b)
    log, failed = [], []

    vcc = pad(j2, '12').GetNetCode()

    todo = list(order)
    for cap in (1.4, None):
        again = []
        for name, jp1, jp2 in todo:
            p1, p2 = pad(j1, jp1), pad(j2, jp2)
            net = p1.GetNetCode()
            if net != p2.GetNetCode():
                failed.append('%s: J1.%s and J2.%s are on different nets' % (name, jp1, jp2))
                continue
            direction = ODD_OUT if int(jp1) % 2 else EVEN_OUT
            r = escape_and_route(m, net, xy(p1), j2t(jp2), (IN1, IN2), direction, cap)
            if r is None:
                again.append((name, jp1, jp2))
                continue
            vc, layer, path = r
            log.append('ok   %-8s J1.%-2s -> J2.%-2s    %-6s %-17s %.1f mm'
                       % (name, jp1, jp2, b.GetLayerName(layer),
                          ('via (%.2f,%.2f)' % vc) if vc else 'no via', length(path)))
        todo = again
    for name, jp1, jp2 in todo:
        failed.append('%s J1.%s->J2.%s' % (name, jp1, jp2))

    # J1's two VCC pins are on the even row with IO5 between them, so they
    # cannot be bridged along the row. Give each its own escape.
    # Either DIP VCC pin will do -- they are bridged to each other further
    # down -- so a pin that cannot reach 37 is offered 12 before giving up.
    #
    # Pin 10 goes first and pin 6 gets its via as a last resort. Both sit on
    # J1's even row with IO5 at pin 8 wedged between them, so they cannot be
    # bridged along the row, and pin 6 is the more boxed-in of the two: its
    # neighbours' hand routing leaves it no corridor of its own. Reaching the
    # via pin 10 has already placed 0.8 mm away is the short way out, and it
    # is the same net.
    vcc_via = None
    for pin in ('10', '6'):
        pp = xy(pad(j1, pin))
        r, dst = None, None
        targets = [('37', j2t('37')), ('12', j2t('12'))]
        if vcc_via is not None:
            targets.append(('J1.10 via', vcc_via))
        for dst, tgt in targets:
            r = escape_and_route(m, vcc, pp, tgt, (IN1, IN2), EVEN_OUT, None)
            if r is not None:
                break
        if r is None:
            # Pin 6 has no escape of its own: going outward the stub is clear
            # but no via will fit, and going inward a via fits but the stub is
            # blocked. It does not need one. Pin 10 is the same net, 0.8 mm
            # along the row, and already has a via -- so step out to that via's
            # column and run down to it on B.Cu. IO5 at pin 8 sits between the
            # two pads, which is why this cannot go straight down the row; at
            # x = the via column the run clears pin 8's pad by 0.6 mm.
            if vcc_via is not None:
                jog = polyline([pp, (vcc_via[0], pp[1]), vcc_via])
                if len(jog) >= 2 and m.track_ok(jog, B_CU, vcc, allow_pads=(pp,)):
                    m.add_track(jog, B_CU, vcc)
                    log.append('ok   VCC      J1.%-2s -> %-9s %-6s %-17s %.1f mm'
                               % (pin, 'J1.10 via', b.GetLayerName(B_CU),
                                  'no via', length(jog)))
                    continue
            failed.append('VCC J1.%s' % pin)
            continue
        vc, layer, path = r
        if vc is not None and vcc_via is None:
            vcc_via = vc
        log.append('ok   VCC      J1.%-2s -> %-9s %-6s %-17s %.1f mm'
                   % (pin, dst, b.GetLayerName(layer),
                      ('via (%.2f,%.2f)' % vc) if vc else 'no via', length(path)))
    # These two go last on purpose. A via pierces every layer, so an F.Cu track
    # laid across the connector's escape zone blocks vias on the inner layers
    # underneath it -- routing the VCC span first cost IO2 its via by 27 um.
    # Both of these have the whole board to detour through; the escapes do not.
    a, c = xy(pad(r1, '2')), j2t('7')
    net = pad(r1, '2').GetNetCode()
    if m.track_ok(polyline([a, c]), F_CU, net, allow_pads=(a, c)):
        m.add_track(polyline([a, c]), F_CU, net)
        log.append('ok   RY//BY   R1.2 -> J2.7       F.Cu   %.1f mm' % length([a, c]))
    else:
        failed.append('RY//BY R1.2->J2.7')

    # The DIP has two VCC pins; bridge them. F.Cu between the rows is empty
    # (F.Cu between the rows now also carries the landing stubs), but the run
    # has to dodge the escape vias, hence the corridor search.
    a, c = j2t('12'), j2t('37')
    span = None
    # Step clear of the pad column before running along it, or the vertical
    # leg sits on top of the pads 2.54 mm up and down the row. Then search a
    # crossing height that misses the escape vias -- a via blocks every layer,
    # so the straight shot at y=89.93 is no longer available.
    for layer in (F_CU, IN2, IN1):
        for d in (2.0, 2.5, 3.0, 3.5):
            for cy in sorted([47.0 + 0.25 * i for i in range(int(88 / 0.25))],
                             key=lambda y: abs(y - a[1])):
                cand = polyline([a, (a[0] + d, a[1]), (a[0] + d, cy),
                                 (c[0] - d, cy), (c[0] - d, c[1]), c])
                if len(cand) >= 2 and m.track_ok(cand, layer, vcc, allow_pads=(a, c)):
                    span = (cand, layer)
                    break
            if span:
                break
        if span:
            break
    if span:
        m.add_track(span[0], span[1], vcc)
        log.append('ok   VCC      J2.12 -> J2.37     %-6s %.1f mm'
                   % (b.GetLayerName(span[1]), length(span[0])))
    else:
        failed.append('VCC J2.12->J2.37')

    return m, log, failed


def stitch(m, b):
    """GND stitching. via_ok ignores same-net spacing deliberately, so the
    pitch is enforced here rather than carpeting the board with holes."""
    gnd = b.FindNet('GND').GetNetCode()
    pitch, placed = 4.0, []
    for gx in [110.5 + 1.0 * i for i in range(29)]:
        for gy in [47.5 + 1.0 * i for i in range(89)]:
            c = (gx, gy)
            if any(math.hypot(c[0] - q[0], c[1] - q[1]) < pitch for q in placed):
                continue
            if m.via_ok(c, gnd):
                m.add_via(c, gnd)
                placed.append(c)
    return len(placed), pitch


def tie_fragments(m, b, gnd, rounds=4):
    """Fill, then drop a stitching via into any pour fragment that came out
    detached from the main one. Repeat -- tying one fragment can merge others.

    A fragment that keeps a GND pad company but reaches nothing else is not an
    island as far as KiCad is concerned, so island removal will not clear it;
    it has to be connected or squeezed out.
    """
    layers = (F_CU, IN1, IN2, B_CU)
    for _ in range(rounds):
        pcbnew.ZONE_FILLER(b).Fill(b.Zones())
        stranded, biggest = [], {}
        for z in b.Zones():
            if z.GetNetCode() != gnd:
                continue
            for lay in layers:
                ps = z.GetFilledPolysList(lay)
                pieces = []
                for i in range(ps.OutlineCount()):
                    o = ps.Outline(i)
                    pts = [(mm(o.CPoint(k).x), mm(o.CPoint(k).y))
                           for k in range(o.PointCount())]
                    a = abs(sum(pts[k][0] * pts[(k + 1) % len(pts)][1] -
                                pts[(k + 1) % len(pts)][0] * pts[k][1]
                                for k in range(len(pts)))) / 2
                    pieces.append((a, pts))
                if len(pieces) < 2:
                    continue
                pieces.sort(key=lambda q: -q[0])
                biggest[lay] = pieces[0][0]
                stranded += [(lay,) + q for q in pieces[1:]]
        if not stranded:
            return 0
        added, hopeless = 0, 0
        for lay, area, pts in stranded:
            # A via needs to land *inside* the fragment; scanning its bounding
            # box just drops one in the main pour next door, which helps
            # nothing. Anything under ~0.7 mm2 cannot hold a 0.45 mm via at all.
            if area < 0.7:
                hopeless += 1
                continue
            xs = [q[0] for q in pts]
            ys = [q[1] for q in pts]
            placed = False
            steps_x = int((max(xs) - min(xs)) / 0.2) + 1
            steps_y = int((max(ys) - min(ys)) / 0.2) + 1
            for i in range(steps_x):
                for j in range(steps_y):
                    c = (round(min(xs) + 0.2 * i, 3), round(min(ys) + 0.2 * j, 3))
                    if not point_in_poly(c, pts):
                        continue
                    if not m.via_ok(c, gnd):
                        continue
                    m.add_via(c, gnd)
                    m.commit_last()
                    added += 1
                    placed = True
                    break
                if placed:
                    break
        if not added:
            return len(stranded)
    return hopeless


def main():
    dry = '--dry-run' in sys.argv
    b = pcbnew.LoadBoard(BOARD)
    print('removed %d via/inner-layer items from the previous run' % strip(b))
    for name, before, after in fix_zones(b):
        print('zone [%s]: clearance/minw/thermal %s -> %s' % (name, before[:3], after[:3]))
    landed = land_smd_field(b)
    print('landing via + F.Cu stub on %d J2 pads: %s'
          % (len(landed), ' '.join(landed)))

    # Order matters more than anything else here: whichever net is planned
    # first takes the corridor it wants, and a greedy pass strands whoever is
    # left. Rather than tune one ordering by hand, try a spread of them and
    # keep the best, then keep promoting stranded nets until it stops helping.
    j1 = b.FindFootprintByReference('J1')
    j2 = b.FindFootprintByReference('J2')

    def span(link):
        def pos(fp, num):
            for p in fp.Pads():
                if p.GetNumber() == num:
                    return (mm(p.GetPosition().x), mm(p.GetPosition().y))
        a, c = pos(j1, link[1]), pos(j2, link[2])
        ox = mm(j2.GetPosition().x)
        cx = ox if abs(c[0] - ox) < DIP_ROW_PITCH / 2 else ox + DIP_ROW_PITCH
        return abs(a[0] - cx) + abs(a[1] - c[1])

    seeds = [
        list(LINKS),
        list(reversed(LINKS)),
        sorted(LINKS, key=span),
        sorted(LINKS, key=span, reverse=True),
        [l for l in LINKS if int(l[1]) % 2] + [l for l in LINKS if not int(l[1]) % 2],
        [l for l in LINKS if not int(l[1]) % 2] + [l for l in LINKS if int(l[1]) % 2],
    ]
    best, tried = None, 0
    for order in seeds:
        for _ in range(6):
            tried += 1
            m, log, failed = plan(b, order)
            if best is None or len(failed) < len(best[2]):
                best = (m, log, failed)
            if not failed:
                break
            stuck = [l for l in order if any(f.startswith(l[0] + ' ') for f in failed)]
            if not stuck or stuck == order[:len(stuck)]:
                break
            order = stuck + [l for l in order if l not in stuck]
        if not best[2]:
            break
    m, log, failed = best
    print('planned %d orderings; best leaves %d unrouted' % (tried, len(failed)))

    for line in log:
        print(line)
    n, pitch = stitch(m, b)
    print('GND stitching vias: %d at %.0f mm pitch' % (n, pitch))
    print('committed %d items' % m.commit())

    left = tie_fragments(m, b, b.FindNet('GND').GetNetCode())
    print('detached pour fragments remaining: %d' % left)
    if not dry:
        pcbnew.SaveBoard(BOARD, b)
    print('\n%s; %d failed' % ('dry run, not saved' if dry else 'saved', len(failed)))
    for f in failed:
        print('  %s' % f)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
