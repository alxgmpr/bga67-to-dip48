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
