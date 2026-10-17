# -*- coding: utf-8 -*-
"""AI 记忆无损迁移核心 —— NTFS Junction（目录联接）方案。

原理：
  把 C 盘的 AI 记忆目录**整体搬移**到其他数据盘（如 D:），
  并在原位置留下一个 NTFS 目录联接（Junction）指过去。
  Junction 对所有程序完全透明：绝对路径不变、无需管理员权限，
  Claude / Cursor / Gemini / Codex 等工具照常按原路径读写，无感知。

安全流水线（每个源目录独立执行，任何一步失败立即回滚）：
  1. 预检   —— 状态 / 目标盘空间 / 源与目标路径交叉检查
  2. 复制   —— 逐文件复制到目标盘（失败重试时可断点续传）
  3. 校验   —— 文件数 + 字节数 + 重解析点清单与源完全一致才继续
  4. 换位   —— 原目录原子改名保留为备份（同卷瞬时完成；文件被
               占用会在此步失败并回滚，提示关闭对应程序）
  5. 联接   —— 原位置建 Junction；失败则把备份改名回来
  6. 穿透校验 —— 通过原路径（此时已是 Junction）再统计一遍，
               与源一致才证明「程序按原路径读到的数据无损」
  7. 清理   —— 穿透校验通过后才删除 C 盘备份，真正释放空间

数据在「穿透校验」通过前从未从 C 盘消失，任何一步出错都自动回滚，
原路径始终可用 —— 这就是「不影响软件运行 + 记忆无损伤」的保证。
"""
import ctypes
import json
import os
import re
import shutil
import stat as stat_mod
import string
import subprocess
import winreg
from datetime import datetime

HOME = os.path.expanduser("~")
ROAMING = os.path.join(HOME, "AppData", "Roaming")
LOCAL = os.path.join(HOME, "AppData", "Local")

BACKUP_SUFFIX = ".scp_migrate_bak"
RESTORE_SUFFIX = ".scp_restore_tmp"

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
IO_REPARSE_TAG_MOUNT_POINT = 0xA0000003


class MigrateError(Exception):
    """迁移失败（数据已自动回滚到原位）。"""


class LockedError(MigrateError):
    """源目录内有文件被其他程序占用，无法换位。"""


# ----------------------------------------------------------------------
# 目录册：可迁移的 AI 记忆项（与 cleaner_core 免疫网同源的目录集合）
# ----------------------------------------------------------------------
# 每项 sources 下的每个真实存在的目录会**各自**建一个 Junction；
# 例如 Cursor 一项会对其 History / workspaceStorage / globalStorage
# 三个记忆子目录分别联接，避免整迁 %APPDATA%\Cursor 波及程序本体。
CATALOG = [
    {
        "id": "claude_code", "icon": "🤖", "category": "编程助手",
        "name": "Claude Code 会话记忆",
        "desc": "~/.claude 对话历史 / todos / 快照（整个目录）",
        "sources": ["~/.claude"],
    },
    {
        "id": "claude_desktop", "icon": "💬", "category": "编程助手",
        "name": "Claude 桌面端数据",
        "desc": "%APPDATA%\\Claude 对话与配置数据",
        "sources": ["%APPDATA%/Claude"],
    },
    {
        "id": "gemini", "icon": "✨", "category": "编程助手",
        "name": "Gemini / Antigravity 记忆",
        "desc": "~/.gemini CLI 与 Antigravity 工作区上下文",
        "sources": ["~/.gemini"],
    },
    {
        "id": "codex", "icon": "🧠", "category": "编程助手",
        "name": "OpenAI Codex 记忆",
        "desc": "~/.codex 与 %APPDATA%\\OpenAI\\Codex 会话/历史",
        "sources": ["~/.codex", "%APPDATA%/OpenAI/Codex"],
    },
    {
        "id": "zcode", "icon": "⚡", "category": "编程助手",
        "name": "ZCode CLI 记忆",
        "desc": "~/.zcode 会话历史 / 记忆 / 配置",
        "sources": ["~/.zcode"],
    },
    {
        "id": "cursor", "icon": "🖱", "category": "编辑器记忆",
        "name": "Cursor 工作区记忆",
        "desc": "User\\History / workspaceStorage / globalStorage（仅记忆子目录）",
        "sources": [
            "%APPDATA%/Cursor/User/History",
            "%APPDATA%/Cursor/User/workspaceStorage",
            "%APPDATA%/Cursor/User/globalStorage",
        ],
    },
    {
        "id": "windsurf", "icon": "🏄", "category": "编辑器记忆",
        "name": "Windsurf 工作区记忆",
        "desc": "User\\History / workspaceStorage / globalStorage（仅记忆子目录）",
        "sources": [
            "%APPDATA%/Windsurf/User/History",
            "%APPDATA%/Windsurf/User/workspaceStorage",
            "%APPDATA%/Windsurf/User/globalStorage",
        ],
    },
    {
        "id": "trae", "icon": "🌊", "category": "编辑器记忆",
        "name": "Trae 工作区记忆",
        "desc": "Trae CN / TRAE SOLO CN 的记忆子目录",
        "sources": [
            "%APPDATA%/Trae CN/User/History",
            "%APPDATA%/Trae CN/User/workspaceStorage",
            "%APPDATA%/Trae CN/User/globalStorage",
            "%APPDATA%/TRAE SOLO CN/User/History",
            "%APPDATA%/TRAE SOLO CN/User/workspaceStorage",
            "%APPDATA%/TRAE SOLO CN/User/globalStorage",
        ],
    },
    {
        "id": "ollama_models", "icon": "🦙", "category": "本地模型",
        "name": "Ollama 本地模型",
        "desc": "~/.ollama/models 模型权重（仅 models，不动密钥）",
        "sources": ["~/.ollama/models"],
    },
    {
        "id": "hf_cache", "icon": "拥", "category": "本地模型",
        "name": "HuggingFace 模型缓存",
        "desc": "~/.cache/huggingface 下载的模型与数据集",
        "sources": ["~/.cache/huggingface"],
    },
    {
        "id": "lmstudio_models", "icon": "🧪", "category": "本地模型",
        "name": "LM Studio 模型",
        "desc": "~/.lmstudio/models 模型权重",
        "sources": ["~/.lmstudio/models"],
    },
    {
        "id": "antigravity_cli", "icon": "🛰", "category": "编程助手",
        "name": "Antigravity Agent 工作区",
        "desc": "~/.antigravity 本地工作区与索引（可达 GB 级）",
        "sources": ["~/.antigravity"],
    },
    {
        "id": "opencode", "icon": "🔌", "category": "编程助手",
        "name": "OpenCode 会话数据",
        "desc": "~/.config/opencode 会话与项目数据",
        "sources": ["~/.config/opencode"],
    },
    {
        "id": "qwen_cli", "icon": "🐧", "category": "编程助手",
        "name": "Qwen Code CLI",
        "desc": "~/.qwen 会话历史与配置",
        "sources": ["~/.qwen"],
    },
    {
        "id": "cherry_studio", "icon": "🍒", "category": "AI 助手",
        "name": "Cherry Studio 数据",
        "desc": "%APPDATA%\\CherryStudio 对话与知识库数据",
        "sources": ["%APPDATA%/CherryStudio"],
    },
    {
        "id": "ima", "icon": "📚", "category": "AI 助手",
        "name": "ima 知识库数据",
        "desc": "%LOCALAPPDATA%\\ima.copilot 知识库/对话数据（迁移前请关闭 ima）",
        "sources": ["%LOCALAPPDATA%/ima.copilot"],
    },
    {
        "id": "doubao_desktop", "icon": "🥟", "category": "AI 助手",
        "name": "豆包桌面版数据",
        "desc": "%LOCALAPPDATA%\\Doubao 本地数据（迁移前请关闭豆包）",
        "sources": ["%LOCALAPPDATA%/Doubao"],
    },
    {
        "id": "minimax_desktop", "icon": "🎲", "category": "AI 助手",
        "name": "MiniMax 桌面数据",
        "desc": "%APPDATA%\\MiniMax 桌面版会话数据（迁移前请关闭 MiniMax）",
        "sources": ["%APPDATA%/MiniMax"],
    },
    {
        "id": "zcode_desktop", "icon": "⚡", "category": "编程助手",
        "name": "ZCode 桌面会话",
        "desc": "%APPDATA%\\ZCode 桌面版会话数据",
        "sources": ["%APPDATA%/ZCode"],
    },
]

# 自动发现时跳过的家族目录（目录册已有显式项，避免重复）
_DISCOVER_SKIP_FAMILY = {"cursor", "windsurf", "trae cn", "trae solo cn"}

_VSCODE_FAMILY_SUBDIRS = ("User/History", "User/workspaceStorage",
                          "User/globalStorage")

# AI CLI / Agent 的家目录 dot 目录（自动发现白名单：只认已知 AI 工具名，
# 绝不碰 .config/.cache 等通用目录）。存在且非空即生成迁移项。
_DOT_AGENT_DIRS = (
    ".antigravity", ".antigravity-ide", ".antigravity_cockpit",
    ".antigravity_tools", ".cline", ".codebuddy", ".codebuddycn", ".codeium",
    ".comate", ".comate-engine", ".continue", ".copilot", ".cursor",
    ".devin", ".devin-shared", ".factory", ".kimi-work", ".kimi-webbridge",
    ".kiro", ".kilocode", ".lingma", ".minimax", ".minimax-agent-cn",
    ".neovate", ".openhands", ".opencode-browser", ".qoder", ".qoder-cli",
    ".qoder-cn", ".qwen", ".qwenworkcn", ".roo", ".trae", ".trae-aicc",
    ".trae-cn", ".windsurf", ".workbuddy", ".zencoder", ".mavis",
    ".hermes", ".ai_completion", ".codex-gpt", ".clawdbot", ".modlens",
    ".config/opencode",
)


def _discover_vscode_family(roaming=None):
    """自动发现 %APPDATA% 下的 VSCode 家族 AI IDE（含 User/globalStorage 标记）。

    Qoder / Lingma(通义灵码) / Comate(百度) / CodeBuddy(腾讯) / Antigravity /
    Trae 新版 / devin / VS Code(Copilot 记忆)…… 以后新装的 AI IDE 只要沿用
    VSCode 目录布局就会被自动识别，无需改代码。
    """
    roaming = roaming or ROAMING
    items = []
    try:
        names = sorted(os.listdir(roaming))
    except OSError:
        return items
    for name in names:
        if name.lower() in _DISCOVER_SKIP_FAMILY:
            continue
        base = os.path.join(roaming, name)
        if not os.path.isdir(os.path.join(base, "User", "globalStorage")):
            continue
        sources = [os.path.join(base, *sub.split("/"))
                   for sub in _VSCODE_FAMILY_SUBDIRS]
        items.append({
            "id": "vsf_" + re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower(),
            "icon": "🧩", "category": "编辑器记忆(自动发现)",
            "name": f"{name} 工作区记忆",
            "desc": "User\\History / workspaceStorage / globalStorage"
                    "（自动发现的 VSCode 家族记忆目录）",
            "sources": sources,
        })
    return items


def _discover_dot_agents(home=None, min_files=3, min_bytes=1024 * 1024):
    """自动发现家目录下的 AI CLI / Agent 记忆目录（~/.claude、~/.qoder-cn 等）。

    只认 _DOT_AGENT_DIRS 白名单里的名字（存在且非空、真实目录非联接、
    达到最小体量），按（文件数>=min_files 或 体积>=min_bytes）过滤噪音，
    联接/悬空目录跳过（可能是用户已有的迁移点）。
    """
    home = home or HOME
    items = []
    for dot in _DOT_AGENT_DIRS:
        p = os.path.normpath(os.path.join(home, *dot.split("/")))
        if not os.path.isdir(p) or is_reparse_dir(p):
            continue
        try:
            files, total, _r = walk_stats(p)
        except Exception:
            continue
        if files < min_files and total < min_bytes:
            continue
        items.append({
            "id": "dot_" + re.sub(r"[^A-Za-z0-9]+", "_", dot).strip("_").lower(),
            "icon": "🤖", "category": "Agent 记忆(自动发现)",
            "name": f"{dot} Agent 数据",
            "desc": f"~/{dot} AI CLI 会话/记忆/配置（自动发现）",
            "sources": [p],
        })
    return items


def _exp(p):
    """展开 ~ 与环境变量，返回绝对路径。"""
    return os.path.abspath(os.path.expandvars(os.path.expanduser(p)))


def build_catalog():
    """返回真实存在（至少一个源目录存在）的迁移项列表。

    = 静态目录册 CATALOG + _discover_vscode_family() 自动发现的项
    （按已认领的源路径归一化去重，显式项优先）。
    每项附带 sources_resolved：[源绝对路径]，只保留存在的。
    """
    items = []
    claimed = set()

    def _resolve(spec):
        resolved = []
        for s in spec["sources"]:
            p = _exp(s)
            try:
                if os.path.exists(p):
                    resolved.append(p)
            except OSError:
                pass
        return resolved

    for spec in CATALOG:
        resolved = _resolve(spec)
        if resolved:
            it = dict(spec)
            it["sources_resolved"] = resolved
            items.append(it)
            claimed.update(os.path.normcase(p) for p in resolved)

    for spec in _discover_vscode_family():
        resolved = [p for p in _resolve(spec)
                    if os.path.normcase(p) not in claimed]
        if not resolved:
            continue
        it = dict(spec)
        it["sources_resolved"] = resolved
        items.append(it)
        claimed.update(os.path.normcase(p) for p in resolved)

    for spec in _discover_dot_agents():
        resolved = [p for p in _resolve(spec)
                    if os.path.normcase(p) not in claimed]
        if not resolved:
            continue
        it = dict(spec)
        it["sources_resolved"] = resolved
        items.append(it)
        claimed.update(os.path.normcase(p) for p in resolved)
    return items


# ----------------------------------------------------------------------
# Junction 探测 / 创建 / 删除
# ----------------------------------------------------------------------
def _lstat(path):
    try:
        return os.lstat(path)
    except OSError:
        return None


def is_junction(path):
    """path 是否为 NTFS 目录联接（Mount Point 重解析点）。"""
    st = _lstat(path)
    if st is None:
        return False
    if not (getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT):
        return False
    tag = getattr(st, "st_reparse_tag", 0)
    return tag in (stat_mod.IO_REPARSE_TAG_MOUNT_POINT, IO_REPARSE_TAG_MOUNT_POINT)


def is_reparse_dir(path):
    """path 是否为任何形式的重解析目录（Junction / 符号链接）。"""
    st = _lstat(path)
    if st is None:
        return False
    return bool(getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)


def link_target(path):
    """读取联接目标并归一化（去 \\?\\ 前缀 + normcase）。失败返回 None。"""
    try:
        t = os.readlink(path)
    except OSError:
        return None
    if t.startswith("\\\\?\\"):
        t = t[4:]
    return os.path.normcase(os.path.normpath(t))


def create_junction(link_path, target_path):
    """在 link_path 创建指向 target_path 的目录联接。无需管理员权限。"""
    link_path = os.path.abspath(link_path)
    target_path = os.path.abspath(target_path)
    try:
        import _winapi
        _winapi.CreateJunction(link_path, target_path)
    except Exception:
        # 兜底：mklink /J（同样不需要管理员权限）。cmd 输出是本地代码页
        # 编码，用 bytes 接收，只看返回码，避免解码线程崩溃。
        try:
            r = subprocess.run(
                ["cmd", "/c", "mklink", "/J", link_path, target_path],
                capture_output=True,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            if r.returncode != 0:
                return False
        except Exception:
            return False
    return os.path.isdir(link_path)


def remove_junction(junction_path):
    """删除联接本身（os.rmdir 只删重解析点，绝不递归删目标内容）。"""
    if not is_reparse_dir(junction_path):
        return False
    try:
        # 只读属性可能挡住 rmdir
        os.chmod(junction_path, stat_mod.S_IWRITE)
    except OSError:
        pass
    try:
        os.rmdir(junction_path)
        return True
    except OSError:
        return False


# ----------------------------------------------------------------------
# 统计（walk 不深入任何重解析点，避免穿透联接重复统计/循环）
# ----------------------------------------------------------------------
def walk_stats(root, progress=None, every=200):
    """统计目录：返回 (files, bytes, reparse_relpaths)。

    遇到重解析点（Junction/符号链接）不深入内容，仅记录其相对路径 ——
    复制阶段会按「重建联接」处理，因此校验阶段也按联接本体比对。
    """
    files = 0
    total = 0
    reparse = []
    seen = 0
    stack = [os.path.abspath(root)]
    while stack:
        cur = stack.pop()
        try:
            entries = list(os.scandir(cur))
        except OSError:
            continue
        for e in entries:
            seen += 1
            try:
                if e.is_dir(follow_symlinks=False) and \
                        (e.stat(follow_symlinks=False).st_file_attributes
                         & FILE_ATTRIBUTE_REPARSE_POINT):
                    reparse.append(os.path.relpath(e.path, root))
                    continue
                if e.is_dir(follow_symlinks=False):
                    stack.append(e.path)
                elif e.is_file(follow_symlinks=False):
                    st = e.stat(follow_symlinks=False)
                    files += 1
                    total += st.st_size
            except OSError:
                continue
            if progress and seen % every == 0:
                progress(seen, -1)
    return files, total, reparse


def get_dir_free_space(path):
    """返回路径所在卷的剩余字节数。"""
    try:
        drive = os.path.splitdrive(os.path.abspath(path))[0]
        if not drive:
            drive = "\\"
        elif not drive.endswith("\\"):
            drive += "\\"
        return shutil.disk_usage(drive).free
    except Exception:
        return 0


DRIVE_FIXED = 3


def volume_fs(drive_letter):
    """返回盘符的文件系统名（如 'NTFS' / 'exFAT'），探测失败返回 ''。"""
    try:
        root = drive_letter if drive_letter.endswith("\\") else drive_letter + "\\"
        buf = ctypes.create_unicode_buffer(64)
        ok = ctypes.windll.kernel32.GetVolumeInformationW(
            root, None, 0, None, None, None, buf, len(buf))
        return buf.value if ok else ""
    except Exception:
        return ""


def list_target_drives():
    """迁移目标候选：除 C: 以外的**固定磁盘**，且必须 NTFS。

    Junction 只存在于 NTFS 上 —— exFAT/FAT32 盘直接排除，避免复制完整趟
    之后才在「建联接」一步失败。返回 ['D:\\\\', 'E:\\\\', ...]。
    """
    out = []
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
    except Exception:
        return out
    for i, letter in enumerate(string.ascii_uppercase):
        if letter == "C":
            continue
        if (bitmask >> i) & 1:
            d = f"{letter}:\\"
            try:
                if ctypes.windll.kernel32.GetDriveTypeW(d) != DRIVE_FIXED:
                    continue
                if volume_fs(d).upper() != "NTFS":
                    continue
                out.append(d)
            except Exception:
                pass
    return out


# ----------------------------------------------------------------------
# 迁移记录（与 lock_store 同目录：%LOCALAPPDATA%/SafeCleanerPro）
# ----------------------------------------------------------------------
def _manifest_path():
    base = os.environ.get("LOCALAPPDATA") or HOME
    app_dir = os.path.join(base, "SafeCleanerPro")
    try:
        os.makedirs(app_dir, exist_ok=True)
    except OSError:
        pass
    return os.path.join(app_dir, "move_map.json")


def load_manifest():
    try:
        with open(_manifest_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get("migrations", []) or []
    except (OSError, ValueError):
        pass
    return []


def save_manifest_entry(entry):
    data = load_manifest()
    data = [m for m in data
            if not (m.get("source", "").lower() == entry.get("source", "").lower())]
    data.append(entry)
    p = _manifest_path()
    tmp = p + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"migrations": data}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    except OSError:
        pass


def drop_manifest_entry(source):
    data = load_manifest()
    data = [m for m in data if m.get("source", "").lower() != source.lower()]
    p = _manifest_path()
    tmp = p + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"migrations": data}, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    except OSError:
        pass


# ----------------------------------------------------------------------
# 状态检测
# ----------------------------------------------------------------------
# 单源状态
ST_CLEAN = "clean"          # 真实目录，未迁移
ST_MIGRATED = "migrated"    # Junction 且目标存在且指向登记目标
ST_BROKEN = "broken"        # Junction 但目标丢失 / 指向不明
ST_OTHER = "other"          # 其他重解析点（符号链接等），不可迁移动
ST_MISSING = "missing"      # 路径不存在

_STATUS_LABEL = {
    ST_CLEAN: "未迁移",
    ST_MIGRATED: "已迁移",
    ST_BROKEN: "联接悬空!",
    ST_OTHER: "已是链接",
    ST_MISSING: "不存在",
}


def source_status(source):
    st = _lstat(source)
    if st is None:
        return ST_MISSING
    if getattr(st, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT:
        if is_junction(source):
            tgt = link_target(source)
            if tgt and os.path.isdir(tgt):
                return ST_MIGRATED
            return ST_BROKEN
        return ST_OTHER
    return ST_CLEAN if st.st_mode & stat_mod.S_IFDIR else ST_MISSING


def item_status(item):
    """聚合一项的所有源：clean / migrated / partial / broken。"""
    statuses = [source_status(s) for s in item["sources_resolved"]]
    if any(s == ST_BROKEN for s in statuses):
        return "broken"
    if all(s == ST_MIGRATED for s in statuses):
        return "migrated"
    if any(s in (ST_MIGRATED,) for s in statuses):
        return "partial"
    if all(s == ST_CLEAN for s in statuses):
        return "clean"
    return "partial"


_STATUS_ITEM_LABEL = {
    "clean": "未迁移",
    "migrated": "已迁移",
    "partial": "部分迁移",
    "broken": "联接悬空!",
}


# ----------------------------------------------------------------------
# 复制 / 校验
# ----------------------------------------------------------------------
def _copy_file(src, dst):
    """复制单文件，保留元数据；目标已存在且等大则跳过（断点续传）。"""
    try:
        if os.path.isfile(dst) and \
                os.stat(dst).st_size == os.stat(src).st_size:
            return False
    except OSError:
        pass
    dst_dir = os.path.dirname(dst)
    if dst_dir and not os.path.isdir(dst_dir):
        os.makedirs(dst_dir, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def _copy_file_resilient(src, dst, first_error, warnings, log=None):
    """单文件复制失败的兜底（按序尝试）：

    1) \\\\?\\ 前缀重试 —— 名尾点/尾空格/超长路径会被 Win32 路径规范化
       吞掉（scandir 列得到、按名字打开报 WinError 2）；
    2) 源已消失 —— AI 工具运行中会滚动删除自己的 bak/log，恰好在复制
       间隙被删。跳过并警告：校验阶段按源实时重算，两侧依然严格一致，
       迁移可以继续（数据无损：消失的文件本来就不存在了）；
    3) 都不行 → 抛 MigrateError 交上层回滚。

    返回 True=已复制 / False=已跳过。
    """
    src_ext = "\\\\?\\" + os.path.abspath(src)
    try:
        if os.path.isfile(src_ext):
            dst_ext = "\\\\?\\" + os.path.abspath(dst)
            ddir = os.path.dirname(dst_ext)
            if not os.path.isdir(ddir):
                os.makedirs(ddir, exist_ok=True)
            shutil.copy2(src_ext, dst_ext)
            return True
    except OSError:
        pass
    try:
        still_there = os.path.lexists(src) or os.path.isfile(src_ext)
    except OSError:
        still_there = True
    if not still_there:
        msg = f"源文件在复制间隙消失(已跳过): {src}"
        warnings.append(msg)
        if log:
            log(f"⚠ {msg}")
        return False
    raise MigrateError(f"复制失败 {src}: {first_error}")


def copy_tree(src_root, dst_root, log=None, progress=None, cancel=None):
    """把 src_root 复制到 dst_root（可续传）。重解析点按「重建联接」处理。

    单文件复制失败直接抛 MigrateError —— 让上层回滚，数据无损。
    progress(seen_entries, copied_bytes) 由上层包装。
    """
    copied = 0
    copied_bytes = 0
    run_bytes = 0            # 含续传跳过的已就位文件，用于进度显示
    warnings = []
    seen = 0
    os.makedirs(dst_root, exist_ok=True)
    stack = [(src_root, dst_root)]
    while stack:
        s_root, d_root = stack.pop()
        try:
            entries = list(os.scandir(s_root))
        except OSError as e:
            raise MigrateError(f"无法读取源目录 {s_root}: {e}")
        for e in entries:
            if cancel and cancel():
                raise MigrateError("已取消")
            seen += 1
            s_path = e.path
            d_path = os.path.join(d_root, e.name)
            try:
                st = e.stat(follow_symlinks=False)
                if st.st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                    # 源内部已有联接/符号链接：原样重建，不深入复制
                    if os.path.lexists(d_path):
                        if is_reparse_dir(d_path):
                            pass  # 续传时已建过
                        else:
                            _rmtree_force(d_path)
                            create_junction(d_path, link_target(s_path) or s_path)
                    else:
                        tgt = link_target(s_path) or s_path
                        if not create_junction(d_path, tgt):
                            warnings.append(f"重建联接失败(已跳过): {e.name}")
                    continue
                if e.is_dir(follow_symlinks=False):
                    if not os.path.isdir(d_path):
                        os.makedirs(d_path, exist_ok=True)
                    stack.append((s_path, d_path))
                    continue
                if e.is_file(follow_symlinks=False):
                    try:
                        done = _copy_file(s_path, d_path)
                    except OSError as ex:
                        done = _copy_file_resilient(s_path, d_path, ex,
                                                    warnings, log)
                    if done:
                        copied += 1
                        copied_bytes += st.st_size
                    run_bytes += st.st_size
            except MigrateError:
                raise
            except OSError as ex:
                raise MigrateError(f"复制失败 {s_path}: {ex}")
            if progress and seen % 50 == 0:
                progress(seen, run_bytes)
    if progress:
        progress(seen, run_bytes)
    return copied, copied_bytes, warnings


def _force_rm(func, path, excinfo):
    try:
        os.chmod(path, stat_mod.S_IWRITE)
        func(path)
        return
    except OSError:
        pass
    # 名尾点/尾空格等被 Win32 路径规范化吞掉的条目：\\?\ 前缀重试
    try:
        func("\\\\?\\" + os.path.abspath(path))
    except OSError:
        pass


def _rmtree_force(path):
    """强删目录树（清只读位重试）。兼容 onexc(3.12+)/onerror(旧版)：
    onerror 参数自 3.12 弃用、3.14 移除，冻结版若换 Python 不能炸在这里。"""
    def _on_any(func, path, exc):
        _force_rm(func, path, exc if isinstance(exc, tuple) else (type(exc), exc, None))
    try:
        shutil.rmtree(path, onexc=_on_any)
    except TypeError:
        shutil.rmtree(path, onerror=_on_any)


def verify_same(src_root, dst_root, progress=None):
    """逐字节级口径比对两个树：文件数 / 总字节 / 重解析点清单必须一致。

    返回 None 表示一致；否则返回差异描述字符串。
    """
    sf, sb, sr = walk_stats(src_root, progress=progress)
    df, db, dr = walk_stats(dst_root, progress=progress)
    if (sf, sb) != (df, db):
        return f"文件数/体积不一致 (源 {sf}个/{sb}B vs 目标 {df}个/{db}B)"
    if sorted(x.lower() for x in sr) != sorted(x.lower() for x in dr):
        return f"内部联接清单不一致 (源 {len(sr)} vs 目标 {len(dr)})"
    return None


# ----------------------------------------------------------------------
# 迁移 / 迁回
# ----------------------------------------------------------------------
def _check_path_safety(source, target):
    """源与目标不得互相嵌套（否则联接成环 / 递归复制）。"""
    s = os.path.normcase(os.path.normpath(source))
    t = os.path.normcase(os.path.normpath(target))
    if s == t:
        raise MigrateError("目标路径与源路径相同")
    if t.startswith(s + os.sep):
        raise MigrateError("目标路径位于源目录内部")
    if s.startswith(t + os.sep):
        raise MigrateError("源目录位于目标路径内部")


def _plan_targets(item, target_root, item_target=None):
    """为每个源规划目标目录。

    item_target：用户为该子项单独指定的目标路径 ——
      单源   → 精确落到该路径，**不自动追加任何子文件夹**；
      多源   → 一条路径放不下多个目录，在该路径内按 <序号_目录名> 分放。
    未指定 → 默认 <target_root>/<item_id>/<idx>_<dirname>。
    """
    plans = []
    single = item_target and len(item["sources_resolved"]) == 1
    for i, s in enumerate(item["sources_resolved"]):
        tail = os.path.basename(s.rstrip("\\/")) or "mem"
        if single:
            dst = os.path.abspath(item_target)
        elif item_target:
            dst = os.path.join(os.path.abspath(item_target),
                               f"{i:02d}_{tail}")
        else:
            dst = os.path.join(target_root, item["id"], f"{i:02d}_{tail}")
        plans.append((s, dst))
    return plans


def migrate_item(item, target_root, log=None, progress=None, cancel=None,
                 item_target=None):
    """迁移一项（其全部源目录）。返回汇总 dict；失败抛 MigrateError。

    log(msg)      —— 进度日志
    progress(cur_src, done_files, total_files, done_bytes, total_bytes)
    cancel()      —— 返回 True 中止（自动回滚）
    item_target   —— 该子项的自定义目标路径（见 _plan_targets）
    """
    def _log(m):
        if log:
            log(m)

    plans = _plan_targets(item, target_root)

    # ---- 1. 预检：状态 ----
    for s in item["sources_resolved"]:
        stt = source_status(s)
        if stt == ST_MISSING:
            raise MigrateError(f"源目录不存在: {s}")
        if stt == ST_BROKEN:
            raise MigrateError(f"{s} 是悬空联接，请先修复")
        if stt == ST_OTHER:
            raise MigrateError(f"{s} 是非联接链接，为安全起见不迁移")
        if stt == ST_MIGRATED:
            raise MigrateError(f"{s} 已经是迁移联接，无需重复迁移")

    # ---- 1. 预检：路径安全 + 目标盘格式 + 空间 + 与已迁移条目不重叠 ----
    total_bytes = 0
    total_files = 0
    src_stats = {}
    for s in item["sources_resolved"]:
        f, b, r = walk_stats(s)
        src_stats[s] = (f, b, r)
        total_files += f
        total_bytes += b
    for s, d in plans:
        _check_path_safety(s, d)
        if volume_fs(os.path.splitdrive(d)[0]).upper() != "NTFS":
            raise MigrateError(
                f"目标盘不是 NTFS 格式，无法创建目录联接: {os.path.splitdrive(d)[0]}")
        free = get_dir_free_space(d)
        if free and free < total_bytes + 64 * 1024 * 1024:
            raise MigrateError(
                f"目标盘空间不足：需要约 {total_bytes / 1024 ** 3:.1f} GB，"
                f"剩余 {free / 1024 ** 3:.1f} GB")
        if os.path.lexists(d) and not os.path.isdir(d):
            raise MigrateError(f"目标位置被非目录文件占用: {d}")
    # 目标不得嵌进其他条目已迁移的联接树里（防止套娃到别人的数据盘目录）
    for m in load_manifest():
        mt = m.get("target", "")
        if not mt:
            continue
        mt = os.path.normcase(os.path.normpath(mt))
        for _s, d in plans:
            dd = os.path.normcase(os.path.normpath(d))
            if dd == mt or dd.startswith(mt + os.sep) or mt.startswith(dd + os.sep):
                raise MigrateError(
                    f"目标路径与已迁移条目「{m.get('name', mt)}」的目标重叠: {d}")

    target_of = dict(plans)

    # ---- 2. 复制 + 3. 校验（逐源）----
    done_bytes = 0
    actual = {}      # 复制校验通过那一刻的源真实统计（消失文件已扣除）
    for s, d in plans:
        _log(f"⇢ 复制 {s} → {d}")

        def _prog(seen, run_bytes, s=s):
            if progress:
                if run_bytes < 0:      # verify / walk 阶段无字节数：视为该源已完成
                    run_bytes = src_stats[s][1]
                progress(s, seen, total_files, done_bytes + run_bytes, total_bytes)

        try:
            copy_tree(s, d, log=_log, progress=_prog, cancel=cancel)
        except MigrateError:
            raise
        diff = verify_same(s, d, progress=_prog)
        if diff:
            raise MigrateError(
                f"复制校验未通过（{diff}）；源目录在迁移期间可能仍有写入，"
                f"请关闭对应软件后重试（目标临时文件已保留，重试自动断点续传）")
        actual[s] = walk_stats(s)
        done_bytes += actual[s][1]
        _log(f"✓ 复制校验通过 {s} ({actual[s][0]} 个文件)")

    # ---- 4~6. 换位 / 联接 / 穿透校验（逐源；失败立即回滚该源）----
    swapped = []          # 已完成换位的 (src, backup)
    linked = []           # 已建联接的 src
    try:
        for s, d in plans:
            backup = s + BACKUP_SUFFIX
            while os.path.lexists(backup):
                backup += "_"
            if progress:
                progress(s, total_files, total_files, done_bytes, total_bytes)
            try:
                os.rename(s, backup)          # 原子换位；被占用在此失败
            except OSError as e:
                winerr = getattr(e, "winerror", None)
                if winerr in (5, 32):
                    raise LockedError(
                        f"「{os.path.basename(s)}」正被其他程序占用，请关闭对应软件后重试"
                        f"（已自动回滚，数据无损）") from e
                raise MigrateError(f"换位失败 {s}: {e}") from e
            swapped.append((s, backup))

            if not create_junction(s, d):
                raise MigrateError(f"创建目录联接失败: {s}")
            linked.append(s)

            # 穿透校验：通过原路径（联接）统计，与「复制校验通过那一刻」
            # 的源真实统计比对（消失文件已在 actual 中扣除）
            f, b, r = walk_stats(s)
            exp = actual[s]
            if (f, b) != (exp[0], exp[1]) or \
                    sorted(x.lower() for x in r) != sorted(x.lower() for x in exp[2]):
                raise MigrateError(f"联接穿透校验未通过: {s}")
            _log(f"✓ 联接生效且穿透校验通过 {s}")
    except Exception:
        # ---- 回滚：删联接 → 备份改名回原位。原路径恢复如初。----
        for s in linked:
            remove_junction(s)
        for s, backup in swapped:
            if not os.path.lexists(s) and os.path.lexists(backup):
                try:
                    os.rename(backup, s)
                except OSError:
                    pass
        raise

    # ---- 7. 清理备份，真正释放 C 盘空间 ----
    freed = 0
    for s, backup in swapped:
        try:
            _rmtree_force(backup)
        except OSError as e:
            _log(f"⚠ 备份删除失败（不影响使用，可手动删）: {backup} — {e}")
        freed += actual[s][1]
        save_manifest_entry({
            "id": item["id"],
            "name": item["name"],
            "source": s,
            "target": target_of.get(s, ""),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "files": actual[s][0],
            "bytes": actual[s][1],
        })
    return {"files": sum(v[0] for v in actual.values()),
            "bytes": freed, "targets": [d for _, d in plans]}


def restore_item(item, log=None, progress=None, cancel=None):
    """把已迁移的项迁回 C 盘原位。返回释放的目标盘字节数。"""
    def _log(m):
        if log:
            log(m)

    # 预检：所有源必须都是有效联接
    for s in item["sources_resolved"]:
        if not is_junction(s):
            raise MigrateError(f"{s} 不是迁移联接，无法迁回")

    for s in item["sources_resolved"]:
        if cancel and cancel():
            raise MigrateError("已取消")
        tgt = link_target(s)
        if not tgt or not os.path.isdir(tgt):
            raise MigrateError(f"联接目标丢失: {s} → {tgt}")
        tmp = s + RESTORE_SUFFIX
        while os.path.lexists(tmp):
            tmp += "_"

        # 预统计目标数据量，把 copy_tree 的 (seen, bytes) 包装成与迁移
        # 一致的 5 参进度签名 progress(cur_src, done_f, total_f, done_b, total_b)
        tf, tb, _tr = walk_stats(tgt)

        def _prog(seen, run_bytes, tgt=tgt, tf=tf, tb=tb):
            if progress:
                progress(tgt, seen, tf, run_bytes, tb)

        _log(f"⇠ 复制回 C 盘 {tgt} → {tmp}")
        copy_tree(tgt, tmp, log=_log, progress=_prog, cancel=cancel)
        diff = verify_same(tgt, tmp, progress=_prog)
        if diff:
            _rmtree_force(tmp)
            raise MigrateError(f"迁回复制校验未通过（{diff}），联接保持不变")

        # 换位：删联接 → 临时目录改名到原位。失败则恢复联接。
        try:
            if not remove_junction(s):
                _rmtree_force(tmp)
                raise MigrateError(f"删除联接失败: {s}")
            try:
                os.rename(tmp, s)
            except OSError as e:
                # 恢复联接，避免原路径悬空
                create_junction(s, tgt)
                winerr = getattr(e, "winerror", None)
                if winerr in (5, 32):
                    raise LockedError(
                        f"「{os.path.basename(s)}」正被其他程序占用，请关闭后重试"
                        f"（联接已恢复，数据无损）") from e
                raise MigrateError(f"还原改名失败 {s}: {e}") from e
        except MigrateError:
            raise

        # 验证原位真实目录可用，再清理目标盘数据
        if source_status(s) != ST_CLEAN:
            raise MigrateError(f"迁回后原位状态异常: {s}")
        try:
            _rmtree_force(tgt)
        except OSError as e:
            _log(f"⚠ 目标盘数据删除失败（不影响使用，可手动删）: {tgt} — {e}")
        drop_manifest_entry(s)
        _log(f"✓ 已迁回 {s}")
    return True


def migrated_target_of(source):
    """若 source 是联接，返回其目标（未归一化失败返回 None）。"""
    if is_junction(source):
        t = link_target(source)
        return t if (t and os.path.isdir(t)) else None
    return None


# ----------------------------------------------------------------------
# 联接改址：已迁移项换目标位置（同卷改名零拷贝 / 跨卷复制+校验）
# ----------------------------------------------------------------------
def retarget_junction(source, new_target, log=None, progress=None):
    """把已迁移联接的目标数据搬到 new_target，并让原联接改指新位置。

    安全序列：
      1. 预检（源是有效联接 / 新旧路径不嵌套 / 新盘空间）
      2. 数据搬运 —— 同卷：os.rename 瞬时完成（零拷贝）；
                     跨卷：copy_tree 复制 + verify_same 校验
      3. 换联接 —— 删旧联接 → 立即建新联接（失败回滚：重建旧联接）
      4. 穿透校验 —— 经原路径统计与新位置一致
      5. 清旧数据 + 更新台账
    返回 {"mode": "rename"|"copy", "bytes": N}。
    """
    def _log(m):
        if log:
            log(m)

    # ---- 1. 预检 ----
    if not is_junction(source):
        raise MigrateError(f"{source} 不是迁移联接，无法改址")
    old_target = link_target(source)
    if not old_target or not os.path.isdir(old_target):
        raise MigrateError(f"旧联接目标丢失: {source} → {old_target}")
    new_target = os.path.abspath(new_target)
    _check_path_safety(source, new_target)
    if os.path.normcase(old_target) == os.path.normcase(new_target):
        return {"mode": "none", "bytes": 0}
    if os.path.lexists(new_target) and not os.path.isdir(new_target):
        raise MigrateError(f"新位置被非目录文件占用: {new_target}")
    old_f, old_b, old_r = walk_stats(old_target)
    free = get_dir_free_space(new_target)
    same_vol = (os.path.splitdrive(os.path.abspath(old_target))[0].lower()
                == os.path.splitdrive(new_target)[0].lower())
    if not same_vol and free and free < old_b + 64 * 1024 * 1024:
        raise MigrateError(f"目标盘空间不足：需要约 {old_b / 1024 ** 3:.1f} GB")

    # ---- 2. 数据搬运 ----
    os.makedirs(os.path.dirname(new_target), exist_ok=True)
    if same_vol:
        # 同卷改名：瞬时零拷贝。旧目标若正被改名/占用则报错回滚前不动画。
        while os.path.lexists(new_target):
            new_target += "_"
        try:
            os.rename(old_target, new_target)
        except OSError as e:
            raise MigrateError(f"同卷搬移失败 {old_target}: {e}") from e
        _log(f"⇢ 同卷改名（零拷贝）→ {new_target}")
        mode = "rename"
    else:
        while os.path.lexists(new_target):
            new_target += "_"
        _log(f"⇢ 跨卷复制 {old_target} → {new_target}")

        def _prog(seen, run_bytes):
            if progress:
                progress(new_target, seen, old_f, run_bytes, old_b)

        copy_tree(old_target, new_target, log=_log, progress=_prog)
        diff = verify_same(old_target, new_target, progress=_prog)
        if diff:
            raise MigrateError(f"改址复制校验未通过（{diff}），旧数据原封不动")
        mode = "copy"

    # ---- 3. 换联接（失败回滚）----
    if not remove_junction(source):
        # 回滚数据位置
        if same_vol:
            try:
                os.rename(new_target, old_target)
            except OSError:
                pass
        raise MigrateError(f"删除旧联接失败: {source}")
    if not create_junction(source, new_target):
        create_junction(source, old_target)      # 必须恢复，防悬空
        raise MigrateError(f"创建新联接失败: {source}")

    # ---- 4. 穿透校验 ----
    f, b, r = walk_stats(source)
    if (f, b) != (old_f, old_b) or \
            sorted(x.lower() for x in r) != sorted(x.lower() for x in old_r):
        create_junction(source, old_target)      # 校验不过：联接指回旧位
        if mode == "copy":
            _rmtree_force(new_target)
        else:
            try:
                os.rename(new_target, old_target)
            except OSError:
                pass
        raise MigrateError(f"改址穿透校验未通过: {source}")
    _log(f"✓ 穿透校验通过，联接已指向 {new_target}")

    # ---- 5. 清旧数据 + 台账（沿用台账中已有的 id/名称） ----
    if mode == "copy":
        try:
            _rmtree_force(old_target)
        except OSError as e:
            _log(f"⚠ 旧位置数据删除失败（不影响使用，可手动删）: {old_target} — {e}")
    prev = next((m for m in load_manifest()
                 if m.get("source", "").lower() == os.path.normcase(
                     os.path.normpath(source))), None)
    base_name = os.path.basename(source.rstrip("\\/"))
    save_manifest_entry({
        "id": (prev or {}).get("id") or base_name.lstrip("."),
        "name": (prev or {}).get("name") or base_name,
        "source": source,
        "target": new_target,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files": old_f,
        "bytes": old_b,
        "note": "retarget",
    })
    return {"mode": mode, "bytes": old_b}


# ----------------------------------------------------------------------
# 目标位置持久化：常规目录 / AI 记忆 两条默认根 + 各子项自定义目标
# ----------------------------------------------------------------------
def _target_config_path():
    base = os.environ.get("LOCALAPPDATA") or HOME
    app_dir = os.path.join(base, "SafeCleanerPro")
    try:
        os.makedirs(app_dir, exist_ok=True)
    except OSError:
        pass
    return os.path.join(app_dir, "migrate_target.json")


def load_target_config():
    """读取目标配置 → {'root_shell': 常规目录根, 'root_ai': AI 记忆根,
    'custom_targets': {item_id: 自定义目标路径}}。

    兼容旧版单 root 记忆（旧值视为 AI 记忆根）。无效路径原样返回，
    由 UI 决定默认值。
    """
    cfg = {"root_shell": "", "root_ai": "", "custom_targets": {}}
    try:
        with open(_target_config_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            cfg["root_ai"] = data.get("root_ai") or data.get("root") or ""
            cfg["root_shell"] = data.get("root_shell") or ""
            ct = data.get("custom_targets")
            if isinstance(ct, dict):
                cfg["custom_targets"] = {
                    k: v for k, v in ct.items()
                    if isinstance(k, str) and isinstance(v, str) and v}
    except (OSError, ValueError):
        pass
    return cfg


def save_target_config(root_shell=None, root_ai=None, custom_targets=None):
    """增量保存：只覆盖给出的字段，其余保留。"""
    cfg = load_target_config()
    if root_shell is not None:
        cfg["root_shell"] = root_shell
    if root_ai is not None:
        cfg["root_ai"] = root_ai
    if custom_targets is not None:
        cfg["custom_targets"] = custom_targets
    try:
        p = _target_config_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
    except OSError:
        pass


def load_target_root():
    """兼容旧接口：返回 AI 记忆根（缺失返回 None）。"""
    root = load_target_config().get("root_ai", "")
    if root and os.path.splitdrive(root)[0] and os.path.isdir(
            os.path.splitdrive(root)[0] + "\\"):
        return root
    return None


def save_target_root(root):
    """兼容旧接口：保存 AI 记忆根。"""
    save_target_config(root_ai=root)


# ======================================================================
# C 盘常规目录迁移（桌面 / 下载 / 文档 / 图片…用户 Shell 文件夹）
# ======================================================================
# 无感原理：注册表 User Shell Folders **保持指向 C 盘原路径不动**，
# 只把原路径整体搬到数据盘并在原位留 Junction。资源管理器、保存对话框、
# 一切硬编码 C 路径的程序读到的仍是同一条路径 —— 桌面永远只有一张，
# 新放的东西穿透联接直接落到数据盘。别的"搬家工具"出多桌面事故，
# 正是因为改了注册表却留下（或新造）了第二份实体目录。
#
# 对被其他软件迁移过（注册表已指向别处）的目录做「统一迁移」：
#   各处内容全部并入数据盘统一目录（同名文件自动重命名共存），
#   注册表改回 C 盘原路径，原路径换联接 —— 恢复到唯一、无感的标准态。

SHELL_KEY_USER = (r"Software\Microsoft\Windows\CurrentVersion\Explorer"
                  r"\User Shell Folders")
SHELL_KEY_CACHE = (r"Software\Microsoft\Windows\CurrentVersion\Explorer"
                   r"\Shell Folders")

# 注册表值名 -> (中文名, 图标, %USERPROFILE% 下标准子目录, 排序权重)
SHELL_FOLDERS = [
    ("Desktop", "桌面", "🖥", "Desktop", 0),
    ("{374DE290-123F-4565-9164-39C4925E467B}", "下载", "📥", "Downloads", 1),
    ("Personal", "文档", "📄", "Documents", 2),
    ("My Pictures", "图片", "🖼", "Pictures", 3),
    ("My Video", "视频", "🎬", "Videos", 4),
    ("My Music", "音乐", "🎵", "Music", 5),
    ("Favorites", "收藏夹", "⭐", "Favorites", 6),
    ("{4C5C32FF-BB9D-43B0-B5B4-2E72C03E7C91}", "保存的游戏", "🎮",
     "Saved Games", 7),
    ("{56784854-C6CB-462B-8165-E86B88CB8CF5}", "联系人", "👤", "Contacts", 8),
    ("{7D1D3A04-BB5D-4E90-AE11-5B5D3B82D6B6}", "搜索", "🔎", "Searches", 9),
    ("{31C0E8C9-43C3-4A3F-9A58-26B8CB50A99A}", "3D 对象", "🧊",
     "3D Objects", 10),
]

# shell 项状态（在通用 ST_* 之上扩展）
SST_FOREIGN = "foreign"          # 注册表被他处软件改指到别的位置
SST_FOREIGN_DUP = "foreign_dup"  # 他迁 + C 盘原位仍有实体内容（重复目录）
SST_ONEDRIVE = "onedrive"        # OneDrive 接管（KFM 同步），不可迁

_SHELL_STATUS_LABEL = {
    SST_FOREIGN: "已他迁·可统一",
    SST_FOREIGN_DUP: "重复!建议统一",
    SST_ONEDRIVE: "OneDrive 管理",
}


def _open_shell_key(cache=False, write=False):
    path = SHELL_KEY_CACHE if cache else SHELL_KEY_USER
    access = winreg.KEY_SET_VALUE | winreg.KEY_READ if write else winreg.KEY_READ
    try:
        return winreg.OpenKey(winreg.HKEY_CURRENT_USER, path, 0, access)
    except FileNotFoundError:
        if write:
            return winreg.CreateKey(winreg.HKEY_CURRENT_USER, path)
        return None
    except OSError:
        return None


def read_shell_folders():
    """读 HKCU User Shell Folders → {值名: 展开后的绝对路径}。"""
    out = {}
    k = _open_shell_key()
    if k is None:
        return out
    try:
        i = 0
        while True:
            try:
                name, val, _typ = winreg.EnumValue(k, i)
            except OSError:
                break
            i += 1
            if isinstance(val, str) and val.strip():
                out[name] = os.path.abspath(
                    os.path.expandvars(val.strip().strip('"')))
    finally:
        k.Close()
    return out


def _broadcast_shell_change():
    """广播 WM_SETTINGCHANGE，尽力让资源管理器立即感知路径变化。"""
    try:
        HWND_BROADCAST = 0xFFFF
        WM_SETTINGCHANGE = 0x001A
        SMTO_ABORTIFHUNG = 0x0002
        res = ctypes.c_ulong()
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, None,
            SMTO_ABORTIFHUNG, 800, ctypes.byref(res))
    except Exception:
        pass


def write_shell_folder(value_name, path):
    """User Shell Folders 与 Shell Folders（兼容缓存）两处一起写。

    path 用展开后的绝对路径；REG_EXPAND_SZ 类型保留（无变量也合法），
    这样别的工具读到的值类型不变。仅「统一迁移」把注册表改回 C 原路径时使用。
    """
    path = os.path.abspath(path)
    for cache in (False, True):
        k = _open_shell_key(cache=cache, write=True)
        if k is None:
            continue
        try:
            winreg.SetValueEx(
                k, value_name, 0,
                winreg.REG_SZ if cache else winreg.REG_EXPAND_SZ, path)
        except OSError:
            pass
        finally:
            k.Close()
    _broadcast_shell_change()


def shell_same_path(a, b):
    return os.path.normcase(os.path.normpath(a)) == \
        os.path.normcase(os.path.normpath(b))


def build_shell_items(home=None):
    """生成「C 盘常规目录」迁移项列表（存在过才列）。

    每项：c_path=标准 C 盘原路径（联接落点，永不改动）、
          reg_path=注册表当前指向（可能被其他软件改过）、
          onedrive=True 表示被 OneDrive 接管（只展示不可迁）。
    """
    home = home or HOME
    reg = read_shell_folders()
    items = []
    for value_name, cn, icon, sub, _order in SHELL_FOLDERS:
        c_path = os.path.abspath(os.path.join(home, sub))
        reg_path = reg.get(value_name)
        raw_missing = reg_path is None
        reg_path = reg_path or c_path
        if raw_missing and not os.path.lexists(c_path):
            continue          # 系统从未有过此目录（如 3D 对象被删）
        onedrive = "onedrive" in reg_path.lower() or \
            "sharepoint" in reg_path.lower()
        items.append({
            "id": "shell_" + re.sub(r"[^a-z0-9]+", "_", sub.lower()).strip("_"),
            "kind": "shell", "icon": icon, "category": "常规目录",
            "name": cn, "value_name": value_name,
            "desc": f"{reg_path}" if not shell_same_path(reg_path, c_path)
                    else f"~/{sub}",
            "c_path": c_path, "reg_path": reg_path, "onedrive": onedrive,
            "sources": [c_path], "sources_resolved": [c_path],
        })
    items.sort(key=lambda x: next(o for v, _c, _i, _s, o in SHELL_FOLDERS
                                  if v == x["value_name"]))
    return items


def shell_item_status(item):
    """shell 项状态：clean / migrated / foreign / foreign_dup / onedrive /
    broken / missing。返回 (status, extras dict)。

    注册表以**操作时刻**的实读为准（别的搬家工具可能刚改过），
    并回写 item["reg_path"]，保证后续 unify 用同一份事实。
    """
    c_path = item["c_path"]
    live = read_shell_folders().get(item["value_name"])
    reg_path = live or item["c_path"]
    item["reg_path"] = reg_path
    extras = {}
    if "onedrive" in reg_path.lower() or "sharepoint" in reg_path.lower():
        return SST_ONEDRIVE, extras
    foreign = not shell_same_path(reg_path, c_path)
    st = source_status(c_path)
    if st == ST_MISSING and not foreign:
        return ST_MISSING, extras
    if st == ST_BROKEN:
        return ST_BROKEN, extras
    if foreign:
        extras["reg_path"] = reg_path
        c_real = os.path.isdir(c_path) and not is_reparse_dir(c_path)
        reg_real = os.path.isdir(reg_path) and not is_reparse_dir(reg_path)
        if c_real and reg_real:
            try:
                cf, _cb, _r = walk_stats(c_path)
                rf, _rb, _r2 = walk_stats(reg_path)
                extras["c_files"], extras["reg_files"] = cf, rf
                if cf and rf:
                    return SST_FOREIGN_DUP, extras
            except Exception:
                pass
        return SST_FOREIGN, extras
    if st == ST_MIGRATED:
        extras["target"] = migrated_target_of(c_path)
        return ST_MIGRATED, extras
    if st == ST_CLEAN:
        return ST_CLEAN, extras
    return st, extras


def shell_item_stats(item):
    """体积口径：clean/migrated 看 C 侧（或联接目标），foreign 看注册表
    指向侧；foreign_dup 合计两侧。返回 (files, bytes, status, extras)。"""
    status, extras = shell_item_status(item)
    files = bytes_ = 0
    try:
        if status == SST_FOREIGN_DUP:
            for p in (item["c_path"], extras.get("reg_path", "")):
                if p and os.path.isdir(p):
                    f, b, _r = walk_stats(p)
                    files += f
                    bytes_ += b
        elif status == SST_FOREIGN:
            p = extras.get("reg_path", "")
            if p and os.path.isdir(p):
                f, b, _r = walk_stats(p)
                files, bytes_ = f, b
        elif status == ST_CLEAN:
            f, b, _r = walk_stats(item["c_path"])
            files, bytes_ = f, b
        elif status == ST_MIGRATED:
            tgt = extras.get("target")
            if tgt and os.path.isdir(tgt):
                f, b, _r = walk_stats(tgt)
                files, bytes_ = f, b
    except Exception:
        pass
    return files, bytes_, status, extras


# ----------------------------------------------------------------------
# 合并复制：内容并入已存在目录，同名不同内容自动重命名共存
# ----------------------------------------------------------------------
def _dedupe_name(dst_dir, name):
    """dst_dir 里 name 已被占用时给一个未占用的 name(2).ext。"""
    if not os.path.lexists(os.path.join(dst_dir, name)):
        return name, False
    stem, ext = os.path.splitext(name)
    i = 2
    while True:
        cand = f"{stem}({i}){ext}"
        if not os.path.lexists(os.path.join(dst_dir, cand)):
            return cand, True
        i += 1


def merge_tree(src_root, dst_root, log=None, progress=None, cancel=None):
    """把 src_root 的内容并入已存在的 dst_root（dst 必须是真实目录）。

    - 同名且等大的文件视为同一文件，跳过（与 copy_tree 断点续传同语义）
    - 同名不同内容的文件保留双方：新来的改名「name(2).ext」——两个桌面
      里各有一份「简历.doc」时，谁也不覆盖谁
    - 同名目录递归合并；文件撞目录时文件改名避让
    - 重解析点原样重建联接，不深入
    返回 (copied_files, copied_bytes, mapping)；
    mapping = [(rel_src, dst_rel)] 覆盖来源**每一个**文件（含跳过的），
    供 verify_merged 逐文件核对落位。真正改名的条目会顺带写日志。
    """
    def _log(m):
        if log:
            log(m)

    if not os.path.isdir(dst_root) or is_reparse_dir(dst_root):
        raise MigrateError(f"合并目标必须是真实目录: {dst_root}")
    copied = 0
    copied_bytes = 0
    run_bytes = 0
    mapping = []
    seen = 0
    stack = [(src_root, "")]
    while stack:
        s_dir, rel = stack.pop()
        try:
            entries = list(os.scandir(s_dir))
        except OSError as e:
            raise MigrateError(f"无法读取来源目录 {s_dir}: {e}")
        for e in entries:
            if cancel and cancel():
                raise MigrateError("已取消")
            seen += 1
            s_path = e.path
            rel_src = os.path.join(rel, e.name)
            d_dir = os.path.join(dst_root, rel) if rel else dst_root
            try:
                st = e.stat(follow_symlinks=False)
                if st.st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT:
                    tgt = link_target(s_path) or s_path
                    d_path = os.path.join(d_dir, e.name)
                    if not os.path.lexists(d_path) and \
                            not create_junction(d_path, tgt):
                        _log(f"⚠ 重建联接失败(已跳过): {rel_src}")
                    continue
                if e.is_dir(follow_symlinks=False):
                    d_path = os.path.join(d_dir, e.name)
                    if os.path.lexists(d_path) and not os.path.isdir(d_path):
                        d_name2, _r = _dedupe_name(d_dir, e.name)
                        d_path = os.path.join(d_dir, d_name2)
                    if not os.path.isdir(d_path):
                        os.makedirs(d_path, exist_ok=True)
                    stack.append((s_path,
                                  os.path.join(rel, os.path.basename(d_path))))
                    continue
                if e.is_file(follow_symlinks=False):
                    run_bytes += st.st_size
                    d_name = e.name
                    if os.path.isfile(os.path.join(d_dir, d_name)):
                        try:
                            if os.stat(os.path.join(
                                    d_dir, d_name)).st_size == st.st_size:
                                mapping.append((rel_src, os.path.join(rel, d_name)))
                                continue        # 同名等大：视为同一文件
                        except OSError:
                            pass
                        d_name, renamed = _dedupe_name(d_dir, e.name)
                    else:
                        renamed = False
                    rel_dst = os.path.join(rel, d_name)
                    os.makedirs(d_dir, exist_ok=True)
                    shutil.copy2(s_path, os.path.join(d_dir, d_name))
                    copied += 1
                    copied_bytes += st.st_size
                    mapping.append((rel_src, rel_dst))
                    if renamed:
                        _log(f"  同名共存：{rel_src} → {rel_dst}")
            except MigrateError:
                raise
            except OSError as ex:
                raise MigrateError(f"合并复制失败 {s_path}: {ex}")
            if progress and seen % 50 == 0:
                progress(seen, run_bytes)
    if progress:
        progress(seen, run_bytes)
    return copied, copied_bytes, mapping


def verify_merged(src_root, mapping, dst_root):
    """校验合并结果：mapping 里每个来源文件都已在 dst_root 落位且等大。

    返回 None 表示一致，否则差异描述。
    """
    src_abs = os.path.abspath(src_root)
    dst_abs = os.path.abspath(dst_root)
    for rel_src, rel_dst in mapping:
        try:
            s1 = os.stat(os.path.join(src_abs, rel_src)).st_size
            s2 = os.stat(os.path.join(dst_abs, rel_dst)).st_size
        except OSError as e:
            return f"合并落位缺失 {rel_dst}: {e}"
        if s1 != s2:
            return f"合并大小不一致 {rel_dst} (源 {s1}B vs 落位 {s2}B)"
    return None


# ----------------------------------------------------------------------
# 统一迁移（常规目录主入口）
# ----------------------------------------------------------------------
def unify_shell_item(item, target_root, sub_name=None, auto_mkdir=True,
                     log=None, progress=None, cancel=None, target_dir=None):
    """把一个常规目录（桌面/下载/文档…）统一迁移到数据盘。

    默认目标 <target_root>/<sub_name>；target_dir 给出（用户为该子项
    单独指定）时精确落到该路径，不再追加任何子文件夹。

    无论之前是标准布局还是被其他软件改过注册表，最终状态统一为：
      • 真实数据：target_dir
      • C 盘原路径 c_path：Junction 联接 → 真实数据（入口不变，无感）
      • 注册表 User Shell Folders：指回 c_path
    两侧（C 原位 + 注册表指向处）内容全部并入统一目录，同名文件自动
    重命名共存，任何一步失败自动回滚。返回汇总 dict。
    """
    def _log(m):
        if log:
            log(m)

    c_path = item["c_path"]
    value_name = item["value_name"]
    if target_dir:
        target_dir = os.path.abspath(target_dir)
    else:
        target_dir = os.path.abspath(
            os.path.join(target_root, sub_name or item["name"]))

    # ---- 1. 预检（shell_item_status 内部实读注册表并回写 reg_path）----
    st, extras = shell_item_status(item)
    reg_path = item["reg_path"]
    foreign = not shell_same_path(reg_path, c_path)
    if st == SST_ONEDRIVE:
        raise MigrateError("该目录由 OneDrive 接管，为免破坏同步不提供迁移")
    if st == ST_BROKEN:
        raise MigrateError(f"{c_path} 是悬空联接，请先处理")
    if st == ST_MIGRATED and not foreign:
        raise MigrateError(f"{c_path} 已迁移过，无需重复迁移")
    if st == ST_MISSING and not foreign:
        raise MigrateError(f"源目录不存在: {c_path}")
    _check_path_safety(c_path, target_dir)
    if foreign and os.path.isdir(reg_path):
        _check_path_safety(reg_path, target_dir)
        _check_path_safety(c_path, reg_path)
    if volume_fs(os.path.splitdrive(target_dir)[0]).upper() != "NTFS":
        raise MigrateError(
            f"目标盘不是 NTFS 格式，无法创建目录联接: "
            f"{os.path.splitdrive(target_dir)[0]}")

    # ---- 2. 收集合并来源并统计 ----
    sources = []          # (标签, 路径)
    c_real = os.path.isdir(c_path) and not is_reparse_dir(c_path)
    if c_real:
        sources.append(("C盘原位", c_path))
    if foreign and os.path.isdir(reg_path) and not is_reparse_dir(reg_path) \
            and not shell_same_path(reg_path, target_dir):
        sources.append(("原迁移位置", reg_path))
    total_bytes = 0
    total_files = 0
    src_stats = {}
    for _tag, s in sources:
        f, b, _r = walk_stats(s)
        src_stats[s] = (f, b)
        total_files += f
        total_bytes += b
    free = get_dir_free_space(target_dir)
    if free and free < total_bytes + 64 * 1024 * 1024:
        raise MigrateError(
            f"目标盘空间不足：需要约 {total_bytes / 1024 ** 3:.1f} GB，"
            f"剩余 {free / 1024 ** 3:.1f} GB")
    if os.path.lexists(target_dir) and not os.path.isdir(target_dir):
        raise MigrateError(f"目标位置被非目录文件占用: {target_dir}")
    if not os.path.isdir(target_dir):
        if not auto_mkdir:
            raise MigrateError(
                f"目标文件夹不存在（未勾选自动建立）：{target_dir}")
        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
            raise MigrateError(f"无法创建目标文件夹 {target_dir}: {e}")
        _log(f"✓ 已建立目标文件夹 {target_dir}")

    # 目标不与其他条目的联接树重叠
    for m in load_manifest():
        mt = m.get("target", "")
        if not mt:
            continue
        mt = os.path.normcase(os.path.normpath(mt))
        td = os.path.normcase(os.path.normpath(target_dir))
        if td == mt or td.startswith(mt + os.sep) or mt.startswith(td + os.sep):
            raise MigrateError(
                f"目标路径与已迁移条目「{m.get('name', mt)}」的目标重叠: "
                f"{target_dir}")

    # ---- 3. 逐来源并入统一目录（失败即整体回滚语义：目标内只增不删，
    #        C 侧原封未动 —— 此时还没有任何不可逆操作）----
    done_bytes = 0
    all_renames = []
    records = []
    for tag, s in sources:
        f, b = src_stats[s]

        def _prog(seen, run_bytes, s=s, f=f, b=b, tag=tag):
            if progress:
                progress(s, seen, total_files, done_bytes + run_bytes,
                         total_bytes)

        _log(f"⇢ 并入[{tag}] {s} → {target_dir}")
        _copied, _bytes, record = merge_tree(
            s, target_dir, log=_log, progress=_prog, cancel=cancel)
        diff = verify_merged(s, record, target_dir)
        if diff:
            raise MigrateError(
                f"合并校验未通过（{diff}）；源目录在迁移期间可能仍有写入，"
                f"请关闭占用程序后重试（已并入的文件保留，重试自动续传）")
        records.append((s, record))
        all_renames.extend((rs, rd) for rs, rd in record
                           if os.path.normcase(rs) != os.path.normcase(rd))
        done_bytes += b
        _log(f"✓ 合并校验通过 [{tag}] ({f} 个文件)")

    # ---- 4. 注册表改回 C 盘原路径（foreign 时）----
    if foreign:
        write_shell_folder(value_name, c_path)
        _log(f"✓ 注册表已改回 C 盘原路径：{value_name} → {c_path}")

    # ---- 5. C 盘原路径换位 → 联接（失败回滚）----
    if c_real:
        backup = c_path + BACKUP_SUFFIX
        while os.path.lexists(backup):
            backup += "_"
        if progress:
            progress(c_path, total_files, total_files, done_bytes, total_bytes)
        try:
            os.rename(c_path, backup)
        except OSError as e:
            winerr = getattr(e, "winerror", None)
            if winerr in (5, 32):
                raise LockedError(
                    f"「{item['name']}」正被其他程序占用（资源管理器/微信等），"
                    f"请关闭后重试（已自动回滚，数据无损）") from e
            raise MigrateError(f"换位失败 {c_path}: {e}") from e
        try:
            if not create_junction(c_path, target_dir):
                raise MigrateError(f"创建目录联接失败: {c_path}")
        except MigrateError:
            try:
                os.rename(backup, c_path)
            except OSError:
                pass
            raise
    else:
        if os.path.lexists(c_path):
            raise MigrateError(f"C 盘原路径被非目录占用: {c_path}")
        if not create_junction(c_path, target_dir):
            raise MigrateError(f"创建目录联接失败: {c_path}")

    # ---- 6. 穿透校验：经原路径能完整看到各来源全部内容 ----
    for s, record in records:
        diff = verify_merged(s, record, c_path)
        if diff:
            # 回滚：删联接，恢复备份
            remove_junction(c_path)
            if c_real and os.path.lexists(backup) and not os.path.lexists(c_path):
                try:
                    os.rename(backup, c_path)
                except OSError:
                    pass
            raise MigrateError(f"联接穿透校验未通过: {s}")
    _log(f"✓ 联接生效且穿透校验通过 {c_path}")

    # ---- 7. 清理 C 盘备份，登记台账 ----
    freed = 0
    if c_real:
        try:
            _rmtree_force(backup)
        except OSError as e:
            _log(f"⚠ 备份删除失败（不影响使用，可手动删）: {backup} — {e}")
        freed = src_stats.get(c_path, (0, 0))[1]
        if progress:
            progress(c_path, total_files, total_files, total_bytes, total_bytes)
    save_manifest_entry({
        "id": item["id"], "name": f"{item['name']}(C盘常规目录)",
        "source": c_path, "target": target_dir,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files": total_files, "bytes": freed, "kind": "shell",
    })
    if foreign:
        _log(f"ℹ 原迁移位置 {reg_path} 的数据已全部并入，确认无误后可手动删除")
    return {"files": total_files, "bytes": freed, "target": target_dir,
            "renames": all_renames, "foreign": foreign}
