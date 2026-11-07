"""Generate hardware/OpenSpand-Card.kicad_pcb (outline, footprints, nets, placement, planes).

Run with KiCad's bundled Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py
Routing is done afterwards by route.sh (Freerouting).

Board: a 155 x 57 mm card (body 155 x 49 mm, ZX81 edge fingers below), 4 layers (F.Cu signal, In1 GND plane, In2 +3V3 plane, B.Cu signal),
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

# Card: a 155 x 49 mm body with the 23-position ZX81 edge (a tongue 58.42 x 8 mm)
# below it, toward the right. Seen from the front (the component side, which
# faces the ZX81), the card lines up with the ZX81's own edge connector, so the
# fingers sit RIGHT_OVERHANG mm in from the card's right edge.
X0, Y0, W, BODY_H, RAD = 100.0, 50.0, 155.0, 49.0, 2.0
H = BODY_H + 8.0                       # overall height, fingers included
RIGHT_OVERHANG = 6.38                  # card edge beyond the end of the fingers (see README)
TX1 = X0 + W - RIGHT_OVERHANG          # tongue right edge
TX0 = TX1 - 23 * 2.54                  # tongue left edge
YB = Y0 + BODY_H                       # body bottom = tongue top
MM = pcbnew.FromMM
HDMI_OVERHANG = 2.86                   # courtyard past the edge: puts the footprint's 'PCB Edge' line on it


def on_board(x, y, margin=0.0, tongue=True):
    """True if (x, y) is at least margin inside the outline (the tongue counts unless tongue=False)."""
    if X0 + margin <= x <= X0 + W - margin and Y0 + margin <= y <= YB - margin:
        return True
    return tongue and TX0 + margin <= x <= TX1 - margin and YB - margin <= y <= Y0 + H - margin


# ------------------------------------------------------------ fixed placement
# ref: (x, y, rotation_deg[, 'B'])          footprint origin at x, y
#      ('box', left, top, rotation)          courtyard top-left corner at left, top
#      ('edge', side, along, overhang[, 'B']) connector facing out of the 'top'/'left'/'right'
#                                             edge, centred at 'along', courtyard sticking out
#                                             by 'overhang' mm; orientation found automatically
PLACE = {
    'J1': (TX0, YB, 0),                    # gold fingers; footprint origin at the tongue's top-left
    'J4': ('edge', 'left', 76.0, 6.9),     # joystick, low on the left edge; shell overhangs like upstream
    'J8': ('edge', 'right', 83.5, HDMI_OVERHANG),  # HDMI, level with U2's HSTX pins
    'U10': (242.0, 80.25, 0),              # TMDS ESD, flow-through, in front of J8's pins 1-6
    'U11': (242.0, 83.4, 0),               # and pins 7-12
    # TMDS series resistors, a 1.1 mm column in the socket's pin order (D2+ at the top)
    'R24': (238.0, 79.0, 0),
    'R25': (238.0, 80.1, 0),
    'R26': (238.0, 81.2, 0),
    'R27': (238.0, 82.3, 0),
    'R28': (238.0, 83.4, 0),
    'R29': (238.0, 84.5, 0),
    'R30': (238.0, 85.6, 0),
    'R31': (238.0, 86.7, 0),
    'J5': ('edge', 'right', 66.2, 0.0),    # microSD, right edge above the HDMI socket; card goes in from the side
    'U4': (116.5, 66.0, 90),               # MCP23009, beside the joystick
    'JP1': (114.0, 76.0, 90),
    'JP2': (117.5, 76.0, 90),
    # top edge, left to right
    'J6': ('box', 100.5, Y0 + 1.0, 0),     # SPI 2x3, top of the left edge, above the joystick
    'H1': (116.0, Y0 + 4.0, 0),
    # right-angle THT buttons (C&K PTS645VL83, hand-fitted), plungers out through the top
    # edge, about 5.8 mm past it; footprint origin is pad 1, the body's centre 2.25 mm right
    # of it and its front face 2.59 mm above it, here flush with the edge
    'SW1': (149.5 - 2.25, Y0 + 2.6, 0),    # Reset
    'SW4': (162.7 - 2.25, Y0 + 2.6, 0),    # Config
    'SW3': (175.9 - 2.25, Y0 + 2.6, 0),    # BOOTSEL
    'SW2': (189.1 - 2.25, Y0 + 2.6, 0),    # RUN

    'J3': ('edge', 'top', 204.0, 0.3),     # USB-C
    # core: RP2350B turned 90 degrees CCW, bus side (GPIO0..31) facing the fingers
    'U2': (221.0, 79.0, 90),
    'U3': (208.5, 81.5, 0),                # QSPI flash, left of the QSPI pins
    'Y1': (230.0, 80.0, 90),               # crystal pins are on U2's right side
    'U9': (213.1, 74.0, 0),                # 1.2 V core LDO, by U2's VREG pins
    'U8': (226.0, 69.0, 0),                # Z80_CLK buffer, above U2's GPIO40
    'U1': (178.0, 93.0, 0),                # LDO
    'D1': (184.0, 95.5, 0),                # ZX81 5 V in, beside the +5V finger
    'D2': (197.0, 59.5, 90),               # USB 5 V in
    'U6': (150.0, 84.0, 0),                # EEPROM
    'U5': (150.0, 72.0, 0),                # DS3231MZ RTC
    'BT1': (132.0, YB - 11.25, 0),         # CR2032; coin slides in from the bottom edge
    # status LEDs: 3 mm THT, legs bent so the body lies on the board and looks up out of
    # the top edge, 10 mm apart in the space J6 left. Footprint origin is pad 1 (cathode);
    # turned 180 degrees the body runs up from 1.27 mm above the pads, so with the pads
    # 2.0 mm below the edge the flange sits 0.73 mm inside it and the dome about 4.6 mm past.
    # The body's centre is 1.27 mm left of the origin.
    'D3': (126.0 + 1.27, Y0 + 2.0, 180),   # red
    'D4': (136.0 + 1.27, Y0 + 2.0, 180),   # green
    'R22': (126.0, Y0 + 5.5, 0),
    'R23': (136.0, Y0 + 5.5, 0),
    'H2': (162.0, 93.5, 0),
    'H3': (X0 + 4.0, YB - 3.3, 0),         # case screw posts: lower left, under the line out,
    'H4': (251.0, Y0 + 4.2, 0),            # top right corner, above the microSD,
    'H5': (251.5, 95.8, 0),                # bottom right corner, below the HDMI socket
}

# Passives are dropped next to the IC they serve; first matching anchor wins.
# The strip above the fingers is kept for the bus fan-out.
RESERVE = [(TX0 - 2.0, YB - 10.0, TX1 + 1.0, YB),
           (220.9, 84.3, 236.8, 87.3)]   # the TMDS lines' channel from U2's HSTX pins to R24..R31
ANCHOR_PREF = ['U2', 'U3', 'U5', 'U6', 'U4', 'U1', 'Y1', 'J3', 'J5', 'J1', 'D3', 'D4', 'J8', 'U8', 'J4', 'SW3']
NET_CLASSES = {  # name: (track mm, clearance mm, nets)
    'Power': (0.5, 0.15, ['+5V', '5VZX']),
    'Plane': (0.3, 0.127, ['GND', '+3V3']),
    'Core': (0.3, 0.127, ['+1V2', 'VBUS']),  # VBUS: 0.3 mm leaves the USB-C pads
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
    # body: rounded corners; tongue: chamfered corners and the key slot at position 3
    x1, r, c = X0 + W, RAD, 0.5
    sx = TX0 + 2.54 * 2.5                  # key slot centre
    sw, sd, yt = 2.03, 7.4, Y0 + H
    seg((X0 + r, Y0), (x1 - r, Y0))
    arc((x1 - r, Y0 + r), (x1 - r, Y0), (x1, Y0 + r))
    seg((x1, Y0 + r), (x1, YB - r))
    arc((x1 - r, YB - r), (x1, YB - r), (x1 - r, YB))
    seg((x1 - r, YB), (TX1, YB))
    pts = [(TX1, YB), (TX1, yt - c), (TX1 - c, yt), (sx + sw / 2, yt), (sx + sw / 2, yt - sd),
           (sx - sw / 2, yt - sd), (sx - sw / 2, yt), (TX0 + c, yt), (TX0, yt - c), (TX0, YB)]
    for a, b in zip(pts, pts[1:]):
        seg(a, b)
    seg((TX0, YB), (X0 + r, YB))
    arc((X0 + r, YB - r), (X0 + r, YB), (X0, YB - r))
    seg((X0, YB - r), (X0, Y0 + r))
    arc((X0 + r, Y0 + r), (X0, Y0 + r), (X0 + r, Y0))


BODY = ((X0, Y0), (X0 + W, Y0), (X0 + W, YB), (X0, YB))


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
            bb[1] >= Y0 + margin and bb[3] <= YB - margin)  # the body only, never the tongue


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


def button_labels(board):
    """Name each push button on the silkscreen, just under it; its reference goes to F.Fab,
    since the footprint puts it off the board or on the button above."""
    for fp in board.GetFootprints():
        if not fp.GetReference().startswith('SW'):
            continue
        fp.Reference().SetLayer(pcbnew.F_Fab)
        bb = courtyard(fp)
        t = pcbnew.PCB_TEXT(board)
        t.SetText(fp.GetValue().upper())
        t.SetLayer(pcbnew.F_SilkS)
        t.SetTextSize(pcbnew.VECTOR2I(MM(0.8), MM(0.8)))
        t.SetTextThickness(MM(0.12))
        t.SetPosition(pcbnew.VECTOR2I(MM((bb[0] + bb[2]) / 2), MM(bb[3] + 0.9)))
        board.Add(t)


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
                if q['name'] == '':  # a blank pin name drops out: "unconnected-(REF-PadN)"
                    n = 'unconnected-(%s-Pad%s)' % (p['ref'], q['num'])
                else:
                    nm = q['name'] if q['name'] != '~' else q['num']
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
        fp.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        # half a turn if that puts the pad that isn't ground nearer the pin it serves,
        # so its link doesn't cross the neighbouring pins
        reach = []
        for r in (rot, rot + 180):
            fp.SetOrientationDegrees(r)
            q = pad_pos(fp, nets)
            reach.append((math.hypot(q[0] - target[0], q[1] - target[1]) if q else 0, r))
        fp.SetOrientationDegrees(min(reach)[1])
        placed.append(courtyard(fp))

    button_labels(board)

    # ---- planes: In1 GND, In2 +3V3
    for layer, net in ((pcbnew.In1_Cu, 'GND'), (pcbnew.In2_Cu, '+3V3')):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(netinfo[net])  # keyed by design net name
        poly = z.Outline()
        poly.NewOutline()
        for (x, y) in BODY:
            poly.Append(MM(x), MM(y))
        z.SetMinThickness(MM(0.2))
        z.SetLocalClearance(MM(0.25))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
        board.Add(z)
    # fingers: no vias and no copper pour on the tongue
    z = pcbnew.ZONE(board)
    z.SetIsRuleArea(True)
    z.SetLayerSet(pcbnew.LSET.AllCuMask())
    z.SetDoNotAllowVias(True)
    z.SetDoNotAllowZoneFills(True)
    z.SetDoNotAllowTracks(False)
    z.SetDoNotAllowPads(False)
    z.SetDoNotAllowFootprints(False)
    z.SetZoneName('fingers')
    poly = z.Outline()
    poly.NewOutline()
    for (x, y) in ((TX0, YB), (TX1, YB), (TX1, Y0 + H), (TX0, Y0 + H)):
        poly.Append(MM(x), MM(y))
    board.Add(z)
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)

    t = pcbnew.PCB_TEXT(board)
    t.SetText('OpenSpand Card v0.2\nbased on OpenSpand HW 1.3.1 (CC BY-SA 4.0)\nthis side faces away from the ZX81')
    t.SetLayer(pcbnew.B_SilkS)
    t.SetPosition(pcbnew.VECTOR2I(MM(150), MM(74)))
    t.SetMirrored(True)
    t.SetTextSize(pcbnew.VECTOR2I(MM(1.5), MM(1.5)))
    board.Add(t)

    pcbnew.SaveBoard(OUT, board)
    print('wrote', OUT)


if __name__ == '__main__':
    main()
