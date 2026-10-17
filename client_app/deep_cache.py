# -*- coding: utf-8 -*-
"""AppData 深度优化：可清缓存规则库 + 只读扫描引擎。

设计原则（安全优先）：
1. **只清纯缓存**：Cache / Code Cache / GPUCache / CacheStorage / blob_storage /
   ShaderCache / Crashpad / 日志 / 崩溃转储。绝不清 Cookies、登录态、配置、
   sqlite 数据库、用户上传内容、聊天消息库。
2. **精确到子目录**：应用目录（如 JianyingPro）下既有缓存又有用户数据，
   只取其缓存子目录，绝不整目录删除。
3. **免疫网兜底**：复用 cleaner_core.AGENT_MEMORY_WHITELIST（AI Agent 记忆），
   删除前由 clean_directory 二次校验，规则无法越过。
4. 本模块**扫描只读**；清理调用既有 clean_directory，不另写删除逻辑。
"""
import os
import time
from secure_rules import RulePackError

from cleaner_core import (
    AGENT_MEMORY_WHITELIST,
    is_agent_memory_path,
)

BS = chr(92)
LOCAL = os.environ.get("LOCALAPPDATA", "") or ""
ROAM = os.environ.get("APPDATA", "") or ""
HOME = os.path.expanduser("~")
# %USERPROFILE%\AppData\LocalLow（游戏/Unity 缓存常在此）
LOW = os.path.join(os.path.dirname(LOCAL), "LocalLow") if LOCAL else ""


def _L(*parts):
    return os.path.join(LOCAL, *parts) if LOCAL else ""


def _R(*parts):
    return os.path.join(ROAM, *parts) if ROAM else ""


# ----------------------------------------------------------------------
# 绝不清理的文件名 / 扩展名（浏览器状态与用户数据）
# ----------------------------------------------------------------------
PROTECTED_NAMES = {
    "cookies", "cookies-journal", "login data", "login data-journal",
    "web data", "web data-journal", "local state", "preferences",
    "bookmarks", "bookmarks.bak", "favicons", "history", "history-journal",
    "shortcuts", "extension cookies", "secure preferences",
    "current session", "current tabs", "last session", "last tabs",
    "sync data.sqlite3", "local storage leveldb",
}
PROTECTED_EXTS = {
    ".sqlite", ".sqlite3", ".db", ".ldb", ".log1",
}
# 路径关键字命中即视为用户数据，整体跳过
PROTECTED_KEYWORDS = (
    "extensions", "local storage", "indexeddb", "file system",
    "databases", "wechat files", "msgattach", "filestorage\\msg",
    "filestorage\\file", "filestorage\\video", "filestorage\\image",
    "filestorage\\cache\\msg", "customemoji", "tencent files",
    # WebView/Chromium 分区与网页存储：内含登录态与网页数据，绝不清
    "partitions", "webstorage",
)
# AI 记忆目录：按「路径段精确匹配」判定，不用子串包含。
# 反例：%L%\Codex\logs（可清日志）含 "codex"，而 %H%\.codex（禁）也含 "codex"，
# 子串匹配会把可清日志一起误保护。
PROTECTED_AI_DIRS = (
    ".claude", ".codex", ".gemini", ".cursor", ".continue", ".continue-dev",
    ".codeium", ".aider", ".windsurf", ".cline", ".tabby", ".roo", ".kilocode",
    ".vscode", ".trae", ".trae-cn", ".trae-aicc", ".qoder", ".qoder-cn",
    ".codebuddy", ".codebuddycn", ".lingma", ".comate", ".comate-engine",
    ".qwen", ".minimax", ".devin", ".factory", ".kiro", ".zencoder",
    ".opencode2dsh", ".neovate", ".mcpjam", ".playwright-mcp", ".coding-tools-mcp",
    ".dsh", ".antigravity", ".lmstudio", ".insightface", ".u2net", ".keras",
    ".antigravity-ide", ".antigravity_cockpit", ".antigravity_tools",
    ".qoder-cli", ".qwenworkcn", ".mavis", ".kimi-work", ".kimi-webbridge",
    ".workbuddy", ".codex-gpt", ".hermes", ".ai_completion", ".clawdbot",
    ".modlens", ".opencode-browser", ".openhands", ".minimax-agent-cn",
)
# AppData 下的 AI 应用目录（Roaming / Local 一级目录名）。
# 只保护「记忆/会话占主体」的应用；VSCode 家族（Cursor/Windsurf/Trae...）
# 的缓存由 User 子目录碎片 + workspaceStorage/globalStorage 关键字精细保护，
# 其 Cache/CachedData/GPUCache/Crashpad/CachedExtensionVSIXs 可安全清理。
PROTECTED_AI_APPDATA = ("claude", "openai", "zcode")

# 凭据 / 密钥（删了无法恢复）
PROTECTED_CREDS = (
    ".ssh", ".aws", ".kube", ".azure", ".gcloud", ".gnupg", ".pki", ".docker",
    "credentials", "protect", "crypto", "keystore", "npmrc", "netrc",
    "git-credentials", "gitconfig", "config.json", "auth.json",
)
# 工作区 / 依赖（不是缓存，删了项目跑不起来）
PROTECTED_WORKSPACE = (
    "node_modules", "site-packages", ".git", ".svn", "venv", ".venv", "env",
    "dist", "build", "__pycache__", "packages\\*\\localstate", "localstate",
    "workspaceStorage", "globalStorage", "localhistory", "backups", "workspaces",
)


# 编辑器/AI IDE 的用户配置根（扩展、设置、快捷键、AI 会话）
# 注意：只精确匹配 <编辑器目录>\User，不能用裸 "user" 段
# （Chrome/JianyingPro 的 "User Data" 是另一个段，清缓存必须放行）
PROTECTED_EDITOR_USER_FRAGMENTS = (
    "\\code\\user\\", "\\code - insiders\\user\\", "\\cursor\\user\\",
    "\\windsurf\\user\\", "\\trae\\user\\", "\\trae cn\\user\\",
    "\\vscodium\\user\\", "\\code oss\\user\\",
    # 国产 AI IDE 家族（Trae SOLO / Qoder / 通义灵码 / 腾讯 CodeBuddy /
    # 百度 Comate / Google Antigravity / 美团 WorkBuddy）
    "\\trae solo cn\\user\\", "\\qoder\\user\\", "\\lingma\\user\\",
    "\\codebuddy cn\\user\\", "\\comate\\user\\", "\\antigravity\\user\\",
    "\\antigravity ide\\user\\", "\\workbuddy\\user\\",
)


def _seg_match(low, names):
    """路径中出现该目录段（完整段，带分隔符边界）即命中。"""
    sep = os.sep
    for n in names:
        if low.endswith(sep + n) or (sep + n + sep) in low:
            return True
    return False


def is_protected_path(path):
    """删除/统计前的最后一道闸门：命中即不可清。"""
    try:
        low = os.path.abspath(path).lower().rstrip("\\/")
    except Exception:
        return True
    base = os.path.basename(low)
    if base in PROTECTED_NAMES:
        return True
    if os.path.splitext(base)[1] in PROTECTED_EXTS:
        return True
    for kw in PROTECTED_KEYWORDS:
        if kw in low:
            return True
    if _seg_match(low, PROTECTED_AI_DIRS):
        return True
    if _seg_match(low, PROTECTED_AI_APPDATA):
        return True
    if _seg_match(low, PROTECTED_CREDS):
        return True
    if _seg_match(low, PROTECTED_WORKSPACE):
        return True
    for frag in PROTECTED_EDITOR_USER_FRAGMENTS:
        if frag in low:
            return True
    # WSL / Docker 虚拟机磁盘（删 = 容器镜像全丢）
    for vm in ("\\wsl\\", "\\docker\\wsl", "ext4.vhdx"):
        if vm in low:
            return True
    # 模型权重本体（用户花数小时下载）
    for m in ("\\.ollama\\models", "\\huggingface\\hub", "\\lmstudio\\models", "\\jan\\models"):
        if m in low:
            return True
    # AI Agent 记忆免疫网
    try:
        if is_agent_memory_path(low):
            return True
    except Exception:
        for w in AGENT_MEMORY_WHITELIST:
            if low == w or low.startswith(w + os.sep):
                return True
    return False


# ----------------------------------------------------------------------
# 规则库
# ----------------------------------------------------------------------
# Chromium 内核：User Data 下每个 Profile（Default / Profile N / 其他）
CHROMIUM_SUBDIRS = [
    ("Cache", "网页缓存"),
    ("Code Cache", "JS 代码缓存"),
    ("GPUCache", "GPU 着色缓存"),
    ("Service Worker\\CacheStorage", "Service Worker 缓存"),
    ("Service Worker\\ScriptCache", "Service Worker 脚本缓存"),
    ("blob_storage", "Blob 数据缓存"),
    ("Session Storage", "会话存储缓存"),
    ("ShaderCache", "着色器缓存"),
    ("Media Cache", "媒体缓存"),
    ("VideoDecodeStats", "视频解码统计"),
]
CHROMIUM_ROOT_SUBDIRS = [
    ("ShaderCache", "GPU 着色缓存"),
    ("Crashpad", "崩溃转储"),
]
CHROMIUM_USERDATA = [
    ("Google Chrome", _L("Google", "Chrome", "User Data")),
    ("Microsoft Edge", _L("Microsoft", "Edge", "User Data")),
    ("360 极速浏览器", _L("360Chrome", "Chrome", "User Data")),
    ("360 安全浏览器", _L("360se6", "User Data")),
    ("QQ 浏览器", _L("Tencent", "QQBrowser", "User Data")),
    ("搜狗浏览器", _L("SogouExplorer", "User Data")),
    ("Chromium", _L("Chromium", "User Data")),
    ("Brave", _L("BraveSoftware", "Brave-Browser", "User Data")),
    # AI 应用的 Chromium 内核数据（登录态由 PROTECTED 名单兜底，只清纯缓存）
    ("ima 知识库", _L("ima.copilot", "User Data")),
    ("豆包", _L("Doubao", "User Data")),
    ("腾讯元宝", _L("com.tencent.yuanbao", "EBWebView")),
]

# Electron / CEF 应用：目录名 -> (搜索根, 显示名)
WILDCARD_CACHE_SUBDIRS = [
    "GPUCache", "Code Cache", "Cache", "Code Cache\\js", "CacheStorage",
    "Service Worker\\CacheStorage", "Service Worker\\ScriptCache",
    "ShaderCache", "GrShaderCache", "DawnCache", "DawnWebGPUCache",
    "DawnGraphiteCache", "Crashpad\\reports", "crash_dumps", "crash_reports",
    "CachedData", "VideoDecodeStats", "JumpListIconsMostVisited",
    "JumpListIconsRecentClosed", "logs", "Logs", "log", "Log",
    "blob_storage", "Session Storage", "Media Cache", "ShaderCache\\GPUCache",
    "CachedExtensionVSIXs",      # AI IDE 已下载扩展安装包（可重新下载）
]

ELECTRON_CACHE_SUBDIRS = [
    "GPUCache", "Code Cache", "Cache", "CacheStorage", "blob_storage",
    "ShaderCache", "Crashpad", "Logs", "logs", "Crashpad\\attachments",
    "CachedExtensionVSIXs",      # 已下载扩展安装包（可重新下载）
]

# AI 编辑器家族（VSCode 布局）：其 Cache/CachedData/CachedExtensionVSIXs 等
# 在 roaming 根下，缓存子目录白名单清理；User\* 记忆由免疫网精细保护。
# 注意：不整目录清理，记忆目录（workspaceStorage/globalStorage/History）
# 由 clean_directory 免疫网二次校验兜底。
AI_FAMILY_ELECTRON_APPS = [
    ("Trae", ROAM, "Trae"),
    ("Trae CN", ROAM, "Trae CN"),
    ("TRAE SOLO CN", ROAM, "TRAE SOLO CN"),
    ("Qoder", ROAM, "Qoder"),
    ("通义灵码 Lingma", ROAM, "Lingma"),
    ("CodeBuddy CN", ROAM, "CodeBuddy CN"),
    ("百度 Comate", ROAM, "Comate"),
    ("WorkBuddy", ROAM, "WorkBuddy"),
    ("Antigravity", ROAM, "Antigravity"),
    ("Antigravity IDE", ROAM, "Antigravity IDE"),
    ("Windsurf", ROAM, "Windsurf"),
    ("Cursor", ROAM, "Cursor"),
    ("VS Code", ROAM, "Code"),
    ("MiniMax 桌面版", ROAM, "MiniMax"),
    ("Kimi 桌面版", ROAM, "kimi-desktop"),
]
ELECTRON_APPS = [
    ("剪映专业版", LOCAL, "JianyingPro"),
    ("豆包", LOCAL, "Doubao"),
    ("钉钉", LOCAL, "DingTalk_108"),
    ("企业微信", ROAM, "Tencent\\WXWork"),
    ("飞书", LOCAL, "Feishu"),
    ("Lark", LOCAL, "Lark"),
    ("Notion", LOCAL, "Notion"),
    ("Discord", LOCAL, "Discord"),
    ("Slack", LOCAL, "slack"),
    ("Spotify", LOCAL, "Spotify"),
    ("WhatsApp", LOCAL, "WhatsApp"),
    ("Telegram Desktop", ROAM, "Telegram Desktop"),
    ("Postman", LOCAL, "Postman"),
    ("Obsidian", ROAM, "obsidian"),
    ("Typora", ROAM, "Typora"),
    ("夸克", LOCAL, "Quark"),
    ("ima.copilot", LOCAL, "ima.copilot"),
    ("GitHub Desktop", LOCAL, "GitHubDesktop"),
    ("Playwright", LOCAL, "ms-playwright"),
    ("Quark 云盘", LOCAL, "Quark"),
]
ELECTRON_APPS += AI_FAMILY_ELECTRON_APPS

# 开发 / 包管理缓存
DEV_CACHE = [
    ("npm 缓存", _L("npm-cache", "_cacache")),
    ("pnpm 缓存", _L("pnpm-cache")),
    ("Yarn 缓存", _L("Yarn", "Cache")),
    ("uv 缓存", _L("uv", "cache")),
    ("pip 缓存", _L("pip", "cache")),
    ("Poetry 缓存", _L("pypoetry", "cache")),
    ("Go 构建缓存", _L("go-build")),
    ("NuGet 缓存", _L("NuGet", "http-cache")),
    ("Gradle 缓存", os.path.join(HOME, ".gradle", "caches")),
    ("Electron 缓存", _L("electron", "Cache")),
    ("Node GPUCache", _L("node-gyp", "Cache")),
]

# 系统级缓存
SYSTEM_CACHE = [
    ("Windows 临时文件", _L("Temp")),
    ("崩溃转储", _L("CrashDumps")),
    ("资源管理器缩略图缓存", _L("Microsoft", "Windows", "Explorer")),
    ("DirectX 着色器缓存", _L("D3DSCache")),
    ("NVIDIA 着色器缓存", _L("NVIDIA", "DXCache")),
    ("NVIDIA GLCache", _L("NVIDIA", "GLCache")),
    ("AMD 着色器缓存", _L("AMD", "DxCache")),
    ("字体缓存", _L("Microsoft", "Windows", "Fonts", "FontCache")),
    ("Windows 图标缓存", _L("IconCache.db")),
    ("传递优化缓存", _R("Microsoft", "Windows", "Delivery Optimization")),
    # 对齐通用清理器标准项（火绒级扫描对照后补充）
    ("Windows Temp 系统临时文件", r"C:\Windows\Temp"),
    ("Windows 组件日志 (CBS/DISM)", r"C:\Windows\Logs"),
    ("错误报告 (系统 WER)", r"C:\ProgramData\Microsoft\Windows\WER"),
    ("错误报告 (用户 WER)", _L("Microsoft", "Windows", "WER")),
    ("系统内存转储 (Minidump)", r"C:\Windows\Minidump"),
    ("内核实时转储", r"C:\Windows\LiveKernelReports"),
    ("Windows 更新下载缓存", r"C:\Windows\SoftwareDistribution\Download"),
    ("HubStudio SDK 缓存", _R("hubstudio-client", "sdk", "cache")),
    ("微信日志 (xwechat)", _R("Tencent", "xwechat", "log")),
    ("微信旧版日志", _R("Tencent", "WeChat", "log")),
    ("Office 升级包下载缓存", "C:" + BS + "Program Files (x86)" + BS + "Microsoft Office" + BS + "Updates" + BS + "Download"),
    ("Office 升级包下载缓存 (x64)", "C:" + BS + "Program Files" + BS + "Microsoft Office" + BS + "Updates" + BS + "Download"),
]

# 游戏 / 大平台缓存
GAME_CACHE = [
    ("Steam 下载缓存", _L("Steam", "steamapps", "downloading")),
    ("Steam 临时文件", _L("Steam", "steamapps", "temp")),
    ("Steam 着色器缓存", _L("Steam", "steamapps", "shadercache")),
    ("Steam 应用缓存", _L("Steam", "appcache")),
    ("Epic Games 缓存", _L("EpicGames", "Epic Online Services", "Cache")),
    ("Riot 客户端缓存", _L("Riot Games", "Riot Client", "Cache")),
    ("Battle.net 缓存", _L("Battle.net", "Cache")),
    ("Ubisoft 缓存", _L("Ubisoft Game Launcher", "cache")),
    ("Minecraft 缓存", _L("Minecraft", "cache")),
]

# 手动确认档：体积大、删了可恢复但代价高（重新下载/重建索引），绝不默认勾选
MANUAL_CACHE = [
    ("TRAE SOLO 虚拟机缓存",
     _R("TRAE SOLO CN", "VMCache"),
     "TRAE SOLO 的 Agent 虚拟机镜像缓存（可达 10GB）。删除后下次使用 SOLO "
     "需重新下载完整镜像，不用 SOLO 则可放心清。"),
    ("Trae ModularData",
     _R("Trae CN", "ModularData"),
     "Trae 的模块化功能数据（含 AI 索引）。删除后 Trae 会重建索引，"
     "首次启动变慢。"),
    ("Trae(国际版) ModularData",
     _R("Trae", "ModularData"),
     "同 Trae CN 的模块化数据，删除后重建。"),
    ("Ollama 更新包缓存",
     _L("Ollama", "updates_v2"),
     "Ollama 已下载的更新安装包，删除不影响当前版本运行。"),
]

CATEGORY_OF = {
    "chromium": "🌐 浏览器缓存",
    "electron": "⚡ 应用缓存",
    "dev": "💻 开发缓存",
    "system": "⚙️ 系统缓存",
    "game": "🎮 游戏缓存",
    "manual": "⚠️ 手动确认（默认不选）",
}


def _profile_dirs(userdata):
    """返回 User Data 下的所有 Profile 目录（Default / Profile N / ...）。"""
    if not userdata or not os.path.isdir(userdata):
        return []
    found = []
    try:
        for name in os.listdir(userdata):
            full = os.path.join(userdata, name)
            if not os.path.isdir(full):
                continue
            if name == "Default" or name.startswith("Profile ") or name.startswith("Guest"):
                found.append((name, full))
    except Exception:
        pass
    return found


def discover_electron_caches():
    """通配发现 AppData 一级应用目录下的通用缓存子目录。

    报告 §1.1：%L%\\*\\GPUCache、Code Cache、Service Worker、logs 等模式
    跨应用通用，硬编码应用名单必然漏（DingTalk_91、js.design、CodeBuddy 等）。
    这里做**白名单子目录**发现：只取已知安全的缓存目录名，绝不取父目录。
    """
    found = []
    for base, tag in ((LOCAL, "L"), (ROAM, "R")):
        if not base or not os.path.isdir(base):
            continue
        try:
            apps = [d for d in os.listdir(base)
                    if os.path.isdir(os.path.join(base, d))
                    and not is_reparse_point(os.path.join(base, d))]
        except Exception:
            continue
        for app in apps:
            root = os.path.join(base, app)
            if is_protected_path(root):
                continue
            for sub in WILDCARD_CACHE_SUBDIRS:
                p = os.path.join(root, sub)
                if os.path.isdir(p) and not is_protected_path(p) and not is_reparse_point(p):
                    found.append({
                        "id": f"wild_{tag}_{app}_{sub}".replace(" ", "_").replace("\\", "_").replace(".", "_"),
                        "name": f"{app} · {sub}",
                        "cat": "electron",
                        "paths": [p],
                        "risk": "safe",
                        "desc": "应用通用渲染/脚本缓存，进程退出后自动重建。",
                    })
    return found



def discover_updater_caches():
    """扫描 %LOCALAPPDATA% 下所有 *-updater 应用更新残留缓存。

    electron-updater 布局：优先清 pending 子目录（下载的安装包）；
    无 pending 的目录仅当内容全部是安装包/日志文件时才整目录清理，
    含 Update.exe / app-* 等程序结构的跳过（那是程序本体，不是缓存）。
    """
    base = os.environ.get("LOCALAPPDATA", "") or ""
    if not base or not os.path.isdir(base):
        return []
    paths = []
    try:
        names = os.listdir(base)
    except OSError:
        return []
    safe_exts = (".exe", ".nupkg", ".zip", ".log", ".txt", ".json", ".yaml")
    for name in names:
        if "-updater" not in name.lower():
            continue
        root = os.path.join(base, name)
        if not os.path.isdir(root):
            continue
        pend = os.path.join(root, "pending")
        if os.path.isdir(pend):
            paths.append(pend)
            continue
        try:
            entries = os.listdir(root)
        except OSError:
            continue
        if entries and all(f.lower().endswith(safe_exts) for f in entries):
            paths.append(root)
    return paths


def build_rules():
    """构造完整规则表：[{id, name, cat, paths:[...], risk}]。paths 为具体目录。"""
    rules = []

    # 1) Chromium 系
    for app_name, userdata in CHROMIUM_USERDATA:
        if not userdata or not os.path.isdir(userdata):
            continue
        paths = []
        for sub, _desc in CHROMIUM_ROOT_SUBDIRS:
            p = os.path.join(userdata, sub)
            if os.path.isdir(p):
                paths.append(p)
        for pname, pdir in _profile_dirs(userdata):
            for sub, _desc in CHROMIUM_SUBDIRS:
                p = os.path.join(pdir, sub)
                if os.path.isdir(p):
                    paths.append(p)
        if paths:
            rules.append({
                "id": "chromium_" + app_name.replace(" ", "_"),
                "name": f"{app_name} 深度缓存",
                "cat": "chromium",
                "paths": paths,
                "risk": "safe",
                "desc": "网页/JS/GPU/ServiceWorker 缓存，清理后不影响密码、书签与登录态。",
            })

    # 2) Electron / CEF 应用
    for disp, base, rel in ELECTRON_APPS:
        if not base:
            continue
        root = os.path.join(base, rel)
        if not os.path.isdir(root):
            continue
        paths = []
        for sub in ELECTRON_CACHE_SUBDIRS:
            p = os.path.join(root, sub)
            if os.path.isdir(p):
                paths.append(p)
        if not paths:
            # 应用存在但无已知缓存子目录：给它自身目录下的常见缓存（一层）
            try:
                for name in os.listdir(root):
                    if name.lower() in ("gpucache", "code cache", "cache", "logs", "crashpad"):
                        p = os.path.join(root, name)
                        if os.path.isdir(p):
                            paths.append(p)
            except Exception:
                pass
        if paths:
            rules.append({
                "id": "electron_" + disp.replace(" ", "_").replace(".", "_"),
                "name": f"{disp} 应用缓存",
                "cat": "electron",
                "paths": paths,
                "risk": "safe",
                "desc": "应用渲染缓存与日志，不影响账号与用户文件。",
            })

    # 3) 开发缓存
    for disp, p in DEV_CACHE:
        if p and os.path.isdir(p):
            rules.append({
                "id": "dev_" + disp.replace(" ", "_"),
                "name": disp,
                "cat": "dev",
                "paths": [p],
                "risk": "safe",
                "desc": "包管理/构建缓存，清理后首次构建会重新生成。",
            })

    # 4) 系统缓存
    for disp, p in SYSTEM_CACHE:
        if p and os.path.exists(p) and not is_protected_path(p):
            rules.append({
                "id": "sys_" + disp.replace(" ", "_"),
                "name": disp,
                "cat": "system",
                "paths": [p],
                "risk": "safe",
                "desc": "系统级缓存，由 Windows 自动重建。",
            })

    # 5) 游戏缓存
    for disp, p in GAME_CACHE:
        if p and os.path.isdir(p):
            rules.append({
                "id": "game_" + disp.replace(" ", "_"),
                "name": disp,
                "cat": "game",
                "paths": [p],
                "risk": "safe",
                "desc": "游戏平台缓存，不影响已安装游戏与存档。",
            })
    # 5.5) 手动确认档：体积大 / 删了需重新下载，默认不勾选
    for disp, p, desc in MANUAL_CACHE:
        if p and os.path.isdir(p) and not is_protected_path(p):
            rules.append({
                "id": "manual_" + disp.replace(" ", "_").replace("(", "_"),
                "name": "⚠ " + disp,
                "cat": "manual",
                "paths": [p],
                "risk": "manual",
                "desc": desc,
            })
    # 6) 通配发现（覆盖硬编码名单之外的应用）
    rules += discover_electron_caches()
    # 6.5) 应用更新残留缓存（*-updater）与 Office 升级包
    up_paths = discover_updater_caches()
    office_paths = [q for q in (
        "C:" + BS + "Program Files (x86)" + BS + "Microsoft Office" + BS + "Updates" + BS + "Download",
        "C:" + BS + "Program Files" + BS + "Microsoft Office" + BS + "Updates" + BS + "Download",
    ) if os.path.isdir(q)]
    if up_paths or office_paths:
        rules.append({
            "id": "sys_app_updater_caches",
            "name": "应用更新残留缓存与升级包",
            "cat": "system",
            "paths": up_paths + office_paths,
            "risk": "safe",
            "desc": "应用自动更新下载的安装包与 Office 升级包，删除不影响已安装版本。",
        })

    # 去重：同一路径被多条规则命中时只保留第一条（父子套叠防重复计数）
    seen = set()
    deduped = []
    for r in rules:
        keep = []
        for p in r["paths"]:
            key = os.path.abspath(p).lower().rstrip("\\/")
            if key in seen:
                continue
            seen.add(key)
            keep.append(p)
        if keep:
            r["paths"] = keep
            deduped.append(r)
    return deduped


def is_reparse_point(path):
    """重解析点（junction / 符号链接）判定。

    AppData 下存在 %L%\\Application Data -> %L%、%R%\\Roaming 等重解析点，
    跟随它们会导致体积重复统计、规则串到其他根目录。**一律不跟随**。
    """
    try:
        import ctypes
        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        return bool(attrs != 0xFFFFFFFF and attrs & FILE_ATTRIBUTE_REPARSE_POINT)
    except Exception:
        return False


def stat_path(path, protected_check=True):
    """统计一个目录：体积 / 文件数 / 最近修改。只读，不删除。"""
    total = 0
    count = 0
    newest = 0
    try:
        for root, dirs, files in os.walk(path):
            # 目录级免疫：命中保护关键字的子树直接剪掉
            if protected_check and is_protected_path(root):
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs
                       if not (protected_check and is_protected_path(os.path.join(root, d)))
                       and not is_reparse_point(os.path.join(root, d))]
            for f in files:
                fp = os.path.join(root, f)
                if protected_check and is_protected_path(fp):
                    continue
                try:
                    st = os.stat(fp)
                except Exception:
                    continue
                total += st.st_size
                count += 1
                if st.st_mtime > newest:
                    newest = st.st_mtime
    except Exception:
        pass
    return {"size": total, "files": count, "mtime": newest}


# ----------------------------------------------------------------------
# 大文件安全分级
# ----------------------------------------------------------------------
# 明确「删了会坏」的：属于程序本体/依赖/模型，绝不推荐
def _bs(text):
    """把 / 写法转成路径分隔符（运行时转换，源码零转义）。"""
    return text.replace("/", chr(92))


LARGE_UNSAFE_FRAGMENTS = tuple(_bs(x) for x in (
    "/site-packages/", "/node_modules/", "/dist-info/", "/.venv/",
    "/venv/", "/python/python", "/programs/ollama/lib/", "/miniconda",
    "/anaconda", "/jdk", "/jre/", "/microsoft/windows/", "/windows/",
    "/program files", "/packages/", "/wsl/", "/.ollama/models",
    "/huggingface/hub", "/ms-playwright", "/jetbrains/", "/android/sdk",
    "/gradle/wrapper", "/.m2/repository", "/.cargo/registry", "/.nuget/",
    "/componentstore/", "/cwd_global/", "/applicationplugins/",
    "/unrealengine/", "/sogoupy/models/", "/office6/backup/",
    "/provenancedata/", "/crx_cache/", "/app.asar", "/qqguild/",
    "/motion graphics templates/", "/im/file/", "/wwmapp/", "/tbs/",
    "/support/plugins/", "/bin/",
    "/sdk_storage/", "/modelzoo/", ".bak-",
))
# 明确「可安全删」的：缓存/日志/转储/更新残留/临时
LARGE_SAFE_FRAGMENTS = tuple(_bs(x) for x in (
    "/cache/", "/logs/", "/log/", "/temp/", "/tmp/", "/crash",
    "updates_v2", "/crashdumps/", "/dumps/", "-updater/pending",
    "/thumbcache", "/iconcache", "/d3dscache/", "/dxcache/",
    "/vmcache", "/cachedextensionvsixs", "-updater", "/env-kit/",
    "/user data/updates/", "/component_crx_cache/",
))
# 文件名级精确判级（组件 DLL = 程序本体；安装器 = 可重下缓存）
LARGE_UNSAFE_FILENAMES = ("chrome.dll", "libcef.dll", "flue.dll", "unins000.dat")
LARGE_SAFE_FILENAMES = ("installer.exe",)

LARGE_SAFE_EXTS = {".msi", ".cache",
    ".log", ".dmp", ".tmp", ".log.txt", ".etl", ".old", ".bak.tmp",
}


def grade_large_file(path):
    """大文件安全分级 -> 'safe' | 'unsafe' | 'unknown'。

    只有 safe 才允许勾选/推荐；unsafe 一律不可选（删了会破坏程序本体、
    依赖、模型或系统）；unknown 列为「需自行判断」，默认不勾选。
    """
    low = path.lower()
    if is_protected_path(path):
        return "unsafe"
    base = os.path.basename(low)
    for fn in LARGE_UNSAFE_FILENAMES:
        if base == fn:
            return "unsafe"
    for fn in LARGE_SAFE_FILENAMES:
        if base == fn:
            return "safe"
    if low.endswith(".exe"):
        return "unsafe"          # AppData 下的大 exe 默认是程序本体
    for frag in LARGE_UNSAFE_FRAGMENTS:
        if frag in low:
            return "unsafe"
    ext = os.path.splitext(low)[1]
    for frag in LARGE_SAFE_FRAGMENTS:
        if frag in low:
            return "safe"
    if ext in LARGE_SAFE_EXTS:
        return "safe"
    return "unknown"


def scan_roots():
    """可扫描的根目录（不止 AppData）。"""
    roots = []
    for p in (LOCAL, ROAM, LOW):
        if p and os.path.isdir(p):
            roots.append(p)
    # 用户主目录下的常见缓存/下载（不含 Documents 等用户文件区）
    # 注意：不要加 HOME\AppData —— 它已是 Local/Roaming/LocalLow 的父目录，
    # 加进来会把子目录再扫一遍（重复计数）。
    for sub in ("Downloads", ".cache"):
        p = os.path.join(HOME, sub)
        if os.path.isdir(p) and p not in roots:
            roots.append(p)
    return roots


def find_large_files(roots, min_mb=100, limit=60, on_progress=None):
    """发现 AppData 下的大文件（供用户手动确认）。只读。"""
    threshold = min_mb * 1024 * 1024
    found = []
    seen = 0
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        try:
            for cur, dirs, files in os.walk(root):
                if is_protected_path(cur):
                    dirs[:] = []
                    continue
                dirs[:] = [d for d in dirs
                           if not is_protected_path(os.path.join(cur, d))
                           and not is_reparse_point(os.path.join(cur, d))]
                for f in files:
                    fp = os.path.join(cur, f)
                    seen += 1
                    if on_progress and seen % 400 == 0:
                        on_progress(seen)
                    if is_protected_path(fp):
                        continue
                    try:
                        st = os.stat(fp)
                    except Exception:
                        continue
                    if st.st_size >= threshold:
                        grade = grade_large_file(fp)
                        found.append({
                            "path": fp, "size": st.st_size, "mtime": st.st_mtime,
                            "grade": grade,
                        })
        except Exception:
            pass
    # 排序：可安全删的在前 + 体积降序
    rank = {"safe": 0, "unknown": 1, "unsafe": 2}
    found.sort(key=lambda x: (rank.get(x["grade"], 1), -x["size"]))
    return found[:limit]


def scan_rules_stream(rules, emit=None):
    """流式扫描：每扫完一条规则就通过 emit(item) 上抛结果。

    与 scan_rules 的区别：不等全部扫完，扫到有体积的项立即回调，
    让 UI 边扫边显示（用户对「扫描中列表空白」的反馈）。
    """
    for rule in rules:
        size = 0
        files = 0
        newest = 0
        per_path = []
        for p in rule["paths"]:
            s = stat_path(p)
            if s["files"]:
                per_path.append({"path": p, "size": s["size"], "files": s["files"]})
                size += s["size"]
                files += s["files"]
                newest = max(newest, s["mtime"])
        if size > 0 and emit:
            emit({
                "id": rule["id"],
                "name": rule["name"],
                "cat": rule["cat"],
                "cat_name": CATEGORY_OF.get(rule["cat"], "其他"),
                "size": size,
                "files": files,
                "mtime": newest,
                "risk": rule["risk"],
                "desc": rule.get("desc", ""),
                "paths": per_path,
            })
        yield rule["name"]


def scan_rules(rules, on_progress=None):
    """按规则统计体积，返回按体积降序的结果列表。只读。"""
    out = []
    for idx, rule in enumerate(rules):
        size = 0
        files = 0
        newest = 0
        per_path = []
        for p in rule["paths"]:
            s = stat_path(p)
            if s["files"]:
                per_path.append({"path": p, "size": s["size"], "files": s["files"]})
                size += s["size"]
                files += s["files"]
                newest = max(newest, s["mtime"])
        if size > 0:
            out.append({
                "id": rule["id"],
                "name": rule["name"],
                "cat": rule["cat"],
                "cat_name": CATEGORY_OF.get(rule["cat"], "其他"),
                "size": size,
                "files": files,
                "mtime": newest,
                "risk": rule["risk"],
                "desc": rule.get("desc", ""),
                "paths": per_path,
            })
        if on_progress:
            on_progress(idx + 1, len(rules), rule["name"])
    out.sort(key=lambda x: x["size"], reverse=True)
    return out

# ----------------------------------------------------------------------
# 并入主界面两条扫描线（安全扫描 / 深度扫描）
# ----------------------------------------------------------------------
CAT_TYPE = {"chromium": "system", "electron": "app", "dev": "dev",
            "system": "system", "game": "app", "manual": "system"}
CAT_ICON = {"chromium": "🌐", "electron": "⚡", "dev": "💻",
            "system": "⚙️", "game": "🎮", "manual": "⚠️", "ai": "🤖"}


def to_apps():
    """把清理规则转换为主界面的清理项（按风险等级分流）。

    risk="safe"   → 安全扫描线（默认勾选，放心清理）
    risk="manual" → 深度扫描线（默认不勾选，清理前有确认流）
    """
    apps = []
    seen = set()
    for r in build_rules():
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        manual = r.get("risk") == "manual"
        apps.append({
            "id": "dc_" + r["id"],
            "name": r["name"],
            "paths": list(r["paths"]),
            "icon": CAT_ICON.get(r["cat"], "🧩"),
            "immune": False,
            "type": CAT_TYPE.get(r["cat"], "system"),
            "risk_level": "risk" if manual else "safe",
            "risk_desc": r.get("desc", "只清理可再生缓存，不影响账号与数据。"),
        })
    # 360 痕迹规则库（Directory/File 类，默认不勾选，确认后清理）
    try:
        import trace_rules_360
        apps += trace_rules_360.build_trace_apps()
    except RulePackError:
        raise
    except Exception:
        pass
    return apps
