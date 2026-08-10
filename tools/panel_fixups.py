"""Post-process a kikit panel. Run by tools/panelize.sh under KiCad's Python.

Mouse-bite spacing. kikit treats the `spacing` parameter as a maximum and then
divides each cut evenly, so the realised pitch is usually tighter than asked
for -- 0.75 mm requested comes out as low as 0.667 mm. It also emits a bite
from each side of a tab junction, which lands two drills within 0.13 mm of
each other or exactly on top of one another.

JLCPCB wants 0.2-0.3 mm between mouse bites ("Mouse bites Panel", capabilities
page). Rather than hunt for a `spacing` value whose rounding happens to land
above the limit, cull afterwards: walk the bites and drop any that sits closer
than the limit to one already kept. Losing the occasional bite costs nothing --
the perforation is redundant by design.
"""
import math
import sys

import pcbnew

MIN_GAP_MM = 0.25          # JLC 0.2-0.3 between mouse bites; take the middle
MAX_ERROR_MM = 0.001       # arc faceting; see thin_edge_clearance() below


def cull_mousebites(board):
    """Drop NPTH footprints closer than MIN_GAP_MM edge-to-edge to a kept one."""
    bites = []
    for fp in board.GetFootprints():
        if fp.GetValue() != "NPTH":
            continue
        r = max((p.GetDrillSizeX() for p in fp.Pads()), default=0) / 2.0
        pos = fp.GetPosition()
        bites.append((pos.x, pos.y, r, fp))
    bites.sort(key=lambda b: (b[0], b[1]))

    kept, dropped = [], []      # dropped holds references; pcbnew segfaults without
    for x, y, r, fp in bites:
        clash = False
        for kx, ky, kr, _ in kept:
            if abs(kx - x) > pcbnew.FromMM(4):      # sorted by x, so we can stop
                continue
            gap = math.hypot(kx - x, ky - y) - kr - r
            if gap < pcbnew.FromMM(MIN_GAP_MM):
                clash = True
                break
        if clash:
            dropped.append(fp)
        else:
            kept.append((x, y, r, fp))
    for fp in dropped:
        board.Remove(fp)
    return len(dropped), len(kept)


def tighten_arc_error(board):
    """Drop the arc-approximation error so zone fills stop grazing the edge.

    kikit's millradius corners are arcs. The zone filler polygonises them at
    the board's max_error, and the chord sits inside the true arc by up to that
    much -- which shows up as a 0.1995 mm edge clearance against a 0.2 mm rule.
    It is a faceting artifact, not a real 0.5 um clearance problem, so fix the
    faceting rather than loosening the rule or distorting the pour.
    """
    ds = board.GetDesignSettings()
    ds.m_MaxError = pcbnew.FromMM(MAX_ERROR_MM)


def main(path):
    board = pcbnew.LoadBoard(path)
    tighten_arc_error(board)
    removed, kept = cull_mousebites(board)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(path, board)
    sys.stdout.write(
        "mouse-bite drills: {} kept, {} culled for spacing < {} mm\n".format(
            kept, removed, MIN_GAP_MM
        )
    )


if __name__ == "__main__":
    main(sys.argv[1])
