#!/usr/bin/env python3
"""Ring out an XGecu adapter's pin mapping, and check the result.

  python3 tools/ringout.py                          NAND: print the probe checklist
  python3 tools/ringout.py RESULTS                  NAND: check recorded readings
  python3 tools/ringout.py --family emmc             eMMC: print the probe checklist
  python3 tools/ringout.py --family emmc RESULTS     eMMC: check recorded readings

NAND (default family, `T76_B48(63)_08-005`):

The whole design rests on one unmeasured assumption: that the adapter is a
passive 1:1 router, so TSOP48 contact N reaches DIP48 pin N.  Nothing in
software can catch it being wrong -- both boards would be consistently
wrong together, and ERC, DRC and a netlist diff would all pass.  Hence a
multimeter.

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

eMMC (`--family emmc`, XGecu "EMMC BGA153/BGA169 Adapter IC Socket"):

Unlike the NAND TSOP48 adapter, there is no documented DF40<->DIP48 identity
to check readings against -- this ring-out *discovers* the eMMC adapter's
DIP48 pin-out, it does not merely confirm one. The check is therefore just
completeness and bijectivity: every probed DF40 pin (the 12 eMMC signals
plus VCC, VCCQ and one representative GND) must land on its own distinct
DIP48 pin, with nothing missing and nothing shared.

RESULTS format -- one line per probed DF40 pin, '#' comments ignored:

    <df40_pin> <dip48_pin_that_rang>

Use `-` if nothing rang.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import families

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


EMMC_SIGNALS = {'CLK', 'CMD', 'RST_n', 'DS'} | {'DAT%d' % i for i in range(8)}


def emmc_probes():
    """DF40 pin -> net name, for the eMMC pins worth ring-out: the 12 eMMC
    signals, VCC, VCCQ, and one representative GND pin.

    GND is commoned across many DF40 pins on the carrier (a ground plane),
    so probing all of them proves nothing that probing one doesn't; VCC and
    VCCQ each occupy exactly one DF40 pin in the universal contract.
    """
    nm = families.net_map('emmc')
    out = {pin: name for pin, name in nm.items()
           if name in EMMC_SIGNALS or name in ('VCC', 'VCCQ')}
    gnd_pins = sorted(pin for pin, name in nm.items() if name == 'GND')
    out[gnd_pins[0]] = 'GND'
    return out


def checklist_emmc():
    probes = emmc_probes()
    order = sorted(probes)
    print('Ring out %d pins on the XGecu EMMC BGA153/BGA169 adapter against' % len(order))
    print("this board's DF40 connector J1.")
    print()
    print('Setup: adapter out of the programmer, socket empty. Meter on')
    print('continuity. Probe the DF40 pin listed below on the carrier board')
    print('and walk the DIP48 pins on the adapter until one rings.')
    print()
    print('Unlike the NAND TSOP48 adapter, there is no documented DF40<->')
    print('DIP48 identity to check against -- this ring-out DISCOVERS the')
    print('mapping, it does not just confirm one.')
    print()
    print('Record one line per pin as "<df40_pin> <dip48_pin_that_rang>",')
    print('or "<df40_pin> -" if nothing rang. Then:')
    print('    python3 tools/ringout.py --family emmc docs/ringout-results-emmc.txt')
    print()
    print('  %-6s %-8s %s' % ('DF40', 'signal', 'DIP48 pin (fill at bench)'))
    print('  ' + '-' * 50)
    for p in order:
        print('  %-6d %-8s %s' % (p, probes[p], '____'))
    print()
    gnd_count = sum(1 for n in families.net_map('emmc').values() if n == 'GND')
    gnd_pin = next(p for p in order if probes[p] == 'GND')
    print('GND is commoned across %d DF40 pins on the carrier; pin %d above'
          % (gnd_count, gnd_pin))
    print('is only a representative -- any of them would do.')
    print()
    print('If the same DIP48 pin rings for two different DF40 signals, stop:')
    print('that is a short or a bussed pin on the adapter, not a mapping to')
    print('record.')


def parse_emmc(path):
    got, blank = {}, []
    for lineno, raw in enumerate(open(path), 1):
        line = raw.split('#')[0].strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 2:
            raise SystemExit('%s:%d: expected "<df40_pin> <dip48_pin>", got %r'
                             % (path, lineno, raw.strip()))
        try:
            df40 = int(parts[0])
        except ValueError:
            raise SystemExit('%s:%d: DF40 pin %r is not a number' % (path, lineno, parts[0]))
        if parts[1] == '?':
            blank.append(df40)
            continue
        try:
            dip = None if parts[1] == '-' else int(parts[1])
        except ValueError:
            raise SystemExit('%s:%d: %r is not a DIP48 pin number, "-" or "?"'
                             % (path, lineno, parts[1]))
        if df40 in got:
            raise SystemExit('%s:%d: DF40 pin %d recorded twice' % (path, lineno, df40))
        got[df40] = dip
    return got, blank


def check_emmc(path):
    probes = emmc_probes()
    got, blank = parse_emmc(path)
    expected = sorted(probes)
    missing = [p for p in expected if p not in got]
    if blank:
        print('%d of %d pins are still "?" -- not measured yet: %s'
              % (len(blank), len(expected), ', '.join(map(str, sorted(blank)))))
    extra = [p for p in got if p not in probes]

    print('read %d readings from %s' % (len(got), path))
    if missing:
        print('  NOT MEASURED: %s' % ', '.join(map(str, missing)))
    if extra:
        print('  note: readings for unused pins %s (ignored for the verdict)'
              % ', '.join(map(str, sorted(extra))))

    opens = [p for p in expected if p in got and got[p] is None]
    if opens:
        print()
        print('OPEN CIRCUIT on %d pin(s): %s' % (len(opens), ', '.join(map(str, opens))))
        print('  A used pin that does not ring is a dead signal. Re-seat the')
        print('  probes before believing it.')

    # Two distinct DF40 signals landing on the same DIP48 pin is a short or
    # a bussed pin on the adapter, not a mapping worth recording.
    by_dip = {}
    for p in expected:
        if p in got and got[p] is not None:
            by_dip.setdefault(got[p], []).append(p)
    dups = {dip: ps for dip, ps in by_dip.items() if len(ps) > 1}

    if dups:
        print()
        print('DUPLICATE DIP48 ASSIGNMENT:')
        for dip, ps in sorted(dups.items()):
            names = ', '.join('DF40 %d (%s)' % (p, probes[p]) for p in ps)
            print('  DIP48 %d rang for more than one DF40 pin: %s' % (dip, names))
        print('  Two different signals cannot share one DIP48 pin. This is a')
        print('  short or a bussed pin on the adapter -- not a mapping to record.')

    print()
    if not opens and not dups and not missing:
        print('PASS - all %d probed pins reached a distinct DIP48 pin.' % len(expected))
        print('       Record the DF40<->DIP48 map in docs/connector-pinout.md')
        print('       before routing base_variants/emmc/.')
        return 0

    print('FAIL - base_variants/emmc/ stays unrouted until this passes.')
    return 1


def main(argv):
    family = 'nand_x8'
    if argv and argv[0] == '--family':
        if len(argv) < 2:
            raise SystemExit('--family requires an argument')
        family = argv[1]
        argv = argv[2:]

    if family == 'nand_x8':
        return check(argv[0]) if argv else (checklist() or 0)
    elif family == 'emmc':
        return check_emmc(argv[0]) if argv else (checklist_emmc() or 0)
    else:
        raise SystemExit('unknown family %r (expected nand_x8 or emmc)' % family)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
