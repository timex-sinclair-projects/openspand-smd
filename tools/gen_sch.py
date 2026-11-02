"""Generate hardware/OpenSpand-SMD.kicad_sch from design.py.

Layout style: each part is placed once, every connected pin gets a net label,
unused pins get a no-connect flag. Parts are grouped by functional block.
"""
import copy
import os
import uuid

import design
from kisexp import S, Sym, dump, find, first, parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HW = os.path.join(ROOT, 'hardware')
KICAD_SYM = os.environ.get('KICAD_SYMBOL_DIR',
                           '/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols')
LIBS = {'OpenSpandSMD': os.path.join(HW, 'lib', 'OpenSpandSMD.kicad_sym')}
G = 2.54
# Stable UUIDs so regenerating keeps the PCB <-> schematic links intact.
NS = uuid.UUID('6f1d1c2e-3a57-4c43-9d55-0b6e5f0c5a11')


def sid(*a):
    return str(uuid.uuid5(NS, '/'.join(str(x) for x in a)))


ROOT_UUID = sid('root')
_libcache = {}


def lib_file(lib):
    return LIBS.get(lib) or os.path.join(KICAD_SYM, lib + '.kicad_sym')


def load_symbol(lib_id):
    lib, name = lib_id.split(':')
    if lib not in _libcache:
        _libcache[lib] = {s[1]: s for s in find(parse(open(lib_file(lib)).read()), 'symbol')}
    syms = _libcache[lib]
    s = copy.deepcopy(syms[name])
    ext = first(s, 'extends')
    if ext:  # flatten "extends": parent graphics + child properties
        parent = copy.deepcopy(syms[ext[1]])
        props = {p[1]: p for p in find(s, 'property')}
        out = [Sym('symbol'), name]
        for item in parent[2:]:
            if isinstance(item, list) and item[0] == 'property' and item[1] in props:
                out.append(props.pop(item[1]))
            elif isinstance(item, list) and item[0] == 'symbol':
                item[1] = item[1].replace(ext[1] + '_', name + '_', 1)
                out.append(item)
            else:
                out.append(item)
        out[2:2] = list(props.values())
        s = out
    s[1] = lib_id
    return s


def pins_of(sym):
    out = []

    def walk(n, unit):
        for c in n:
            if isinstance(c, list) and c:
                if c[0] == 'symbol':
                    walk(c, int(c[1].rsplit('_', 2)[-2]))
                elif c[0] == 'pin':
                    at = first(c, 'at')
                    out.append(dict(num=first(c, 'number')[1], name=first(c, 'name')[1],
                                    type=str(c[1]), x=float(at[1]), y=float(at[2]),
                                    ang=int(float(at[3])), unit=unit,
                                    hidden=bool(first(c, 'hide'))))
    walk(sym, 0)
    return out


def bbox(pins):
    xs = [p['x'] for p in pins] or [0]
    ys = [p['y'] for p in pins] or [0]
    return min(xs), max(xs), min(ys), max(ys)


def label_for(p, sx, sy, net):
    x, y = sx + p['x'], sy - p['y']
    ang = {0: 180, 180: 0, 90: 270, 270: 90}[p['ang']]
    just = 'right' if ang in (180, 270) else 'left'
    return S('label', net, S('at', round(x, 2), round(y, 2), ang),
             S('effects', S('font', S('size', 1.27, 1.27)), S('justify', Sym(just), Sym('bottom'))),
             S('uuid', sid('label', net, x, y)))


def no_connect(p, sx, sy):
    x, y = sx + p['x'], sy - p['y']
    return S('no_connect', S('at', round(x, 2), round(y, 2)), S('uuid', sid('nc', x, y)))


def fprop(name, value, x, y, hide=False, ang=0):
    eff = S('effects', S('font', S('size', 1.27, 1.27)))
    if hide:
        eff.append(S('hide', Sym('yes')))
    return S('property', name, value, S('at', round(x, 2), round(y, 2), ang), eff)


def symbol_instance(p, lib_sym, sx, sy, pins):
    x0, x1, y0, y1 = bbox(pins)
    u = sid('sym', p['ref'])
    two_pin_vertical = len(pins) <= 2 and all(q['ang'] in (90, 270) for q in pins)
    if two_pin_vertical:
        rpos, vpos = (sx + 2.54, sy - 1.27), (sx + 2.54, sy + 1.27)
    else:
        rpos, vpos = (sx, sy - y1 - 2.54), (sx, sy - y0 + 2.54)
    node = S('symbol', S('lib_id', lib_sym[1]), S('at', sx, sy, 0), S('unit', 1),
             S('exclude_from_sim', Sym('no')), S('in_bom', Sym('yes' if p.get('in_bom', True) and not p.get('dnp') else 'no')),
             S('on_board', Sym('yes')), S('dnp', Sym('yes' if p.get('dnp') else 'no')),
             S('uuid', u))
    rp = fprop('Reference', p['ref'], *rpos)
    vp = fprop('Value', p['value'], *vpos)
    if two_pin_vertical:
        for pr in (rp, vp):
            first(pr, 'effects').append(S('justify', Sym('left')))
    node += [rp, vp,
             fprop('Footprint', p['fp'], sx, sy, True),
             fprop('Datasheet', '', sx, sy, True),
             fprop('Description', '', sx, sy, True),
             fprop('LCSC', p['lcsc'], sx, sy, True),
             fprop('Note', p.get('note', ''), sx, sy, True)]
    if p.get('mpn'):
        node.append(fprop('MPN', p['mpn'], sx, sy, True))
    for q in pins:
        node.append(S('pin', q['num'], S('uuid', sid('pin', p['ref'], q['num']))))
    node.append(S('instances', S('project', design.PROJECT,
                                 S('path', '/' + ROOT_UUID, S('reference', p['ref']), S('unit', 1)))))
    return node


def snap(v):
    return round(v / G) * G


def main():
    lib_syms = {}
    items = []
    blocks = []
    for p in design.parts:
        if p['block'] not in blocks:
            blocks.append(p['block'])
    for p in design.parts:
        if p['sym'] not in lib_syms:
            lib_syms[p['sym']] = load_symbol(p['sym'])
    flag = load_symbol('power:PWR_FLAG')
    lib_syms['power:PWR_FLAG'] = flag

    # ---- place blocks in columns of cells
    cur_x, cur_y, row_h = 25.4, 30.48, 0
    page_w = 800
    for blk in blocks:
        members = [p for p in design.parts if p['block'] == blk]
        # heading
        items.append(S('text', blk, S('exclude_from_sim', Sym('no')),
                       S('at', cur_x, cur_y, 0),
                       S('effects', S('font', S('size', 3, 3), S('bold', Sym('yes'))),
                         S('justify', Sym('left'), Sym('bottom'))),
                       S('uuid', sid('text', blk))))
        cur_y += 7.62
        bx = cur_x
        for p in members:
            sym = lib_syms[p['sym']]
            pins = [q for q in pins_of(sym) if q['unit'] in (0, 1)]
            units = {q['unit'] for q in pins_of(sym)}
            assert units <= {0, 1}, (p['ref'], units)
            x0, x1, y0, y1 = bbox(pins)
            lab = max([len(n or '') for n in p['pins'].values()] + [3]) * 1.0 + 3
            left_m = (-x0 + lab) if any(q['ang'] == 0 for q in pins) else max(-x0, 3) + 8
            right_m = (x1 + lab) if any(q['ang'] == 180 for q in pins) else max(x1, 3) + 8
            top_m = y1 + (lab if any(q['ang'] == 270 for q in pins) else 5)
            bot_m = -y0 + (lab if any(q['ang'] == 90 for q in pins) else 5)
            w, h = left_m + right_m, top_m + bot_m
            if bx + w > page_w:
                bx = cur_x
                cur_y += row_h + 5
                row_h = 0
            sx, sy = snap(bx + left_m), snap(cur_y + top_m)
            items.append(symbol_instance(p, sym, sx, sy, pins))
            for q in pins:
                net = p['pins'].get(q['num'], 'MISSING')
                if net == 'MISSING':
                    if q['type'] != 'no_connect':
                        raise SystemExit('%s pin %s (%s) not in design' % (p['ref'], q['num'], q['name']))
                    net = None
                if net:
                    items.append(label_for(q, sx, sy, net))
                elif q['type'] != 'no_connect':
                    items.append(no_connect(q, sx, sy))
            extra = set(p['pins']) - {q['num'] for q in pins}
            if extra:
                raise SystemExit('%s: pins %s not on symbol' % (p['ref'], extra))
            bx += w + 5
            row_h = max(row_h, h)
        cur_y += row_h + 15
        row_h = 0

    # ---- power flags
    fx = cur_x
    fpin = pins_of(flag)[0]
    for i, net in enumerate(design.PWR_FLAGS):
        sx, sy = snap(fx + i * 20), snap(cur_y + 10)
        ref = '#FLG%02d' % (i + 1)
        items.append(symbol_instance(dict(ref=ref, value='PWR_FLAG', fp='', lcsc='', in_bom=False),
                                     flag, sx, sy, [fpin]))
        items.append(label_for(fpin, sx, sy, net))
    page_h = cur_y + 30

    sch = S('kicad_sch', S('version', 20260306), S('generator', 'eeschema'),
            S('generator_version', '10.0'), S('uuid', ROOT_UUID),
            S('paper', 'User', snap(page_w + 40), snap(max(page_h, 200))),
            S('title_block', S('title', 'OpenSpand SMD'), S('rev', '0.1'),
              S('company', 'Derived from OpenSpand HW 1.3.1 by Adam Klotblixt & ZX-Team, CC BY-SA 4.0'),
              S('comment', 1, 'Generated by tools/gen_sch.py from tools/design.py - edit the design, not this file'),
              S('comment', 2, 'GPIO map identical to OpenSpand_SW/pins.h (RP2350B, Olimex Pico2-XL build)')),
            S('lib_symbols', *lib_syms.values()))
    sch += items
    sch.append(S('sheet_instances', S('path', '/', S('page', '1'))))
    sch.append(S('embedded_fonts', Sym('no')))
    out = os.path.join(HW, design.PROJECT + '.kicad_sch')
    with open(out, 'w') as f:
        f.write(dump(sch) + '\n')
    print('wrote', out)


if __name__ == '__main__':
    main()
