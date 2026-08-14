#!/usr/bin/env python3
"""Route boards/emmc_bga153/carrier: B.Cu escapes, inner-layer fan-out, pours.

Run with KiCad's bundled Python (see Makefile's KICAD_PY).  Idempotent: it
deletes every track, via and zone it finds before laying its own down, so it
can be re-run after an edit to the plan below.

Why the plan looks the way it does
----------------------------------
U1 is a 153-ball 0.5 mm-pitch field of 0.25 mm lands on B.Cu; J1 is the DF40
plug on F.Cu, its two 0.4 mm-pitch pad rows crossing the field at
y = 98.645 / 101.355.  Three numbers decide every routing choice:

  gate       two orthogonally adjacent lands leave 0.25 mm of clear copper.
             A trace centred in it needs land/2 + w/2 + clearance
             = 0.125 + 0.045 + 0.09 = 0.260 mm of half-gate but only has
             0.250 mm.  *Nothing* legal passes between two adjacent lands,
             so a ball can only escape to a vacant ball site next to it.
  saddle     the interstitial diagonal is 0.354 mm from four lands.  A 0.12 mm
             trace clears it (0.354 - 0.125 - 0.06 = 0.169 mm), so diagonal
             single steps are fine; a via is not (0.20 mm drill needs
             0.10 + 0.20 + 0.125 = 0.425 mm).
  via site   a 0.45/0.20 via needs 0.450 mm to a different-net land centre
             (copper) and 0.425 mm (hole), so vacant ball sites (0.500 mm)
             work and nothing else inside the field does.  It also needs
             0.325 mm to a DF40 land centre (check_interposer) plus 0.325 mm
             to its copper, which bans vias from the two ball rows either
             side of each DF40 row.

That leaves four via regions: the strips outside the field, the moat (the
vacant ring at column 4 / column 11 / row D / row L, usable only where it
clears the DF40 rows), and the vacant 4x4 block enclosed by the inner ball
ring.  Balls in row B and ball N2 touch none of them and are left unrouted;
see the task report.
"""
import sys
from pathlib import Path

import pcbnew

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dogbones

MM = pcbnew.FromMM
BOARD = (Path(__file__).resolve().parents[1]
         / "boards" / "emmc_bga153" / "carrier" / "carrier.kicad_pcb")

VIA = dogbones.ViaSpec(land_mm=0.45, drill_mm=0.20, stub_width_mm=0.12)
FIELD_W = 0.12          # B.Cu escapes threading the land field
RUN_W = 0.15            # F.Cu / In1 runs in open copper
F, IN1, IN2, B = pcbnew.F_Cu, pcbnew.In1_Cu, pcbnew.In2_Cu, pcbnew.B_Cu

# ---------------------------------------------------------------- via sites
# name -> (x, y, net)
VIAS = [
    # top strip, above row A.  Row A's three signals reach pins 17/21/25,
    # whose x order reverses theirs, so the crossing is resolved here (B.Cu
    # over In1) and each F.Cu descent runs straight to its pin.
    ("D0",      99.60,  94.80, "/DAT0"),
    ("D1a",     98.25,  96.25, "/DAT1"),
    ("D1b",     99.15,  95.90, "/DAT1"),
    ("D2",      98.00,  95.50, "/DAT2"),
    # inner block, enclosed by the inner ball ring
    ("VCC_NW",  99.35,  99.35, "VCC"),
    ("RST",     99.50, 100.65, "/RST_n"),
    ("VCC_SE", 100.65, 100.65, "VCC"),
    ("GND_BLK",100.65,  99.35, "GND"),
    # moat: column 11 top (VCCQ from C6), column 11 bottom (CLK from M6),
    # column 4 bottom (CMD from M5)
    ("VCCQ_T", 101.75,  99.35, "VCCQ"),
    ("CLK_E",  101.75, 100.65, "/CLK"),
    ("DS_W",    98.25, 100.00, "/DS"),
    ("CMD_W",   98.25, 100.60, "/CMD"),
    # bottom strip, below row P: the south fan-in, ordered west to east to
    # match its pins (12, 10, 8, 6) so the F.Cu approaches nest
    ("CLK_S",   96.60, 104.00, "/CLK"),
    ("VCCQ_A",  97.75, 103.75, "VCCQ"),
    ("VCCQ_B",  98.75, 103.75, "VCCQ"),
    ("CMD_S",   99.90, 104.30, "/CMD"),
    ("VCC_S",  100.90, 104.30, "VCC"),
    # GND stitching, all in the strips outside the field
    ("ST1",     94.60,  93.60, "GND"),
    ("ST2",    105.40,  93.60, "GND"),
    ("ST3",     94.60, 106.40, "GND"),
    ("ST4",    105.40, 106.40, "GND"),
    ("ST5",     94.60, 100.00, "GND"),
    ("ST6",    105.40, 100.00, "GND"),
    ("ST7",     95.40,  97.00, "GND"),
    ("ST8",    104.60,  97.00, "GND"),
    ("ST9",     95.40, 103.00, "GND"),
    ("ST10",   104.60, 103.00, "GND"),
]

# ------------------------------------------------------------------ routing
# (net, layer, width, [(x, y), ...]); "U1:<ball>" and "J1:<pin>" resolve to
# that pad's centre so the plan reads like the escape it describes.
ROUTES = [
    # --- row A signals: straight out of the field, then down F.Cu to the pins
    ("/DAT0", B, FIELD_W, ["U1:A3", (97.40, 96.40), (97.40, 94.80), (99.60, 94.80)]),
    ("/DAT0", F, RUN_W,   [(99.60, 94.80), (100.05, 95.60), (100.05, 97.60),
                           (99.60, 98.10), "J1:17"]),
    ("/DAT1", B, FIELD_W, ["U1:A4", (98.25, 96.25)]),
    ("/DAT1", IN1, RUN_W, [(98.25, 96.25), (99.15, 95.90)]),
    ("/DAT1", F, RUN_W,   [(99.15, 95.90), "J1:21"]),
    ("/DAT2", B, FIELD_W, ["U1:A5", (98.75, 95.50), (98.00, 95.50)]),
    ("/DAT2", F, RUN_W,   [(98.00, 95.50), (97.75, 96.00), (97.75, 97.60),
                           (98.00, 98.20), "J1:25"]),

    # --- row C: C4 chains to the GND ball E7, C6 crosses the moat to column 11
    ("GND",  B, FIELD_W, ["U1:C4", (98.75, 98.25), (99.75, 98.42), "U1:E7"]),
    ("VCCQ", B, FIELD_W, ["U1:C6", (99.25, 98.06), (101.75, 98.06), (101.75, 99.35)]),

    # --- inner ring balls escape into the vacant block
    ("VCC",   B, FIELD_W, ["U1:E6", (99.35, 99.35)]),
    ("VCC",   B, FIELD_W, ["U1:F5", (99.35, 99.35)]),
    ("/DS",   B, FIELD_W, ["U1:H5", (98.25, 100.00)]),
    ("/RST_n",B, FIELD_W, ["U1:K5", (99.50, 100.65)]),
    ("VCC",   B, FIELD_W, ["U1:J10", (100.65, 100.65)]),
    ("VCC",   B, FIELD_W, ["U1:K9", (100.65, 100.65)]),

    # --- row M signals cross the moat's row L lane to a column lane
    ("/CMD", B, FIELD_W, ["U1:M5", (98.75, 101.75), (98.25, 101.75), (98.25, 100.60)]),
    ("/CLK", B, FIELD_W, ["U1:M6", (99.25, 101.75), (101.75, 101.75), (101.75, 100.65)]),

    # --- row M/N/P power: M4 and N4 chain diagonally to P3 on the outer ring
    ("VCCQ", B, FIELD_W, ["U1:M4", "U1:N4", "U1:P3"]),
    ("VCCQ", B, FIELD_W, ["U1:P3", (97.75, 103.75)]),
    ("VCCQ", B, FIELD_W, ["U1:P5", (98.75, 103.75)]),
    ("GND",  B, FIELD_W, ["U1:N5", "U1:P4"]),

    # --- In1: the two nets whose escape via and south fan-in via keep their
    # west-to-east order, plus the VCC pair's own join
    ("VCC",  IN1, RUN_W, [(99.35, 99.35), (99.35, 100.20), (100.65, 100.20),
                          (100.65, 100.65)]),
    ("/CMD", IN1, RUN_W, [(98.25, 100.60), (98.40, 102.50), (99.90, 104.00),
                          (99.90, 104.30)]),
    ("VCC",  IN1, RUN_W, [(100.65, 100.65), (100.90, 102.50), (100.90, 104.30)]),
    ("VCCQ", IN1, RUN_W, [(97.75, 103.75), (98.75, 103.75)]),

    # --- In2: the two nets that have to cross the others, around the outside
    # of the GND plane's board area (the plane fills around them)
    ("/CLK", IN2, RUN_W, [(101.75, 100.65), (102.90, 101.50), (102.90, 105.50),
                          (96.60, 105.50), (96.60, 104.00)]),
    ("VCCQ", IN2, RUN_W, [(101.75, 99.35), (101.00, 98.40), (97.00, 98.40),
                          (96.20, 99.20), (96.20, 102.80), (97.75, 103.75)]),

    # --- F.Cu inside the DF40 corridor (usable band y 99.15 .. 100.85)
    ("/DS",   F, RUN_W, [(98.25, 100.00), (99.00, 99.80), (101.20, 99.80),
                         "J1:9"]),
    ("/RST_n",F, RUN_W, [(99.50, 100.65), (99.50, 100.20), (102.40, 100.20),
                         "J1:4"]),

    # --- F.Cu south fan-in: four nested staircases up to the even pin row
    ("/CLK",  F, RUN_W, [(96.60, 104.00), (96.60, 102.40), (100.80, 102.40),
                         "J1:12"]),
    ("VCCQ",  F, RUN_W, [(98.75, 103.75), (98.75, 102.80), (101.20, 102.80),
                         "J1:10"]),
    ("/CMD",  F, RUN_W, [(99.90, 104.30), (99.90, 103.20), (101.60, 103.20),
                         "J1:8"]),
    ("VCC",   F, RUN_W, [(100.90, 104.30), (100.90, 103.60), (102.00, 103.60),
                         "J1:6"]),
]

ZONES = [("GND", B), ("GND", F), ("GND", IN2)]


def pad_positions(board):
    """{"U1:A3": (x, y)} for every pad, read before anything is removed."""
    positions = {}
    for footprint in board.GetFootprints():
        reference = footprint.GetReference()
        for pad in footprint.Pads():
            position = pad.GetPosition()
            positions["%s:%s" % (reference, pad.GetNumber())] = (
                pcbnew.ToMM(position.x), pcbnew.ToMM(position.y))
    return positions


def resolve(positions, point):
    return positions[point] if isinstance(point, str) else point


def add_track(board, net, layer, width, start, end):
    track = pcbnew.PCB_TRACK(board)
    track.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
    track.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
    track.SetLayer(layer)
    track.SetWidth(MM(width))
    track.SetNet(net)
    board.Add(track)


def add_zone(board, net, layer, outline):
    zone = pcbnew.ZONE(board)
    zone.SetLayer(layer)
    zone.SetNet(net)
    zone.SetIsFilled(True)
    zone.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    zone.SetLocalClearance(MM(0.10))
    zone.SetMinThickness(MM(0.25))
    zone.SetAssignedPriority(0)
    zone.Outline().NewOutline()
    for x, y in outline:
        zone.Outline().Append(MM(x), MM(y))
    board.Add(zone)
    return zone


def main():
    board = pcbnew.LoadBoard(str(BOARD))

    # Order matters and is not cosmetic (see build_chip.collect_removals):
    # board.Remove() poisons the SWIG type registry for the whole process, so
    # every read -- nets, pads, board extents -- happens first, then the
    # removals, then the additions.
    by_name = board.GetNetsByName()
    nets = {name: by_name[name]
            for name in {via[3] for via in VIAS}
            | {route[0] for route in ROUTES} | {net for net, _ in ZONES}}
    field = dogbones.Field(board, "U1", "J1")
    positions = pad_positions(board)
    box = board.GetBoardEdgesBoundingBox()
    inset = MM(0.30)
    outline = [
        (pcbnew.ToMM(box.GetLeft() + inset), pcbnew.ToMM(box.GetTop() + inset)),
        (pcbnew.ToMM(box.GetRight() - inset), pcbnew.ToMM(box.GetTop() + inset)),
        (pcbnew.ToMM(box.GetRight() - inset), pcbnew.ToMM(box.GetBottom() - inset)),
        (pcbnew.ToMM(box.GetLeft() + inset), pcbnew.ToMM(box.GetBottom() - inset)),
    ]
    doomed = list(board.GetTracks()) + list(board.Zones())
    for item in doomed:
        board.Remove(item)

    complaints = []
    placed = []
    for name, x, y, net in VIAS:
        reasons = field.reasons_site_illegal((x, y), VIA, nets[net].GetNetCode(),
                                             placed)
        for reason in reasons:
            complaints.append("via %s at (%.3f, %.3f): %s" % (name, x, y, reason))
        placed.append((x, y, VIA, nets[net].GetNetCode()))
        board.Add(dogbones.make_via(board, (x, y), VIA, nets[net]))

    for net, layer, width, points in ROUTES:
        resolved = [resolve(positions, point) for point in points]
        net_code = nets[net].GetNetCode()
        for start, end in zip(resolved, resolved[1:]):
            if layer == B:
                for reason in field.reasons_stub_illegal(start, end, VIA, net_code):
                    complaints.append("%s %s-%s: %s" % (net, start, end, reason))
            add_track(board, nets[net], layer, width, start, end)

    zones = [add_zone(board, nets[net], layer, outline) for net, layer in ZONES]
    pcbnew.ZONE_FILLER(board).Fill(zones)

    pcbnew.SaveBoard(str(BOARD), board)
    if complaints:
        print("%d geometry complaint(s):" % len(complaints))
        for complaint in complaints[:40]:
            print("   ", complaint)
    else:
        print("geometry checks clean")
    print("wrote", BOARD)


if __name__ == "__main__":
    main()
