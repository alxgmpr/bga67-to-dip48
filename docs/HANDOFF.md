# Handoff

## Non-negotiable architecture

The actual NAND remains clamped in the commercial XGecu VFBGA67-to-DIP48 socket adapter.
That complete adapter/NAND assembly moves between the programmer and board B.

```text
XGecu programmer <--- move adapter + NAND ---> board B DIP48 socket
                                                |
                                         DF40 service joint
                                                |
                                      chipless interposer A
                                                |
                                      Google motherboard
```

Board A contains no NAND and no sacrificial memory. `U1` is a mirrored VFBGA67 motherboard
land interface used only for net naming; it is excluded from BOM/position files and has no
NAND body or 3D model.

## Current design direction

- Carrier: nominal 10.2 × 7.6 mm notched cross, four layers, mirrored lands on B.Cu and
  30-pin DF40 plug on F.Cu.
- Shape: Courk rev-3 cross rotated 90 degrees, with the center widened 0.9 mm for the larger
  DF40 connector.
- Escape: 0.15 mm traces and ordinary 0.45/0.20 mm through-via dogbones.
- Fabrication: standard JLCPCB four-layer process; no HDI, microvia, blind/buried via,
  via-in-pad, or filled/capped-via requirement.
- Base: 30 × 90 mm socket board with two 1×24 SMT DIP socket strips and a 4.0 mm DF40
  receptacle.
- Connector: Courk's ten DF17 pin pairs occupy DF40 pins 7–26; all surplus contacts are GND.
- Placement: carrier J1 and U1 are exactly concentric at the cross center; base J1 is exactly
  centered on the base outline.
- DF40 plug footprint: includes all four non-electrical MT retention lands and the downloaded
  STEP model with its verified `(-3.275, -1.355, 0)` origin correction.

## Current validation status

- Carrier and base PCBs are intentionally unrouted for manual routing. Both contain zero
  tracks, zero vias, and zero copper zones.
- Carrier outline, connector pinout, mirrored footprint, and concentric placement checks pass.
- Both schematic J1 connector blocks still need to be redrawn to match the new Courk-ordered
  PCB pinout. ERC alone cannot detect that board/schematic contract drift.
- Carrier panel: regenerate after closing the KiCad project; the current lock prevents the
  panel script from safely replacing an open board.

Do not send fabrication files until manual routing is complete and `make check` passes. The
intended process does not require HDI or via-in-pad.

## Mechanical rule

Routine cycling is the XGecu adapter entering board B's DIP48 socket. The DF40 normally stays
mated. A cradle or standoff system must support board B beside the socket strips and keep
insertion/extraction load out of the DF40, carrier, and motherboard solder lands.

## Release checks

1. Close KiCad before running file-generating scripts.
2. Run `make check`.
3. Regenerate the carrier panel with `make panel` after any carrier outline/routing change.
4. Verify mated pin-1 orientation and XGecu adapter pin-1 orientation before fabrication.

The authoritative mapping is `tools/pinout.py` and `docs/connector-pinout.md`.
