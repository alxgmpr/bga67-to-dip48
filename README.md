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

The manufacturing target is a standard JLCPCB four-layer stackup, 1.6 mm, ENIG.

The 47 unused motherboard lands remain floating. `U1` is only a logical pin map and mirrored
land interface; it is excluded from BOM/position output and has no NAND model or package
graphics.

The carrier and the base are both routed. Base DRC reports zero unconnected items and zero
schematic parity issues; its remaining 20 warnings are all `text thickness out of range` on
silkscreen and are cosmetic.

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
chipless mirrored footprint, cross outline, same-number DF40 contract, ordinary through-via dogbones,
and absence of via-in-pad/HDI topology.
