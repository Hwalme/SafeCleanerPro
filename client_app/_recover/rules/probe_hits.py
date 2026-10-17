# -*- coding: utf-8 -*-
"""probe_hits.py — 探测本机命中的 winapp2/dismpp 规则数与可清理量级"""
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
lib = json.load(open(os.path.join(HERE, "rules_library.json"), encoding="utf-8"))

ENV = {k: os.environ.get(k, "") for k in
       ("LOCALAPPDATA", "APPDATA", "SystemRoot", "SystemDrive", "ProgramFiles",
        "ProgramFiles(x86)", "ProgramData", "USERPROFILE", "WINDIR", "CommonAppData",
        "AllUsersProfile", "LocalLowAppData")}


def expand(p):
    out = p
    # winapp2 环境变量写法
    out = out.replace("%LocalLowAppData%", os.path.join(ENV["USERPROFILE"], "AppData", "LocalLow"))
    out = out.replace("%LocalAppData%", ENV["LOCALAPPDATA"])
    out = out.replace("%AppData%", ENV["APPDATA"])
    out = out.replace("%SystemDrive%", ENV["SystemDrive"].rstrip("\\") if ENV["SystemDrive"] else "C:")
    out = out.replace("%SystemRoot%", ENV["SystemRoot"])
    out = out.replace("%Windir%", ENV["SystemRoot"])
    out = out.replace("%Windows%", ENV["SystemRoot"])
    out = out.replace("%ProgramFiles%", ENV["ProgramFiles"])
    out = out.replace("%ProgramW6432%", ENV["ProgramFiles"])
    out = out.replace("%ProgramFiles(x86)%", ENV["ProgramFiles(x86)"])
    out = out.replace("%CommonProgramFiles%", os.path.join(ENV["ProgramFiles"], "Common Files"))
    out = out.replace("%ProgramData%", ENV["ProgramData"])
    out = out.replace("%CommonAppData%", ENV["ProgramData"])
    out = out.replace("%AllUsersProfile%", ENV["ProgramData"])
    out = out.replace("%UserProfile%", ENV["USERPROFILE"])
    out = out.replace("%HomePath%", ENV["USERPROFILE"])
    out = out.replace("%Documents%", os.path.join(ENV["USERPROFILE"], "Documents"))
    return out


def root_exists(pathpart):
    """根路径支持 * 通配符，任意分支命中即算存在（浅层快速探测）"""
    if not pathpart:
        return False
    base = pathpart.rstrip("\\/")
    if "*" in base or "?" in base:
        try:
            return any(glob.iglob(base + "*") for _ in [0]) and next(glob.iglob(base + "*"), None) is not None
        except OSError:
            return False
    return os.path.isdir(base) or os.path.isfile(base)


def probe():
    hits_safe, hits_risk = [], []
    for r in lib["winapp2"]:
        ok = False
        det = r["detect"]
        if det:
            ok = any(root_exists(expand(d)) for d in det)
        if not ok and r["filekeys"]:
            for fk in r["filekeys"]:
                parts = fk.split("|")
                if not parts or not parts[0]:
                    continue
                if root_exists(expand(parts[0])):
                    ok = True
                    break
        if ok:
            (hits_safe if r["risk"] == "safe" else hits_risk).append(r)
    print("winapp2 detect hits:", len(hits_safe), "safe +", len(hits_risk), "risk =",
          len(hits_safe) + len(hits_risk))
    from collections import Counter
    print("safe by cat:", Counter(h["category_cn"] for h in hits_safe).most_common(10))

    dpaths = 0
    for r in lib["dismpp"]:
        for fp in r["file_paths"]:
            root = expand(fp["root"])
            q = fp["query"]
            full = os.path.join(root, q)
            if next(glob.iglob(full), None) is not None:
                dpaths += 1
    print("dismpp query hits:", dpaths, "/", sum(len(r["file_paths"]) for r in lib["dismpp"]))


if __name__ == "__main__":
    probe()
