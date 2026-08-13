# Mechanical outputs

- `base-assembly.step` and `carrier-assembly.step` are direct KiCad exports of
  the two boards and their assigned component models.
- `mated-assembly.step` rotates the base -90 degrees about J1, aligns the two J1
  mating centres, and holds the PCB faces at Hirose's specified 4.0 mm mated
  height. Base pin 1 and carrier pin 1 point in the same mating direction.
- `renders/base-top.png` shows the two top-side 24-position socket strips.
- `renders/base-bottom.png` shows the centered underside DF40 receptacle.
- `renders/carrier-top.png` shows the routed carrier and DF40 plug.
- `renders/mated-assembly.png` is a close underside view of the base (green)
  mated to the carrier (orange).

Regenerate the socket model with `tools/generate_3d_models.py`, export the two
board assemblies with KiCad CLI, then run `tools/generate_mated_assembly.py`.
Both Python generators require CadQuery; the mated PNG renderer also uses VTK.
