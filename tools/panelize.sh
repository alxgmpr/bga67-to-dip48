#!/usr/bin/env bash
#
# Rebuild panel/carrier-panel.kicad_pcb from carrier/carrier.kicad_pcb.
#
# This script is the single source of truth for the panel recipe. If the panel
# needs to change, change it here -- do not paste a modified kikit command into
# a shell, and do not edit the generated panel by hand. Everything under panel/
# except fp-lib-table is disposable output.
#
#   ./tools/panelize.sh          rebuild and check
#   make panel                   same thing
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/carrier/carrier.kicad_pcb"
OUT="$ROOT/panel/carrier-panel.kicad_pcb"
KICAD_CLI="${KICAD_CLI:-/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli}"
KICAD_PY="${KICAD_PY:-/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/3.9/Resources/Python.app/Contents/MacOS/Python}"

# ---------------------------------------------------------------- parameters
# Keep every tunable here, named, so a change is a one-line diff.
ROWS=5
COLS=5
SPACE=6mm          # solid sacrificial FR-4 strips, scored on both edges
FRAME_WIDTH=5mm    # perimeter process rails
TOOLING_SIZE=2mm   # JLC assembly guide: tooling holes are typically 2-4 mm
FID_COPPER=1mm
FID_OPENING=2mm

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
die()  { printf '\033[31merror: %s\033[0m\n' "$*" >&2; exit 1; }

# ------------------------------------------------------- guard: KiCad is open
# KiCad holds a project in memory and writes its own copy on save. Panelizing
# while the carrier is open silently ships whatever was on disk before the last
# unsaved edit.
shopt -s nullglob
locks=("$ROOT"/carrier/~*.lck "$ROOT"/panel/~*.lck)
shopt -u nullglob
if [ ${#locks[@]} -gt 0 ]; then
	printf '\033[31merror: KiCad has a project open:\033[0m\n' >&2
	printf '         %s\n' "${locks[@]##*/}" >&2
	die "close it before panelizing -- the panel would be built from a stale carrier"
fi

[ -f "$SRC" ]        || die "no carrier board at $SRC"
[ -x "$KICAD_CLI" ]  || die "kicad-cli not at $KICAD_CLI (override with KICAD_CLI=)"
command -v kikit >/dev/null || die "kikit not on PATH"

# ---------------------------------------------------------- source is panel-safe
step "Checking the source board"
"$KICAD_CLI" pcb drc --severity-error \
	-o /tmp/carrier-drc.json --format json "$SRC" >/dev/null 2>&1
python3 - <<'EOF'
import json, sys
d = json.load(open('/tmp/carrier-drc.json'))
v = d.get('violations', [])
u = len(d.get('unconnected_items', []))
if v:
	for item in v:
		print('%s: %s' % (item.get('type', 'violation'), item.get('description', '')))
	sys.exit(1)
print('carrier has no DRC errors (%d unrouted connections expected)' % u)
EOF

# ----------------------------------------------------------------- panelize
step "Panelizing ${ROWS}x${COLS}"
rm -f "$OUT" "${OUT%.kicad_pcb}.kicad_pro" "${OUT%.kicad_pcb}.kicad_prl"
kikit panelize \
	--layout  "grid; rows: $ROWS; cols: $COLS; space: $SPACE" \
	--tabs    "none" \
	--cuts    "none" \
	--framing "frame; width: $FRAME_WIDTH; space: 0mm; cuts: none" \
	--tooling "3hole; hoffset: 1.5mm; voffset: 1.5mm; size: $TOOLING_SIZE" \
	--fiducials "3fid; hoffset: 4mm; voffset: 3.5mm; coppersize: $FID_COPPER; opening: $FID_OPENING" \
	--post    "millradius: 0mm" \
	"$SRC" "$OUT"

# ------------------------------------------------------------- library table
# kikit copies footprints by reference, so the panel needs to resolve the same
# nicknames the carrier does. Regenerated every run so a fresh clone works.
step "Writing panel/fp-lib-table"
cat > "$ROOT/panel/fp-lib-table" <<'EOF'
(fp_lib_table
  (version 7)
  (lib (name "carrier") (type "KiCad") (uri "${KIPRJMOD}/../carrier/lib/carrier.pretty") (options "") (descr ""))
  (lib (name "Connector_Hirose_DF40") (type "KiCad") (uri "${KIPRJMOD}/../carrier/lib/Connector_Hirose_DF40.pretty") (options "") (descr ""))
)
EOF

# ----------------------------------------------------------------- fixups
step "Fixups"
"$KICAD_PY" "$ROOT/tools/panel_fixups.py" "$OUT" 2>/dev/null \
	| grep -v "memory leak"
"$KICAD_PY" "$ROOT/tools/check_panel.py" "$OUT" 2>/dev/null \
	| grep -v "memory leak"

# ------------------------------------------------------------------- verify
step "Panel DRC"
set +e
"$KICAD_CLI" pcb drc --severity-error --severity-warning \
	-o /tmp/panel-drc.json --format json "$OUT" >/dev/null 2>&1
set -e
python3 - "$ROOT" <<'EOF'
import json, sys
from collections import Counter
d = json.load(open('/tmp/panel-drc.json'))
c = Counter(v['type'] for v in d.get('violations', []))
u = len(d.get('unconnected_items', []))

# Not the panel's problem:
#   lib_footprint_*         kikit rewrites footprints into the panel by value
#   silk_*, text_*          inherited from the carrier, cosmetic, and the
#                           carrier's own DRC already reports them once each
#   *_outline               the 20 intentional open Edge.Cuts lines are the
#                           full-length JLC V-score specification
SOFT = ('lib_footprint_mismatch', 'lib_footprint_issues',
        'silk_overlap', 'silk_edge_clearance',
        'silk_over_copper', 'text_height', 'text_thickness',
        'malformed_outline', 'invalid_outline')

hard = {t: n for t, n in c.items() if t not in SOFT}
soft = {t: n for t, n in c.items() if t in SOFT}
print('hard: %s' % (', '.join('%d %s' % (n, t) for t, n in sorted(hard.items())) or 'none'))
print('soft: %s' % (', '.join('%d %s' % (n, t) for t, n in sorted(soft.items())) or 'none'))
if u:
	print('%5d unconnected' % u)
sys.exit(1 if hard else 0)
EOF

step "Panel"
python3 - "$OUT" <<'EOF'
import re, sys
t = open(sys.argv[1]).read()
# Outline extent. Take every gr_line endpoint -- the only board-level gr_lines
# kikit emits are the cuts, and filtering on the layer is brittle because the
# (layer ...) token does not sit at a fixed offset from (start ...).
xs, ys = [], []
for m in re.finditer(r'\(gr_line\s+\(start ([-\d.]+) ([-\d.]+)\)\s*\(end ([-\d.]+) ([-\d.]+)\)', t):
	xs += [float(m.group(1)), float(m.group(3))]
	ys += [float(m.group(2)), float(m.group(4))]
if xs:
	print('%.2f x %.2f mm' % (max(xs) - min(xs), max(ys) - min(ys)))
print('%d boards' % t.count('carrier:BGA-67_6.5x8.0mm_Layout8x10_P0.8mm_Mirrored_Interposer"'))
print('%d V-cut relief slots' % len(re.findall(r'\(property "Reference" "VCUT_RELIEF_', t)))
EOF
