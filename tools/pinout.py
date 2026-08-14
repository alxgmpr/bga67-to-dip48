# Canonical J1 pinout - single source of truth for both boards and schematics.
#
# This is the already-routed carrier pinout.  The base receptacle uses the same
# electrical pin numbers: J1.n on the plug must mate with J1.n on the
# receptacle.  Do not apply a second electrical mirror in the base net table;
# the bottom-side receptacle footprint already handles the face-to-face
# mechanical orientation.
DF40 = {
   1:'/WP',  2:'GND',  3:'GND',  4:'/WE',  5:'ALE',  6:'VCC',
   7:'GND',  8:'/CE',  9:'/RE', 10:'VCC', 11:'GND', 12:'RY//BY',
  13:'CLE', 14:'GND', 15:'GND', 16:'IO8', 17:'IO1', 18:'GND',
  19:'GND', 20:'IO6', 21:'IO2', 22:'GND', 23:'GND', 24:'IO7',
  25:'IO3', 26:'GND', 27:'GND', 28:'IO5', 29:'IO4', 30:'GND',
}
# Universal contract positions.  'S' marks the 15 signal positions; families
# assign their signals onto them via tools/families.py.  Pin 10 is the VCCQ
# position: single-supply families strap it to VCC on the base, which is why
# the shipped nand_x8 boards carry net VCC there.
POSITIONS = {
    p: ('GND' if DF40[p] == 'GND' else 'VCC' if p == 6
        else 'VCCQ' if p == 10 else 'S')
    for p in DF40
}

def check():
    sig=lambda n: n not in ('GND','VCC')
    nets=[v for v in DF40.values() if sig(v)]
    assert sorted(nets)==sorted(['IO%d'%i for i in range(1,9)]+['/CE','/RE','/WE','/WP','CLE','ALE','RY//BY']), nets
    assert list(DF40.values()).count('VCC')==2
    assert list(DF40.values()).count('GND')==13
    assert set(DF40)==set(range(1,31))
    return True
if __name__=='__main__':
    check()
    print("same-number DF40 mating contract OK")
    print(f"  odd  row: {[(p,DF40[p]) for p in range(1,31,2)]}")
    print(f"  even row: {[(p,DF40[p]) for p in range(2,31,2)]}")
    print(f"  GND x{list(DF40.values()).count('GND')}  VCC x2  signals x15")
