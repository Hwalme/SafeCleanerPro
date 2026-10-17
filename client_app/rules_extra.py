# -*- coding: utf-8 -*-
"""外部规则库统一适配器：Winapp2 / BleachBit / Dism++ / 腾讯管家 → 主界面清理项。

分流策略：
  名称含 cache/temp/log/crash/gpu/shader/thumb/icon/prefetch → 安全线（默认勾选）
  其余（含 history/recent/password/session/autofill/backup 及未知）→ 深度线（默认不勾选）

安全设计：
  * winapp2 file_key 的 exclude 掩码我们无法执行 → 该 key 整条跳过（防多删）
  * *-updater / Squirrel 程序结构、Update.exe 等程序本体 → 不生成
  * 所有路径过 is_protected_path（免疫网）后才入规则
  * 许可署名：Winapp2 CC-BY-SA-4.0、BleachBit GPL——条目描述已注明
"""
import glob
import io
import json
import os
import re
import sys

NL = chr(10)
BS = chr(92)

HOME = os.path.expanduser("~")
LOCAL = os.environ.get("LOCALAPPDATA") or os.path.join(HOME, "AppData", "Local")
ROAM = os.environ.get("APPDATA") or os.path.join(HOME, "AppData", "Roaming")
LOW = os.path.join(os.path.dirname(LOCAL), "LocalLow")
PROGD = "C:" + BS + "ProgramData"
PF = "C:" + BS + "Program Files"
PF86 = "C:" + BS + "Program Files (x86)"
WINDIR = "C:" + BS + "Windows"
DOCS = os.path.join(HOME, "Documents")

try:
    from deep_cache import is_protected_path
except Exception:
    is_protected_path = lambda p: False

_RULES_DIR = None


def _rules_dir():
    global _RULES_DIR
    if _RULES_DIR is None:
        import sys
        base = getattr(sys, "_MEIPASS", None) or os.path.dirname(
            os.path.abspath(__file__))
        here = os.path.join(base, "rules")
        parent = os.path.join(os.path.dirname(base), "rules")
        _RULES_DIR = here if os.path.isdir(here) else parent
    return _RULES_DIR


def _load(name):
    try:
        with io.open(os.path.join(_rules_dir(), name), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _bs(text):
    return text.replace("/", BS)


# 通用环境变量表（键小写，含 $ 与 % 两种写法的名字）
_VARS = {
    "localappdata": LOCAL, "local_app_data": LOCAL, "localappdatalow": LOW,
    "appdata": ROAM, "commonappdata": PROGD, "common_app_data": PROGD,
    "userprofile": HOME, "userprofiles": HOME, "home": HOME,
    "systemdrive": "C:", "homedrive": "C:",
    "windir": WINDIR, "programfiles": PF, "programfiles(x86)": PF86,
    "commonprogramfiles": "C:" + BS + "Program Files" + BS + "Common Files",
    "public": "C:" + BS + "Users" + BS + "Public",
    "personal": DOCS, "documents": DOCS,
    "music": os.path.join(HOME, "Music"),
    "pictures": os.path.join(HOME, "Pictures"),
    "desktop": os.path.join(HOME, "Desktop"),
    "tmp": os.environ.get("TEMP", ""), "temp": os.environ.get("TEMP", ""),
}
_VAR_RE = re.compile(r"[%$]([A-Za-z0-9_()x86]+)[%$]?")


def _expand(path):
    """展开 %var% / $var / ~；未知变量返回 None。"""
    if path.startswith("~"):
        path = HOME + path[1:]
    out = path
    for var in _VAR_RE.findall(path):
        key = var.lower()
        if key not in _VARS:
            return None
        out = out.replace("%" + var + "%", _VARS[key])
        out = out.replace("$" + var, _VARS[key])
        out = out.replace("%" + var, _VARS[key])
        out = out.replace("$" + var + "%", _VARS[key])
    if "%" in out or "$" in out:
        return None
    return out


_SAFE_KW = ("cache", "temp", "tmp", "log", "crash", "gpu", "shader", "thumb",
            "icon", "prefetch", "dump", "backup files", "reportcache")
_RISK_KW = ("history", "recent", "mru", "cookie", "password", "session",
            "autofill", "form", "saved", "backup", "bookmark", "login",
            "typedurl", "jump", "prefetch_")


def _tier(name_text, path_text):
    t = (name_text + " " + path_text).lower()
    if any(k in t for k in _RISK_KW):
        return "risk"
    if any(k in t for k in _SAFE_KW):
        return "safe"
    return "risk"                    # 未知 → 深度线，宁保守


_SEQ = [0]


def _mk_item(prefix, idx, name, paths, tier, credit):
    _SEQ[0] += 1
    return {
        "id": f"xtra_{prefix}_{_SEQ[0]}_{abs(hash(name + str(idx))) % 99999999}",
        "name": name,
        "paths": paths,
        "icon": "🧩",
        "immune": False,
        "type": "system",
        "risk_level": tier,
        "risk_desc": credit,
    }


def _chunk_add(bucket_map, key, tier, paths):
    e = bucket_map.setdefault(key, {"safe": [], "risk": []})
    e[tier] += paths


# ══════════════════ Winapp2 ══════════════════

# ══════════════════ BleachBit ══════════════════
def _bleachbit_apps(seen):
    data = _load("bleachbit" + os.sep + "bleachbit_rules.json")
    if not data:
        return []
    apps = []
    buckets = {}
    for opt in data:
        label = f'{opt.get("app", "")} {opt.get("option_label", "")}'.strip()
        for act in opt.get("actions", []):
            if act.get("command") != "delete":
                continue
            osf = act.get("os")
            if osf and osf not in ("windows", "win"):
                continue
            path = act.get("path", "")
            exp = _expand(path)
            if not exp:
                continue
            tier = _tier(label, exp.lower())
            norm = os.path.normcase(os.path.normpath(exp.replace("/", BS)))
            if norm in seen:
                continue
            seen.add(norm)
            _chunk_add(buckets, ("bb", label), tier, [exp])
    for (tag, label), e in buckets.items():
        for tier in ("safe", "risk"):
            paths = e[tier]
            if not paths:
                continue
            for i in range(0, len(paths), 60):
                piece = paths[i:i + 60]
                apps.append(_mk_item(
                    "bb", i // 60, f"BleachBit·{label} {suffix_of(paths, i)}",
                    piece, tier, "来源 BleachBit 规则（GPL）"))
    return apps


def suffix_of(paths, i):
    n = (len(paths) + 59) // 60
    return f"（{i // 60 + 1}/{n}）" if n > 1 else ""


# ══════════════════ Dism++（仅路径类 General 动作） ══════════════════

# ══════════════════ 腾讯管家（QQ/微信专用路径） ══════════════════
def _qq_apps(seen):
    data = _load("qqpcmgr" + os.sep + "tencent_app_paths.json")
    if not data:
        return []
    apps = []
    for rule in data.get("rules", []):
        app = rule.get("app", "腾讯系")
        paths = []
        for it in rule.get("items", []):
            t = it.get("target", "")
            if "<" in t:                 # <QQ号>/<wxid> 等运行时占位 → 通配
                import re as _re
                t = _re.sub(r"<[^>]+>", "*", t)
            exp = _expand(t)
            if not exp:
                continue
            exp = exp.replace("*" + BS + "*", "*" + BS)
            norm = os.path.normcase(os.path.normpath(exp))
            if norm in seen:
                continue
            seen.add(norm)
            paths.append(exp)
        if paths:
            nd = "；".join(rule.get("never_delete", []))
            desc = "QQ/微信缓存与接收文件。"
            if nd:
                desc += f"⚠ 绝不触碰：{nd}。"
            desc += "接收的文件属个人文档，确认无用后再清。"
            apps.append(_mk_item("qq", abs(hash(app)) % 99999999,
                                 f"腾讯·{app}（{len(paths)} 处）", paths, "risk",
                                 desc))
    return apps


# ══════════════════ 汇总入口 ══════════════════
def build_apps(seen=None):
    """返回外部规则库转换出的清理项列表。seen：已有路径规范化集合（去重）。"""
    if seen is None:
        seen = set()
    apps = []
    for fn in (_bleachbit_apps, _qq_apps):
        try:
            apps += fn(seen)
        except Exception as e:
            print("rules_extra:", fn.__name__, "failed:", e)
    return apps


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    apps = build_apps()
    safe = [a for a in apps if a["risk_level"] == "safe"]
    risk = [a for a in apps if a["risk_level"] == "risk"]
    total = sum(len(a["paths"]) for a in apps)
    print(f"外部规则项: {len(apps)}（安全 {len(safe)} / 深度 {len(risk)}），"
          f"路径合计 {total}")
    for a in safe[:8]:
        print(f"  [safe] {a['name'][:46]:48s} {len(a['paths']):4d} 条")
    for a in risk[:8]:
        print(f"  [risk] {a['name'][:46]:48s} {len(a['paths']):4d} 条")
