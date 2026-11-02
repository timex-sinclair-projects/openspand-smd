"""Minimal KiCad S-expression reader/writer."""
import re
import uuid as _uuid

_TOK = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()"]+')


class Sym(str):
    """Bare (unquoted) atom."""


def parse(text):
    stack = [[]]
    for m in _TOK.finditer(text):
        t = m.group(0)
        if t == '(':
            stack.append([])
        elif t == ')':
            x = stack.pop()
            stack[-1].append(x)
        elif t.startswith('"'):
            stack[-1].append(t[1:-1].replace('\\"', '"').replace('\\\\', '\\'))
        else:
            stack[-1].append(Sym(t))
    return stack[0][0]


def q(s):
    return '"' + str(s).replace('\\', '\\\\').replace('"', '\\"') + '"'


def fmt_num(v):
    if isinstance(v, float):
        s = ('%.4f' % v).rstrip('0').rstrip('.')
        return '0' if s in ('-0', '') else s
    return str(v)


def dump(node, indent=0):
    """Serialise a node; plain str -> quoted, Sym -> bare, numbers -> bare."""
    if isinstance(node, Sym):
        return str(node)
    if isinstance(node, str):
        return q(node)
    if isinstance(node, (int, float)):
        return fmt_num(node)
    tab = '\t' * indent
    head = [x for x in node if not isinstance(x, list)]
    kids = [x for x in node if isinstance(x, list)]
    s = '(' + ' '.join(dump(x) for x in head)
    if not kids:
        return s + ')'
    for k in kids:
        s += '\n' + tab + '\t' + dump(k, indent + 1)
    return s + '\n' + tab + ')'


def find(node, name):
    return [c for c in node if isinstance(c, list) and c and c[0] == name]


def first(node, name):
    r = find(node, name)
    return r[0] if r else None


def uid():
    return str(_uuid.uuid4())


def S(*a):
    """Build a list node whose first element is a bare symbol."""
    return [Sym(a[0])] + list(a[1:])
