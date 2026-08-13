# bga67-to-dip48

Reusable bridge between the Google Home Mini's VFBGA67 NAND lands and a commercial XGecu
BGA-to-DIP48 socket adapter.

The architecture is intentionally asymmetric:

```text
PROGRAM                          BOOT / TEST

XGecu programmer                Google Home motherboard
       ^                                  ^
       | DIP48                            | solder balls
[ XGecu adapter ]                 [ chipless carrier A ]
[ actual NAND   ]                         |
       |                                 | DF40 service joint
       +------------------------> [ socket base B ]
                                  [ DIP48 receptacle ]
```

The actual NAND remains clamped in the XGecu adapter. That adapter/NAND assembly moves
between the programmer and board B. Board A is a permanent, chipless interposer soldered to
the Google motherboard; it has no NAND package and no sacrificial memory.

| Board | Contents | Nominal size |
|---|---|---:|
| `carrier/` | mirrored VFBGA67 motherboard lands + DF40 plug | 8.41 × 7.60 mm |
| `base/` | DIP48 socket for XGecu adapter + DF40 receptacle + passives | 27.78 × 61.38 mm |
| `chip/` | real VFBGA67 lands + DF40 receptacle, NAND soldered here | 8.41 × 7.60 mm |
| `prog/` | DF40 plug + DIP48 male pins for the XGecu T76 ZIF | 27.78 × 61.38 mm |

## Compact routed carrier

Board A follows the useful parts of Courk's original NandBug routing topology:

- the current compact 8.41 × 7.60 mm outline;
- top-side DF40 within 0.20 mm of the bottom-side mirrored VFBGA67 field centre;
- the completed carrier routing preserved as the canonical DF40 electrical order;
- one short diagonal dogbone from each used VFBGA67 land;
- ordinary 0.45 mm vias with 0.20 mm finished drills;
- no blind/buried vias, microvias, via-in-pad, fill/cap, or HDI process.

That last point holds for boards A, B and D. **Board C is the deliberate exception** — see
"Via-in-pad on board C" below.

The manufacturing target is a standard JLCPCB four-layer stackup, 1.6 mm, ENIG.

The 47 unused motherboard lands remain floating. `U1` is only a logical pin map and mirrored
land interface; it is excluded from BOM/position output and has no NAND model or package
graphics.

The carrier and the base are both routed. Base DRC reports zero unconnected items and zero
schematic parity issues; its remaining 20 warnings are all `text thickness out of range` on
silkscreen and are cosmetic.

## Via-in-pad on board C

Board C is the only board that puts vias inside BGA lands. The NAND is reflowed onto those
lands, which forces the choice:

- a soldermask-plugged via is not flat enough to print a stencil against when reballing;
- an untented via wicks solder out of the ball joint.

So board C's in-pad vias use JLCPCB's **Epoxy Filled & Capped** process: resin filled, baked,
levelled, then copper plated over to a flat surface. Via diameters must be 0.15–0.55 mm and
the vias must carry no soldermask opening on either face.

> **Pre-order gate.** JLCPCB document Epoxy Filled & Capped as the default at **6 layers and
> above** and do not list it as a standard 4-layer option. Board C is 4-layer. Confirm with
> JLCPCB that the process is available on a 4-layer order, and at what price, **before
> fabricating board C**. If it is not, the options are moving board C to 6 layers or routing
> the in-pad vias back out to dogbones.

Boards A, B and D remain free of via-in-pad and are unaffected. `tools/check_interposer.py`
still enforces the strict no-via-near-pad rule on carrier A, and enforces the fill-process
rules on board C: fillable drill range, minimum annular ring, via land no wider than the ball
land, and tenting on both faces.

## Mechanical load path

The DF40 pair normally remains mated. Routine removal happens at board B's DIP48 socket when
the complete XGecu adapter/NAND assembly moves to the programmer. The DIP48 socket and any
future standoffs/cradle must carry insertion force; it must not be reacted through the DF40,
carrier, or Google motherboard BGA lands.

## Verification

Close KiCad before scripted edits, then run:

```bash
make check
make panel
```

`tools/pinout.py` is the connector source of truth. `tools/check_interposer.py` guards the
chipless mirrored footprint, cross outline, same-number DF40 contract, ordinary through-via
dogbones, and absence of via-in-pad/HDI topology on carrier A. On board C, where via-in-pad is
intended, it instead enforces the Epoxy Filled & Capped rules: 0.15–0.55 mm fillable drills,
0.05 mm minimum annular ring, via land no wider than the ball land, and tenting on both faces.

`tools/bga_fit.py` checks BGA handedness: it fits a placed pad set against the normal land
pattern allowing rotation and translation only, and fails when the better fit is a reflection.
