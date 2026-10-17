"""Extract constants, names and structure from a 3.12 .pyc without a decompiler.

The code objects retain all string literals, function/class names and the
module import list, which is exactly what we need to learn what the original
main.py wired up (esp. the dedup integration).
"""
import dis
import marshal
import sys


def load_code(path):
    with open(path, "rb") as f:
        data = f.read()
    # 3.12 header is 16 bytes
    return marshal.loads(data[16:])


def walk(code, depth=0, out=None):
    if out is None:
        out = []
    out.append((depth, code))
    for c in code.co_consts:
        if hasattr(c, "co_code"):
            walk(c, depth + 1, out)
    return out


path = sys.argv[1]
code = load_code(path)
codes = walk(code)

print("=" * 70)
print("MODULE:", path)
print("=" * 70)
print("top-level names imported/defined:")
print("  ", sorted(set(code.co_names)))
print()

print("=" * 70)
print("ALL STRING LITERALS (dedup-related first)")
print("=" * 70)
strings = set()
for _, c in codes:
    for k in c.co_consts:
        if isinstance(k, str) and len(k) > 1:
            strings.add(k)

keys = ("dedup", "查重", "Dedup", "重复", "去重", "duplicate", "冗余")
print("\n--- MATCHING dedup strings ---")
for s in sorted(strings):
    if any(k in s for k in keys):
        print("   ", repr(s))

print("\n--- ALL top-level class/def names ---")
for d in (0,):
    for depth, c in codes:
        if depth == d:
            for k in c.co_consts:
                if hasattr(k, "co_code"):
                    print("   %-40s (line %s)" % (k.co_name, k.co_firstlineno))

print("\n--- module-level constants that look like config ---")
for k in code.co_consts:
    if not hasattr(k, "co_code") and not isinstance(k, str):
        print("   ", repr(k)[:120])
