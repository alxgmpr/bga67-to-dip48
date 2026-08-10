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
| Soldermask expansion | 1:1 (0) | Soldermask |

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

`tools/panelize.sh` carries the mouse-bite geometry, also from the capabilities page:

- mouse bite drill **0.5 mm** — JLC's minimum NPTH and the floor of the 0.5–0.8 mm
  recommended bite range. The previous 0.45 mm was below the NPTH minimum.
- bite spacing **0.75 mm** — 0.5 mm drill + 0.25 mm gap, inside the recommended 0.2–0.3.
- frame width **5 mm** — *"the minimum width of breakaway tab is 4 mm. For breakaway with
  mouse-bites, the minimum width is 5 mm."* The previous 3 mm frame met only the plain
  tooling-edge minimum, not the mouse-bite one.
- board spacing 2 mm, four 1.5 mm tooling holes — both at spec.

kikit treats bite `spacing` as a maximum and then divides each cut evenly, so the realised
pitch comes out tighter than requested — 0.75 mm asked for lands as low as 0.667 mm, and
tab junctions emit two bites within 0.13 mm of each other. `tools/panel_fixups.py` culls
afterwards rather than hunting for a spacing value whose rounding happens to work.

It also drops the board's arc-approximation error to 0.001 mm. kikit's `millradius`
corners are arcs; the zone filler polygonises them, and the chord sits inside the true arc
far enough to report a 0.1995 mm edge clearance against a 0.2 mm rule. That is a faceting
artifact of 0.5 µm, so the fix is the faceting — not loosening the rule or distorting the
pour.

## Known gaps

- **Same-net track spacing 0.25 mm** is a JLC limit with no KiCad DRC equivalent. Not
  checked. It matters where a track doubles back on itself; neither board does.
- **Min SMD pad 0.25 × 0.25 mm.** The DF40 land pattern is 0.2 × 0.7 mm, narrower than
  JLC's general guideline, because that is what Hirose specifies for a 0.4 mm-pitch
  connector. Left as-is deliberately; the soldermask bridge between them is 0.2 mm, twice
  JLC's 0.10 mm minimum, so the constraint that actually matters is satisfied.
