#!/usr/bin/env python3
"""Chirality-checked rigid fit between a BGA pad set and a reference land pattern.

A chip-replacement interposer and the motherboard it solders to are both seen
looking down at the assembly, so the ball-name -> position pattern must agree
under rotation and translation ONLY.  A reflection means the board is mirrored
and every ball lands on the wrong pad.

check_interposer.py used to assert each pad against a formula restating the
footprint's own contents, which cannot detect a mirror.  This can.

  python3 tools/bga_fit.py    run the self-test
"""
import cmath
import re
from pathlib import Path

PAD_RE = re.compile(r'\(pad\s+"([A-K]\d+)".*?\(at\s+([-0-9.]+)\s+([-0-9.]+)', re.S)


def read_footprint_pads(path):
    """ball name -> (x, y) in footprint-local mm."""
    return {
        name: (float(x), float(y))
        for name, x, y in PAD_RE.findall(Path(path).read_text())
    }


def fit(reference, candidate):
    """Best similarity transform of reference onto candidate, and of its mirror.

    Returns (proper, reflected), each (scale, angle_degrees, rms_residual_mm).
    Complex least squares: for centred point sets a and b, the single complex
    number r minimising sum|b - r*a|^2 is sum(b * conj(a)) / sum(|a|^2), and
    conjugating the source first gives the reflected solution.
    """
    keys = sorted(set(reference) & set(candidate))
    if len(keys) < 3:
        raise ValueError("need at least 3 shared pads, got %d" % len(keys))

    def centred(table):
        cx = sum(table[k][0] for k in keys) / len(keys)
        cy = sum(table[k][1] for k in keys) / len(keys)
        return [complex(table[k][0] - cx, table[k][1] - cy) for k in keys]

    target = centred(candidate)

    def solve(source):
        rotation = (sum(b * a.conjugate() for a, b in zip(source, target))
                    / sum(abs(a) ** 2 for a in source))
        residual = (sum(abs(b - rotation * a) ** 2
                        for a, b in zip(source, target)) / len(source)) ** 0.5
        return abs(rotation), cmath.phase(rotation) * 180 / cmath.pi, residual

    source = centred(reference)
    return solve(source), solve([a.conjugate() for a in source])


def assert_no_mirror(reference, candidate, label, tolerance=1e-4):
    """Fail if candidate is a reflection of reference, or does not fit at all."""
    (_, angle, proper), (_, _, reflected) = fit(reference, candidate)
    assert proper < reflected, (
        "%s is MIRRORED against its reference land pattern: proper-rotation "
        "residual %.6f mm, reflected residual %.6f mm" % (label, proper, reflected)
    )
    assert proper < tolerance, (
        "%s does not fit its reference land pattern under rotation: residual "
        "%.6f mm at %.3f deg" % (label, proper, angle)
    )
    return angle


def _self_test():
    import math
    reference = {"A1": (-2.0, -3.6), "A8": (2.8, -3.6),
                 "K1": (-2.0, 3.6), "K8": (2.8, 3.6), "E4": (-0.4, -0.4)}

    def transform(table, degrees, mirror=False, dx=100.0, dy=50.0):
        out = {}
        for name, (x, y) in table.items():
            z = complex(x, -y if mirror else y) * cmath.exp(1j * math.radians(degrees))
            out[name] = (z.real + dx, z.imag + dy)
        return out

    angle = assert_no_mirror(reference, transform(reference, 90.0), "rotated 90")
    assert abs(angle - 90.0) < 1e-6, angle
    assert_no_mirror(reference, transform(reference, 0.0), "identity")

    try:
        assert_no_mirror(reference, transform(reference, 45.0, mirror=True), "mirrored")
    except AssertionError as error:
        assert "MIRRORED" in str(error), error
    else:
        raise AssertionError("a reflected pad set was not detected")

    (_, _, proper), (_, _, reflected) = fit(reference, transform(reference, 30.0))
    assert proper < 1e-9 and reflected > 0.1, (proper, reflected)


if __name__ == "__main__":
    _self_test()
    print("bga_fit self-test OK: rotation accepted, reflection rejected")
