"""VFBGA67 (6.5x8.0mm, 0.8mm pitch, 8x10 layout) — shipped nand_x8 carrier chip."""
NAME = 'vfbga67'
FAMILY = 'nand_x8'
BODY_MM = (6.5, 8.0)
PITCH_MM = 0.8
LAND_MM = 0.40          # matches the shipped BGA-67 footprint's pad diameter
GRID = ('ABCDEFGHJK', 8)  # 10 rows x 8 cols, 67 populated
PROVENANCE = ('Transcribed from the shipped carrier board '
              '(carrier/carrier.kicad_pcb U1 pad nets); LAND_MM and GRID verified '
              'against carrier/lib/carrier.pretty/'
              'BGA-67_6.5x8.0mm_Layout8x10_P0.8mm.kicad_mod. Bench ring-out pending '
              '(docs/ringout-results.txt is an unfilled template).')
BALLS = {
    # ball: signal | 'VCC' | 'GND' | None (NC) — transcribed from U1 pad
    # nets on carrier/carrier.kicad_pcb, in row-major order.
    'A2': None, 'A3': None, 'A6': None, 'A7': None, 'A8': None,
    'B1': None, 'B2': '/WP', 'B3': 'ALE', 'B4': 'GND', 'B5': '/CE',
    'B6': '/WE', 'B7': 'RY//BY', 'B8': None,
    'C1': None, 'C2': None, 'C3': '/RE', 'C4': 'CLE', 'C5': None,
    'C6': None, 'C7': None, 'C8': None,
    'D2': None, 'D3': None, 'D4': None, 'D5': None, 'D6': None, 'D7': None,
    'E2': None, 'E3': None, 'E4': None, 'E5': None, 'E6': None, 'E7': None,
    'F2': None, 'F3': None, 'F4': None, 'F5': None, 'F6': None, 'F7': None,
    'G2': None, 'G3': 'IO1', 'G4': None, 'G5': None, 'G6': None, 'G7': 'VCC',
    'H1': None, 'H2': None, 'H3': 'IO2', 'H4': None, 'H5': 'VCC',
    'H6': 'IO6', 'H7': 'IO8', 'H8': None,
    'J1': None, 'J2': 'GND', 'J3': 'IO3', 'J4': 'IO4', 'J5': 'IO5',
    'J6': 'IO7', 'J7': 'GND', 'J8': None,
    'K1': None, 'K2': None, 'K3': None, 'K6': None, 'K7': None, 'K8': None,
}
