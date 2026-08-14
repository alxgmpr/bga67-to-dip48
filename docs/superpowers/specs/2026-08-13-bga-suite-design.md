# BGA chip-off adapter suite — design

2026-08-13. Approved in brainstorming session; extends this repo in place.

## Goal

Generalize the VFBGA67 four-board system into a suite of chip-off adapters for common
storage BGA packages, reusing the DF40 service joint and the XGecu T76 / DIP48 programmer
path. Per package the suite provides the two tiny package-specific boards — a mirrored
**carrier** (board A role) and a **chip** board (board C role, epoxy-filled via-in-pad) —
and reuses a shared **base** (board B role) per family. The existing VFBGA67
`carrier/`, `chip/`, `base/`, `prog/` boards are unchanged and become the first family's
shipped instance.

Build approach: **hybrid** — scripted generation of footprints, land fields, netlists, and
board skeletons from per-package data modules; escape routing stays manual, guarded by
generalized checks. Full routing generation (scripted fanout / Freerouting) is explicitly
out of scope for now and noted as a possible later upgrade.

## Target packages

| Phase | Package | Family | Notes |
|---|---|---|---|
| 2 | eMMC BGA-153 | `emmc` | proving package for all new tooling |
| 3 | eMMC BGA-169 | `emmc` | |
| 3 | eMCP BGA-221 | `emmc` | eMMC balls only; LPDDR balls float |
| 3 | eMCP BGA-254 | `emmc` | eMMC balls only; LPDDR balls float |
| 4 | NAND BGA-48 | `nand_x8` | |
| 4 | NAND BGA-63 | `nand_x8` | |
| 5 | NAND BGA-132 | `nand_x8` | channel 0 only (see wide contract, future work) |
| 5 | NAND BGA-152 | `nand_x8` | channel 0 only |
| 6 | UFS BGA-153 | `ufs` | carrier + chip only; no T76 path |
| 6 | UFS BGA-254 | `ufs` | carrier + chip only; no T76 path |

(VFBGA67 is phase 1's regression target, not new work.)

## DF40 contract

One **universal 30-pin contract** on the existing DF40 part. Pin positions are fixed by
`tools/pinout.py` (still the single source of truth); each family assigns its signals onto
those positions through an overlay:

- Physical layout stays exactly as routed today: 15 signal positions, 13 GND, 2 supply
  pins (6 and 10), same-number mating contract.
- **Pin 10 is redefined from second VCC to `VCCQ`.** Single-supply families (`nand_x8`)
  strap VCCQ to VCC on the base, which makes the already-routed VFBGA67 boards compliant
  as-built. Dual-supply families (`emmc`, `ufs`) drive it as the I/O rail.
- `nand_x8` overlay: identity — `IO1–8`, `/CE`, `/RE`, `/WE`, `/WP`, `CLE`, `ALE`,
  `RY//BY` on their current positions.
- `emmc` overlay (12 signals): `DAT0–7` on the `IO1–8` positions; `CLK` on a GND-flanked
  position (position 12, today's `RY//BY`, has GND at 11 and 14); `CMD`, `RST_n`, `DS` on
  remaining control positions; 3 signal positions unused.
- `ufs` overlay (6 signals): the two differential pairs on physically adjacent IO
  positions with GND neighbors; `REF_CLK`, `RST_n` on control positions. UFS needs a
  third rail (`VCCQ2`); assign it one spare signal position in the overlay.

Exact per-position overlay tables are produced in phase 1 and validated by
`pinout.py check()` (see Tooling). The overlays live in a new `tools/families.py`.

**BGA-132/152:** the JEDEC ballout is dual x8 (~30+ signals), which cannot fit the 30-pin
contract. Suite scope is **channel 0 only** under the `nand_x8` overlay — full reads of
single-die parts, half of dual-die parts. A second-tier ~60-pin DF40 "wide" contract with
its own base variant is documented **future work**, not designed here.

## Base variants

Each XGecu adapter family has its own DIP48 pinout, so board B becomes a set of wiring
variants of one template: identical outline, DIP48 socket, DF40 receptacle, and passive
placement; only the DIP48↔DF40 copper (and supply strapping) changes per family.

- `nand_x8`: the existing `base/` board, unchanged.
- `emmc`: new variant, phase 2.
- `ufs`: none — the T76 cannot program UFS; the programmer path for UFS is out of scope.

**Gate:** no base variant is routed until that family's XGecu adapter DIP48 pinout is
verified — bench ring-out (as recorded in `docs/ringout-results.txt` for the NAND
adapter) or authoritative vendor documentation. This is a per-family gate, not a suite
blocker.

## Package data model

One Python data module per package under `packages/`, plain-dict style consistent with
`pinout.py`, importable by all checks:

```
packages/
  vfbga67.py        # retrofit of the shipped board; proves the model
  emmc_bga153.py
  emmc_bga169.py
  emcp_bga221.py
  emcp_bga254.py
  nand_bga48.py
  nand_bga63.py
  nand_bga132.py
  nand_bga152.py
  ufs_bga153.py
  ufs_bga254.py
```

Each module declares:

- `family` — `'nand_x8' | 'emmc' | 'ufs'`
- body outline (x, y, thickness) and ball pitch / array dimensions
- full ball map: ball name → grid position, **including NC/unused balls** so
  `bga_fit.py` sees the true land pattern
- signal assignment: ball → universal DF40 position via the family overlay
- ballout provenance: a citation of the exact JEDEC ballout / MO document the map was
  transcribed from (required; vendor drawings alone are not sufficient for eMCP)

## Repo layout

```
packages/                  # data modules (above)
boards/
  <package>/
    carrier/               # mirrored lands + DF40 plug        (board A role)
    chip/                  # true lands + DF40 receptacle      (board C role)
base_variants/
  emmc/                    # base template rewired for eMMC adapter pinout
tools/
  pinout.py                # universal DF40 positions (source of truth, extended)
  families.py              # per-family signal overlays
  gen_footprint.py         # new
  gen_board.py             # new
  check_interposer.py      # parameterized by package module
  bga_fit.py, check_mating.py, panelize.sh, ...   # generalized as needed
```

The shipped VFBGA67 `carrier/`, `chip/`, `base/`, `prog/` directories stay where they
are; migration under `boards/` is optional later work.

## Tooling

New scripts follow the repo's existing scripted-edit pattern (KiCad closed, run via
`make`, checks gate everything):

- **`gen_footprint.py`** — from a package module, emit the true land-pattern footprint
  and its mirrored twin, including NC lands.
- **`gen_board.py`** — emit carrier and chip board skeletons: outline from body size,
  land field placed, DF40 placed within the 0.20 mm centre rule, nets assigned from the
  family overlay, JLC 4-layer stackup and `tools/jlc-4layer.kicad_dru` applied. Output is
  a routable `.kicad_pcb` plus a minimal schematic (logical pin-map symbol like today's
  `U1`, DF40, decoupling) so ERC/board parity checks work.
- Escape routing is manual per board.

Checks generalize rather than multiply:

- `check_interposer.py` takes a package module and enforces the same rules as today:
  chipless mirrored footprint, cross outline, same-number DF40 contract, ordinary
  through-via dogbones and **no via-in-pad on carriers**; on chip boards, the Epoxy
  Filled & Capped rules (0.15–0.55 mm fillable drills, 0.05 mm minimum annular ring, via
  land no wider than the ball land, tented both faces).
- `bga_fit.py` (handedness) and `check_mating.py` run per package pair.
- `pinout.py check()` additionally validates every family overlay: bijection onto legal
  signal positions, supply-pin rules per family (VCCQ strap for `nand_x8`, distinct rails
  for `emmc`/`ufs`).
- `make check` fans out over all package modules and existing boards; the panelizer takes
  a package list so small carriers/chips share panels.

## Phasing

1. **Foundations** — universal contract + overlays in `pinout.py`/`families.py`;
   `gen_footprint.py`/`gen_board.py`; generalized checks. Proven by regenerating a
   VFBGA67 carrier skeleton and diffing its lands, DF40 placement, and nets against the
   shipped board.
2. **eMMC BGA-153** — first new package end-to-end: carrier + chip routed; eMMC base
   variant after adapter ring-out. Validates everything new.
3. **eMMC BGA-169, eMCP BGA-221/254** — carriers + chips only (family base exists).
4. **NAND BGA-48/63** — carriers + chips only (existing base).
5. **NAND BGA-132/152** — carriers + chips, channel 0 under the `nand_x8` overlay.
6. **UFS BGA-153/254** — carriers + chips only; programmer path documented out of scope.

Each phase ends with `make check` clean and DRC clean (zero unconnected items, schematic
parity) on its new boards. Fabrication is per-phase at the owner's discretion.

## Risks

- **Epoxy Filled & Capped on 4 layers** — the README's pre-order gate applies to every
  chip board in the suite; one JLCPCB confirmation covers all of them. Fallbacks per the
  README: 6-layer chip boards, or dogbone re-route.
- **XGecu adapter pinouts** — a wrong guess costs a base respin; hence the per-family
  ring-out gate before any base variant is routed.
- **eMCP ballouts** — mitigated by the required JEDEC citation in each package module.
- **UFS signal integrity** — M-PHY diff pairs across the DF40 are plausible at low gear
  but unvalidated; listed as open future work with the wide contract.

## Future work (explicitly out of scope)

- 60-pin "wide" DF40 contract + base variant for dual-channel BGA-132/152.
- UFS programmer-side story and SI validation.
- Automated escape routing.
- Migrating the shipped VFBGA67 boards under `boards/`.

## Success criteria

- `make check` validates every package module and board against the universal contract.
- Regenerated VFBGA67 skeleton matches the shipped carrier (lands, DF40 placement, nets).
- Every phase's boards pass DRC with zero unconnected items and schematic parity.
- Adding a new package of an existing family requires only a data module plus manual
  routing — no tooling changes.
