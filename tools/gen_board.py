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
CENTRE = pcbnew.VECTOR2I(MM(100), MM(100))
# KiCad's own global footprint libraries, installed alongside the KiCad app
# bundle (same install this repo already hardcodes a default path for via
# the Makefile's KICAD_PY/KICAD_CLI).  Used for generic passives referenced
# by a package's CHIP_CAPS -- follows the shipped chip board's own
# convention of pointing straight at "Capacitor_SMD:C_0402_1005Metric"
# rather than vendoring a copy into a project-local .pretty (see
# chip/chip.kicad_pcb, chip/fp-lib-table).
STANDARD_FOOTPRINTS_DIR = pathlib.Path(
    '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')


def board_net_name(logical):
    if logical in ('GND', 'VCC', 'VCCQ') or logical.startswith(('NC_', 'AUX_')):
        return logical
    return '/' + logical.replace('/', '{slash}')


def load_footprint(lib_dir, name):
    io = pcbnew.PCB_IO_KICAD_SEXPR()
    return io.FootprintLoad(str(lib_dir), name)


def load_standard_footprint(fpid):
    """Load 'Lib:Footprint' straight out of KiCad's global libraries."""
    lib, name = fpid.split(':', 1)
    return load_footprint(STANDARD_FOOTPRINTS_DIR / (lib + '.pretty'), name)


def courtyard_span_mm(fp):
    """Width of fp's F.Courtyard bounding box, in mm.

    Falls back to the full footprint bounding box (pads included) if no
    courtyard-layer graphics can be found.  Read right after FootprintLoad,
    before any rotation/flip, so it always sees the library's native F.CrtYd
    layer rather than a post-flip B.CrtYd.
    """
    items = [gi for gi in fp.GraphicalItems() if gi.GetLayer() == pcbnew.F_CrtYd]
    if items:
        bbox = items[0].GetBoundingBox()
        for gi in items[1:]:
            bbox.Merge(gi.GetBoundingBox())
    else:
        bbox = fp.GetBoundingBox()
    return pcbnew.ToMM(bbox.GetWidth())


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
        # Package-specific: some shipped boards seat the land field rotated
        # relative to the DF40 escape axis (see packages/vfbga67.py's
        # CARRIER_ROT_DEG).  Set the pre-flip angle the package asks for
        # (default 0); KiCad's flip then remaps it to 180-theta, which is why
        # vfbga67's 90 degrees reads back as 90 after the flip below (its own
        # fixed point) rather than 0 staying 0.
        u1.SetOrientationDegrees(getattr(pkg, 'CARRIER_ROT_DEG', 0))
        if u1.GetLayer() != pcbnew.B_Cu:
            u1.Flip(u1.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
    for pad in u1.Pads():
        signal = pkg.BALLS.get(str(pad.GetNumber()))
        if signal:
            pad.SetNet(nets[signal])

    # J1: DF40.
    j1 = load_footprint(DF40_LIB, PLUG if role == 'carrier' else RECEPTACLE)
    # Read the connector's own courtyard span before any rotation/flip so the
    # outline formula below uses each role's real footprint extent (the
    # plug's for carrier, the receptacle's for chip) rather than a single
    # shared constant.
    connector_span_mm = courtyard_span_mm(j1)
    j1.SetReference('J1')
    board.Add(j1)
    j1.SetPosition(CENTRE)
    if role == 'carrier':
        j1.SetOrientationDegrees(180)
    if role == 'chip' and j1.GetLayer() != pcbnew.B_Cu:
        # KiCad's flip remaps orientation theta -> 180-theta; a footprint
        # loaded at its native 0 degrees therefore reads back as 180 degrees
        # after this call.  Same side effect build_chip.py's connector.Flip()
        # already relies on for the real chip board.
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

    # Chip-role local decoupling: optional, package-specific.  Each pkg.
    # CHIP_CAPS entry is (ref, value, "Lib:Footprint", net_a, net_b, dx_mm,
    # dy_mm); dx/dy are relative to CENTRE.  Placed on B.Cu with pad "1" ->
    # net_a and pad "2" -> net_b, mirroring build_chip.py's C1/C2 flow for
    # the shipped VFBGA67 chip board, generalized so any package can declare
    # its own local caps instead of that flow being hand-rolled per board.
    if role == 'chip':
        for ref, value, fpid, net_a, net_b, dx, dy in getattr(pkg, 'CHIP_CAPS', []):
            cap = load_standard_footprint(fpid)
            cap.SetReference(ref)
            cap.SetValue(value)
            board.Add(cap)
            cap.SetPosition(pcbnew.VECTOR2I(CENTRE.x + MM(dx), CENTRE.y + MM(dy)))
            if cap.GetLayer() != pcbnew.B_Cu:
                cap.Flip(cap.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
            cap.SetOrientationDegrees(0)
            for pad in cap.Pads():
                number = str(pad.GetNumber())
                if number == '1':
                    pad.SetNet(nets[net_a])
                elif number == '2':
                    pad.SetNet(nets[net_b])
                else:
                    raise AssertionError('unexpected pad %r on %s' % (number, ref))

    # Outline.  Each role's connector footprint sets its own minimum span;
    # the shipped chip board deliberately uses a smaller outline than the
    # receptacle courtyard (8.41 mm vs. 9.15 mm) once routed by hand, so this
    # generated width is a default starting point, not a floor to preserve.
    w = max(pkg.BODY_MM[0], connector_span_mm) + 1.0
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
