# Handoff

Everything a new agent needs to continue this project. Repo is at `~/bga67-to-dip48`,
git-tracked, clean tree.

## Goal

A BGA-67 NAND flash → DIP48 adapter for an XGecu programmer, so salvaged flash chips can be
read/written and swapped without rebuilding the DIP48 pin field each time.

Split into two boards because the DIP48 span is fixed by the socket (23 × 2.54 = 58.42 mm
pin 1 to pin 24) while the flash carrier wants to be small and replicated:

| | dir | contents | size |
|---|---|---|---|
| A | `carrier/` | TC58NVG1S3HBAI6 (VFBGA-67) + DF40 30-pin plug | 9.25 × 7.45 mm |
| B | `base/` | DIP48 SMT socket field + DF40 30-pin receptacle + pull-ups + bulk | 30 × 90 mm |

## Working preferences

- **Do not use the Konnect MCP tools.** The user asked for them to be avoided. Edit files
  directly. `.kicad_pro` is plain JSON; a `json` round-trip with `indent=2` is safe.
- **Close KiCad before editing project files.** KiCad holds the project in memory and writes
  its own copy over yours on save. This caused a lost edit already.
- Verify claims against files before stating them. Do not repeat stale findings from earlier
  in a conversation without re-checking.

## Current state

**Done and verified:**

- `carrier/` schematic is drawn and wired. U1 (flash) + J1 (connector) + power symbols.
  15 signal nets: `IO1`–`IO8`, `/CE`, `/WE`, `/RE`, `/WP`, `CLE`, `ALE`, `RY//BY`, plus
  `VCC`/`GND`. ERC is clean. Netlist verified pin-for-pin against the ball map.

  *This was broken until 2026-08-09.* The `lib_symbols` cache still keyed its entries under
  the old `bga67-to-dip:` nickname while the instances referenced `carrier:`. KiCad could
  not resolve the cached definitions, so U1 and J1 were placed with **no pins**: 85 ERC
  violations, every label dangling, and the netlist collapsed to 2 nets with all 67 U1 pads
  shorted together. If you ever rename a project library, grep the schematic for the old
  nickname — a stale cache key fails silently and still opens.
- `carrier/` PCB is **placed, routed and DRC-clean** — 0 violations, 0 unconnected.
  9.25 × 7.45 mm, 4 layers, one via per signal net (20) plus 15 GND stitching vias around
  the perimeter, uniform 0.15 mm tracks, teardrops throughout, GND poured on all four
  layers (In1/In2 at 52.1 mm² each of 68.9).
- `base/` schematic is drawn and wired. ERC clean, 17 nets, cross-checked against both
  tables in `connector-pinout.md`.
- Custom parts, all built from the datasheet/catalog and cross-checked against source
  dimensions:
  - `carrier:TC58NVG1S3HBAI6` symbol, 67 pins
  - `carrier:BGA-67_6.5x8.0mm_Layout8x10_P0.8mm` footprint, 67 pads, **no paste layer**
    (chips are reballed with leaded solder), `solder_mask_margin 0.05`
  - `carrier/lib/3d/BGA-67_....step` — built to datasheet dims, verified ball centres match
    pad coordinates exactly
  - `carrier:DF40TC-30DP-0.4V_51_` symbol + `Connector_Hirose_DF40:HIROSE_DF40TC-30DP-0.4V_51_`
    footprint, and `carrier:DF40TC_4.0_-30DS-0.4V_51_` + its receptacle footprint, derived
    from the DF40T (p.9) and DF40 (p.10) catalog dimension tables. 30 pins, no G1–G4.
    The superseded DF40GB pair is still in the library; nothing references it.
  - `base:DIP-48_SocketStrip_SMD_W15.24mm_P2.54mm` footprint — 48 SMD pads on DIP
    numbering, tails staggered ±1.65 mm about the two 15.24 mm-spaced row centrelines
- Design rules and net classes set on both projects (see below).
- `docs/connector-pinout.md` — the interface contract between the two boards.

- `panel/carrier-panel.kicad_pcb` — 4×4 mouse-bite panel, 56.80 × 49.60 mm, 16 up.

- `base/` PCB is placed and routed: **0 DRC violations, 0 unconnected**, ERC clean.
  `make check` passes on both projects. Run `make route-base` to rebuild the vias and
  inner-layer routing; it is additive and re-runnable, and it now also lays the SMD
  field's landing stubs and vias.
- Every connector pad is connected. All 19 used J2 pads have a track endpoint on the pad
  centre; J1's 12 unlanded pads are exactly the checkerboard's GND pins, which take the
  pour by design. Cross-checked against KiCad's own connectivity engine
  (`GetUnconnectedCount() == 0`), not just the DRC report.
- **Two routes are hand work the router cannot reproduce.** `strip()` preserves F.Cu and
  B.Cu, so a `make route-base` rerun leaves both alone — but verify they survive:
  - `J1.6` (VCC) escapes *inward* on B.Cu, a 0.5 mm stub from (125.14, 89.103) into the
    channel between the connector rows. `escape_and_route` rejects both directions for
    this pad: outward, IO5's and IO7's routes pass 0.4 mm away, which is exactly the via
    clearance limit, so no via will fit; inward, its stub check fails.
  - The GND pad tie at (121.5, 89.5) → (122.56, 89.502) on B.Cu, which cleared the last
    detached pour fragments.

The detached GND pour fragments that used to sit here are gone. They were not slivers
needing another stitching via, which is what `tie_fragments` kept trying and failing to
do — more rounds made it worse, not better. The pour needed one direct tie to a J1 GND
pad. Worth remembering if fragments reappear after a re-pour.

**Not done:**
- No 3D model on the DF40 30-pin plug or receptacle footprints. The STEP files under
  `carrier/lib/` are the **48**-pin part, not the 30-pin one, and both are now the
  superseded DF40GB shape anyway.
- TSOP48 pinout: **confirmed**, see docs/connector-pinout.md. Matches Samsung
  `K9F2G08U0C` 48-TSOP1 on all 19 used pins and all 29 NC pins, and 13 of 15 signals are
  proven end to end by the working dump. `/WP` and `RY//BY` are not exercised by a
  read-only dump; both have 10 k pull-ups on board B. Still worth confirming on the bench,
  and `tools/ringout.py` will check the readings: the adapter's **pin 1 corner** and the
  socket's row spacing. Orientation is the residual risk, not signal assignment.
- The DF40TC plug's end pads are unverified — see "Unverified" below.
- **Nothing checks that the XGecu adapter's body clears the base board.** The DIP48 field
  is surface mount now, so the adapter seats ~3 mm lower than it would have.

## Stack height — 4.0 mm, via the automotive family

**4.0 mm.** `DF40TC-30DP-0.4V(51)` plug (HRS `CL0684-4263-0-51`) on the carrier,
`DF40TC(4.0)-30DS-0.4V(51)` receptacle (HRS `CL0684-4256-0-51`) on the base.

The earlier note in this file said 4.0 mm did not exist at 30 positions in any DF40
family. That was wrong, and here is the correction: it does not exist in the shielded
`DF40GB` family (30 pos at 1.5 mm only) and it does not exist in plain `DF40C`/`DF40HC`
(3.5 mm at 30 pos), but **`DF40T` — the 125 °C automotive family — is mass production at
30 positions × 4.0 mm.** DF40T/DF40GT catalog (Jan 2026), p.2 variation matrix and p.8
combinations table. 4.5–7.0 mm at 30 pos is Under Planning, so 4.0 mm is the ceiling.

**The plug part number carries no stacking height.** One DF40TC plug covers 1.5 through
4.0 mm; the receptacle sets the gap. Changing the stack height again is a board-B-only
part swap.

The swap was nearly free in layout terms because the land patterns are identical: DF40T
p.9 gives the plug as P=0.4, B=5.60, pad 0.23 wide, rows 3.37/2.05 → 0.66 long at
y = ±1.355, and DF40 p.10 (DF40HC, No Retention Tab) gives the receptacle as 0.2 × 0.70 at
y = ±1.54. Both match the DF40GB footprints pad for pad. **All 30 signal pads are unmoved
on both boards.** Only G1–G4 went away — `TC` has no retention tabs — so the symbols,
schematics and footprints all dropped those four pads and their GND ties.

What it costs: 0.3 A instead of 0.5 A (the flash draws 30 mA), **10 mating cycles instead
of 30**, and no shield. The 10-cycle figure makes the existing rule load-bearing: the
repeatedly separated joint is the DIP48/ZIF end.

## Design rules

**Moved to `docs/jlc-rules.md`, and they are now generated, not hand-set.**
`tools/drc-rules.py` is the only writer -- run `make rules` after editing
`tools/jlc-4layer.kicad_dru`, and `make check` to verify nothing drifted. Every value is
quoted from JLCPCB's capabilities page with the section it came from.

Netclasses (still per project, still hand-set):

```
Default  track 0.15  clr 0.1  via 0.45/0.25
Signal   track 0.15  clr 0.1  via 0.45/0.25
Power    track 0.4   clr 0.1  via 0.6/0.3

patterns: /* -> Signal, VCC -> Power, GND -> Power
```

Default deliberately carries the signal geometry so control nets need no pattern.
KiCad netclass patterns are `*`/`?` wildcards only -- **no regex alternation**, `VCC|GND`
matches nothing.

The pattern is `/*`, not `IO*`. Root-sheet local labels get a sheet-path prefix, so the
signal nets are named `/IO1`, `/{slash}CE`, `/RY{slash}{slash}BY`. `IO*` matched nothing and
every signal net fell through to Default. Verified: all 15 now resolve to Signal, VCC/GND
to Power.

**Clearance is 0.1 mm, not 0.15, for a reason.** At 0.15 the ball field is unroutable:

```
0.8 mm pitch, 0.4 mm pads, diagonal spacing 1.1314 mm
dogbone via sits 0.5657 mm from 4 pad centres

via 0.60 pad -> 0.0657 mm gap    fails everything
via 0.45 pad -> 0.1407 mm gap    fails 0.15, passes 0.1
via 0.40 pad -> 0.1657 mm gap

trace between adjacent pads (0.400 mm available):
  0.15 trace + 2x0.15 clr = 0.450  fails
  0.15 trace + 2x0.10 clr = 0.350  ok
```

**Copper clearance is not what binds -- hole clearance is.** The escape was sized against
a 0.25 mm hole clearance:

```
via 0.45 / 0.25 drill -> 0.5657 - 0.125 - 0.200 = 0.2407 mm   fails 0.25
via 0.45 / 0.20 drill -> 0.5657 - 0.100 - 0.200 = 0.2657 mm   passes
```

JLC's actual inner-layer via-hole-to-copper limit turns out to be **0.20 mm**, so the
board now has margin it did not have when it was routed. **Do not spend it by widening
the drill.** 0.45/0.20 sits exactly on JLC's free-tooling boundary; a wider drill or a
narrower pad both cost more. See `docs/jlc-rules.md`.

Note also that netclass via/track defaults do not apply inside the ball field: Power wants a
0.6 mm via and a 0.4 mm track, neither of which fits. Escape stubs are 0.15 mm and escape vias
are 0.45/0.20 on every net including VCC and GND. Netclass values are defaults, not minima, so
DRC is satisfied.

A per-pad clearance override does **not** help -- KiCad resolves clearance between two items
as the largest applicable value, so loosening one side changes nothing.

## Fab

JLCPCB, **4 layers**, ENIG. L2 must be a solid ground pour spanning the ball field.

- Via-in-pad was considered and rejected: JLC's free via-in-pad is **6 layers and up**, not
  4. At 0.8 mm pitch with only 20 used balls, dogbone escape is adequate.
- **Tent the vias.** An untented 0.45 mm via leaves a 0.0907 mm solder mask dam to the
  neighbouring BGA pad; JLC's minimum is 0.10 mm.
- **Keep board-level solder mask expansion at 0.** The DF40 has only 0.17 mm of copper gap
  at 0.4 mm pitch; any global expansion drops its mask dams below 0.10 mm. The BGA carries
  its own +0.05 margin at footprint level.
- `min_copper_edge_clearance` is **0.2 mm** (was KiCad's 0.5). JLC allows 0.2, and 0.5 was
  costing a millimetre of width.
- **Trace geometry is not what costs money at JLC.** 4-layer 1 oz is 0.09/0.09 mm standard
  and they explicitly allow 3 mil in BGA fanouts. The surcharge is on drilling: *"0.2mm or
  0.25mm hole size with via diameter less than 0.45mm, will cost more."* The vias are
  0.45/0.20 — exactly on the free boundary. **Do not shrink the via pad below 0.45.**
- Minimum board size is 3 × 3 mm for FR4 at ≥0.6 mm thickness, so there is headroom left.

## Hard constraints

- **F.Cu is the carrier's mating face.** J1 (the plug) is on F.Cu and faces board B. U1 and
  the passives go on **B.Cu**, the outward face, where they have unlimited headroom — the
  VFBGA67 is 1.00 mm max tall, so it would physically fit in the mezzanine gap, but it does not
  live there. B.Cu therefore carries the parts; nothing but the connector sits on F.Cu.
  U1 is rotated 90°, so the 8.0 × 6.5 package sits 8.0 wide. The board is now trimmed to
  9.25 × 7.45 mm, which leaves ≥0.32 mm to the package body and ≥0.36 mm to copper — no room
  for passives on either face, which is why decoupling moved to board B.
- **The 47 NC balls float.** Do not tie them to ground.
- **Do not permute the data bus.** Commands and addresses travel over the same I/O pins;
  a swizzle corrupts the command byte, it does not merely scramble a dump.
- **DF40TC is rated 10 mating cycles.** The repeatedly-separated joint must be the
  DIP48/ZIF end, not the mezzanine. This matters more than it did at 30 cycles.
- **Mirror trap.** The boards mate face to face, so X flips. On `base`, viewed from the top,
  the receptacle's pin 1 sits at the opposite end from where intuition puts it. Check a
  mated pair in the 3D viewer before ordering.

## Board A bill of materials

- U1 — TC58NVG1S3HBAI6
- J1 — DF40TC-30DP-0.4V(51)
- **No decoupling on the carrier.** Worked the numbers rather than assuming: worst case is
  8 I/O switching into 30 pF with 5 ns edges — 158 mA through 5.45 nH — which is 173 mV,
  5.2% of 3.3 V against a 660 mV budget to VIH. At the 20–50 ns edges a programmer actually
  produces it is 2–11 mV. The datasheet specifies no bypass cap; DC is 30 mA max over two
  DF40 contacts rated 0.5 A each; program/erase draw that over milliseconds with no di/dt.
  The largest inductance term is the carrier's own J1-to-ball trace, which a local cap only
  partly shortens.
  **Decoupling lives on board B: 100 nF within ~2 mm of the receptacle's VCC pins.**
  If dumps ever come back flaky, adding a carrier cap is the first thing to try — it needs
  ~2.6 mm more board width.

Pull-ups (`RY//BY` 10 k, `/WP` 10 k) and the 1 µF bulk were moved to board B — they are
static or low-frequency and board B has the space.

## Unverified

**The DF40TC plug's end pads.** The DF40T catalog's plug land drawing (p.9) carries
0.475 and 0.35 dimensions at each end that may be hold-down pads, but `TC` means no
retention tab and the catalog shows no with/without pair the way the receptacle page does.
The footprint omits them. That is the safe direction to be wrong in: if the part does have
hold-downs they go unsoldered and you lose a little retention, whereas pads under a
housing with no metal there would take paste and tilt a 0.4 mm-pitch connector.

**The TSOP48 pinout is no longer in this section** -- it is confirmed, see
docs/connector-pinout.md. Two independent manufacturer datasheets agree pin-for-pin
including every no-connect, and the working dump proves 13 of 15 signals end to end
through the real programmer and adapter. Ring it out against the physical XGecu
adapter before committing the base board layout. Also confirm the socket's row spacing is
0.6″ and where its pin 1 sits relative to the lever.

## Source documents

- Datasheet: `/Users/alex/Downloads/KIOXIA_TC58NVG1S3HBAI6_Rev2.00_E191001C.pdf`
  (ball map p.2, package dimensions p.64)
- Hirose DF40 catalog: https://www.hirose.com/en/product/document?series=DF40&documenttype=Catalog&lang=en&documentid=en_DF40_CAT
- JLCPCB capabilities: https://jlcpcb.com/capabilities/pcb-capabilities
