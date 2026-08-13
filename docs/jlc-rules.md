# JLCPCB 4-layer design rules

Both projects and the panel target **JLCPCB, 4-layer FR-4, 1 oz outer / 0.5 oz inner,
ENIG, 1.6 mm**. Every number below is quoted from *Rigid PCB Manufacturing Capabilities*,
jlcpcb.com, retrieved 2026-08-09.

**Do not edit rules per project.** `tools/drc-rules.py` is the only writer:

```bash
make rules
```

It patches `design_settings.rules` in all three `.kicad_pro` files and copies
`tools/jlc-4layer.kicad_dru` to `<project>.kicad_dru`. `make check` runs it with
`--check` and fails if any project has drifted.

The split is deliberate. Plain numeric limits live in `.kicad_pro` so they show up in
KiCad's Board Setup dialog. Anything needing a condition — "SMD only", "inner layers
only", "plated holes only" — lives in the `.kicad_dru`, because KiCad cannot express
those as a single global number.

## What is enforced

| Limit | Value | JLC section |
|---|---|---|
| Min track / clearance | 0.09 / 0.09 mm | Traces, multilayer 1 oz |
| Min connection width | 0.09 mm | — |
| Copper to routed edge | 0.20 mm | Outline → Routed |
| Min via hole / diameter | 0.15 / 0.25 mm | Drilling |
| Via annular ring | 0.05 mm | "diameter ≥ hole + 0.1 mm" |
| PTH annular ring | 0.15 mm | Traces (0.20 recommended) |
| Min PTH drill | 0.15 mm | Drilling, multilayer |
| Min NPTH | 0.50 mm | Drilling |
| Via hole to via hole | 0.20 mm | Drilling |
| PTH hole to PTH hole | 0.45 mm | Drilling |
| Mouse bite to mouse bite | 0.20 mm | Outline → Mouse bites Panel |
| Via hole to copper | 0.20 mm | Traces, inner layer |
| PTH hole to copper (inner) | 0.30 mm | Traces |
| Via hole to track | 0.20 mm | Traces |
| PTH to track | 0.28 mm | Traces (0.35 recommended) |
| NPTH to track | 0.20 mm | Traces |
| SMD pad to SMD pad | 0.15 mm | Traces, different nets |
| Pad to silkscreen | 0.15 mm | Legend |
| Min text height / line | 1.00 / 0.15 mm | Legend |
| Soldermask expansion | 1:1 target; 0.005 mm KiCad numerical floor | Soldermask |

The shared 0.005 mm board value is KiCad's practical near-zero setting, copied from the
carrier so mask-related DRC behaves identically in every project. It does not represent a
different fabrication capability; footprint-specific mask expansions still take precedence.

The BGA-specific 4-layer rules from JLCPCB's *BGA Design Guidelines* are also
enforced for the mirrored VFBGA67 land footprint:

| BGA limit | Value | KiCad constraint |
|---|---:|---|
| BGA pad diameter | 0.25 mm | `assertion` on both pad dimensions |
| BGA pad to different-net trace | 0.10 mm | `clearance` |
| BGA pad to via copper, including same-net vias | 0.10 mm | `physical_clearance` |

The page's 0.15 mm via drill, 0.25 mm via diameter, and 0.09 mm trace spacing
limits are already covered by the global rules above. Its 4-layer drill-to-BGA
pad minimum is zero. The footprint library identifier, rather than `U1`, scopes
the custom rules so they survive reference renumbering during panelization.

One rule is `severity warning` rather than an error: **via diameter under 0.45 mm**. That
is a cost boundary, not a manufacturability one — *"0.15 mm hole size with any size via
diameter, and 0.2 mm or 0.25 mm hole size with via diameter less than 0.45 mm, will cost
more."* The escape vias are 0.45/0.20, exactly on the free side. The warning fires if
anyone shrinks them.

## Where these differ from what the project used before

- `min_copper_edge_clearance` on `base` was **0.5 mm**, KiCad's default. JLC allows 0.2.
- `min_hole_clearance` was 0.25 mm, chosen conservatively. JLC's actual inner-layer via
  hole to copper is 0.20 mm. The carrier's escape was sized against 0.25 and so has
  margin — **do not widen the 0.20 mm drills to spend it**, the cost boundary still binds.
- `min_silk_clearance` was 0, `min_text_height` 0.8 mm, `min_text_thickness` 0.08 mm.
  All three were below JLC's legend minimums and were silently passing bad silkscreen.
- `min_via_diameter` was 0.3 mm, which is neither JLC's floor (0.25) nor the cost
  boundary (0.45). It is now the floor, with the cost boundary as a warning.

## Panel

The production panel follows JLC's
[panelization help](https://jlcpcb.com/help/article/pcb-panelization) and
[panelization guide](https://jlcpcb.com/blog/pcb-panelization):

- **5 × 5 carriers**, **85 × 72 mm** overall. This clears JLC's 70 × 70 mm
  minimum for a V-cut panel.
- **5 mm perimeter rails** and **6 mm solid internal spacer strips**. Each
  carrier is bounded by two straight horizontal and two straight vertical
  scores; the 6 mm waste strips are also removed by V-cut.
- **20 full-panel score lines**: ten vertical and ten horizontal. Parallel
  lines are never closer than 6 mm, comfortably above JLC's 2 mm minimum.
- **100 NPTH obround corner-relief slots**, 2.2 × 1.2 mm, centered where the
  carrier's four score lines meet. They reproduce the carrier's shallow corner
  ears after separation. These are real routed drill features, not graphics.
- **0.30 mm minimum copper clearance** from both the score grid and relief
  slots. The postprocessor carves 0.31 mm from saved zone fills so rounding
  cannot put copper below the rule; tracks and pads are checked separately by
  panel DRC.
- **Three asymmetric 2 mm tooling holes** and **three asymmetric global
  fiducial locations on both sides**, with 1 mm copper and 2 mm soldermask
  openings. The fiducials sit 3 mm inside the outside edge and clear the relief
  slots.

`tools/panelize.sh` is the recipe and `tools/panel_fixups.py` turns KiKit's
placement into the score grid, relief slots, fiducial positions, and copper
keepouts. `tools/check_panel.py` asserts all counts, dimensions, pitches, drill
shapes, and score extents after every rebuild.

## Known gaps

- **Get JLC CAM approval for the corner-relief method.** JLC's public guidance
  requires straight full-length score lines but does not explicitly say that a
  score may cross an obround routed slot. Select **Confirm Production File =
  Yes** and approve only a CAM preview that shows all 20 V-cuts continuing
  through the 100 relief-slot centers.
- **The guide's conservative 1 mm copper-to-V-cut recommendation is not met.**
  The panel enforces 0.30 mm, which is compatible with JLC's tighter production
  guidance and is DRC-clean, but reaching 1 mm would require rerouting the
  compact carrier.
- **The future second board is not included.** A mixed-board panel should be
  considered only after that board exists and its stackup, thickness, copper
  weight, surface finish, and assembly process match this carrier panel.
- **Same-net track spacing 0.25 mm** is a JLC limit with no KiCad DRC equivalent. Not
  checked. It matters where a track doubles back on itself; neither board does.
- **Min SMD pad 0.25 × 0.25 mm.** The DF40 land pattern is 0.2 × 0.7 mm, narrower than
  JLC's general guideline, because that is what Hirose specifies for a 0.4 mm-pitch
  connector. Left as-is deliberately; the soldermask bridge between them is 0.2 mm, twice
  JLC's 0.10 mm minimum, so the constraint that actually matters is satisfied.
