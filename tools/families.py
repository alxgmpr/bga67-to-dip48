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
