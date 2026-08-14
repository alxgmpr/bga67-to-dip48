"""eMMC BGA-153 (11.5x13.0mm, 0.5mm pitch, 14x14 grid, 153 populated)."""
NAME = 'emmc_bga153'
FAMILY = 'emmc'
BODY_MM = (11.5, 13.0)
PITCH_MM = 0.5
LAND_MM = 0.25          # NSMD land for 0.30 mm balls at 0.5 mm pitch
GRID = ('ABCDEFGHJKLMNP', 14)   # skips I, O per the JEDEC drawing; 14 rows x 14 cols
PROVENANCE = (
    'Micron "e.MMC Memory MTFC32GANALEA-WT, MTFC64GANALAM-WT" production '
    'datasheet, doc 153ball_emmc_v51_100s_j37y_j38y.pdf, Rev. D 10/17 EN '
    '(CCMTD-284460984-10446); JEDEC/MMC standard version 5.1-compliant per '
    'JEDEC Standard No. JESD84-B51 (per datasheet Features section). Ball '
    'positions from Figure 3 "153-Ball (Top View, Ball Down)" (p.8); symbol '
    'definitions (VCCM/VCCQM/VSS/VDDIM/NC/RFU/VSF) from Table 5 "e.MMC Ball '
    'Descriptions" (p.9); pitch (0.5mm TYP), body (11.5 x 13.0mm) and row '
    'lettering A-P confirmed against Figure 4 "153-Ball WFBGA - 11.5mm x '
    '13.0mm x 0.8mm (Package Code: EA)" (p.10). Retrieved via DigiKey\'s '
    'public document server (mm.digikey.com), no login required; the PDF '
    'carries a "Micron Confidential and Proprietary" header despite being '
    'served without authentication, noted here for transparency. Full '
    'literal transcription (JEDEC symbols, all 153 balls) recorded in '
    'docs/ballouts/emmc_bga153.txt; this dict is generated from that file '
    '(VCCM->VCC, VCCQM->VCCQ, VSS->GND, VDDIM->AUX_VDDI, NC->None; RFU and '
    'the internally-tied vendor-specific VSF2-VSF7 balls also ->None, as '
    'this design assigns them no function, same as NC).'
)
BALLS = {
    # Generated from docs/ballouts/emmc_bga153.txt; see PROVENANCE for the
    # symbol-to-signal mapping rules. Do not hand-edit without regenerating.
    'A1': None, 'A2': None, 'A3': 'DAT0', 'A4': 'DAT1', 'A5': 'DAT2',
    'A6': 'GND', 'A7': None, 'A8': None, 'A9': None, 'A10': None,
    'A11': None, 'A12': None, 'A13': None, 'A14': None,
    'B1': None, 'B2': 'DAT3', 'B3': 'DAT4', 'B4': 'DAT5', 'B5': 'DAT6',
    'B6': 'DAT7', 'B7': None, 'B8': None, 'B9': None, 'B10': None,
    'B11': None, 'B12': None, 'B13': None, 'B14': None,
    'C1': None, 'C2': 'AUX_VDDI', 'C3': None, 'C4': 'GND', 'C5': None,
    'C6': 'VCCQ', 'C7': None, 'C8': None, 'C9': None, 'C10': None,
    'C11': None, 'C12': None, 'C13': None, 'C14': None,
    'D1': None, 'D2': None, 'D3': None, 'D4': None,
    'D12': None, 'D13': None, 'D14': None,
    'E1': None, 'E2': None, 'E3': None, 'E5': None, 'E6': 'VCC',
    'E7': 'GND', 'E8': None, 'E9': None, 'E10': None,
    'E12': None, 'E13': None, 'E14': None,
    'F1': None, 'F2': None, 'F3': None, 'F5': 'VCC', 'F10': None,
    'F12': None, 'F13': None, 'F14': None,
    'G1': None, 'G2': None, 'G3': None, 'G5': 'GND', 'G10': None,
    'G12': None, 'G13': None, 'G14': None,
    'H1': None, 'H2': None, 'H3': None, 'H5': 'DS', 'H10': 'GND',
    'H12': None, 'H13': None, 'H14': None,
    'J1': None, 'J2': None, 'J3': None, 'J5': 'GND', 'J10': 'VCC',
    'J12': None, 'J13': None, 'J14': None,
    'K1': None, 'K2': None, 'K3': None, 'K5': 'RST_n', 'K6': None,
    'K7': None, 'K8': 'GND', 'K9': 'VCC', 'K10': None,
    'K12': None, 'K13': None, 'K14': None,
    'L1': None, 'L2': None, 'L3': None,
    'L12': None, 'L13': None, 'L14': None,
    'M1': None, 'M2': None, 'M3': None, 'M4': 'VCCQ', 'M5': 'CMD',
    'M6': 'CLK', 'M7': None, 'M8': None, 'M9': None, 'M10': None,
    'M11': None, 'M12': None, 'M13': None, 'M14': None,
    'N1': None, 'N2': 'GND', 'N3': None, 'N4': 'VCCQ', 'N5': 'GND',
    'N6': None, 'N7': None, 'N8': None, 'N9': None, 'N10': None,
    'N11': None, 'N12': None, 'N13': None, 'N14': None,
    'P1': None, 'P2': None, 'P3': 'VCCQ', 'P4': 'GND', 'P5': 'VCCQ',
    'P6': 'GND', 'P7': None, 'P8': None, 'P9': None, 'P10': None,
    'P11': None, 'P12': None, 'P13': None, 'P14': None,
}
