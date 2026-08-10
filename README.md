# bga67-to-dip48

BGA-67 NAND flash to DIP48 adapter for an XGecu programmer, split across two boards so the
flash carrier can be swapped without rebuilding the DIP48 field.

| | Board | Contents | Size |
|---|---|---|---|
| A | `carrier/` | KIOXIA TC58NVG1S3HBAI6 (VFBGA-67) + DF40 30-pin plug | 9.25 × 7.45 mm |
| B | `base/` | DIP48 socket + DF40 30-pin receptacle + pull-ups + bulk | ~63 × 20 mm |

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
- **Stack height is 1.5 mm and is not a free choice.** The plug is a shielded `DF40GB`, and
  that family offers 30 positions at 1.5 mm only. No DF40 family reaches 4.0 mm at 30
  positions. See `docs/connector-pinout.md`.
- **DF40 is rated 30 mating cycles.** Keep the repeated joint at the DIP48/ZIF end, not here.
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

`panel/carrier-panel.kicad_pcb` is a 4×4 mouse-bite panel, 52.9 × 45.7 mm, generated with
KiKit from the single board:

```bash
kikit panelize --layout 'grid; rows: 4; cols: 4; space: 2mm' \
  --tabs 'fixed; width: 3mm; vcount: 2; hcount: 1' \
  --cuts 'mousebites; drill: 0.45mm; spacing: 0.9mm; offset: -0.3mm; prolong: 0.5mm' \
  --framing 'frame; width: 3mm; space: 2mm; cuts: both' \
  --tooling '4hole; hoffset: 1.5mm; voffset: 1.5mm; size: 1.5mm' \
  --post 'millradius: 1mm' carrier/carrier.kicad_pcb panel/carrier-panel.kicad_pcb
```

The **negative** mouse-bite offset matters. At the default the bites sit inside the board
edge and land 0.17 mm from signal copper, below JLCPCB's 0.2 mm hole-to-track minimum; at
−0.3 mm they sit in the waste and DRC is clean. Regenerating the panel also leaves 64
co-located drills at tab junctions that need deduping — see the commit history.

Panel DRC is clean apart from silkscreen-over-copper warnings where refdes text meets the
bites, which are cosmetic. Rails give you something to hold while reflowing the BGA and
hand-soldering a 0.4 mm-pitch connector.

## State

Both schematics are drawn, wired and ERC-clean. **The carrier is finished** — placed,
routed, 0 DRC violations, 0 unconnected — and panelized. Board B has a schematic and
footprints but no layout yet.

**The TSOP48 pinout is unverified.** It comes from the JEDEC standard, not from the Kioxia
datasheet, which documents only the BGA. Ring it out against the physical XGecu adapter
before ordering board B.
