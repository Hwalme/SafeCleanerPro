# -*- coding: utf-8 -*-
"""
硬盘只读扫描 v1（不动任何文件）
输出：JSON + 控制台摘要
"""
import os, json, hashlib, time, sys

D = "D:\\"
E = "E:\\"

SKIP_DIRS = {
    "$RECYCLE.BIN", "System Volume Information", "pagefile.sys",
    "DumpStack.log", "DumpStack.log.tmp", "Config.Msi",
    "$WinREAgent", "Recovery", "ProgramData",
    # Antigravity 大缓存不递归
    "Antigravity_backup_20260905_082321", "Antigravity_backup_20260905_082321_IDE",
    # node_modules 深度太大
    "node_modules", ".pnpm-store", ".git", "__pycache__",
    # .venv 同上
    "venv", ".venv", "env", ".env",
    # 浏览器/cache 大目录
    ".cache", ".cargo", ".bun", ".npm", ".next", "dist", "build",
}

def safe_size(path, max_depth=2):
    """浅层估算（最多递归 max_depth 层，限时）"""
    total = 0
    files = 0
    dirs = 0
    try:
        for root, dirnames, filenames in os.walk(path):
            # 剪枝
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".git")]
            depth = root[len(path):].count(os.sep)
            if depth > max_depth:
                dirnames[:] = []
                continue
            for f in filenames:
                try:
                    fp = os.path.join(root, f)
                    st = os.stat(fp)
                    total += st.st_size
                    files += 1
                except OSError:
                    pass
            dirs += len(dirnames)
            # 时间控制：超过 3 秒就停
            if time.time() - start_time > 3:
                break
    except OSError as e:
        return None, str(e)
    return total, files

def scan_root(root, top_only=True):
    """列顶层 + 大致体量"""
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        try:
            st = os.stat(full)
        except OSError:
            continue
        entry = {"name": name, "is_dir": os.path.isdir(full)}
        if os.path.isdir(full):
            entry["size_bytes"] = 0
            entry["files_top"] = 0
            try:
                with os.scandir(full) as it:
                    count = 0
                    for x in it:
                        count += 1
                        if count > 200: break
                    entry["files_top"] = count
            except OSError:
                pass
            # 顶层目录用文件数 + 占用大小近似
            try:
                entry["size_bytes"] = sum(
                    os.scandir(full).__next__().stat().st_size
                    for _ in [0]
                ) if False else 0
            except Exception:
                pass
        else:
            entry["size_bytes"] = st.st_size
        out.append(entry)
    return out

def fmt(b):
    for u in ["B","KB","MB","GB","TB"]:
        if b < 1024: return f"{b:.1f}{u}"
        b /= 1024
    return f"{b:.1f}PB"

start_time = time.time()
print("=== D:\\ 顶层概览 ===")
d_top = scan_root(D)
total_d = 0
for e in d_top:
    sz = e.get("size_bytes", 0)
    total_d += sz
    marker = "/" if e["is_dir"] else ""
    print(f"  {e['name']:<35} {marker}  {fmt(sz):>10}")
print(f"  {'(顶层合计，仅文件)':<35}    {fmt(total_d):>10}")

print("\n=== D:\\Coding\\ 全部顶层 ===")
c_top = scan_root("D:\\Coding")
print(f"  共 {len(c_top)} 项")
total_c = 0
for e in c_top:
    sz = e.get("size_bytes", 0)
    total_c += sz
    print(f"  {e['name']:<35} {fmt(sz):>10}")
print(f"  {'(Coding 顶层合计)':<35} {fmt(total_c):>10}")

print("\n=== E:\\ 顶层 ===")
e_top = scan_root(E)
for e in e_top:
    print(f"  {e['name']:<35} {fmt(e.get('size_bytes',0)):>10}")

# 写报告
report = {
    "scan_time": time.strftime("%Y-%m-%d %H:%M:%S"),
    "D_top": d_top,
    "Coding_top": c_top,
    "E_top": e_top,
}
with open("D:\\Coding\\Organization\\_audit_readonly.json", "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"\n[报告已落盘] D:\\Coding\\Organization\\_audit_readonly.json  耗时 {time.time()-start_time:.1f}s")