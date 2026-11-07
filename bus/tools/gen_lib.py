"""Build the project library hardware/lib/ZX81Bus.{kicad_sym,pretty}.

Symbol:
  ZX81_Edge                  : the ZX81 expansion edge, A and C rows (as on the card)
Footprints:
  ZX81_EdgeStraddle          : front edge pads for a card-edge socket whose tails are bent to
                               pinch the board (straddle mount), mating with the ZX81 in its plane
  ZX81_Slot_2x23_...         : vertical card-edge socket, 2x23 at 2.54 mm, rows 5.08 mm apart
  ZX81_EdgeFingers_Rear      : the ZX81's edge repeated as gold fingers on the board's rear edge
"""
import os

from kisexp import S, Sym, dump

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIB = os.path.join(ROOT, 'hardware', 'lib')
NAME = 'ZX81Bus'

G = 2.54
POSITIONS = 23        # 0.1 in positions, numbered 1..23 from the left
KEY_POS = 3           # key slot: no finger, and the socket's polarising key
ROW = 5.08            # slot socket: 0.2 in between the two rows of tails
SLOT_PAD, SLOT_DRILL = 1.5, 1.0
TONGUE_H = 8.0        # finger strip, as on the card
FINGER_W, FINGER_H = 1.65, 7.0
FINGER_GAP = 0.7      # finger end to the bevelled tip
STRADDLE_W, STRADDLE_L = FINGER_W, FINGER_H   # front pads: the same size as the rear fingers
STRADDLE_GAP = 0.3    # front pads start this far in from the edge (copper-to-edge clearance)


def pin_names(p):
    """Footprint pad names at position p: C row (ZX81 top side), A row (underside)."""
    return 'C%d' % (28 - p), 'A%d' % (28 - p)


def prop(name, value, x=0, y=0, hide=False):
    eff = S('effects', S('font', S('size', 1.27, 1.27)))
    if hide:
        eff.append(S('hide', Sym('yes')))
    return S('property', name, value, S('at', x, y, 0), eff)


def edge_symbol():
    names = {'A5': '~{ROMCS}', 'A6': 'A4', 'A7': 'A5', 'A8': 'A6', 'A9': 'A7',
             'A10': 'A8', 'A11': 'A9', 'A12': 'A10', 'A13': 'A11', 'A14': 'A12',
             'A15': 'A13', 'A16': 'A14', 'A17': 'A15', 'A18': 'A3', 'A19': 'A2',
             'A20': 'A1', 'A21': 'A0', 'A22': 'CLK', 'A23': '0V', 'A24': '0V',
             'A26': '+9V', 'A27': '+5V',
             'C5': '~{RFSH}', 'C6': '~{M1}', 'C7': '~{RESET}', 'C8': '~{BUSRQ}',
             'C9': '~{WAIT}', 'C10': '~{BUSAK}', 'C11': '~{WR}', 'C12': '~{RD}',
             'C13': '~{IORQ}', 'C14': '~{MREQ}', 'C15': '~{HALT}', 'C16': '~{NMI}',
             'C17': '~{INT}', 'C18': 'D4', 'C19': 'D3', 'C20': 'D5', 'C21': 'D6',
             'C22': 'D2', 'C23': 'D1', 'C24': 'D0', 'C26': '~{RAMCS}', 'C27': 'D7'}
    rows = 23
    w = 20.32
    top = 11 * G
    body = S('symbol', 'ZX81_Edge_0_1',
             S('rectangle', S('start', -w / 2, top + G), S('end', w / 2, top - rows * G),
               S('stroke', S('width', 0.254), S('type', Sym('default'))),
               S('fill', S('type', Sym('background')))))
    pins = S('symbol', 'ZX81_Edge_1_1')
    for side, row in ((0, 'A'), (1, 'C')):
        for i, n in enumerate(range(5, 28)):
            if n == 25:  # position 3, the key slot
                continue
            num = '%s%d' % (row, n)
            y = top - i * G
            x = -w / 2 - G if side == 0 else w / 2 + G
            pins.append(S('pin', Sym('passive'), Sym('line'), S('at', x, y, 0 if side == 0 else 180),
                          S('length', G),
                          S('name', names[num], S('effects', S('font', S('size', 1.27, 1.27)))),
                          S('number', num, S('effects', S('font', S('size', 1.27, 1.27))))))
    return S('symbol', 'ZX81_Edge',
             S('exclude_from_sim', Sym('no')), S('in_bom', Sym('yes')), S('on_board', Sym('yes')),
             prop('Reference', 'J', 0, top + G + 1.27),
             prop('Value', 'ZX81_Edge', 0, top - rows * G - 1.27),
             prop('Footprint', '', hide=True),
             prop('Datasheet', '', hide=True),
             prop('Description', 'ZX80/ZX81 expansion edge (A: underside, address/power; C: top side, data/control)',
                  hide=True),
             body, pins)


def fp_prop(name, value, x, y, layer, size=1.0):
    return S('property', name, value, S('at', x, y, 0), S('layer', layer),
             S('effects', S('font', S('size', size, size), S('thickness', 0.15))))


def line(a, b, layer, w=0.12):
    return S('fp_line', S('start', *a), S('end', *b), S('stroke', S('width', w), S('type', Sym('solid'))),
             S('layer', layer))


def rect(a, b, layer, w=0.05, fill=False):
    return S('fp_rect', S('start', *a), S('end', *b), S('stroke', S('width', w), S('type', Sym('solid'))),
             S('fill', Sym('yes' if fill else 'no')), S('layer', layer))


def slot_footprint():
    """Vertical card-edge socket for a ZX81-style card.

    Origin: the socket's centre. Position 1 (C27/A27) is on the left. The C row
    (the ZX81's top-side signals) is at +y: on the board that is the row nearer
    the ZX81, so a card's component side faces the ZX81. Position 3 (the key)
    gets plated holes with no net, so an unkeyed socket with all 46 tails fits too.
    """
    name = 'ZX81_Slot_2x23_P2.54mm_Row5.08mm'
    hx = (POSITIONS / 2) * G + 3.8          # body half-length (approx. 0.1 in card-edge socket)
    hy = 3.95                               # body half-width (0.31 in)
    items = [S('version', 20241229), S('generator', 'zx81bus_gen_lib'), S('layer', 'F.Cu'),
             S('descr', 'Vertical card-edge socket for a ZX81-style card: 2x23 positions at 2.54 mm, '
                        'rows 5.08 mm (0.2 in) apart, key at position 3'),
             S('tags', 'ZX81 card edge socket slot'),
             fp_prop('Reference', 'J**', -hx - 2.5, 0, 'F.SilkS'),
             fp_prop('Value', name, 0, hy + 1.5, 'F.Fab'),
             S('attr', Sym('through_hole'))]
    items.append(rect((-hx, -hy), (hx, hy), 'F.SilkS', 0.12))
    items.append(rect((-hx, -hy), (hx, hy), 'F.Fab', 0.1))
    items.append(rect((-hx - 0.3, -hy - 0.3), (hx + 0.3, hy + 0.3), 'F.CrtYd'))
    # card slot in the body, and a block over the key position
    cx = lambda p: (p - (POSITIONS + 1) / 2) * G
    items.append(rect((cx(1) - 1.0, -0.8), (cx(POSITIONS) + 1.0, 0.8), 'F.Fab', 0.1))
    items.append(rect((cx(KEY_POS) - 0.6, -0.8), (cx(KEY_POS) + 0.6, 0.8), 'F.SilkS', 0.12, fill=True))
    # position 1 mark, by the C row (the side the card's components face)
    items.append(S('fp_poly', S('pts', S('xy', cx(1) - 0.9, hy + 0.5), S('xy', cx(1) + 0.9, hy + 0.5),
                                S('xy', cx(1), hy + 1.4)),
                   S('stroke', S('width', 0.1), S('type', Sym('solid'))), S('fill', Sym('yes')),
                   S('layer', 'F.SilkS')))
    for p in range(1, POSITIONS + 1):
        c, a = pin_names(p) if p != KEY_POS else ('', '')
        for num, y in ((c, ROW / 2), (a, -ROW / 2)):
            items.append(S('pad', num, Sym('thru_hole'), Sym('circle'), S('at', round(cx(p), 4), y),
                           S('size', SLOT_PAD, SLOT_PAD), S('drill', SLOT_DRILL),
                           S('layers', '*.Cu', '*.Mask')))
    return name, S('footprint', name, *items)


def rear_fingers_footprint():
    """The ZX81's edge, repeated on the rear edge of the bus board.

    Origin: the left end of the line where the tongue meets the board body; the
    tongue points up (-y). Seen from above, as on the ZX81: position 1 on the
    left, the C row (D7, ~RAMCS, key, D0 ... ~RFSH) on the top copper, the A row
    (+5V, +9V, key, 0V ... ~ROMCS) on the bottom. The outline and key slot are
    drawn by gen_pcb.py.
    """
    name = 'ZX81_EdgeFingers_Rear'
    w = POSITIONS * G
    fy = -(TONGUE_H - FINGER_GAP - FINGER_H / 2)
    items = [S('version', 20241229), S('generator', 'zx81bus_gen_lib'), S('layer', 'F.Cu'),
             S('descr', 'ZX81 expansion edge as gold fingers, 2x23 positions at 2.54 mm, key slot at position 3, '
                        'tongue pointing -y'),
             S('tags', 'ZX81 edge connector fingers'),
             fp_prop('Reference', 'J**', -2.5, -4, 'F.SilkS'),
             fp_prop('Value', name, w / 2, 1.5, 'F.Fab'),
             S('attr', Sym('smd'), Sym('exclude_from_pos_files'))]
    for layer in ('F.CrtYd', 'B.CrtYd'):
        items.append(rect((-0.25, -TONGUE_H - 0.25), (w + 0.25, -0.05), layer))
    items.append(rect((0, -TONGUE_H), (w, 0), 'F.Fab', 0.1))
    for p in range(1, POSITIONS + 1):
        if p == KEY_POS:
            continue
        x = G / 2 + (p - 1) * G
        c, a = pin_names(p)
        for num, layers in ((c, ('F.Cu', 'F.Mask')), (a, ('B.Cu', 'B.Mask'))):
            items.append(S('pad', num, Sym('smd'), Sym('rect'), S('at', round(x, 4), round(fy, 4)),
                           S('size', FINGER_W, FINGER_H), S('layers', *layers)))
    return name, S('footprint', name, *items)


def straddle_footprint():
    """Front edge pads for a straddle-mounted card-edge socket.

    A 2x23 card-edge socket's tails are bent in to pinch the board edge and
    soldered here, so the socket sticks out of the front edge and takes the ZX81's
    fingers with the bus board in the same plane as the ZX81's board. Its top row
    of contacts meets the ZX81's top side (C row): pads on F.Cu. Its bottom row
    meets the underside (A row): pads on B.Cu. Position 3 (the key) gets pads with
    no net, for a tail to be soldered for strength if the socket has one there.

    Origin: the left end of the board edge; the board is at -y. Position 1 on the
    left, seen from above.
    """
    name = 'ZX81_EdgeStraddle'
    w = POSITIONS * G
    fy = -(STRADDLE_GAP + STRADDLE_L / 2)
    items = [S('version', 20241229), S('generator', 'zx81bus_gen_lib'), S('layer', 'F.Cu'),
             S('descr', 'Edge pads for a straddle-mounted ZX81 card-edge socket (tails bent to pinch the board), '
                        '2x23 positions at 2.54 mm, C row on top, A row on the bottom'),
             S('tags', 'ZX81 edge connector straddle'),
             fp_prop('Reference', 'J**', -2.5, -2.3, 'F.SilkS'),
             fp_prop('Value', name, w / 2, -6.0, 'F.Fab'),
             S('attr', Sym('smd'), Sym('exclude_from_pos_files'))]
    for layer in ('F.CrtYd', 'B.CrtYd'):
        items.append(rect((-0.25, -(STRADDLE_GAP + STRADDLE_L + 0.25)), (w + 0.25, 0), layer))
    items.append(rect((0, -(STRADDLE_GAP + STRADDLE_L)), (w, 0), 'F.Fab', 0.1))
    for p in range(1, POSITIONS + 1):
        x = G / 2 + (p - 1) * G
        c, a = pin_names(p) if p != KEY_POS else ('', '')
        for num, layers in ((c, ('F.Cu', 'F.Mask')), (a, ('B.Cu', 'B.Mask'))):
            items.append(S('pad', num, Sym('smd'), Sym('rect'), S('at', round(x, 4), round(fy, 4)),
                           S('size', STRADDLE_W, STRADDLE_L), S('layers', *layers)))
    return name, S('footprint', name, *items)


def main():
    os.makedirs(LIB, exist_ok=True)
    lib = S('kicad_symbol_lib', S('version', 20241209), S('generator', 'zx81bus_gen_lib'),
            S('generator_version', '9.0'), edge_symbol())
    with open(os.path.join(LIB, NAME + '.kicad_sym'), 'w') as f:
        f.write(dump(lib) + '\n')
    pretty = os.path.join(LIB, NAME + '.pretty')
    os.makedirs(pretty, exist_ok=True)
    for name, fp in (slot_footprint(), rear_fingers_footprint(), straddle_footprint()):
        with open(os.path.join(pretty, name + '.kicad_mod'), 'w') as f:
            f.write(dump(fp) + '\n')
    print('wrote', LIB)


if __name__ == '__main__':
    main()
