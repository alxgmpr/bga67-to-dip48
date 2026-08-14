#!/usr/bin/env python3
"""Generate true and mirrored BGA land-pattern footprints from a package module.

Run with KiCad's bundled Python (pcbnew required).
"""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
import pcbnew
import packages

MM = pcbnew.FromMM


def _footprint(pkg, mirrored):
    n = len(pkg.BALLS)
    suffix = '_Mirrored_Interposer' if mirrored else ''
    name = f"BGA-{n}_{pkg.NAME}{suffix}"
    fp = pcbnew.FOOTPRINT(None)
    fp.SetFPID(pcbnew.LIB_ID('', name))
    fp.SetAttributes(pcbnew.FP_SMD | pcbnew.FP_EXCLUDE_FROM_BOM
                     | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    for ball in sorted(pkg.BALLS):
        x, y = packages.ball_xy(pkg, ball)
        if mirrored:
            x = -x
        pad = pcbnew.PAD(fp)
        pad.SetNumber(ball)
        pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
        pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
        pad.SetSize(pcbnew.VECTOR2I(MM(pkg.LAND_MM), MM(pkg.LAND_MM)))
        pad.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        pad.SetLayerSet(pcbnew.PAD.SMDMask())
        fp.Add(pad)
    return name, fp


def generate(pkg, out_dir):
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for mirrored in (False, True):
        name, fp = _footprint(pkg, mirrored)
        # KiCad 10: write via the plugin API against a .pretty directory.
        io = pcbnew.PCB_IO_KICAD_SEXPR()
        io.FootprintSave(str(out_dir), fp)
        paths.append(out_dir / (name + '.kicad_mod'))
    return paths[0], paths[1]


if __name__ == '__main__':
    pkg = packages.load(sys.argv[1])
    normal, mirrored = generate(pkg, sys.argv[2])
    print(normal); print(mirrored)
