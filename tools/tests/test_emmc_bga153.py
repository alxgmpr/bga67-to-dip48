#!/usr/bin/env python3
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
import packages, families, check_package

pkg = packages.load('emmc_bga153')
assert pkg.FAMILY == 'emmc'
assert len(pkg.BALLS) == 153, len(pkg.BALLS)
assert pkg.PITCH_MM == 0.5
assert pkg.BODY_MM in ((11.5, 13.0), (13.0, 11.5)), pkg.BODY_MM
used = {s for s in pkg.BALLS.values() if s and not s.startswith('AUX_')
        and s not in ('VCC', 'VCCQ', 'GND')}
assert used == set(families.OVERLAYS['emmc']), used ^ set(families.OVERLAYS['emmc'])
assert 'AUX_VDDI' in set(pkg.BALLS.values()), "VDDi must be mapped for its local cap"
assert 'JESD84' in pkg.PROVENANCE or 'JEDEC' in pkg.PROVENANCE
assert check_package.check(pkg) is True
print("emmc_bga153 package ok")
