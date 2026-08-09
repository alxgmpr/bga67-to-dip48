# bga67-to-dip48

BGA-67 NAND flash to DIP48 adapter for an XGecu programmer, split across two boards so the
flash carrier can be swapped without rebuilding the DIP48 field.

| | Board | Contents | Size |
|---|---|---|---|
| A | `carrier/` | KIOXIA TC58NVG1S3HBAI6 (VFBGA-67) + DF40 30-pin plug + 2× 100 nF | ~12 × 14 mm |
| B | `base/` | DIP48 pin field + DF40 30-pin receptacle + pull-ups + bulk | ~63 × 20 mm |

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

- **Carrier bottom side must stay clear.** Clearance to board B. All passives go top side,
  outside the BGA outline.
- **DF40 is rated 30 mating cycles.** Keep the repeated joint at the DIP48/ZIF end, not here.
- **The 47 NC balls float.** Do not ground them.
- **Data bus order is load-bearing** — commands and addresses share the I/O pins. See
  `docs/connector-pinout.md`.

## Fab

JLCPCB, 4 layers. L2 must be a solid ground pour spanning the ball field; the connector's
checkerboard ground pinout does nothing without it. ENIG — HASL on 0.4 mm BGA pads is not
worth the trouble. No paste on the BGA footprint (chips get reballed with leaded solder).

Design rules in both projects are set to the same values; net classes `Power` and `Signal`
are defined but net assignment happens once the schematics are wired.
