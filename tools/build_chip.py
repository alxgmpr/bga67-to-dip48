#!/usr/bin/env python3
"""Set up board C's geometry and nets, leaving routing to the PCB editor.

Board C is the device carrier: the real NAND on F.Cu, the DF40 receptacle on
B.Cu.  It keeps carrier A's 8.41 x 7.60 mm outline so the two tile on one
panel and occupy the same footprint on the target board.

Run this only after Update PCB from Schematic has put the non-mirrored BGA and
the receptacle on the board.  It flips whatever footprints it finds; run it on
a stale board and it will flip the wrong ones.

Close KiCad before running this.
"""
from pathlib import Path

import pcbnew

from pinout import DF40

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "chip" / "chip.kicad_pcb"
MM = pcbnew.FromMM
WIDTH_MM = 8.41
HEIGHT_MM = 7.60
# Free strips flank the receptacle body at |y| ~ 2.1..3.8 mm.  Sitting the
# 0402s at 2.9 mm keeps them clear of the connector and leaves the outer
# 0.5 mm of both long edges free so tweezers can get under the board.
CAP_OFFSET_MM = 2.9
# Match carrier A's Edge.Cuts stroke exactly.  The cut follows the path
# centreline so this is cosmetic for fabrication, but the reported bounding
# box is nominal + stroke, and both boards are checked against the same
# 8.42 x 7.61 figure.
EDGE_WIDTH_MM = 0.01


def board_net_name(logical_name):
    if logical_name in ("GND", "VCC"):
        return logical_name
    return "/" + logical_name.replace("/", "{slash}")


def footprint(board, reference):
    """Look a footprint up by reference.

    Not FindFootprintByReference: on KiCad 10 that returns a bare
    SwigPyObject with no FOOTPRINT interface unless something has already
    iterated GetFootprints() and registered the type.  Iterating directly is
    what the rest of the repo's tooling does.
    """
    for candidate in board.GetFootprints():
        if candidate.GetReference() == reference:
            return candidate
    raise LookupError("no footprint %r on this board" % reference)


def collect_removals(board):
    """Gather everything to delete, before the first Remove().

    board.Remove() poisons the SWIG type registry: afterwards GetTracks(),
    GetDrawings() and GetFootprints() all hand back bare SwigPyObjects with no
    methods on them.  So every read has to happen first, in one pass.

    Carrier A's routing all goes: every pad it terminated on has changed side.
    """
    tracks = list(board.GetTracks())
    edges = [d for d in board.GetDrawings() if d.GetLayer() == pcbnew.Edge_Cuts]
    return tracks, edges


def add_outline(board, centre):
    cx, cy = pcbnew.ToMM(centre.x), pcbnew.ToMM(centre.y)
    half_w, half_h = WIDTH_MM / 2, HEIGHT_MM / 2
    corners = [(cx - half_w, cy - half_h), (cx + half_w, cy - half_h),
               (cx + half_w, cy + half_h), (cx - half_w, cy + half_h)]
    for start, end in zip(corners, corners[1:] + corners[:1]):
        edge = pcbnew.PCB_SHAPE(board)
        edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
        edge.SetLayer(pcbnew.Edge_Cuts)
        edge.SetWidth(MM(EDGE_WIDTH_MM))
        edge.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
        edge.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
        board.Add(edge)


def place(board):
    interface = footprint(board, "U1")
    connector = footprint(board, "J1")

    if interface.GetLayer() != pcbnew.F_Cu:
        interface.Flip(interface.GetPosition(), False)
    if connector.GetLayer() != pcbnew.B_Cu:
        connector.Flip(connector.GetPosition(), False)

    # Concentric, exactly.  Board C has no escape-offset allowance: unlike the
    # carrier it does not have to dodge a pre-existing routed topology.
    centre = interface.GetPosition()
    connector.SetPosition(centre)

    nets = board.GetNetsByName()
    for pad in connector.Pads():
        number = str(pad.GetNumber())
        if number.isdigit():
            pad.SetNet(nets[board_net_name(DF40[int(number)])])

    for reference, sign in (("C1", -1), ("C2", 1)):
        cap = footprint(board, reference)
        if cap.GetLayer() != pcbnew.B_Cu:
            cap.Flip(cap.GetPosition(), False)
        cap.SetOrientationDegrees(0)
        cap.SetPosition(pcbnew.VECTOR2I(
            centre.x, centre.y + sign * MM(CAP_OFFSET_MM)))

    return centre


def main():
    board = pcbnew.LoadBoard(str(BOARD))

    # Order matters and is not cosmetic: read everything, then remove, then
    # add.  See collect_removals for why interleaving them does not work.
    centre = place(board)
    tracks, edges = collect_removals(board)
    for item in tracks + edges:
        board.Remove(item)
    removed = len(tracks)
    add_outline(board, centre)
    board.Save(str(BOARD))

    verify = pcbnew.LoadBoard(str(BOARD))
    edges = verify.GetBoardEdgesBoundingBox()
    print("stripped %d carrier tracks" % removed)
    print("chip outline %.2f x %.2f mm"
          % (pcbnew.ToMM(edges.GetWidth()), pcbnew.ToMM(edges.GetHeight())))
    for placed in sorted(verify.GetFootprints(), key=lambda f: f.GetReference()):
        position = placed.GetPosition()
        print("  %-3s %-5s at (%.3f, %.3f)"
              % (placed.GetReference(), verify.GetLayerName(placed.GetLayer()),
                 pcbnew.ToMM(position.x), pcbnew.ToMM(position.y)))


if __name__ == "__main__":
    main()
