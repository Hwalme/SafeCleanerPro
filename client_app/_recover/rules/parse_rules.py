# -*- coding: utf-8 -*-
"""parse_rules.py — 全量解析 Winapp2.ini + Dism++ Data.xml 为统一 JSON 规则库
覆盖 100% 条目（不挑本地命中的），按风险分级，供 cleaner_core 运行时加载。
"""
import json
import os
import re
from xml.etree import ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "rules_library.json")

# ---------- 1) Winapp2.ini 全量解析 ----------
# LangSecRef → 类别/风险映射（CCleaner 标准 section id）
LANGSECREG = {
    "3021": ("应用", "app"),
    "3022": ("互联网", "internet"),
    "3023": ("多媒体", "multimedia"),
    "3024": ("实用工具", "utility"),
    "3025": ("Windows", "windows"),
    "3026": ("Windows 系统日志等", "windows"),
    "3027": ("Windows 高级", "windows_adv"),
    "3028": ("Windows 组件", "windows_comp"),
    "3029": ("浏览器", "browser"),
    "3030": ("Windows Store", "windows"),
    "3031": ("浏览器（新）", "browser"),
}

# 高风险关键词：命中则默认不勾选（保护用户数据）
RISKY_PATTERNS = [
    "password", "bookmark", "preference", "session", "login", "cookie",
    "history", "form data", "autofill", "credential", "saved", "extension",
    "addon", "theme", "setting", "config", "profile", "sync", "backup",
    "license", "activation", "registry", "mrulist", "typed", "recent",
]
SAFE_HINTS = ["cache", "temp", "log", "crash", "dump", "thumb", "report",
              "leftover", "setup", "install", "update cache", "gpu cache",
              "code cache", "shader"]


def classify_winapp2(title, keys):
    """按标题与规则体给风险分级: safe / caution / risky"""
    t = title.lower()
    joined = " ".join(keys).lower()
    score = 0
    for p in RISKY_PATTERNS:
        if p in t:
            score += 2
    for p in RISKY_PATTERNS:
        if p in joined:
            score += 1
    for s in SAFE_HINTS:
        if s in t:
            score -= 3
    # REMOVESELF 删除整棵树，加风险
    if any("REMOVESELF" in k for k in keys):
        score += 2
    if score <= 0:
        return "safe"
    if score <= 2:
        return "caution"
    return "risky"


def parse_winapp2():
    path = os.path.join(HERE, "Winapp2.ini")
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        raw = f.read()
    entries = []
    cur = None
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith(";"):
            continue
        m = re.match(r"^\[(.+)\]$", line)
        if m:
            if cur:
                entries.append(cur)
            cur = {"title": m.group(1), "filekeys": [], "regkeys": [],
                   "detect": [], "exclude": [], "opts": {}}
            continue
        if cur is None:
            continue
        low = line.lower()
        if low.startswith("filekey"):
            cur["filekeys"].append(line.split("=", 1)[1].strip())
        elif low.startswith("regkey"):
            cur["regkeys"].append(line.split("=", 1)[1].strip())
        elif low.startswith(("detectfile", "detect")):
            cur["detect"].append(line.split("=", 1)[1].strip())
        elif low.startswith("excludekey"):
            cur["exclude"].append(line.split("=", 1)[1].strip())
        elif "=" in low:
            k, v = line.split("=", 1)
            cur["opts"][k.strip().lower()] = v.strip()
    if cur:
        entries.append(cur)

    rules = []
    for e in entries:
        fk = [k for k in e["filekeys"]]
        risk = classify_winapp2(e["title"], fk + e["regkeys"])
        # LangSecRef 映射
        cat_cn, cat_en = LANGSECREG.get(
            e["opts"].get("langsecref", ""), ("其他", "other"))
        rules.append({
            "src": "winapp2",
            "id": 'w2-' + re.sub(r"[^a-z0-9]+", "-", e["title"].lower())[:60],
            "title": e["title"].rstrip("*").strip(),
            "category": cat_en,
            "category_cn": cat_cn,
            "risk": risk,
            "detect": e["detect"],
            "filekeys": fk,
            "regkeys": e["regkeys"],
            "exclude": e["exclude"],
            "default": e["opts"].get("default", ""),
        })
    return rules


# ---------- 2) Dism++ Data.xml 全量解析 ----------
def parse_dism():
    path = os.path.join(HERE, "Dismpp.xml")
    tree = ET.parse(path)
    root = tree.getroot()
    cc = root.find("CleanCollection4")
    rules = []
    for item in cc.findall("Item"):
        name = item.get("Name", "").lstrip("#")
        level = int(item.get("Level", "1") or "1")
        desc_el = item.find("Description")
        grp_el = item.find("Group")
        warn_el = item.find("Warning")
        scans = item.findall("Scan")
        # 汇总所有 Scan 里的路径规则
        file_paths = []       # (rootpath, query, recurse)
        custom_ops = []       # DISM 特殊操作（非文件删除）
        for sc in scans:
            act = sc.find("Activate")
            if act is None:
                continue
            gen = act.find("General")
            if gen is not None:
                rp = gen.get("RootPath", "")
                flags = gen.get("Flags", "")
                recurse = "recurse" in (flags or "").lower() or "directory" in (flags or "").lower()
                for q in gen.findall("Query"):
                    if q.text:
                        file_paths.append((rp, q.text.strip(), recurse))
            for cust in act.findall("Custom"):
                custom_ops.append({
                    "proc": cust.get("ProcName", ""),
                    "flags": cust.get("Flags", ""),
                })
        # 风险：Level 1 安全 2 警告 3 专家；有 Custom 的保持 special
        risk = {1: "safe", 2: "caution", 3: "risky"}.get(level, "caution")
        if custom_ops and not file_paths:
            risk = "special"
        rules.append({
            "src": "dismpp",
            "id": 'dm-' + re.sub(r"[^a-z0-9]+", "-", name.lower())[:60],
            "title": name,
            "category": "dismpp",
            "category_cn": (grp_el.text.lstrip("#") if grp_el is not None
                            and grp_el.text else "系统清理"),
            "risk": risk,
            "detect": [],   # FileExist 条件并入 file_paths 扫描阶段处理
            "file_paths": [
                {"root": rp, "query": q, "recurse": rec}
                for (rp, q, rec) in file_paths
            ],
            "custom_ops": custom_ops,
            "desc": desc_el.text.strip("# ") if desc_el is not None and desc_el.text else "",
            "warning": warn_el.text.strip("# ") if warn_el is not None and warn_el.text else "",
            "level": level,
        })
    return rules


def main():
    w2 = parse_winapp2()
    dm = parse_dism()
    lib = {
        "version": 1,
        "sources": {
            "winapp2": {"entries": len(w2),
                        "license": "CC-BY-SA-4.0 (Winapp2 project)"},
            "dismpp": {"entries": len(dm),
                       "license": "Chuyu-Team Dism-Multi-language"},
        },
        "winapp2": w2,
        "dismpp": dm,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(lib, f, ensure_ascii=False, indent=1)
    # 统计
    from collections import Counter
    print("== Winapp2 ==")
    print("total:", len(w2))
    print("risk:", Counter(r["risk"] for r in w2))
    print("cat:", Counter(r["category_cn"] for r in w2).most_common(12))
    print("== Dism++ ==")
    print("total:", len(dm))
    print("risk:", Counter(r["risk"] for r in dm))
    print("file_path rules:", sum(len(r["file_paths"]) for r in dm))
    print("custom ops:", sum(len(r["custom_ops"]) for r in dm))
    print("written:", OUT, os.path.getsize(OUT), "bytes")


if __name__ == "__main__":
    main()
