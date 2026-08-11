#!/usr/bin/env python3
"""Ring out the XGecu adapter's TSOP48 <-> DIP48 mapping, and check the result.

  python3 tools/ringout.py                     print the probe checklist
  python3 tools/ringout.py RESULTS             check recorded readings

The whole design rests on one unmeasured assumption: that
`T76_B48(63)_08-005` is a passive 1:1 router, so TSOP48 contact N reaches
DIP48 pin N.  Nothing in software can catch it being wrong -- both boards
would be consistently wrong together, and ERC, DRC and a netlist diff would
all pass.  Hence a multimeter.

Only the 19 pins that carry nets are worth probing, but each one is probed
against its own neighbours too, because the failure that actually bites is
an off-by-one or a swapped pair, not a wholesale scramble.

RESULTS format -- one line per probed DIP pin, '#' comments ignored:

    <dip_pin> <tsop_contact_that_rang>

Use `-` if nothing rang.  Example:

    7  7
    8  8
    9  -

The checker reports the failure mode by name (offset, mirror, bus
permutation) rather than just a diff, because those have very different
consequences.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# TSOP48 pin -> signal. Straight out of docs/connector-pinout.md "DIP48 side".
# Kioxia's I/O1 is the socket's I/O0; these are the socket's numbers.
TSOP48 = {
    29: 'IO1', 30: 'IO2', 31: 'IO3', 32: 'IO4',
    41: 'IO5', 42: 'IO6', 43: 'IO7', 44: 'IO8',
    7: 'RY//BY', 8: '/RE', 9: '/CE',
    16: 'CLE', 17: 'ALE', 18: '/WE', 19: '/WP',
    12: 'VCC', 37: 'VCC',
    13: 'GND', 36: 'GND',
}

# Losing one of these silently corrupts a dump in a way that looks like a
# software problem. Commands and addresses ride the same pins as data.
BUS = {'IO1', 'IO2', 'IO3', 'IO4', 'IO5', 'IO6', 'IO7', 'IO8'}


def neighbours(pin):
    """Adjacent contacts on the same physical row of a 48-pin DIP/TSOP body."""
    out = []
    for d in (-1, 1):
        n = pin + d
        if 1 <= n <= 48 and ((pin <= 24) == (n <= 24)):
            out.append(n)
    return out


def checklist():
    order = sorted(TSOP48)
    print('Ring out %d pins on the XGecu T76_B48(63)_08-005 adapter.' % len(order))
    print()
    print('Setup: adapter out of the programmer, TSOP48 ZIF lever OPEN and')
    print('nothing in it. Meter on continuity. Probe the DIP48 pin underneath')
    print('and the corresponding TSOP48 socket contact on top.')
    print()
    print('Record one line per pin as "<dip_pin> <tsop_contact_that_rang>",')
    print('or "<dip_pin> -" if nothing rang. Then:')
    print('    python3 tools/ringout.py docs/ringout-results.txt')
    print()
    print('  %-4s %-8s %-26s %s' % ('DIP', 'signal', 'expect SHORT to TSOP', 'expect OPEN to'))
    print('  ' + '-' * 72)
    for p in order:
        nb = ', '.join(str(n) for n in neighbours(p))
        print('  %-4d %-8s %-26s %s' % (p, TSOP48[p], p, nb))
    print()
    print('Mechanical checks, while it is on the bench:')
    print('  [ ] DIP48 row spacing is 0.600 in / 15.24 mm centre to centre')
    print('  [ ] which physical corner is DIP pin 1, relative to the ZIF lever')
    print('  [ ] adapter body outline -- does it overhang the base board, which')
    print('      now seats it ~3 mm lower than a through-hole socket would')
    print()
    print('If any "expect OPEN" pair rings, stop: that is a short, not a')
    print('mapping question, and it will not be fixed by relabelling.')


def parse(path):
    got, blank = {}, []
    for lineno, raw in enumerate(open(path), 1):
        line = raw.split('#')[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise SystemExit('%s:%d: expected "<dip_pin> <tsop_contact>", got %r'
                             % (path, lineno, raw.strip()))
        try:
            dip = int(parts[0])
        except ValueError:
            raise SystemExit('%s:%d: DIP pin %r is not a number' % (path, lineno, parts[0]))
        if parts[1] == '?':
            blank.append(dip)
            continue
        try:
            tsop = None if parts[1] == '-' else int(parts[1])
        except ValueError:
            raise SystemExit('%s:%d: %r is not a TSOP contact number, "-" or "?"'
                             % (path, lineno, parts[1]))
        if dip in got:
            raise SystemExit('%s:%d: DIP pin %d recorded twice' % (path, lineno, dip))
        got[dip] = tsop
    return got, blank


def check(path):
    got, blank = parse(path)
    expected = sorted(TSOP48)
    missing = [p for p in expected if p not in got]
    if blank:
        print('%d of %d pins are still "?" -- not measured yet: %s'
              % (len(blank), len(expected), ', '.join(map(str, sorted(blank)))))
    extra = [p for p in got if p not in TSOP48]

    print('read %d readings from %s' % (len(got), path))
    if missing:
        print('  NOT MEASURED: %s' % ', '.join(map(str, missing)))
    if extra:
        print('  note: readings for unused pins %s (ignored for the verdict)'
              % ', '.join(map(str, sorted(extra))))

    opens, wrong = [], []
    for p in expected:
        if p not in got:
            continue
        if got[p] is None:
            opens.append(p)
        elif got[p] != p:
            wrong.append((p, got[p], TSOP48[p]))

    print()
    if opens:
        print('OPEN CIRCUIT on %d pin(s): %s' % (len(opens), ', '.join(map(str, opens))))
        print('  A used pin that does not ring is a dead signal. Re-seat the')
        print('  probes before believing it; ZIF contacts read open if the')
        print('  lever is closed on nothing.')
        print()

    if not wrong and not opens and not missing:
        print('PASS - all %d used pins are 1:1. The adapter is a passive'
              % len(expected))
        print('       router, which is what docs/connector-pinout.md assumes.')
        print()
        print('Update the "Unverified" notes in docs/HANDOFF.md, docs/'
              'connector-pinout.md and README.md, and record the meter and date.')
        return 0

    if wrong:
        deltas = {t - d for d, t, _ in wrong}
        mirrored = all(t == 49 - d for d, t, _ in wrong)
        print('MISMATCH on %d pin(s):' % len(wrong))
        for d, t, sig in wrong:
            flag = '   <-- DATA BUS' if sig in BUS else ''
            print('  DIP %-3d (%-7s) rang to TSOP %-3d, expected %d%s' % (d, sig, t, d, flag))
        print()
        if len(deltas) == 1 and 0 not in deltas:
            off = deltas.pop()
            print('  Diagnosis: uniform offset of %+d. The adapter is 1:1 but' % off)
            print('  numbered from a different origin than assumed. Every pin')
            print('  moves together, so this is a one-line fix to the TSOP48')
            print('  table in docs/connector-pinout.md -- not a board respin.')
        elif mirrored:
            print('  Diagnosis: mirrored (pin N <-> pin 49-N). The adapter is')
            print('  1:1 but pin 1 is at the opposite end from what the table')
            print('  assumes. Check which corner pin 1 is, relative to the ZIF')
            print('  lever, before changing anything.')
        else:
            bus = [s for _, _, s in wrong if s in BUS]
            print('  Diagnosis: irregular mapping.')
            if bus:
                print('  %d of the mismatches are DATA BUS lines (%s).'
                      % (len(bus), ', '.join(sorted(bus))))
                print('  This is the case docs/connector-pinout.md warns about:')
                print('  commands and addresses ride the same pins as data, so a')
                print('  swizzle corrupts the command byte -- the device will not')
                print('  respond at all, it will not merely scramble a dump.')
            print('  Board B must be rerouted to match before it is ordered.')
    return 1


if __name__ == '__main__':
    sys.exit(check(sys.argv[1]) if len(sys.argv) > 1 else (checklist() or 0))
