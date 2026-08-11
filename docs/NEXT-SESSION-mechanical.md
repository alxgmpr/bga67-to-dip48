# Mechanical follow-up: support the removable XGecu adapter

The NAND remains in the XGecu adapter. The adapter/NAND assembly moves between the programmer
and board B; board A is a permanent chipless interposer on the Google motherboard.

```text
[ XGecu adapter + NAND ]
           |
     DIP48 insertion force
           v
[ board B + rigid cradle ]  <-- standoffs/rails react load here
           |
     DF40 service joint
           |
[ chipless cross carrier A ]
           |
[ Google motherboard ]
```

## Fixed dimensions and constraints

| Item | Value |
|---|---:|
| carrier A | nominal 10.2 × 7.6 mm notched cross |
| original Courk cross, rotated | about 10.2 × 6.7 mm |
| board B | about 30 × 90 mm |
| DIP48 longitudinal span | 58.42 mm |
| DIP row spacing | 15.24 mm |
| DF40 mated height | 4.0 mm |

The carrier is wider than Courk's by 0.9 mm solely to clear and escape the 30-pin DF40. Do
not add a NAND package envelope: the carrier has no NAND.

## Next mechanical deliverable

- Measure the XGecu adapter body, overhang, pin length, insertion depth, and pin-1 corner.
- Reduce board B only after those measurements.
- Add four board-B mounting points and an underside cradle with supports directly beneath
  the socket rows.
- Add positive insertion stops so the SMT socket pads do not carry the full operator load.
- Keep all support loads out of the DF40 and Google motherboard lands.
- Verify the carrier cross clears nearby motherboard parts and shielding.

Any board-B outline or hole change requires routing/DRC revalidation. Any carrier change also
requires `make panel`.
