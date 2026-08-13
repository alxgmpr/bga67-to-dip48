#!/usr/bin/env python3
"""Prepare board B for a reroute using the canonical same-number DF40 table."""

from pathlib import Path

import pcbnew

from pinout import DF40


ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "base" / "base.kicad_pcb"


def board_net_name(logical_name):
    if logical_name in ("GND", "VCC"):
        return logical_name
    return "/" + logical_name.replace("/", "{slash}")


def main():
    board = pcbnew.LoadBoard(str(BOARD))
    connector = next(fp for fp in board.GetFootprints() if fp.GetReference() == "J1")
    edges = board.GetBoardEdgesBoundingBox()
    connector.SetPosition(
        pcbnew.VECTOR2I(
            (edges.GetLeft() + edges.GetRight()) // 2,
            (edges.GetTop() + edges.GetBottom()) // 2,
        )
    )
    nets = board.GetNetsByName()
    for pad in connector.Pads():
        pad.SetNet(nets[board_net_name(DF40[int(str(pad.GetNumber()))])])

    for item in list(board.GetTracks()):
        board.Remove(item)
    for zone in list(board.Zones()):
        board.Remove(zone)

    pcbnew.SaveBoard(str(BOARD), board)
    print("base prepared: centred canonical DF40, all routing removed")


if __name__ == "__main__":
    main()
