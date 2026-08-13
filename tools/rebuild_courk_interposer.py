#!/usr/bin/env python3
"""Prepare the carrier for the Courk-style standard-through-via reroute.

This deliberately removes the carrier routing and leaves a clean ratsnest for
manual work in KiCad.
"""

from pathlib import Path
import math

import pcbnew

from pinout import DF40


ROOT = Path(__file__).resolve().parents[1]
CARRIER = ROOT / "carrier" / "carrier.kicad_pcb"
MM = pcbnew.FromMM


def board_net_name(logical_name):
    if logical_name in ("GND", "VCC"):
        return logical_name
    return "/" + logical_name.replace("/", "{slash}")


def set_connector_pinout(board):
    connector = board.FindFootprintByReference("J1")
    interface = board.FindFootprintByReference("U1")
    # Keep the top-side connector concentric with the bottom-side motherboard
    # land field.  Routing is intentionally left entirely to the PCB editor.
    connector.SetPosition(interface.GetPosition())
    # Preserve the routed carrier orientation and canonical pin sequence.
    connector.SetOrientationDegrees(180)
    nets = board.GetNetsByName()
    for pad in connector.Pads():
        number = str(pad.GetNumber())
        if not number.isdigit():
            continue
        net_name = board_net_name(DF40[int(number)])
        pad.SetNet(nets[net_name])


def replace_outline(board):
    removed = []
    for drawing in list(board.GetDrawings()):
        if drawing.GetLayer() == pcbnew.Edge_Cuts:
            board.Remove(drawing)
            removed.append(drawing)

    interface = board.FindFootprintByReference("U1")
    centre = interface.GetPosition()
    cx, cy = pcbnew.ToMM(centre.x), pcbnew.ToMM(centre.y)
    # Courk rev-3 rotated 90 degrees to follow this board's U1 orientation.
    # Courk's cross is 10.2 x 6.7 mm after rotation.  Retain its 10.2 mm
    # length and notch proportions, but widen the centre to 7.6 mm for the
    # larger 30-pin DF40 escape corridor.
    relative = [
        (-5.10, -3.20), (-4.00, -3.20), (-4.00, -3.80),
        (4.00, -3.80), (4.00, -3.20), (5.10, -3.20),
        (5.10, 3.20), (4.00, 3.20), (4.00, 3.80),
        (-4.00, 3.80), (-4.00, 3.20), (-5.10, 3.20),
    ]
    points = [(cx + x, cy + y) for x, y in relative]
    for start, end in zip(points, points[1:] + points[:1]):
        edge = pcbnew.PCB_SHAPE(board)
        edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
        edge.SetLayer(pcbnew.Edge_Cuts)
        edge.SetWidth(MM(0.05))
        edge.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
        edge.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
        board.Add(edge)
    return removed


def add_courk_dogbones(board, balls=None, fixed=False):
    """Give every used VFBGA land its own ordinary through-via escape."""
    interface = board.FindFootprintByReference("U1")
    connector = board.FindFootprintByReference("J1")
    used_pads = [pad for pad in interface.Pads() if not str(pad.GetNetname()).startswith("unconnected")]
    if balls is not None:
        used_pads = [pad for pad in used_pads if str(pad.GetNumber()) in balls]
    all_pads = list(interface.Pads())

    targets = {}
    for pad in connector.Pads():
        targets.setdefault(pad.GetNetCode(), []).append(pad.GetPosition())

    connector_rectangles = []
    for pad in connector.Pads():
        box = pad.GetBoundingBox()
        connector_rectangles.append(
            (
                pcbnew.ToMM(box.GetLeft()), pcbnew.ToMM(box.GetTop()),
                pcbnew.ToMM(box.GetRight()), pcbnew.ToMM(box.GetBottom()),
            )
        )

    def point_to_rectangle(point, rectangle):
        x, y = pcbnew.ToMM(point.x), pcbnew.ToMM(point.y)
        left, top, right, bottom = rectangle
        dx = max(left - x, 0, x - right)
        dy = max(top - y, 0, y - bottom)
        return math.hypot(dx, dy)

    def key(point):
        return (round(pcbnew.ToMM(point.x), 4), round(pcbnew.ToMM(point.y), 4))

    candidates = {}
    pads_by_ball = {str(pad.GetNumber()): pad for pad in used_pads}
    for pad in used_pads:
        ball = str(pad.GetNumber())
        position = pad.GetPosition()
        choices = []
        for dx in (-0.4, 0.4):
            for dy in (-0.4, 0.4):
                candidate = pcbnew.VECTOR2I(position.x + MM(dx), position.y + MM(dy))
                # 0.45 mm via + 0.40 mm land + 0.10 mm clearance needs
                # 0.525 mm centre spacing.  A 0.4/0.4 diagonal is 0.566 mm.
                if any(
                    other is not pad
                    and math.hypot(
                        pcbnew.ToMM(candidate.x - other.GetPosition().x),
                        pcbnew.ToMM(candidate.y - other.GetPosition().y),
                    ) < 0.525
                    for other in all_pads
                ):
                    continue
                # A through via exists on F.Cu too.  Keep its 0.225 mm copper
                # radius plus 0.10 mm clearance away from every DF40 land.
                if any(point_to_rectangle(candidate, rectangle) < 0.325
                       for rectangle in connector_rectangles):
                    continue
                target_distance = min(
                    math.hypot(
                        pcbnew.ToMM(candidate.x - target.x),
                        pcbnew.ToMM(candidate.y - target.y),
                    )
                    for target in targets[pad.GetNetCode()]
                )
                choices.append((target_distance, key(candidate), candidate))
        candidates[ball] = sorted(choices)
        assert candidates[ball], f"no dogbone candidate for U1 {ball}"

    # Local bipartite matching: one interstitial via site per used land.  The
    # target-distance ordering biases each short escape toward its DF40 pad.
    site_owner = {}

    def assign(ball, visited):
        for _, site, _ in candidates[ball]:
            if site in visited:
                continue
            visited.add(site)
            owner = site_owner.get(site)
            if owner is None or assign(owner, visited):
                site_owner[site] = ball
                return True
        return False

    for ball in sorted(pads_by_ball, key=lambda item: len(candidates[item])):
        assert assign(ball, set()), f"could not match dogbone for U1 {ball}"

    pad_sites = {ball: site for site, ball in site_owner.items()}
    for ball, pad in pads_by_ball.items():
        site = pad_sites[ball]
        candidate = next(value for _, choice, value in candidates[ball] if choice == site)
        track = pcbnew.PCB_TRACK(board)
        track.SetStart(pad.GetPosition())
        track.SetEnd(candidate)
        track.SetLayer(pcbnew.B_Cu)
        track.SetWidth(MM(0.15))
        track.SetNet(pad.GetNet())
        track.SetLocked(fixed)
        board.Add(track)

        via = pcbnew.PCB_VIA(board)
        via.SetPosition(candidate)
        via.SetWidth(MM(0.45))
        via.SetDrill(MM(0.20))
        via.SetNet(pad.GetNet())
        via.SetLocked(fixed)
        board.Add(via)


def main():
    board = pcbnew.LoadBoard(str(CARRIER))
    set_connector_pinout(board)
    replace_outline(board)

    removed = []
    for item in list(board.GetTracks()):
        board.Remove(item)
        removed.append(item)
    # Old pours encode the rounded-rectangle route and export as dozens of
    # disconnected Specctra conduction areas.  Route the new topology cleanly;
    # ground copper can be re-added after the dogbone route is stable.
    for zone in list(board.Zones()):
        board.Remove(zone)
        removed.append(zone)
    pcbnew.SaveBoard(str(CARRIER), board)
    print("carrier prepared: concentric Courk cross/DF40, all routing removed")


if __name__ == "__main__":
    main()
