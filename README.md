# bga67-to-dip48

BGA-67 NAND flash to DIP48 adapter for an XGecu programmer, split across two boards so the
flash carrier can be swapped without rebuilding the DIP48 field.

| | Board | Contents | Size |
|---|---|---|---|
| A | `carrier/` | KIOXIA TC58NVG1S3HBAI6 (VFBGA-67) + DF40 30-pin plug | 9.25 × 7.45 mm |
| B | `base/` | DIP48 SMT socket field + DF40 30-pin receptacle + pull-ups + bulk | 30 × 90 mm |

The DIP48 span is fixed by the socket — 23 × 2.54 = 58.42 mm from pin 1 to pin 24 — which is
why the boards are split. Only the carrier needs to be small and repeatable.

## Layout

```
carrier/        board A project (KiCad)
  lib/          shared symbols, footprints, 3D models  <- both projects point here
base/           board B project (KiCad)
docs/           connector-pinout.md  <- read before touching either board
```

`base` references the libraries via `${KIPRJMOD}/../carrier/lib/...`, so the repo relocates
and clones cleanly. Shared libraries live under `carrier/lib` because the BGA footprint's 3D
model path is `${KIPRJMOD}/lib/3d/...`; moving the directory would break that reference.

## Constraints worth knowing before editing

- **F.Cu is the carrier's mating face.** Only the DF40 plug lives there. U1 and the passives
  go on B.Cu, the outward face.
- **Stack height is 4.0 mm**, via the `DF40T` (125 °C) family — the only DF40 that does 30
  positions at 4.0 mm. The plug part number carries no height, so the receptacle alone sets
  the gap. See `docs/connector-pinout.md`.
- **DF40TC is rated 10 mating cycles**, not 30. Keep the repeated joint at the DIP48/ZIF
  end, not here.
- **The DIP48 field is surface mount** — two 1×24 socket strips with staggered tails, so
  nothing protrudes below the board into the carrier's space.
- **The 47 NC balls float.** Do not ground them.
- **Data bus order is load-bearing** — commands and addresses share the I/O pins. See
  `docs/connector-pinout.md`.

## Fab

JLCPCB, 4 layers, 1.6 mm. The ground pour sits on **In2.Cu**, the inner layer adjacent to
the ball field — U1 is on B.Cu, so In1.Cu is the wrong side of the stack. Without that plane
the connector's checkerboard ground pinout does nothing. ENIG — HASL on 0.4 mm BGA pads is
not worth the trouble. No paste on the BGA footprint (chips get reballed with leaded solder).

Design rules are identical in both projects. Net classes bind via pattern `/*` → Signal and
`VCC`/`GND` → Power; the leading slash matters, because root-sheet local labels land on the
board as `/IO1` rather than `IO1`.

## Panel

`panel/carrier-panel.kicad_pcb` is a 4×4 mouse-bite panel, 56.80 × 49.60 mm, generated from
the single board. **Everything under `panel/` except `fp-lib-table` is disposable output.**
Close KiCad, then:

```bash
make panel
```

That runs [`tools/panelize.sh`](tools/panelize.sh), which is the only place the recipe
lives — the parameters are named variables at the top of the script. It refuses to run
while KiCad holds a lock (otherwise you panelize a stale carrier), DRCs the source board
first, regenerates `panel/fp-lib-table` so a fresh clone resolves footprints, dedupes the
co-located mouse-bite drills KiKit leaves at every tab junction, then DRCs the result and
prints the panel size and board count. Non-zero exit means something needs looking at.

Do not hand-edit the panel and do not paste a modified `kikit` command into a shell — edit
the script. The **negative** mouse-bite offset in particular is load-bearing and the script
says why.

Rails give you something to hold while reflowing the BGA and hand-soldering a 0.4 mm-pitch
connector.

`make check` runs ERC and DRC over both projects and validates `tools/pinout.py`.

## State

Both schematics are drawn, wired and ERC-clean.

**The carrier is finished** — placed, routed, 0 DRC violations, 0 unconnected — and
panelized.

**Board B is routed and clean**: 0 DRC violations, 0 unconnected. `make check` passes on
both projects.

Every pad is connected. All 19 used J2 pads have copper landing on the pad centre, and
J1's 12 unlanded pads are exactly the checkerboard's GND pins that take the pour by
design.

Two routes on `base/` are hand work that `tools/route_base.py` cannot reproduce. `strip()`
only removes vias and inner-layer tracks, so a `make route-base` rerun preserves both —
but check they are still there afterwards:

- **`J1.6` (VCC)** escapes *inward* on B.Cu, into the channel between the connector rows.
  The router rejects both directions for this pad: outward, IO5's and IO7's routes pass
  0.4 mm away, exactly the via clearance limit, so no via fits; inward, its stub check
  fails.
- **The GND pad tie at (121.5, 89.5) → (122.56, 89.502)** on B.Cu. This is what finally
  cleared the detached pour fragments. They were not slivers wanting another stitching via
  — the pour needed a direct tie to that J1 GND pad. `tie_fragments` never found it, and
  raising its round count made things worse rather than better.

**The TSOP48 pinout is confirmed** — see `docs/connector-pinout.md`. It agrees pin-for-pin
with Samsung's `K9F2G08U0C` 48-TSOP1 datasheet across all 19 used pins *and* all 29 NC
pins, and 13 of the 15 signals are additionally proven end to end by the 285 MB dump that
was read through this programmer and adapter — a permuted bus cannot return a valid Read
ID, let alone a parseable filesystem.

`/WP` and `RY//BY` are the two a read-only dump cannot exercise; both carry 10 k pull-ups
on board B. What is left is orientation rather than assignment: confirm which corner of
the adapter is pin 1 against `J2`'s, which is top-left viewed from the top.
`python3 tools/ringout.py` prints a probe checklist if you want to measure it anyway.

**The DF40TC plug's end pads are unverified.** The DF40T catalog's plug land drawing
carries 0.475 and 0.35 dimensions at each end that could be hold-down pads, but `TC` means
no retention tab. The footprint omits them, which is the safe error: if the part does have
hold-downs they simply go unsoldered, whereas pads under a housing that has no metal there
would collect paste and tilt the connector.
