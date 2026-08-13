# Chip carrier and host adapter implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build board C (`chip/`), the carrier the NAND is soldered to permanently, and board D (`prog/`), the adapter that carries it into the XGecu T76, so reprogramming is an unplug instead of a reflow.

**Architecture:** Three roles over one unchanged 30-pin interface — target adapter (`carrier/`), device carrier (`chip/`), host adapter (`prog/`). Board C is carrier A's outline with a real BGA on F.Cu and a DF40 receptacle on B.Cu. Board D is base B's outline and net map with both connectors moved to the opposite face. Verification is by checker script, not by eye: each board's checks are written failing, then the board is built until they pass.

**Tech Stack:** KiCad 10.0.5, pcbnew Python API, `kicad-cli`, kikit, plain Python 3 stdlib. No test framework — the repo's checkers are `tools/check_*.py` run by `make check`.

## Global Constraints

- **Every board is 4 layer, 1.6 mm, ENIG, JLCPCB standard process.** A shared panel forces one stackup; this is not a preference.
- **No HDI, microvia, blind/buried via, via-in-pad, or filled/capped via on any board.** Ordinary 0.45 mm / 0.20 mm through-via dogbones, 0.15 mm tracks.
- **`tools/pinout.py` must not change.** One 30-pin table serves all four boards. A pinout change is atomic across carrier, base, chip, prog, `docs/connector-pinout.md`, and the checkers.
- **Close KiCad before running any script that writes a board file.** KiCad holds the project in memory and overwrites on save. `panelize.sh` already guards on `~*.lck`; scripts here do not.
- **New project directory names are exactly `chip` and `prog`.** `tools/check_mating.py:schematic_pin_map` derives paths as `ROOT/<project>/<project>.kicad_sch`.
- **Do not remove these strings from the docs:** `chipless interposer`, `NAND remains in the XGecu adapter`, `mirrored VFBGA67`. `tools/check_interposer.py` asserts their presence. Do not introduce `ours carries a desoldered chip`, `carrier — with the flash on it`, or `U1 (flash)`; the same checker asserts their absence.
- **Reference spec:** `docs/superpowers/specs/2026-08-12-chip-carrier-and-host-adapter-design.md`.

## Who does what

Tasks 1, 2, 3, 5, 8 and 10 are fully scriptable and an agent can complete them.

Tasks 4, 6, 7 and 9 contain **manual KiCad work** — drawing a schematic and routing a BGA escape. No agent can do that. Those tasks are structured so the agent writes the failing checker and the scaffolding, then hands off; the human works in KiCad until `make check` goes green. Each such step is marked **[MANUAL]**.

## File structure

| File | Responsibility | Task |
|---|---|---|
| `tools/bga_fit.py` | new — chirality-checked rigid fit between a pad set and a reference land pattern | 1 |
| `tools/check_interposer.py` | modify — use the fit instead of a self-referential assert | 2 |
| `README.md`, `docs/HANDOFF.md`, `docs/connector-pinout.md` | modify — correct stale base B status, add the three-role contract | 3 |
| `chip/` | new project — board C | 4, 5, 6 |
| `tools/build_chip.py` | new — outline, placement and net assignment for board C | 5 |
| `tools/check_mating.py` | modify — netlist checks for chip and prog | 4, 7 |
| `prog/` | new project — board D | 7, 8, 9 |
| `prog/lib/prog.pretty/DIP-48_Pins_THT_W15.24mm_P2.54mm.kicad_mod` | new — combined 48-pin male footprint | 8 |
| `tools/build_prog.py` | new — outline, placement and net assignment for board D | 8 |
| `tools/drc-rules.py`, `Makefile` | modify — register the two new projects | 4, 7 |
| `tools/panelize.sh` | modify — carrier-only panel becomes a four-board system panel | 10 |

---

### Task 1: Chirality-checked rigid fit

The existing check in `tools/check_interposer.py:130-145` asserts each ball against `expected_x = -(column - 4.5) * 0.8` and `expected_y = ROW_Y_MM[row]`, which restates the footprint's own contents. It cannot detect a mirror. This module can.

A chip-replacement interposer and the motherboard it solders to are both seen looking down at the assembly, so the pad-name to position pattern must agree under **rotation and translation only**. A reflection means every ball lands on the wrong pad.

**Files:**
- Create: `tools/bga_fit.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `read_footprint_pads(path) -> dict[str, tuple[float, float]]`; `fit(reference, candidate) -> ((scale, angle_deg, residual_mm), (scale, angle_deg, residual_mm))` returning proper then reflected; `assert_no_mirror(reference, candidate, label, tolerance=1e-4) -> float` returning the fitted angle in degrees.

- [ ] **Step 1: Write the module with its self-test**

```python
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
```

- [ ] **Step 2: Run the self-test**

Run: `python3 tools/bga_fit.py`
Expected: `bga_fit self-test OK: rotation accepted, reflection rejected`

- [ ] **Step 3: Confirm it agrees with the real carrier board**

This reproduces the measurement recorded in the spec. It is a one-off sanity run, not a committed file.

```bash
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python - <<'EOF' 2>&1 | grep -v Warning
import sys; sys.path.insert(0, "tools")
import pcbnew
from bga_fit import read_footprint_pads, fit
reference = read_footprint_pads(
    "carrier/lib/carrier.pretty/BGA-67_6.5x8.0mm_Layout8x10_P0.8mm.kicad_mod")
board = pcbnew.LoadBoard("carrier/carrier.kicad_pcb")
u1 = board.FindFootprintByReference("U1")
candidate = {str(p.GetNumber()): (pcbnew.ToMM(p.GetPosition().x),
                                  pcbnew.ToMM(p.GetPosition().y)) for p in u1.Pads()}
print("proper   ", fit(reference, candidate)[0])
print("reflected", fit(reference, candidate)[1])
EOF
```

Expected: proper residual `0.0` at angle `90.0`, reflected residual about `2.7447`.

- [ ] **Step 4: Commit**

```bash
git add tools/bga_fit.py
git commit -m "Add chirality-checked BGA rigid fit

The interposer position assertion in check_interposer.py restates the
footprint's own contents and cannot detect a mirror. This fits a pad set
against its reference land pattern allowing rotation and translation only,
and fails loudly when the better fit is a reflection."
```

---

### Task 2: Use the fit in `check_interposer.py`

**Files:**
- Modify: `tools/check_interposer.py` — replace the two pad-position loops, drop the now-unused `ROW_Y_MM` table

**Interfaces:**
- Consumes: `bga_fit.read_footprint_pads`, `bga_fit.assert_no_mirror` from Task 1.
- Produces: nothing new. `check()` keeps its signature and `__main__` behaviour.

- [ ] **Step 1: Add the import and a reference-pattern constant**

Next to the existing `from pinout import DF40`, add:

```python
from bga_fit import assert_no_mirror, read_footprint_pads
```

Next to the existing `FOOTPRINT` constant, add:

```python
NORMAL_FOOTPRINT = (
    ROOT
    / "carrier"
    / "lib"
    / "carrier.pretty"
    / "BGA-67_6.5x8.0mm_Layout8x10_P0.8mm.kicad_mod"
)
```

- [ ] **Step 2: Replace the board-level pad loop**

Delete this block:

```python
    for pad in interface.Pads():
        ball = str(pad.GetNumber())
        row, column = ball[0], int(ball[1:])
        position = pad.GetFPRelativePosition()
        expected_x = -(column - 4.5) * 0.8
        expected_y = ROW_Y_MM[row]
        assert abs(mm(position.x) - expected_x) < 1e-6, (
            f"ball {ball}: x={mm(position.x):.3f}, expected mirrored x={expected_x:.3f}"
        )
        assert abs(mm(position.y) - expected_y) < 1e-6, (
            f"ball {ball}: y={mm(position.y):.3f}, expected y={expected_y:.3f}"
        )
```

with:

```python
    # Carrier A's B.Cu pads and the motherboard's lands are both seen looking
    # down at the assembly, so the pattern must agree under rotation only.  A
    # reflection here would put every ball on the wrong land.
    reference = read_footprint_pads(NORMAL_FOOTPRINT)
    placed = {
        str(pad.GetNumber()): (mm(pad.GetPosition().x), mm(pad.GetPosition().y))
        for pad in interface.Pads()
    }
    assert len(placed) == 67, f"U1 has {len(placed)} pads, expected 67"
    assert_no_mirror(reference, placed, "carrier U1")
```

- [ ] **Step 3: Replace the library-level pad loop**

Delete this block:

```python
    for pad in library_interface.Pads():
        ball = str(pad.GetNumber())
        row, column = ball[0], int(ball[1:])
        position = pad.GetFPRelativePosition()
        assert abs(mm(position.x) - (-(column - 4.5) * 0.8)) < 1e-6
        assert abs(mm(position.y) - ROW_Y_MM[row]) < 1e-6
```

with:

```python
    # The library footprint's local coordinates are the normal pattern rotated
    # 180 degrees, not mirrored; the physical mirror comes from placing it on
    # B.Cu.  Either way the composed result must not be a reflection.
    library_pads = {
        str(pad.GetNumber()): (mm(pad.GetFPRelativePosition().x),
                               mm(pad.GetFPRelativePosition().y))
        for pad in library_interface.Pads()
    }
    assert len(library_pads) == 67, f"library footprint has {len(library_pads)} pads"
    assert_no_mirror(reference, library_pads, "Mirrored_Interposer library footprint")
```

- [ ] **Step 4: Delete the now-unused `ROW_Y_MM` table**

Remove the `ROW_Y_MM = {...}` dict near the top of the file. Confirm nothing else references it:

Run: `grep -n ROW_Y_MM tools/check_interposer.py`
Expected: no output.

- [ ] **Step 5: Run the checker**

Run: `make check`
Expected: `mating netlist OK`, `interposer geometry OK`, then `carrier`/`base` ERC and DRC all `clean`.

- [ ] **Step 6: Prove the new check can actually fail**

Temporarily reflect the reference inside `check()` and confirm the assertion fires. Do not commit this edit.

Two traps here. `make check` runs `check_interposer.py 2>/dev/null`, so an `AssertionError` message is discarded — run the script **directly** instead. And `git checkout` would restore the last commit, which at this point is the state *before* Step 2, destroying this task's work — restore from a copy instead.

```bash
cp tools/check_interposer.py /tmp/ci-backup.py
python3 - <<'EOF'
import pathlib
p = pathlib.Path("tools/check_interposer.py")
t = p.read_text()
new = t.replace('assert_no_mirror(reference, placed, "carrier U1")',
    'assert_no_mirror({k: (x, -y) for k, (x, y) in reference.items()}, placed, "carrier U1")')
assert new != t, "replacement target not found"
p.write_text(new)
EOF
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python \
  tools/check_interposer.py 2>&1 | grep -iE 'MIRRORED|AssertionError'
cp /tmp/ci-backup.py tools/check_interposer.py
```

Expected:

```
AssertionError: carrier U1 is MIRRORED against its reference land pattern: proper-rotation residual 2.744750 mm, reflected residual 0.000000 mm
```

If grep prints nothing, the replacement in Step 2 did not take effect.

- [ ] **Step 7: Commit**

```bash
git add tools/check_interposer.py
git commit -m "Check interposer handedness instead of restating the footprint

The old assertion recomputed the footprint's own pad formula, so a mirrored
board would have passed. Fit against the normal land pattern instead and
reject a reflected best fit."
```

---

### Task 3: Correct the stale documentation and record the three-role contract

`README.md` and `docs/HANDOFF.md` both state that base B has 34 unconnected items and must not be fabricated. Measured DRC on `base/base.kicad_pcb` is 0 unconnected items, 0 schematic parity issues, and 20 warnings, all `text thickness out of range`.

**Files:**
- Modify: `README.md`
- Modify: `docs/HANDOFF.md`
- Modify: `docs/connector-pinout.md`
- Modify: `carrier/lib/carrier.pretty/BGA-67_6.5x8.0mm_Layout8x10_P0.8mm_Mirrored_Interposer.kicad_mod`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing. Documentation only.

- [ ] **Step 1: Confirm the measurement before writing it down**

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc --refill-zones \
  -o /tmp/base-drc.json --format json base/base.kicad_pcb 2>&1 | tail -2
python3 -c "
import json; d=json.load(open('/tmp/base-drc.json'))
print('unconnected', len(d.get('unconnected_items',[])))
print('parity     ', len(d.get('schematic_parity',[])))
from collections import Counter
print(Counter(v.get('severity') for v in d.get('violations',[])))"
```

Expected: `unconnected 0`, `parity 0`, `Counter({'warning': 20})`.

- [ ] **Step 2: Fix `README.md`**

Replace this paragraph:

```
The carrier is routed. The base still needs its signal reroute after correcting the former
double-mirrored connector table; do not fabricate it until DRC reports zero unconnected
items.
```

with:

```
The carrier and the base are both routed. Base DRC reports zero unconnected items and zero
schematic parity issues; its remaining 20 warnings are all `text thickness out of range` on
silkscreen and are cosmetic.
```

Add two rows to the board table:

```
| `chip/` | real VFBGA67 lands + DF40 receptacle, NAND soldered here | 8.41 × 7.60 mm |
| `prog/` | DF40 plug + DIP48 male pins for the XGecu T76 ZIF | 27.78 × 61.38 mm |
```

- [ ] **Step 3: Fix `docs/HANDOFF.md`**

Replace the two stale bullets under "Current validation status":

```
- The base PCB and schematic now use that identical J1 table. Signal routing on the base is
  intentionally incomplete after removing routes that terminated at the old permutation.
```
```
- Electrical and mechanical mating checks pass, as do ERC and carrier DRC. Base DRC has no
  geometry/clearance violations after refilling zones, but reports 34 unconnected items; the
  base is therefore not fabrication-ready.
```

with:

```
- The base PCB and schematic use that identical J1 table and are fully routed.
```
```
- Electrical and mechanical mating checks pass, as do ERC and DRC on both projects. Base DRC
  reports zero unconnected items and zero schematic parity issues. Both boards are
  fabrication-ready.
```

- [ ] **Step 4: Add the three-role contract to `docs/connector-pinout.md`**

Insert immediately after the existing "Mezzanine connector contract" intro paragraph:

```markdown
## Three roles, one interface

The DF40 30-position same-number contract is the invariant of the whole system. Three board
roles plug into it:

| Role | Board | Specific to |
|---|---|---|
| Target adapter | `carrier/` | the footprint being tapped |
| Device carrier | `chip/` | the NAND package |
| Host adapter | `base/`, `prog/` | the programmer or clamp adapter |

A new target, package, or programmer means one new board in one role, not a new system. The
electrical side is sized for this NAND specifically — 30 positions carrying 15 signals plus
power — so this is a documented pattern, not a general-purpose fixture.
```

- [ ] **Step 5: Comment the misleading footprint name**

The footprint's local pad coordinates are the normal pattern with **both** coordinates negated — a 180 degree rotation, not a mirror. `A2` at `(-2.0, -3.6)` becomes `(+2.0, +3.6)`. Add to the footprint's existing descriptive text near `Chipless mirrored VFBGA-67 land interface`:

```
Local pad coordinates are the normal land pattern rotated 180 degrees, not mirrored.
The physical mirror comes from placing this footprint on B.Cu. Verified by
tools/bga_fit.py: the composed result is a proper rotation of the motherboard pattern.
```

Do not rename the footprint. `tools/check_interposer.py` asserts `"Mirrored" in footprint_name`, and renaming would churn both boards and the panel.

- [ ] **Step 6: Verify the documentation assertions still hold**

`tools/check_interposer.py` asserts that `chipless interposer`, `NAND remains in the XGecu adapter` and `mirrored VFBGA67` are all still present across the four doc files, and that three obsolete phrases are absent.

Run: `make check`
Expected: all green, including `interposer geometry OK`.

- [ ] **Step 7: Commit**

```bash
git add README.md docs/HANDOFF.md docs/connector-pinout.md \
  carrier/lib/carrier.pretty/BGA-67_6.5x8.0mm_Layout8x10_P0.8mm_Mirrored_Interposer.kicad_mod
git commit -m "Correct base board status and document the three-role contract

Base B is routed: DRC reports 0 unconnected items and 0 parity issues. README
and HANDOFF both claimed 34 unconnected and 'do not fabricate'. Also records
that the Mirrored_Interposer footprint is rotated 180 degrees rather than
mirrored, which is what bga_fit.py verifies."
```

---

### Task 4: Failing checks for board C, and project registration

Write the checks before the board exists. They must fail for the right reason.

**Files:**
- Modify: `tools/check_mating.py` — add chip to the netlist contract
- Modify: `tools/drc-rules.py:PROJECTS` — add `chip/chip.kicad_pro`
- Modify: `Makefile` — add `chip` to the ERC/DRC loop
- Create: `chip/` project **[MANUAL]**

**Interfaces:**
- Consumes: `schematic_pin_map(project, reference)`, `BGA67`, `DF40` — all already in `tools/check_mating.py`.
- Produces: a `chip` project whose `U1` ball-to-net map equals carrier A's and whose `J1` equals the canonical `DF40` table.

- [ ] **Step 1: Add the chip assertions to `check_mating.py`**

Inside `check()`, immediately after the existing `assert carrier_j1 == base_j1, ...` line, add:

```python
    # Board C carries the real NAND.  Its ball -> net map must be identical to
    # carrier A's, and its J1 must be the same canonical table, which together
    # mean the chip on board C sees exactly what the target motherboard would
    # have driven it with.
    chip_j1 = schematic_pin_map("chip", "J1")
    chip_u1 = schematic_pin_map("chip", "U1")
    assert chip_j1 == expected_df40, ("chip J1", chip_j1)
    carrier_u1_map = schematic_pin_map("carrier", "U1")
    assert chip_u1 == carrier_u1_map, (
        "chip U1 and carrier U1 disagree on ball -> net; the chip would be "
        "driven differently than the motherboard drives it"
    )
```

The existing `carrier_u1 = schematic_pin_map("carrier", "U1")` line further down stays; leave it alone rather than reordering the function.

- [ ] **Step 2: Run it and confirm the right failure**

Run: `python3 tools/check_mating.py`
Expected: a `subprocess.CalledProcessError` or a `FileNotFoundError` naming `chip/chip.kicad_sch`. This is correct — the project does not exist yet. It must **not** pass.

- [ ] **Step 3: Create the project skeleton**

```bash
mkdir -p chip/lib
cp carrier/carrier.kicad_pro chip/chip.kicad_pro
cp carrier/carrier.kicad_sch chip/chip.kicad_sch
cp carrier/carrier.kicad_pcb chip/chip.kicad_pcb
cp carrier/sym-lib-table chip/sym-lib-table
cat > chip/fp-lib-table <<'EOF'
(fp_lib_table
  (version 7)

  (lib (name "carrier") (type "KiCad") (uri "${KIPRJMOD}/../carrier/lib/carrier.pretty") (options "") (descr ""))

  (lib (name "Connector_Hirose_DF40") (type "KiCad") (uri "${KIPRJMOD}/../carrier/lib/Connector_Hirose_DF40.pretty") (options "") (descr ""))
)
EOF
sed -i '' 's|${KIPRJMOD}/lib/carrier.kicad_sym|${KIPRJMOD}/../carrier/lib/carrier.kicad_sym|' chip/sym-lib-table
```

Board C reuses carrier's libraries rather than copying them, matching how `base/fp-lib-table` already reaches across with `${KIPRJMOD}/../carrier/lib/...`. Both symbols it needs — `TC58NVG1S3HBAI6` and `DF40TC_4.0_-30DS-0.4V_51_` — are already in `carrier/lib/carrier.kicad_sym`.

- [ ] **Step 4: [MANUAL] Edit `chip/chip.kicad_sch` in Eeschema**

Open `chip/chip.kicad_pro` in KiCad and make exactly these changes:

1. `U1` — keep the `TC58NVG1S3HBAI6` symbol and every net label untouched. Set its Value to `TC58NVG1S3HBAI6` (carrier A overrides this to `HOME_VFBGA67_INTERFACE`; board C carries a real chip). Set its Footprint to `carrier:BGA-67_6.5x8.0mm_Layout8x10_P0.8mm` — the **non-mirrored** one.
2. `J1` — replace the `DF40TC-30DP-0.4V_51_` plug symbol with `DF40TC_4.0_-30DS-0.4V_51_`. Footprint `Connector_Hirose_DF40:HIROSE_DF40TC_4.0_-30DS-0.4V_51_`. Every pin keeps the net it had: pin `n` on the receptacle carries the same net as pin `n` on the plug. **Do not re-permute the table.** The face-to-face mirror lives in the footprint geometry, which `check_interposer.py` already verifies.
3. Add `C1` = 100 nF and `C2` = 1 µF, both `Device:C`, footprint `Capacitor_SMD:C_0402_1005Metric`, each wired VCC to GND.
4. Annotate, then run ERC to zero errors.
5. **Open Pcbnew and run Tools > Update PCB from Schematic (F8), accepting footprint changes.** `chip/chip.kicad_pcb` was copied from the carrier, so until this runs it still carries the *mirrored* BGA footprint and the DF40 *plug*. `tools/build_chip.py` in Task 5 flips whatever footprints it finds; if it runs first it will flip the wrong ones and Task 6's `"Mirrored" not in name` assertion will fail. `U1` and `J1` keep their positions through the update; `C1` and `C2` arrive unplaced and get positioned in Task 5 Step 3.

- [ ] **Step 5: Register the project with the tooling**

In `tools/drc-rules.py`, add to `PROJECTS`, after the `base` entry:

```python
    (ROOT / 'chip' / 'chip.kicad_pro', True),
```

In the `Makefile`, change the check loop from:

```make
	@check_result=0; for p in carrier base; do \
```

to:

```make
	@check_result=0; for p in carrier base chip; do \
```

- [ ] **Step 6: Push the rule set and confirm the netlist contract**

```bash
./tools/drc-rules.py
python3 tools/check_mating.py
```

Expected: `mating netlist OK: BGA67 -> J1 same-number pair -> DIP48`. If `chip U1 and carrier U1 disagree` fires, a net label was changed in Step 4 — revert it, do not adjust the checker.

- [ ] **Step 7: Commit**

```bash
git add chip/chip.kicad_pro chip/chip.kicad_sch chip/sym-lib-table chip/fp-lib-table \
  chip/chip.kicad_dru tools/check_mating.py tools/drc-rules.py Makefile
git commit -m "Add chip project schematic and its netlist contract

Board C carries the real NAND. Its U1 ball-to-net map is asserted identical
to carrier A's, so the chip sees what the motherboard would have driven."
```

---

### Task 5: Board C outline, placement and nets

Scripted, following the house pattern of `tools/rebuild_courk_interposer.py`: set geometry and nets, leave a clean ratsnest for manual routing.

**Files:**
- Create: `tools/build_chip.py`
- Modify: `chip/chip.kicad_pcb` (as script output)

**Interfaces:**
- Consumes: `pinout.DF40`; `board_net_name(logical_name)` — copy the three-line helper from `tools/rebuild_courk_interposer.py:20-23` rather than importing it, since that module runs a full rebuild on import-time constants.
- Produces: a `chip/chip.kicad_pcb` with an 8.41 x 7.60 mm rectangular outline, `U1` on F.Cu, `J1` on B.Cu, all nets assigned, zero tracks.

- [ ] **Step 1: Write the build script**

```python
#!/usr/bin/env python3
"""Set up board C's geometry and nets, leaving routing to the PCB editor.

Board C is the device carrier: the real NAND on F.Cu, the DF40 receptacle on
B.Cu.  It keeps carrier A's 8.41 x 7.60 mm outline so the two tile on one
panel and occupy the same footprint on the target board.

Close KiCad before running this.
"""
from pathlib import Path

import pcbnew

from pinout import DF40

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "chip" / "chip.kicad_pcb"
MM = pcbnew.FromMM
WIDTH_MM = 8.41
HEIGHT_MM = 7.60


def board_net_name(logical_name):
    if logical_name in ("GND", "VCC"):
        return logical_name
    return "/" + logical_name.replace("/", "{slash}")


def strip_routing(board):
    for track in list(board.GetTracks()):
        board.Remove(track)


def replace_outline(board, centre):
    for drawing in list(board.GetDrawings()):
        if drawing.GetLayer() == pcbnew.Edge_Cuts:
            board.Remove(drawing)
    cx, cy = pcbnew.ToMM(centre.x), pcbnew.ToMM(centre.y)
    half_w, half_h = WIDTH_MM / 2, HEIGHT_MM / 2
    corners = [(cx - half_w, cy - half_h), (cx + half_w, cy - half_h),
               (cx + half_w, cy + half_h), (cx - half_w, cy + half_h)]
    for start, end in zip(corners, corners[1:] + corners[:1]):
        edge = pcbnew.PCB_SHAPE(board)
        edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
        edge.SetLayer(pcbnew.Edge_Cuts)
        edge.SetWidth(MM(0.05))
        edge.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
        edge.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
        board.Add(edge)


def place(board):
    interface = board.FindFootprintByReference("U1")
    connector = board.FindFootprintByReference("J1")

    if interface.GetLayer() != pcbnew.F_Cu:
        interface.Flip(interface.GetPosition(), False)
    if connector.GetLayer() != pcbnew.B_Cu:
        connector.Flip(connector.GetPosition(), False)

    # Concentric, exactly.  Board C has no escape-offset allowance: unlike the
    # carrier it does not have to dodge a pre-existing routed topology.
    connector.SetPosition(interface.GetPosition())

    nets = board.GetNetsByName()
    for pad in connector.Pads():
        number = str(pad.GetNumber())
        if number.isdigit():
            pad.SetNet(nets[board_net_name(DF40[int(number)])])
    return interface.GetPosition()


def main():
    board = pcbnew.LoadBoard(str(BOARD))
    strip_routing(board)
    centre = place(board)
    replace_outline(board, centre)
    board.Save(str(BOARD))
    edges = board.GetBoardEdgesBoundingBox()
    print("chip outline %.2f x %.2f mm"
          % (pcbnew.ToMM(edges.GetWidth()), pcbnew.ToMM(edges.GetHeight())))
    print("U1 on %s, J1 on %s"
          % (board.GetLayerName(board.FindFootprintByReference("U1").GetLayer()),
             board.GetLayerName(board.FindFootprintByReference("J1").GetLayer())))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run it**

Close KiCad first.

Run: `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python tools/build_chip.py 2>/dev/null`

Expected:
```
chip outline 8.42 x 7.61 mm
U1 on F.Cu, J1 on B.Cu
```

The 0.01 mm overshoot on each axis is the 0.05 mm Edge.Cuts stroke width, the same allowance `check_interposer.py` already makes for the carrier.

- [ ] **Step 3: [MANUAL] Place the decoupling capacitors and the silkscreen**

Open `chip/chip.kicad_pcb`. Put `C1` and `C2` on B.Cu in the strips flanking the receptacle body, clear of the outer 0.5 mm of both long edges so tweezers can get under the board. The receptacle occupies roughly the middle 4 mm of the 7.60 mm dimension, leaving about 1.8 mm per strip; an 0402 is 1.0 x 0.5 mm.

Add a pin-1 marker on **both** faces — F.SilkS next to ball A1 and B.SilkS next to receptacle pin 1 — plus the board name. Board C is the part that gets handled every cycle and it is an 8.4 mm square with no other orientation cue. Keep silk text at or above the 1.0 mm height and 0.15 mm line width `tools/drc-rules.py` enforces, so board C does not inherit base B's text-thickness warnings.

- [ ] **Step 4: Confirm nets landed and nothing is routed yet**

```bash
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python - <<'EOF' 2>/dev/null
import sys; sys.path.insert(0, "tools")
import pcbnew
from pinout import DF40
b = pcbnew.LoadBoard("chip/chip.kicad_pcb")
j1 = b.FindFootprintByReference("J1")
actual = {int(str(p.GetNumber())): str(p.GetNetname())
          for p in j1.Pads() if str(p.GetNumber()).isdigit()}
expected = {n: (v if v in ("GND", "VCC") else "/" + v.replace("/", "{slash}"))
            for n, v in DF40.items()}
print("J1 nets match:", actual == expected)
print("tracks:", len([t for t in b.GetTracks()]))
EOF
```

Expected: `J1 nets match: True`, `tracks: 0`.

- [ ] **Step 5: Commit**

```bash
git add tools/build_chip.py chip/chip.kicad_pcb
git commit -m "Add board C geometry and net assignment

8.41 x 7.60 mm to match carrier A so the two tile on one panel. Real BGA on
F.Cu, DF40 receptacle on B.Cu, concentric. Routing left to the PCB editor."
```

---

### Task 6: Route board C

**Files:**
- Modify: `chip/chip.kicad_pcb` **[MANUAL]**
- Modify: `tools/check_interposer.py` — add board C geometry checks

**Interfaces:**
- Consumes: `bga_fit.assert_no_mirror`, `bga_fit.read_footprint_pads`.
- Produces: a DRC-clean, fully routed board C.

- [ ] **Step 1: Write the board C geometry check first**

Add to `tools/check_interposer.py`, as a new function called from `check()`:

```python
def check_chip():
    """Board C: real chip on F.Cu, receptacle on B.Cu, no mirror anywhere."""
    board = pcbnew.LoadBoard(str(ROOT / "chip" / "chip.kicad_pcb"))
    interface = board.FindFootprintByReference("U1")
    connector = board.FindFootprintByReference("J1")

    assert interface.GetLayer() == pcbnew.F_Cu, "board C's NAND must be top-side"
    assert connector.GetLayer() == pcbnew.B_Cu, "board C's receptacle must be bottom-side"

    name = str(interface.GetFPID().GetLibItemName())
    assert "Mirrored" not in name, (
        f"board C must use the normal land pattern, got {name}"
    )

    # The netlist check cannot catch a plug left on board C: plug and receptacle
    # share pin numbering by design, so a verbatim copy of the carrier passes it.
    # Only the footprint identity distinguishes them.
    connector_name = str(connector.GetFPID().GetLibItemName())
    assert "30DS" in connector_name, (
        f"board C needs the DF40 receptacle (30DS), got {connector_name}"
    )
    assert not {"MT1", "MT2", "MT3", "MT4"} & {
        str(pad.GetNumber()) for pad in connector.Pads()
    }, "board C's J1 has the plug's MT retention lands; it is still a plug"

    reference = read_footprint_pads(NORMAL_FOOTPRINT)
    placed = {
        str(pad.GetNumber()): (mm(pad.GetPosition().x), mm(pad.GetPosition().y))
        for pad in interface.Pads()
    }
    assert len(placed) == 67, f"board C U1 has {len(placed)} pads, expected 67"
    assert_no_mirror(reference, placed, "chip U1")

    edge_box = board.GetBoardEdgesBoundingBox()
    assert abs(mm(edge_box.GetWidth()) - 8.42) < 0.02, mm(edge_box.GetWidth())
    assert abs(mm(edge_box.GetHeight()) - 7.61) < 0.02, mm(edge_box.GetHeight())

    for via in [t for t in board.GetTracks() if t.GetClass() == "PCB_VIA"]:
        assert via.GetViaType() == pcbnew.VIATYPE_THROUGH, (
            f"{via.GetNetname()} uses a non-through via"
        )
        assert mm(via.GetDrillValue()) >= 0.20 - 1e-6, mm(via.GetDrillValue())
        for pad in interface.Pads():
            separation = (
                (mm(via.GetPosition().x - pad.GetPosition().x) ** 2)
                + (mm(via.GetPosition().y - pad.GetPosition().y) ** 2)
            ) ** 0.5
            assert separation >= 0.35, (
                f"{via.GetNetname()} via is in or too near U1 pad "
                f"{pad.GetNumber()} ({separation:.3f} mm)"
            )
```

Call it from the end of `check()`:

```python
    check_chip()
```

- [ ] **Step 2: Run it against the unrouted board**

Run: `make check`
Expected: the `chip` geometry assertions pass (nothing is routed, so the via loop is vacuous), but `chip drc` reports `FAIL` on unconnected items. That failure is the gate for the next step.

- [ ] **Step 3: [MANUAL] Route board C in KiCad**

Escape all 22 used balls to the receptacle. Follow carrier A's conventions exactly, because the panel and the DRC rule set are shared:

- 0.15 mm tracks
- one short diagonal dogbone from each used land to its own ordinary through via, 0.45 mm pad / 0.20 mm drill
- no via inside or within 0.35 mm of any BGA pad
- no microvia, blind or buried via, via-in-pad, or filled/capped via
- the 47 unused balls stay floating
- keep the outer 0.5 mm of both long B.Cu edges clear

- [ ] **Step 4: Run the full check**

Run: `make check`
Expected: `chip erc clean` and `chip drc clean`, alongside carrier and base.

- [ ] **Step 5: Confirm zero unconnected explicitly**

```bash
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc --refill-zones \
  -o /tmp/chip-drc.json --format json chip/chip.kicad_pcb 2>&1 | tail -1
python3 -c "
import json; d=json.load(open('/tmp/chip-drc.json'))
print('unconnected', len(d.get('unconnected_items',[])))
print('parity     ', len(d.get('schematic_parity',[])))"
```

Expected: `unconnected 0`, `parity 0`.

- [ ] **Step 6: Commit**

```bash
git add chip/chip.kicad_pcb tools/check_interposer.py
git commit -m "Route board C and check its geometry

Normal land pattern on F.Cu verified non-mirrored by rigid fit, receptacle on
B.Cu, ordinary through-via dogbones only, zero unconnected items."
```

---

### Task 7: Failing checks for board D, and project registration

**Files:**
- Modify: `tools/check_mating.py`
- Modify: `tools/drc-rules.py:PROJECTS`
- Modify: `Makefile`
- Create: `prog/` project **[MANUAL]**

**Interfaces:**
- Consumes: `schematic_pin_map`, `DF40`, `TSOP48` — all already imported by `tools/check_mating.py`.
- Produces: a `prog` project whose `J1` equals the canonical `DF40` table and whose `J2` matches `TSOP48`.

- [ ] **Step 1: Add the prog assertions to `check_mating.py`**

Immediately after the existing `base_j2` loop in `check()`, add:

```python
    # Board D is the host adapter: the same DF40 table on F.Cu, and DIP48 male
    # pins carrying the TSOP48 map into the XGecu T76's 48-pin ZIF.
    prog_j1 = schematic_pin_map("prog", "J1")
    prog_j2 = schematic_pin_map("prog", "J2")
    assert prog_j1 == expected_df40, ("prog J1", prog_j1)
    for pin, net in TSOP48.items():
        assert prog_j2[str(pin)] == net, (pin, prog_j2[str(pin)], net)
    assert prog_j2 == base_j2, (
        "prog and base must present the same DIP48 map; one plugs into the "
        "programmer and the other receives the clamp adapter, but both are the "
        "same TSOP48 contract"
    )
```

- [ ] **Step 2: Run and confirm the right failure**

Run: `python3 tools/check_mating.py`
Expected: failure naming `prog/prog.kicad_sch`. It must not pass.

- [ ] **Step 3: Create the project skeleton from base**

```bash
mkdir -p prog/lib/prog.pretty
cp base/base.kicad_pro prog/prog.kicad_pro
cp base/base.kicad_sch prog/prog.kicad_sch
cp base/base.kicad_pcb prog/prog.kicad_pcb
cp base/sym-lib-table prog/sym-lib-table
cat > prog/fp-lib-table <<'EOF'
(fp_lib_table
  (version 7)

  (lib (name "carrier") (type "KiCad") (uri "${KIPRJMOD}/../carrier/lib/carrier.pretty") (options "") (descr ""))

  (lib (name "Connector_Hirose_DF40") (type "KiCad") (uri "${KIPRJMOD}/../carrier/lib/Connector_Hirose_DF40.pretty") (options "") (descr ""))

  (lib (name "base") (type "KiCad") (uri "${KIPRJMOD}/../base/lib/base.pretty") (options "") (descr ""))

  (lib (name "prog") (type "KiCad") (uri "${KIPRJMOD}/lib/prog.pretty") (options "") (descr ""))
)
EOF
sed -i '' 's|${KIPRJMOD}/lib/base.kicad_sym|${KIPRJMOD}/../base/lib/base.kicad_sym|' prog/sym-lib-table
```

- [ ] **Step 4: [MANUAL] Edit `prog/prog.kicad_sch` in Eeschema**

1. `J1` — replace the `DF40TC_4.0_-30DS-0.4V_51_` receptacle symbol with `DF40TC-30DP-0.4V_51_`. Footprint `Connector_Hirose_DF40:HIROSE_DF40TC-30DP-0.4V_51_`. Pin `n` keeps the net it already had. **Do not re-permute.**
2. `J2` — keep the `DIP-48_Socket` symbol and every net. Change only its Footprint to `prog:DIP-48_Pins_THT_W15.24mm_P2.54mm`, created in Task 8.
3. Add `C1` = 100 nF, `Device:C`, footprint `Capacitor_SMD:C_0402_1005Metric`, VCC to GND.
4. Annotate, then ERC to zero errors.

- [ ] **Step 5: Register with the tooling**

In `tools/drc-rules.py:PROJECTS`, after the `chip` entry:

```python
    (ROOT / 'prog' / 'prog.kicad_pro', True),
```

In the `Makefile`, change `for p in carrier base chip; do` to `for p in carrier base chip prog; do`.

- [ ] **Step 6: Verify**

```bash
./tools/drc-rules.py
python3 tools/check_mating.py
```

Expected: `mating netlist OK: BGA67 -> J1 same-number pair -> DIP48`.

- [ ] **Step 7: Commit**

```bash
git add prog/prog.kicad_pro prog/prog.kicad_sch prog/sym-lib-table prog/fp-lib-table \
  prog/prog.kicad_dru tools/check_mating.py tools/drc-rules.py Makefile
git commit -m "Add prog project schematic and its netlist contract

Board D presents the canonical DF40 table on a plug and the same TSOP48 DIP48
map base B does, asserted equal to base B's."
```

---

### Task 8: DIP48 male footprint and board D geometry

Base B's `J2` is a Samtec SSM-124-L-SV SMT socket with staggered pads at ±1.9275 mm from each mating centreline. Board D needs through-hole male pins instead, so the pads sit **on** the centrelines with no stagger.

**Files:**
- Create: `prog/lib/prog.pretty/DIP-48_Pins_THT_W15.24mm_P2.54mm.kicad_mod`
- Create: `tools/build_prog.py`
- Modify: `prog/prog.kicad_pcb` (as script output)

**Interfaces:**
- Consumes: `pinout.DF40`.
- Produces: pin `n` for `n <= 24` at `(0, (n-1) * 2.54)`; pin `n` for `n > 24` at `(15.24, (48-n) * 2.54)`. Pin 1 at the origin, matching the `row_centre` / `row_index` convention `check_interposer.py` already uses for base B's socket.

- [ ] **Step 1: Generate the footprint**

```bash
python3 - <<'EOF'
from pathlib import Path
pads = []
for pin in range(1, 49):
    x = 0.0 if pin <= 24 else 15.24
    y = ((pin - 1) if pin <= 24 else (48 - pin)) * 2.54
    shape = "rect" if pin == 1 else "circle"
    pads.append(
        '  (pad "%d" thru_hole %s (at %.2f %.2f) (size 1.6 1.6) (drill 1.0)\n'
        '    (layers "*.Cu" "*.Mask"))' % (pin, shape, x, y))
body = "\n".join(pads)
text = (
    '(footprint "DIP-48_Pins_THT_W15.24mm_P2.54mm"\n'
    '  (version 20240108)\n'
    '  (generator "bga67-to-dip48")\n'
    '  (layer "F.Cu")\n'
    '  (descr "DIP-48 male pins, 2.54 mm pitch, 15.24 mm row spacing, for the '
    'XGecu T76 48-pin ZIF. Square 0.64 mm pins, as used by XGecu\'s own '
    'BGA63/BGA48 T76 adapter. Pin 1 at the origin; numbering runs down the '
    'first row and back up the second, matching base B\'s socket convention.")\n'
    '  (attr through_hole)\n'
    '  (property "Reference" "J**" (at 0 -2.54 0) (layer "F.SilkS")\n'
    '    (effects (font (size 1 1) (thickness 0.15))))\n'
    '  (property "Value" "DIP-48_Pins_THT_W15.24mm_P2.54mm" (at 7.62 61 0) '
    '(layer "F.Fab")\n'
    '    (effects (font (size 1 1) (thickness 0.15))))\n'
    + body + "\n)\n")
out = Path("prog/lib/prog.pretty/DIP-48_Pins_THT_W15.24mm_P2.54mm.kicad_mod")
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(text)
print("wrote", out, "with", text.count("(pad "), "pads")
EOF
```

Expected: `wrote prog/lib/prog.pretty/DIP-48_Pins_THT_W15.24mm_P2.54mm.kicad_mod with 48 pads`

- [ ] **Step 2: Verify the pin geometry**

```bash
/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python - <<'EOF' 2>/dev/null
import pcbnew
fp = pcbnew.FootprintLoad("prog/lib/prog.pretty", "DIP-48_Pins_THT_W15.24mm_P2.54mm")
mm = pcbnew.ToMM
bad = []
for pad in fp.Pads():
    pin = int(str(pad.GetNumber()))
    p = pad.GetFPRelativePosition()
    want_x = 0.0 if pin <= 24 else 15.24
    want_y = ((pin - 1) if pin <= 24 else (48 - pin)) * 2.54
    if abs(mm(p.x) - want_x) > 1e-6 or abs(mm(p.y) - want_y) > 1e-6:
        bad.append((pin, mm(p.x), mm(p.y), want_x, want_y))
print("pads:", len(list(fp.Pads())), "| misplaced:", bad or "none")
EOF
```

Expected: `pads: 48 | misplaced: none`

- [ ] **Step 3: Write the board D build script**

```python
#!/usr/bin/env python3
"""Set up board D's connector faces and nets, leaving routing to the editor.

Board D is the host adapter: the DF40 plug on F.Cu facing up toward board C,
and DIP48 male pins pointing down into the XGecu T76's 48-pin ZIF.  It keeps
base B's outline and net map; only the two connectors change face.

Both connectors move.  That is two transforms, not one board flip, and it is
the change that produced the earlier double-mirrored connector table.  Nothing
here is trusted: check_interposer.py and check_mating.py verify the result.

Close KiCad before running this.
"""
from pathlib import Path

import pcbnew

from pinout import DF40

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / "prog" / "prog.kicad_pcb"


def board_net_name(logical_name):
    if logical_name in ("GND", "VCC"):
        return logical_name
    return "/" + logical_name.replace("/", "{slash}")


def main():
    board = pcbnew.LoadBoard(str(BOARD))
    for track in list(board.GetTracks()):
        board.Remove(track)

    connector = board.FindFootprintByReference("J1")
    pins = board.FindFootprintByReference("J2")

    if connector.GetLayer() != pcbnew.F_Cu:
        connector.Flip(connector.GetPosition(), False)
    if pins.GetLayer() != pcbnew.B_Cu:
        pins.Flip(pins.GetPosition(), False)

    edges = board.GetBoardEdgesBoundingBox()
    connector.SetPosition(pcbnew.VECTOR2I(
        (edges.GetLeft() + edges.GetRight()) // 2,
        (edges.GetTop() + edges.GetBottom()) // 2))

    nets = board.GetNetsByName()
    for pad in connector.Pads():
        number = str(pad.GetNumber())
        if number.isdigit():
            pad.SetNet(nets[board_net_name(DF40[int(number)])])

    board.Save(str(BOARD))
    print("prog outline %.2f x %.2f mm"
          % (pcbnew.ToMM(edges.GetWidth()), pcbnew.ToMM(edges.GetHeight())))
    print("J1 on %s, J2 on %s"
          % (board.GetLayerName(connector.GetLayer()),
             board.GetLayerName(pins.GetLayer())))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run it**

Close KiCad first.

Run: `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python tools/build_prog.py 2>/dev/null`

Expected:
```
prog outline 27.79 x 61.39 mm
J1 on F.Cu, J2 on B.Cu
```

- [ ] **Step 5: Commit**

```bash
git add prog/lib/prog.pretty/DIP-48_Pins_THT_W15.24mm_P2.54mm.kicad_mod \
  tools/build_prog.py prog/prog.kicad_pcb
git commit -m "Add DIP48 male footprint and board D geometry

Through-hole pins on the mating centrelines, no SSM stagger, numbered to base
B's convention. Plug moves to F.Cu, pins to B.Cu, nets reassigned."
```

---

### Task 9: Route board D

**Files:**
- Modify: `prog/prog.kicad_pcb` **[MANUAL]**
- Modify: `tools/check_interposer.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: a DRC-clean, fully routed board D.

- [ ] **Step 1: Write the board D geometry check first**

Add to `tools/check_interposer.py` and call it from `check()`:

```python
def check_prog():
    """Board D: plug up to board C, DIP48 male pins down into the T76 ZIF."""
    board = pcbnew.LoadBoard(str(ROOT / "prog" / "prog.kicad_pcb"))
    connector = board.FindFootprintByReference("J1")
    pins = board.FindFootprintByReference("J2")

    assert connector.GetLayer() == pcbnew.F_Cu, "board D's plug must face up"
    assert pins.GetLayer() == pcbnew.B_Cu, "board D's DIP48 pins must face down"

    connector_pads = {str(pad.GetNumber()): pad for pad in connector.Pads()}
    assert {"MT1", "MT2", "MT3", "MT4"} <= connector_pads.keys(), (
        "board D's DF40 plug is missing its four retention lands"
    )

    edges = board.GetBoardEdgesBoundingBox()
    centre = pcbnew.VECTOR2I((edges.GetLeft() + edges.GetRight()) // 2,
                             (edges.GetTop() + edges.GetBottom()) // 2)
    assert connector.GetPosition() == centre, "board D's J1 must be outline-centred"

    # Male pins sit ON the mating centrelines.  Base B's staggered +/-1.9275 mm
    # offsets belong to the SSM-124-L-SV SMT socket and must not appear here.
    for pad in pins.Pads():
        pin = int(str(pad.GetNumber()))
        position = pad.GetFPRelativePosition()
        expected_x = 0.0 if pin <= 24 else 15.24
        expected_y = ((pin - 1) if pin <= 24 else (48 - pin)) * 2.54
        assert abs(mm(position.x) - expected_x) < 1e-6, (pin, mm(position.x))
        assert abs(mm(position.y) - expected_y) < 1e-6, (pin, mm(position.y))
        assert pad.GetAttribute() == pcbnew.PAD_ATTRIB_PTH, (
            f"DIP48 pin {pin} must be through-hole"
        )
```

Call it at the end of `check()`:

```python
    check_prog()
```

- [ ] **Step 2: Run it against the unrouted board**

Run: `make check`
Expected: the `prog` geometry assertions pass; `prog drc` reports `FAIL` on unconnected items.

- [ ] **Step 3: [MANUAL] Route board D in KiCad**

22 nets from the centred DF40 plug out to the DIP48 field. Same rule set as the other boards: 0.15 mm minimum tracks, ordinary through vias only, no via-in-pad. The 26 unused DIP positions stay unconnected — they match the NC pins of a real TSOP48 device and must not be tied to anything.

- [ ] **Step 4: Run the full check**

Run: `make check`
Expected: `carrier`, `base`, `chip` and `prog` all `clean` for both ERC and DRC.

- [ ] **Step 5: Commit**

```bash
git add prog/prog.kicad_pcb tools/check_interposer.py
git commit -m "Route board D and check its geometry

Plug centred on F.Cu, through-hole DIP48 pins on B.Cu on the mating
centrelines with no SSM stagger, zero unconnected items."
```

---

### Task 10: System panel

`tools/panelize.sh` currently builds a 5x5 grid of carrier A alone. It becomes four grids, one per board.

`kikit panelize` takes exactly one source board per invocation and has no merge operation, so "one panel with all four boards on it" would mean writing a custom kikit layout plugin. That is not worth it here: four panel files at the same 1.6 mm / 4 layer / ENIG stackup are still **one fab order**, which is what the spec's "one panel does everything" was actually buying. Four grids, one order.

- `panel/carrier-panel.kicad_pcb` — 5x5, existing
- `panel/chip-panel.kicad_pcb` — 5x5, same 8.41 x 7.60 outline so the identical tab strategy applies
- `panel/base-panel.kicad_pcb` — 1x2
- `panel/prog-panel.kicad_pcb` — 1x2

**Files:**
- Modify: `tools/panelize.sh`
- Modify: `tools/drc-rules.py:PROJECTS`
- Modify: `Makefile` — the `panel` help text still says "from carrier/"
- Modify: `README.md` — record that panelizing produces four files, one per board

**Interfaces:**
- Consumes: DRC-clean `carrier/`, `chip/`, `base/`, `prog/` boards from Tasks 6 and 9.
- Produces: the four panel files listed above.

- [ ] **Step 1: Confirm the outlines actually pair up**

```bash
python3 - <<'EOF'
import re
for name, path in [("carrier","carrier/carrier.kicad_pcb"), ("chip","chip/chip.kicad_pcb"),
                   ("base","base/base.kicad_pcb"), ("prog","prog/prog.kicad_pcb")]:
    t = open(path).read()
    xs, ys = [], []
    for m in re.finditer(r'\(gr_line\s*\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)', t):
        xs += [float(m.group(1)), float(m.group(3))]
        ys += [float(m.group(2)), float(m.group(4))]
    print("%-8s %.2f x %.2f" % (name, max(xs)-min(xs), max(ys)-min(ys)))
EOF
```

Expected: `carrier` and `chip` both about `8.41 x 7.60`; `base` and `prog` both about `27.78 x 61.38`. If a pair disagrees, stop — the panel recipe below assumes they match.

- [ ] **Step 2: Turn the fixed source/output pair into a table and loop**

In `tools/panelize.sh`, replace the fixed `SRC` and `OUT` assignments with one table, keeping every tunable named at the top as the file's own comment requires:

```bash
# source board              output panel                 rows cols
PANELS=(
  "carrier/carrier.kicad_pcb panel/carrier-panel.kicad_pcb 5 5"
  "chip/chip.kicad_pcb       panel/chip-panel.kicad_pcb    5 5"
  "base/base.kicad_pcb       panel/base-panel.kicad_pcb    1 2"
  "prog/prog.kicad_pcb       panel/prog-panel.kicad_pcb    1 2"
)
```

Then wrap everything from the "source is panel-safe" DRC step through the final report in:

```bash
for entry in "${PANELS[@]}"; do
	set -- $entry
	SRC="$ROOT/$1"; OUT="$ROOT/$2"; ROWS="$3"; COLS="$4"
	[ -f "$SRC" ] || die "no board at $SRC"
	# ... existing body, unchanged, using $SRC $OUT $ROWS $COLS ...
done
```

`FRAME_WIDTH`, `SPACE`, `TOOLING_SIZE`, `FID_COPPER` and `FID_OPENING` stay as they are and apply to every panel. Move the `[ -x "$KICAD_CLI" ]` and `command -v kikit` guards above the loop; they are per-run, not per-panel.

- [ ] **Step 3: Extend the lock guard and the library table**

The existing guard globs `carrier/~*.lck` and `panel/~*.lck`. Add the two new projects:

```bash
locks=("$ROOT"/carrier/~*.lck "$ROOT"/chip/~*.lck "$ROOT"/base/~*.lck \
       "$ROOT"/prog/~*.lck "$ROOT"/panel/~*.lck)
```

Add the two libraries board D needs to the generated `panel/fp-lib-table` heredoc:

```
  (lib (name "base") (type "KiCad") (uri "${KIPRJMOD}/../base/lib/base.pretty") (options "") (descr ""))
  (lib (name "prog") (type "KiCad") (uri "${KIPRJMOD}/../prog/lib/prog.pretty") (options "") (descr ""))
```

- [ ] **Step 4: Fix the board-count report**

The final report counts `carrier:BGA-67_..._Mirrored_Interposer"` occurrences, which is carrier-only. Replace with a per-panel footprint count:

```bash
python3 - "$OUT" <<'EOF'
import re, sys
t = open(sys.argv[1]).read()
xs, ys = [], []
for m in re.finditer(r'\(gr_line\s+\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)', t):
	xs += [float(m.group(1)), float(m.group(3))]
	ys += [float(m.group(2)), float(m.group(4))]
if xs:
	print('%.2f x %.2f mm' % (max(xs) - min(xs), max(ys) - min(ys)))
print('%d J1 instances' % len(re.findall(r'\(property "Reference" "J1', t)))
EOF
```

- [ ] **Step 5: Update the Makefile help text and register the new panels**

The `help` target still says `make panel    rebuild panel/ from carrier/`. Change it to:

```make
	@echo "make panel    rebuild all four panels in panel/ (close KiCad first)"
```

In `tools/drc-rules.py:PROJECTS`, add the three new panels alongside the existing carrier panel, all with `False` for the same reason the comment there already gives — kikit derives each panel's `.kicad_dru` from its source board:


```python
    (ROOT / 'panel' / 'chip-panel.kicad_pro', False),
    (ROOT / 'panel' / 'base-panel.kicad_pro', False),
    (ROOT / 'panel' / 'prog-panel.kicad_pro', False),
```

- [ ] **Step 6: Build the panels**

Close KiCad first.

Run: `make panel`
Expected: four `==> Panelizing` blocks, each ending with `hard: none` and a printed panel size.

- [ ] **Step 7: Full green**

Run: `make check`
Expected: every project clean, and `./tools/drc-rules.py --check` silent.

- [ ] **Step 8: Commit**

```bash
git add tools/panelize.sh tools/drc-rules.py Makefile README.md panel/
git commit -m "Panelize all four boards

One stackup, one fab order, four panel files. kikit panelizes a single source
board at a time, so each board gets its own grid rather than forcing a merge."
```

---

## Before ordering

Neither of these blocks the build, both block the fab order.

- [ ] Clear base B's 20 `text thickness out of range` warnings. The panel inherits them.
- [ ] Confirm pin 1 by eye on every mated interface: carrier A to board C, board D to board C, and board D into the T76 ZIF. `tools/ringout.py` exists for the DIP48 half and needs a multimeter, not software.
- [ ] Read the DF40 unmating force from the Hirose datasheet. Board C has no grip feature by decision; the number tells you how careful to be.
