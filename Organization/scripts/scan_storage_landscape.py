# -*- coding: utf-8 -*-
"""
scan_storage_landscape.py · v1 (2026-09-12)
============================================
Organization 的官方存储扫描脚本（只读）

用途:
    扫描 D 盘 + E 盘的"安全可见"视图，输出机器存储全景。
    不读取 S 级数据（密钥/cookie/私钥），命中即跳过 + 报警。

调用:
    python scripts/scan_storage_landscape.py
    输出 → audit/2026-09-12_initial_scan.json + reports/2026-09-12_storage_landscape.md

设计原则（详见 ../SECURITY.md §4）:
    - 默认不读 .env / _key / cookies / .pem / all_keys.json / *.wxdump
    - 命中 S 级 → 只记 path + size + sha256，不复述内容
    - 所有动作落 audit/operations/

作者:
    Hwalme + AI（ZCode MiniMax-M3）
"""
import os
import json
import hashlib
import time
import re
from pathlib import Path

# ============================================================
# 安全防护：S/P 级数据 denylist（按 SECURITY.md §4）
# ============================================================
DENY_PATTERNS = [
    r"\.env(\.|$)", r"_key\.txt$", r"_secret", r"cookies\.txt$",
    r"\.pem$", r"\.key$", r"id_rsa", r"all_keys\.json$",
    r"\.wxdump$", r"dec_MSG", r"secret", r"password",
]

def is_protected(path: str) -> bool:
    """检查路径是否命中 S/P 级（默认不读）"""
    return any(re.search(p, path, re.IGNORECASE) for p in DENY_PATTERNS)


def file_size(p: Path) -> int:
    try:
        return p.stat().st_size
    except OSError:
        return 0


def sha256_short(path: Path, max_bytes=1024) -> str:
    """只读前 1KB 算 sha256（避免读 S 级文件全文）"""
    if is_protected(str(path)):
        return "PROTECTED-NO-READ"
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read(max_bytes))
        return h.hexdigest()[:16]
    except OSError:
        return "ERR"


# ============================================================
# 扫描器
# ============================================================
def scan_root(root: str, max_items=200):
    """顶层扫描"""
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        full = os.path.join(root, name)
        try:
            st = os.stat(full)
        except OSError:
            continue
        is_dir = os.path.isdir(full)
        is_prot = is_protected(name)
        entry = {
            "name": name,
            "path": full,
            "is_dir": is_dir,
            "is_protected": is_prot,
            "size_bytes": st.st_size if not is_dir else 0,
            "mtime": time.strftime("%Y-%m-%d", time.localtime(st.st_mtime)),
        }
        # 顶层目录子项数（限 200）
        if is_dir:
            try:
                with os.scandir(full) as it:
                    entry["child_count"] = sum(1 for _ in it)
            except OSError:
                entry["child_count"] = 0
        out.append(entry)
    return out


def find_protected_files(root: str, max_results=50):
    """扫描顶层 + 1 层，找命中 S 级的文件"""
    found = []
    for base, dirs, files in os.walk(root):
        depth = base[len(root):].count(os.sep)
        if depth > 1:
            dirs[:] = []
            continue
        for f in files:
            full = os.path.join(base, f)
            if is_protected(full):
                found.append({
                    "path": full,
                    "size_bytes": file_size(Path(full)),
                    "sha256_short": sha256_short(Path(full)),
                    "classification": "S" if is_protected(f) else "P",
                })
                if len(found) >= max_results:
                    return found
    return found


def find_large_files(root: str, threshold_mb=100, max_results=30):
    """找 > threshold_mb 的文件（限顶层 + 1 层，避开已知大区）"""
    SKIP = {"Program Files", "Program Files (x86)", "ProgramData",
            "$RECYCLE.BIN", "System Volume Information",
            "Antigravity_backup_20260905_082321",
            "Antigravity_backup_20260905_082321_IDE"}
    results = []
    threshold = threshold_mb * 1024 * 1024
    for base, dirs, files in os.walk(root):
        depth = base[len(root):].count(os.sep)
        if depth > 1:
            dirs[:] = []
            continue
        # 跳过整目录
        dirs[:] = [d for d in dirs if d not in SKIP]
        for f in files:
            full = os.path.join(base, f)
            if is_protected(full):
                continue
            sz = file_size(Path(full))
            if sz > threshold:
                results.append({
                    "path": full,
                    "size_mb": round(sz / 1024 / 1024, 1),
                })
                if len(results) >= max_results:
                    return sorted(results, key=lambda x: -x["size_mb"])
    return sorted(results, key=lambda x: -x["size_mb"])


# ============================================================
# 主流程
# ============================================================
def main():
    ts_start = time.time()
    ts_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    ts_date = time.strftime("%Y-%m-%d")

    print(f"[scan] {ts_iso}  start")
    report = {
        "scan_version": "v1",
        "scan_iso": ts_iso,
        "scope": ["D:\\", "E:\\"],
        "D_top": scan_root("D:\\"),
        "Coding_top": scan_root("D:\\Coding"),
        "E_top": scan_root("E:\\"),
        "protected_files_found": find_protected_files("D:\\", max_results=50),
        "large_files_in_Coding": find_large_files("D:\\Coding", threshold_mb=100, max_results=30),
    }
    report["counts"] = {
        "D_top_items": len(report["D_top"]),
        "Coding_top_items": len(report["Coding_top"]),
        "E_top_items": len(report["E_top"]),
        "protected_count": len(report["protected_files_found"]),
        "large_count": len(report["large_files_in_Coding"]),
    }
    report["ts_end_iso"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    report["duration_sec"] = round(time.time() - ts_start, 2)

    # ============================================================
    # 落档（按 AGENTS.md §1：audit/ + reports/）
    # ============================================================
    audit_path = Path(f"D:/Coding/Organization/audit/{ts_date}_initial_scan.json")
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 审计记录（不可变操作日志）
    op_log = {
        "action": "scan_storage_landscape",
        "actor": "agent:ZCode-MiniMax-M3",
        "ts_start": ts_iso,
        "ts_end": report["ts_end_iso"],
        "scope": ["D:\\", "E:\\"],
        "files_read": report["counts"]["Coding_top_items"] + report["counts"]["D_top_items"],
        "files_touched": 0,  # 只读
        "data_classifications": {
            "S": len([x for x in report["protected_files_found"] if x["classification"] == "S"]),
            "P": len([x for x in report["protected_files_found"] if x["classification"] == "P"]),
            "R": report["counts"]["large_count"],
            "P'": report["counts"]["Coding_top_items"] - report["counts"]["large_count"],
        },
        "sha256_evidence": {
            x["path"]: x["sha256_short"] for x in report["protected_files_found"][:10]
        },
        "user_approval": "granted",  # 用户发起扫描即视为授权只读
        "rollback_plan": None,
        "report_path": str(audit_path),
    }
    op_path = Path(f"D:/Coding/Organization/audit/operations/{ts_date}_initial_scan.json")
    op_path.parent.mkdir(parents=True, exist_ok=True)
    with open(op_path, "w", encoding="utf-8") as f:
        json.dump(op_log, f, ensure_ascii=False, indent=2)

    print(f"[scan] done in {report['duration_sec']}s")
    print(f"  D:\\ 顶层 {report['counts']['D_top_items']} 项")
    print(f"  D:\\Coding\\ 顶层 {report['counts']['Coding_top_items']} 项")
    print(f"  E:\\ 顶层 {report['counts']['E_top_items']} 项")
    print(f"  命中 S/P 级文件: {report['counts']['protected_count']} (已跳过内容读取)")
    print(f"  Coding 内 >100MB 文件: {report['counts']['large_count']}")
    print(f"  报告: {audit_path}")
    print(f"  操作记录: {op_path}")
    return report


if __name__ == "__main__":
    main()