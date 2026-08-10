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
| A | `carrier/` | TC58NVG1S3HBAI6 (VFBGA-67) + DF40 30-pin plug + 2× 100 nF | ~12 × 14 mm |
| B | `base/` | DIP48 pin field + DF40 30-pin receptacle + pull-ups + bulk | ~63 × 20 mm |

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
- `carrier/` PCB: nets imported, U1 fpid corrected, 4 copper layers on a JLCPCB 1.6 mm
  stackup, GND pour on In2.Cu. DRC clean, 37 unconnected (nothing routed).
- `base/` schematic is drawn and wired. ERC clean, 17 nets, cross-checked against both
  tables in `connector-pinout.md`.
- Custom parts, all built from the datasheet/catalog and cross-checked against source
  dimensions:
  - `carrier:TC58NVG1S3HBAI6` symbol, 67 pins
  - `carrier:BGA-67_6.5x8.0mm_Layout8x10_P0.8mm` footprint, 67 pads, **no paste layer**
    (chips are reballed with leaded solder), `solder_mask_margin 0.05`
  - `carrier/lib/3d/BGA-67_....step` — built to datasheet dims, verified ball centres match
    pad coordinates exactly
  - `carrier:DF40GB-30DP-0.4V_51_` symbol + `Connector_Hirose_DF40:HIROSE_DF40GB-30DP-0.4V_51_`
    footprint, derived from the Hirose DF40 catalog dimension table
- Design rules and net classes set on both projects (see below).
- `docs/connector-pinout.md` — the interface contract between the two boards.

**Not done:**

- `carrier/` PCB layout — nothing placed or routed.
- `base/` PCB — 4 layers and net classes are set, but nothing imported or placed.
- No 3D model on the DF40 30-pin plug or receptacle footprints. The STEP files under
  `carrier/lib/` are the **48**-pin part, not the 30-pin one.
- No decoupling caps in the `carrier/` schematic. The BOM below lists 2× 100 nF; they are
  not drawn yet.

## Stack height — settled, and not the way you would guess

**1.5 mm.** The carrier's plug is `DF40GB-30DP-0.4V(51)`, and `GB` is the *shielded* DF40
family. The catalog's shielded matrix offers 30 positions at 1.5 mm only; the sole mating
receptacle is `DF40GB(1.5)-30DS-0.4V(51)` (HRS `CL0684-4198-4-51`, 30 signal + 4 ground).

4.0 mm does not exist at 30 positions in *any* DF40 family — it starts at 50 positions.
Unshielded DF40C/HC reach 3.5 mm at 30 positions, so if you need a bigger gap the carrier's
plug has to be re-specified too. That is the only lever.

## Design rules (both projects, JLCPCB 4-layer 1 oz)

```
min track 0.09   min clearance 0.09   min via 0.3/0.2   min hole 0.2

Default  track 0.15  clr 0.1  via 0.45/0.25
Signal   track 0.15  clr 0.1  via 0.45/0.25
Power    track 0.4   clr 0.1  via 0.6/0.3

patterns: /* -> Signal, VCC -> Power, GND -> Power
```

Default deliberately carries the signal geometry so control nets need no pattern.
KiCad netclass patterns are `*`/`?` wildcards only — **no regex alternation**, `VCC|GND`
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
  0.15 trace + 2×0.15 clr = 0.450  fails
  0.15 trace + 2×0.10 clr = 0.350  ok
```

A per-pad clearance override does **not** help — KiCad resolves clearance between two items
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
- `min_copper_edge_clearance` is still KiCad's 0.5 mm. JLC allows 0.2. Worth changing —
  0.5 costs a millimetre of width on a 12 mm board.

## Hard constraints

- **F.Cu is the carrier's mating face.** J1 (the plug) is on F.Cu and faces board B. U1 and
  the passives go on **B.Cu**, the outward face, where they have unlimited headroom — the
  VFBGA67 is 1.00 mm max tall, so it would physically fit in a 1.5 mm gap, but it does not
  live there. B.Cu therefore carries the parts; nothing but the connector sits on F.Cu.
  There are 2.5 mm strips either side of the BGA courtyard and 2.75 mm at each end (courtyard
  8.5 × 7.0 on a 14 × 12 board, i.e. U1 rotated 90°) — enough for the two 0402s.
- **The 47 NC balls float.** Do not tie them to ground.
- **Do not permute the data bus.** Commands and addresses travel over the same I/O pins;
  a swizzle corrupts the command byte, it does not merely scramble a dump.
- **DF40 is rated 30 mating cycles.** The repeatedly-separated joint must be the DIP48/ZIF
  end, not the mezzanine.
- **Mirror trap.** The boards mate face to face, so X flips. On `base`, viewed from the top,
  the receptacle's pin 1 sits at the opposite end from where intuition puts it. Check a
  mated pair in the 3D viewer before ordering.

## Board A bill of materials

- U1 — TC58NVG1S3HBAI6
- J1 — DF40GB-30DP-0.4V(51)
- 2× 100 nF 0402, top side, near VCC balls G7 (+2.0, +1.2) and H5 (+0.4, +2.0);
  GND ball J7 is at (+2.0, +2.8), so a cap around x ≈ +2.0, y ≈ +4.6 reaches all three

Pull-ups (`RY//BY` 10 k, `/WP` 10 k) and the 1 µF bulk were moved to board B — they are
static or low-frequency and board B has the space.

## Unverified

**The TSOP48 pinout in `docs/connector-pinout.md` comes from the JEDEC standard, not from
the Kioxia datasheet**, which documents only the BGA. Ring it out against the physical XGecu
adapter before committing the base board layout. Also confirm the socket's row spacing is
0.6″ and where its pin 1 sits relative to the lever.

## Source documents

- Datasheet: `/Users/alex/Downloads/KIOXIA_TC58NVG1S3HBAI6_Rev2.00_E191001C.pdf`
  (ball map p.2, package dimensions p.64)
- Hirose DF40 catalog: https://www.hirose.com/en/product/document?series=DF40&documenttype=Catalog&lang=en&documentid=en_DF40_CAT
- JLCPCB capabilities: https://jlcpcb.com/capabilities/pcb-capabilities
