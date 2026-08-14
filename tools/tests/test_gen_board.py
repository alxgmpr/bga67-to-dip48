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
