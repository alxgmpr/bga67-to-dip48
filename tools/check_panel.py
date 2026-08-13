#!/usr/bin/env python3
"""Check the generated carrier panel's JLCPCB-facing invariants."""

import math
import sys
from pathlib import Path

import pcbnew

PANEL = Path(__file__).resolve().parents[1] / "panel" / "carrier-panel.kicad_pcb"


def mm(value):
    return pcbnew.ToMM(value)


def positions(items):
    return [(mm(item.GetPosition().x), mm(item.GetPosition().y)) for item in items]


def point(value):
    return mm(value.x), mm(value.y)


def non_collinear(points):
    points = list(dict.fromkeys(points))
    if len(points) < 3:
        return False
    (ax, ay), (bx, by), (cx, cy) = points[:3]
    return not math.isclose((bx - ax) * (cy - ay), (by - ay) * (cx - ax))


def unique_axis(values):
    return sorted({round(value, 3) for value in values})


def assert_pitch(values, expected):
    values = unique_axis(values)
    assert len(values) == 5
    for first, second in zip(values, values[1:]):
        assert math.isclose(second - first, expected, abs_tol=0.001)


def check(path=PANEL):
    board = pcbnew.LoadBoard(str(path))
    footprints = list(board.GetFootprints())

    carriers = [
        fp for fp in footprints if fp.GetValue() == "HOME_VFBGA67_INTERFACE"
    ]
    assert len(carriers) == 25, "V-cut panel must contain 25 carrier boards"
    carrier_positions = positions(carriers)
    assert_pitch((x for x, _ in carrier_positions), 16.2)
    assert_pitch((y for _, y in carrier_positions), 13.6)

    edge_points = []
    for drawing in board.GetDrawings():
        if drawing.GetLayer() == pcbnew.Edge_Cuts:
            edge_points.extend((point(drawing.GetStart()), point(drawing.GetEnd())))
    minx = min(x for x, _ in edge_points)
    miny = min(y for _, y in edge_points)
    maxx = max(x for x, _ in edge_points)
    maxy = max(y for _, y in edge_points)
    assert math.isclose(maxx - minx, 85.0, abs_tol=0.01)
    assert math.isclose(maxy - miny, 72.0, abs_tol=0.01)

    tooling = [fp for fp in footprints if fp.GetReference().startswith("KiKit_TO_")]
    assert len(tooling) == 3, "JLC assembly panel must use three asymmetric tooling holes"
    assert non_collinear(positions(tooling)), "tooling holes must be asymmetric"
    for footprint in tooling:
        pads = list(footprint.Pads())
        assert len(pads) == 1
        drill = mm(pads[0].GetDrillSizeX())
        assert 2.0 <= drill <= 4.0, "JLC tooling holes must be 2.0-4.0 mm"

    fiducials = [
        fp for fp in footprints if fp.GetReference().startswith("KiKit_FID_")
    ]
    assert len(fiducials) == 6, "three fiducial locations are required on both sides"
    assert non_collinear(positions(fiducials)), "global fiducials must be asymmetric"

    mouse_bites = [
        fp for fp in footprints if fp.GetReference().startswith("KiKit_MB_")
    ]
    assert not mouse_bites, "V-cut panel must not contain mouse bites"

    reliefs = [
        fp for fp in footprints if fp.GetReference().startswith("VCUT_RELIEF_")
    ]
    assert len(reliefs) == 100, "each carrier must have four corner relief slots"
    for footprint in reliefs:
        pads = list(footprint.Pads())
        assert len(pads) == 1
        assert pads[0].GetAttribute() == pcbnew.PAD_ATTRIB_NPTH
        assert pads[0].GetDrillShape() == pcbnew.PAD_DRILL_SHAPE_OBLONG
        drill = sorted((mm(pads[0].GetDrillSizeX()), mm(pads[0].GetDrillSizeY())))
        assert math.isclose(drill[0], 1.2, abs_tol=0.001)
        assert math.isclose(drill[1], 2.2, abs_tol=0.001)
    for fid_x, fid_y in positions(fiducials):
        for relief_x, relief_y in positions(reliefs):
            assert math.hypot(fid_x - relief_x, fid_y - relief_y) >= 2.5, (
                "fiducial mask must stay clear of every V-cut relief slot"
            )

    vertical, horizontal = [], []
    for drawing in board.GetDrawings():
        if drawing.GetLayer() != pcbnew.Edge_Cuts:
            continue
        if not hasattr(drawing, "GetStart") or not hasattr(drawing, "GetEnd"):
            continue
        start, end = point(drawing.GetStart()), point(drawing.GetEnd())
        if math.isclose(start[0], end[0], abs_tol=0.001):
            if math.isclose(min(start[1], end[1]), miny, abs_tol=0.001) and math.isclose(
                max(start[1], end[1]), maxy, abs_tol=0.001
            ):
                vertical.append(start[0])
        if math.isclose(start[1], end[1], abs_tol=0.001):
            if math.isclose(min(start[0], end[0]), minx, abs_tol=0.001) and math.isclose(
                max(start[0], end[0]), maxx, abs_tol=0.001
            ):
                horizontal.append(start[1])
    assert len(unique_axis(vertical)) == 12, "10 V-cuts plus two outer vertical edges"
    assert len(unique_axis(horizontal)) == 12, "10 V-cuts plus two outer horizontal edges"

    print(
        "panel topology OK: {} carriers, {} tooling holes, {} fiducials, "
        "{} relief slots, 20 V-cuts".format(
            len(carriers), len(tooling), len(fiducials), len(reliefs)
        )
    )


if __name__ == "__main__":
    check(Path(sys.argv[1]) if len(sys.argv) > 1 else PANEL)
