"""扩充清理能力后的整体验证。"""
import sys
import time

sys.path.insert(0, '.')
import main as m  # noqa: E402
import cleaner_rules as cr  # noqa: E402
import cleaner_core as cc  # noqa: E402

ok, bad = [], []


def check(label, cond):
    (ok if cond else bad).append(label)
    print("  [%s] %s" % ("OK" if cond else "FAIL", label))


print("=== 1. 规则库 ===")
print("   规则总数:", cr.count_rules())
apps = cc.get_supported_apps()
print("   合并后清理项:", len(apps))
check("清理项 > 原 64 项", len(apps) > 64)
ids = [a["id"] for a in apps]
check("无重复 id", len(ids) == len(set(ids)))

required = ["id", "name", "paths", "icon", "immune", "type", "risk_level", "risk_desc"]
missing = []
for a in apps:
    for k in required:
        if k not in a:
            missing.append((a.get("id"), k))
check("所有项字段完整", not missing)
if missing:
    print("    缺字段:", missing[:5])

check("risk_level 只取 safe/risk",
      all(a["risk_level"] in ("safe", "risk") for a in apps))
check("type 取值合法",
      all(a["type"] in ("system", "app", "chat", "dev", "ai", "adobe") for a in apps))
check("免疫项仍为 4 个", sum(1 for a in apps if a.get("immune")) == 4)

print()
print("=== 2. 免疫网（核心安全） ===")
check("白名单非空", len(cc.AGENT_MEMORY_WHITELIST) > 0)
check("~/.claude/projects 受保护",
      cc.is_agent_memory_path(cc.os.path.expanduser("~/.claude/projects")))
check("~/.claude/sessions 受保护",
      cc.is_agent_memory_path(cc.os.path.expanduser("~/.claude/sessions")))
check("Cursor 历史受保护",
      cc.is_agent_memory_path(
          cc.os.path.join(cc.os.environ.get("APPDATA", ""), "Cursor", "User", "History")))
check("普通临时目录不受保护",
      not cc.is_agent_memory_path(r"C:\Windows\Temp\x.tmp"))

print()
print("=== 3. 新增删除容错 ===")
check("delete_file_resilient 存在", hasattr(cc, "delete_file_resilient"))
check("_schedule_reboot_delete 存在", hasattr(cc, "_schedule_reboot_delete"))
import inspect  # noqa: E402
sig = inspect.signature(cc.clean_directory)
check("clean_directory 支持 stale_days", "stale_days" in sig.parameters)

print()
print("=== 4. stale_days 规则已接线 ===")
stale_apps = [a for a in apps if a.get("stale_days")]
check("存在 stale_days 规则", len(stale_apps) > 0)
for a in stale_apps:
    print("    %s (stale_days=%s)" % (a["name"], a["stale_days"]))
src = open("main.py", encoding="utf-8").read()
check("main.py 已透传 stale_days", "stale_days=app.get(\"stale_days\")" in src)

print()
print("=== 5. 主窗口仍可正常构建 ===")
app = m.SafeCleanerApp()
app.update_idletasks()
t0 = time.perf_counter()
app.build_ui()
t1 = time.perf_counter()
app.update()
t2 = time.perf_counter()
print("   build_ui: %.0f ms, 首次绘制: %.0f ms" % ((t1 - t0) * 1000, (t2 - t1) * 1000))
check("主窗口构建成功", hasattr(app, "btn_action"))
check("查重台按钮在", hasattr(app, "btn_dedup"))

print()
print("=== 6. 惰性列表仍生效 ===")
# Round M 后：未扫描时 0 大小项默认隐藏（队列只有分组标题，属预期）。
# 打开「显示所有项」再验证惰性分批建行。
app.render_scroll_list()
q = len(app._row_queue)
check("未扫描隐藏 0 大小项（队列 %d 项）" % q, q <= 2)
app.show_all_items = True
app.render_scroll_list()
q2 = len(app._row_queue)
check("显示所有项后已排队 %d 项" % q2, q2 > 0)
frames = 0
while app._row_queue and frames < 20000:
    app.update()
    frames += 1
check("队列跑完，建行 %d" % len(app.app_rows), len(app.app_rows) > 0)

app.destroy()
print()
print("=" * 50)
print("通过 %d，失败 %d" % (len(ok), len(bad)))
if bad:
    print("失败:", bad)
print("=" * 50)
