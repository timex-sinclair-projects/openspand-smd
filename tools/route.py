"""Route hardware/OpenSpand-SMD.kicad_pcb, then pour ground.

1. Fan out every GND and +3V3 SMD pad to its plane (In1 GND, In2 +3V3) with a via.
   The RP2350 core supply (+1V1) is fanned out the same way and its vias are joined
   by a track tree on In2, cut into the +3V3 plane.
2. Autoroute the remaining nets with Freerouting on F.Cu and B.Cu.
3. Pour GND on F.Cu and B.Cu and fill all zones.

Run with KiCad's bundled Python. Needs Java 21+ and the Freerouting jar:
  FREEROUTING_JAR=/path/freerouting.jar JAVA=/path/java python3 route.py [passes]
Pass 'reuse' instead of a pass count to re-import the last run's .ses without routing.
"""
import heapq
import math
import os
import re
import subprocess
import sys

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import OUT, X0, Y0, W, H  # noqa: E402

JAR = os.environ['FREEROUTING_JAR']
JAVA = os.environ.get('JAVA', 'java')
PASSES = sys.argv[1] if len(sys.argv) > 1 else '100'
MM = pcbnew.FromMM
TO = pcbnew.ToMM
PLANE_NETS = ('/GND', '/+3V3')
CORE_NET = '/+1V1'  # fanned out like a plane net, then joined on In2
FANOUT_NETS = PLANE_NETS + (CORE_NET,)
IN2_W, IN2_CLR, GRID = 0.3, 0.25, 0.05
# short, critical nets maze-routed on F.Cu: the regulator before the fanout, USB and
# the flash bus after it
PREROUTE = {'/VREG_LX': 0.25, '/VREG_AVDD': 0.2}
PREROUTE_LATE = {'/QSPI_' + n: 0.15 for n in ('SS', 'SD1', 'SD2', 'SD0', 'SCLK', 'SD3')}
# USB has to cross the flash bus, so it goes in with vias (finish.py's layered maze),
# pin to series resistor, while the area round the MCU is still empty
PREROUTE_VIAS = (('/USB_DM', 'U2', '66', 'R8', '2'), ('/USB_DP', 'U2', '67', 'R7', '2'))
PRE_DONE = set()  # prerouted nets, kept out of Freerouting
DSN_EXTRA_CLR = 10  # um added to Freerouting's clearances: it rounds a few um under the rule
VIA_D, VIA_DRILL, FAN_W, CLR = 0.45, 0.25, 0.3, 0.2
FINE_W, FINE_CLR = 0.2, 0.15  # escaping 0.4 mm-pitch leads


def rect_dist(px, py, bb):
    dx = max(bb[0] - px, 0, px - bb[2])
    dy = max(bb[1] - py, 0, py - bb[3])
    return math.hypot(dx, dy)


def bbox_mm(item):
    b = item.GetBoundingBox()
    return (TO(b.GetLeft()), TO(b.GetTop()), TO(b.GetRight()), TO(b.GetBottom()))


def seg_dist(px, py, a, b):
    vx, vy = b[0] - a[0], b[1] - a[1]
    L = vx * vx + vy * vy
    k = 0 if L == 0 else max(0, min(1, ((px - a[0]) * vx + (py - a[1]) * vy) / L))
    return math.hypot(px - a[0] - k * vx, py - a[1] - k * vy)


def fanout(board):
    """Short track + via from each fanout-net SMD pad. Returns (vias added, pads skipped)."""
    pads = [(p, bbox_mm(p), p.GetNetname()) for p in board.GetPads()]
    vias = []  # (x, y, net)
    segs = [((TO(t.GetStart().x), TO(t.GetStart().y)), (TO(t.GetEnd().x), TO(t.GetEnd().y)),
             t.GetNetname(), TO(t.GetWidth()))
            for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK' and t.GetLayer() == pcbnew.F_Cu]
    skipped = []
    pending = []

    def free(x, y, net, seg_from=None, own=None, w=FAN_W, clr=CLR, via=True):
        if not (X0 + 0.8 < x < X0 + W - 0.8 and Y0 + 0.8 < y < Y0 + H - 11.5):
            return False
        # points along the new track (if any), then the via itself
        pts = []
        if seg_from:
            n = max(2, int(math.hypot(x - seg_from[0], y - seg_from[1]) / 0.05))
            pts = [(seg_from[0] + (x - seg_from[0]) * i / n, seg_from[1] + (y - seg_from[1]) * i / n, w / 2)
                   for i in range(1, n)]
        pts.append((x, y, VIA_D / 2 if via else w / 2))
        for p, bb, n in pads:
            if n == net and n:
                continue
            if own is not None and not n and p.GetParentFootprint() == own:
                continue  # paste apertures inside an exposed pad
            extra = 0.1 if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) else 0
            for qx, qy, r in pts:
                if rect_dist(qx, qy, bb) < r + clr + extra:
                    return False
        for vx, vy, n in vias:
            for qx, qy, r in pts:
                gap = 0.15 if n == net else clr + 0.05
                if math.hypot(vx - qx, vy - qy) < VIA_D / 2 + r + gap:
                    return False
        for a, b, n, sw in segs:
            if n == net:
                continue
            for qx, qy, r in pts:
                if seg_dist(qx, qy, a, b) < sw / 2 + r + clr:
                    return False
        return True

    def free_seg(a, b, net):
        """Track from a to b (b lands on a same-net pad, so no via-sized check at b)."""
        n = max(2, int(math.hypot(b[0] - a[0], b[1] - a[1]) / 0.05))
        for i in range(1, n):
            x = a[0] + (b[0] - a[0]) * i / n
            y = a[1] + (b[1] - a[1]) * i / n
            for p, bb, pn in pads:
                if pn != net and rect_dist(x, y, bb) < FINE_W / 2 + FINE_CLR:
                    return False
            for vx, vy, vn in vias:
                if vn != net and math.hypot(vx - x, vy - y) < VIA_D / 2 + FINE_W / 2 + FINE_CLR:
                    return False
            for sa, sb, sn, sw in segs:
                if sn != net and seg_dist(x, y, sa, sb) < sw / 2 + FINE_W / 2 + FINE_CLR:
                    return False
        return True

    def add_via(x, y, net):
        v = pcbnew.PCB_VIA(board)
        v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
        v.SetWidth(MM(VIA_D))
        v.SetDrill(MM(VIA_DRILL))
        v.SetNet(board.FindNet(net))
        board.Add(v)
        vias.append((x, y, net))

    def add_track(a, b, net, w=FAN_W):
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
        t.SetWidth(MM(w))
        t.SetLayer(pcbnew.F_Cu)
        t.SetNet(board.FindNet(net))
        board.Add(t)
        segs.append((a, b, net, w))

    jobs = []
    for fp in board.GetFootprints():
        if any(p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH and p.GetNetname() in PLANE_NETS for p in fp.Pads()):
            continue  # through-hole plane pins already reach the planes
        for pad in fp.Pads():
            if (pad.GetNetname() in FANOUT_NETS and pad.GetAttribute() == pcbnew.PAD_ATTRIB_SMD
                    and pad.IsOnLayer(pcbnew.F_Cu)):
                jobs.append((fp, pad))
    # the core rail has no plane, so it goes first; then by reference, since the
    # footprints' file order follows their random UUIDs
    jobs.sort(key=lambda j: (j[1].GetNetname() != CORE_NET, j[0].GetReference(), j[1].GetNumber()))
    for fp, pad in jobs:
        net = pad.GetNetname()
        fc = fp.GetPosition()
        fcx, fcy = TO(fc.x), TO(fc.y)
        pc = pad.GetPosition()
        px, py = TO(pc.x), TO(pc.y)
        bb = bbox_mm(pad)
        sx, sy = (bb[2] - bb[0]) / 2, (bb[3] - bb[1]) / 2
        if sx > 1.2 and sy > 1.2 and fp.GetReference()[0] == 'U':  # exposed pad: via grid
            n = 3
            for i in range(n):
                for j in range(n):
                    x = bb[0] + (i + 0.5) * (bb[2] - bb[0]) / n
                    y = bb[1] + (j + 0.5) * (bb[3] - bb[1]) / n
                    if free(x, y, net, own=fp):
                        add_via(x, y, net)
            if not any(bb[0] < vx < bb[2] and bb[1] < vy < bb[3] for vx, vy, _ in vias):
                skipped.append('%s.%s' % (fp.GetReference(), pad.GetNumber()))
            continue
        # Elongated pads escape along their long axis, away from the part; fine-pitch
        # pads (IC leads) only straight out, so the track never cuts across a neighbour.
        if sx > 1.3 * sy:
            base = 0 if px >= fcx else math.pi
        elif sy > 1.3 * sx:
            base = math.pi / 2 if py >= fcy else -math.pi / 2
        else:
            ax, ay = px - fcx, py - fcy
            base = math.atan2(ay, ax) if math.hypot(ax, ay) > 0.05 else 0
        fine = 2 * min(sx, sy) < 0.45
        done = False
        # fine-pitch leads: first a straight stub clear of the neighbours, then any direction
        edge0 = abs(sx * math.cos(base)) + abs(sy * math.sin(base))
        qfn = fine and any(min(b[2] - b[0], b[3] - b[1]) > 2.4 for b in map(bbox_mm, fp.Pads()))
        if qfn:
            # QFN: put the via in the ring between the leads and the exposed pad, so the
            # outside stays free for the signals' escape. No room: tie to a neighbour later.
            ib = base + math.pi
            for s in (0.1, 0.45, 0.8, 1.15, 1.5):
                r = edge0 + s + VIA_D / 2 + 0.1
                x = round((px + r * math.cos(ib)) * 40) / 40
                y = round((py + r * math.sin(ib)) * 40) / 40
                if free(x, y, net, (px, py), own=fp, w=FINE_W, clr=FINE_CLR):
                    add_track((px, py), (x, y), net, FINE_W)
                    add_via(x, y, net)
                    done = True
                    break
        if qfn and not done:
            pending.append((fp, pad, px, py, base, edge0, sx, sy))
            continue
        starts = [(px, py, None)]
        if fine:
            starts = [(round((px + (edge0 + s) * math.cos(base)) * 40) / 40,
                       round((py + (edge0 + s) * math.sin(base)) * 40) / 40, (px, py))
                      for s in (0.45, 0.8, 1.2, 1.7)]
        for (ox, oy, pre) in starts:
            if done:
                break
            if pre and not free(ox, oy, net, pre, w=FINE_W, clr=FINE_CLR, via=False):
                continue
            for dist in (0.0, 0.25, 0.5, 0.8, 1.2, 1.7, 2.3, 3.0):
                for k in (0, 1, -1, 2, -2, 3, -3, 4):
                    if pre and abs(k) > 2:
                        continue  # never double back over the IC
                    t = base + k * math.pi / 4
                    edge = 0 if pre else abs(sx * math.cos(t)) + abs(sy * math.sin(t))
                    r = edge + VIA_D / 2 + 0.1 + dist
                    x = round((ox + r * math.cos(t)) * 40) / 40
                    y = round((oy + r * math.sin(t)) * 40) / 40
                    if pre:
                        ok = (free(ox, oy, net, pre, w=FINE_W, clr=FINE_CLR, via=False) and
                              free(x, y, net, (ox, oy), w=FINE_W, clr=FINE_CLR))
                    else:
                        ok = free(x, y, net, (px, py))
                    if ok:
                        if pre:
                            add_track(pre, (ox, oy), net, FINE_W)
                        add_track((ox, oy), (x, y), net, FINE_W if pre else FAN_W)
                        add_via(x, y, net)
                        done = True
                        break
                if done:
                    break
        if not done:
            pending.append((fp, pad, px, py, base, edge0, sx, sy))

    # Second pass: tie a pad that found no via spot to a nearby same-net pad
    # (usually its decoupling cap), whose own fanout via then reaches the plane.
    def key(p):
        return (p.GetParentFootprint().GetReference(), p.GetNumber())
    stuck = {key(j[1]) for j in pending}  # no via yet: tying to these would make an island
    for fp, pad, px, py, base, edge0, sx, sy in pending:
        net = pad.GetNetname()
        near = []
        # an adjacent same-net lead of the same IC: a straight pin-to-pin link is enough
        for q in fp.Pads():
            qc = q.GetPosition()
            if (q != pad and q.GetNetname() == net and key(q) not in stuck
                    and math.hypot(TO(qc.x) - px, TO(qc.y) - py) < 0.8):
                add_track((px, py), (TO(qc.x), TO(qc.y)), net, FINE_W)
                stuck.discard(key(pad))
                break
        else:
            q = None
        if q is not None:
            continue
        for q, bb, n in pads:
            if (n != net or q.GetParentFootprint() == fp or q.GetAttribute() != pcbnew.PAD_ATTRIB_SMD
                    or key(q) in stuck):
                continue
            qc = q.GetPosition()
            d = math.hypot(TO(qc.x) - px, TO(qc.y) - py)
            if d < 4.0:
                near.append((d, TO(qc.x), TO(qc.y)))
        done = False
        for d, qx, qy in sorted(near):
            for s in (0.45, 0.8, 1.2):
                ox = round((px + (edge0 + s) * math.cos(base)) * 40) / 40
                oy = round((py + (edge0 + s) * math.sin(base)) * 40) / 40
                if (free(ox, oy, net, (px, py), w=FINE_W, clr=FINE_CLR, via=False) and
                        free_seg((ox, oy), (qx, qy), net)):
                    add_track((px, py), (ox, oy), net, FINE_W)
                    add_track((ox, oy), (qx, qy), net, FINE_W)
                    stuck.discard(key(pad))
                    done = True
                    break
            if done:
                break
        if not done:
            skipped.append('%s.%s' % (fp.GetReference(), pad.GetNumber()))
    return len(vias), skipped


class Grid:
    """GRID-mm raster of one copper layer around a window, for short maze routes."""

    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0 = x0, y0
        self.nx, self.ny = int((x1 - x0) / GRID) + 1, int((y1 - y0) / GRID) + 1
        self.blocked = bytearray(self.nx * self.ny)

    def cell(self, x, y):
        return (round((x - self.x0) / GRID), round((y - self.y0) / GRID))

    def xy(self, c):
        return (self.x0 + c[0] * GRID, self.y0 + c[1] * GRID)

    def cells_near(self, bb, r):
        """Cells within r of the box bb (x0, y0, x1, y1)."""
        for i in range(max(0, int((bb[0] - r - self.x0) / GRID)), min(self.nx, int((bb[2] + r - self.x0) / GRID) + 2)):
            for j in range(max(0, int((bb[1] - r - self.y0) / GRID)), min(self.ny, int((bb[3] + r - self.y0) / GRID) + 2)):
                if rect_dist(self.x0 + i * GRID, self.y0 + j * GRID, bb) < r:
                    yield (i, j)

    def block(self, bb, r):
        for i, j in self.cells_near(bb, r):
            self.blocked[j * self.nx + i] = 1

    def block_seg(self, a, b, r):
        for i, j in self.cells_near((min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])), r):
            if seg_dist(self.x0 + i * GRID, self.y0 + j * GRID, a, b) < r:
                self.blocked[j * self.nx + i] = 1

    def block_outside_board(self, margin):
        for i in range(self.nx):
            for j in range(self.ny):
                x, y = self.xy((i, j))
                if not (X0 + margin < x < X0 + W - margin and Y0 + margin < y < Y0 + H - margin):
                    self.blocked[j * self.nx + i] = 1

    def path(self, sources, targets):
        """Cheapest 8-way path from any source cell to any target cell, as corner cells."""
        steps = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1),
                 (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        dist = {c: 0 for c in sources}
        prev = {}
        heap = [(0, c) for c in sources]
        heapq.heapify(heap)
        while heap:
            d, c = heapq.heappop(heap)
            if d > dist.get(c, 1e9):
                continue
            if c in targets:
                p = [c]
                while p[-1] in prev:
                    p.append(prev[p[-1]])
                return [p[0]] + [m for a, m, b in zip(p, p[1:], p[2:])
                                 if (m[0] - a[0], m[1] - a[1]) != (b[0] - m[0], b[1] - m[1])] + [p[-1]]
            for dx, dy, w in steps:
                n = (c[0] + dx, c[1] + dy)
                if not (0 <= n[0] < self.nx and 0 <= n[1] < self.ny):
                    continue
                if self.blocked[n[1] * self.nx + n[0]] and n not in targets:
                    continue
                if c in prev and (c[0] - prev[c][0], c[1] - prev[c][1]) != (dx, dy):
                    w += 0.5  # prefer few, long segments
                if d + w < dist.get(n, 1e9):
                    dist[n] = d + w
                    prev[n] = c
                    heapq.heappush(heap, (d + w, n))
        return None


def add_path(board, pts, layer, net, w):
    for a, b in zip(pts, pts[1:]):
        if a == b:
            continue
        t = pcbnew.PCB_TRACK(board)
        t.SetStart(pcbnew.VECTOR2I(MM(a[0]), MM(a[1])))
        t.SetEnd(pcbnew.VECTOR2I(MM(b[0]), MM(b[1])))
        t.SetWidth(MM(w))
        t.SetLayer(layer)
        t.SetNet(board.FindNet(net))
        board.Add(t)


def core_vias(board):
    return [(TO(v.GetPosition().x), TO(v.GetPosition().y)) for v in board.GetTracks()
            if v.GetClass() == 'PCB_VIA' and v.GetNetname() == CORE_NET]


def link_pads(board, skipped):
    """Track each fanout pad that found no via spot to the nearest other copper of its
    net on F.Cu (a cap pad, or a via). Returns the pads still unlinked."""
    left = []
    for ref in skipped:
        r, num = ref.split('.')
        pad = board.FindFootprintByReference(r).FindPadByNumber(num)
        net = pad.GetNetname()
        px, py = TO(pad.GetPosition().x), TO(pad.GetPosition().y)
        g = Grid(px - 5, py - 5, px + 5, py + 5)
        r_obs = FINE_W / 2 + FINE_CLR
        targets = set()
        for p in board.GetPads():
            if not p.IsOnLayer(pcbnew.F_Cu) or p == pad:
                continue
            bb = bbox_mm(p)
            if p.GetNetname() == net and '%s.%s' % (p.GetParentFootprint().GetReference(), p.GetNumber()) in skipped:
                g.block(bb, r_obs)  # no via of its own either: linking to it would make an island
            elif p.GetNetname() == net:
                targets |= set(g.cells_near(bb, 0))
            else:
                g.block(bb, r_obs + (0.1 if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH else 0))
        for t in board.GetTracks():
            if t.GetClass() == 'PCB_VIA':
                c = t.GetPosition()
                vb = (TO(c.x), TO(c.y), TO(c.x), TO(c.y))
                if t.GetNetname() == net:
                    targets |= set(g.cells_near(vb, GRID))
                else:
                    g.block(vb, VIA_D / 2 + r_obs)
            elif t.GetLayer() == pcbnew.F_Cu:
                a = (TO(t.GetStart().x), TO(t.GetStart().y))
                b = (TO(t.GetEnd().x), TO(t.GetEnd().y))
                if t.GetNetname() == net:
                    continue
                g.block_seg(a, b, TO(t.GetWidth()) / 2 + r_obs)
        g.block_outside_board(0.5)
        corners = g.path(set(g.cells_near(bbox_mm(pad), 0)) | {g.cell(px, py)}, targets)
        if corners is None:
            left.append(ref)
            continue
        add_path(board, [g.xy(c) for c in corners], pcbnew.F_Cu, net, FINE_W)
    return left


def preroute(board, nets):
    """Maze-route nets ({name: width}) pad to pad on F.Cu. A net that doesn't route
    completely is taken up again and left to Freerouting. Returns the pads left unrouted."""
    left = []
    clr = 0.15
    for net, w in nets.items():
        before = len(left)
        pads = sorted((p for p in board.GetPads() if p.GetNetname() == net),
                      key=lambda p: (p.GetParentFootprint().GetReference(), p.GetNumber()))
        pads.sort(key=lambda p: p.GetParentFootprint().GetReference()[0] != 'U')  # start at the IC
        bbs = [bbox_mm(p) for p in pads]
        g = Grid(min(b[0] for b in bbs) - 3, min(b[1] for b in bbs) - 3,
                 max(b[2] for b in bbs) + 3, max(b[3] for b in bbs) + 3)
        for p in board.GetPads():
            if p.IsOnLayer(pcbnew.F_Cu) and p.GetNetname() != net:
                g.block(bbox_mm(p), w / 2 + clr + (0.1 if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH else 0))
        for t in board.GetTracks():
            if t.GetNetname() != net and t.GetClass() == 'PCB_VIA':
                c = t.GetPosition()
                g.block((TO(c.x), TO(c.y), TO(c.x), TO(c.y)), TO(t.GetWidth(pcbnew.F_Cu)) / 2 + w / 2 + clr)
            elif t.GetNetname() != net and t.GetLayer() == pcbnew.F_Cu:
                g.block_seg((TO(t.GetStart().x), TO(t.GetStart().y)), (TO(t.GetEnd().x), TO(t.GetEnd().y)),
                            TO(t.GetWidth()) / 2 + w / 2 + clr)
        g.block_outside_board(0.5)
        tree = set(g.cells_near(bbs[0], 0)) | {g.cell((bbs[0][0] + bbs[0][2]) / 2, (bbs[0][1] + bbs[0][3]) / 2)}
        for p, bb in zip(pads[1:], bbs[1:]):
            target = set(g.cells_near(bb, 0)) | {g.cell((bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2)}
            corners = g.path(tree, target)
            if corners is None:
                left.append('%s.%s' % (p.GetParentFootprint().GetReference(), p.GetNumber()))
                continue
            add_path(board, [g.xy(c) for c in corners], pcbnew.F_Cu, net, w)
            for a, b in zip(corners, corners[1:]):
                n = max(abs(b[0] - a[0]), abs(b[1] - a[1]), 1)
                for k in range(n + 1):
                    tree.add((a[0] + (b[0] - a[0]) * k // n, a[1] + (b[1] - a[1]) * k // n))
            tree |= target
        if len(left) > before:
            for t in list(board.GetTracks()):
                if t.GetNetname() == net:
                    board.Delete(t)
        else:
            PRE_DONE.add(net)
    return left


def join_core(board):
    """Join the CORE_NET fanout vias with a track tree on In2 (maze search around the
    other nets' vias and drilled pads), cut into the +3V3 plane. Returns the number of
    vias left unjoined."""
    terms = core_vias(board)
    if len(terms) < 2:
        return 0
    g = Grid(min(x for x, _ in terms) - 4, min(y for _, y in terms) - 4,
             max(x for x, _ in terms) + 4, max(y for _, y in terms) + 4)
    r_obs = IN2_W / 2 + IN2_CLR
    for v in board.GetTracks():
        if v.GetClass() == 'PCB_VIA' and v.GetNetname() != CORE_NET:
            c = v.GetPosition()
            g.block((TO(c.x), TO(c.y), TO(c.x), TO(c.y)), TO(v.GetWidth(pcbnew.F_Cu)) / 2 + r_obs)
    for p in board.GetPads():
        if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH) and p.GetNetname() != CORE_NET:
            g.block(bbox_mm(p), r_obs)
    g.block_outside_board(0.5 + IN2_W / 2)
    cells = [g.cell(x, y) for x, y in terms]
    tree = {cells[0]}
    todo = set(cells[1:]) - tree
    while todo:
        corners = g.path(tree, todo)
        if corners is None:
            break
        # end exactly on the via centres the path joins
        pts = [g.xy(c) for c in corners]
        for k in (0, -1):
            pts[k] = min(terms, key=lambda t: math.hypot(t[0] - pts[k][0], t[1] - pts[k][1])) \
                if corners[k] in cells else pts[k]
        add_path(board, pts, pcbnew.In2_Cu, CORE_NET, IN2_W)
        # every cell along the new path joins the tree
        for a, b in zip(corners, corners[1:]):
            n = max(abs(b[0] - a[0]), abs(b[1] - a[1]))
            for k in range(n + 1):
                tree.add((a[0] + (b[0] - a[0]) * k // n, a[1] + (b[1] - a[1]) * k // n))
        todo.discard(corners[0])
    return len(todo)


def snapshot(board):
    """The fanout nets' tracks and vias, as plain data."""
    out = []
    for t in board.GetTracks():
        if t.GetNetname() in FANOUT_NETS + tuple(PRE_DONE):
            if t.GetClass() == 'PCB_VIA':
                p = t.GetPosition()
                out.append(('via', t.GetNetname(), (p.x, p.y), None, t.GetWidth(pcbnew.F_Cu), t.GetDrillValue()))
            else:
                a, b = t.GetStart(), t.GetEnd()
                out.append(('track', t.GetNetname(), (a.x, a.y), (b.x, b.y), t.GetWidth(), t.GetLayer()))
    return out


def restore(board, snap):
    """The DSN leaves the fanout nets out, and Freerouting returns their copper under the
    wrong net or not at all: replace whatever came back with the snapshot."""
    for t in list(board.GetTracks()):
        if t.GetNetname() in FANOUT_NETS + tuple(PRE_DONE):
            board.Delete(t)
    for kind, net, a, b, w, extra in snap:
        if kind == 'via':
            t = pcbnew.PCB_VIA(board)
            t.SetPosition(pcbnew.VECTOR2I(*a))
            t.SetWidth(w)
            t.SetDrill(extra)
        else:
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(*a))
            t.SetEnd(pcbnew.VECTOR2I(*b))
            t.SetWidth(w)
            t.SetLayer(extra)
        t.SetNet(board.FindNet(net))
        board.Add(t)


def preroute_vias(board):
    """Route PREROUTE_VIAS with finish.py's layered maze, trying both orders. Returns the
    nets left to Freerouting."""
    import finish  # imports this module: load it only when needed
    ends = [(n, board.FindFootprintByReference(r1).FindPadByNumber(p1),
             board.FindFootprintByReference(r2).FindPadByNumber(p2)) for n, r1, p1, r2, p2 in PREROUTE_VIAS]
    for order in (ends, ends[::-1]):
        count = finish.unconnected(board)
        added = []
        for net, a, b in order:
            new, count = finish.join(board, a.GetNetCode(), [a], [b], count)
            if new is None:
                break
            added += new
        else:
            PRE_DONE.update(n for n, _, _ in ends)
            return []
        for i in added:
            board.Delete(i)
    return [n for n, _, _ in ends]


def strip_plane_nets(dsn):
    """Drop the fanout nets from the DSN network so Freerouting leaves them alone."""
    t = open(dsn).read()
    for net in FANOUT_NETS + tuple(PRE_DONE):
        pat = re.compile(r'\(net "?%s"?\s*\(pins[^)]*\)\s*\)' % re.escape(net))
        t, n = pat.subn('', t)
        if not n:
            raise SystemExit('net %s not found in DSN' % net)
    t = re.sub(r'\(clearance ([\d.]+)', lambda m: '(clearance %g' % (float(m.group(1)) + DSN_EXTRA_CLR), t)
    open(dsn, 'w').write(t)


def cleanup(board):
    """Fix Freerouting leftovers: thin via rings and vias that connect nothing."""
    tracks = [t for t in board.GetTracks() if t.GetClass() == 'PCB_TRACK']
    for t in tracks:
        if t.GetWidth() < MM(0.1):  # Freerouting necks down to the pad width
            t.SetWidth(MM(0.1))
    for v in [t for t in board.GetTracks() if t.GetClass() == 'PCB_VIA']:
        if v.GetWidth(pcbnew.F_Cu) - v.GetDrillValue() < MM(0.2):
            v.SetDrill(v.GetWidth(pcbnew.F_Cu) - MM(0.2))
        if v.GetNetname() in PLANE_NETS:
            continue
        pos = v.GetPosition()
        r = v.GetWidth(pcbnew.F_Cu) / 2
        layers = {t.GetLayer() for t in tracks if t.GetNetCode() == v.GetNetCode() and
                  min((t.GetStart() - pos).EuclideanNorm(), (t.GetEnd() - pos).EuclideanNorm()) < r}
        for p in board.GetPads():
            if p.GetNetCode() == v.GetNetCode() and p.HitTest(pos):
                layers |= {pcbnew.F_Cu, pcbnew.B_Cu} if p.GetAttribute() == pcbnew.PAD_ATTRIB_PTH \
                    else {p.GetPrincipalLayer()}
        if len(layers) < 2:
            board.Delete(v)


def pour(board, layer, net):
    z = pcbnew.ZONE(board)
    z.SetLayer(layer)
    z.SetNet(board.FindNet(net))
    poly = z.Outline()
    poly.NewOutline()
    for (x, y) in ((X0, Y0), (X0 + W, Y0), (X0 + W, Y0 + H), (X0, Y0 + H)):
        poly.Append(MM(x), MM(y))
    z.SetMinThickness(MM(0.2))
    z.SetLocalClearance(MM(0.25))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THT_THERMAL)  # SMD pads solid
    z.SetThermalReliefGap(MM(0.3))
    z.SetThermalReliefSpokeWidth(MM(0.4))
    board.Add(z)


def main():
    base = os.path.splitext(OUT)[0]
    dsn, ses = base + '.dsn', base + '.ses'
    board = pcbnew.LoadBoard(OUT)
    for t in list(board.GetTracks()):
        board.Delete(t)
    for z in list(board.Zones()):
        if z.GetLayer() in (pcbnew.F_Cu, pcbnew.B_Cu):
            board.Delete(z)
    print('preroute: no path for %s' % (preroute(board, PREROUTE) or 'none'))
    nvias, skipped = fanout(board)
    print('fanout: %d vias, no room for %s' % (nvias, skipped or 'none'))
    print('core tree: %d vias unjoined' % join_core(board))
    print('pads linked on F.Cu, still unlinked: %s' % (link_pads(board, skipped) or 'none'))
    print('late preroute: no path for %s' % (preroute(board, PREROUTE_LATE) or 'none'))
    print('preroute with vias: left to the autorouter %s' % (preroute_vias(board) or 'none'))
    print('prerouted:', ', '.join(sorted(PRE_DONE)))
    keep = snapshot(board)
    if not pcbnew.ExportSpecctraDSN(board, dsn):
        raise SystemExit('DSN export failed')
    strip_plane_nets(dsn)
    if PASSES != 'reuse':  # 'reuse': import the .ses left by the last run
        subprocess.run([JAVA, '-jar', JAR, '-de', dsn, '-do', ses, '-mp', PASSES,
                        '--gui.enabled=false', '--usage_and_diagnostic_data.disable_analytics=true',
                        '--profile.allow_telemetry=false'], check=True)
    if not pcbnew.ImportSpecctraSES(board, ses):
        raise SystemExit('SES import failed')
    restore(board, keep)
    cleanup(board)
    pour(board, pcbnew.F_Cu, '/GND')
    pour(board, pcbnew.B_Cu, '/GND')
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    pcbnew.SaveBoard(OUT, board)
    os.remove(dsn)
    print('routed', OUT)


if __name__ == '__main__':
    main()
