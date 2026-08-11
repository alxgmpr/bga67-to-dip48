# Mezzanine connector pinout

**Single source of truth.** `carrier` and `base` are separate KiCad projects, so nothing
cross-checks them. Any change here must be applied to both boards in the same commit.

- Carrier (board A): `DF40TC-30DP-0.4V(51)` plug, HRS `CL0684-4263-0-51`
- Base (board B): `DF40TC(4.0)-30DS-0.4V(51)` receptacle, HRS `CL0684-4256-0-51`

**Stack height is 4.0 mm.** Getting there meant leaving the shielded `DF40GB` family,
which offers 30 positions at 1.5 mm only. Plain `DF40C`/`DF40HC` stop at 3.5 mm at 30
positions. **`DF40T` (125 °C, automotive) does 30 positions at 4.0 mm and it is mass
production** — see the DF40T/DF40GT catalog (Jan 2026) p.2 variation matrix and the p.8
combinations table. 4.5–7.0 mm at 30 positions is still Under Planning, so 4.0 mm is the
ceiling for this pin count in any DF40 family.

**The plug carries no stacking height in its part number.** One `DF40TC-30DP-0.4V(51)`
serves every height from 1.5 to 4.0 mm; the receptacle sets the gap. If the stack height
ever changes again, only board B's part number moves.

What the DF40T family costs, relative to the DF40GB pair it replaced:

| | DF40GB (was) | DF40TC (now) |
|---|---|---|
| Stack height, 30 pos | 1.5 mm only | 1.5 / 2.0 / 2.5 / 3.0 / 3.5 / **4.0** mm |
| Rated current | 0.5 A | 0.3 A (flash draws 30 mA) |
| Mating durability | 30 cycles | **10 cycles** |
| Shield | yes | no |
| Retention tabs | G1–G4 | **none** |

The 10-cycle rating sharpens a rule that was already in this document: the repeatedly
separated joint is the DIP48/ZIF end, not the mezzanine.

Receptacle land pattern (catalog p.12, "Recommended PCB Pattern" &lt;30 pos.&gt;):

```
signal  0.2 x 0.70  at y = +-1.54, x = -2.8 .. +2.8 step 0.4   (pitch 0.4, span 5.6)
body    8.6 x 3.38, 3.90 above board
```

There are no ground/retention pads: `TC` means no retention tab. The signal geometry is
byte-for-byte what the DF40GB pair used — DF40 catalog p.10 gives the No-Retention-Tab
receptacle pattern as rows 3.78 outer / 2.38 inner (so 0.70 long at y = ±1.54) and
0.2 wide, and DF40T catalog p.9 gives the plug as rows 3.37/2.05 (0.66 long at
y = ±1.355) and 0.23 wide, both at P=0.4 and B=5.60. **Every one of the 30 signal pads is
unmoved on both boards**; only G1–G4 disappeared. That is why raising the stack height
cost no re-routing.

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

G1–G4 are gone. `DF40TC` has no retention tabs, so both footprints drop those four pads
and the schematics no longer tie them to GND. J1's ground return is unaffected: the
checkerboard already puts 13 GND pins in the signal field.

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

### Cross-checked against an independent source

The table above was read off the Kioxia datasheet (p.2). It has since been confirmed
pin-for-pin against courk's **NandBug** hardware, which targets the same part in the same
Google Home Mini:

- `interposer_board/schematics.pdf` rev 3.0, 07/05/2020
- `daughter_board/schematics.pdf` rev 1.0, 23/05/2020
- https://github.com/courk/Nandbug-Hardware

All 20 used balls agree — IO1–IO8, the seven control lines, both VCC and all three VSS.
Two independent sources on the one table that cannot be caught by ERC, DRC or a netlist
diff, because both boards would be consistently wrong together.

Nothing else from NandBug applies here. Its mezzanine is a 20-pin DF17 0.5 mm carrying
15 signals, 2 VCC and only 3 GND, all bunched at pins 9/11/13 — no checkerboard, and seven
IO lines in a row with no adjacent return. Its interposer also uses a **mirrored** BGA
footprint, because it solders into the Home Mini in place of the flash rather than
carrying a chip. The repo ships Gerbers and a schematic PDF only, no CAD source.

## DIP48 side (base board)

Board B presents a **48-position DIP socket field built from two 1×24 surface-mount
socket strips** (Samtec `SSM-124-L-SV` class), 2.54 mm pitch, 0.6″ / 15.24 mm row spacing,
footprint `base:DIP-48_SocketStrip_SMD_W15.24mm_P2.54mm`. The XGecu adapter carries the
male DIP48 pins and inserts into it from above. Both parts are viewed from the top, so the
socket is **not** mirrored — unlike the DF40 pair.

**It is surface mount, so nothing protrudes below the board** and the carrier mezzanine
underneath is unobstructed. No one-piece SMT DIP48 at 0.6″ exists in distribution, which
is why it is two strips rather than one part.

The tails **stagger ±1.65 mm** either side of each row centreline, alternating, which is
how SMT socket strips fit a 2.54 mm pitch. Consequences worth knowing:

- All 48 pad **Y coordinates are unchanged** from the through-hole footprint, and the row
  centrelines still sit 15.24 mm apart — that is what the adapter's pins seat on.
- The inner pad edges leave a **10.04 mm channel** between the rows. The carrier is
  7.45 mm wide, so it still clears, with ~1.3 mm either side.
- SMD pads live on **F.Cu only**. Every net on this board arrives from B.Cu or an inner
  layer, so each used pad gets a 0.15 mm F.Cu stub back to its row centreline and a
  0.45/0.20 via there — placed by `tools/route_base.py`. The via sits exactly where the
  through-hole pad centre used to be, so every existing route still lands where it always
  did. The 1.4 mm gap between the staggered pad columns takes that via with 0.475 mm of
  copper clearance, well over the 0.1 mm rule.
- **48 SMT contacts now take the full DIP insertion force with no through-hole anchor.**
  This is the highest-force and most-cycled joint on the board. If pads start lifting,
  that is the reason, and mounting hardware is the fix.

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
documents only the BGA. Ring it out against the actual XGecu adapter before ordering board
B — nothing in software can catch it being wrong, because both boards would be
consistently wrong together and ERC, DRC and a netlist diff would all pass.

`tools/ringout.py` drives this. Run it with no arguments for the probe checklist (19 used
pins, each with the neighbours that must stay open), record the readings in
`docs/ringout-results.txt`, then `make ringout`. It names the failure mode rather than
just diffing: a uniform offset or a mirror is a one-line table fix, whereas an irregular
mapping that touches the data bus means board B has to be rerouted before it is ordered.

Only ~21 of the 48 positions need pins populated (the 17 nets plus corner pins for
retention), but the board must still span pin 1 to pin 24: 23 × 2.54 = 58.42 mm.
