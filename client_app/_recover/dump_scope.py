"""Dump every string literal grouped by its defining function, all depths."""
import marshal
import sys


def load_code(path):
    with open(path, "rb") as f:
        return marshal.loads(f.read()[16:])


def walk(code, depth=0, out=None):
    if out is None:
        out = []
    out.append((depth, code))
    for c in code.co_consts:
        if hasattr(c, "co_code"):
            walk(c, depth + 1, out)
    return out


code = load_code(sys.argv[1])
codes = walk(code)

target = sys.argv[2] if len(sys.argv) > 2 else None

for depth, c in codes:
    if target and c.co_name != target:
        continue
    strs = [k for k in c.co_consts if isinstance(k, str) and len(k) >= 2]
    if not strs:
        continue
    print("\n" + "=" * 68)
    print("### %s (line %s)  depth=%d" % (c.co_name, c.co_firstlineno, depth))
    print("=" * 68)
    print("  names:", sorted(set(c.co_names))[:40])
    for s in strs:
        print("   ", repr(s))
