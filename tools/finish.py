"""Finish the connections the autorouter left open.

Reads the open connections from KiCad's DRC report, then routes each one with a maze search
across F.Cu and B.Cu, and where those are full, In2.Cu and In1.Cu (the +3V3 and GND
plane layers, where a track cuts a slot in the plane), adding vias where the path changes layer. A route that cuts off part of a plane is
taken up and tried again on the outer layers only. When a pad is boxed in, the nearest
signal net in its way is ripped up, the pad routed, and the ripped net routed again.
Run after route.py, with KiCad's Python:
  python3 finish.py
"""
import heapq
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile

import pcbnew

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_pcb import OUT, X0, Y0, W, H  # noqa: E402
from route import FANOUT_NETS, bbox_mm, rect_dist, seg_dist  # noqa: E402

MM = pcbnew.FromMM
TO = pcbnew.ToMM
GRID = 0.05
TW, CLR = 0.127, 0.135        # track width and clearance (the rule is 0.127)
VD, VDRILL = 0.45, 0.25
LAYERS = (pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In2_Cu, pcbnew.In1_Cu)
LAYER_COST = (1.0, 1.0, 1.6, 1.3)  # the plane layers only where the outer layers are full
# layer sets tried in turn: GND (In1) before +3V3 (In2), since a slot in the GND plane
# can't strand anything (ground also reaches both outer pours through many vias)
TRIES = ((pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In1_Cu), LAYERS, (pcbnew.F_Cu, pcbnew.B_Cu))
VIA_COST = 16                 # in grid steps: about 0.8 mm of track
MARGIN = 6.0                  # mm searched around the two ends


def open_connections(board_file, refill=False):
    with tempfile.TemporaryDirectory() as d:
        rpt = os.path.join(d, 'drc.json')
        subprocess.run(['kicad-cli', 'pcb', 'drc', '--format', 'json', '-o', rpt, board_file]
                       + (['--refill-zones'] if refill else []),
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return [[i['uuid'] for i in u['items']] for u in json.load(open(rpt))['unconnected_items']]


class Maze:
    def __init__(self, board, net, bb, layers=LAYERS, keepout=()):
        self.ok = [L in layers for L in LAYERS]
        self.x0, self.y0 = max(bb[0] - MARGIN, X0), max(bb[1] - MARGIN, Y0)
        self.nx = int((min(bb[2] + MARGIN, X0 + W) - self.x0) / GRID) + 1
        self.ny = int((min(bb[3] + MARGIN, Y0 + H) - self.y0) / GRID) + 1
        n = self.nx * self.ny
        self.track = [bytearray(n) for _ in LAYERS]  # 1: a track centre here breaks clearance
        self.via = bytearray(n)                       # 1: a via centre here breaks clearance
        win = (self.x0, self.y0, self.x0 + self.nx * GRID, self.y0 + self.ny * GRID)

        def hits(b, r):
            return not (b[2] + r < win[0] or b[0] - r > win[2] or b[3] + r < win[1] or b[1] - r > win[3])

        for p in board.GetPads():
            if p.GetNetCode() == net and p.GetNetCode() > 0:
                continue
            b = bbox_mm(p)
            if not hits(b, 1):
                continue
            clr = max(CLR, TO(p.GetOwnClearance(pcbnew.F_Cu)) + 0.005)
            drilled = p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH)
            for k, L in enumerate(LAYERS):
                if drilled or p.IsOnLayer(L):
                    self.block(self.track[k], b, TW / 2 + clr)
            if drilled or p.IsOnLayer(pcbnew.F_Cu) or p.IsOnLayer(pcbnew.B_Cu):
                self.block(self.via, b, VD / 2 + clr)
        for p in board.GetPads():  # holes, whatever their net: no via drilled into them
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                b = bbox_mm(p)
                if hits(b, 1):
                    self.block(self.via, b, VD / 2 + 0.25)
        for t in board.GetTracks():
            if t.GetNetCode() == net:
                continue
            clr = max(CLR, TO(t.GetOwnClearance(pcbnew.F_Cu)) + 0.005)
            if t.GetClass() == 'PCB_VIA':
                c = t.GetPosition()
                b = (TO(c.x), TO(c.y), TO(c.x), TO(c.y))
                r = TO(t.GetWidth(pcbnew.F_Cu)) / 2
                if hits(b, 1):
                    for arr in self.track:
                        self.block(arr, b, r + TW / 2 + clr)
                    self.block(self.via, b, r + VD / 2 + clr)
                continue
            if t.GetLayer() not in LAYERS:
                continue
            a = (TO(t.GetStart().x), TO(t.GetStart().y))
            e = (TO(t.GetEnd().x), TO(t.GetEnd().y))
            b = (min(a[0], e[0]), min(a[1], e[1]), max(a[0], e[0]), max(a[1], e[1]))
            if not hits(b, 1):
                continue
            r = TO(t.GetWidth()) / 2
            self.block_seg(self.track[LAYERS.index(t.GetLayer())], a, e, r + TW / 2 + clr)
            self.block_seg(self.via, a, e, r + VD / 2 + clr)  # a via goes through every layer
        # board edge, and the edge socket's own slots
        edges = [s for s in board.GetDrawings() if s.GetLayer() == pcbnew.Edge_Cuts]
        for fp in board.GetFootprints():
            edges += [s for s in fp.GraphicalItems() if s.GetLayer() == pcbnew.Edge_Cuts]
        for s in edges:
            b = bbox_mm(s)
            if hits(b, 1):
                for arr in self.track:
                    self.block(arr, b, TW / 2 + 0.3)
                self.block(self.via, b, VD / 2 + 0.3)
        for layer, kb in keepout:  # reserved for another net's track: no track, no via
            self.block(self.track[LAYERS.index(layer)], kb, 0)
            self.block(self.via, kb, VD / 2 + TW / 2 + CLR)
        for i in range(self.nx):
            for j in range(self.ny):
                x, y = self.xy(i, j)
                if not (X0 + 0.5 < x < X0 + W - 0.5 and Y0 + 0.5 < y < Y0 + H - 0.5):
                    for arr in self.track:
                        arr[j * self.nx + i] = 1
                    self.via[j * self.nx + i] = 1

    def xy(self, i, j):
        return (self.x0 + i * GRID, self.y0 + j * GRID)

    def cells(self, b, r):
        for i in range(max(0, int((b[0] - r - self.x0) / GRID)), min(self.nx, int((b[2] + r - self.x0) / GRID) + 2)):
            for j in range(max(0, int((b[1] - r - self.y0) / GRID)), min(self.ny, int((b[3] + r - self.y0) / GRID) + 2)):
                x, y = self.xy(i, j)
                if rect_dist(x, y, b) <= r:
                    yield i, j

    def block(self, arr, b, r):
        for i, j in self.cells(b, r):
            arr[j * self.nx + i] = 1

    def block_seg(self, arr, a, e, r):
        for i, j in self.cells((min(a[0], e[0]), min(a[1], e[1]), max(a[0], e[0]), max(a[1], e[1])), r):
            if seg_dist(*self.xy(i, j), a, e) < r:
                arr[j * self.nx + i] = 1

    def item_states(self, item):
        """(layer index, i, j) states covered by a pad, track or via."""
        out = set()
        if item.GetClass() == 'PCB_TRACK':
            a = (TO(item.GetStart().x), TO(item.GetStart().y))
            e = (TO(item.GetEnd().x), TO(item.GetEnd().y))
            k = LAYERS.index(item.GetLayer())
            r = TO(item.GetWidth()) / 2
            for i, j in self.cells((min(a[0], e[0]), min(a[1], e[1]), max(a[0], e[0]), max(a[1], e[1])), r):
                if seg_dist(*self.xy(i, j), a, e) < r:
                    out.add((k, i, j))
            return out
        b = bbox_mm(item)
        if item.GetClass() == 'PCB_VIA':
            b = (b[0] + 0.1, b[1] + 0.1, b[2] - 0.1, b[3] - 0.1)
        for k, L in enumerate(LAYERS):
            if self.ok[k] and (item.GetClass() == 'PCB_VIA' or item.IsOnLayer(L)):
                out |= {(k, i, j) for i, j in self.cells(b, 0)}
        return out

    def route(self, src, dst):
        tx = sum(i for _, i, _ in dst) / len(dst)
        ty = sum(j for _, _, j in dst) / len(dst)

        def h(i, j):
            return math.hypot(i - tx, j - ty) * 0.9

        steps = [(1, 0, 1), (-1, 0, 1), (0, 1, 1), (0, -1, 1),
                 (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414)]
        dist = {s: 0 for s in src}
        prev = {}
        heap = [(h(i, j), 0, s) for s in src for _, i, j in [s]]
        heapq.heapify(heap)
        while heap:
            _, d, s = heapq.heappop(heap)
            if d > dist.get(s, 1e18):
                continue
            if s in dst:
                path = [s]
                while path[-1] in prev:
                    path.append(prev[path[-1]])
                return path[::-1]
            k, i, j = s
            moves = []
            for dx, dy, w in steps:
                n = (k, i + dx, j + dy)
                if 0 <= n[1] < self.nx and 0 <= n[2] < self.ny and \
                        (not self.track[k][n[2] * self.nx + n[1]] or n in dst):
                    p = prev.get(s)
                    turn = 0.5 if p and p[0] == k and (i - p[1], j - p[2]) != (dx, dy) else 0
                    moves.append((n, w * LAYER_COST[k] + turn))
            if not self.via[j * self.nx + i]:
                for k2 in range(len(LAYERS)):
                    if k2 != k and self.ok[k2] and not self.track[k2][j * self.nx + i]:
                        moves.append(((k2, i, j), VIA_COST))
            for n, w in moves:
                nd = d + w
                if nd < dist.get(n, 1e18):
                    dist[n] = nd
                    prev[n] = s
                    heapq.heappush(heap, (nd + h(n[1], n[2]), nd, n))
        return None


def build(board, maze, path, net):
    """Turn a cell path into tracks (merged straight runs) and vias. Returns the new items."""
    netinfo = board.FindNet(board.GetNetInfo().GetNetItem(net).GetNetname())
    added = []
    runs = [[path[0]]]
    for s in path[1:]:
        if s[0] != runs[-1][-1][0]:
            v = pcbnew.PCB_VIA(board)
            x, y = maze.xy(s[1], s[2])
            v.SetPosition(pcbnew.VECTOR2I(MM(x), MM(y)))
            v.SetWidth(MM(VD))
            v.SetDrill(MM(VDRILL))
            v.SetNet(netinfo)
            board.Add(v)
            added.append(v)
            runs.append([s])
        else:
            runs[-1].append(s)
    for run in runs:
        corners = [run[0]] + [b for a, b, c in zip(run, run[1:], run[2:])
                              if (b[1] - a[1], b[2] - a[2]) != (c[1] - b[1], c[2] - b[2])] + [run[-1]]
        for a, b in zip(corners, corners[1:]):
            t = pcbnew.PCB_TRACK(board)
            t.SetStart(pcbnew.VECTOR2I(*[MM(v) for v in maze.xy(a[1], a[2])]))
            t.SetEnd(pcbnew.VECTOR2I(*[MM(v) for v in maze.xy(b[1], b[2])]))
            t.SetWidth(MM(TW))
            t.SetLayer(LAYERS[a[0]])
            t.SetNet(netinfo)
            board.Add(t)
            added.append(t)
    return added


def unconnected(board):
    """Open connections, counted by KiCad's DRC on a scratch copy (with the project's rules).
    kicad-cli refills the zones: the Python zone filler upsets the SWIG bindings."""
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, 'scratch.kicad_pcb')
        shutil.copy(os.path.splitext(OUT)[0] + '.kicad_pro', os.path.join(d, 'scratch.kicad_pro'))
        pcbnew.SaveBoard(f, board)
        return len(open_connections(f, refill=True))


def join(board, net, a_items, b_items, count, keepout=()):
    """Route from a_items to b_items, keeping it only if the board's open-connection count
    drops (a cut plane raises it). Returns (new items, new count) or (None, count)."""
    bbs = [bbox_mm(i) for i in a_items + b_items]
    box = (min(b[0] for b in bbs), min(b[1] for b in bbs), max(b[2] for b in bbs), max(b[3] for b in bbs))
    for layers in TRIES:
        maze = Maze(board, net, box, layers, keepout)
        src = set().union(*(maze.item_states(i) for i in a_items))
        dst = set().union(*(maze.item_states(i) for i in b_items))
        path = maze.route(src, dst) if src and dst else None
        if path is None:
            continue
        added = build(board, maze, path, net)
        now = unconnected(board)
        if now < count:
            return added, now
        for i in added:
            board.Delete(i)
    return None, count


def route_net(board, net, count):
    """Route every pad of a net from scratch, nearest pad first. Returns (items, count)."""
    groups = {}  # pads sharing a number (the edge socket's front, back and hole) go together
    for p in board.GetPads():
        if p.GetNetCode() == net:
            groups.setdefault((p.GetParentFootprint().GetReference(), p.GetNumber()), []).append(p)
    rest = list(groups.values())
    tree, added = rest.pop(0), []
    while rest:
        c = tree[0].GetPosition()
        rest.sort(key=lambda g: min((p.GetPosition() - c).EuclideanNorm() for p in g))
        new, count = join(board, net, tree + added, rest[0], count)
        if new is None:
            return None, added, count
        added += new
        tree += rest.pop(0)
    return added, added, count


def snapshot(board, net):
    out = []
    for t in list(board.GetTracks()):
        if t.GetNetCode() == net:
            if t.GetClass() == 'PCB_VIA':
                p = t.GetPosition()
                out.append(('via', (p.x, p.y), None, t.GetWidth(pcbnew.F_Cu), t.GetDrillValue()))
            else:
                a, b = t.GetStart(), t.GetEnd()
                out.append(('track', (a.x, a.y), (b.x, b.y), t.GetWidth(), t.GetLayer()))
            board.Delete(t)
    return out


def restore(board, net, snap):
    ni = board.FindNet(board.GetNetInfo().GetNetItem(net).GetNetname())
    for kind, a, b, w, extra in snap:
        t = pcbnew.PCB_VIA(board) if kind == 'via' else pcbnew.PCB_TRACK(board)
        if kind == 'via':
            t.SetPosition(pcbnew.VECTOR2I(*a))
            t.SetDrill(extra)
        else:
            t.SetStart(pcbnew.VECTOR2I(*a))
            t.SetEnd(pcbnew.VECTOR2I(*b))
            t.SetLayer(extra)
        t.SetWidth(w)
        t.SetNet(ni)
        board.Add(t)


def blockers(board, net, items, keep):
    """Signal nets with copper near the given items, nearest first."""
    near = {}
    for it in items:
        b = bbox_mm(it)
        for t in board.GetTracks():
            n = t.GetNetCode()
            if n == net or n in keep:
                continue
            tb = bbox_mm(t)
            d = max(tb[0] - b[2], b[0] - tb[2], tb[1] - b[3], b[1] - tb[3], 0)
            if d < 0.8:
                near[n] = min(near.get(n, 9), d)
    return sorted(near, key=near.get)


def main():
    todo = open_connections(OUT)
    board = pcbnew.LoadBoard(OUT)
    by_id = {i.m_Uuid.AsString(): i for i in list(board.GetPads()) + list(board.GetTracks())}
    # never ripped: planes and core, the regulator loop, and nets still waiting their turn
    keep = {board.FindNet(n).GetNetCode() for n in FANOUT_NETS + ('/VREG_LX', '/VREG_AVDD')}
    keep |= {by_id[i].GetNetCode() for pair in todo for i in pair}
    count = unconnected(board)
    left = 0
    for a_id, b_id in todo:
        a, b = by_id[a_id], by_id[b_id]
        net, name = a.GetNetCode(), a.GetNetname()
        added, count = join(board, net, [a], [b], count)
        if added is not None:
            print('%s: routed' % name)
            continue
        near = blockers(board, net, [a, b], keep)
        tries = [[r] for r in near[:6]] + [[r, q] for k, r in enumerate(near[:4]) for q in near[k + 1:4]]
        for rip in tries:
            names = '+'.join(board.GetNetInfo().GetNetItem(r).GetNetname() for r in rip)
            snaps = [snapshot(board, r) for r in rip]
            added, after = join(board, net, [a], [b], unconnected(board))
            redone = []
            ok = added is not None
            for r in rip if ok else []:
                r_added, r_all, after = route_net(board, r, after)
                redone += r_all
                if r_added is None:
                    ok = False
                    break
            if ok and after < count:
                count = after
                print('%s: routed after moving %s' % (name, names))
                break
            for i in redone + (added or []):
                board.Delete(i)
            for r, snap in zip(rip, snaps):
                restore(board, r, snap)
            count = unconnected(board)
        else:
            print('no path for', name)
            left += 1
    pcbnew.SaveBoard(OUT, board)
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--save-board', '-o', os.devnull, OUT],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print('%d of %d open connections routed' % (len(todo) - left, len(todo)))


if __name__ == '__main__':
    main()
