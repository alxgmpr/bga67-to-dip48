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
| `carrier/` | mirrored VFBGA67 motherboard lands + DF40 plug | 10.2 × 7.6 mm cross |
| `base/` | DIP48 socket for XGecu adapter + DF40 receptacle + passives | 30 × 90 mm |

## Courk-style carrier

Board A now follows the useful parts of Courk's original NandBug topology:

- a notched cross outline, rotated to suit this assembly;
- top-side DF40 and bottom-side mirrored VFBGA67 field exactly concentric;
- Courk's DF17 pair ordering preserved in the middle 20 contacts of the 30-pin DF40;
- one short diagonal dogbone from each used VFBGA67 land;
- ordinary 0.45 mm vias with 0.20 mm finished drills;
- no blind/buried vias, microvias, via-in-pad, fill/cap, or HDI process.

Courk's exact rotated outline is about 10.2 × 6.7 mm. This carrier retains its 10.2 mm
length and notch proportions but widens the center to 7.6 mm because the 30-pin DF40 is
larger than Courk's 20-pin DF17. The manufacturing target is a standard JLCPCB four-layer
stackup, 1.6 mm, ENIG.

The 47 unused motherboard lands remain floating. `U1` is only a logical pin map and mirrored
land interface; it is excluded from BOM/position output and has no NAND model or package
graphics.

Both PCB files are intentionally unrouted so the final copper can be placed by hand in
KiCad. The stored boards contain no tracks, vias, or copper zones.

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
chipless mirrored footprint, cross outline, Courk ordering, ordinary through-via dogbones,
and absence of via-in-pad/HDI topology.
