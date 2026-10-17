# -*- coding: utf-8 -*-
"""library_rules.py — 外部规则库加载器（Winapp2 + Dism++）

数据源：rules_library.json（由 _recover/rules/parse_rules.py 全量生成）
  * Winapp2.ini 4068 条（CC-BY-SA-4.0, MoscaDotTo/Winapp2 项目）
  * Dism++ Data.xml 73 项（Chuyu-Team Dism-Multi-language）

安全策略（宁可少删，不可误删）：
  1. 含 ExcludeKey 的条目跳过 —— core 协议无法保证排除语义；
  2. 纯注册表条目跳过 —— core 无注册表清理能力；
  3. REMOVESELF 降级为「删除目录内容、保留目录壳」；
  4. RECURSE 降级为根层匹配（宁缺勿滥，后续版本增强）；
  5. Dism++ 的 Custom 特殊操作（DISM API 类）不自动执行；
  6. 所有条目必须本机命中（detect 或 FileKey 根存在）才进入列表；
  7. Winapp2 caution/risky 统一映射 risk_level="risk"，UI 确认后才清理。
"""
import os
from secure_rules import RulePackError, load_dataset

_LIB = None

_ENV_ORDER = [
    ("LocalLowAppData", lambda: os.path.join(os.path.expanduser("~"),
                                             "AppData", "LocalLow")),
    ("LocalAppData", lambda: os.environ.get("LOCALAPPDATA", "")),
    ("AppData", lambda: os.environ.get("APPDATA", "")),
    ("SystemDrive", lambda: os.environ.get("SystemDrive", "C:")),
    ("SystemRoot", lambda: os.environ.get("SystemRoot", r"C:\Windows")),
    ("Windows", lambda: os.environ.get("SystemRoot", r"C:\Windows")),
    ("Windir", lambda: os.environ.get("SystemRoot", r"C:\Windows")),
    ("ProgramFiles", lambda: os.environ.get("ProgramFiles", r"C:\Program Files")),
    ("ProgramW6432", lambda: os.environ.get("ProgramW6432",
                                            os.environ.get("ProgramFiles",
                                                           r"C:\Program Files"))),
    ("ProgramFiles(x86)", lambda: os.environ.get("ProgramFiles(x86)",
                                                 r"C:\Program Files (x86)")),
    ("CommonProgramFiles", lambda: os.path.join(
        os.environ.get("ProgramFiles", r"C:\Program Files"), "Common Files")),
    ("ProgramData", lambda: os.environ.get("ProgramData", r"C:\ProgramData")),
    ("CommonAppData", lambda: os.environ.get("ProgramData", r"C:\ProgramData")),
    ("AllUsersProfile", lambda: os.environ.get("ProgramData", r"C:\ProgramData")),
    ("UserProfile", lambda: os.path.expanduser("~")),
    ("HomePath", lambda: os.path.expanduser("~")),
    ("Documents", lambda: os.path.join(os.path.expanduser("~"), "Documents")),
]


def _expand(path):
    """展开 Winapp2 / Dism++ 的环境变量写法。"""
    out = path
    for name, getter in _ENV_ORDER:
        token = "%" + name + "%"
        if token in out:
            try:
                out = out.replace(token, getter())
            except Exception:
                return ""
    return out


def _root_exists(pathpart):
    """根路径快速存在性探测（支持一层通配符）。"""
    if not pathpart:
        return False
    base = pathpart.rstrip("\\/")
    if not base:
        return False
    try:
        if ("*" in base) or ("?" in base):
            head = base.split("*")[0].split("?")[0].rstrip("\\/")
            if head and not os.path.exists(head):
                return False
            import glob as _g
            return next(_g.iglob(base), None) is not None
        return os.path.isdir(base) or os.path.isfile(base)
    except OSError:
        return False


def _load_lib():
    global _LIB
    if _LIB is not None:
        return _LIB
    _LIB = load_dataset("library")
    return _LIB


def _cat_type(cat):
    """Winapp2 category → UI 分组 type。"""
    m = {"browser": "app", "windows": "system", "windows_adv": "system",
         "windows_comp": "system", "app": "app", "internet": "app",
         "multimedia": "app", "utility": "app", "other": "app"}
    return m.get(cat, "app")


_ICON = {"app": "📱", "system": "🪟", "browser": "🌐"}


def _filekey_paths(fk):
    """Winapp2 FileKey → paths 协议。

    语法 root|mask1;mask2|RECURSE/REMOVESELF
    返回通配符路径列表（core 会 glob 展开 + 目录递归）。
    """
    parts = fk.split("|")
    if not parts or not parts[0].strip():
        return []
    root = _expand(parts[0].strip())
    if not root:
        return []
    masks = [m.strip() for m in (parts[1].split(";") if len(parts) > 1 and parts[1]
                                 else ["*"]) if m.strip()]
    if not masks:
        masks = ["*"]
    flag = parts[2].strip().upper() if len(parts) > 2 else ""
    out = []
    for m in masks:
        if flag == "REMOVESELF":
            # 降级：删除目录内全部内容，保留目录壳（安全）
            out.append(os.path.join(root, "*"))
        else:
            # RECURSE 降级为根层匹配；普通匹配天然等价
            out.append(os.path.join(root, m))
    return out


def _winapp2_apps():
    lib = _load_lib()
    apps = []
    for r in lib.get("winapp2", []):
        fks = r.get("filekeys") or []
        if not fks:
            continue                      # 纯注册表条目跳过
        if r.get("exclude"):
            continue                      # ExcludeKey 语义不可保证，跳过
        det = r.get("detect") or []
        hit = False
        if det:
            hit = any(_root_exists(_expand(d)) for d in det if d)
        if not hit:
            for fk in fks:
                root = _expand(fk.split("|")[0].strip()) if fk else ""
                if _root_exists(root):
                    hit = True
                    break
        if not hit:
            continue                      # 本机不存在，不进列表
        paths = []
        for fk in fks:
            paths.extend(_filekey_paths(fk))
        paths = [p for p in paths if p]
        if not paths:
            continue
        risk = "safe" if r.get("risk") == "safe" else "risk"
        cat = r.get("category_cn", "其他")
        t = _cat_type(r.get("category", "other"))
        title = r.get("title", "") or "未命名条目"
        desc = ("来源 Winapp2 规则库（%s 分类，%d 条路径规则）。"
                % (cat, len(paths)))
        if risk == "risk":
            desc += " 该项可能涉及浏览器历史、会话或个人配置，请确认后再清理。"
        apps.append({
            "id": "w2_" + r["id"][3:] if r["id"].startswith("w2-") else r["id"],
            "name": title,
            "paths": paths,
            "icon": _ICON.get(t, "🧩"),
            "immune": False,
            "type": t,
            "risk_level": risk,
            "risk_desc": desc,
        })
    return apps


def _dismpp_apps():
    lib = _load_lib()
    apps = []
    for r in lib.get("dismpp", []):
        fps = r.get("file_paths") or []
        if not fps:
            continue                      # Custom DISM 操作不自动执行
        paths = []
        for fp in fps:
            root = _expand(fp.get("root", ""))
            q = fp.get("query", "")
            if not root or not q:
                continue
            paths.append(os.path.join(root, q))
        paths = [p for p in paths if p]
        if not paths:
            continue
        hit = any(_root_exists(p) for p in paths)
        if not hit:
            continue
        risk = "safe" if r.get("risk") == "safe" else "risk"
        warn = r.get("warning", "")
        desc = "来源 Dism++ 官方清理规则（%s）。" % r.get("category_cn", "系统清理")
        if warn:
            desc += " 注意：" + warn
        apps.append({
            "id": r["id"].replace("dm-", "dm_"),
            "name": r.get("title", "Dism++ 清理项"),
            "paths": paths,
            "icon": "🪟",
            "immune": False,
            "type": "system",
            "risk_level": risk,
            "risk_desc": desc,
        })
    return apps


def get_library_apps():
    """返回本机命中的外部规则库清理项（协议与 cleaner_rules.RULES 一致）。"""
    result = []
    try:
        result.extend(_winapp2_apps())
    except RulePackError:
        raise
    except Exception:
        pass
    try:
        result.extend(_dismpp_apps())
    except RulePackError:
        raise
    except Exception:
        pass
    return result


def library_info():
    lib = _load_lib()
    return lib.get("sources", {})


if __name__ == "__main__":
    apps = get_library_apps()
    safe = sum(1 for a in apps if a["risk_level"] == "safe")
    print("library apps:", len(apps), "safe:", safe, "risk:", len(apps) - safe)
    for a in apps[:5]:
        print(" -", a["id"], a["name"], "paths:", len(a["paths"]))
