# Mezzanine connector contract

The NAND remains in the XGecu adapter. Board A is a permanent chipless interposer; board B
receives the removable adapter's DIP48 pins. The DF40 pair is normally left mated.

## Three roles, one interface

The DF40 30-position same-number contract is the invariant of the whole system. Three board
roles plug into it:

| Role | Board | Specific to |
|---|---|---|
| Target adapter | `carrier/` | the footprint being tapped |
| Device carrier | `chip/` | the NAND package |
| Host adapter | `base/`, `prog/` | the programmer or clamp adapter |

A new target, package, or programmer means one new board in one role, not a new system. The
electrical side is sized for this NAND specifically — 30 positions carrying 15 signals plus
power — so this is a documented pattern, not a general-purpose fixture.

- Carrier: `DF40TC-30DP-0.4V(51)` plug
- Base: `DF40TC(4.0)-30DS-0.4V(51)` receptacle
- Pitch: 0.4 mm; mated height: 4.0 mm

The plug footprint also has four non-electrical corner contacts, `MT1`-`MT4`. They are
0.35 x 0.66 mm retention lands at x = +/-3.275 mm and y = +/-1.355 mm. They are soldered
for mechanical strength but are not connector positions and carry no net. The verified STEP
model uses MT1 as its origin, so its KiCad transform is offset `(-3.275, -1.355, 0)`, with
unit scale and zero rotation.

## Routed, same-number DF40 mapping

This table preserves the completed carrier routing. The base uses the identical table:
plug `J1.n` mates to receptacle `J1.n`. Do not mirror this table again in the schematic or
PCB nets; the bottom-side receptacle footprint handles the face-to-face mechanical mirror.

| Pair | Odd pin | Even pin |
|---:|---|---|
| 1 | 1 /WP | 2 GND |
| 2 | 3 GND | 4 /WE |
| 3 | 5 ALE | 6 VCC |
| 4 | 7 GND | 8 /CE |
| 5 | 9 /RE | 10 VCC |
| 6 | 11 GND | 12 RY//BY |
| 7 | 13 CLE | 14 GND |
| 8 | 15 GND | 16 IO8 |
| 9 | 17 IO1 | 18 GND |
| 10 | 19 GND | 20 IO6 |
| 11 | 21 IO2 | 22 GND |
| 12 | 23 GND | 24 IO7 |
| 13 | 25 IO3 | 26 GND |
| 14 | 27 GND | 28 IO5 |
| 15 | 29 IO4 | 30 GND |

`tools/pinout.py` is the machine-readable source of truth. A pinout change is atomic: update
carrier PCB/schematic, base PCB/schematic, this table, and the checker together.

The boards mate face-to-face, so the base receptacle footprint mirrors the plug geometry.
Pin 1 must meet pin 1; a net-table mirror would double-mirror the interface and is forbidden.

## DIP48 receptacle geometry

`J2` is two top-side Samtec `SSM-124-L-SV` 1×24 friction socket strips, not a ZIF
mechanism. The mating centrelines are 15.24 mm apart. Each strip uses 2.54 mm pitch and the
manufacturer's staggered -SV pads: 1.27 × 1.02 mm at ±1.9275 mm from its mating centreline.
The combined STEP model places both 60.96 × 2.54 × 7.49 mm housings at this exact spacing.

## NAND mapping

| Signal | VFBGA67 ball | TSOP48/DIP pin |
|---|---:|---:|
| IO1 | G3 | 29 |
| IO2 | H3 | 30 |
| IO3 | J3 | 31 |
| IO4 | J4 | 32 |
| IO5 | J5 | 41 |
| IO6 | H6 | 42 |
| IO7 | J6 | 43 |
| IO8 | H7 | 44 |
| RY//BY | B7 | 7 |
| /RE | C3 | 8 |
| /CE | B5 | 9 |
| CLE | C4 | 16 |
| ALE | B3 | 17 |
| /WE | B6 | 18 |
| /WP | B2 | 19 |
| VCC | G7, H5 | 12, 37 |
| GND | B4, J2, J7 | 13, 36 |

IO1–IO8 must remain end-to-end identical. NAND commands and addresses use this same bus, so
a data-line permutation is not a harmless byte shuffle. The other 47 VFBGA67 lands are NC
and must float.

The VFBGA map was checked against the Kioxia device documentation and Courk's NandBug rev-3
hardware: https://github.com/courk/Nandbug-Hardware

## Manufacturing topology

The carrier escape is deliberately conventional: 0.15 mm tracks and 0.45/0.20 mm ordinary
through-via dogbones. No BGA pad contains a via. There are no microvias, blind/buried vias,
VIPPO, filled/capped vias, or other HDI requirements.
