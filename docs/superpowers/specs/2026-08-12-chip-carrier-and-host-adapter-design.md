# Board C (chip carrier) and board D (host adapter)

Date: 2026-08-12
Status: approved, not yet implemented

## Problem

Reprogramming the target NAND currently means moving the chip itself. Even with the existing
carrier A / base B path, the chip lives clamped in an XGecu BGA adapter, and the resulting
stack on the target board is:

    carrier A -> DF40 (4.0) -> base B -> SSM-124-L-SV strips (7.49) -> clamp adapter -> NAND

That is roughly 25 mm tall and top-heavy, with the mass cantilevered off a mated 0.4 mm
30-position connector whose load path terminates in carrier A's solder joints on the target
motherboard. The handoff rule says that path must never carry service load.

## Goals

- Solder the NAND exactly once, to a dedicated carrier, and never hot-air it again.
- Cycle between target board and programmer by unplugging a mezzanine joint, not by reflow.
- Reduce stack height and cantilevered mass on the target board.

## Non-goals

- Generalizing the interface to other packages or programmers. See "Productization" below.
- Any change to `tools/pinout.py`. The 30-pin table is invariant across all four boards.
- HDI, microvia, or blind/buried via on any board. Via-in-pad and filled/capped vias are
  excluded on boards A, B and D. **Superseded for board C on 2026-08-13**: board C uses
  via-in-pad with JLCPCB Epoxy Filled & Capped, because the NAND is reflowed onto its lands
  and neither a soldermask-plugged via (not flat enough to stencil against) nor an untented
  one (wicks solder from the ball joint) is acceptable there. Unconfirmed on 4 layers — see
  the pre-order gate in `docs/HANDOFF.md`.

## Architecture

Three roles over one interface:

| Role | Board | Specific to |
|---|---|---|
| Target adapter | carrier A, `carrier/` | the footprint being tapped |
| Device carrier | board C, `chip/` | the NAND package |
| Host adapter | board D, `prog/` | the programmer |

The invariant between them is the DF40 30-position same-number contract already recorded in
`docs/connector-pinout.md`: plug `J1.n` mates receptacle `J1.n`, and the mechanical
face-to-face mirror lives in the receptacle footprint, never in a net table.

    normal operation                 programming

    NAND                             NAND
    board C                          board C
    DF40 4.0 mm                      DF40 4.0 mm
    carrier A                        board D
    target board                     T76 48-pin ZIF

Board C plus NAND is the assembly that moves. Carrier A stays soldered to the target board.
Board D stays in the programmer.

Base B and the XGecu clamp adapter remain a working second path for running the target board
with a chip that has not been committed to a carrier. Base B's electrical design, net table,
and routing are unchanged by this work; it is touched only for stale documentation and the
cosmetic silkscreen warnings noted under "Open items".

## Verified facts

Measured on 2026-08-12 with pcbnew 10.0.5. These are the numbers the design depends on.

**Carrier A's mirrored footprint is correct.** Its B.Cu pads in absolute top-view
coordinates fit the normal land pattern as a proper rotation: scale 1.000000, angle exactly
90.000 deg, RMS residual 0.000000 mm. The reflected fit gives RMS residual 2.744750 mm. A
chip-replacement interposer requires a proper rotation with no mirror, because carrier A and
the motherboard are both seen looking down at the assembly. Carrier A passes.

**The footprint name is misleading but harmless.** `..._Mirrored_Interposer` local pad
coordinates are the normal footprint with *both* coordinates negated, a 180 deg rotation, not
a mirror. Example: ball `A2` at (-2.0, -3.6) becomes (+2.0, +3.6). Composed with KiCad's
back-layer flip and `U1`'s 90 deg placement this yields the correct physical result. Do not
rename the footprint; add a comment instead.

**The existing position check is self-referential.** `tools/check_interposer.py` asserts
`expected_x = -(column - 4.5) * 0.8` and `expected_y = ROW_Y_MM[row]`, which restates the
footprint's own contents. It cannot detect a mirror error. Replace it.

**BGA geometry.** 67 pads. Ball field 5.6 mm (8 columns) by 7.2 mm (10 rows) at 0.8 mm
pitch. Package body 6.5 x 8.0 mm. `U1` is placed at 90 deg, so the body sits 8.0 mm along
the board's 8.41 mm axis and 6.5 mm along its 7.60 mm axis, leaving 0.205 mm and 0.55 mm of
margin per side. The package is fully supported; board C does not need to grow.

**DF40 plug versus receptacle.** Exact pin-for-pin X-mirror across all 30 positions. Plug
rows at y = +/-1.355 mm with 0.23 x 0.66 mm pads; receptacle rows at y = +/-1.54 mm with
0.2 x 0.7 mm pads. The plug additionally carries non-electrical retention lands MT1-MT4 at
x = +/-3.275, y = +/-1.355, 0.35 x 0.66 mm.

**Base B is routed and fabricable.** DRC on `base/base.kicad_pcb`: 0 unconnected items, 0
schematic parity issues, 20 violations all of severity `warning` and all "text thickness out
of range" on silkscreen. `README.md` and `docs/HANDOFF.md` both still claim 34 unconnected
items and "do not fabricate"; both are stale.

**Programmer.** XGecu T76, 48-pin ZIF. Its own BGA63/BGA48 adapter uses square pins, so
square pins are what this socket expects and board D uses them.

## Board C, `chip/`

The board the NAND is permanently soldered to.

- Outline 8.41 x 7.60 mm, identical to carrier A, so it tiles on the same panel and occupies
  the same footprint on the target board.
- Four layers, 1.6 mm, ENIG, JLCPCB standard process. The thickness is load-bearing: a
  shared panel forces one thickness across every board.
- F.Cu: `U1`, the existing non-mirrored `BGA-67_6.5x8.0mm_Layout8x10_P0.8mm` footprint. Real
  chip, real balls, normal orientation. No mirrored variant is involved anywhere on board C.
- B.Cu: `J1`, `HIROSE_DF40TC_4.0_-30DS-0.4V_51_`, the same receptacle base B uses, with base
  B's net table unchanged.
- The 47 unused balls float, matching carrier A and matching what the target motherboard
  does with them.
- Decoupling: 100 nF plus 1 uF, 0402, between VCC and GND on B.Cu, in the roughly 1.8 mm
  strips flanking the receptacle body. In normal operation the target board's decoupling is
  now two boards and a mated connector away from the die. Parts hang 0.5 mm into a 4.0 mm
  gap, so they cannot touch carrier A.
- Escape routing follows carrier A's conventions: 0.15 mm tracks, ordinary 0.45/0.20 mm
  through-via dogbones, one short diagonal from each used land, no via in any BGA pad.
- Silkscreen: pin-1 marker on both faces, board name.
- The outer 0.5 mm of both long B.Cu edges stays clear of components so tweezers can get
  under the board.

Resulting stack on the target board: 1.6 + 4.0 + 1.6 + ~1.0 = **~8.2 mm**, against roughly
25 mm for the base B path.

### Accepted risk: extraction

Board C is the part that gets cycled, and it has no grip feature. Removing it means gripping
an 8.4 mm board with a chip on it and pulling square off a mated 30-position 0.4 mm
connector. Rocking it instead of lifting it puts a moment through carrier A into the target
board's BGA joints. Grip tab, tooling holes, and a dedicated puller were all considered and
declined in favour of preserving the outline and the clearance win. If wear or joint damage
shows up in practice, tooling holes are the cheapest retrofit and do not change the outline.

## Board D, `prog/`

The host adapter that carries board C into the programmer.

- Derived from base B: same 27.78 x 61.38 mm outline and the same routing topology, because
  base B is routed and the net map is identical. Shrinking to roughly 20 mm wide is possible
  once the socket strips no longer set the width, but the panel area saved is not worth
  disturbing a working routing topology.
- Four layers, 1.6 mm, ENIG, same ruleset and ground plane as the other boards.
- F.Cu: `J1`, `HIROSE_DF40TC-30DP-0.4V_51_`, the same plug carrier A uses, same net table,
  centred along the length so board C clears the ZIF lever.
- B.Cu: two 1x24 2.54 mm square-pin headers pointing down, 15.24 mm row spacing. All 48
  positions populated for even clamping in the ZIF; only 22 carry nets, the remaining 26
  float, matching the NC pins of a real TSOP48 device.
- Decoupling: 100 nF at the plug.

Both connectors change face relative to base B. That is two separate transforms, not one
board flip, and it is exactly the class of change that produced the earlier double-mirrored
connector table. Build it deliberately and verify it with the fit test rather than flipping
and trusting.

Board C plus NAND rises about 6.6 mm above board D's top surface.

## Panel

One panel, all four boards, since every board is now 1.6 mm / 4 layer / ENIG and nothing is
blocked on routing.

- Extend `tools/panelize.sh` from carrier-only to a system panel.
- Roughly ten each of carrier A and board C, which tile identically because they share an
  outline, plus one or two each of base B and board D.
- That is about 4700 mm2 of board area, but base B and board D are each 61.38 mm long, so
  the long axis and not the total area sets the panel outline. Let `panelize.sh` determine
  the final panel size rather than fixing a number here.
- Board C inherits the tab and depanel strategy the existing `panel/` project already proved
  for the 8.41 x 7.60 outline.

## Verification

`tools/pinout.py` does not change. That is the strongest property of this design: one 30-pin
table serves all four boards.

1. Replace the self-referential ball-position assertion in `tools/check_interposer.py` with
   the rigid-fit handedness test. For each board, fit its BGA pad set against the normal
   footprint allowing rotation and translation only, and separately allowing reflection. The
   proper-rotation residual must be the smaller of the two and must be near zero. The boards
   carrying a BGA field are carrier A and board C; both must pass.
2. New check: board C's *ball name to DF40 pin* map must equal carrier A's *ball name to
   DF40 pin* map. Same ball, same pin. If these agree, the chip on board C sees exactly what
   the target motherboard would have driven it with. This is the single check that catches
   the mirror class of bug end to end.
3. New check: board D's *DIP pin to DF40 pin* map must match the TSOP48 column of the NAND
   mapping table in `docs/connector-pinout.md`.
4. Extend `tools/check_mating.py` to the two new mated pairs, A to C and D to C. Both are the
   same X-mirror relationship already checked for A to B.
5. `make check` gains ERC and DRC for `chip/` and `prog/`.
6. Do not release fabrication files until `make check` passes on all four projects and
   pin-1 orientation has been confirmed by eye on every mated interface.

## Documentation changes

- Correct `README.md` and `docs/HANDOFF.md`: base B is routed, 0 unconnected items, and is
  fabricable. Both currently say the opposite.
- Add boards C and D to the board table in `README.md`.
- Add a comment at `..._Mirrored_Interposer` recording that its local coordinates are a
  180 deg rotation rather than a mirror, and that the physical mirror comes from the
  back-layer placement.
- Add the three-role description to `docs/connector-pinout.md`: target adapter, device
  carrier, host adapter, with the DF40 30-pin same-number contract as the invariant between
  them.

## Productization

The architecture is already the right shape for a general fine-pitch access system, and
saying so in the docs costs a paragraph. Building for it does not pay yet: 30 positions
carrying 15 signals plus power is sized for this NAND specifically, and a package-agnostic
fixture would need a wider connector and a signal-agnostic pin contract. Document the
contract now, generalize nothing.

## Open items

- Hirose DF40 unmating force has not been read from the datasheet. It informs how bad the
  extraction risk above actually is, but does not block the design.
- The 20 silkscreen text-thickness warnings on base B are cosmetic and should be cleared
  before the shared panel is generated, since the panel carries them forward.
