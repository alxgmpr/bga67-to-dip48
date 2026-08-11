# Mezzanine connector contract

The NAND remains in the XGecu adapter. Board A is a permanent chipless interposer; board B
receives the removable adapter's DIP48 pins. The DF40 pair is normally left mated.

- Carrier: `DF40TC-30DP-0.4V(51)` plug
- Base: `DF40TC(4.0)-30DS-0.4V(51)` receptacle
- Pitch: 0.4 mm; mated height: 4.0 mm

The plug footprint also has four non-electrical corner contacts, `MT1`-`MT4`. They are
0.35 x 0.66 mm retention lands at x = +/-3.275 mm and y = +/-1.355 mm. They are soldered
for mechanical strength but are not connector positions and carry no net. The verified STEP
model uses MT1 as its origin, so its KiCad transform is offset `(-3.275, -1.355, 0)`, with
unit scale and zero rotation.

## Courk-ordered DF40 mapping

Pins 7–26 reproduce Courk's ten NandBug DF17 pin pairs in the same order. The five surplus
DF40 pair-columns are ground returns. This replaces the former checkerboard assignment and
is the mapping that both PCBs must use.

| Pair | Odd pin | Even pin |
|---:|---|---|
| 1 | 1 GND | 2 GND |
| 2 | 3 GND | 4 GND |
| 3 | 5 GND | 6 GND |
| 4 | 7 RY//BY | 8 ALE |
| 5 | 9 /WE | 10 /WP |
| 6 | 11 /CE | 12 /RE |
| 7 | 13 CLE | 14 VCC |
| 8 | 15 GND | 16 GND |
| 9 | 17 GND | 18 IO5 |
| 10 | 19 GND | 20 IO2 |
| 11 | 21 IO6 | 22 IO1 |
| 12 | 23 IO8 | 24 IO3 |
| 13 | 25 IO7 | 26 IO4 |
| 14 | 27 GND | 28 GND |
| 15 | 29 GND | 30 GND |

`tools/pinout.py` is the machine-readable source of truth. A pinout change is atomic: update
carrier PCB/schematic, base PCB/schematic, this table, and the checker together.

The boards mate face-to-face, so the base receptacle footprint mirrors the plug's X axis.
Pin 1 must meet pin 1 in the mated 3D/mechanical check.

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
