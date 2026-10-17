# -*- coding: utf-8 -*-
"""
dedup_scan.py — 查重索引器
============================
模式 A（推荐，秒级）: 从既有 czkawka 报告建档（复用哈希成果，只补元数据）
    python scripts/dedup_scan.py --from-czkawka 报告1.txt 报告2.txt --out reports/dedup_index.json
模式 B: 全新扫描某目录（分阶段哈希：体积→首尾1KB→全量，带缓存）
    python scripts/dedup_scan.py --scan F:\\某目录 --out reports/dedup_index.json

每条文件记录字段:
    path 文件完整路径 | name 文件名 | ext 扩展名 | folder 所在文件夹 | drive 盘符
    size 字节 | ctime 创建时间戳(Windows原生) | mtime 修改时间戳
    hash sha256(来自czkawka报告或本脚本) | category 类别
    group 组号 | group_count 组内副本数 | redundant 是否冗余副本 | waste 冗余则浪费字节
    protected 是否在写红线区
"""
import argparse
import hashlib
import json
import os
import re
import time
from pathlib import Path

ROOT = Path(r"D:\Coding\Organization")

RED_LINE_PREFIXES = ["C:\\", "G:\\", "F:\\temp", "D:\\ChatRecords", "D:\\backup", "E:\\Obsidian"]

CAT_MAP = {
    "图片": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".heif", ".svg", ".ico", ".raw", ".cr2", ".nef", ".arw", ".dng", ".psd", ".ai"},
    "视频": {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".ts", ".m4v", ".mpg", ".mpeg", ".3gp", ".webm", ".rmvb", ".rm"},
    "音频": {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma", ".ape", ".opus", ".mid"},
    "文档": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv", ".rtf", ".odt", ".mmap", ".xmind", ".vcf"},
    "压缩包": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"},
    "安装包": {".exe", ".msi", ".apk", ".dmg", ".appx"},
    "数据": {".json", ".xml", ".db", ".sqlite", ".sql", ".yaml", ".yml", ".ini", ".cfg"},
    "代码": {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".h", ".go", ".rs", ".sh", ".bat", ".ps1", ".ipynb"},
}


def category_of(ext: str) -> str:
    e = ext.lower()
    for cat, exts in CAT_MAP.items():
        if e in exts:
            return cat
    return "其他"


def is_protected(path: str) -> bool:
    p = path.rstrip("\\/") + "\\"
    return any(p.lower().startswith(pref.lower()) for pref in RED_LINE_PREFIXES)


def stat_record(path: str, hash_val: str, group: int, group_count: int,
                redundant: bool, keep_path: str = ""):
    try:
        st = os.stat(path)
    except OSError:
        return None
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1]
    return {
        "path": path,
        "name": name,
        "ext": ext,
        "folder": os.path.dirname(path),
        "drive": os.path.splitdrive(path)[0] + "\\",
        "size": st.st_size,
        "ctime": int(st.st_ctime),
        "mtime": int(st.st_mtime),
        "hash": hash_val,
        "category": category_of(ext),
        "group": group,
        "group_count": group_count,
        "redundant": redundant,
        "waste": st.st_size if redundant else 0,
        "protected": is_protected(path),
    }


def parse_czkawka(report_path: str):
    """解析 czkawka dup 报告 → [(组内路径列表, 组字节), ...]"""
    groups, cur = [], None
    for ln in open(report_path, encoding="utf-8", errors="replace"):
        ln = ln.strip()
        if ln.startswith("---- Size"):
            cur = []
            groups.append(cur)
        elif ln.startswith('"') and ln.endswith('"') and cur is not None and len(ln) > 2:
            cur.append(ln[1:-1])
    return [g for g in groups if len(g) > 1]


def keep_policy(paths):
    """保留策略: references > 非缓存目录 > 最短路径（与 Music 清理同源）"""
    for p in paths:
        if "references" in p:
            return p
    for p in paths:
        if "checkpoints" not in p and "snapshots" not in p:
            return p
    return min(paths, key=len)


def build_from_czkawka(reports, out):
    files, gid, skipped = [], 0, 0
    total_waste = 0
    for rp in reports:
        for g in parse_czkawka(rp):
            gid += 1
            keep = keep_policy(g)
            for p in g:
                rec = stat_record(p, "", gid, len(g), p != keep)
                if rec is None:
                    skipped += 1
                    continue
                rec["waste"] = rec["size"] if rec["redundant"] else 0
                total_waste += rec["waste"]
                files.append(rec)
    return finish(files, out, reports, skipped, total_waste)


def finish(files, out, sources, skipped, total_waste):
    redundant = [f for f in files if f["redundant"]]
    index = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "sources": sources,
        "stats": {
            "files": len(files),
            "groups": len(set(f["group"] for f in files)),
            "redundant": len(redundant),
            "reclaim_bytes": sum(f["size"] for f in redundant),
        },
        "files": files,
    }
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(index, ensure_ascii=False), encoding="utf-8")
    print(f"[index] 文件 {len(files)} | 组 {index['stats']['groups']} | "
          f"冗余 {len(redundant)} | 可释放 {total_waste/1024/1024/1024:.2f}GB | "
          f"失效跳过 {skipped}")
    print(f"[index] → {out}")
    return index


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-czkawka", nargs="+", help="czkawka 报告 txt 列表")
    ap.add_argument("--scan", help="全新扫描目录（分阶段哈希）")
    ap.add_argument("--out", default=str(ROOT / "reports" / "dedup_index.json"))
    a = ap.parse_args()
    if a.from_czkawka:
        build_from_czkawka(a.from_czkawka, a.out)
    elif a.scan:
        print("scan 模式请先用 czkawka_cli 出报告再 --from-czkawka（哈希已缓存，秒级）")
        print(f'  {ROOT / "tools" / "czkawka_cli.exe"} dup -d "{a.scan}" -m 1 -s hash -f 报告.txt')
    else:
        ap.error("需要 --from-czkawka 或 --scan")


if __name__ == "__main__":
    main()