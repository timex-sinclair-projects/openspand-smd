"""Generate hardware/ZX81-Bus.kicad_pcb: outline, footprints, nets, tracks and pours.

Run with KiCad's bundled Python:
  /Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3 gen_pcb.py

A 4-layer passive backplane (F.Cu signal, In1 GND plane, In2 +5V plane, B.Cu signal). Seen from above with the ZX81 in front (at the bottom
of the drawing), every connector has position 1 on the left and position n at the
same x, so each signal is one straight run front to back: C-row signals (the ZX81's
top side) on F.Cu, A-row signals (its underside) on B.Cu. Where a run meets the
other row's hole at a slot it steps half a pitch sideways and back. At the front
there are no holes: J1 is a socket straddling the edge, soldered to pads on both
sides. No
autorouter is needed. The bus runs cross the board from edge to edge on both
outer layers, so the outer GND pour is only strips; vias tie each strip to the
In1 plane.
"""
import os
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import design  # noqa: E402
from gen_lib import KEY_POS, POSITIONS, ROW, STRADDLE_GAP, STRADDLE_L, TONGUE_H, pin_names  # noqa: E402
from gen_sch import load_symbol, pins_of, sid  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HW = os.path.join(ROOT, 'hardware')
STOCK = os.environ.get('KICAD_FOOTPRINT_DIR',
                       '/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')
OUT = os.path.join(HW, design.PROJECT + '.kicad_pcb')
MM = pcbnew.FromMM
G = 2.54

# ------------------------------------------------------------------ geometry
# y grows toward the ZX81 (the front). The rear fingers' tip is at Y0.
XC = 150.0                              # centre of the pin span
X0, XR, RAD = 110.0, 195.0, 2.0         # board sides: room for holes on the left, the DC jack on the right
W = XR - X0
Y0 = 50.0                               # rear finger tip
YT = Y0 + TONGUE_H                      # rear edge of the body (tongue root)
SLOT_PITCH = 20.32                      # 0.8 in between slots: the card's DE-9 / VGA stand 12.5 mm proud
S3 = YT + 7.0                           # slot centres, rear to front
S2 = S3 + SLOT_PITCH
S1 = S2 + SLOT_PITCH
YF = S1 + 22.86                         # front edge, where J1 plugs onto the ZX81
SLOTS = (('J2', S1), ('J3', S2), ('J4', S3))   # front to back
J1_PAD = YF - STRADDLE_GAP - STRADDLE_L / 2   # centre of J1's straddle pads
J1_END = YF - STRADDLE_GAP - STRADDLE_L       # inner end of those pads
FINGER_Y = YT - (TONGUE_H - 0.7 - 3.5)  # rear finger centre
TX0 = XC - POSITIONS / 2 * G            # tongue left edge
TX1 = XC + POSITIONS / 2 * G
# DC jack (CUI PJ-102AH footprint): in the gap between J1 and slot 1, opening out of
# the right edge. Its origin is the centre pin (rear); the mouth is 14.2 mm further out.
JACK_Y = S1 + 4.25 + 6.7               # its side-pin bulge (6.5 mm) just clear of slot 1's courtyard
JACK_X = XR - 13.7                      # mouth 0.5 mm past the edge
G32, G21 = (S3 + S2) / 2, (S2 + S1) / 2  # the gaps between slots
HOLES = {'H1': (X0 + 3.5, G32), 'H2': (X0 + 3.5, G21), 'H3': (X0 + 3.5, JACK_Y),
         'H4': (XR - 4.0, G32), 'H5': (XR - 4.0, G21)}

SIG_W, PWR_W = 0.3, 0.6
JOG = G / 2


def xp(p):
    """x of position p (1..23, left to right seen from above)."""
    return XC + (p - (POSITIONS + 1) / 2) * G


def net_name(n):
    return '/' + n


def load_fp(fpid):
    lib, name = fpid.split(':')
    path = (os.path.join(HW, 'lib', lib + '.pretty') if lib == design.LIB
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
    x1, r, c = X0 + W, RAD, 0.5
    sx = TX0 + G * (KEY_POS - 0.5)          # key slot centre
    sw, sd = 2.03, 7.4
    # front edge and sides
    arc((X0 + r, YF - r), (X0 + r, YF), (X0, YF - r))
    seg((X0 + r, YF), (x1 - r, YF))
    arc((x1 - r, YF - r), (x1, YF - r), (x1 - r, YF))
    seg((x1, YF - r), (x1, YT + r))
    arc((x1 - r, YT + r), (x1 - r, YT), (x1, YT + r))
    seg((x1 - r, YT), (TX1, YT))
    # rear tongue: chamfered corners, key slot at position 3
    pts = [(TX1, YT), (TX1, Y0 + c), (TX1 - c, Y0), (sx + sw / 2, Y0), (sx + sw / 2, Y0 + sd),
           (sx - sw / 2, Y0 + sd), (sx - sw / 2, Y0), (TX0 + c, Y0), (TX0, Y0 + c), (TX0, YT)]
    for a, b in zip(pts, pts[1:]):
        seg(a, b)
    seg((TX0, YT), (X0 + r, YT))
    arc((X0 + r, YT + r), (X0, YT + r), (X0 + r, YT))
    seg((X0, YT + r), (X0, YF - r))


def pad_xy(fp, num):
    for q in fp.Pads():
        if q.GetNumber() == num and q.GetAttribute() == pcbnew.PAD_ATTRIB_PTH:
            return pcbnew.ToMM(q.GetPosition().x), pcbnew.ToMM(q.GetPosition().y)
    for q in fp.Pads():
        if q.GetNumber() == num:
            return pcbnew.ToMM(q.GetPosition().x), pcbnew.ToMM(q.GetPosition().y)
    raise KeyError(num)


def add_track(board, net, layer, pts, width):
    for a, b in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
        t.SetLayer(layer)
        t.SetWidth(MM(width))
        t.SetNet(net)
        board.Add(t)


def route(board, netinfo):
    """One straight run per signal, with a half-pitch step round the other row's holes."""
    for p in range(1, POSITIONS + 1):
        if p == KEY_POS:
            continue
        x = xp(p)
        c, a = pin_names(p)
        for pin, layer in ((c, pcbnew.F_Cu), (a, pcbnew.B_Cu)):
            n = design.SIGNALS[pin]
            w = PWR_W if n in design.POWER else SIG_W
            j = x + JOG
            if pin.startswith('C'):
                pts = [(x, J1_PAD)]
                for _, s in SLOTS:
                    yc, ya = s + ROW / 2, s - ROW / 2
                    pts += [(x, yc), (j, yc - JOG), (j, ya - JOG), (x, ya - 2 * JOG)]
            else:
                pts = [(x, J1_PAD)]
                for _, s in SLOTS:
                    yc, ya = s + ROW / 2, s - ROW / 2
                    pts += [(x, yc + 2 * JOG), (j, yc + JOG), (j, yc - JOG), (x, yc - 2 * JOG), (x, ya)]
            pts.append((x, FINGER_Y))
            add_track(board, netinfo[n], layer, pts, w)


def stitch(board, netinfo):
    """Vias to the planes.

    GND: between every pair of runs midway between connectors (clear of the steps),
    so each strip of outer pour reaches In1, plus a grid in the margins either side.
    +5V: beside the +5V run between connectors, to the In2 plane."""
    def via(x, y, net):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        v.SetWidth(MM(0.6))
        v.SetDrill(MM(0.3))
        v.SetNet(netinfo[net])
        board.Add(v)
    gaps = [(J1_END - 1.0, J1_END - 1.0)]   # just behind J1's pads, clear of the jack and the +9V feed
    for (_, s), (_, s2) in zip(SLOTS, SLOTS[1:]):
        gaps.append((s - ROW / 2 - 2 * JOG, s2 + ROW / 2 + 2 * JOG))
    ys = [(a + b) / 2 for a, b in gaps]
    for y in ys:
        for p in range(1, POSITIONS + 1):
            if y == ys[0] and p == 2:
                continue  # the +9V feed runs up through here on In2
            via(xp(p) + JOG, y, 'GND')
        # the D7 run is above the +5V run on F.Cu, so the via sits just outboard on a stub
        via(xp(1) - 1.8, y, '+5V')
        add_track(board, netinfo['+5V'], pcbnew.B_Cu, [(xp(1), y), (xp(1) - 1.8, y)], PWR_W)
    xs = [X0 + 2.5, X0 + 6.0, xp(POSITIONS) + 6.5, xp(POSITIONS) + 10.5, XR - 2.5]
    for x in xs:
        for i in range(13):
            y = YT + 3.0 + i * 5.0
            if y > J1_END - 1 or any(abs(y - h[1]) < 4.5 and abs(x - h[0]) < 4.5 for h in HOLES.values()):
                continue
            if x > xp(POSITIONS) and abs(y - JACK_Y) < 7.0:
                continue
            via(x, y, 'GND')


def feed_9v(board, netinfo, jack, diode):
    """+9V from the jack to the +9V run (position 2, left end, B.Cu), through D1.

    The jack's centre pin (VIN) runs down to D1's anode on F.Cu. From D1's cathode
    a via takes +9V to In2, where it crosses the bus as a 1 mm track cut into the
    +5V plane (the bus runs cover both outer layers from edge to edge). It runs
    across just behind J1's pads, turns back up beside the +9V run, and comes up
    through a via there (C26 is over the run on F.Cu) to join it on a B.Cu stub."""
    tip = pad_xy(jack, '1')
    anode, cathode = pad_xy(diode, '2'), pad_xy(diode, '1')
    add_track(board, netinfo['VIN'], pcbnew.F_Cu, [tip, (tip[0], anode[1]), anode], 0.8)
    cx = cathode[0] + 2.4
    add_track(board, netinfo['+9V'], pcbnew.F_Cu, [cathode, (cx, cathode[1])], 0.8)
    vx, fy = xp(2) + JOG, J1_END + 1.6
    for x, y in ((cx, cathode[1]), (vx, JACK_Y)):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        v.SetWidth(MM(0.8))
        v.SetDrill(MM(0.4))
        v.SetNet(netinfo['+9V'])
        board.Add(v)
    add_track(board, netinfo['+9V'], pcbnew.In2_Cu,
              [(cx, cathode[1]), (cx, fy), (vx, fy), (vx, JACK_Y)], 1.0)
    add_track(board, netinfo['+9V'], pcbnew.B_Cu, [(xp(2), JACK_Y), (vx, JACK_Y)], PWR_W)


def silk(board, txt, x, y, size=1.2, layer=pcbnew.F_SilkS, bold=False, just=None):
    t = pcbnew.PCB_TEXT(board)
    t.SetText(txt)
    t.SetLayer(layer)
    t.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    t.SetTextSize(pcbnew.VECTOR2I(MM(size), MM(size)))
    t.SetTextThickness(MM(size * (0.2 if bold else 0.15)))
    if layer == pcbnew.B_SilkS:
        t.SetMirrored(True)
    if just is not None:
        t.SetHorizJustify(just)
    board.Add(t)


def main():
    board = pcbnew.NewBoard(OUT)
    board.SetCopperLayerCount(4)
    ds = board.GetDesignSettings()
    ds.SetCopperLayerCount(4)
    ns = ds.m_NetSettings
    dflt = ns.GetDefaultNetclass()
    dflt.SetTrackWidth(MM(SIG_W))
    dflt.SetClearance(MM(0.2))
    dflt.SetViaDiameter(MM(0.6))
    dflt.SetViaDrill(MM(0.3))
    ds.m_TrackMinWidth = MM(0.2)
    ds.m_MinClearance = MM(0.15)
    ds.m_ViasMinSize = MM(0.5)
    ds.m_MinThroughDrill = MM(0.3)
    ds.m_HoleClearance = MM(0.25)
    ds.m_CopperEdgeClearance = MM(0.3)
    nc = pcbnew.NETCLASS('Power')
    nc.SetTrackWidth(MM(PWR_W))
    nc.SetClearance(MM(0.2))
    nc.SetViaDiameter(MM(0.6))
    nc.SetViaDrill(MM(0.3))
    ns.SetNetclass('Power', nc)
    for n in design.POWER | {'VIN'}:
        ns.SetNetclassPatternAssignment(net_name(n), 'Power')

    outline(board)

    netinfo = {}
    for n in sorted(design.nets()):
        ni = pcbnew.NETINFO_ITEM(board, net_name(n))
        board.Add(ni)
        netinfo[n] = ni

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
        if not p.get('in_bom', True):
            fp.SetExcludedFromBOM(True)
        fp.SetExcludedFromPosFiles(True)  # nothing here is machine-placed
        board.Add(fp)
        unused = {q['num'] for q in pins_of(load_symbol(p['sym'])) if not p['pins'].get(q['num'])}
        for pad in fp.Pads():
            n = p['pins'].get(pad.GetNumber())
            if n:
                pad.SetNet(netinfo[n])
            elif pad.GetNumber() in unused:  # KiCad's name for an unused symbol pin's net
                ni = pcbnew.NETINFO_ITEM(board, 'unconnected-(%s-Pad%s)' % (p['ref'], pad.GetNumber()))
                board.Add(ni)
                pad.SetNet(ni)
        fp.GetField(pcbnew.FIELD_T_DESCRIPTION).SetText('')
        fp.GetField(pcbnew.FIELD_T_DATASHEET).SetText('')
        fps[p['ref']] = fp

    # ---- placement
    fps['J1'].SetPosition(pcbnew.VECTOR2I(MM(TX0), MM(YF)))
    for ref, s in SLOTS:
        fps[ref].SetPosition(pcbnew.VECTOR2I(MM(XC), MM(s)))
    fps['J5'].SetPosition(pcbnew.VECTOR2I(MM(TX0), MM(YT)))
    for ref, (x, y) in HOLES.items():
        fps[ref].SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
    jack = fps['J6']
    jack.SetOrientationDegrees(90)      # mouth (+y in the footprint) toward +x
    jack.SetPosition(pcbnew.VECTOR2I(MM(JACK_X), MM(JACK_Y)))
    assert pad_xy(jack, '2')[0] > JACK_X, 'jack faces the wrong way'
    jack.Reference().SetVisible(False)   # labelled '9V tip+' instead
    diode = fps['D1']
    diode.SetOrientationDegrees(180)     # anode (pad 2) on the left, toward the jack's centre pin
    diode.SetPosition(pcbnew.VECTOR2I(MM(JACK_X + 4.7), MM(YF - 3.5)))
    dr = diode.Reference()
    dr.SetPosition(pcbnew.VECTOR2I(MM(JACK_X + 4.7), MM(YF - 5.8)))
    dr.SetTextAngleDegrees(0)
    # every connector: position n at the same x
    for ref in ('J1', 'J2', 'J3', 'J4', 'J5'):
        for p in (1, 2, 12, 23):
            for name in pin_names(p):
                assert abs(pad_xy(fps[ref], name)[0] - xp(p)) < 0.01, (ref, name)
    # reference designators beside the slots
    for ref, s in SLOTS:
        f = fps[ref].Reference()
        f.SetPosition(pcbnew.VECTOR2I(MM(xp(1) - 7.5), MM(s)))
        f.SetTextSize(pcbnew.VECTOR2I(MM(1.2), MM(1.2)))
    fps['J5'].Reference().SetPosition(pcbnew.VECTOR2I(MM(TX0 - 3.0), MM(YT - 3.0)))
    j1r = fps['J1'].Reference()
    j1r.SetPosition(pcbnew.VECTOR2I(MM(xp(1) - 7.5), MM(J1_PAD)))
    j1r.SetTextAngleDegrees(0)
    j1r.SetTextSize(pcbnew.VECTOR2I(MM(1.2), MM(1.2)))
    j1r.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
    for ref in HOLES:
        fps[ref].Reference().SetVisible(False)

    route(board, netinfo)
    feed_9v(board, netinfo, jack, diode)
    stitch(board, netinfo)

    # ---- GND pour on both outer layers, In1 GND plane, In2 +5V plane: body only
    body = ((X0, YT), (X0 + W, YT), (X0 + W, YF), (X0, YF))
    for layer, net in ((pcbnew.F_Cu, 'GND'), (pcbnew.B_Cu, 'GND'), (pcbnew.In1_Cu, 'GND'), (pcbnew.In2_Cu, '+5V')):
        z = pcbnew.ZONE(board)
        z.SetLayer(layer)
        z.SetNet(netinfo[net])
        poly = z.Outline()
        poly.NewOutline()
        for (x, y) in body:
            poly.Append(MM(x), MM(y))
        z.SetMinThickness(MM(0.25))
        z.SetLocalClearance(MM(0.3))
        z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
        z.SetThermalReliefGap(MM(0.4))
        z.SetThermalReliefSpokeWidth(MM(0.5))
        board.Add(z)
    # rear fingers: no vias and no pour on the tongue
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
    for (x, y) in ((TX0, Y0), (TX1, Y0), (TX1, YT), (TX0, YT)):
        poly.Append(MM(x), MM(y))
    board.Add(z)
    board.SetLayerType(pcbnew.In1_Cu, pcbnew.LT_POWER)
    board.SetLayerType(pcbnew.In2_Cu, pcbnew.LT_POWER)

    # ---- silkscreen
    L, R = pcbnew.GR_TEXT_H_ALIGN_LEFT, pcbnew.GR_TEXT_H_ALIGN_RIGHT
    for i, (ref, s) in enumerate(SLOTS):
        silk(board, 'SLOT %d' % (i + 1), xp(23) + 6.0, s, 1.2, bold=True, just=L)
    silk(board, 'ZX81 this way', XC, J1_END - 2.0, 1.2, bold=True)
    silk(board, 'cards: component side faces the ZX81', XC, S1 + 6.6, 1.0)
    silk(board, 'ZX81 bus  rev 0.1', XC, S3 + 6.5, 1.5, bold=True)
    silk(board, '9V tip+', XR - 5.5, JACK_Y - 7.6, 1.0)
    silk(board, '1', xp(1), YT + 1.5, 1.0)
    silk(board, '23', xp(23), YT + 1.5, 1.0)
    silk(board, 'ZX81 bus v0.1 - 3 slots, rear edge = ZX81 edge\n'
                'J1: card-edge socket straddling the front edge',
         XC, (S1 + S2) / 2, 1.2, layer=pcbnew.B_SilkS)

    pcbnew.SaveBoard(OUT, board)
    print('wrote', OUT)
    print('board %.1f x %.1f mm (body %.1f deep, rear tongue %.1f)' % (W, YF - Y0, YF - YT, TONGUE_H))


if __name__ == '__main__':
    main()
