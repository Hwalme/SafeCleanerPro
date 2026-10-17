"""Dump the FULL structure of the original main.pyc so we can reconstruct it."""
import marshal
import sys


def load_code(path):
    with open(path, "rb") as f:
        data = f.read()
    return marshal.loads(data[16:])


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

print("=" * 72)
print("FULL STRUCTURE")
print("=" * 72)
for depth, c in codes:
    if depth <= 2:
        print("%s%-46s line %-6s args=%s" % (
            "  " * depth, c.co_name, c.co_firstlineno, c.co_varnames[:c.co_argcount]))

print()
print("=" * 72)
print("ALL STRING LITERALS (>=3 chars), grouped by defining scope")
print("=" * 72)
for depth, c in codes:
    if depth > 1:
        continue
    strs = [k for k in c.co_consts if isinstance(k, str) and len(k) >= 3]
    if strs:
        print("\n### %s%s (line %s)" % ("  " * depth, c.co_name, c.co_firstlineno))
        for s in strs:
            print("    ", repr(s))
