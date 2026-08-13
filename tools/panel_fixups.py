"""Turn KiKit's 5x5 placement into the JLCPCB V-cut production panel.

KiKit supplies the repeated copper, 5 mm frame, tooling holes, and fiducials.
This pass replaces every carrier's routed cross outline with a rectangular,
full-panel V-score grid.  A 2.2 x 1.2 mm NPTH oblong relief centered at each
carrier corner recreates the shallow ears after the scores are separated.

JLC must approve score lines crossing the relief slots during CAM review.
"""
import sys

import pcbnew
from kikit.panelize import KIKIT_LIB


BOARD_WIDTH_MM = 10.2
BOARD_HEIGHT_MM = 7.6
RELIEF_X_MM = 2.2
RELIEF_Y_MM = 1.2
VCUT_CLEARANCE_MM = 0.3
EDGE_WIDTH_MM = 0.1
FID_EDGE_OFFSET_MM = 3.0
CLEARANCE_MARGIN_MM = 0.01


def mm(value):
    return pcbnew.ToMM(value)


def point(x, y):
    return pcbnew.VECTOR2I(pcbnew.FromMM(x), pcbnew.FromMM(y))


def edge_extents(board):
    xs, ys = [], []
    for drawing in board.GetDrawings():
        if drawing.GetLayer() != pcbnew.Edge_Cuts:
            continue
        for position in (drawing.GetStart(), drawing.GetEnd()):
            xs.append(mm(position.x))
            ys.append(mm(position.y))
    if not xs:
        raise RuntimeError("panel has no Edge.Cuts geometry")
    return min(xs), min(ys), max(xs), max(ys)


def add_edge(board, start, end):
    segment = pcbnew.PCB_SHAPE(board)
    segment.SetShape(pcbnew.S_SEGMENT)
    segment.SetLayer(pcbnew.Edge_Cuts)
    segment.SetStart(point(*start))
    segment.SetEnd(point(*end))
    segment.SetWidth(pcbnew.FromMM(EDGE_WIDTH_MM))
    board.Add(segment)


def score_axes(carrier_centers):
    xs = sorted({round(x, 6) for x, _ in carrier_centers})
    ys = sorted({round(y, 6) for _, y in carrier_centers})
    score_xs = sorted(
        {x + dx for x in xs for dx in (-BOARD_WIDTH_MM / 2, BOARD_WIDTH_MM / 2)}
    )
    score_ys = sorted(
        {y + dy for y in ys for dy in (-BOARD_HEIGHT_MM / 2, BOARD_HEIGHT_MM / 2)}
    )
    return score_xs, score_ys


def add_rectangle(polyset, minx, miny, maxx, maxy):
    outline = polyset.NewOutline()
    for x, y in ((minx, miny), (maxx, miny), (maxx, maxy), (minx, maxy)):
        polyset.Append(point(x, y), outline)


def carve_score_clearance(board, carrier_centers, extents):
    """Remove zone copper for 0.3 mm on both sides of every score line."""
    minx, miny, maxx, maxy = extents
    score_xs, score_ys = score_axes(carrier_centers)
    half_width = VCUT_CLEARANCE_MM + CLEARANCE_MARGIN_MM
    mask = pcbnew.SHAPE_POLY_SET()
    for x in score_xs:
        add_rectangle(mask, x - half_width, miny, x + half_width, maxy)
    for y in score_ys:
        add_rectangle(mask, minx, y - half_width, maxx, y + half_width)
    for center_x, center_y in carrier_centers:
        for dx in (-BOARD_WIDTH_MM / 2, BOARD_WIDTH_MM / 2):
            for dy in (-BOARD_HEIGHT_MM / 2, BOARD_HEIGHT_MM / 2):
                relief_x, relief_y = center_x + dx, center_y + dy
                add_rectangle(
                    mask,
                    relief_x - RELIEF_X_MM / 2 - half_width,
                    relief_y - RELIEF_Y_MM / 2 - half_width,
                    relief_x + RELIEF_X_MM / 2 + half_width,
                    relief_y + RELIEF_Y_MM / 2 + half_width,
                )
    mask.Simplify()

    for zone in board.Zones():
        for layer in zone.GetLayerSet().Seq():
            if not zone.HasFilledPolysForLayer(layer):
                continue
            copper = zone.GetFilledPolysList(layer)
            copper.BooleanSubtract(mask)
            # Zone fills are serialized as fractured outlines; restore that
            # representation so internal clearance holes remain holes.
            copper.Fracture()
            zone.SetFilledPolysList(layer, copper)


def replace_edges_with_vcuts(board, carrier_centers):
    minx, miny, maxx, maxy = edge_extents(board)
    removed_edges = []
    for drawing in list(board.GetDrawings()):
        if drawing.GetLayer() == pcbnew.Edge_Cuts:
            board.Remove(drawing)
            # Keep SWIG proxies alive until after SaveBoard. Releasing removed
            # board items early corrupts later GetFootprints() iteration.
            removed_edges.append(drawing)

    # The only closed profile is the 85 x 72 mm outside of the panel.
    add_edge(board, (minx, miny), (maxx, miny))
    add_edge(board, (maxx, miny), (maxx, maxy))
    add_edge(board, (maxx, maxy), (minx, maxy))
    add_edge(board, (minx, maxy), (minx, miny))

    score_xs, score_ys = score_axes(carrier_centers)
    for score_x in score_xs:
        add_edge(board, (score_x, miny), (score_x, maxy))
    for score_y in score_ys:
        add_edge(board, (minx, score_y), (maxx, score_y))

    return (minx, miny, maxx, maxy), removed_edges


def reposition_global_fiducials(board, carrier_centers, extents):
    minx, miny, maxx, maxy = extents
    del minx, maxx
    carrier_xs = sorted({round(x, 6) for x, _ in carrier_centers})
    locations = {
        "1": (carrier_xs[0], miny + FID_EDGE_OFFSET_MM),
        "2": (carrier_xs[-1], miny + FID_EDGE_OFFSET_MM),
        "3": (carrier_xs[0], maxy - FID_EDGE_OFFSET_MM),
    }
    moved = 0
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        if not reference.startswith("KiKit_FID_"):
            continue
        footprint.SetPosition(point(*locations[reference.rsplit("_", 1)[-1]]))
        moved += 1
    if moved != 6:
        raise RuntimeError("expected six front/back fiducial footprints")


def add_relief(board, pad_layers, position, index):
    footprint = pcbnew.FOOTPRINT(board)
    footprint.SetPosition(point(*position))
    footprint.SetReference("VCUT_RELIEF_{}".format(index))
    footprint.SetValue("VCUT_CORNER_RELIEF")
    footprint.Reference().SetVisible(False)
    footprint.Value().SetVisible(False)
    if hasattr(footprint, "SetExcludedFromBOM"):
        footprint.SetExcludedFromBOM(True)
    if hasattr(footprint, "SetExcludedFromPosFiles"):
        footprint.SetExcludedFromPosFiles(True)
    if hasattr(footprint, "SetBoardOnly"):
        footprint.SetBoardOnly(True)

    pad = pcbnew.PAD(footprint)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_NPTH)
    pad.SetLayerSet(pad_layers)
    size = point(RELIEF_X_MM, RELIEF_Y_MM)
    pad.SetShape(pcbnew.PAD_SHAPE_OVAL)
    pad.SetDrillShape(pcbnew.PAD_DRILL_SHAPE_OBLONG)
    pad.SetSize(size)
    pad.SetDrillSize(size)
    footprint.Add(pad)
    board.Add(footprint)


def add_corner_reliefs(board, pad_layers, carrier_centers):
    positions = []
    for center_x, center_y in carrier_centers:
        for dx in (-BOARD_WIDTH_MM / 2, BOARD_WIDTH_MM / 2):
            for dy in (-BOARD_HEIGHT_MM / 2, BOARD_HEIGHT_MM / 2):
                positions.append((center_x + dx, center_y + dy))
    for index, position in enumerate(positions, 1):
        add_relief(board, pad_layers, position, index)
    return len(positions)


def main(path):
    board = pcbnew.LoadBoard(path)
    relief_template = pcbnew.FootprintLoad(KIKIT_LIB, "NPTH")
    if relief_template is None:
        raise RuntimeError("cannot load KiKit NPTH footprint")
    relief_pad_layers = next(iter(relief_template.Pads())).GetLayerSet()
    carriers = [
        footprint
        for footprint in board.GetFootprints()
        if footprint.GetValue() == "HOME_VFBGA67_INTERFACE"
    ]
    if len(carriers) != 25:
        raise RuntimeError("expected 25 carriers, found {}".format(len(carriers)))
    centers = [(mm(fp.GetPosition().x), mm(fp.GetPosition().y)) for fp in carriers]

    # Refill while KiKit's 25 closed carrier outlines still exist. Once those
    # outlines become open full-panel score lines, KiCad cannot recompute zone
    # clipping reliably. The saved fills therefore retain 0.3 mm score relief.
    settings = board.GetDesignSettings()
    settings.m_CopperEdgeClearance = pcbnew.FromMM(VCUT_CLEARANCE_MM)
    settings.m_MaxError = pcbnew.FromMM(0.001)
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    extents = edge_extents(board)
    carve_score_clearance(board, centers, extents)

    (minx, miny, maxx, maxy), removed_edges = replace_edges_with_vcuts(
        board, centers
    )
    reposition_global_fiducials(board, centers, (minx, miny, maxx, maxy))
    relief_count = add_corner_reliefs(board, relief_pad_layers, centers)

    pcbnew.SaveBoard(path, board)
    del removed_edges

    sys.stdout.write(
        "V-cut panel: {:.2f} x {:.2f} mm, 20 full-length scores, "
        "{} corner relief slots\n".format(maxx - minx, maxy - miny, relief_count)
    )


if __name__ == "__main__":
    main(sys.argv[1])
