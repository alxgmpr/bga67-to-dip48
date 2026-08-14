# BGA Suite Phases 1–2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the suite foundations (universal DF40 contract, package data model, footprint/board generators, generalized checks) and prove them by regenerating the VFBGA67 carrier and producing routed eMMC BGA-153 carrier and chip boards.

**Architecture:** Per-package Python data modules feed `pcbnew`-based generator scripts that emit footprints and routable board skeletons; escape routing is manual; assert-style check scripts gate everything through `make check`, following this repo's existing tooling pattern.

**Tech Stack:** KiCad 10 `pcbnew` Python API (run under `$(KICAD_PY)` = KiCad's bundled Python), plain Python 3 data modules, GNU make. No pip dependencies, no pytest — tests are standalone assert scripts, matching the repo.

**Spec:** `docs/superpowers/specs/2026-08-13-bga-suite-design.md`

## Global Constraints

- KiCad must be closed before any script that writes a `.kicad_pcb` (repo rule).
- `pcbnew` scripts run via `$(KICAD_PY)`: `/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python` (macOS default; override with `KICAD_PY=`). Pure-data scripts run with `python3`.
- `tools/pinout.py` remains the single source of truth for DF40 pin positions. The literal value of its `DF40` dict must not change (shipped boards depend on it).
- Board net names follow the repo convention: `GND`/`VCC` bare; every other net is `'/' + name.replace('/', '{slash}')` (see `board_net_name` in `tools/build_chip.py:36`).
- Carrier boards: no via-in-pad, ordinary 0.45 mm vias with 0.20 mm drills. Chip boards: Epoxy Filled & Capped in-pad vias, 0.15–0.55 mm drills, ≥0.05 mm annular ring, via land ≤ ball land, tented both faces (README + `check_interposer.py`).
- JLC 4-layer stackup, 1.6 mm, ENIG; design rules from `tools/jlc-4layer.kicad_dru` pushed by `./tools/drc-rules.py`.
- DF40 connector: 30-pin `HIROSE_DF40TC-30DP-0.4V_51_` (plug) / `HIROSE_DF40TC_4.0_-30DS-0.4V_51_` (receptacle), footprints in `carrier/lib/Connector_Hirose_DF40.pretty`. Same-number mating contract; do not double-mirror (header comment in `tools/pinout.py`).
- Footprint lookup on KiCad 10: iterate `board.GetFootprints()`, never `FindFootprintByReference` (see `tools/build_chip.py:42-53`).
- `board.Remove()` poisons the SWIG registry: collect everything to read/remove first, then remove, then add (see `tools/build_chip.py:56-67`).
- pcbnew SWIG objects: after `pcbnew.SaveBoard`, reload the board for verification rather than trusting live objects.
- Commit after every task with the footer:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 1: Universal DF40 positions and family overlays

**Files:**
- Modify: `tools/pinout.py`
- Create: `tools/families.py`
- Test: `tools/tests/test_families.py`

**Interfaces:**
- Consumes: `tools/pinout.py` `DF40` dict (existing).
- Produces:
  - `pinout.POSITIONS: dict[int, str]` — pin → `'GND' | 'VCC' | 'VCCQ' | 'S'` (`'S'` marks the 15 signal positions).
  - `families.OVERLAYS: dict[str, dict[str, int]]` — family → {signal name → pin}. Families: `'nand_x8'`, `'emmc'`, `'ufs'`.
  - `families.net_map(family) -> dict[int, str]` — pin → logical net name for that family (GND on GND pins; `VCC` on pin 6; pin 10 is `VCC` for `nand_x8` (strap) and `VCCQ` otherwise; unused signal pins map to `NC_<pin>`).
  - `families.check() -> True` — asserts every overlay is injective, lands only on `'S'` positions, and `net_map('nand_x8') == pinout.DF40` extended with `NC_` fills (see step 1 test for the exact identity).

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_families.py`:

```python
#!/usr/bin/env python3
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import pinout, families

# Positions partition the 30 pins exactly as routed today.
assert set(pinout.POSITIONS) == set(range(1, 31))
assert [p for p in sorted(pinout.POSITIONS) if pinout.POSITIONS[p] == 'GND'] == \
    [2, 3, 7, 11, 14, 15, 18, 19, 22, 23, 26, 27, 30]
assert pinout.POSITIONS[6] == 'VCC' and pinout.POSITIONS[10] == 'VCCQ'
assert sum(1 for v in pinout.POSITIONS.values() if v == 'S') == 15

# The nand_x8 overlay reproduces the shipped contract exactly.
nand = families.net_map('nand_x8')
assert nand == pinout.DF40, {p: (nand[p], pinout.DF40[p])
                             for p in nand if nand[p] != pinout.DF40[p]}

# eMMC overlay: DATn rides the IO(n+1) position, CLK is GND-flanked.
emmc = families.OVERLAYS['emmc']
for n in range(8):
    assert emmc['DAT%d' % n] == families.OVERLAYS['nand_x8']['IO%d' % (n + 1)]
assert emmc['CLK'] == 12
assert set(emmc) == {'CLK', 'CMD', 'RST_n', 'DS'} | {'DAT%d' % n for n in range(8)}
emmc_map = families.net_map('emmc')
assert emmc_map[10] == 'VCCQ' and emmc_map[6] == 'VCC'
assert emmc_map[1] == 'NC_1' and emmc_map[5] == 'NC_5' and emmc_map[13] == 'NC_13'

# UFS overlay: two pairs, each member GND-flanked by construction.
ufs = families.OVERLAYS['ufs']
assert set(ufs) == {'DIN_t', 'DIN_c', 'DOUT_t', 'DOUT_c', 'REF_CLK', 'RST_n', 'VCCQ2'}
assert {ufs['DIN_t'], ufs['DIN_c']} == {16, 17}
assert {ufs['DOUT_t'], ufs['DOUT_c']} == {20, 21}

assert families.check() is True
print("families ok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 tools/tests/test_families.py`
Expected: FAIL with `AttributeError: module 'pinout' has no attribute 'POSITIONS'`

- [ ] **Step 3: Implement**

Append to `tools/pinout.py` (below the existing `DF40` dict, which stays byte-identical):

```python
# Universal contract positions.  'S' marks the 15 signal positions; families
# assign their signals onto them via tools/families.py.  Pin 10 is the VCCQ
# position: single-supply families strap it to VCC on the base, which is why
# the shipped nand_x8 boards carry net VCC there.
POSITIONS = {
    p: ('GND' if DF40[p] == 'GND' else 'VCC' if p == 6
        else 'VCCQ' if p == 10 else 'S')
    for p in DF40
}
```

Create `tools/families.py`:

```python
"""Per-family signal overlays onto the universal DF40 positions."""
import pinout

OVERLAYS = {
    # Identity with the shipped contract.
    'nand_x8': {name: pin for pin, name in pinout.DF40.items()
                if pinout.POSITIONS[pin] == 'S'},
    # DATn rides IO(n+1)'s position; CLK sits between GND 11 and GND 14.
    'emmc': {
        'DAT0': 17, 'DAT1': 21, 'DAT2': 25, 'DAT3': 29,
        'DAT4': 28, 'DAT5': 20, 'DAT6': 24, 'DAT7': 16,
        'CLK': 12, 'CMD': 8, 'RST_n': 4, 'DS': 9,
    },
    # Loosely-coupled pairs on facing-row position couples; every member is
    # GND-flanked within its row.  SI validation is future work (see spec).
    'ufs': {
        'DIN_t': 17, 'DIN_c': 16, 'DOUT_t': 21, 'DOUT_c': 20,
        'REF_CLK': 12, 'RST_n': 8, 'VCCQ2': 4,
    },
}


def net_map(family):
    """Pin -> logical net name for one family."""
    overlay = OVERLAYS[family]
    by_pin = {pin: name for name, pin in overlay.items()}
    out = {}
    for pin, role in pinout.POSITIONS.items():
        if role == 'GND':
            out[pin] = 'GND'
        elif role == 'VCC':
            out[pin] = 'VCC'
        elif role == 'VCCQ':
            out[pin] = 'VCC' if family == 'nand_x8' else 'VCCQ'
        else:
            out[pin] = by_pin.get(pin, 'NC_%d' % pin)
    return out


def check():
    for family, overlay in OVERLAYS.items():
        pins = list(overlay.values())
        assert len(pins) == len(set(pins)), f"{family}: overlay not injective"
        for name, pin in overlay.items():
            assert pinout.POSITIONS[pin] == 'S', f"{family}.{name} on non-signal pin {pin}"
    nand = net_map('nand_x8')
    assert nand == pinout.DF40, "nand_x8 overlay must reproduce the shipped contract"
    return True


if __name__ == '__main__':
    check()
    print("family overlays OK")
    for family in OVERLAYS:
        used = sorted(OVERLAYS[family].values())
        print(f"  {family:8s} {len(used):2d} signals on pins {used}")
```

Note: `net_map('nand_x8')` must equal `pinout.DF40` with **no** `NC_` entries — the shipped contract uses all 15 signal positions, so the identity holds exactly.

- [ ] **Step 4: Run tests**

Run: `python3 tools/tests/test_families.py && python3 tools/pinout.py && python3 tools/families.py`
Expected: `families ok`, existing pinout output unchanged, overlay listing prints.

- [ ] **Step 5: Commit**

```bash
git add tools/pinout.py tools/families.py tools/tests/test_families.py
git commit -m "Add universal DF40 positions and per-family signal overlays"
```

---

### Task 2: Package data model, validator, VFBGA67 retrofit

**Files:**
- Create: `packages/__init__.py`, `packages/vfbga67.py`
- Create: `tools/check_package.py`
- Test: `tools/tests/test_vfbga67_package.py`

**Interfaces:**
- Consumes: `families.OVERLAYS`, `families.net_map`.
- Produces:
  - Package module attributes (every `packages/*.py` must define): `NAME: str`, `FAMILY: str`, `BODY_MM: (w, h)`, `PITCH_MM: float`, `LAND_MM: float` (ball-land diameter), `GRID: (row_letters: str, n_cols: int)`, `BALLS: dict[str, str | None]` (ball id like `'A1'` → signal name from the family overlay, `'VCC'`/`'VCCQ'`/`'GND'`, other named supply, or `None` for NC), `PROVENANCE: str` (citation of the ballout document).
  - `packages.ball_xy(module, ball) -> (x_mm, y_mm)` — ball centre relative to the field centre, +x right +y down when viewing the land side, row A at top, column 1 at left.
  - `packages.load(name) -> module` — import `packages.<name>`.
  - `check_package.check(module) -> True` — structural validation; `python3 tools/check_package.py` validates every module in `packages/`.

- [ ] **Step 1: Write `packages/__init__.py`**

```python
"""Package data modules: one per BGA package.  See the suite spec."""
import importlib
import string

# JEDEC ball naming skips I, O, Q, S, X, Z in some standards; each package
# declares the exact row letters it uses, in top-to-bottom order.
def ball_xy(module, ball):
    rows, n_cols = module.GRID
    row, col = ball[0], int(ball[1:])
    assert row in rows and 1 <= col <= n_cols, ball
    pitch = module.PITCH_MM
    x = (col - 1 - (n_cols - 1) / 2) * pitch
    y = (rows.index(row) - (len(rows) - 1) / 2) * pitch
    return x, y


def load(name):
    return importlib.import_module('packages.' + name)
```

- [ ] **Step 2: Write the failing test**

Create `tools/tests/test_vfbga67_package.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 tools/tests/test_vfbga67_package.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.vfbga67'`

- [ ] **Step 4: Transcribe the VFBGA67 ball map from the shipped board**

The shipped carrier already encodes ball → net. Extract it (throwaway helper, run once, do not commit):

```python
# scratch/extract_vfbga67.py — run with $KICAD_PY from repo root
import pcbnew
board = pcbnew.LoadBoard('carrier/carrier.kicad_pcb')
u1 = next(fp for fp in board.GetFootprints() if fp.GetReference() == 'U1')
for pad in sorted(u1.Pads(), key=lambda p: (str(p.GetNumber())[0], int(str(p.GetNumber())[1:]))):
    net = str(pad.GetNetname())
    print(str(pad.GetNumber()), repr(None if net.startswith('unconnected') else
          net.lstrip('/').replace('{slash}', '/')))
```

Author `packages/vfbga67.py` from its output:

```python
NAME = 'vfbga67'
FAMILY = 'nand_x8'
BODY_MM = (6.5, 8.0)
PITCH_MM = 0.8
LAND_MM = 0.40          # matches the shipped BGA-67 footprint's pad diameter
GRID = ('ABCDEFGHJK', 8)  # 10 rows x 8 cols, 67 populated
PROVENANCE = ('Transcribed from the shipped carrier board '
              '(carrier/carrier.kicad_pcb U1 pad nets, verified against the '
              'Home motherboard ring-out in docs/ringout-results.txt).')
BALLS = {
    # ball: signal | 'VCC' | 'GND' | None (NC)  — fill all 67 from the
    # extractor output; the test and check_package enforce completeness.
    'A1': None,
    # ... every populated ball, in row-major order ...
}
```

Every entry comes from the extractor output — the executor fills all 67; the tests below make omissions fail loudly. Verify `LAND_MM` and `GRID` against the shipped footprint file `carrier/lib/carrier.pretty/BGA-67_6.5x8.0mm_Layout8x10_P0.8mm.kicad_mod` (read the pad `(size ...)` and the pad-name span) before committing.

- [ ] **Step 5: Write the validator**

Create `tools/check_package.py`:

```python
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
```

`AUX_` prefix: supply-adjacent balls that need board-local treatment but no DF40 pin (e.g. eMMC `AUX_VDDI`, which gets only a local capacitor). Multiple balls may share a rail name; signals are single-ball.

- [ ] **Step 6: Run tests**

Run: `python3 tools/tests/test_vfbga67_package.py && python3 tools/check_package.py`
Expected: `vfbga67 package ok` twice (test + validator sweep).

- [ ] **Step 7: Commit**

```bash
git add packages/ tools/check_package.py tools/tests/test_vfbga67_package.py
git commit -m "Add package data model with VFBGA67 retrofit and validator"
```

---

### Task 3: Footprint generator with VFBGA67 regression

**Files:**
- Create: `tools/gen_footprint.py`
- Test: `tools/tests/test_gen_footprint.py` (runs under `$KICAD_PY`)

**Interfaces:**
- Consumes: package module attributes, `packages.ball_xy`.
- Produces: `gen_footprint.generate(pkg, out_dir) -> (normal_path, mirrored_path)` writing `BGA-<n>_<name>.kicad_mod` and `BGA-<n>_<name>_Mirrored_Interposer.kicad_mod`. Normal: SMD circle pads (`LAND_MM`) on F.Cu at `ball_xy` positions, one pad per ball **including NC balls** (NC pads get no net later; they must exist so `bga_fit.py` sees the true land pattern). Mirrored: x negated. CLI: `gen_footprint.py <package> <out_dir>`.

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_gen_footprint.py`:

```python
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
```

If `bga_fit.read_footprint_pads` has a different signature, adapt the test to the actual one (`sed -n '1,40p' tools/bga_fit.py` first) — the assertion logic stays the same.

- [ ] **Step 2: Run test to verify it fails**

Run: `"$KICAD_PY" tools/tests/test_gen_footprint.py` (set `KICAD_PY` to the path in Global Constraints)
Expected: FAIL with `ModuleNotFoundError: No module named 'gen_footprint'`

- [ ] **Step 3: Implement `tools/gen_footprint.py`**

```python
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
```

API note for the executor: the exact save call differs across KiCad point releases (`PCB_IO_KICAD_SEXPR().FootprintSave(dir, fp)` on KiCad 9/10; older `pcbnew.PCB_IO()`). Probe interactively with `"$KICAD_PY" -c 'import pcbnew; print([n for n in dir(pcbnew) if "IO" in n])'` and keep whichever works. The attribute constants (`FP_SMD` etc.) likewise: verify with `dir(pcbnew)` and adjust names, keeping the semantics (SMD footprint, excluded from BOM and position files — same as the shipped interposer footprint).

- [ ] **Step 4: Run test**

Run: `"$KICAD_PY" tools/tests/test_gen_footprint.py`
Expected: `gen_footprint vfbga67 regression ok`

- [ ] **Step 5: Commit**

```bash
git add tools/gen_footprint.py tools/tests/test_gen_footprint.py
git commit -m "Add footprint generator with VFBGA67 regression test"
```

---

### Task 4: Board skeleton generator with VFBGA67 regression

**Files:**
- Create: `tools/gen_board.py`
- Test: `tools/tests/test_gen_board.py` (runs under `$KICAD_PY`)

**Interfaces:**
- Consumes: `gen_footprint.generate`, `families.net_map`, package modules, DF40 footprints in `carrier/lib/Connector_Hirose_DF40.pretty`.
- Produces: `gen_board.generate(pkg, role, out_path) -> None` where `role` is `'carrier'` or `'chip'`. Writes a routable `.kicad_pcb`:
  - Nets created for every non-None value of `families.net_map(pkg.FAMILY)` plus rails/AUX nets used by `pkg.BALLS` (net names via the repo's `board_net_name` convention).
  - `U1` = the package land field at the board centre — mirrored footprint on **B.Cu** for `carrier`, normal footprint on **F.Cu** for `chip`. Pad nets from `pkg.BALLS`; NC balls left unconnected.
  - `J1` = DF40 **plug** on F.Cu (`carrier`) or **receptacle** on B.Cu (`chip`), concentric with U1, orientation 180° (carrier, matching `rebuild_courk_interposer.py:34`) / 0° (chip). Pad nets from `families.net_map`.
  - Rectangular Edge.Cuts outline centred on U1: `max(BODY_MM.w, DF40 body 11.34 mm) + 1.0` wide, `BODY_MM.h + 1.6` tall, rounded to 0.01 mm, stroke 0.01 mm — verify the DF40 body span by reading the plug footprint's courtyard before hardcoding; the constant lives at the top of `gen_board.py` as `DF40_BODY_MM`.
  - 4 copper layers enabled; no routing, no zones.
  - CLI: `gen_board.py <package> <carrier|chip> <out.kicad_pcb>`

- [ ] **Step 1: Write the failing test**

Create `tools/tests/test_gen_board.py`:

```python
#!/usr/bin/env python3
"""Regression: generated VFBGA67 carrier skeleton matches the shipped carrier.

Run with $KICAD_PY.  Phase-1 success criterion from the spec: lands, DF40
placement, and nets match; outline differs (shipped uses the Courk cross).
"""
import sys, math, pathlib, tempfile
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
import pcbnew
import packages, families, gen_board

out = pathlib.Path(tempfile.mkdtemp()) / 'carrier_skel.kicad_pcb'
gen_board.generate(packages.load('vfbga67'), 'carrier', out)

def snapshot(path):
    board = pcbnew.LoadBoard(str(path))
    u1 = next(f for f in board.GetFootprints() if f.GetReference() == 'U1')
    j1 = next(f for f in board.GetFootprints() if f.GetReference() == 'J1')
    c = u1.GetPosition()
    pads = {}
    for fp in (u1, j1):
        for pad in fp.Pads():
            net = str(pad.GetNetname())
            pads[(fp.GetReference(), str(pad.GetNumber()))] = (
                round(pcbnew.ToMM(pad.GetPosition().x - c.x), 3),
                round(pcbnew.ToMM(pad.GetPosition().y - c.y), 3),
                None if net.startswith('unconnected') or net == '' else net)
    offset = math.hypot(pcbnew.ToMM(j1.GetPosition().x - c.x),
                        pcbnew.ToMM(j1.GetPosition().y - c.y))
    return pads, offset, u1.GetLayer(), j1.GetLayer()

ours, off_ours, u1_layer, j1_layer = snapshot(out)
shipped, off_shipped, su1, sj1 = snapshot(ROOT / 'carrier/carrier.kicad_pcb')

assert u1_layer == su1 and j1_layer == sj1
assert off_ours <= 0.20 + 1e-6
# Shipped J1 sits within 0.20 mm of centre; ours is concentric.  Compare pads
# net-for-net; positions of J1 pads may differ by the shipped escape offset.
for key, (x, y, net) in shipped.items():
    assert key in ours, key
    assert ours[key][2] == net, (key, ours[key][2], net)
    if key[0] == 'U1':
        assert (abs(ours[key][0] - x) < 5e-3 and abs(ours[key][1] - y) < 5e-3), key
print("gen_board vfbga67 carrier regression ok")
```

Caveat for the executor: shipped U1 pads may be mirrored about the shipped board's own centre — if positional asserts fail uniformly in x, compare against `-x` (the shipped mirrored footprint already encodes the flip; the generated mirrored footprint must land identically since the test compares like-for-like references on the same layer).

- [ ] **Step 2: Run test to verify it fails**

Run: `"$KICAD_PY" tools/tests/test_gen_board.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'gen_board'`

- [ ] **Step 3: Implement `tools/gen_board.py`**

```python
#!/usr/bin/env python3
"""Generate a routable carrier or chip board skeleton from a package module."""
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / 'tools'))
import pcbnew
import packages, families, gen_footprint

MM = pcbnew.FromMM
DF40_LIB = ROOT / 'carrier' / 'lib' / 'Connector_Hirose_DF40.pretty'
PLUG = 'HIROSE_DF40TC-30DP-0.4V_51_'
RECEPTACLE = 'HIROSE_DF40TC_4.0_-30DS-0.4V_51_'
DF40_BODY_MM = 11.34   # verify against the plug courtyard before trusting
CENTRE = pcbnew.VECTOR2I(MM(100), MM(100))


def board_net_name(logical):
    if logical in ('GND', 'VCC', 'VCCQ') or logical.startswith(('NC_', 'AUX_')):
        return logical
    return '/' + logical.replace('/', '{slash}')


def load_footprint(lib_dir, name):
    io = pcbnew.PCB_IO_KICAD_SEXPR()
    return io.FootprintLoad(str(lib_dir), name)


def generate(pkg, role, out_path):
    assert role in ('carrier', 'chip')
    board = pcbnew.NewBoard(str(out_path)) if hasattr(pcbnew, 'NewBoard') \
        else pcbnew.CreateEmptyBoard()
    board.GetDesignSettings().SetCopperLayerCount(4)

    net_names = set(families.net_map(pkg.FAMILY).values())
    net_names |= {s for s in pkg.BALLS.values() if s}
    nets = {}
    for logical in sorted(net_names):
        if logical.startswith('NC_'):
            continue
        info = pcbnew.NETINFO_ITEM(board, board_net_name(logical))
        board.Add(info)
        nets[logical] = info

    # U1: land field.
    fp_dir = pathlib.Path(out_path).parent / 'lib' / (pkg.NAME + '.pretty')
    normal, mirrored = gen_footprint.generate(pkg, fp_dir)
    u1 = load_footprint(fp_dir, (mirrored if role == 'carrier' else normal).stem)
    u1.SetReference('U1')
    u1.SetValue(pkg.NAME.upper() + '_INTERFACE')
    board.Add(u1)
    u1.SetPosition(CENTRE)
    if role == 'carrier' and u1.GetLayer() != pcbnew.B_Cu:
        u1.Flip(u1.GetPosition(), False)
    for pad in u1.Pads():
        signal = pkg.BALLS.get(str(pad.GetNumber()))
        if signal:
            pad.SetNet(nets[signal])

    # J1: DF40.
    j1 = load_footprint(DF40_LIB, PLUG if role == 'carrier' else RECEPTACLE)
    j1.SetReference('J1')
    board.Add(j1)
    j1.SetPosition(CENTRE)
    if role == 'carrier':
        j1.SetOrientationDegrees(180)
    if role == 'chip' and j1.GetLayer() != pcbnew.B_Cu:
        j1.Flip(j1.GetPosition(), False)
    pin_nets = families.net_map(pkg.FAMILY)
    for pad in j1.Pads():
        number = str(pad.GetNumber())
        if number.isdigit():
            logical = pin_nets[int(number)]
            if not logical.startswith('NC_'):
                pad.SetNet(nets[logical])

    # Outline.
    w = max(pkg.BODY_MM[0], DF40_BODY_MM) + 1.0
    h = pkg.BODY_MM[1] + 1.6
    cx, cy = pcbnew.ToMM(CENTRE.x), pcbnew.ToMM(CENTRE.y)
    corners = [(cx - w/2, cy - h/2), (cx + w/2, cy - h/2),
               (cx + w/2, cy + h/2), (cx - w/2, cy + h/2)]
    for start, end in zip(corners, corners[1:] + corners[:1]):
        edge = pcbnew.PCB_SHAPE(board)
        edge.SetShape(pcbnew.SHAPE_T_SEGMENT)
        edge.SetLayer(pcbnew.Edge_Cuts)
        edge.SetWidth(MM(0.01))
        edge.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
        edge.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
        board.Add(edge)

    pcbnew.SaveBoard(str(out_path), board)


if __name__ == '__main__':
    generate(packages.load(sys.argv[1]), sys.argv[2], sys.argv[3])
    print("wrote", sys.argv[3])
```

Executor notes: (1) empty-board creation and footprint-library APIs vary by KiCad release — probe as in Task 3 and keep what works; (2) before relying on `DF40_BODY_MM`, print the plug footprint's `GetBoundingBox()` and set the constant from it; (3) net-name convention now includes `VCCQ` bare — extend the existing `board_net_name` convention consistently (bare rails: GND, VCC, VCCQ).

- [ ] **Step 4: Run test**

Run: `"$KICAD_PY" tools/tests/test_gen_board.py`
Expected: `gen_board vfbga67 carrier regression ok`

- [ ] **Step 5: Commit**

```bash
git add tools/gen_board.py tools/tests/test_gen_board.py
git commit -m "Add board skeleton generator with VFBGA67 carrier regression"
```

---

### Task 5: Parameterize checks and wire into make

**Files:**
- Modify: `tools/check_interposer.py`
- Modify: `Makefile`
- Test: `make check` (existing suite must stay green) plus new `make suite-check`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `check_interposer.py` gains `check_generic(board_path, pkg, role)` enforcing, for `role='carrier'`: U1 on B.Cu, mirrored footprint name, no 3D models/graphics on U1, J1 within 0.20 mm of U1, J1 pad nets == `families.net_map`, no via within 0.325 mm of any DF40 land, **no via-in-pad** (no via centre within `LAND_MM/2` of a U1 pad centre); for `role='chip'`: U1 on F.Cu non-mirrored, J1 receptacle on B.Cu, and the epoxy rules for any via touching a U1 pad: drill 0.15–0.55 mm, annular ≥ 0.05 mm, via land ≤ `LAND_MM`, no mask opening either face. The existing `check()` for the shipped boards keeps running unchanged (it may delegate to `check_generic` internally once outputs are identical).
  - Makefile target `suite-check`: runs `python3 tools/families.py`, `python3 tools/check_package.py`, all `tools/tests/test_*.py` (pure ones with `python3`, pcbnew ones with `$(KICAD_PY)`), and `check_generic` over every board under `boards/`. `check` depends on `suite-check`.

- [ ] **Step 1: Refactor `check_interposer.py`**

Read the whole file first. Extract the body of the existing `check()` into `check_generic(board_path, pkg, role)` parameterized by: board path, expected footprint names (built from `pkg.NAME`), land diameter (`pkg.LAND_MM`), net map (`families.net_map(pkg.FAMILY)` through `board_net_name`). Keep a thin `check()` that calls `check_generic` with the VFBGA67 values plus the shipped-board extras that don't generalize (the Courk cross outline check stays VFBGA67-only, guarded by `pkg.NAME == 'vfbga67'`). The chip-board epoxy rules already exist in this file for board C — parameterize them the same way.

- [ ] **Step 2: Verify no regression**

Run: `make check`
Expected: identical pass/fail state to before the refactor (run `make check` once before starting to record the baseline).

- [ ] **Step 3: Add `suite-check` to the Makefile**

```make
suite-check:
	@python3 tools/pinout.py >/dev/null && python3 tools/families.py
	@python3 tools/check_package.py
	@python3 tools/tests/test_families.py
	@python3 tools/tests/test_vfbga67_package.py
	@$(KICAD_PY) tools/tests/test_gen_footprint.py 2>/dev/null
	@$(KICAD_PY) tools/tests/test_gen_board.py 2>/dev/null
	@$(KICAD_PY) tools/check_interposer.py --all-boards 2>/dev/null

check: suite-check
```

Add `--all-boards` to `check_interposer.py.__main__`: for every `boards/<pkg>/{carrier,chip}/*.kicad_pcb` that exists, run `check_generic` with the matching package module; with no boards present it prints `no suite boards yet` and exits 0.

- [ ] **Step 4: Run and commit**

Run: `make check`
Expected: all green including `suite-check`.

```bash
git add tools/check_interposer.py Makefile
git commit -m "Parameterize interposer checks; add suite-check make target"
```

---

### Task 6: eMMC BGA-153 package module

**Files:**
- Create: `packages/emmc_bga153.py`
- Test: `tools/tests/test_emmc_bga153.py`

**Interfaces:**
- Consumes: data model from Task 2.
- Produces: `packages/emmc_bga153.py` with the full 153-ball map.

- [ ] **Step 1: Obtain the JEDEC ballout**

The eMMC 153-ball FBGA ballout is defined in JESD84-B51 (eMMC 5.1). Fetch the standard (jedec.org free with registration) or a manufacturer datasheet that reprints the full ball map with the JEDEC drawing (e.g. Kingston EMMC04G-M627 or Micron MTFC*GA* datasheets — the ball map table, not the marketing pinout). **The module's `PROVENANCE` string must cite the exact document and revision transcribed from.** Do not use forum pinout images.

- [ ] **Step 2: Write the failing test**

Create `tools/tests/test_emmc_bga153.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 tools/tests/test_emmc_bga153.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 4: Transcribe the module**

Author `packages/emmc_bga153.py`:

```python
NAME = 'emmc_bga153'
FAMILY = 'emmc'
BODY_MM = (11.5, 13.0)
PITCH_MM = 0.5
LAND_MM = 0.25          # NSMD land for 0.30 mm balls at 0.5 mm pitch
GRID = ('ABCDEFGHJKMNPRTU', 14)   # set exactly from the JEDEC drawing
PROVENANCE = '<document id, revision, table/figure number>'
BALLS = {
    # Transcribe every populated ball from the JEDEC drawing.  eMMC signal
    # balls map to overlay names: CLK, CMD, DAT0..DAT7, RST_n, DS.  Supply
    # balls map to VCC (flash core), VCCQ (I/O), GND.  VDDi maps to
    # 'AUX_VDDI' (local regulator cap only, no DF40 pin).  Unpopulated grid
    # positions are simply absent; populated NC balls map to None.
}
```

Transcription mechanics (the map is 153 entries; do it in a way that can be re-verified): build the dict in a spreadsheet-like text block first (`docs/ballouts/emmc_bga153.txt`, one line per ball `A3 DAT0`), commit that file as the reviewable artifact, and generate the dict from it with a five-line throwaway script. Cross-check counts before writing the module: total 153; DAT0–7, CLK, CMD, RST_n, DS each exactly once. Verify `GRID` letters against the drawing — JEDEC row lettering skips some letters; use exactly the sequence the drawing shows, top row first, and let `check_package` catch any ball that falls outside it.

- [ ] **Step 5: Run tests**

Run: `python3 tools/tests/test_emmc_bga153.py && python3 tools/check_package.py && make suite-check`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add packages/emmc_bga153.py docs/ballouts/emmc_bga153.txt tools/tests/test_emmc_bga153.py
git commit -m "Add eMMC BGA-153 package module transcribed from JEDEC ballout"
```

---

### Task 7: Generate the eMMC BGA-153 carrier and chip skeletons

**Files:**
- Create: `boards/emmc_bga153/carrier/carrier.kicad_pcb` (+ `lib/emmc_bga153.pretty/`)
- Create: `boards/emmc_bga153/chip/chip.kicad_pcb` (+ `lib/`)
- Test: `make suite-check` (picks the new boards up via `--all-boards`)

**Interfaces:**
- Consumes: `gen_board.generate`, Task 6 module.
- Produces: two unrouted, net-complete board files ready for manual escape routing.

- [ ] **Step 1: Generate both skeletons**

```bash
mkdir -p boards/emmc_bga153/carrier boards/emmc_bga153/chip
"$KICAD_PY" tools/gen_board.py emmc_bga153 carrier boards/emmc_bga153/carrier/carrier.kicad_pcb
"$KICAD_PY" tools/gen_board.py emmc_bga153 chip boards/emmc_bga153/chip/chip.kicad_pcb
./tools/drc-rules.py    # push jlc-4layer.kicad_dru into the new projects
```

If `drc-rules.py` discovers projects by a hardcoded list, add the two new board directories to it (read the script first).

- [ ] **Step 2: Add the chip board's local capacitors**

The eMMC chip board needs three 0402 capacitors on B.Cu (same flow as `build_chip.py`'s C1/C2): 1 µF VCC–GND, 1 µF VCCQ–GND, 100 nF AUX_VDDI–GND. Add them with pcbnew in a small extension to the generation step (footprint `Capacitor_SMD:C_0402_1005Metric` from the KiCad standard library, or copy the 0402 footprint already used by `chip/` into the new project lib — check `chip/lib/` first and prefer the repo's own). Position: flanking the DF40 receptacle at the y-offset pattern `build_chip.py` uses (`CAP_OFFSET_MM = 2.9`, scaled to this board's taller outline — put them at ±(BODY_MM[1]/2 - 1.2) and adjust during routing if they collide).

- [ ] **Step 3: Run checks**

Run: `make suite-check`
Expected: `check_generic` passes on both new boards (geometry/net checks; DRC is not yet expected to pass — routing comes next). If `check_generic`'s no-via rules fail on an unrouted board, that's a bug in the check (no vias exist yet) — fix the check, not the board.

- [ ] **Step 4: Commit**

```bash
git add boards/emmc_bga153
git commit -m "Generate eMMC BGA-153 carrier and chip skeletons"
```

---

### Task 8: Route the eMMC BGA-153 carrier

**Files:**
- Modify: `boards/emmc_bga153/carrier/carrier.kicad_pcb`

**Interfaces:**
- Consumes: Task 7 skeleton.
- Produces: fully routed carrier passing `check_generic` and `kicad-cli pcb drc` with zero errors and zero unconnected items.

- [ ] **Step 1: Add dogbone escapes**

Reuse the dogbone algorithm: lift `add_courk_dogbones` from `tools/rebuild_courk_interposer.py` into a shared helper `tools/dogbones.py` (parameterized by board, land-field reference, connector reference, via geometry 0.45/0.20 mm, candidate offsets ±`PITCH_MM/2`) and call it on this board. At 0.5 mm pitch the 0.525 mm minimum via-to-land spacing does **not** hold on the diagonal (0.354 mm < 0.525 mm) — the interstitial-diagonal dogbone pattern from the 0.8 mm board cannot be reused as-is. Only ~13 of 153 balls carry signals, so use perimeter-biased escapes instead: for signal balls in the outer two rows, route straight out past the field edge on B.Cu before dropping a via clear of the land field; for interior signal balls, route between lands (0.25 mm land at 0.5 mm pitch leaves 0.25 mm gaps; 0.1 mm trace with 0.07 mm clearance fits — confirm against `jlc-4layer.kicad_dru` minimums before routing, and if it does not fit, escalate to the user: the land diameter or rules need a decision). Implement the helper so it places via + stub for balls it can solve and reports the ones it cannot; finish those manually.

- [ ] **Step 2: Route via KiCad (manual)**

Open the board in KiCad (or use the KiCad MCP `route_trace`/`route_pad_to_pad` tools as previous sessions did for board C) and connect every via stub to its DF40 pad on In1/In2/B.Cu as needed. GND lands tie to a B.Cu GND pour added after signal routing (`add_copper_pour` / zone on B.Cu + F.Cu, GND net, then refill).

- [ ] **Step 3: Verify**

```bash
make suite-check
/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli pcb drc --refill-zones \
  --exit-code-violations --severity-error -o /tmp/emmc-carrier-drc.json \
  --format json boards/emmc_bga153/carrier/carrier.kicad_pcb
python3 -c "import json;d=json.load(open('/tmp/emmc-carrier-drc.json'));print(len(d['violations']),'violations',len(d['unconnected_items']),'unconnected')"
```

Expected: 0 violations, 0 unconnected.

- [ ] **Step 4: Commit**

```bash
git add boards/emmc_bga153/carrier tools/dogbones.py
git commit -m "Route eMMC BGA-153 carrier"
```

---

### Task 9: Route the eMMC BGA-153 chip board

**Files:**
- Modify: `boards/emmc_bga153/chip/chip.kicad_pcb`

**Interfaces:**
- Consumes: Task 7 skeleton, Task 8's `tools/dogbones.py` learnings.
- Produces: routed chip board passing `check_generic` (epoxy rules) and DRC clean.

- [ ] **Step 1: Place in-pad vias**

This is the board-C pattern: signal balls get vias **inside** the land (Epoxy Filled & Capped). For each signal/rail ball that needs to reach the DF40 receptacle on B.Cu, place a via centred on the pad: drill 0.20 mm, via land 0.25 mm (= `LAND_MM`, satisfying land ≤ ball land with annular (0.25−0.20)/2 = 0.025 mm — **that violates the 0.05 mm annular minimum; use drill 0.15 mm** giving 0.05 mm annular exactly). No mask opening on either face for these vias. Script it (extend `tools/dogbones.py` with `add_inpad_vias(board, pads)`) so the geometry is exact.

- [ ] **Step 2: Route to the DF40 receptacle**

Same as Task 8 step 2, on the B.Cu side plus inners. Wire the three capacitors: VCC/VCCQ/AUX_VDDI to their rails, other terminal to GND pour.

- [ ] **Step 3: Verify epoxy rules + DRC**

Run: `make suite-check` — `check_generic(..., role='chip')` must confirm every in-pad via: drill within 0.15–0.55, annular ≥ 0.05, land ≤ 0.25, tented both faces. Then the same `kicad-cli pcb drc` gate as Task 8.
Expected: all clean.

- [ ] **Step 4: Commit**

```bash
git add boards/emmc_bga153/chip tools/dogbones.py
git commit -m "Route eMMC BGA-153 chip board with epoxy filled-and-capped vias"
```

---

### Task 10: eMMC adapter ring-out checklist and base-variant gate

**Files:**
- Modify: `tools/ringout.py`
- Create: `docs/emmc-base-gate.md`

**Interfaces:**
- Consumes: `families.net_map('emmc')`.
- Produces: a printable probe checklist for the XGecu eMMC adapter; documentation that the eMMC base variant is blocked until a human records `docs/ringout-results-emmc.txt`.

- [ ] **Step 1: Extend `ringout.py`**

Read `tools/ringout.py` first. Add a `--family emmc` mode that prints the probe checklist: for each of the 12 eMMC signals plus VCC/VCCQ/GND, the DF40 pin (from `families.net_map('emmc')`) and a blank DIP48 column to fill at the bench, and that parses/validates `docs/ringout-results-emmc.txt` in the same format the NAND results file uses (every DF40 signal pin mapped to exactly one DIP48 pin, no duplicates).

- [ ] **Step 2: Write the gate doc**

`docs/emmc-base-gate.md`: state that `base_variants/emmc/` must not be routed until `python3 tools/ringout.py --family emmc docs/ringout-results-emmc.txt` passes on human-recorded measurements of the physical XGecu eMMC adapter; name the adapter to buy (link the XGecu store's eMMC BGA-153 adapter for the T76) and reference the spec's per-family gate.

- [ ] **Step 3: Verify and commit**

Run: `python3 tools/ringout.py --family emmc` (no file) — prints the checklist and exits 0.

```bash
git add tools/ringout.py docs/emmc-base-gate.md
git commit -m "Add eMMC adapter ring-out checklist and base-variant gate"
```

---

## Deviations from spec (deliberate, flagged)

- **No generated schematics in this plan.** The spec's `gen_board.py` description includes a minimal generated schematic for ERC/parity. This plan validates generated boards' nets directly against the contract via `check_generic` instead — a schematic generated from the same data would only ever agree with the board by construction, so parity against it adds no check. Schematic generation moves to a later phase if fab/documentation needs it.
- **Panelizer generalization deferred.** The spec's package-list panelizer lands with the first multi-package fab order (phase 3), since nothing in phases 1–2 is being panelized.

## Post-plan

- Push at the end (allowed standing permission), summarize what passed.
- The eMMC base variant, remaining eMMC/eMCP packages, NAND/UFS families are phases 3–6: separate plans after this one lands.
- If JLCPCB confirms/denies epoxy-fill on 4 layers in the meantime, record it in the README's pre-order gate section.
