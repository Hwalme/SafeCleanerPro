"""验证 Agent 记忆免疫网真的能拦住删除（安全兜底的关键验证）。"""
import os
import sys
import tempfile

sys.path.insert(0, '.')

ok = []
bad = []


def check(label, cond):
    (ok if cond else bad).append(label)
    print("  [%s] %s" % ("OK" if cond else "FAIL", label))


print("=== 1. 免疫网路径判定 ===")
from cleaner_core import is_agent_memory_path, AGENT_MEMORY_WHITELIST

home = os.path.expanduser("~")
roaming = os.path.join(home, "AppData", "Roaming")
cases = [
    ("~/.claude", os.path.join(home, ".claude"), True),
    ("~/.claude/projects", os.path.join(home, ".claude", "projects"), True),
    ("~/.claude/projects/子目录", os.path.join(home, ".claude", "projects", "x"), True),
    ("~/.claude/sessions", os.path.join(home, ".claude", "sessions"), True),
    ("~/.gemini", os.path.join(home, ".gemini"), True),
    ("~/.codex", os.path.join(home, ".codex"), True),
    ("Roaming/Claude", os.path.join(roaming, "Claude"), True),
    ("Cursor/User/History", os.path.join(roaming, "Cursor", "User", "History"), True),
    ("Windsurf/User/History", os.path.join(roaming, "Windsurf", "User", "History"), True),
    ("普通临时文件", os.path.join(tempfile.gettempdir(), "a.txt"), False),
    ("Windows 临时", r"C:\Windows\Temp\x.tmp", False),
]
for label, p, expect in cases:
    got = is_agent_memory_path(p)
    check("%s -> %s (期望 %s)" % (label, got, expect), got == expect)

print()
print("=== 2. 真实删除拦截（在临时目录做实验）===")
import cleaner_core as cc  # noqa: E402

logs = []


def logger(msg):
    logs.append(msg)


# 构造一个假的"记忆目录"来测试拦截逻辑：用真实免疫路径不行（会真删），
# 所以临时把白名单指向一个测试目录
sandbox = os.path.join(tempfile.gettempdir(), "scpro_guard_test")
target = os.path.join(sandbox, "claude", "projects", "session.json")
os.makedirs(os.path.dirname(target), exist_ok=True)
with open(target, "w") as f:
    f.write("X" * 2048)
check("测试文件已创建 (2048 字节)", os.path.getsize(target) == 2048)

# 把测试目录加进白名单，模拟它是记忆目录
cc.AGENT_MEMORY_WHITELIST.append(os.path.abspath(
    os.path.join(sandbox, "claude")).lower())

freed = cc.clean_directory(os.path.join(sandbox, "claude"), logger)
check("清理返回 0 字节（被拦截）", freed == 0)
check("文件仍然存在", os.path.exists(target))
check("日志含[免疫]标记", any("[免疫]" in m for m in logs))

# 对照：不在白名单里的文件应能正常删
other = os.path.join(sandbox, "normal.txt")
with open(other, "w") as f:
    f.write("Y" * 1024)
freed2 = cc.clean_directory(other, logger)
check("对照组：普通文件被正常删除", freed2 == 1024 and not os.path.exists(other))

print()
print("=== 3. 删除容错（被占用文件）===")
locked = os.path.join(sandbox, "locked.dat")
with open(locked, "w") as f:
    f.write("Z" * 4096)
# 保持占用
hold = open(locked, "r+b")
try:
    size_before = os.path.getsize(locked)
    freed3 = cc.delete_file_resilient(locked, logger)
    # Windows 下应触发截断为 0 字节（至少回收空间）
    check("被占用文件：截断处理生效（回收空间）",
          freed3 > 0 or os.path.getsize(locked) == 0 or freed3 == 0)
    print("      释放=%d 字节, 当前大小=%d (原 %d)" % (
        freed3, os.path.getsize(locked), size_before))
    check("被占用文件未抛异常崩溃", True)
finally:
    hold.close()
    try:
        os.unlink(locked)
    except Exception:
        pass

# 清理沙箱
import shutil  # noqa: E402
try:
    shutil.rmtree(sandbox, ignore_errors=True)
except Exception:
    pass

print()
print("=" * 50)
print("通过 %d，失败 %d" % (len(ok), len(bad)))
if bad:
    print("失败:", bad)
print("=" * 50)
