# -*- coding: utf-8 -*-
"""一次性运维：把已迁移项改址到 E:\\temp\\Agent（同卷改名/跨卷复制均走安全流水线）。"""
import os
import sys
import shutil
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import migrate_core as mc

AGENT = "E:" + os.sep + "temp" + os.sep + "Agent"
os.makedirs(AGENT, exist_ok=True)

jobs = [
    (os.path.expanduser("~/.gemini"),
     "E:" + os.sep + "temp" + os.sep + "Gemini-Antigravity" + os.sep + ".gemini",
     os.path.join(AGENT, "gemini", "00_.gemini")),
    (os.path.expanduser("~/.claude"),
     "F:" + os.sep + "temp" + os.sep + "Agent" + os.sep + "claude_code" + os.sep + "00_.claude",
     os.path.join(AGENT, "claude_code", "00_.claude")),
    (os.path.expandvars("%APPDATA%" + os.sep + "Claude"),
     "F:" + os.sep + "temp" + os.sep + "Agent" + os.sep + "claude_desktop" + os.sep + "00_Claude",
     os.path.join(AGENT, "claude_desktop", "00_Claude")),
]

print("== 改址到 " + AGENT + " ==")
ok = 0
for src, old, new in jobs:
    label = os.path.basename(src)
    cur = mc.link_target(src)
    if cur and os.path.normcase(cur) == os.path.normcase(new):
        print("  - %s: 已在新位置，跳过" % label)
        ok += 1
        continue
    res = mc.retarget_junction(src, new, log=lambda m: print("    " + m))
    print("  OK %s: [%s] %.1f MB -> %s" % (label, res["mode"],
                                           res["bytes"] / 1048576, new))
    ok += 1
print("%d/3 改址完成" % ok)

# codex 续传缓存搬到新根（F: 上 3 个文件，未来按新根迁移可续传）
old_codex = ("F:" + os.sep + "temp" + os.sep + "Agent" + os.sep
             + "codex" + os.sep + "00_.codex")
new_codex = os.path.join(AGENT, "codex", "00_.codex")
if os.path.isdir(old_codex):
    for cur, dirs, files in os.walk(old_codex):
        rel = os.path.relpath(cur, old_codex)
        for f in files:
            d = os.path.join(new_codex, rel, f)
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(os.path.join(cur, f), d)
    print("  OK codex 续传缓存已复制到新根")

# 清理旧位置（只删空目录，非空保留待人工确认）
time.sleep(0.5)
for p in ("E:" + os.sep + "temp" + os.sep + "Gemini-Antigravity",
          "F:" + os.sep + "temp" + os.sep + "Agent" + os.sep + "claude_code",
          "F:" + os.sep + "temp" + os.sep + "Agent" + os.sep + "claude_desktop",
          "F:" + os.sep + "temp" + os.sep + "Agent" + os.sep + "codex",
          "F:" + os.sep + "temp" + os.sep + "Agent"):
    if os.path.isdir(p):
        try:
            os.rmdir(p)
            print("  OK 已移除空目录 " + p)
        except OSError:
            print("  -- 非空，保留待人工确认: " + p)

# 预置默认目标根
mc.save_target_root(AGENT)
print("")
print("DONE 默认迁移目标已设为 " + AGENT)
