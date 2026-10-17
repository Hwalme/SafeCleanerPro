# -*- coding: utf-8 -*-
"""360 安全卫士痕迹规则 → SafeCleaner 深度扫描项转换器。

输入 rules/trace_rules.json（来自 docs/360清理规则逆向报告.md 的解密交付）：
  每组 = {id, category, app, items: [{type, target, options}]}
转换口径：
  融入  Directory / File 两类（缓存与痕迹文件），展开 %变量%，
  按分类聚合成深度扫描项（默认不勾选，确认后清理）。
  跳过  SQLite / RegValue / RegKey / Ini / XML（引擎不支持注册表与库内清理）；
        Cookie / 密码 / 表单 / 会话相关（违背"登录态与用户数据不碰"原则）；
        %InstallPath% / %SID% 等本机无法解析的变量。
"""
import glob
import os
import re
from secure_rules import load_dataset

NL = chr(10)
BS = chr(92)

try:
    from deep_cache import is_protected_path
except Exception:
    is_protected_path = lambda p: False

CAT_NAME = {
    "1": "IE 上网痕迹", "11": "Firefox 痕迹", "12": "Chrome 痕迹",
    "13": "其他浏览器痕迹", "3": "系统使用痕迹", "41": "Windows 自带程序痕迹",
    "42": "办公软件痕迹", "43": "媒体播放痕迹", "44": "压缩工具痕迹",
    "59": "其他应用痕迹", "8": "Metro 应用痕迹",
}

# 隐私关键目标：即使 360 认为可清，我们也绝不碰
DENY_PAT = re.compile(
    r"cookie|formhistory|password|logins?\.json|key[34]\.db|sitesecurity"
    r"|places\.sqlite|sessionstore|webdata|bookmark", re.I)


def _load_json():
    return load_dataset("trace")


def _firefox_profiles(kind):
    """kind: DataFile1 = roaming 默认 profile；DataFile2/3 = local。"""
    if kind == "DataFile1":
        base = os.path.join(os.path.expanduser("~"), "AppData", "Roaming",
                            "Mozilla", "Firefox", "Profiles")
    else:
        base = os.path.join(os.path.expanduser("~"), "AppData", "Local",
                            "Mozilla", "Firefox", "Profiles")
    return glob.glob(os.path.join(base, "*.default*"))


def expand_target(target):
    """展开 360 路径变量 → (路径列表, 可解析?)。"""
    t = target
    home = os.path.expanduser("~")
    local = os.path.join(home, "AppData", "Local")
    roam = os.path.join(home, "AppData", "Roaming")

    mapping = {
        "LOCAL_APPDATA": local, "Local_AppData": local,
        "APPDATA": roam, "AppData": roam,
        "COMMON_APPDATA": "C:" + BS + "ProgramData",
        "ProgramData": "C:" + BS + "ProgramData",
        "PUBLIC": "C:" + BS + "Users" + BS + "Public",
        "UserProfile": home,
        "PERSONAL": os.path.join(home, "Documents"),
        "RECENT": os.path.join(roam, "Microsoft", "Windows", "Recent"),
        "LOCAL_APPDATA_LOW": os.path.join(os.path.dirname(local), "LocalLow"),
    }
    m = re.search(r"%DataFile([123])%", t)
    if m:
        profiles = _firefox_profiles("DataFile" + m.group(1))
        if not profiles:
            return [], False
        bases = []
        for prof in profiles:
            tt = t
            for v in ("DataFile1", "DataFile2", "DataFile3"):
                if tt.startswith("%" + v + "%"):
                    tt = tt.replace("%" + v + "%", prof)          # 开头 = 完整 profile 路径
                else:
                    tt = tt.replace("%" + v + "%",
                                    os.path.join("Profiles", os.path.basename(prof)))
            bases.append(tt)
    else:
        bases = [t]
    outs = []
    for tt in bases:
        bad = False
        for var in re.findall(r"%([A-Za-z0-9_]+)%", tt):
            if var in ("InstallPath", "SID", "PROFILE"):
                bad = True
                break
            if var in mapping:
                tt = tt.replace("%" + var + "%", mapping[var])
        if not bad:
            outs.append(os.path.normpath(tt))
    return outs, True

    for var in re.findall(r"%([A-Za-z0-9_]+)%", t):
        if var in ("InstallPath", "SID", "PROFILE"):
            return [], False          # 本机无法解析
        if var not in mapping:
            return [], False          # 未知变量，保守跳过
        t = t.replace("%" + var + "%", mapping[var])
    return [os.path.normpath(t)], True


def _denied(target):
    return bool(DENY_PAT.search(target))


def build_trace_apps():
    """按 trace 分类聚合成深度扫描项；单项路径超 60 条时拆分。"""
    data = _load_json()
    if not data:
        return []

    cat_paths = {}
    for g in data:
        cat = str(g.get("category", "59"))
        if cat in ("5", "999"):
            continue
        cname = CAT_NAME.get(cat, "分类" + cat)
        bucket = cat_paths.setdefault(cname, set())
        for it in g.get("items", []):
            if it.get("type", "") not in ("Directory", "File"):
                continue
            target = it.get("target", "")
            if _denied(target):
                continue
            targets, ok = expand_target(target)
            if not ok:
                continue
            for t in targets:
                bucket.add(os.path.normpath(t))

    apps = []
    for cname in sorted(cat_paths, key=lambda x: (len(cat_paths[x]), x),
                        reverse=True):
        paths = sorted(cat_paths[cname])
        if not paths:
            continue
        chunks = [paths[i:i + 60] for i in range(0, len(paths), 60)]
        for idx, piece in enumerate(chunks):
            suffix = f"（{idx + 1}/{len(chunks)}）" if len(chunks) > 1 else ""
            apps.append({
                "id": "t360_" + str(abs(hash(cname + str(idx))) % 99999999),
                "name": f"360 痕迹规则·{cname} {suffix}",
                "paths": piece,
                "icon": "🧭",
                "immune": False,
                "type": "system",
                "risk_level": "risk",       # 深度扫描线：默认不勾选
                "risk_desc": "来自 360 痕迹规则库的使用痕迹路径（默认不勾选），"
                             "包含浏览器缓存与使用记录，确认后再清理。",
            })
    return apps


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    apps = build_trace_apps()
    total = sum(len(a["paths"]) for a in apps)
    print(f"转换出 {len(apps)} 个深度扫描项，覆盖 {total} 条路径")
    for a in apps[:15]:
        print(f"  {a['name']:46s} {len(a['paths']):4d} 条  例: {a['paths'][0][:70]}")
