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
# Measured from the plug footprint's F.Courtyard bounding box (KiCad 10.0.5):
# GetBoundingBox().GetWidth() == 8_070_000 nm exactly.  The brief's 11.34 mm
# placeholder was the full pad-span bbox, not the courtyard; the courtyard is
# the correct "keep-out body" figure for the outline formula below.
DF40_BODY_MM = 8.07
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
    out_path = pathlib.Path(out_path)
    board = pcbnew.NewBoard(str(out_path))
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
    fp_dir = out_path.parent / 'lib' / (pkg.NAME + '.pretty')
    normal, mirrored = gen_footprint.generate(pkg, fp_dir)
    u1 = load_footprint(fp_dir, (mirrored if role == 'carrier' else normal).stem)
    u1.SetReference('U1')
    u1.SetValue(pkg.NAME.upper() + '_INTERFACE')
    board.Add(u1)
    u1.SetPosition(CENTRE)
    if role == 'carrier':
        # The land field's row/column axes run 90 degrees off the board's
        # DF40 escape axis on the shipped carrier (see carrier/carrier.kicad_pcb
        # U1: orientation 90, FPID *_Mirrored_Interposer).  Rotate before the
        # mirror-flip so the flip's -90 -> 90 fixed point reproduces that
        # placement exactly (verified pad-for-pad against the shipped board).
        u1.SetOrientationDegrees(90)
        if u1.GetLayer() != pcbnew.B_Cu:
            u1.Flip(u1.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
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
        j1.Flip(j1.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    pin_nets = families.net_map(pkg.FAMILY)
    for pad in j1.Pads():
        number = str(pad.GetNumber())
        if number.isdigit():
            logical = pin_nets[int(number)]
            if not logical.startswith('NC_'):
                pad.SetNet(nets[logical])
        elif number.startswith('MT'):
            # DF40 mechanical/shield tabs; tied to GND on the shipped boards.
            pad.SetNet(nets['GND'])

    # Outline.
    w = max(pkg.BODY_MM[0], DF40_BODY_MM) + 1.0
    h = pkg.BODY_MM[1] + 1.6
    w, h = round(w, 2), round(h, 2)
    cx, cy = pcbnew.ToMM(CENTRE.x), pcbnew.ToMM(CENTRE.y)
    corners = [(cx - w / 2, cy - h / 2), (cx + w / 2, cy - h / 2),
               (cx + w / 2, cy + h / 2), (cx - w / 2, cy + h / 2)]
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
