#!/usr/bin/env python3
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import packages, families
import check_package

pkg = packages.load('vfbga67')
assert pkg.NAME == 'vfbga67' and pkg.FAMILY == 'nand_x8'
assert len(pkg.BALLS) == 67, len(pkg.BALLS)
assert pkg.PITCH_MM == 0.8
used = {s for s in pkg.BALLS.values() if s not in (None, 'VCC', 'GND')}
assert used == set(families.OVERLAYS['nand_x8']), used
assert check_package.check(pkg) is True
print("vfbga67 package ok")
