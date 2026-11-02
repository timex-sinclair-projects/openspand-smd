"""Generate hardware/OpenSpand-SMD.kicad_pcb (outline, footprints, nets, placement, planes).

Run with KiCad's bundled Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
Routing is done afterwards by route.sh (Freerouting).

Board: 100 x 70 mm, 4 layers (F.Cu signal, In1 GND plane, In2 +3V3 plane, B.Cu signal),
all SMD parts on top so JLCPCB can assemble one side.
"""
import math
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design  # noqa: E402
from gen_sch import load_symbol, pins_of, sid  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HW = os.path.join(ROOT, 'hardware')
STOCK = os.environ.get('KICAD_FOOTPRINT_DIR',
                       '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')
OUT = os.path.join(HW, design.PROJECT + '.kicad_pcb')

X0, Y0, W, H, RAD = 100.0, 50.0, 100.0, 70.0, 3.0
MM = pcbnew.FromMM

# ------------------------------------------------------------ fixed placement
# ref: (x, y, rotation_deg[, 'B'])          footprint origin at x, y
#      ('box', left, top, rotation)          courtyard top-left corner at left, top
#      ('edge', side, along, overhang[, 'B']) connector facing out of the 'top'/'left'/'right'
#                                             edge, centred at 'along', courtyard sticking out
#                                             by 'overhang' mm; orientation found automatically
PLACE = {
    'J1': (150.0, Y0 + H + 0.2, -90, 'B'),  # ZX81 edge socket, same offset to the edge as upstream
    # right edge, bottom side: joystick; shell overhangs like upstream
    'J4': ('edge', 'right', 80.0, 6.9, 'B'),
    # left edge: USB and buttons
    'J3': ('edge', 'left', 63.0, 0.3),
    'SW1': (104.5, 74.0, 0),               # Reset
    'SW4': (104.5, 82.0, 0),               # Config
    'SW3': (113.0, 74.0, 0),               # BOOTSEL
    'SW2': (113.0, 82.0, 0),               # RUN
    'D2': (116.0, 68.5, 0),
    # top edge, left to right
    'J5': ('edge', 'top', 121.0, 0.0),     # microSD
    'J10': ('box', 130.0, Y0 + 1.0, 90),   # I2C/UART 2x4
    'J6': ('box', 142.5, Y0 + 1.0, 90),    # SPI 2x3
    'J9': ('box', 152.5, Y0 + 1.0, 90),    # digitized audio 1x4
    'J8': ('box', 165.0, Y0 + 1.0, 90),    # video 1x2
    'J2': ('box', 172.0, Y0 + 1.0, 90),    # SWD
    'J7': ('edge', 'top', 187.0, 0.0),     # line out
    'D3': (131.0, 60.5, 0),
    'D4': (135.0, 60.5, 0),
    'JP3': (169.0, 59.0, 90),
    # core
    'U2': (152.0, 88.0, 0),                # RP2350B
    'U3': (154.0, 74.5, 0),                # QSPI flash, above the QSPI pins
    'Y1': (146.0, 97.5, 0),
    'L1': (160.5, 79.5, 0),
    'U1': (172.0, 100.0, 0),               # LDO
    'D1': (165.0, 104.5, 0),
    'U7': (178.0, 66.0, 0),                # PCM5102A, near the jack
    'U4': (172.0, 84.0, 0),                # MCP23009, near the joystick
    'JP1': (178.0, 92.0, 0),
    'JP2': (178.0, 95.0, 0),
    'R7': (145.75, 79.5, 90), 'R8': (144.0, 79.5, 90),  # USB pair side by side
    'U5': (125.0, 73.0, 0),                # DS1307
    'Y2': (125.0, 79.0, 0),
    'U6': (135.0, 73.0, 0),                # EEPROM
    'BT1': (123.0, 97.0, 0),
    'H1': (X0 + 3.5, Y0 + 3.5, 0), 'H2': (X0 + W - 3.5, Y0 + 3.5, 0),
    'H3': (X0 + 3.5, 104.0, 0),
}

# Passives are dropped next to the IC they serve; first matching anchor wins.
# areas kept clear of passives: the QSPI bus between U2's top edge and the flash
RESERVE = [(149.4, 77.6, 153.0, 82.6)]
ANCHOR_PREF = ['U2', 'U3', 'U7', 'U5', 'U6', 'U4', 'U1', 'Y1', 'Y2', 'J3', 'J5', 'J1', 'J7', 'D3', 'D4', 'J8', 'SW3']
NET_CLASSES = {  # name: (track mm, clearance mm, nets)
    'Power': (0.5, 0.15, ['+5V', '5VZX']),
    'Plane': (0.3, 0.127, ['GND', '+3V3']),
    'Core': (0.3, 0.127, ['+1V1', 'VREG_LX', 'VBUS']),  # VBUS: 0.3 mm leaves the USB-C pads
}


def net_name(n):
    """Board net name for a design net: the schematic uses local labels, which KiCad prefixes with '/'."""
    return '/' + n


def load_fp(fpid):
    lib, name = fpid.split(':')
    path = (os.path.join(HW, 'lib', lib + '.pretty') if lib == 'OpenSpandSMD'
            else os.path.join(STOCK, lib + '.pretty'))
    fp = pcbnew.FootprintLoad(path, name)
    if fp is None:
        raise SystemExit('footprint not found: ' + fpid)
    fp.SetFPID(pcbnew.LIB_ID(lib, name))
    return fp


def outline(board):
    def seg(a, b):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_SEGMENT)
        s.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
        s.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        board.Add(s)

    def arc(c, start, end):
        s = pcbnew.PCB_SHAPE(board, pcbnew.SHAPE_T_ARC)
        s.SetCenter(pcbnew.VECTOR2I(MM(c[0]), MM(c[1])))
        s.SetStart(pcbnew.VECTOR2I(MM(start[0]), MM(start[1])))
        s.SetEnd(pcbnew.VECTOR2I(MM(end[0]), MM(end[1])))
        s.SetLayer(pcbnew.Edge_Cuts)
        s.SetWidth(MM(0.1))
        board.Add(s)
    x1, y1, r = X0 + W, Y0 + H, RAD
    seg((X0 + r, Y0), (x1 - r, Y0))
    seg((x1, Y0 + r), (x1, y1 - r))
    seg((x1 - r, y1), (X0 + r, y1))
    seg((X0, y1 - r), (X0, Y0 + r))
    arc((x1 - r, Y0 + r), (x1 - r, Y0), (x1, Y0 + r))
    arc((x1 - r, y1 - r), (x1, y1 - r), (x1 - r, y1))
    arc((X0 + r, y1 - r), (X0 + r, y1), (X0, y1 - r))
    arc((X0 + r, Y0 + r), (X0, Y0 + r), (X0 + r, Y0))


def courtyard(fp):
    """Courtyard bbox grown to cover the pads (some imported footprints have pads outside it)."""
    cy = fp.GetCourtyard(pcbnew.B_CrtYd if fp.IsFlipped() else pcbnew.F_CrtYd)
    bb = cy.BBox() if cy.OutlineCount() else fp.GetBoundingBox(False)
    box = [pcbnew.ToMM(bb.GetLeft()), pcbnew.ToMM(bb.GetTop()),
           pcbnew.ToMM(bb.GetRight()), pcbnew.ToMM(bb.GetBottom())]
    for p in fp.Pads():
        pb = p.GetBoundingBox()
        box = [min(box[0], pcbnew.ToMM(pb.GetLeft())), min(box[1], pcbnew.ToMM(pb.GetTop())),
               max(box[2], pcbnew.ToMM(pb.GetRight())), max(box[3], pcbnew.ToMM(pb.GetBottom()))]
    return tuple(box)


def overlaps(a, b, gap=0.25):
    return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])


def inside_board(bb, margin=0.6):
    return (bb[0] >= X0 + margin and bb[2] <= X0 + W - margin and
            bb[1] >= Y0 + margin and bb[3] <= Y0 + H - 11.5)  # keep clear of the edge socket


def place_on_edge(fp, side, along, overhang):
    """Rotate so the body points out of the board edge, then butt it against that edge."""
    out = {'top': (0, -1), 'left': (-1, 0), 'right': (1, 0)}[side]
    best = None
    for rot in (0, 90, 180, 270):
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(pcbnew.VECTOR2I(0, 0))
        bb = courtyard(fp)
        c = pad_centroid(fp)
        # the body sits in front of the pins, so centre-of-body minus centre-of-pads points out
        reach = ((bb[0] + bb[2]) / 2 - c[0]) * out[0] + ((bb[1] + bb[3]) / 2 - c[1]) * out[1]
        if best is None or reach > best[0]:
            best = (reach, rot)
    fp.SetOrientationDegrees(best[1])
    fp.SetPosition(pcbnew.VECTOR2I(0, 0))
    bb = courtyard(fp)
    if side == 'top':
        dx, dy = along - (bb[0] + bb[2]) / 2, Y0 - overhang - bb[1]
    elif side == 'left':
        dx, dy = X0 - overhang - bb[0], along - (bb[1] + bb[3]) / 2
    else:
        dx, dy = X0 + W + overhang - bb[2], along - (bb[1] + bb[3]) / 2
    fp.SetPosition(pcbnew.VECTOR2I(MM(dx), MM(dy)))


def pad_centroid(fp):
    ps = [p.GetPosition() for p in fp.Pads()]
    return (pcbnew.ToMM(sum(p.x for p in ps) / len(ps)), pcbnew.ToMM(sum(p.y for p in ps) / len(ps)))


def pad_pos(fp, nets):
    pts = [p.GetPosition() for p in fp.Pads() if p.GetNetname() in nets]
    if not pts:
        return None
    return (pcbnew.ToMM(sum(p.x for p in pts) / len(pts)), pcbnew.ToMM(sum(p.y for p in pts) / len(pts)))


def main():
    board = pcbnew.NewBoard(OUT)
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(4)
    ns = ds.m_NetSettings
    dflt = ns.GetDefaultNetclass()
    dflt.SetTrackWidth(MM(0.127))
    dflt.SetClearance(MM(0.127))
    dflt.SetViaDiameter(MM(0.45))
    dflt.SetViaDrill(MM(0.25))
    ds.m_TrackMinWidth = MM(0.1)  # Freerouting necks down at pads; JLC 4-layer does 0.09 mm
    ds.m_MinClearance = MM(0.127)
    ds.m_ViasMinSize = MM(0.45)
    ds.m_MinThroughDrill = MM(0.25)
    ds.m_HoleClearance = MM(0.2)
    ds.m_CopperEdgeClearance = MM(0.3)
    for cname, (tw, cl, nets) in NET_CLASSES.items():
        nc = pcbnew.NETCLASS(cname)
        nc.SetTrackWidth(MM(tw))
        nc.SetClearance(MM(cl))
        nc.SetViaDiameter(MM(0.6 if cname == 'Power' else 0.45))
        nc.SetViaDrill(MM(0.3 if cname == 'Power' else 0.25))
        ns.SetNetclass(cname, nc)
        for n in nets:
            ns.SetNetclassPatternAssignment(net_name(n), cname)

    outline(board)

    netinfo = {}
    for n in sorted(design.nets()):
        ni = pcbnew.NETINFO_ITEM(board, net_name(n))
        board.Add(ni)
        netinfo[n] = ni

    # KiCad names the net of each unused symbol pin "unconnected-(REF-PIN-PadN)"
    unused = {}
    for p in design.parts:
        for q in pins_of(load_symbol(p['sym'])):
            if not p['pins'].get(q['num']):
                nm = q['name'] if q['name'] not in ('~', '') else q['num']
                n = 'unconnected-(%s-%s-Pad%s)' % (p['ref'], nm.replace('/', '{slash}'), q['num'])
                ni = pcbnew.NETINFO_ITEM(board, n)
                board.Add(ni)
                unused[(p['ref'], q['num'])] = ni

    fps = {}
    for p in design.parts:
        fp = load_fp(p['fp'])
        fp.SetReference(p['ref'])
        fp.SetValue(p['value'])
        fp.SetPath(pcbnew.KIID_PATH('/' + sid('sym', p['ref'])))
        fp.SetSheetname('Root')
        fp.SetSheetfile(design.PROJECT + '.kicad_sch')
        for fname, fval in (('LCSC', p['lcsc']), ('Note', p.get('note', '')), ('MPN', p.get('mpn'))):
            if fval is None:
                continue
            f = pcbnew.PCB_FIELD(fp, fp.GetNextFieldOrdinal(), fname)
            f.SetText(fval)
            f.SetVisible(False)
            f.SetLayer(pcbnew.F_Fab)
            fp.Add(f)
        if p.get('dnp'):
            fp.SetDNP(True)
            fp.SetExcludedFromBOM(True)
            fp.SetExcludedFromPosFiles(True)
        if not p.get('in_bom', True):
            fp.SetExcludedFromBOM(True)
        board.Add(fp)
        for pad in fp.Pads():
            n = p['pins'].get(pad.GetNumber())
            if n:
                pad.SetNet(netinfo[n])
            elif (p['ref'], pad.GetNumber()) in unused:
                pad.SetNet(unused[(p['ref'], pad.GetNumber())])
        fp.GetField(pcbnew.FIELD_T_DESCRIPTION).SetText('')
        fp.GetField(pcbnew.FIELD_T_DATASHEET).SetText('')
        fps[p['ref']] = fp

    # ---- fixed parts
    placed = []
    for ref, pl in PLACE.items():
        fp = fps[ref]
        if pl[-1] == 'B':
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_LEFT_RIGHT)
        if pl[0] == 'edge':
            place_on_edge(fp, pl[1], pl[2], pl[3])
        elif pl[0] == 'box':
            fp.SetOrientationDegrees(pl[3])
            bb = courtyard(fp)
            fp.Move(pcbnew.VECTOR2I(MM(pl[1] - bb[0]), MM(pl[2] - bb[1])))
        else:
            fp.SetOrientationDegrees(pl[2])
            fp.SetPosition(pcbnew.VECTOR2I(MM(pl[0]), MM(pl[1])))
        if ref == 'J1':
            continue
        bb = courtyard(fp)
        for oref, obb in placed:
            if overlaps(bb, obb, 0) and fp.IsFlipped() == fps[oref].IsFlipped():
                print('warning: %s overlaps %s' % (ref, oref))
        placed.append((ref, bb))
    placed = [bb for _, bb in placed]
    # edge socket: reserve its strip
    placed.append((X0, Y0 + H - 11.0, X0 + W, Y0 + H))
    placed.extend(RESERVE)

    # ---- passives: spiral search around the pins they connect to
    loose = [p for p in design.parts if p['ref'] not in PLACE]
    for p in loose:
        fp = fps[p['ref']]
        nets = {net_name(n) for n in p['pins'].values() if n and n not in ('GND',)}
        target = None
        if p['ref'] in design.NEAR:
            a, pin = design.NEAR[p['ref']]
            pp = [q.GetPosition() for q in fps[a].Pads() if q.GetNumber() == pin][0]
            target = (pcbnew.ToMM(pp.x), pcbnew.ToMM(pp.y))
        for a in ([] if target else ANCHOR_PREF):
            target = pad_pos(fps[a], nets - {net_name('+3V3'), net_name('+5V')}) or None
            if target:
                break
        if not target:
            for a in ANCHOR_PREF:
                target = pad_pos(fps[a], nets)
                if target:
                    break
        if not target:
            raise SystemExit('no anchor for ' + p['ref'])
        best = None
        for rot in (0, 90):
            fp.SetOrientationDegrees(rot)
            for r in [i * 0.5 for i in range(0, 60)]:
                cands = []
                steps = max(8, int(r * 6))
                for k in range(steps):
                    t = 2 * math.pi * k / steps
                    cands.append((target[0] + r * math.cos(t), target[1] + r * math.sin(t)))
                for (x, y) in cands:
                    x, y = round(x * 4) / 4, round(y * 4) / 4
                    fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
                    bb = courtyard(fp)
                    if inside_board(bb) and not any(overlaps(bb, o) for o in placed):
                        d = math.hypot(x - target[0], y - target[1])
                        if best is None or d < best[0]:
                            best = (d, x, y, rot)
                        break
                if best and best[3] == rot:
                    break
        if not best:
            raise SystemExit('could not place ' + p['ref'])
        _, x, y, rot = best
        fp.SetOrientationDegrees(rot)
        fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        placed.append(courtyard(fp))

    # ---- planes: In1 GND, In2 +3V3
    for layer, net in ((pcbnew.In1_Cu, 'GND'), (pcbnew.In2_Cu, '+3V3')):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(netinfo[net])  # keyed by design net name
        poly = z.Outline()
        poly.NewOutline()
        for (x, y) in ((X0, Y0), (X0 + W, Y0), (X0 + W, Y0 + H), (X0, Y0 + H)):
            poly.Append(MM(x), MM(y))
        z.SetMinThickness(MM(0.2))
        z.SetLocalClearance(MM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        board.Add(z)
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)

    t = pcbnew.PCB_TEXT(board)
    t.SetText('OpenSpand SMD v0.1\nbased on OpenSpand HW 1.3.1 (CC BY-SA 4.0)')
    t.SetLayer(pcbnew.B_SilkS)
    t.SetPosition(pcbnew.VECTOR2I(MM(150), MM(80)))
    t.SetMirrored(True)
    t.SetTextSize(pcbnew.VECTOR2I(MM(1.5), MM(1.5)))
    board.Add(t)

    pcbnew.SaveBoard(OUT, board)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
