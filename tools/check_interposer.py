#!/usr/bin/env python3
"""Verify that board A is a chipless, face-to-face Home interposer."""

from pathlib import Path

import pcbnew


ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "carrier" / "carrier.kicad_pcb"
FOOTPRINT = (
    ROOT
    / "carrier"
    / "lib"
    / "carrier.pretty"
    / "BGA-67_6.5x8.0mm_Layout8x10_P0.8mm_Mirrored_Interposer.kicad_mod"
)
FOOTPRINT_NAME = "BGA-67_6.5x8.0mm_Layout8x10_P0.8mm_Mirrored_Interposer"
DF40_PLUG_FOOTPRINT = (
    ROOT
    / "carrier"
    / "lib"
    / "Connector_Hirose_DF40.pretty"
    / "HIROSE_DF40TC-30DP-0.4V_51_.kicad_mod"
)

ROW_Y_MM = {
    "A": 3.6,
    "B": 2.8,
    "C": 2.0,
    "D": 1.2,
    "E": 0.4,
    "F": -0.4,
    "G": -1.2,
    "H": -2.0,
    "J": -2.8,
    "K": -3.6,
}

# Courk's DF17 pin-pair order, placed in the middle ten pair-columns of the
# 30-pin DF40.  The five surplus pair-columns are ground returns.
COURK_STYLE_DF40 = {
    1: "GND", 2: "GND", 3: "GND", 4: "GND", 5: "GND", 6: "GND",
    7: "RY//BY", 8: "ALE", 9: "/WE", 10: "/WP", 11: "/CE", 12: "/RE",
    13: "CLE", 14: "VCC", 15: "GND", 16: "GND", 17: "GND", 18: "IO5",
    19: "GND", 20: "IO2", 21: "IO6", 22: "IO1", 23: "IO8", 24: "IO3",
    25: "IO7", 26: "IO4", 27: "GND", 28: "GND", 29: "GND", 30: "GND",
}


def mm(value):
    return pcbnew.ToMM(value)


def point_in_ring(point, ring):
    """Return whether an XY point is inside a simple polygon ring."""
    x, y = point
    inside = False
    for first, second in zip(ring, ring[1:] + ring[:1]):
        x1, y1 = first
        x2, y2 = second
        if (y1 > y) != (y2 > y):
            crossing_x = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < crossing_x:
                inside = not inside
    return inside


def check():
    board = pcbnew.LoadBoard(str(BOARD))
    interface = next(fp for fp in board.GetFootprints() if fp.GetReference() == "U1")
    connector = next(fp for fp in board.GetFootprints() if fp.GetReference() == "J1")

    assert interface.GetValue() == "HOME_VFBGA67_INTERFACE", interface.GetValue()
    footprint_name = str(interface.GetFPID().GetLibItemName())
    assert "Mirrored" in footprint_name, footprint_name
    assert len(interface.Models()) == 0, "the chipless interposer must not render a NAND package"
    assert len(interface.GraphicalItems()) == 0, "the board instance must not draw a NAND body"

    # The top-side DF40 and bottom-side motherboard land field share the exact
    # centre of the cross.  This keeps both faces mechanically symmetric and
    # leaves routing decisions to the human router.
    assert connector.GetPosition() == interface.GetPosition(), (
        "carrier J1 and U1 must be concentric"
    )

    # The manufacturer model uses MT1 as its STEP origin.  The footprint needs
    # all four non-electrical corner contacts and the inverse origin transform.
    connector_pads = {str(pad.GetNumber()): pad for pad in connector.Pads()}
    assert {"MT1", "MT2", "MT3", "MT4"} <= connector_pads.keys(), (
        "DF40TC plug is missing its four mechanical corner lands"
    )
    assert len(connector.Models()) == 1, "DF40TC plug must carry one verified STEP model"
    model = connector.Models()[0]
    assert str(model.m_Filename).endswith("DF40TC-30DP-0.4V(51).STEP")
    assert abs(model.m_Offset.x - (-3.275)) < 1e-6
    assert abs(model.m_Offset.y - (-1.355)) < 1e-6
    assert abs(model.m_Offset.z) < 1e-6
    assert (model.m_Rotation.x, model.m_Rotation.y, model.m_Rotation.z) == (0.0, 0.0, 0.0)
    assert (model.m_Scale.x, model.m_Scale.y, model.m_Scale.z) == (1.0, 1.0, 1.0)

    plug_library = pcbnew.FootprintLoad(
        str(DF40_PLUG_FOOTPRINT.parent), DF40_PLUG_FOOTPRINT.stem
    )
    assert plug_library is not None
    assert {"MT1", "MT2", "MT3", "MT4"} <= {
        str(pad.GetNumber()) for pad in plug_library.Pads()
    }
    assert len(plug_library.Models()) == 1

    for pad in interface.Pads():
        ball = str(pad.GetNumber())
        row, column = ball[0], int(ball[1:])
        position = pad.GetFPRelativePosition()
        expected_x = -(column - 4.5) * 0.8
        expected_y = ROW_Y_MM[row]
        assert abs(mm(position.x) - expected_x) < 1e-6, (
            f"ball {ball}: x={mm(position.x):.3f}, expected mirrored x={expected_x:.3f}"
        )
        assert abs(mm(position.y) - expected_y) < 1e-6, (
            f"ball {ball}: y={mm(position.y):.3f}, expected y={expected_y:.3f}"
        )

    library_interface = pcbnew.FootprintLoad(str(FOOTPRINT.parent), FOOTPRINT_NAME)
    assert library_interface is not None
    assert library_interface.GetValue() == "HOME_VFBGA67_INTERFACE"
    assert len(library_interface.Models()) == 0
    for pad in library_interface.Pads():
        ball = str(pad.GetNumber())
        row, column = ball[0], int(ball[1:])
        position = pad.GetFPRelativePosition()
        assert abs(mm(position.x) - (-(column - 4.5) * 0.8)) < 1e-6
        assert abs(mm(position.y) - ROW_Y_MM[row]) < 1e-6

    # Courk's rev-3 board is a 6.7 x 10.2 mm notched cross.  U1 is rotated 90
    # degrees on this design.  Keep the 10.2 mm length and cross topology, but
    # widen the centre to 7.6 mm for the larger 30-pin DF40 escape corridor.
    edge_box = board.GetBoardEdgesBoundingBox()
    # GetBoardEdgesBoundingBox includes half the 0.05 mm edge stroke on both
    # sides, hence 10.25 x 7.65 for the nominal 10.20 x 7.60 outline.
    assert abs(mm(edge_box.GetWidth()) - 10.25) < 0.02, mm(edge_box.GetWidth())
    assert abs(mm(edge_box.GetHeight()) - 7.65) < 0.02, mm(edge_box.GetHeight())
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, True)
    assert outline.OutlineCount() == 1
    contour = outline.Outline(0)
    ring = [
        (mm(contour.CPoint(index).x), mm(contour.CPoint(index).y))
        for index in range(contour.PointCount())
    ]
    centre = interface.GetPosition()
    cx, cy = mm(centre.x), mm(centre.y)
    for relative in ((0, 3.50), (0, -3.50), (4.75, 0), (-4.75, 0)):
        assert point_in_ring((cx + relative[0], cy + relative[1]), ring), relative
    for relative in ((4.75, 3.50), (4.75, -3.50), (-4.75, 3.50), (-4.75, -3.50)):
        assert not point_in_ring((cx + relative[0], cy + relative[1]), ring), relative

    # This must stay on JLCPCB's ordinary 4-layer process.  Courk escapes the
    # BGA with 0.20 mm drilled dogbones; no blind/buried/microvias and no
    # pad-centred VIPPO are required here.
    interface_pads = list(interface.Pads())
    vias = [item for item in board.GetTracks() if item.GetClass() == "PCB_VIA"]
    for via in vias:
        assert via.GetViaType() == pcbnew.VIATYPE_THROUGH, (
            f"{via.GetNetname()} uses non-through via type {via.GetViaType()}"
        )
        assert mm(via.GetDrillValue()) >= 0.20 - 1e-6, mm(via.GetDrillValue())
        assert mm(via.GetWidth(pcbnew.F_Cu)) >= 0.45 - 1e-6, mm(via.GetWidth(pcbnew.F_Cu))
        via_position = via.GetPosition()
        for pad in interface_pads:
            pad_position = pad.GetPosition()
            separation = (
                (mm(via_position.x - pad_position.x) ** 2)
                + (mm(via_position.y - pad_position.y) ** 2)
            ) ** 0.5
            assert separation >= 0.35, (
                f"{via.GetNetname()} via is centred in/too near U1 pad {pad.GetNumber()} "
                f"({separation:.3f} mm)"
            )

    def board_net_name(logical_name):
        if logical_name in ("GND", "VCC"):
            return logical_name
        return "/" + logical_name.replace("/", "{slash}")

    # The direct Courk ordering removes the checkerboard crossings that drove
    # the old HDI escape.  Both halves of the face-to-face DF40 must change as
    # one atomic pinout.
    for board_path in (BOARD, ROOT / "base" / "base.kicad_pcb"):
        checked_board = pcbnew.LoadBoard(str(board_path))
        connector = checked_board.FindFootprintByReference("J1")
        actual = {
            int(str(pad.GetNumber())): str(pad.GetNetname())
            for pad in connector.Pads()
            if str(pad.GetNumber()).isdigit()
        }
        expected = {
            pin: board_net_name(net)
            for pin, net in COURK_STYLE_DF40.items()
        }
        assert actual == expected, f"{board_path}: DF40 is not Courk-ordered"

    base_board = pcbnew.LoadBoard(str(ROOT / "base" / "base.kicad_pcb"))
    base_connector = base_board.FindFootprintByReference("J1")
    base_edges = base_board.GetBoardEdgesBoundingBox()
    base_centre = pcbnew.VECTOR2I(
        (base_edges.GetLeft() + base_edges.GetRight()) // 2,
        (base_edges.GetTop() + base_edges.GetBottom()) // 2,
    )
    assert base_connector.GetPosition() == base_centre, "base J1 must be outline-centred"

    footprint_text = FOOTPRINT.read_text()
    assert "Chipless mirrored VFBGA-67 land interface" in footprint_text
    assert "no NAND component is fitted" in footprint_text

    documentation = "\n".join(
        (ROOT / name).read_text()
        for name in (
            "README.md",
            "docs/HANDOFF.md",
            "docs/NEXT-SESSION-mechanical.md",
            "docs/connector-pinout.md",
        )
    )
    for required in (
        "chipless interposer",
        "NAND remains in the XGecu adapter",
        "mirrored VFBGA67",
    ):
        assert required in documentation, f"documentation omits: {required}"
    for obsolete in (
        "ours carries a desoldered chip",
        "carrier — with the flash on it",
        "U1 (flash)",
    ):
        assert obsolete not in documentation, f"obsolete architecture remains: {obsolete}"


if __name__ == "__main__":
    check()
    print("interposer geometry OK: chipless, mirrored, concentric; route may be unfinished")
