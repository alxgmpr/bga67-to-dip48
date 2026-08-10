# Mezzanine connector pinout

**Single source of truth.** `carrier` and `base` are separate KiCad projects, so nothing
cross-checks them. Any change here must be applied to both boards in the same commit.

- Carrier (board A): `DF40GB-30DP-0.4V(51)` plug
- Base (board B): `DF40GB(1.5)-30DS-0.4V(51)` receptacle, HRS `CL0684-4198-4-51`

**Stack height is 1.5 mm and is not a free choice.** `DF40GB` is the *shielded* DF40
family. Per the DF40 catalog, the shielded stacking-height matrix offers 30 positions at
1.5 mm only, and `DF40GB(1.5)-30DS-0.4V(51)` is its sole 30-position mating receptacle
(30 signal + 4 ground). The unshielded families reach 2.0/2.5/3.0/3.5 mm at 30 positions,
and **no** DF40 reaches 4.0 mm at 30 positions — 4.0 mm exists only at 50, 60, 80 and 90.
Going above 1.5 mm therefore means re-specifying the carrier's plug, not just the
receptacle.

Receptacle land pattern (catalog p.12, "Recommended PCB Pattern" &lt;30 pos.&gt;):

```
signal  0.2 x 0.70  at y = +-1.54, x = -2.8 .. +2.8 step 0.4   (pitch 0.4, span 5.6)
ground  0.28 x 0.72 at x = +-3.24, y = +-1.68                   (span 6.48 ctr-to-ctr)
body    8.64 x 3.38, height 1.45
```

The receptacle footprint is **mirrored in X** relative to the plug — pin 1 sits at +X —
because the boards mate face to face. See "Mirror check" below.

Pins 1/2 are a facing pair at one end; odd pins are one row, even the other, 0.4 mm pitch.
Layout is a checkerboard: no signal is ever adjacent to or directly opposite another signal.
Separators are GND except at pins 6 and 10, where VCC does the job — acceptable because VCC
is an AC ground given the decoupling on board B. The two rows are offset by 0.4 mm, so odd-row
signals sit opposite even-row separators and vice versa.

| x pos | Odd row | Even row |
|------:|---------|----------|
|  1 | **1** IO4 | 2 GND |
|  2 | 3 GND | **4** IO7 |
|  3 | **5** IO3 | 6 VCC |
|  4 | 7 GND | **8** IO5 |
|  5 | **9** IO2 | 10 VCC |
|  6 | 11 GND | **12** IO8 |
|  7 | **13** IO1 | 14 GND |
|  8 | 15 GND | **16** IO6 |
|  9 | **17** CLE | 18 GND |
| 10 | 19 GND | **20** RY//BY |
| 11 | **21** /RE | 22 GND |
| 12 | 23 GND | **24** /WE |
| 13 | **25** ALE | 26 GND |
| 14 | 27 GND | **28** /CE |
| 15 | **29** /WP | 30 GND |

**This assignment is derived from the flash's ball geometry, not chosen by hand.** The
VFBGA67's used balls fall into two clusters: columns 2–4 (upper half) carry IO1–IO4 and
the four control lines CLE/RE/ALE/WP, and columns 5–7 (lower half) carry IO5–IO8, the
remaining control lines and both VCC balls. That is exactly 8 and 7 signals — and J1's odd
row has exactly 8 signal slots, its even row exactly 7. The split has zero slack, so the
row assignment is forced. Within a row, pins are ordered by ball x, which makes the escape
fan out monotonically and keeps the connector fanout crossing-free. VCC takes separator
pins 6 and 10, whose x lines up with the VCC balls H5 and G7.

Consequently **IO1–IO8 are not in pin order on the connector**, and that is deliberate. See
"Do not permute the data bus" below — the rule is about the end-to-end mapping, not the
connector pin order.

G1–G4 (retention tabs, both ends) → GND on both boards.

## Net names

Use these exact strings on both boards — the net classes key off them.

`IO1`–`IO8`, `/CE`, `/WE`, `/RE`, `/WP`, `CLE`, `ALE`, `RY//BY`, `VCC`, `GND`

The pinout table above uses `nCE`-style names for readability; the actual nets carry the
datasheet's slash form. KiCad escapes these as `{slash}CE` in the file format — that is
normal, not corruption.

### Net class patterns

Both projects carry these patterns in `.kicad_pro` already:

| pattern | net class |
|---|---|
| `/*` | Signal |
| `VCC` | Power |
| `GND` | Power |

**Why `/*` and not `IO*`.** The 15 signal nets come from *local* labels on the root
sheet, so KiCad prefixes them with the sheet path: they land on the board as `/IO1`,
`/{slash}CE`, `/RY{slash}{slash}BY` and so on. A pattern of `IO*` matches none of them and
every signal net silently falls through to Default. `VCC` and `GND` come from power
symbols and global labels, which are global and stay unprefixed, so they match bare.

Verified on the carrier: all 15 signal nets resolve to Signal (0.15 mm track), VCC and GND
to Power (0.4 mm).

## Do not permute the data bus

Commands and addresses travel over the same I/O pins as data. Swapping IO lines does not
merely byte-swizzle a dump — it corrupts the command byte and the device will not respond.

**The rule is about the end-to-end mapping**: flash ball IO*n* must reach TSOP48 socket
IO*n*. It says nothing about which J1 pin carries which net in between. Permuting the
connector assignment is safe — and is what the table above does — provided both boards use
the same table. `tools/pinout.py` holds the canonical table plus a checker that asserts the
checkerboard invariant and the full net set; both schematics were generated from it. Run
`python3 tools/pinout.py` after any edit.

What would break the device is editing one board's J1 assignment without the other.

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

Board B presents a **48-pin DIP socket** (female), 2.54 mm pitch, 0.6″ / 15.24 mm row
spacing, footprint `base:DIP-48_Socket_W15.24mm_P2.54mm`. The XGecu adapter carries the
male DIP48 pins and inserts into it from above. Both parts are viewed from the top, so the
socket is **not** mirrored — unlike the DF40 pair.

All 48 positions are drilled even though only 19 carry nets; populating the full socket is
cheaper mechanically than a partial one and gives the adapter even support.

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
