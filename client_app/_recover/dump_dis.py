"""Dump disassembly of the original main.pyc so control flow is recoverable.

Python 3.12 .pyc cannot be decompiled by available tools, but `dis` gives the
full instruction stream, from which structure (loops, conditionals, calls with
exact arguments) can be reconstructed reliably.
"""
import dis
import io
import marshal
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def load_code(path):
    with open(path, "rb") as f:
        return marshal.loads(f.read()[16:])


def walk(code, depth=0, out=None, prefix=""):
    if out is None:
        out = []
    name = prefix + code.co_name
    out.append((depth, name, code))
    for c in code.co_consts:
        if hasattr(c, "co_code"):
            walk(c, depth + 1, out, name + ".")
    return out


code = load_code(sys.argv[1])
codes = walk(code)
want = sys.argv[2] if len(sys.argv) > 2 else None

for depth, name, c in codes:
    if want and want not in name:
        continue
    print("=" * 74)
    print("### %s   (line %d, depth %d)" % (name, c.co_firstlineno, depth))
    print("   args :", c.co_varnames[: c.co_argcount + c.co_kwonlyargcount])
    print("   names:", sorted(set(c.co_names)))
    print("=" * 74)
    try:
        dis.dis(c, depth=0)
    except Exception as e:
        print("   dis failed:", e)
    print()
