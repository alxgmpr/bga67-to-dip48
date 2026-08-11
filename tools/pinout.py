# Canonical J1 pinout - single source of truth for both boards and the docs.
# Pins 7-26 reproduce Courk's ten DF17 pin pairs, in order.  The 30-pin DF40
# has five surplus pair-columns; those ten contacts are ground returns.
DF40 = {
   1:'GND',    2:'GND',  3:'GND',  4:'GND', 5:'GND', 6:'GND',
   7:'RY//BY', 8:'ALE',  9:'/WE', 10:'/WP', 11:'/CE', 12:'/RE',
  13:'CLE',   14:'VCC', 15:'GND', 16:'GND', 17:'GND', 18:'IO5',
  19:'GND',   20:'IO2', 21:'IO6', 22:'IO1', 23:'IO8', 24:'IO3',
  25:'IO7',   26:'IO4', 27:'GND', 28:'GND', 29:'GND', 30:'GND',
}
def check():
    sig=lambda n: n not in ('GND','VCC')
    courk_pairs = [
        ('RY//BY', 'ALE'), ('/WE', '/WP'), ('/CE', '/RE'), ('CLE', 'VCC'),
        ('GND', 'GND'), ('GND', 'IO5'), ('GND', 'IO2'), ('IO6', 'IO1'),
        ('IO8', 'IO3'), ('IO7', 'IO4'),
    ]
    assert [(DF40[p], DF40[p + 1]) for p in range(7, 27, 2)] == courk_pairs
    assert all(DF40[p] == 'GND' for p in (*range(1, 7), *range(27, 31)))
    nets=[v for v in DF40.values() if sig(v)]
    assert sorted(nets)==sorted(['IO%d'%i for i in range(1,9)]+['/CE','/RE','/WE','/WP','CLE','ALE','RY//BY']), nets
    assert list(DF40.values()).count('VCC')==1
    return True
if __name__=='__main__':
    check()
    print("Courk topology OK: DF17 pair order preserved on DF40 pins 7-26")
    print(f"  odd  row: {[(p,DF40[p]) for p in range(1,31,2)]}")
    print(f"  even row: {[(p,DF40[p]) for p in range(2,31,2)]}")
    print(f"  GND x{list(DF40.values()).count('GND')}  VCC x1  signals x15")
