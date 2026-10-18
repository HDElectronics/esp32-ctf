"""Load and flatten KiCad library symbols (resolving `extends`)."""
import copy
import os
import sys

from sexp import Sym, find, find1, parse

SYSLIB = "/usr/share/kicad/symbols"
LOCALLIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "defuse32.kicad_sym")
_cache = {}


def _lib(name):
    if name not in _cache:
        path = LOCALLIB if name == "defuse32" else os.path.join(SYSLIB, name + ".kicad_sym")
        _cache[name] = parse(open(path).read())
    return _cache[name]


def _raw(libname, sym):
    for s in find(_lib(libname), "symbol"):
        if s[1] == sym:
            return s
    raise KeyError("%s:%s" % (libname, sym))


def flat(libname, sym):
    """Return a flattened copy of symbol `sym` (named without library prefix)."""
    s = copy.deepcopy(_raw(libname, sym))
    ext = find1(s, "extends")
    if not ext:
        return s
    parent = flat(libname, ext[1])
    pname = parent[1]
    out = [Sym("symbol"), sym]
    childprops = {p[1]: p for p in find(s, "property")}
    for x in parent[2:]:
        if isinstance(x, list) and x[0] == "property":
            out.append(childprops.pop(x[1], x))
        elif isinstance(x, list) and x[0] == "symbol":
            x = copy.deepcopy(x)
            x[1] = sym + x[1][len(pname):]
            out.append(x)
        else:
            out.append(x)
    idx = max(i for i, x in enumerate(out) if isinstance(x, list) and x[0] == "property")
    for p in childprops.values():
        idx += 1
        out.insert(idx, p)
    return out


def _is_hidden(p):
    if any(isinstance(a, Sym) and a == "hide" for a in p):
        return True
    h = find1(p, "hide")
    return bool(h) and (len(h) == 1 or h[1] == "yes")


def pins(symnode):
    res = []
    for sub in find(symnode, "symbol"):
        parts = sub[1].rsplit("_", 2)
        unit, style = int(parts[-2]), int(parts[-1])
        for p in find(sub, "pin"):
            at = find1(p, "at")
            res.append(dict(unit=unit, style=style, type=str(p[1]), num=find1(p, "number")[1],
                            name=find1(p, "name")[1], x=float(at[1]), y=float(at[2]),
                            rot=float(at[3]) if len(at) > 3 else 0.0,
                            length=float(find1(p, "length")[1]), hidden=_is_hidden(p)))
    return res


def prop(symnode, key):
    for p in find(symnode, "property"):
        if p[1] == key:
            return p[2]
    return None


if __name__ == "__main__":
    s = flat(sys.argv[1], sys.argv[2])
    for p in find(s, "property"):
        if not p[1].startswith("ki_"):
            print("prop", p[1], "=", p[2])
    for p in pins(s):
        print(p)
