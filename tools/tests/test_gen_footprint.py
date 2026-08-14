#!/usr/bin/env python3
"""Regression: generated VFBGA67 footprint matches the shipped one.

Run with $KICAD_PY (needs pcbnew).
"""
import sys, pathlib, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
import pcbnew
import packages, gen_footprint
from bga_fit import read_footprint_pads   # existing: path -> {name: (x, y)} mm

pkg = packages.load('vfbga67')
out = pathlib.Path(tempfile.mkdtemp())
normal, mirrored = gen_footprint.generate(pkg, out)

shipped = read_footprint_pads(str(
    ROOT / 'carrier/lib/carrier.pretty/BGA-67_6.5x8.0mm_Layout8x10_P0.8mm.kicad_mod'))
ours = read_footprint_pads(str(normal))
assert set(ours) == set(shipped), (set(ours) ^ set(shipped))
# Same relative geometry: compare after removing each set's centroid.
def centred(pads):
    cx = sum(x for x, y in pads.values()) / len(pads)
    cy = sum(y for x, y in pads.values()) / len(pads)
    return {n: (round(x - cx, 3), round(y - cy, 3)) for n, (x, y) in pads.items()}
assert centred(ours) == centred(shipped)

mirror = read_footprint_pads(str(mirrored))
cn, cm = centred(ours), centred(mirror)
assert all(cm[n] == (-cn[n][0], cn[n][1]) for n in cn)
print("gen_footprint vfbga67 regression ok")
