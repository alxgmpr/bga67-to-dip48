#!/usr/bin/env python3
"""Push the JLCPCB 4-layer rule set into every project in the repo.

  ./tools/drc-rules.py          apply
  ./tools/drc-rules.py --check  fail if any project is out of sync

Two halves:
  * the scalar limits below go into each .kicad_pro, because KiCad has
    first-class settings for them and the UI shows them;
  * tools/jlc-4layer.kicad_dru is copied to <project>.kicad_dru for the
    conditional constraints that need an expression.

Source for every number: "Rigid PCB Manufacturing Capabilities", jlcpcb.com,
retrieved 2026-08-09.  4-layer FR-4, 1 oz outer / 0.5 oz inner, ENIG.
"""
import json
import pathlib
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DRU = ROOT / 'tools' / 'jlc-4layer.kicad_dru'
# (project file, manage its .kicad_dru?)
#
# The panel's .kicad_dru is derived, not authored: kikit reads
# carrier/carrier.kicad_dru and re-emits every rule namespaced per board
# ("Board_0-JLC via hole to track 0.2mm", x16). Overwriting it with the flat
# copy would throw that away and put the file permanently out of sync with the
# next `make panel`. Its .kicad_pro scalars are still ours to set.
PROJECTS = [
    (ROOT / 'carrier' / 'carrier.kicad_pro', True),
    (ROOT / 'base' / 'base.kicad_pro', True),
    (ROOT / 'chip' / 'chip.kicad_pro', True),
    (ROOT / 'panel' / 'carrier-panel.kicad_pro', False),
]

# key -> (value, why)
RULES = {
    # Traces: "Min. track width and spacing (1 oz), multilayer: 0.09 / 0.09 mm"
    'min_track_width':            (0.09, 'multilayer 1 oz min track'),
    'min_clearance':              (0.09, 'multilayer 1 oz min spacing'),
    'min_connection':             (0.09, 'narrowest copper neck'),
    # Outline: "Copper clearance from routed board edges >= 0.2 mm"
    'min_copper_edge_clearance':  (0.20, 'routed edge copper clearance'),
    # Traces: "Inner layer via hole to copper clearance 0.2mm" is the tightest
    # global case; the 0.3 mm PTH variant is a conditional rule in the .dru.
    'min_hole_clearance':         (0.20, 'inner-layer via hole to copper'),
    # Drilling: "Via Hole-to-Hole Spacing 0.2mm"; the 0.45 mm pad-to-pad and
    # the mouse-bite cases are conditional rules in the .dru.
    'min_hole_to_hole':           (0.20, 'via hole to via hole'),
    # Drilling: multilayer drill 0.15-6.3 mm
    'min_through_hole_diameter':  (0.15, 'multilayer min drill'),
    # Drilling: "Min. Via hole size/diameter, multilayer: 0.15mm / 0.25mm"
    'min_via_diameter':           (0.25, 'multilayer min via diameter'),
    # "Via diameter should be 0.1mm larger than via hole size" -> 0.05 ring
    'min_via_annular_width':      (0.05, 'via diameter >= hole + 0.1'),
    # Legend: "Pad To Silkscreen 0.15mm"
    'min_silk_clearance':         (0.15, 'pad to silkscreen'),
    # Legend: "Minimum text height 40 mil (1.0mm)", "Minimum Line Width 0.15mm"
    'min_text_height':            (1.00, 'legend min text height'),
    'min_text_thickness':         (0.15, 'legend min line width'),
    # KiCad's practical zero-expansion floor.  This is the carrier project's
    # authored value and is shared so DRC behaves identically on every board.
    # The BGA footprint still carries its own +0.05 locally.
    'solder_mask_to_copper_clearance': (0.005, 'shared carrier mask expansion'),
    # Blind/buried vias are not supported, so microvia limits are inert; leave
    # them at KiCad's defaults rather than implying microvias are available.
    'min_resolved_spokes':        (2, 'thermal relief spokes'),
}


def apply(path, check, manage_dru=True, rule_overrides=None):
    doc = json.loads(path.read_text())
    ds = doc.setdefault('board', {}).setdefault('design_settings', {})
    cur = ds.setdefault('rules', {})
    drift = []
    project_rules = dict(RULES)
    project_rules.update(rule_overrides or {})
    for key, (val, why) in project_rules.items():
        if cur.get(key) != val:
            drift.append('%s: %s -> %s  (%s)' % (key, cur.get(key), val, why))
            cur[key] = val
    dru = path.with_suffix('.kicad_dru')
    want = DRU.read_text()
    if manage_dru and (not dru.exists() or dru.read_text() != want):
        drift.append('%s: rewritten from tools/jlc-4layer.kicad_dru' % dru.name)
        if not check:
            shutil.copyfile(DRU, dru)
    if drift and not check:
        path.write_text(json.dumps(doc, indent=2) + '\n')
    return drift


def main():
    check = '--check' in sys.argv
    dirty = False
    for p, manage_dru in PROJECTS:
        if not p.exists():
            print('skip (missing): %s' % p)
            continue
        # The panel's V-score/relief-slot keepouts deliberately require more
        # copper clearance than an individually routed board edge.
        overrides = ({'min_copper_edge_clearance':
                      (0.30, 'panel V-score and relief-slot clearance')}
                     if p.parent.name == 'panel' else None)
        drift = apply(p, check, manage_dru, overrides)
        print('%s: %s' % (p.parent.name, 'in sync' if not drift else
                          ('%d change%s' % (len(drift), '' if len(drift) == 1 else 's'))))
        for d in drift:
            print('    %s' % d)
        dirty = dirty or bool(drift)
    if check and dirty:
        print('\nout of sync -- run ./tools/drc-rules.py')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
