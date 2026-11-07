"""Build the project library hardware/lib/OpenSpandSMD.{kicad_sym,pretty}.

Symbols are simple boxes generated here. Footprints:
  ZX-EDGE64-2, DSUB-9 ... : copied unchanged from upstream OpenSpand V1.31 (CC BY-SA 4.0)
  TF-01A, SW_TS-1187A,
  RCJ-014                 : converted from LCSC/EasyEDA with easyeda2kicad, then cleaned up
  ZX81_EdgeFingers        : generated here (card edge that plugs into a ZX81-style socket)
"""
import os
import re
import shutil
import sys

from kisexp import S, Sym, dump

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, 'hardware', 'lib')
UPSTREAM = sys.argv[1] if len(sys.argv) > 1 else None  # path to OpenSpand_HW/V1.31
KICAD_INDUCTOR = os.environ.get('KICAD_INDUCTOR', '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/'
                                'Inductor_SMD.pretty/L_Murata_DFE201610P.kicad_mod')

G = 2.54


def prop(name, value, x=0, y=0, hide=False):
    eff = S('effects', S('font', S('size', 1.27, 1.27)))
    if hide:
        eff.append(S('hide', Sym('yes')))
    return S('property', name, value, S('at', x, y, 0), eff)


def box_symbol(name, ref, descr, left, right, fp=''):
    """left/right: lists of (number, name, type) or None for a gap."""
    rows = max(len(left), len(right))
    longest = max([len(p[1]) for p in left + right if p] + [4])
    w = round((longest * 1.27 * 2 + 5.08) / G) * G
    h = (rows + 1) * G
    top = ((rows - 1) // 2) * G  # keeps every pin on the 2.54 grid
    body = S('symbol', name + '_0_1',
             S('rectangle', S('start', -w / 2, top + G), S('end', w / 2, top - rows * G),
               S('stroke', S('width', 0.254), S('type', Sym('default'))),
               S('fill', S('type', Sym('background')))))
    pins = S('symbol', name + '_1_1')
    for side, plist in ((0, left), (1, right)):
        for i, p in enumerate(plist):
            if not p:
                continue
            num, pname, ptype = p
            y = top - i * G
            x = -w / 2 - G if side == 0 else w / 2 + G
            pins.append(S('pin', Sym(ptype), Sym('line'), S('at', x, y, 0 if side == 0 else 180),
                          S('length', G),
                          S('name', pname, S('effects', S('font', S('size', 1.27, 1.27)))),
                          S('number', num, S('effects', S('font', S('size', 1.27, 1.27))))))
    return S('symbol', name,
             S('exclude_from_sim', Sym('no')), S('in_bom', Sym('yes')), S('on_board', Sym('yes')),
             prop('Reference', ref, 0, top + G + 1.27),
             prop('Value', name, 0, top - rows * G - 1.27),
             prop('Footprint', fp, hide=True),
             prop('Datasheet', '', hide=True),
             prop('Description', descr, hide=True),
             body, pins)


def edge_symbol():
    names = {'A5': '~{ROMCS}', 'A6': 'A4', 'A7': 'A5', 'A8': 'A6', 'A9': 'A7',
             'A10': 'A8', 'A11': 'A9', 'A12': 'A10', 'A13': 'A11', 'A14': 'A12',
             'A15': 'A13', 'A16': 'A14', 'A17': 'A15', 'A18': 'A3', 'A19': 'A2',
             'A20': 'A1', 'A21': 'A0', 'A22': 'CLK', 'A23': '0V', 'A24': '0V',
             'A25': 'KEY', 'A26': '+9V', 'A27': '+5V',
             'C5': '~{RFSH}', 'C6': '~{M1}', 'C7': '~{RESET}', 'C8': '~{BUSRQ}',
             'C9': '~{WAIT}', 'C10': '~{BUSAK}', 'C11': '~{WR}', 'C12': '~{RD}',
             'C13': '~{IORQ}', 'C14': '~{MREQ}', 'C15': '~{HALT}', 'C16': '~{NMI}',
             'C17': '~{INT}', 'C18': 'D4', 'C19': 'D3', 'C20': 'D5', 'C21': 'D6',
             'C22': 'D2', 'C23': 'D1', 'C24': 'D0', 'C25': '~{BUSCS}', 'C26': '~{RAMCS}',
             'C27': 'D7'}
    # position 3 (A25/C25) is the key slot: no finger, so no pin
    left = [('A%d' % i, names['A%d' % i], 'passive') if i != 25 else None for i in range(5, 28)]
    right = [('C%d' % i, names['C%d' % i], 'passive') if i != 25 else None for i in range(5, 28)]
    return box_symbol('ZX81_Edge', 'J', 'ZX80/ZX81 expansion edge (A: address/power side, C: data/control side)',
                      left, right, 'OpenSpandSMD:ZX81_EdgeFingers')


# ZX81 edge geometry: 23 positions at 0.1 in, the key slot at position 3.
# Position p carries symbol pins A(28-p) and C(28-p); see edge_symbol().
EDGE_POSITIONS = 23
EDGE_SLOT_POS = 3
EDGE_PITCH = 2.54
EDGE_TONGUE_W = EDGE_POSITIONS * EDGE_PITCH   # 58.42
EDGE_TONGUE_H = 8.0                           # finger strip below the card body
EDGE_FINGER_W = 1.65
EDGE_FINGER_H = 7.0
EDGE_FINGER_GAP = 0.7                         # finger end to the bevelled edge (clear of the corner chamfers)
EDGE_SLOT_W = 2.03
EDGE_SLOT_D = 7.4
EDGE_CHAMFER = 0.5


def edge_fingers_footprint():
    """Gold fingers for a card standing in a ZX81-style edge socket.

    Origin: top-left corner of the tongue (where its left side meets the card
    body). Seen from the front (F.Cu), position 1 is on the left, as on the
    ZX81's own edge seen from above: F.Cu carries the C row (D7, ~RAMCS, key,
    D0 ... ~RFSH), B.Cu the A row (+5V, +9V, key, 0V ... ~ROMCS). The tongue
    and slot outline is drawn by gen_pcb.py.
    """
    fy = EDGE_TONGUE_H - EDGE_FINGER_GAP - EDGE_FINGER_H / 2
    items = [S('version', 20241229), S('generator', 'openspand_gen_lib'), S('layer', 'F.Cu'),
             S('descr', 'ZX81 expansion edge, 2x23 positions at 2.54 mm, key slot at position 3, gold fingers'),
             S('tags', 'ZX81 edge connector card'),
             S('property', 'Reference', 'J**', S('at', 2, -1.5, 0), S('layer', 'F.SilkS'),
               S('effects', S('font', S('size', 1, 1), S('thickness', 0.15)))),
             S('property', 'Value', 'ZX81_EdgeFingers', S('at', EDGE_TONGUE_W / 2, -3, 0), S('layer', 'F.Fab'),
               S('effects', S('font', S('size', 1, 1), S('thickness', 0.15)))),
             S('attr', Sym('smd'), Sym('exclude_from_pos_files'))]
    for layer in ('F.CrtYd', 'B.CrtYd'):
        items.append(S('fp_rect', S('start', -0.25, 0.05), S('end', EDGE_TONGUE_W + 0.25, EDGE_TONGUE_H + 0.25),
                       S('stroke', S('width', 0.05), S('type', Sym('solid'))), S('fill', Sym('no')), S('layer', layer)))
    items.append(S('fp_rect', S('start', 0, 0), S('end', EDGE_TONGUE_W, EDGE_TONGUE_H),
                   S('stroke', S('width', 0.1), S('type', Sym('solid'))), S('fill', Sym('no')), S('layer', 'F.Fab')))
    for p in range(1, EDGE_POSITIONS + 1):
        if p == EDGE_SLOT_POS:
            continue
        x = EDGE_PITCH / 2 + (p - 1) * EDGE_PITCH
        for row, layers in (('C', ('F.Cu', 'F.Mask')), ('A', ('B.Cu', 'B.Mask'))):
            items.append(S('pad', '%s%d' % (row, 28 - p), Sym('smd'), Sym('rect'), S('at', round(x, 4), round(fy, 4)),
                           S('size', EDGE_FINGER_W, EDGE_FINGER_H), S('layers', *layers)))
    return S('footprint', 'ZX81_EdgeFingers', *items)


def de9_symbol():
    left = [('1', 'UP', 'passive'), ('2', 'DOWN', 'passive'), ('3', 'LEFT', 'passive'),
            ('4', 'RIGHT', 'passive'), ('6', 'FIRE', 'passive')]
    right = [('5', 'P5', 'passive'), ('7', 'P7', 'passive'), ('8', 'GND', 'passive'),
             ('9', 'P9', 'passive'), ('0', 'SHIELD', 'passive')]
    return box_symbol('DE9_Male', 'J', 'DE-9 male, Atari joystick pinout', left, right)


def mcp23009_symbol():
    left = [('1', 'VDD', 'power_in'), ('3', 'SCL', 'input'), ('4', 'SDA', 'bidirectional'),
            ('5', 'ADDR', 'input'), ('6', '~{RESET}', 'input'), ('7', 'INT', 'open_collector'),
            ('20', 'VSS', 'power_in'), None, ('2', 'NC', 'no_connect'), ('10', 'NC', 'no_connect'),
            ('11', 'NC', 'no_connect')]
    right = [('8', 'GP0', 'bidirectional'), ('9', 'GP1', 'bidirectional'),
             ('12', 'GP2', 'bidirectional'), ('13', 'GP3', 'bidirectional'),
             ('14', 'GP4', 'bidirectional'), ('15', 'GP5', 'bidirectional'),
             ('16', 'GP6', 'bidirectional'), ('17', 'GP7', 'bidirectional'), None,
             ('18', 'NC', 'no_connect'), ('19', 'NC', 'no_connect')]
    return box_symbol('MCP23009-E_SS', 'U', 'MCP23009 8-bit open-drain I2C I/O expander, SSOP-20',
                      left, right, 'Package_SO:SSOP-20_5.3x7.2mm_P0.65mm')


def microsd_symbol():
    left = [('2', 'DAT3/CS', 'bidirectional'), ('3', 'CMD/DI', 'input'), ('5', 'CLK', 'input'),
            ('7', 'DAT0/DO', 'bidirectional'), ('8', 'DAT1', 'bidirectional'),
            ('1', 'DAT2', 'bidirectional'), ('9', 'CD', 'passive')]
    right = [('4', 'VDD', 'power_in'), ('6', 'VSS', 'power_in'), None,
             ('10', 'SHIELD', 'passive'), ('11', 'SHIELD', 'passive'),
             ('12', 'SHIELD', 'passive'), ('13', 'SHIELD', 'passive')]
    return box_symbol('MicroSD_TF-01A', 'J', 'microSD push-push socket (TF-01A)', left, right,
                      'OpenSpandSMD:TF-01A')


def lvc3g34_symbol():
    left = [('1', '1A', 'input'), ('3', '2A', 'input'), ('6', '3A', 'input'), None,
            ('8', 'VCC', 'power_in')]
    right = [('7', '1Y', 'output'), ('5', '2Y', 'output'), ('2', '3Y', 'output'), None,
             ('4', 'GND', 'power_in')]
    return box_symbol('74LVC3G34', 'U', 'Triple buffer, 74LVC3G34 (DCU / VSSOP-8 pinout)',
                      left, right, 'Package_SO:VSSOP-8_2.3x2mm_P0.5mm')


def tpd4e05u06_symbol():
    """Flow-through ESD array: each line enters on one side and leaves on the other, so
    pads 1-10, 2-9, 4-7 and 5-6 carry the same line (KiCad's own symbol marks 6-10 NC)."""
    left = [('1', 'IO1', 'passive'), ('2', 'IO2', 'passive'), ('4', 'IO3', 'passive'),
            ('5', 'IO4', 'passive'), None, ('3', 'GND', 'passive')]
    right = [('10', 'IO1', 'passive'), ('9', 'IO2', 'passive'), ('7', 'IO3', 'passive'),
             ('6', 'IO4', 'passive'), None, ('8', 'GND', 'passive')]
    return box_symbol('TPD4E05U06', 'U', 'TPD4E05U06DQA 4-channel flow-through ESD protection, USON-10',
                      left, right, 'Package_SON:USON-10_2.5x1.0mm_P0.5mm')


def write_symbols():
    lib = S('kicad_symbol_lib', S('version', 20241209), S('generator', 'openspand_gen_lib'),
            S('generator_version', '9.0'),
            edge_symbol(), de9_symbol(), mcp23009_symbol(), microsd_symbol(),
            lvc3g34_symbol(), tpd4e05u06_symbol())
    with open(os.path.join(LIB, 'OpenSpandSMD.kicad_sym'), 'w') as f:
        f.write(dump(lib) + '\n')


def fix_easyeda(src, dst, rename=None):
    t = open(src).read()
    t = re.sub(r'\(model "[^"]*/([^/"]+)"', r'(model "${KIPRJMOD}/lib/OpenSpandSMD.3dshapes/\1"', t)
    if rename:
        t = rename(t)
    open(dst, 'w').write(t)


def ltst_s270_footprint():
    """Lite-On LTST-S270 side-looking 0603 LED (LTST-S270KRKT red, -KGKT green).

    Datasheet "Suggest Soldering Pad Dimensions": two 1.10 x 1.10 mm pads, 0.90 mm apart.
    Package: 1.65 mm along the pads, 1.20 mm tall, 0.68 mm deep plus the lens (1.15 mm in
    all). The lens looks out sideways, towards -y here, so with the footprint unrotated
    the light leaves through the board's top edge. Pad 1 is the cathode, as KiCad's
    Device:LED expects; check the part's cathode mark against it in JLC's preview.
    """
    def line(a, b, layer, w):
        return S('fp_line', S('start', *a), S('end', *b), S('stroke', S('width', w), S('type', Sym('solid'))),
                 S('layer', layer))
    items = [S('version', 20241229), S('generator', 'openspand_gen_lib'), S('layer', 'F.Cu'),
             S('descr', 'Lite-On LTST-S270 side-looking LED, 1.65 x 1.2 mm, lens towards -y; pads per datasheet'),
             S('tags', 'LED side view right angle LTST-S270'),
             S('property', 'Reference', 'REF**', S('at', 0, 1.6, 0), S('layer', 'F.SilkS'),
               S('effects', S('font', S('size', 0.8, 0.8), S('thickness', 0.12)))),
             S('property', 'Value', 'LTST-S270', S('at', 0, 2.8, 0), S('layer', 'F.Fab'),
               S('effects', S('font', S('size', 0.8, 0.8), S('thickness', 0.12)))),
             S('attr', Sym('smd'))]
    # body (behind the lens) and lens on F.Fab
    for a, b in (((-0.825, -0.34), (0.825, -0.34)), ((0.825, -0.34), (0.825, 0.34)),
                 ((0.825, 0.34), (-0.825, 0.34)), ((-0.825, 0.34), (-0.825, -0.34)),
                 ((-0.4, -0.34), (-0.4, -0.81)), ((-0.4, -0.81), (0.4, -0.81)), ((0.4, -0.81), (0.4, -0.34))):
        items.append(line(a, b, 'F.Fab', 0.1))
    # cathode bar on the silkscreen, beside pad 1, clear of the pads
    items.append(line((-1.0, 0.75), (-1.0, 0.95), 'F.SilkS', 0.12))
    items.append(line((-1.7, 0.85), (-0.3, 0.85), 'F.SilkS', 0.12))
    items.append(S('fp_rect', S('start', -1.8, -1.0), S('end', 1.8, 0.8),
                   S('stroke', S('width', 0.05), S('type', Sym('solid'))), S('fill', Sym('no')), S('layer', 'F.CrtYd')))
    for num, x in (('1', -1.0), ('2', 1.0)):
        items.append(S('pad', num, Sym('smd'), Sym('rect'), S('at', x, 0), S('size', 1.1, 1.1),
                       S('layers', 'F.Cu', 'F.Paste', 'F.Mask')))
    return S('footprint', 'LED_LiteOn_LTST-S270', *items)


def write_footprints():
    pretty = os.path.join(LIB, 'OpenSpandSMD.pretty')
    shapes = os.path.join(LIB, 'OpenSpandSMD.3dshapes')
    os.makedirs(pretty, exist_ok=True)
    os.makedirs(shapes, exist_ok=True)
    if UPSTREAM:
        for n in ('ZX-EDGE64-2', 'DSUB-9_Male_Horizontal_P2.77x2.84mm_EdgePinOffset4.94mm_Housed_MountingHolesOffset7.48mm'):
            shutil.copy(os.path.join(UPSTREAM, '1.3.1Library.pretty', n + '.kicad_mod'), pretty)
    ee = os.path.join(LIB, 'easyeda.pretty')
    if os.path.isdir(os.path.join(LIB, 'easyeda.3dshapes')):  # the card keeps only the copies in OpenSpandSMD.3dshapes
        for f in os.listdir(os.path.join(LIB, 'easyeda.3dshapes')):
            shutil.copy(os.path.join(LIB, 'easyeda.3dshapes', f), shapes)
    with open(os.path.join(pretty, 'ZX81_EdgeFingers.kicad_mod'), 'w') as f:
        f.write(dump(edge_fingers_footprint()) + '\n')
    with open(os.path.join(pretty, 'LED_LiteOn_LTST-S270.kicad_mod'), 'w') as f:
        f.write(dump(ltst_s270_footprint()) + '\n')
    fix_easyeda(os.path.join(ee, 'TF-SMD_TF-01A.kicad_mod'), os.path.join(pretty, 'TF-01A.kicad_mod'),
                lambda t: re.sub(r'\(pad "" thru_hole circle (\(at [^)]*\)) \(size ([0-9.]+) ([0-9.]+)\) \(drill [0-9.]+\) \(layers [^)]*\)',
                                 r'(pad "" np_thru_hole circle \1 (size \2 \3) (drill \2) (layers *.Cu *.Mask)', t)
                .replace('(footprint "TF-SMD_TF-01A"', '(footprint "TF-01A"')
                           .replace('(module easyeda2kicad:TF-SMD_TF-01A', '(module TF-01A'))

    # Tactile switch: only the diagonal pads 1 and 4 are used, so the part works
    # whichever way its internal contact pairs run. Pad 4 becomes "2" to match SW_Push.
    def sw(t):
        t = t.replace('easyeda2kicad:SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5', 'SW_TS-1187A', 1)
        t = re.sub(r'\(pad 2 ', '(pad "" ', t)
        t = re.sub(r'\(pad 3 ', '(pad "" ', t)
        t = re.sub(r'\(pad 4 ', '(pad 2 ', t)
        return t
    fix_easyeda(os.path.join(ee, 'SW-SMD_4P-L5.1-W5.1-P3.70-LS6.5-TL_H1.5.kicad_mod'),
                os.path.join(pretty, 'SW_TS-1187A.kicad_mod'), sw)

    # RCA jack (CUI RCJ-014; EasyEDA shares the RCJ-013 drawing). The pads are
    # renumbered to match Connector:Conn_Coaxial: 1 centre pin, 2 shell.
    def rca(t):
        t = t.replace('easyeda2kicad:CONN-TH_RCJ-013', 'RCJ-014', 1)
        t = re.sub(r'\(pad 1 ', '(pad S ', t)
        t = re.sub(r'\(pad 2 ', '(pad 1 ', t)
        return t.replace('(pad S ', '(pad 2 ')
    fix_easyeda(os.path.join(ee, 'CONN-TH_RCJ-013.kicad_mod'), os.path.join(pretty, 'RCJ-014.kicad_mod'), rca)

    # RP2350 regulator inductor (Abracon AOTA-B201610S3R3-101-T): KiCad's 2016 land
    # pattern plus a silkscreen dot at pad 1. The part's dot must sit at the regulator
    # output (+1V1), per RP2350 datasheet figures 25 and 28, so pad 1 is +1V1.
    with open(KICAD_INDUCTOR) as f:
        t = f.read()
    t = t.replace('(footprint "L_Murata_DFE201610P"', '(footprint "L_AOTA-B201610"', 1)
    t = re.sub(r'\(descr "[^"]*"\)', '(descr "Abracon AOTA-B201610S3R3-101-T, 2.0x1.6 mm, '
               'polarity dot at pad 1 (RP2350 regulator output)")', t, count=1)
    t = t.replace('(start -1.25 -1.05)', '(start -1.75 -1.05)', 1)  # courtyard takes in the dot
    dot = ('\t(fp_circle (center -1.45 -0.75) (end -1.3 -0.75) (stroke (width 0.1) (type solid)) '
           '(fill yes) (layer "F.SilkS"))\n'
           '\t(fp_circle (center -0.75 -0.55) (end -0.65 -0.55) (stroke (width 0.05) (type solid)) '
           '(fill yes) (layer "F.Fab"))\n')
    t = t.replace('\t(model ', dot + '\t(model ', 1)
    with open(os.path.join(pretty, 'L_AOTA-B201610.kicad_mod'), 'w') as f:
        f.write(t)


if __name__ == '__main__':
    write_symbols()
    write_footprints()
