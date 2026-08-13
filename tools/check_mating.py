#!/usr/bin/env python3
"""Verify the schematic-level carrier -> DF40 -> base -> DIP48 contract."""

from pathlib import Path
import os
import subprocess
import tempfile
import xml.etree.ElementTree as ET

from pinout import DF40
from ringout import TSOP48


ROOT = Path(__file__).resolve().parents[1]
KICAD_CLI = Path(
    os.environ.get(
        "KICAD_CLI",
        "/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli",
    )
)

BGA67 = {
    "B7": "RY//BY", "C3": "/RE", "B5": "/CE", "C4": "CLE",
    "B3": "ALE", "B6": "/WE", "B2": "/WP",
    "G3": "IO1", "H3": "IO2", "J3": "IO3", "J4": "IO4",
    "J5": "IO5", "H6": "IO6", "J6": "IO7", "H7": "IO8",
    "G7": "VCC", "H5": "VCC", "B4": "GND", "J2": "GND", "J7": "GND",
}


def logical_name(net_name):
    if net_name.startswith("/"):
        return net_name[1:]
    return net_name


def schematic_pin_map(project, reference):
    schematic = ROOT / project / f"{project}.kicad_sch"
    with tempfile.NamedTemporaryFile(suffix=".xml") as output:
        subprocess.run(
            [str(KICAD_CLI), "sch", "export", "netlist", "--format", "kicadxml",
             "-o", output.name, str(schematic)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        root = ET.parse(output.name).getroot()
    result = {}
    for net in root.find("nets"):
        net_name = logical_name(net.attrib["name"])
        for node in net:
            if node.attrib.get("ref") == reference:
                pin = node.attrib["pin"]
                if reference != "J1" or pin.isdigit():
                    result[pin] = net_name
    return result


def check():
    expected_df40 = {str(pin): net for pin, net in DF40.items()}
    carrier_j1 = schematic_pin_map("carrier", "J1")
    base_j1 = schematic_pin_map("base", "J1")
    assert carrier_j1 == expected_df40, ("carrier J1", carrier_j1)
    assert base_j1 == expected_df40, ("base J1", base_j1)
    assert carrier_j1 == base_j1, "plug and receptacle must be same-number mapped"

    # Board C carries the real NAND.  Its ball -> net map must be identical to
    # carrier A's, and its J1 must be the same canonical table, which together
    # mean the chip on board C sees exactly what the target motherboard would
    # have driven it with.
    chip_j1 = schematic_pin_map("chip", "J1")
    chip_u1 = schematic_pin_map("chip", "U1")
    assert chip_j1 == expected_df40, ("chip J1", chip_j1)
    carrier_u1_map = schematic_pin_map("carrier", "U1")
    assert chip_u1 == carrier_u1_map, (
        "chip U1 and carrier U1 disagree on ball -> net; the chip would be "
        "driven differently than the motherboard drives it"
    )

    carrier_u1 = schematic_pin_map("carrier", "U1")
    for ball, net in BGA67.items():
        assert carrier_u1[ball] == net, (ball, carrier_u1[ball], net)

    base_j2 = schematic_pin_map("base", "J2")
    for pin, net in TSOP48.items():
        assert base_j2[str(pin)] == net, (pin, base_j2[str(pin)], net)

    # Every active NAND signal must appear exactly once at the DF40 joint.
    active = set(BGA67.values()) - {"GND", "VCC"}
    for net in active:
        pins = [pin for pin, pin_net in expected_df40.items() if pin_net == net]
        assert len(pins) == 1, (net, pins)
        assert net in base_j2.values(), f"{net} does not reach the DIP48 socket"
    return True


if __name__ == "__main__":
    check()
    print("mating netlist OK: BGA67 -> J1 same-number pair -> DIP48")
