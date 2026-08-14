#!/usr/bin/env python3
"""Structural validation for packages/*.py data modules."""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import packages, families


def check(pkg):
    assert pkg.FAMILY in families.OVERLAYS, pkg.FAMILY
    assert pkg.PITCH_MM > 0 and pkg.LAND_MM > 0
    assert pkg.LAND_MM < pkg.PITCH_MM, "land must be smaller than pitch"
    assert pkg.PROVENANCE.strip(), "ballout provenance citation is required"
    rows, n_cols = pkg.GRID
    signals = set(families.OVERLAYS[pkg.FAMILY])
    rails = {'VCC', 'VCCQ', 'GND'}
    seen = set()
    for ball, signal in pkg.BALLS.items():
        x, y = packages.ball_xy(pkg, ball)     # validates grid membership
        assert ball not in seen
        seen.add(ball)
        if signal is not None and signal not in rails:
            assert signal in signals or signal.startswith('AUX_'), \
                f"{pkg.NAME} {ball}: {signal} not in {pkg.FAMILY} overlay"
    # Every overlay signal that the package uses appears exactly once.
    used = [s for s in pkg.BALLS.values() if s in signals]
    assert len(used) == len(set(used)), "duplicate signal assignment"
    return True


def main():
    names = sorted(p.stem for p in (ROOT / 'packages').glob('*.py')
                   if p.stem != '__init__')
    for name in names:
        check(packages.load(name))
        print(f"package {name} ok")


if __name__ == '__main__':
    main()
