#!/usr/bin/env python3
"""Generate the combined two-strip DIP48 receptacle STEP model.

The envelope and land geometry come from Samtec drawing
SSM-1XX-XXX-XX-XX-XX-XX-X-XX, revision DG, for the -SV single-row
surface-mount tail.  The contact internals are deliberately simplified; the
mating centres, body envelope, height, pitch, and solder-tail locations are
dimensionally controlled.
"""

from pathlib import Path

import cadquery as cq


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "base" / "lib" / "3d" / "SSM-124-L-SV_DIP48.step"

PITCH = 2.54
POSITIONS = 24
ROW_SPACING = 15.24
BODY_WIDTH = 2.54
BODY_LENGTH = POSITIONS * PITCH
BODY_HEIGHT = 7.49
PAD_OFFSET = 1.9275
PAD_WIDTH = 1.27
PAD_LENGTH = 1.02


def translated_box(x, y, z, dx, dy, dz):
    return cq.Workplane("XY").box(dx, dy, dz).translate((x, y, z))


def socket_strip(x_offset):
    # KiCad's footprint-to-STEP transform reverses model Y relative to the
    # footprint-local Y used by the pad definitions.  Build toward negative Y
    # so positions 1..24 render over pads 1..24, not off the board edge.
    body = translated_box(
        x_offset,
        -(POSITIONS - 1) * PITCH / 2,
        BODY_HEIGHT / 2,
        BODY_WIDTH,
        BODY_LENGTH,
        BODY_HEIGHT,
    )

    # Square entry funnels identify every mating centre.  The commercial part
    # has shaped Tiger Claw contacts; an open cavity plus visible contact disk
    # is a robust, lightweight mechanical representation for KiCad.
    for index in range(POSITIONS):
        y = -index * PITCH
        cavity = translated_box(x_offset, y, BODY_HEIGHT - 1.0, 1.25, 1.25, 2.2)
        body = body.cut(cavity)

    metal = None
    for index in range(POSITIONS):
        y = -index * PITCH
        side = -1 if index % 2 == 0 else 1
        tail_x = x_offset + side * PAD_OFFSET
        tail = translated_box(tail_x, y, 0.06, PAD_WIDTH, PAD_LENGTH, 0.12)
        neck_centre = (x_offset + tail_x) / 2
        neck = translated_box(
            neck_centre,
            y,
            0.18,
            abs(tail_x - x_offset) + 0.25,
            0.34,
            0.36,
        )
        contact = (
            cq.Workplane("XY")
            .center(x_offset, y)
            .circle(0.36)
            .extrude(0.45)
            .translate((0, 0, BODY_HEIGHT - 2.15))
        )
        piece = tail.union(neck).union(contact)
        metal = piece if metal is None else metal.union(piece)
    return body, metal


def main():
    assembly = cq.Assembly(name="SSM-124-L-SV_DIP48")
    for index, x_offset in enumerate((0.0, ROW_SPACING), start=1):
        body, metal = socket_strip(x_offset)
        assembly.add(body, name=f"housing_{index}", color=cq.Color(0.04, 0.04, 0.04))
        assembly.add(metal, name=f"contacts_{index}", color=cq.Color(0.83, 0.63, 0.18))

    # Pin-1 marker, outside the mating cavity.
    marker = (
        cq.Workplane("XY")
        .center(-0.88, -0.88)
        .circle(0.20)
        .extrude(0.08)
        .translate((0, 0, BODY_HEIGHT))
    )
    assembly.add(marker, name="pin_1_marker", color=cq.Color(0.85, 0.85, 0.85))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    assembly.save(str(OUTPUT), mode="default")
    print(OUTPUT)


if __name__ == "__main__":
    main()
