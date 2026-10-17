# -*- coding: utf-8 -*-
"""
org.py — Hwalme 硬盘整理系统 · 单一入口
================================================

把学到的全部知识封装成命令：PC-Plan 映射、安全红线、工具集成、资源护栏。

设计原则（来自 2026-09-12/13 的全部教训）：
  1. 按需整理      —— 每个命令回答一个具体问题，不做"一键全盘魔法"
  2. 安全第一      —— 红线区永不写；S/P 级文件只记路径+哈希，永不读内容
  3. 资源护栏      —— 所有扫描带 深度上限 + 时间预算 + 重目录排除，绝不跑满 IO
  4. 计划先行      —— 写动作先 plan 后 apply，apply 必须显式 --yes
  5. 可回滚        —— 每次 apply 留 manifest，undo 一键反向

命令一览：
  python org.py status                      体检：风险/dashboard（秒级）
  python org.py scan  <路径> [--depth 2] [--seconds 30]   只读结构扫描
  python org.py big   <路径> [--mb 100]     大文件清单（限深限时）
  python org.py dup   <路径> [--seconds 120]  重复文件（czkawka，自动排除权重目录）
  python org.py map                         PC-Plan 归位映射表（哪些该去哪）
  python org.py plan-move <源> <目标>        生成移动计划 JSON（不执行）
  python org.py apply   <plan.json> --yes   快照→复制→校验（源默认保留）
  python org.py undo    <plan.json>         反向回滚已 apply 的计划
  python org.py snapshot <路径>              robocopy 镜像到 snapshots/

红线（写死在代码里，任何命令都会拒绝触碰）：
  C:\\ 全盘 · G:\\ 全盘 · F:\\temp · D:\\ChatRecords · D:\\backup
  E:\\Obsidian · 任何 .env/_key/cookies/.pem/all_keys.json/dec_MSG*
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"D:\Coding\Organization")
PLANS_DIR = ROOT / "plans"
REPORTS_DIR = ROOT / "reports"
AUDIT_DIR = ROOT / "audit" / "operations"
SNAPSHOTS_DIR = ROOT / "snapshots"
TOOLS_DIR = ROOT / "tools"

# ============================================================
# 规则层：红线 / 敏感文件 / 重目录 / PC-Plan 映射
# ============================================================

# 写动作绝对禁区（前缀匹配）
RED_LINE_PREFIXES = [
    "C:\\", "G:\\", "F:\\temp",
    "D:\\ChatRecords", "D:\\backup",
    "E:\\Obsidian",
]

# 敏感文件（永不读内容，只记路径+大小+短哈希）
DENY_PATTERNS = [
    r"\.env(\.|$)", r"_key\.txt$", r"_secret", r"cookies\.txt$",
    r"\.pem$", r"\.key$", r"id_rsa", r"all_keys\.json$",
    r"\.wxdump", r"dec_MSG", r"passwords\.txt$",
]

# 扫描时排除的重目录（IO 护栏——2026-09-13 卡机教训）
HEAVY_DIRS = {
    "node_modules", ".git", "__pycache__", ".pnpm-store", ".cache",
    "venv", ".venv", "env",
    "seed-vc", "RVC-WebUI", "ViiTorVoice",          # 模型权重（GB级）
    "Program Files", "Program Files (x86)", "ProgramData",
    "$RECYCLE.BIN", "System Volume Information", "Config.Msi",
    "Antigravity_backup_20260905_082321",
    "Antigravity_backup_20260905_082321_IDE",
    "Ubuntu", "temp", "tmp", "adobeTemp",
}

# PC-Plan 归位映射（源前缀 → 目标；decision 记录拍板状态）
PC_PLAN_MAP = [
    {
        "src": r"D:\Coding\Music",
        "dst": r"F:\Date\Music\Tools",
        "why": "配音产线工作区，非代码（2026-09-13 已迁移完成，启动脚本已改路径）",
        "decision": "done",
    },
    {
        "src": r"D:\Coding\ViiTorVoice",
        "dst": r"F:\Date\Music\Tools\ViiTorVoice",
        "why": "配音产线工具+权重 27.9GB，死库（上游已搬家）。2026-09-13 已迁移",
        "decision": "done",
    },
    {
        "src": r"D:\TkPath\TKSucai",
        "dst": None,
        "why": "特效素材原地保留（2026-09-13 你拍板：不动）",
        "decision": "keep",
    },
    {
        "src": r"D:\Coding\telegram_media_downloader",
        "dst": r"F:\Date\Wechat\File",
        "why": "6GB 下载媒体——2026-09-13 复查源已不存在（此前已自行处理），销项",
        "decision": "done",
    },
    {
        "src": r"E:\Screenshots + E:\IMG_*.PNG",
        "dst": r"E:\Obsidian\pic\inbox_20260913 + F:\Date\Photo\杂项",
        "why": "9 张已按内容分拣：8 张视频号AI情报→知识库inbox（带主题改名），1 张排查存档→杂项（2026-09-13 done）",
        "decision": "done",
    },
]


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def today():
    return time.strftime("%Y-%m-%d")


def is_red_line(path: str) -> bool:
    p = path.rstrip("\\/") + "\\"
    for pref in RED_LINE_PREFIXES:
        if p.lower().startswith(pref.lower().rstrip("\\") + "\\") or path.lower() == pref.lower().rstrip("\\"):
            return True
    return False


def is_sensitive(path: str) -> bool:
    return any(re.search(pat, path, re.IGNORECASE) for pat in DENY_PATTERNS)


def short_hash(path: Path, nbytes=1024) -> str:
    """只读前 1KB 算哈希——敏感文件也只到此为止，绝不读全文。"""
    try:
        import hashlib
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read(nbytes))
        return h.hexdigest()[:16]
    except OSError:
        return "ERR"


def fmt_size(n):
    x = float(n)
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if x < 1024:
            return f"{x:.1f}{u}"
        x /= 1024
    return f"{x:.1f}PB"


def log_op(action, detail):
    """不可变操作日志（SECURITY.md §1）。"""
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    rec = {"action": action, "ts": now_iso(), "actor": "org.py", **detail}
    fp = AUDIT_DIR / f"{today()}_{action}.json"
    lines = []
    if fp.exists():
        lines = json.loads(fp.read_text(encoding="utf-8"))
    lines.append(rec)
    fp.write_text(json.dumps(lines, ensure_ascii=False, indent=2), encoding="utf-8")
    return fp


# ============================================================
# 带资源护栏的目录遍历
# ============================================================

def guarded_walk(root, max_depth=2, seconds=30, exclude_heavy=True):
    """yield (path, depth)。超时/超深即停——绝不拖垮 IO。"""
    root = str(root)
    deadline = time.time() + seconds
    stack = [(root, 0)]
    while stack:
        cur, depth = stack.pop()
        if depth > max_depth or time.time() > deadline:
            continue
        try:
            entries = list(os.scandir(cur))
        except OSError:
            continue
        for e in entries:
            yield e.path, depth
            if e.is_dir(follow_symlinks=False):
                if exclude_heavy and e.name in HEAVY_DIRS:
                    continue
                stack.append((e.path, depth + 1))


# ============================================================
# 命令：status —— 体检
# ============================================================

def cmd_status(args):
    t0 = time.time()
    print("=" * 62)
    print("org.py 体检 · 只读 · 预算 60 秒")
    print("=" * 62)

    # 1) PC-Plan 映射状态
    print("\n[1] PC-Plan 归位映射")
    for m in PC_PLAN_MAP:
        src_exists = Path(m["src"]).exists() or "*" in m["src"]
        mark = {"approved-pending-move": "🟡待迁", "needs-review": "⏳待审",
                "done": "✅完成", "keep": "⏸不动"}.get(m["decision"], "·")
        print(f"  {mark}  {m['src']}  →  {m['dst'] or '(按内容分拣)'}")
        if not src_exists:
            print(f"        (源不存在，可能已处理)")

    # 2) git 未提交仓库（只数数量，不展开）
    print("\n[2] D:\\Coding git 仓库健康（每个限时 3 秒）")
    coding = Path(r"D:\Coding")
    dirty, checked = [], 0
    if coding.exists():
        for child in sorted(coding.iterdir()):
            if time.time() - t0 > 45:
                print("  (时间预算用尽，剩余仓库下次再查)")
                break
            git_dir = child / ".git"
            if child.is_dir() and git_dir.exists():
                checked += 1
                try:
                    r = subprocess.run(
                        ["git", "-C", str(child), "status", "--porcelain"],
                        capture_output=True, text=True, timeout=3)
                    n = len([l for l in r.stdout.splitlines() if l.strip()])
                    if n > 0:
                        dirty.append((child.name, n))
                except subprocess.TimeoutExpired:
                    dirty.append((child.name, "?"))

    print(f"  检查了 {checked} 个 git 仓库")
    if dirty:
        for name, n in dirty:
            print(f"  🔴 {name}: {n} 个未提交变更")
    else:
        print("  ✅ 全部干净")

    # 3) Coding 顶层敏感文件（只记元数据）
    print("\n[3] 已知敏感文件复核（不读内容）")
    known = [
        r"D:\Coding\Map\google_maps_api_key.txt",
        r"D:\Coding\ai-creativity\vps_ssh_key.pem",
        r"D:\Coding\hermes_gui\cookies.txt",
        r"D:\Coding\PPSAI\.env",
        r"D:\Coding\Quantitative\.env",
        r"D:\Coding\Contract\.env",
        r"D:\Coding\Learning\.env",
    ]
    for kp in known:
        p = Path(kp)
        if p.exists():
            print(f"  🔴 仍在明文: {kp}  ({p.stat().st_size}B)")

    # 4) 磁盘余量
    print("\n[4] 磁盘余量")
    for drive in ["C:\\", "D:\\", "E:\\", "F:\\"]:
        if os.path.exists(drive):
            try:
                free = subprocess.run(
                    ["powershell", "-NoProfile", "-Command",
                     f"(Get-PSDrive {drive[0]}).Free"],
                    capture_output=True, text=True, timeout=5).stdout.strip()
                if free:
                    print(f"  {drive}  剩余 {fmt_size(int(free))}")
            except Exception:
                pass

    dt = time.time() - t0
    print(f"\n耗时 {dt:.1f}s（预算 60s）")
    log_op("status", {"duration_sec": round(dt, 1)})


# ============================================================
# 命令：scan / big
# ============================================================

def cmd_scan(args):
    root = args.path
    if is_red_line(root) and not args.readonly_ok:
        print(f"⛔ {root} 在红线清单，默认不扫。确认只读查看请加 --readonly-ok")
        return 1
    print(f"扫描 {root}  深度≤{args.depth}  预算 {args.seconds}s（只读）")
    n = 0
    for path, depth in guarded_walk(root, args.depth, args.seconds):
        p = Path(path)
        try:
            st = p.stat()
        except OSError:
            continue
        sens = " 🔒S" if is_sensitive(path) else ""
        print(f"  {'  '*depth}{p.name}{'/' if p.is_dir() else ''}  "
              f"{'' if p.is_dir() else fmt_size(st.st_size)}{sens}")
        n += 1
    print(f"\n共 {n} 项")
    log_op("scan", {"path": root, "items": n, "depth": args.depth})
    return 0


def cmd_big(args):
    root = args.path
    thr = args.mb * 1024 * 1024
    print(f"找 {root} 内 >{args.mb}MB（深度≤3，预算 45s，跳过重目录）")
    found = []
    for path, depth in guarded_walk(root, max_depth=3, seconds=45):
        if is_sensitive(path):
            continue
        p = Path(path)
        try:
            if p.is_file() and p.stat().st_size > thr:
                found.append((p.stat().st_size, path))
        except OSError:
            continue
    found.sort(reverse=True)
    for sz, path in found[: args.top]:
        print(f"  {fmt_size(sz):>10}  {path}")
    print(f"\n共 {len(found)} 个（显示前 {min(len(found), args.top)}）")
    out = REPORTS_DIR / f"{today()}_big_{args.mb}mb.txt"
    out.write_text("\n".join(f"{sz}\t{p}" for sz, p in found), encoding="utf-8")
    print(f"已存: {out}")
    log_op("big", {"path": root, "count": len(found), "report": str(out)})
    return 0


# ============================================================
# 命令：dup —— czkawka 封装（带护栏）
# ============================================================

def cmd_dup(args):
    root = args.path
    if is_red_line(root):
        print(f"⛔ {root} 在红线清单，不扫。")
        return 1
    czk = TOOLS_DIR / "czkawka_cli.exe"
    if not czk.exists():
        print("czkawka_cli.exe 不在 tools/，先安装（见 tools/README.md）")
        return 1
    out = REPORTS_DIR / f"{today()}_dups_{Path(root).name}.txt"
    exclude_args = []
    for heavy in ["seed-vc", "RVC-WebUI", "ViiTorVoice", "node_modules"]:
        exclude_args += ["-e", str(Path(root) / heavy)]
    cmd = [str(czk), "dup", "-d", root, *exclude_args,
           "-m", "1", "-s", "hash", "-f", str(out)]
    print(f"czkawka 重复扫描: {root}")
    print(f"排除: seed-vc / RVC-WebUI / ViiTorVoice / node_modules")
    print(f"限时 {args.seconds}s，结果 → {out}")
    try:
        subprocess.run(cmd, timeout=args.seconds, check=False)
        print(f"✅ 完成（或到时自动停），报告: {out}")
        log_op("dup", {"path": root, "seconds": args.seconds, "report": str(out)})
        return 0
    except subprocess.TimeoutExpired:
        print(f"⏱ 到时已停（部分结果在缓存，重跑会更快）")
        log_op("dup", {"path": root, "seconds": args.seconds, "timeout": True})
        return 0


# ============================================================
# 命令：map —— PC-Plan 映射表
# ============================================================

def cmd_map(args):
    print("PC-Plan 归位映射（E:\\Hrycg\\PC-Plan.png 的落地状态）\n")
    print(f"{'源':<42} {'目标':<26} 状态")
    print("-" * 100)
    for m in PC_PLAN_MAP:
        status = {"approved-pending-move": "🟡 已拍板待执行",
                  "needs-review": "⏳ 需先看内容",
                  "done": "✅ 已完成",
                  "keep": "⏸ 不动"}.get(m["decision"], m["decision"])
        print(f"{m['src']:<42} {str(m['dst'] or '(按内容分拣)'):<26} {status}")
        print(f"{'':<2}↳ {m['why']}")
    print("\n红线区（永不移动）: " + " · ".join(RED_LINE_PREFIXES))


# ============================================================
# 命令：plan-move / apply / undo —— 受控移动三件套
# ============================================================

def build_manifest(src, dst, excludes=None):
    import fnmatch
    src, dst = Path(src), Path(dst)
    if is_red_line(str(src)):
        raise SystemExit(f"⛔ 源 {src} 在红线区，拒绝。")
    if is_red_line(str(dst)):
        raise SystemExit(f"⛔ 目标 {dst} 在红线区，拒绝。")
    excludes = excludes or []
    files, excluded, total = [], [], 0
    # 移动计划必须统计全量（含权重目录）——只读元数据不伤 IO，
    # HEAVY_DIRS 排除仅用于 dup/hash 类内容扫描。
    for path, _ in guarded_walk(src, max_depth=8, seconds=60, exclude_heavy=False):
        p = Path(path)
        try:
            is_f = p.is_file()
        except OSError:
            continue  # 坏符号链接等不可 stat 项，跳过
        if is_f:
            try:
                sz = p.stat().st_size
            except OSError:
                continue
            rel = str(p.relative_to(src))
            if is_sensitive(str(p)):
                # 敏感文件不参与主干移动，摘入 _preserved 保护区（apply 时执行）
                excluded.append({"rel": rel, "size": sz, "reason": "sensitive"})
                continue
            if any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(p.name, pat) for pat in excludes):
                excluded.append({"rel": rel, "size": sz, "reason": "user"})
                continue
            files.append({"rel": rel, "size": sz})
            total += sz
    return {
        "created": now_iso(), "src": str(src), "dst": str(dst),
        "file_count": len(files), "total_bytes": total,
        "files": files, "excluded": excluded, "excludes": excludes,
        "status": "planned",
    }


def cmd_plan_move(args):
    mf = build_manifest(args.src, args.dst, args.exclude)
    PLANS_DIR.mkdir(exist_ok=True)
    name = f"{time.strftime('%Y%m%d_%H%M%S')}_move_{Path(args.src).name}.json"
    fp = PLANS_DIR / name
    fp.write_text(json.dumps(mf, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📋 计划已生成（未执行）: {fp}")
    print(f"   主干 {mf['file_count']} 个文件 / {fmt_size(mf['total_bytes'])}")
    if mf["excluded"]:
        print(f"   🔒 摘入 _preserved 保护区 {len(mf['excluded'])} 个:")
        for ex in mf["excluded"]:
            print(f"      [{ex['reason']}] {ex['rel']}  ({fmt_size(ex['size'])})")
    print(f"   {mf['src']}  →  {mf['dst']}")
    print(f"   执行: python org.py apply {name} --yes")
    log_op("plan-move", {"plan": str(fp), "src": str(mf['src']),
                         "files": mf['file_count'], "excluded": len(mf['excluded'])})


def cmd_apply(args):
    import shutil
    fp = PLANS_DIR / args.plan
    if not fp.exists():
        fp = Path(args.plan)
    mf = json.loads(fp.read_text(encoding="utf-8"))
    if mf.get("status") == "done":
        print("该计划已执行过。要撤销用 undo。")
        return 1
    if not args.yes:
        print(f"⚠ 计划将移动 {mf['file_count']} 个文件 / {fmt_size(mf['total_bytes'])}"
              + (f"（另摘 {len(mf.get('excluded', []))} 个进 _preserved）" if mf.get("excluded") else ""))
        print(f"  {mf['src']} → {mf['dst']}")
        print("确认无误后加 --yes 执行。")
        return 1

    src, dst = Path(mf["src"]), Path(mf["dst"])
    excluded = mf.get("excluded", [])

    # 0) 敏感/排除文件 → 目标 _preserved/ 保护区（保持相对路径）
    if excluded:
        print(f"[0/3] 摘 {len(excluded)} 个文件进 _preserved 保护区…")
        for ex in excluded:
            s, d = src / ex["rel"], dst / "_preserved" / ex["rel"]
            if s.exists():
                d.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(s, d)

    # 1) robocopy 主干复制（/XF 跳过被摘除的文件名）
    print("[1/3] robocopy 复制中…")
    xf = sorted({Path(ex["rel"]).name for ex in excluded})
    cmd = ["robocopy", str(src), str(dst), "/E", "/MT:8", "/R:1", "/W:1",
           "/NFL", "/NDL", "/NP"] + (["/XF", *xf] if xf else [])
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="gbk", errors="replace")
    if r.returncode >= 8:
        print(f"❌ robocopy 失败 code={r.returncode}，源未动，目标可删。")
        log_op("apply-fail", {"plan": str(fp), "code": r.returncode})
        return 1
    # 2) 校验主干文件数（不含 _preserved）
    print("[2/3] 校验文件数…")
    n_dst = 0
    for p in dst.rglob("*"):
        try:
            if p.is_file() and "_preserved" not in p.relative_to(dst).parts:
                n_dst += 1
        except OSError:
            continue  # 坏符号链接等不可访问项不计
    if n_dst < mf["file_count"]:
        print(f"❌ 目标主干 {n_dst} < 计划 {mf['file_count']}，源未动。排查后重试。")
        return 1
    # 3) 删源（保护区文件已在目标安全落位；git 只读对象先解锁再删）
    print("[3/3] 删除源…")
    import shutil
    import stat as _stat

    def _rm_readonly(func, path, _exc):
        os.chmod(path, _stat.S_IWRITE)
        func(path)

    shutil.rmtree(src, onexc=_rm_readonly)
    mf["status"] = "done"
    mf["applied_at"] = now_iso()
    fp.write_text(json.dumps(mf, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"✅ 完成。回滚: python org.py undo {fp.name}")
    log_op("apply", {"plan": str(fp), "files": mf["file_count"],
                     "bytes": mf["total_bytes"], "preserved": len(excluded)})
    return 0


def cmd_undo(args):
    import shutil
    fp = PLANS_DIR / args.plan
    if not fp.exists():
        fp = Path(args.plan)
    mf = json.loads(fp.read_text(encoding="utf-8"))
    if mf.get("status") != "done":
        print("该计划未执行或已回滚，无需 undo。")
        return 1
    if is_red_line(mf["src"]):
        print("⛔ 源变成红线区了，人工处理。")
        return 1
    src, dst = Path(mf["src"]), Path(mf["dst"])
    print(f"反向移动 {dst} → {src}")
    # 1) 主干回移（跳过 _preserved）
    r = subprocess.run(["robocopy", str(dst), str(src), "/E", "/MT:8", "/R:1", "/W:1",
                        "/NFL", "/NDL", "/NP", "/XD", "_preserved"],
                       capture_output=True, text=True,
                       encoding="gbk", errors="replace")
    if r.returncode >= 8:
        print(f"❌ 回滚复制失败 code={r.returncode}")
        return 1
    # 2) 保护区文件放回原位
    for ex in mf.get("excluded", []):
        s, d = dst / "_preserved" / ex["rel"], src / ex["rel"]
        if s.exists():
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(s), str(d))
    # 3) 删目标
    shutil.rmtree(dst)
    mf["status"] = "undone"
    mf["undone_at"] = now_iso()
    fp.write_text(json.dumps(mf, ensure_ascii=False, indent=2), encoding="utf-8")
    print("✅ 已回滚到移动前状态。")
    log_op("undo", {"plan": str(fp)})
    return 0


# ============================================================
# 命令：snapshot
# ============================================================

def cmd_snapshot(args):
    src = Path(args.path)
    if is_red_line(str(src)) and not args.allow_redline:
        print("⛔ 红线区默认不快照（避免触碰）。确认请加 --allow-redline")
        return 1
    name = f"{time.strftime('%Y%m%d_%H%M')}_{src.name or 'root'}"
    dst = SNAPSHOTS_DIR / name
    print(f"镜像 {src} → {dst}")
    r = subprocess.run(["robocopy", str(src), str(dst), "/E", "/MT:8",
                        "/R:1", "/W:1", "/NFL", "/NDL", "/NP"],
                       capture_output=True, text=True)
    code = r.returncode
    print("✅ 快照完成" if code < 8 else f"❌ 失败 code={code}")
    log_op("snapshot", {"src": str(src), "dst": str(dst), "code": code})
    return 0 if code < 8 else 1


# ============================================================
# 命令：sort / sort-undo —— 逐文件按内容分拣
# ============================================================

def cmd_sort(args):
    """执行逐文件分拣计划：{"moves":[{"src","dst","why"}]}
    跨盘 copy2+校验+删源，同盘直接 rename。全程留 manifest 可回滚。"""
    import shutil
    fp = Path(args.plan)
    mf = json.loads(fp.read_text(encoding="utf-8"))
    if mf.get("status") == "done":
        print("该分拣计划已执行过。")
        return 1
    if not args.yes:
        for m in mf["moves"]:
            print(f"  {m['src']}")
            print(f"    → {m['dst']}   # {m.get('why','')}")
        print(f"共 {len(mf['moves'])} 项。加 --yes 执行。")
        return 1
    done = []
    for m in mf["moves"]:
        src, dst = Path(m["src"]), Path(m["dst"])
        if not src.exists():
            print(f"⚠ 跳过（源不在）: {src}")
            continue
        if dst.exists():
            print(f"⚠ 跳过（目标已存在）: {dst}")
            continue
        if is_red_line(str(src)):
            print(f"⛔ 源在红线区，终止: {src}")
            break
        dst.parent.mkdir(parents=True, exist_ok=True)
        same_vol = os.path.splitdrive(str(src))[0] == os.path.splitdrive(str(dst))[0]
        if same_vol:
            os.rename(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
            if src.stat().st_size != dst.stat().st_size:
                print(f"⛔ 校验失败，保留源: {src}")
                continue
            os.unlink(str(src))
        done.append({"src": str(src), "dst": str(dst)})
        print(f"✅ {src.name}  →  {dst.parent}")
    mf["status"] = "done"
    mf["executed_at"] = now_iso()
    mf["executed"] = done
    fp.write_text(json.dumps(mf, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n完成 {len(done)}/{len(mf['moves'])}。回滚: python org.py sort-undo {fp.name}")
    log_op("sort", {"plan": str(fp), "moved": len(done)})
    return 0


def cmd_sort_undo(args):
    import shutil
    fp = Path(args.plan)
    mf = json.loads(fp.read_text(encoding="utf-8"))
    if mf.get("status") != "done":
        print("该计划未执行，无需回滚。")
        return 1
    for m in reversed(mf.get("executed", [])):
        src, dst = Path(m["dst"]), Path(m["src"])
        if dst.exists() and not src.exists():
            same_vol = os.path.splitdrive(str(src))[0] == os.path.splitdrive(str(dst))[0]
            if same_vol:
                os.rename(str(dst), str(src))
            else:
                shutil.copy2(str(dst), str(src))
                os.unlink(str(dst))
            print(f"↩ {dst}  →  {src}")
    mf["status"] = "undone"
    fp.write_text(json.dumps(mf, ensure_ascii=False, indent=2), encoding="utf-8")
    print("分拣已回滚。")
    log_op("sort-undo", {"plan": str(fp)})
    return 0


# ============================================================
# 入口
# ============================================================

def main():
    ap = argparse.ArgumentParser(prog="org.py", description="Hwalme 硬盘整理系统")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="体检：映射状态+git健康+敏感文件+磁盘").set_defaults(func=cmd_status)

    p = sub.add_parser("scan", help="只读结构扫描")
    p.add_argument("path"); p.add_argument("--depth", type=int, default=2)
    p.add_argument("--seconds", type=int, default=30)
    p.add_argument("--readonly-ok", action="store_true")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("big", help="大文件清单")
    p.add_argument("path"); p.add_argument("--mb", type=int, default=100)
    p.add_argument("--top", type=int, default=30)
    p.set_defaults(func=cmd_big)

    p = sub.add_parser("dup", help="重复文件（czkawka 封装）")
    p.add_argument("path"); p.add_argument("--seconds", type=int, default=120)
    p.set_defaults(func=cmd_dup)

    sub.add_parser("map", help="PC-Plan 归位映射表").set_defaults(func=cmd_map)

    p = sub.add_parser("plan-move", help="生成移动计划（不执行）")
    p.add_argument("src"); p.add_argument("dst")
    p.add_argument("--exclude", action="append", default=[],
                   help="排除文件通配符，可多次，如 --exclude *.log")
    p.set_defaults(func=cmd_plan_move)

    p = sub.add_parser("apply", help="执行移动计划（三步走）")
    p.add_argument("plan"); p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_apply)

    p = sub.add_parser("undo", help="回滚已执行的移动")
    p.add_argument("plan")
    p.set_defaults(func=cmd_undo)

    p = sub.add_parser("snapshot", help="快照到 snapshots/")
    p.add_argument("path"); p.add_argument("--allow-redline", action="store_true")
    p.set_defaults(func=cmd_snapshot)

    p = sub.add_parser("sort", help="执行逐文件分拣计划")
    p.add_argument("plan"); p.add_argument("--yes", action="store_true")
    p.set_defaults(func=cmd_sort)

    p = sub.add_parser("sort-undo", help="回滚分拣")
    p.add_argument("plan")
    p.set_defaults(func=cmd_sort_undo)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
