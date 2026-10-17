"""Compare method inventory: original (pyc) vs current (source)."""
import ast
import marshal
import sys


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


orig = {}
for d, name, c in walk(load_code("target.exe_extracted/main.pyc")):
    if name.startswith("<module>"):
        orig[name.replace("<module>.", "")] = c.co_firstlineno

# current source
src = open("../main.py", encoding="utf-8").read()
tree = ast.parse(src)
cur = {}
for node in ast.walk(tree):
    if isinstance(node, ast.ClassDef):
        cur[node.name] = node.lineno
        for sub in node.body:
            if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cur[node.name + "." + sub.name] = sub.lineno
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.col_offset == 0:
        cur[node.name] = node.lineno

print("=" * 72)
print("ORIGINAL main.py: %d code objects, %d lines spanned" % (len(orig), max(orig.values())))
print("CURRENT  main.py: %d defs, %d lines" % (len(cur), len(src.splitlines())))
print("=" * 72)

missing = [k for k in orig if k not in cur]
print("\n### MISSING in current (%d):" % len(missing))
for k in sorted(missing, key=lambda x: orig[x]):
    print("   %-46s  orig line %d" % (k, orig[k]))

print("\n### PRESENT in both (%d):" % len([k for k in orig if k in cur]))
for k in sorted([k for k in orig if k in cur], key=lambda x: orig[x]):
    print("   %-46s  orig line %d  -> current line %d" % (k, orig[k], cur[k]))

extra = [k for k in cur if k not in orig]
print("\n### EXTRA in current (not in original):")
for k in sorted(extra, key=lambda x: cur[x]):
    print("   %-46s  current line %d" % (k, cur[k]))
