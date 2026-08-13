#!/usr/bin/env python3
"""Verify that board A is a chipless, face-to-face Home interposer."""

from pathlib import Path

import pcbnew

from bga_fit import assert_no_mirror, read_footprint_pads
from pinout import DF40


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
NORMAL_FOOTPRINT = (
    ROOT
    / "carrier"
    / "lib"
    / "carrier.pretty"
    / "BGA-67_6.5x8.0mm_Layout8x10_P0.8mm.kicad_mod"
)
DF40_PLUG_FOOTPRINT = (
    ROOT
    / "carrier"
    / "lib"
    / "Connector_Hirose_DF40.pretty"
    / "HIROSE_DF40TC-30DP-0.4V_51_.kicad_mod"
)
DF40_RECEPTACLE_FOOTPRINT = (
    ROOT
    / "carrier"
    / "lib"
    / "Connector_Hirose_DF40.pretty"
    / "HIROSE_DF40TC_4.0_-30DS-0.4V_51_.kicad_mod"
)


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

    # The routed carrier keeps the connector within 0.20 mm of the motherboard
    # land-field centre.  That small escape-routing offset does not affect the
    # DF40-to-DF40 mating datum, which is defined by J1 itself.
    interface_position = interface.GetPosition()
    connector_position = connector.GetPosition()
    offset = (
        mm(connector_position.x - interface_position.x) ** 2
        + mm(connector_position.y - interface_position.y) ** 2
    ) ** 0.5
    assert offset < 0.20, f"carrier J1/U1 offset is {offset:.3f} mm"

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

    # Plug and receptacle number their longitudinal pad arrays in opposite X
    # directions.  This is the one mechanical mirror required for a face-to-
    # face connection; electrical pin n still mates with electrical pin n.
    receptacle_library = pcbnew.FootprintLoad(
        str(DF40_RECEPTACLE_FOOTPRINT.parent), DF40_RECEPTACLE_FOOTPRINT.stem
    )
    assert receptacle_library is not None
    plug_pads = {
        str(pad.GetNumber()): pad for pad in plug_library.Pads()
        if str(pad.GetNumber()).isdigit()
    }
    receptacle_pads = {
        str(pad.GetNumber()): pad for pad in receptacle_library.Pads()
        if str(pad.GetNumber()).isdigit()
    }
    assert plug_pads.keys() == receptacle_pads.keys()
    for number in plug_pads:
        plug_position = plug_pads[number].GetFPRelativePosition()
        receptacle_position = receptacle_pads[number].GetFPRelativePosition()
        assert abs(mm(plug_position.x) + mm(receptacle_position.x)) < 1e-6, number
        assert mm(plug_position.y) * mm(receptacle_position.y) > 0, number

    # Carrier A's B.Cu pads and the motherboard's lands are both seen looking
    # down at the assembly, so the pattern must agree under rotation only.  A
    # reflection here would put every ball on the wrong land.
    reference = read_footprint_pads(NORMAL_FOOTPRINT)
    placed = {
        str(pad.GetNumber()): (mm(pad.GetPosition().x), mm(pad.GetPosition().y))
        for pad in interface.Pads()
    }
    assert len(placed) == 67, f"U1 has {len(placed)} pads, expected 67"
    assert_no_mirror(reference, placed, "carrier U1")

    library_interface = pcbnew.FootprintLoad(str(FOOTPRINT.parent), FOOTPRINT_NAME)
    assert library_interface is not None
    assert library_interface.GetValue() == "HOME_VFBGA67_INTERFACE"
    assert len(library_interface.Models()) == 0
    # The library footprint's local coordinates are the normal pattern rotated
    # 180 degrees, not mirrored; the physical mirror comes from placing it on
    # B.Cu.  Either way the composed result must not be a reflection.
    library_pads = {
        str(pad.GetNumber()): (mm(pad.GetFPRelativePosition().x),
                               mm(pad.GetFPRelativePosition().y))
        for pad in library_interface.Pads()
    }
    assert len(library_pads) == 67, f"library footprint has {len(library_pads)} pads"
    assert_no_mirror(reference, library_pads, "Mirrored_Interposer library footprint")

    # The current routed carrier uses a compact 8.41 x 7.60 mm outline.  The
    # drawing stroke expands the reported bounding box by 0.01 mm overall.
    edge_box = board.GetBoardEdgesBoundingBox()
    assert abs(mm(edge_box.GetWidth()) - 8.42) < 0.02, mm(edge_box.GetWidth())
    assert abs(mm(edge_box.GetHeight()) - 7.61) < 0.02, mm(edge_box.GetHeight())
    outline = pcbnew.SHAPE_POLY_SET()
    board.GetBoardPolygonOutlines(outline, True)
    assert outline.OutlineCount() == 1

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

    # Both halves of the face-to-face DF40 use identical electrical pin
    # numbers.  Mechanical mirroring belongs in the receptacle footprint, not
    # in a second, electrically permuted base-board net table.
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
            for pin, net in DF40.items()
        }
        assert actual == expected, f"{board_path}: DF40 violates same-number mating contract"

    base_board = pcbnew.LoadBoard(str(ROOT / "base" / "base.kicad_pcb"))
    base_connector = base_board.FindFootprintByReference("J1")
    base_edges = base_board.GetBoardEdgesBoundingBox()
    base_centre = pcbnew.VECTOR2I(
        (base_edges.GetLeft() + base_edges.GetRight()) // 2,
        (base_edges.GetTop() + base_edges.GetBottom()) // 2,
    )
    assert base_connector.GetPosition() == base_centre, "base J1 must be outline-centred"
    assert len(base_connector.Models()) == 1
    base_model = base_connector.Models()[0]
    assert str(base_model.m_Filename).endswith("DF40TC(4.0)-30DS-0.4V(51).stp")
    assert abs(base_model.m_Offset.x - (-2.86)) < 1e-6
    assert abs(base_model.m_Offset.y - (-1.69)) < 1e-6
    assert abs(base_model.m_Offset.z) < 1e-6

    socket = base_board.FindFootprintByReference("J2")
    assert socket.GetLayer() == pcbnew.F_Cu, "DIP48 socket strips must be top-side SMT"
    assert len(socket.Models()) == 1, "combined two-strip DIP48 STEP model is missing"
    assert str(socket.Models()[0].m_Filename).endswith("SSM-124-L-SV_DIP48.step")
    pads = {int(str(pad.GetNumber())): pad for pad in socket.Pads()}
    for pin, pad in pads.items():
        position = pad.GetFPRelativePosition()
        row_centre = 0.0 if pin <= 24 else 15.24
        row_index = pin - 1 if pin <= 24 else 48 - pin
        expected_x = row_centre + (-1.9275 if row_index % 2 == 0 else 1.9275)
        expected_y = row_index * 2.54
        assert abs(mm(position.x) - expected_x) < 1e-6, (pin, mm(position.x), expected_x)
        assert abs(mm(position.y) - expected_y) < 1e-6, (pin, mm(position.y), expected_y)
        assert abs(mm(pad.GetSizeX()) - 1.27) < 1e-6
        assert abs(mm(pad.GetSizeY()) - 1.02) < 1e-6

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
    print("interposer geometry OK: chipless and mirrored; connector escape offset <0.20 mm")
