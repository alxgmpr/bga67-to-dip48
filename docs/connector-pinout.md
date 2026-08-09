# Mezzanine connector pinout

**Single source of truth.** `carrier` and `base` are separate KiCad projects, so nothing
cross-checks them. Any change here must be applied to both boards in the same commit.

- Carrier (board A): `DF40GB-30DP-0.4V(51)` plug
- Base (board B): `DF40C(x.x)-30DS-0.4V(51)` receptacle — stack height still to be chosen

Pins 1/2 are a facing pair at one end; odd pins are one row, even the other, 0.4 mm pitch.
Layout is a checkerboard: every signal has GND directly opposite and GND on both in-row sides.

| x pos | Odd row | Even row |
|------:|---------|----------|
|  1 | **1** IO1 | 2 GND |
|  2 | 3 GND | **4** nCE |
|  3 | **5** IO2 | 6 GND |
|  4 | 7 GND | **8** CLE |
|  5 | **9** IO3 | 10 GND |
|  6 | 11 GND | **12** ALE |
|  7 | **13** IO4 | 14 GND |
|  8 | 15 VCC | **16** nWE |
|  9 | **17** IO5 | 18 GND |
| 10 | 19 VCC | **20** nRE |
| 11 | **21** IO6 | 22 GND |
| 12 | 23 GND | **24** nWP |
| 13 | **25** IO7 | 26 GND |
| 14 | 27 GND | **28** RY_nBY |
| 15 | **29** IO8 | 30 GND |

G1–G4 (retention tabs, both ends) → GND on both boards.

## Net names

Use these exact strings on both boards — the net classes key off them.

`IO1`–`IO8`, `/CE`, `/WE`, `/RE`, `/WP`, `CLE`, `ALE`, `RY//BY`, `VCC`, `GND`

The pinout table above uses `nCE`-style names for readability; the actual nets carry the
datasheet's slash form. KiCad escapes these as `{slash}CE` in the file format — that is
normal, not corruption.

### Net class patterns

Net classes `Power` and `Signal` are defined in both projects, but the patterns that bind
nets to them must be entered in Board Setup → Net Classes → Patterns (the MCP tooling
cannot write them). Add:

| pattern | net class |
|---|---|
| `IO*` | Signal |
| `/CE` `/WE` `/RE` `/WP` | Signal |
| `CLE` `ALE` `RY//BY` | Signal |
| `VCC` `GND` | Power |

## Do not permute the data bus

Commands and addresses travel over the same I/O pins as data. Swapping IO lines does not
merely byte-swizzle a dump — it corrupts the command byte and the device will not respond.
IO1→IO8 stay in order end to end.

## Mirror check

The boards mate face to face, so the X axis flips. On `base`, viewed from the top, the
receptacle's pin 1 must sit at the end that lands under the plug's pin 1 after the flip —
the opposite end from where intuition puts it. Verify a mated pair in the 3D viewer before
ordering.

## Flash ball map (TC58NVG1S3HBAI6, VFBGA-67)

| Signal | Ball | | Signal | Ball |
|---|---|---|---|---|
| IO1 | G3 | | nCE | B5 |
| IO2 | H3 | | nWE | B6 |
| IO3 | J3 | | nRE | C3 |
| IO4 | J4 | | CLE | C4 |
| IO5 | J5 | | ALE | B3 |
| IO6 | H6 | | nWP | B2 |
| IO7 | J6 | | RY_nBY | B7 |
| IO8 | H7 | | VCC | G7, H5 |
|     |    | | VSS | B4, J2, J7 |

The other 47 balls are NC. **Leave them floating — do not tie them to ground.**

## DIP48 side (base board)

Standard JEDEC TSOP48 x8 NAND. Note the numbering offset: the Kioxia datasheet's I/O1 is
the socket's I/O0.

| Signal | TSOP48 pin |
|---|---|
| IO1–IO4 (I/O0–3) | 29, 30, 31, 32 |
| IO5–IO8 (I/O4–7) | 41, 42, 43, 44 |
| RY_nBY | 7 |
| nRE | 8 |
| nCE | 9 |
| CLE | 16 |
| ALE | 17 |
| nWE | 18 |
| nWP | 19 |
| VCC | 12, 37 |
| VSS | 13, 36 |

**Unverified.** This comes from the JEDEC standard, not from the Kioxia datasheet, which
documents only the BGA. Ring it out against the actual XGecu adapter before committing the
base board layout.

Only ~21 of the 48 positions need pins populated (the 17 nets plus corner pins for
retention), but the board must still span pin 1 to pin 24: 23 × 2.54 = 58.42 mm.
