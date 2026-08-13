# Connector 3D models

- `DF40TC(4.0)-30DS-0.4V(51).stp` is Hirose's official model for
  CL0684-4256-0-51, download document `0001452464S`. Its manufacturer datum
  requires the footprint offset `(-2.86, -1.69, 0)` to align its mating centre.
- `SSM-124-L-SV_DIP48.step` is a dimensionally controlled, simplified model
  of two Samtec SSM-124-L-SV socket strips on 15.24 mm centres. It is generated
  by `tools/generate_3d_models.py` from Samtec drawing
  `SSM-1XX-XXX-XX-XX-XX-XX-X-XX`, revision DG.

The SSM model intentionally simplifies the internal contact spring shape. Its
mating centres, 2.54 mm pitch, 15.24 mm row spacing, body envelope, 7.49 mm
height, and staggered SMT tail locations match the manufacturer drawing.
