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

- Carrier: nominal 8.41 × 7.60 mm outline, four layers, mirrored lands on B.Cu and
  30-pin DF40 plug on F.Cu.
- Shape: compact routed rectangle derived from the Courk-style escape topology.
- Escape: 0.15 mm traces and ordinary 0.45/0.20 mm through-via dogbones.
- Fabrication: standard JLCPCB four-layer process; no HDI, microvia, or blind/buried via on
  any board. Boards A, B and D additionally require no via-in-pad and no filled/capped vias.
  Board C is the exception and needs Epoxy Filled & Capped in-pad vias — see the pre-order
  gate below.
- Base: 27.78 × 61.38 mm socket board with two 1×24 SMT DIP socket strips and a 4.0 mm DF40
  receptacle.
- Connector: the routed carrier table is canonical; plug `J1.n` mates receptacle `J1.n`.
- Placement: routed carrier J1 is 0.173 mm from U1 at the cross center (within the checked
  0.20 mm escape allowance); base J1 is exactly centered on the base outline.
- DF40 plug footprint: includes all four non-electrical MT retention lands and the downloaded
  STEP model with its verified `(-3.275, -1.355, 0)` origin correction.

## Current validation status

- The carrier is routed and its PCB/schematic J1 table is the preserved source topology.
- The base PCB and schematic use that identical J1 table and are fully routed.
- Carrier outline, connector pinout, mirrored footprint, and placement checks pass.
- The base has manufacturer-dimensioned SSM-124-L-SV lands, a combined two-strip STEP model,
  and Hirose's exact DF40TC(4.0) receptacle STEP model.
- Electrical and mechanical mating checks pass, as do ERC and DRC on both projects. Base DRC
  reports zero unconnected items and zero schematic parity issues. Both boards are
  fabrication-ready.
- Carrier panel: regenerate after closing the KiCad project; the current lock prevents the
  panel script from safely replacing an open board.

Do not send fabrication files until manual routing is complete and `make check` passes. The
intended process does not require HDI. Boards A, B and D do not require via-in-pad either.

## Pre-order gate: board C via filling

Board C puts vias inside its BGA lands on purpose. The NAND is reflowed onto those lands, so
a soldermask-plugged via is not flat enough to print a stencil against, and an untented via
wicks solder out of the ball joint. Board C therefore needs JLCPCB's **Epoxy Filled & Capped**
process: resin filled, baked, levelled, copper plated over flat. Drill diameters must be
0.15–0.55 mm and the vias must have no soldermask opening on either face.

**This is unconfirmed for four layers.** JLCPCB document Epoxy Filled & Capped as the default
at 6 layers and above; their published 4-layer capabilities list only soldermask plugging,
which is the option ruled out for flatness. Board C is 4-layer.

Before ordering board C:

1. Confirm with JLCPCB that Epoxy Filled & Capped is available on a 4-layer order, and at
   what price and lead time.
2. If it is not, either move board C to a 6-layer stackup — its panel is already a separate
   file, so only board C is affected — or route the in-pad vias back out to ordinary
   dogbones as boards A, B and D do.
3. Do not order board C as a plain 4-layer job and hope. A plugged-but-not-capped via under a
   ball is the failure this whole choice exists to avoid.

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
