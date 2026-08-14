#!/usr/bin/env python3
"""Escape-via ("dogbone") placement and clearance arithmetic for BGA fields.

This generalizes ``add_courk_dogbones`` from ``rebuild_courk_interposer.py``,
which hard-codes the 0.8 mm-pitch VFBGA67 carrier: +-0.4 mm diagonal candidate
sites, a 0.525 mm via-to-land floor, a 0.45/0.20 mm via and a 0.15 mm stub.
Every one of those numbers is a parameter here, because none of them survives
a move to 0.5 mm pitch:

    via copper to land copper
        0.45/2 + 0.10 + 0.25/2 = 0.450 mm centre-to-centre
    via *hole* to land copper (the binding one)
        0.20/2 + 0.20 + 0.25/2 = 0.425 mm centre-to-centre
    but the interstitial diagonal at 0.5 mm pitch is only 0.354 mm.

So on a 0.5 mm-pitch field an ordinary 0.45/0.20 via only fits on a *vacant
ball site* (0.500 mm away) or outside the field altogether; the interstitial
diagonal needs both a smaller via and a relaxed drill-to-BGA-pad rule (JLC's
BGA table gives row D "drill to BGA pad spacing 0 mm", which the repo's
global 0.20 mm hole clearance -- quoted from the *inner layer* via-hole-to-
copper row -- currently overrides).  ``Field.reasons_site_illegal`` reports
which floor a rejected site failed, so a caller can tell the two cases apart
instead of just seeing "no candidate".

The solver is deliberately partial: it places what the geometry allows and
*returns* the balls it could not place, with the reason, instead of
asserting.  Callers escape the remainder by hand, or by a second pass with a
different via.

Usage sketch::

    import dogbones
    field = dogbones.Field(board, "U1", "J1")
    result = dogbones.place(field, balls=["H5", "K5"],
                            offsets=dogbones.grid_offsets(0.5,
                                                          include_interstitial=False))
    print(result.report())
    # hand-placed vias go through the same checks:
    print(field.reasons_site_illegal((99.45, 100.25), via=dogbones.ViaSpec(),
                                     net_code=field.pads["H5"].GetNetCode()))
"""

import math
from dataclasses import dataclass, field as dataclass_field

import pcbnew

MM = pcbnew.FromMM
TO_MM = pcbnew.ToMM


@dataclass(frozen=True)
class ViaSpec:
    """Through-via geometry, the stub that reaches it, and its clearances.

    Defaults are the repo-standard 0.45/0.20 mm via and the JLCPCB 4-layer
    floors carried in every project's design settings (0.10 mm copper
    clearance from the netclass, 0.20 mm hole clearance from board setup,
    0.20 mm hole-to-hole).
    """

    land_mm: float = 0.45
    drill_mm: float = 0.20
    stub_width_mm: float = 0.15
    clearance_mm: float = 0.10
    hole_clearance_mm: float = 0.20
    hole_to_hole_mm: float = 0.20

    def via_to_land_mm(self, land_mm):
        """Via centre to different-net land centre floor, copper and hole."""
        return max(self.land_mm / 2 + self.clearance_mm,
                   self.drill_mm / 2 + self.hole_clearance_mm) + land_mm / 2

    def stub_to_land_mm(self, land_mm):
        """Stub centreline to different-net land centre floor."""
        return self.stub_width_mm / 2 + self.clearance_mm + land_mm / 2

    def via_to_via_mm(self, other=None):
        other = other or self
        return max((self.land_mm + other.land_mm) / 2 + self.clearance_mm,
                   (self.drill_mm + other.drill_mm) / 2 + self.hole_to_hole_mm)

    def to_pad_edge_mm(self):
        """Via copper edge clearance to a pad on a layer the via crosses."""
        return self.land_mm / 2 + self.clearance_mm


@dataclass
class Result:
    placed: dict = dataclass_field(default_factory=dict)   # ball -> (x, y) mm
    unsolved: dict = dataclass_field(default_factory=dict)  # ball -> reason

    def report(self):
        lines = ["placed %d dogbone(s)" % len(self.placed)]
        for ball in sorted(self.placed):
            x, y = self.placed[ball]
            lines.append("  %4s  via at (%.3f, %.3f)" % (ball, x, y))
        if self.unsolved:
            lines.append("unsolved %d:" % len(self.unsolved))
            for ball in sorted(self.unsolved):
                lines.append("  %4s  %s" % (ball, self.unsolved[ball]))
        return "\n".join(lines)


def grid_offsets(pitch_mm, reach=1.5, include_interstitial=True):
    """Candidate ball-relative via sites on a half-pitch lattice.

    ``reach`` is in pitches; ``include_interstitial`` keeps the half-pitch
    diagonal sites, which only a via small enough for them can use.
    """
    steps = int(round(reach * 2))
    offsets = []
    for i in range(-steps, steps + 1):
        for j in range(-steps, steps + 1):
            if i == 0 and j == 0:
                continue
            if not include_interstitial and (i % 2 or j % 2):
                continue
            dx, dy = i * pitch_mm / 2, j * pitch_mm / 2
            if math.hypot(dx, dy) > reach * pitch_mm + 1e-9:
                continue
            offsets.append((dx, dy))
    return sorted(offsets, key=lambda offset: (math.hypot(*offset), offset))


def _point_to_rect(x, y, rect):
    left, top, right, bottom = rect
    return math.hypot(max(left - x, 0.0, x - right), max(top - y, 0.0, y - bottom))


def _point_to_segment(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    length2 = vx * vx + vy * vy
    if length2 <= 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / length2))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


class Field:
    """A BGA land field plus the connector it escapes to, in millimetres.

    Holds every geometric test the placer uses so that hand-routed vias can
    be validated against exactly the same arithmetic (``reasons_site_illegal``)
    before they are added to the board.
    """

    def __init__(self, board, field_ref="U1", connector_ref="J1",
                 land_mm=None, connector_keepout_mm=0.325):
        self.board = board
        self.footprint = board.FindFootprintByReference(field_ref)
        self.connector = board.FindFootprintByReference(connector_ref)
        self.field_ref = field_ref
        self.connector_ref = connector_ref
        self.connector_keepout_mm = connector_keepout_mm

        self.pads = {str(pad.GetNumber()): pad for pad in self.footprint.Pads()}
        first = next(iter(self.footprint.Pads()))
        if land_mm is None:
            land_mm = TO_MM(first.GetSize(first.GetLayer()).x)
        self.land_mm = land_mm
        self.lands = [(TO_MM(pad.GetPosition().x), TO_MM(pad.GetPosition().y),
                       pad.GetNetCode(), str(pad.GetNumber()))
                      for pad in self.footprint.Pads()]

        self.connector_pads = []
        for pad in self.connector.Pads():
            box = pad.GetBoundingBox()
            position = pad.GetPosition()
            self.connector_pads.append((
                TO_MM(position.x), TO_MM(position.y), str(pad.GetNumber()),
                (TO_MM(box.GetLeft()), TO_MM(box.GetTop()),
                 TO_MM(box.GetRight()), TO_MM(box.GetBottom()))))

        self.targets = {}
        for pad in self.connector.Pads():
            position = pad.GetPosition()
            self.targets.setdefault(pad.GetNetCode(), []).append(
                (TO_MM(position.x), TO_MM(position.y)))

    def netted_balls(self):
        """Ball names carrying a real net, in ball order."""
        return [ball for ball, pad in sorted(self.pads.items())
                if str(pad.GetNetname())
                and not str(pad.GetNetname()).startswith("unconnected")]

    def reasons_site_illegal(self, site, via, net_code, others=()):
        """Every rule a would-be via at ``site`` breaks; empty list means legal.

        ``others`` are already-committed via sites as (x, y, ViaSpec, net_code).
        """
        x, y = site
        reasons = []
        floor = via.via_to_land_mm(self.land_mm)
        for lx, ly, land_net, number in self.lands:
            if land_net and land_net == net_code:
                continue
            gap = math.hypot(x - lx, y - ly)
            if gap < floor - 1e-9:
                reasons.append("%.3f mm to %s land %s (needs %.3f)"
                               % (gap, self.field_ref, number, floor))
        for cx, cy, number, rect in self.connector_pads:
            gap = math.hypot(x - cx, y - cy)
            if gap < self.connector_keepout_mm - 1e-9:
                reasons.append("%.3f mm to %s land %s centre (needs %.3f)"
                               % (gap, self.connector_ref, number,
                                  self.connector_keepout_mm))
            edge = _point_to_rect(x, y, rect)
            if edge < via.to_pad_edge_mm() - 1e-9:
                reasons.append("%.3f mm to %s land %s copper (needs %.3f)"
                               % (edge, self.connector_ref, number,
                                  via.to_pad_edge_mm()))
        for ox, oy, other_via, other_net in others:
            if other_net and other_net == net_code:
                continue
            gap = math.hypot(x - ox, y - oy)
            need = via.via_to_via_mm(other_via)
            if gap < need - 1e-9:
                reasons.append("%.3f mm to the via at (%.3f, %.3f) (needs %.3f)"
                               % (gap, ox, oy, need))
        return reasons

    def reasons_stub_illegal(self, start, end, via, net_code):
        """Rules a straight stub from ``start`` to ``end`` breaks."""
        floor = via.stub_to_land_mm(self.land_mm)
        reasons = []
        for lx, ly, land_net, number in self.lands:
            if land_net and land_net == net_code:
                continue
            gap = _point_to_segment(lx, ly, start[0], start[1], end[0], end[1])
            if gap < floor - 1e-9:
                reasons.append("stub passes %.3f mm from %s land %s (needs %.3f)"
                               % (gap, self.field_ref, number, floor))
        return reasons

    def target_distance(self, net_code, site):
        """Distance from ``site`` to the nearest connector land of that net."""
        choices = self.targets.get(net_code)
        if not choices:
            return 0.0
        return min(math.hypot(site[0] - tx, site[1] - ty) for tx, ty in choices)


def place(field, balls=None, via=ViaSpec(), offsets=None, fixed_sites=None,
          layer=pcbnew.B_Cu, existing=(), locked=False, dry_run=False):
    """Place one escape via plus its stub per netted land of ``field``.

    ``balls``       restrict to these ball names (default: every netted land).
    ``offsets``     ball-relative candidate sites in mm (see grid_offsets);
                    defaults to the vacant-ball-site lattice for the field's
                    own pitch, inferred from the two closest lands.
    ``fixed_sites`` {ball: (x, y)} absolute overrides, still fully checked.
    ``existing``    via sites already on the board, as (x, y, ViaSpec, net).

    Balls are solved in ascending order of how many legal sites they have, so
    the tightest ball claims its site first.  Nothing is added when
    ``dry_run``.  Returns a Result; the caller decides what to do about
    ``Result.unsolved`` rather than the solver asserting.
    """
    if offsets is None:
        offsets = grid_offsets(_infer_pitch(field), include_interstitial=False)
    fixed_sites = dict(fixed_sites or {})
    wanted = list(balls) if balls is not None else field.netted_balls()

    result = Result()
    committed = [tuple(item) for item in existing]

    candidates = {}
    for ball in wanted:
        pad = field.pads[ball]
        net = pad.GetNetCode()
        bx, by = TO_MM(pad.GetPosition().x), TO_MM(pad.GetPosition().y)
        if ball in fixed_sites:
            sites = [(round(fixed_sites[ball][0], 4),
                      round(fixed_sites[ball][1], 4))]
        else:
            sites = [(round(bx + dx, 4), round(by + dy, 4)) for dx, dy in offsets]
        legal, why = [], []
        for site in sites:
            reasons = field.reasons_site_illegal(site, via, net)
            reasons += field.reasons_stub_illegal((bx, by), site, via, net)
            if reasons:
                why.append("%s: %s" % (_fmt(site), reasons[0]))
                continue
            legal.append((field.target_distance(net, site), site))
        if not legal:
            result.unsolved[ball] = ("no legal site; closest failures: "
                                     + "; ".join(why[:3]) if why
                                     else "no candidate sites offered")
            continue
        candidates[ball] = sorted(legal)

    for ball in sorted(candidates, key=lambda name: (len(candidates[name]), name)):
        pad = field.pads[ball]
        net = pad.GetNetCode()
        bx, by = TO_MM(pad.GetPosition().x), TO_MM(pad.GetPosition().y)
        for _, site in candidates[ball]:
            if field.reasons_site_illegal(site, via, net, committed):
                continue
            result.placed[ball] = site
            committed.append((site[0], site[1], via, net))
            break
        else:
            result.unsolved[ball] = "every legal site is taken by another via"

    if dry_run:
        return result

    for ball, site in sorted(result.placed.items()):
        pad = field.pads[ball]
        track = pcbnew.PCB_TRACK(field.board)
        track.SetStart(pad.GetPosition())
        track.SetEnd(pcbnew.VECTOR2I(MM(site[0]), MM(site[1])))
        track.SetLayer(layer)
        track.SetWidth(MM(via.stub_width_mm))
        track.SetNet(pad.GetNet())
        track.SetLocked(locked)
        field.board.Add(track)
        field.board.Add(make_via(field.board, site, via, pad.GetNet(), locked))
    return result


def make_via(board, site, via, net, locked=False, tented=True):
    """A through via at ``site`` with ``via``'s geometry, tented both faces.

    Vias inside a BGA field are tented: an untented 0.45 mm via land 0.5 mm
    from a 0.25 mm BGA land bridges the two soldermask apertures.
    """
    item = pcbnew.PCB_VIA(board)
    item.SetPosition(pcbnew.VECTOR2I(MM(site[0]), MM(site[1])))
    item.SetWidth(MM(via.land_mm))
    item.SetDrill(MM(via.drill_mm))
    item.SetNet(net)
    item.SetLocked(locked)
    if tented:
        item.SetFrontTentingMode(pcbnew.TENTING_MODE_TENTED)
        item.SetBackTentingMode(pcbnew.TENTING_MODE_TENTED)
    return item


def _infer_pitch(field):
    """Smallest centre-to-centre land spacing in the field, rounded to 10 um."""
    xs = sorted({round(x, 4) for x, _, _, _ in field.lands})
    steps = [b - a for a, b in zip(xs, xs[1:])]
    return round(min(steps), 2) if steps else 0.5


def _fmt(site):
    return "(%.3f, %.3f)" % site
