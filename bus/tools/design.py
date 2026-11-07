"""ZX81 bus board: single source of truth for parts and connectivity.

A passive backplane. It plugs onto the ZX81's edge connector through a card-edge
socket straddle-mounted on its front edge (J1: the socket's tails are bent to
pinch the board and soldered to pads on both sides), so it lies in the same
plane as the ZX81's board. It carries a 9 V DC jack (J6) on the ZX81's +9V line, three vertical card
slots (J2-J4) for cards such as the OpenSpand Card, and repeats the ZX81's own
edge as gold fingers on the rear (J5), so a RAM pack, printer interface or
another bus board can plug on behind it.

Every connector is wired straight through: pin A<n> / C<n> of each connector is
the same signal as pin A<n> / C<n> of the ZX81 edge. gen_sch.py turns this into
the schematic, gen_pcb.py into the board.
"""

PROJECT = 'ZX81-Bus'
LIB = 'ZX81Bus'

# ZX81 edge pinout. Position p (1..23, key slot at 3) is pin A(28-p) / C(28-p).
# C row: the ZX81's top side. A row: its underside.
SIGNALS = {
    'C27': 'D7', 'C26': 'RAMCS_N', 'C24': 'D0', 'C23': 'D1', 'C22': 'D2', 'C21': 'D6',
    'C20': 'D5', 'C19': 'D3', 'C18': 'D4', 'C17': 'INT_N', 'C16': 'NMI_N', 'C15': 'HALT_N',
    'C14': 'MREQ_N', 'C13': 'IORQ_N', 'C12': 'RD_N', 'C11': 'WR_N', 'C10': 'BUSAK_N',
    'C9': 'WAIT_N', 'C8': 'BUSRQ_N', 'C7': 'RESET_N', 'C6': 'M1_N', 'C5': 'RFSH_N',
    'A27': '+5V', 'A26': '+9V', 'A24': 'GND', 'A23': 'GND', 'A22': 'CLK',
    'A21': 'A0', 'A20': 'A1', 'A19': 'A2', 'A18': 'A3', 'A17': 'A15', 'A16': 'A14',
    'A15': 'A13', 'A14': 'A12', 'A13': 'A11', 'A12': 'A10', 'A11': 'A9', 'A10': 'A8',
    'A9': 'A7', 'A8': 'A6', 'A7': 'A5', 'A6': 'A4', 'A5': 'ROMCS_N',
}
POWER = {'+5V', '+9V', 'GND'}

parts = []


def part(ref, sym, value, fp, pins, lcsc='', block='', **kw):
    p = dict(ref=ref, sym=sym, value=value, fp=fp, pins=pins, lcsc=lcsc, block=block)
    p.update(kw)
    parts.append(p)
    return p


B = 'ZX81 bus'
part('J1', LIB + ':ZX81_Edge', 'ZX81 edge socket', LIB + ':ZX81_EdgeStraddle', dict(SIGNALS), '', B,
     note='2x23 0.1 in card-edge socket, tails bent to pinch the front edge and soldered both sides; '
          'takes the ZX81 fingers')
for i, ref in enumerate(('J2', 'J3', 'J4')):
    part(ref, LIB + ':ZX81_Edge', 'Slot %d' % (i + 1), LIB + ':ZX81_Slot_2x23_P2.54mm_Row5.08mm',
         dict(SIGNALS), '', B, note='Card-edge socket, 2x23 at 2.54 mm, rows 5.08 mm apart, key at position 3, hand-fitted')
part('J5', LIB + ':ZX81_Edge', 'Rear edge', LIB + ':ZX81_EdgeFingers_Rear', dict(SIGNALS), '', B,
     in_bom=False, note='Gold fingers on the rear edge (no part): a copy of the ZX81 edge')

B = 'Power in'
# 9 V in from a modern supply (5.5/2.1 mm plug, tip positive) onto the ZX81's +9V pin:
# it powers the ZX81 (through its own regulator) and anything on the bus that uses +9V.
part('J6', 'Connector:Barrel_Jack_Switch', '9V DC in', 'Connector_BarrelJack:BarrelJack_CUI_PJ-102AH_Horizontal',
     {'1': 'VIN', '2': 'GND', '3': None}, '', B,
     note='5.5/2.1 mm DC jack, tip positive, opening out of the right edge; hand-fitted')
# Reverse-polarity protection: a centre-negative supply is blocked instead of putting
# -9 V on the ZX81. Costs about 0.4 V; the ZX81's 7805 has plenty of headroom from 9 V.
part('D1', 'Device:D_Schottky', 'SS34', 'Diode_SMD:D_SMA', {'1': '+9V', '2': 'VIN'}, 'C8678', B,
     note='3 A 40 V Schottky, jack tip (anode) to +9V (cathode); hand-fitted')

B = 'Mechanical'
for i in range(5):
    part('H%d' % (i + 1), 'Mechanical:MountingHole', 'M3', 'MountingHole:MountingHole_3.2mm_M3',
         {}, '', B, in_bom=False)

# Every pin is passive, so ERC needs no power flags.
PWR_FLAGS = []


def nets():
    out = {}
    for p in parts:
        for pin, n in p['pins'].items():
            if n:
                out.setdefault(n, []).append((p['ref'], pin))
    return out
