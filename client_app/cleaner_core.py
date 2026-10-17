import os
import sys
import shutil
import stat
import time
import glob
import winreg
import ctypes
import string
from secure_rules import RulePackError

class SHQUERYRBINFO(ctypes.Structure):
    _fields_ = [
        ('cbSize', ctypes.c_uint32),
        ('i64Size', ctypes.c_int64),
        ('i64NumItems', ctypes.c_int64)
    ]

def get_recycle_bin_size():
    try:
        info = SHQUERYRBINFO()
        info.cbSize = ctypes.sizeof(SHQUERYRBINFO)
        res = ctypes.windll.shell32.SHQueryRecycleBinW(None, ctypes.byref(info))
        if res == 0:
            return info.i64Size
    except Exception:
        pass
    return 0

def empty_recycle_bin():
    try:
        # 7 = SHERB_NOCONFIRMATION | SHERB_NOPROGRESSUI | SHERB_NOSOUND
        res = ctypes.windll.shell32.SHEmptyRecycleBinW(None, None, 7)
        return res == 0
    except Exception:
        return False

def get_size(path, max_files=15000, max_time=1.0):
    total = 0
    try:
        if not os.path.exists(path): return 0
        if os.path.isfile(path):
            return os.path.getsize(path)
        stack = [path]
        file_count = 0
        start_time = time.time()
        while stack:
            if file_count > max_files or (time.time() - start_time) > max_time:
                break
            curr = stack.pop()
            try:
                for entry in os.scandir(curr):
                    if entry.is_file(follow_symlinks=False):
                        total += entry.stat(follow_symlinks=False).st_size
                        file_count += 1
                    elif entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
            except:
                pass
    except:
        pass
    return total

def format_size(bytes_size):
    if bytes_size <= 0:
        return "0.00 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024

def obfuscate_path(path):
    parts = path.split(os.sep)
    if len(parts) > 3:
        return f"{parts[0]}\\{os.sep}***{os.sep}{parts[-2]}{os.sep}{parts[-1]}"
    return path

def remove_readonly(func, path, excinfo):
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except: pass

# ======================================================================
# Agent Memory 免疫网 —— 硬编码白名单，任何清理规则都不得覆盖
#
# 背景（重要）：BleachBit 的 cleaners/claude.xml 等规则会清理
#   ~/.claude/{projects,sessions,file-history,shell-snapshots}
#   %APPDATA%\Cursor 与 Windsurf 下的 User/History、CachedData
# 这些正是 AI Agent 的对话记忆与工作上下文。若按第三方规则库扩充清理项，
# 很容易误删开发者赖以生存的上下文。
#
# 因此这里建立一层"不可被规则覆盖"的兜底：clean_directory 在删除前
# 一律先检查该路径是否落在免疫网内，命中即跳过。
# ======================================================================
def _build_agent_memory_whitelist():
    """构造 AI Agent 记忆目录白名单（小写、规范化，便于前缀匹配）。"""
    paths = []
    home = os.path.expanduser("~")
    roaming = os.path.join(home, "AppData", "Roaming")
    local = os.path.join(home, "AppData", "Local")

    # Claude Code / Claude Desktop 的对话记忆与项目上下文
    for sub in ("projects", "sessions", "session-env", "file-history",
                "shell-snapshots", "statsig", "todos"):
        paths.append(os.path.join(home, ".claude", sub))
    paths.append(os.path.join(home, ".claude"))
    paths.append(os.path.join(roaming, "Claude"))

    # Gemini / Antigravity Agent 记忆
    paths.append(os.path.join(home, ".gemini"))
    paths.append(os.path.join(home, ".gemini", "antigravity"))

    # OpenAI Codex
    paths.append(os.path.join(home, ".codex"))
    paths.append(os.path.join(roaming, "OpenAI", "Codex"))

    # 其他 AI 编辑器（记忆/历史目录）—— VSCode 家族全集（含国产 AI IDE）
    for editor in ("Cursor", "Code", "Windsurf", "Trae CN", "TRAE SOLO CN",
                   "Trae", "Qoder", "Lingma", "CodeBuddy CN", "Comate",
                   "Antigravity", "Antigravity IDE", "WorkBuddy", "MiniMax",
                   "VSCodium", "Kiro", "Void"):
        base = os.path.join(roaming, editor)
        paths.append(os.path.join(base, "User", "History"))
        paths.append(os.path.join(base, "User", "workspaceStorage"))
        paths.append(os.path.join(base, "User", "globalStorage"))

    # AI CLI / Agent 的家目录记忆（与 migrate_core._DOT_AGENT_DIRS 同源；
    # 刻意不复用 import 以免清理核心反向依赖迁移模块）
    for dot in (".antigravity", ".antigravity-ide", ".antigravity_cockpit",
                ".antigravity_tools", ".cline", ".codebuddy", ".codebuddycn",
                ".codeium", ".comate", ".comate-engine", ".continue",
                ".copilot", ".cursor", ".devin", ".devin-shared", ".factory",
                ".kimi-work", ".kimi-webbridge", ".kiro", ".kilocode",
                ".lingma", ".minimax", ".minimax-agent-cn", ".neovate",
                ".openhands", ".opencode-browser", ".qoder", ".qoder-cli",
                ".qoder-cn", ".qwen", ".qwenworkcn", ".roo", ".trae",
                ".trae-aicc", ".trae-cn", ".windsurf", ".workbuddy",
                ".zencoder", ".mavis", ".hermes", ".ai_completion",
                ".codex-gpt", ".clawdbot", ".modlens"):
        paths.append(os.path.join(home, *dot.split("/")))
    paths.append(os.path.join(home, ".config", "opencode"))

    # ZCode 桌面版会话数据（Roaming\ZCode 整体是会话存储）
    paths.append(os.path.join(roaming, "ZCode"))

    # 归一化：小写 + abspath，去掉结尾分隔符
    normed = []
    for p in paths:
        try:
            normed.append(os.path.abspath(p).lower().rstrip("\\/"))
        except Exception:
            pass
    return normed


# 模块加载时构造一次，避免每次删除都重算
AGENT_MEMORY_WHITELIST = _build_agent_memory_whitelist()


def is_agent_memory_path(path):
    """判断路径是否位于 Agent 记忆免疫网内（含其子目录）。"""
    try:
        p = os.path.abspath(path).lower().rstrip("\\/")
    except Exception:
        return False
    for w in AGENT_MEMORY_WHITELIST:
        if p == w or p.startswith(w + os.sep) or p.startswith(w + "/"):
            return True
    return False


def get_registry_value(root, subkey, name):
    try:
        key = winreg.OpenKey(root, subkey, 0, winreg.KEY_READ)
        value, _ = winreg.QueryValueEx(key, name)
        winreg.CloseKey(key)
        return value
    except Exception:
        return None

def get_documents_path():
    reg_doc = get_registry_value(
        winreg.HKEY_CURRENT_USER,
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        "Personal"
    )
    if reg_doc and os.path.exists(reg_doc):
        return reg_doc
    return os.path.join(os.path.expanduser("~"), "Documents")

def get_wechat_path():
    wechat_save_path = get_registry_value(
        winreg.HKEY_CURRENT_USER,
        r"Software\Tencent\WeChat",
        "FileSavePath"
    )
    if wechat_save_path:
        if wechat_save_path == "MyDocuments:":
            return os.path.join(get_documents_path(), "WeChat Files")
        if wechat_save_path.startswith("MyDocuments:"):
            suffix = wechat_save_path.replace("MyDocuments:", "").strip("\\/")
            return os.path.join(get_documents_path(), suffix)
        if os.path.exists(wechat_save_path):
            return wechat_save_path
    return os.path.join(os.path.expanduser("~"), "Documents", "WeChat Files")

def get_qq_path():
    return os.path.join(get_documents_path(), "Tencent Files")

def get_wecom_path():
    return os.path.join(get_documents_path(), "WXWork")

def get_logical_drives():
    drives = []
    try:
        bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for letter in string.ascii_uppercase:
            if bitmask & 1:
                drives.append(f"{letter}:\\")
            bitmask >>= 1
    except Exception:
        drives = ["C:\\"]
    return drives

def get_app_drives(app):
    """Return the set of drive letters (e.g. {'C', 'D'}) that this app's paths reside on."""
    drives = set()
    for p in app.get("paths", []):
        if p.startswith("custom:"):
            drives.add("C")  # recyclebin is system-level
            continue
        # Resolve environment variables and normalize
        expanded = os.path.expandvars(os.path.expanduser(p))
        if len(expanded) >= 2 and expanded[1] == ':':
            drives.add(expanded[0].upper())
    return drives

def get_adobe_common_paths():
    drives = get_logical_drives()
    paths = []
    user_home = os.path.expanduser("~")
    appdata_roaming = os.path.join(user_home, 'AppData', 'Roaming')
    
    paths.append(os.path.join(appdata_roaming, "Adobe", "Common", "Media Cache Files", "*"))
    paths.append(os.path.join(appdata_roaming, "Adobe", "Common", "Peak Files", "*"))
    paths.append(os.path.join(appdata_roaming, "Adobe", "Common", "Media Cache", "*"))
    
    for drive in drives:
        if drive.lower() != "c:\\":
            paths.append(os.path.join(drive, "Adobe", "Common", "Media Cache Files", "*"))
            paths.append(os.path.join(drive, "Adobe", "Common", "Peak Files", "*"))
            paths.append(os.path.join(drive, "Media Cache", "*"))
            paths.append(os.path.join(drive, "AdobeTemp", "*"))
    return paths

def get_d_drive_paths():
    drives = get_logical_drives()
    paths = []
    # v3.9.13 安全加固：非系统盘**只登记已知的厂商缓存目录**。
    #
    # 此前用 {d}Temp\* / {d}Tmp\* / {d}Downloads\* / {d}下载\* / {d}Documents\*
    # 这类「盘根目录通配」会把用户**自建的私人目录**当成垃圾：
    #   实测本机 F:\Temp 实为 997 GB 的私人媒体库，却被计入可清理范围。
    # 盘根目录通配一律移除；以下是明确由对应程序产生的缓存目录
    # （且必须真实存在才登记），删除它们不影响任何用户文件。
    KNOWN_CACHE_DIRS = [
        ("AdobeTemp", "Adobe 媒体缓存 (%sAdobeTemp)"),
        ("Adobe\\Common\\Media Cache Files", "Adobe 媒体缓存文件 (%s)"),
        ("SteamLibrary\\steamapps\\downloading", "Steam 下载缓存 (%s)"),
        ("SteamLibrary\\steamapps\\temp", "Steam 临时文件 (%s)"),
        ("Steam\\steamapps\\downloading", "Steam 下载缓存 (%s)"),
        ("Steam\\steamapps\\temp", "Steam 临时文件 (%s)"),
        ("NVIDIA\\DXCache", "NVIDIA 着色器缓存 (%s)"),
        ("ProgramData\\Package Cache", "安装包缓存 (%s)"),
    ]
    for d in drives:
        if d.lower() == "c:\\":
            continue
        for rel, desc in KNOWN_CACHE_DIRS:
            full = os.path.join(d, rel)
            # 只登记真实存在且确实是缓存用途的目录
            if os.path.isdir(full):
                prefix = "" if "%s" not in desc else f"{d}{rel}"
                paths.append((os.path.join(full, "*"), desc % f"{d}{rel}"))
    return paths

def get_supported_apps():
    user_home = os.path.expanduser("~")
    appdata_roaming = os.path.join(user_home, 'AppData', 'Roaming')
    appdata_local = os.path.join(user_home, 'AppData', 'Local')
    
    wechat_dir = get_wechat_path()
    qq_dir = get_qq_path()
    wecom_dir = get_wecom_path()
    
    steam_paths = [
        "C:\\Program Files (x86)\\Steam\\steamapps\\downloading\\*",
        "C:\\Program Files (x86)\\Steam\\steamapps\\temp\\*",
        "C:\\Program Files (x86)\\Steam\\package\\*"
    ]
    for drive in get_logical_drives():
        if drive.lower() != "c:\\":
            download_dir = os.path.join(drive, "SteamLibrary", "steamapps", "downloading", "*")
            temp_dir = os.path.join(drive, "SteamLibrary", "steamapps", "temp", "*")
            if os.path.exists(os.path.dirname(download_dir)):
                steam_paths.append(download_dir)
            if os.path.exists(os.path.dirname(temp_dir)):
                steam_paths.append(temp_dir)
                
    apps = [
        # ==========================================
        # 安全清理类别 (Safe Clean)
        # ==========================================
        {
            "id": "googlechrome",
            "name": "Google Chrome 浏览器缓存与冗余历史",
            "paths": [
                os.path.join(appdata_local, "Google", "Chrome", "User Data", "Default", "Cache", "*"),
                os.path.join(appdata_local, "Google", "Chrome", "User Data", "Default", "Code Cache", "*"),
                os.path.join(appdata_local, "Google", "Chrome", "User Data", "Default", "GPUCache", "*")
            ],
            "icon": "🌐",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理浏览器网页缓存，安全无害，不影响已保存的密码或账号。"
        },
        {
            "id": "microsoftedge",
            "name": "Microsoft Edge 浏览器垃圾缓存",
            "paths": [
                os.path.join(appdata_local, "Microsoft", "Edge", "User Data", "Default", "Cache", "*"),
                os.path.join(appdata_local, "Microsoft", "Edge", "User Data", "Default", "Code Cache", "*"),
                os.path.join(appdata_local, "Microsoft", "Edge", "User Data", "Default", "GPUCache", "*")
            ],
            "icon": "🧭",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理 Edge 浏览器临时网页缓存，释放系统空间。"
        },
        {
            "id": "firefox",
            "name": "Mozilla Firefox 浏览器历史缓存",
            "paths": [
                os.path.join(appdata_local, "Mozilla", "Firefox", "Profiles", "*", "cache2", "*")
            ],
            "icon": "🦊",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理 Firefox 临时图片和脚本缓存。"
        },
        {
            "id": "windows_temp",
            "name": "Windows 系统垃圾与临时服务日志 (C:\\Windows\\Temp)",
            "paths": [
                os.path.join(appdata_local, "Temp", "*"),
                "C:\\Windows\\Temp\\*"
            ],
            "icon": "⚙️",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理 Windows 系统运行中产生的临时过渡文件、安装日志、解压包残余。"
        },
        {
            "id": "windows_wer",
            "name": "Windows 系统崩溃报告与 WER 诊断日志",
            "paths": [
                os.path.join(appdata_local, "Microsoft", "Windows", "WER", "ReportArchive", "*"),
                os.path.join(appdata_local, "Microsoft", "Windows", "WER", "ReportQueue", "*"),
                "C:\\ProgramData\\Microsoft\\Windows\\WER\\ReportArchive\\*",
                "C:\\ProgramData\\Microsoft\\Windows\\WER\\ReportQueue\\*"
            ],
            "icon": "📝",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理 Windows 系统软件崩溃后生成的诊断报告文件，无害。"
        },
        {
            "id": "windows_update",
            "name": "Windows Update 历史更新分发包缓存",
            "paths": [
                "C:\\Windows\\SoftwareDistribution\\Download\\*"
            ],
            "icon": "🔄",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理已安装完成的 Windows 历史更新包，释放大量系统盘空间。"
        },
        {
            "id": "pyinstaller_temp",
            "name": "PyInstaller EXE 孤立缓存目录 (_MEI)",
            "paths": [
                os.path.join(appdata_local, "Temp", "_MEI*")
            ],
            "icon": "📦",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理绿色单文件 EXE 程序强退后遗留在 Temp 里的庞大临时解压目录（已自动跳过当前程序正在运行的目录）。"
        },
        {
            "id": "pip_npm_cache",
            "name": "Python Pip & NPM 开发依赖包全局缓存",
            "paths": [
                os.path.join(appdata_local, "pip", "cache", "*"),
                os.path.join(appdata_local, "npm-cache", "*")
            ],
            "icon": "📦",
            "immune": False,
            "type": "dev",
            "risk_level": "safe",
            "risk_desc": "清理 npm 和 pip 安装依赖时下载的全局缓存压缩包，下次安装相同依赖时需重新联网下载。"
        },
        {
            "id": "vscode_cache",
            "name": "Visual Studio Code 编辑器运行与插件缓存",
            "paths": [
                os.path.join(appdata_roaming, "Code", "CachedData", "*"),
                os.path.join(appdata_roaming, "Code", "Cache", "*"),
                os.path.join(appdata_roaming, "Code", "CachedExtensionVSIXs", "*")
            ],
            "icon": "💻",
            "immune": False,
            "type": "dev",
            "risk_level": "safe",
            "risk_desc": "清理 VS Code 运行日志与插件临时扩展包缓存。"
        },
        {
            "id": "gpu_downloader",
            "name": "NVIDIA & AMD 显卡驱动冗余安装包",
            "paths": [
                "C:\\ProgramData\\NVIDIA Corporation\\Downloader\\*",
                "C:\\AMD\\*"
            ],
            "icon": "🎮",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理英伟达或超微半导体驱动更新后遗留在电脑中的巨大原始压缩安装包，清理后不影响当前显卡驱动运行。"
        },
        {
            "id": "wps_cache",
            "name": "WPS Office (金山) 临时文档与字体缓存",
            "paths": [
                os.path.join(appdata_roaming, "kingsoft", "office6", "cache", "*"),
                os.path.join(appdata_roaming, "kingsoft", "office6", "docerfonts", "*")
            ],
            "icon": "🏢",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理金山 WPS 的云字体、网络模板和临时运行缓存。"
        },
        {
            "id": "ime_cache",
            "name": "Microsoft IME 中文输入法临时日志",
            "paths": [
                os.path.join(appdata_roaming, "Microsoft", "InputMethod", "Chs", "*.tmp"),
                os.path.join(appdata_roaming, "Microsoft", "InputMethod", "Chs", "*.log")
            ],
            "icon": "✍️",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理微软拼音输入法产生的临时调试日志文件。"
        },
        {
            "id": "windows_shader_cache",
            "name": "Windows DirectX 与显卡着色器缓存",
            "paths": [
                os.path.join(appdata_local, "D3DSCache", "*"),
                os.path.join(appdata_local, "Microsoft", "DirectX", "ShaderCache", "*"),
                os.path.join(appdata_local, "NVIDIA", "DXCache", "*"),
                os.path.join(appdata_local, "NVIDIA", "GLCache", "*"),
                os.path.join(appdata_local, "AMD", "DxCache", "*")
            ],
            "icon": "🎮",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理系统与游戏显卡着色器编译缓存，安全无害，清理后再次运行游戏时会重新生成。"
        },
        {
            "id": "windows_delivery_optimization",
            "name": "Windows 传递优化 (Delivery Optimization) 缓存",
            "paths": [
                "C:\\Windows\\ServiceProfiles\\NetworkService\\AppData\\Local\\Microsoft\\Windows\\DeliveryOptimization\\Cache\\*"
            ],
            "icon": "🌐",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理用于网络邻居或广域网间加速更新分发的文件，安全无害。"
        },
        {
            "id": "windows_system_logs",
            "name": "Windows 系统组件安装、日志与备份文件 (CBS/DISM)",
            "paths": [
                "C:\\Windows\\Logs\\CBS\\*",
                "C:\\Windows\\Logs\\DISM\\*",
                "C:\\Windows\\System32\\LogFiles\\*",
                "C:\\Windows\\*.log",
                "C:\\Windows\\*.bak"
            ],
            "icon": "📝",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理 Windows 组件安装（如 CBS.log）和系统日志文件。这些日志有时会异常膨胀到数十GB。"
        },
        {
            "id": "windows_crash_dumps",
            "name": "Windows 系统蓝屏与应用崩溃转储文件 (Crash Dumps)",
            "paths": [
                "C:\\Windows\\Minidump\\*",
                "C:\\Windows\\MEMORY.DMP",
                os.path.join(appdata_local, "CrashDumps", "*")
            ],
            "icon": "💥",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理系统崩溃后产生的内存转储调试文件，占用空间巨大且对日常运行无害。"
        },
        {
            "id": "windows_live_kernel_reports",
            "name": "Windows 存活内核转储报告 (LiveKernelReports)",
            "paths": [
                "C:\\Windows\\LiveKernelReports\\*.dmp",
                "C:\\Windows\\LiveKernelReports\\*"
            ],
            "icon": "💥",
            "immune": False,
            "type": "system",
            "risk_level": "risk",
            "risk_desc": "警告：这是系统“假死/驱动无响应”时自动保存的内核转储（文件名如 "
                         "PoW32kWatchdog-*.dmp），单文件常达数 GB。删除不会影响电脑运行，"
                         "但会丢失分析上次卡死原因的唯一证据。若近期频繁卡顿，建议先备份再清理。"
        },
        {
            "id": "windows_setupapi_logs",
            "name": "Windows 驱动/应用安装归档日志 (setupapi)",
            "paths": [
                "C:\\Windows\\INF\\setupapi.app.*.log",
                "C:\\Windows\\INF\\setupapi.dev.*.log"
            ],
            "icon": "📝",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理设备安装后归档的 setupapi 日志（带日期戳的历史副本）。"
                         "当前正在写入的 setupapi.app.log / setupapi.dev.log 不在清理范围内。"
        },
        {
            "id": "windows_debug_logs",
            "name": "Windows 调试日志 (Debug)",
            "paths": [
                "C:\\Windows\\Debug\\*.log",
                "C:\\Windows\\Debug\\WIA\\*.log"
            ],
            "icon": "📝",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理 Windows 调试目录下的日志文件（如扫描仪/相机 WIA 追踪日志）。"
        },
        {
            "id": "windows_winsat_datastore",
            "name": "Windows 性能评估数据 (WinSAT)",
            "paths": [
                "C:\\Windows\\Performance\\WinSAT\\DataStore\\*.xml",
                "C:\\Windows\\Performance\\WinSAT\\DataStore\\*.log"
            ],
            "icon": "📊",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理系统性能评分（WinSAT）的历史评估记录与日志，"
                         "下次重新评估时会自动生成。"
        },
        {
            "id": "windows_inet_cache",
            "name": "Windows 网络缓存 (INetCache)",
            "paths": [os.path.join(appdata_local, "Microsoft", "Windows", "INetCache", "*")],
            "icon": "🌐",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理 WinINet/IE 框架的网络缓存（网页、图片、脚本残留），浏览器会按需重新下载。"
        },
        {
            "id": "windows_fonts_deleted",
            "name": "已卸载字体残留 (Fonts\\Deleted)",
            "paths": [os.path.join(appdata_local, "Microsoft", "Windows", "Fonts", "Deleted", "*")],
            "icon": "🔤",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理用户卸载字体后遗留的字体文件副本。"
                         "注意：系统字体目录 C:\\Windows\\Fonts 与用户已安装字体均受保护，不会被清理。"
        },
        {
            "id": "windows_driverstore_temp",
            "name": "驱动安装临时文件 (DriverStore\\Temp)",
            "paths": ["C:\\Windows\\System32\\DriverStore\\Temp\\*"],
            "icon": "🔌",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理驱动安装过程产生的临时文件。"
                         "注意：驱动仓库本体 DriverStore\\FileRepository 受保护——"
                         "其中的驱动即使看似陈旧也仍在被系统使用，删除会导致硬件失效。"
        },
        {
            "id": "adobe_uxp_webview_cache",
            "name": "Adobe UXP 插件网页缓存 (EBWebView)",
            # 实测本机结构为 UXP\PluginsStorage\<App>\<ver>\Internal（插件本体，X 级），
            # 不存在的 Shared\EBWebView 保留为兼容路径；保护闸门已拦截 Internal。
            "paths": [
                os.path.join(appdata_roaming, "Adobe", "UXP", "Shared", "EBWebView", "*"),
                os.path.join(appdata_roaming, "Adobe", "UXP", "*.log")
            ],
            "icon": "🧩",
            "immune": False,
            "type": "app",
            "risk_level": "safe",
            "risk_desc": "清理 UXP 插件平台的网页渲染缓存（约 70 MB）。"
                         "注意：UXP\\Internal 是插件本体，不会被清理。"
        },
        {
            "id": "nvidia_cef_cache",
            "name": "NVIDIA 内嵌浏览器缓存 (CefCache)",
            "paths": [os.path.join(appdata_local, "NVIDIA Corporation", "*", "CefCache", "*")],
            "icon": "🖥️",
            "immune": False,
            "type": "app",
            "risk_level": "safe",
            "risk_desc": "清理 NVIDIA app / Overlay 内嵌浏览器(CEF)的网页缓存（实测约 247 MB）。"
                         "账号登录态(NvAccount)、用户设置(NvBackend\\DAO)与驱动、DLSS 模型均不受影响。"
        },
        {
            "id": "nvidia_component_logs",
            "name": "NVIDIA 组件日志与遥测",
            "paths": [
                os.path.join(appdata_local, "NVIDIA Corporation", "NVIDIA app", "NvBackend", "backend.log*"),
                "C:\\ProgramData\\NVIDIA Corporation\\NVIDIA app\\Logs\\*",
                "C:\\ProgramData\\NVIDIA Corporation\\nvtopps\\nvlog.nvlgstg",
                "C:\\ProgramData\\NVIDIA Corporation\\nvtopps\\nvtopps.log*",
            ],
            "icon": "🖥️",
            "immune": False,
            "type": "app",
            "risk_level": "safe",
            "risk_desc": "清理 NVIDIA app 后端日志、安装日志与遥测日志（实测约 80 MB）。"
                         "驱动本体、3D 设置数据库(nvdrsdb)与 DLSS 模型不会被清理。"
        },
        {
            "id": "adobe_photoshop_logs",
            "name": "Adobe Photoshop 日志与字体缓存",
            "paths": [
                os.path.join(appdata_roaming, "Adobe", "Adobe Photoshop 2021", "Logs", "*"),
                os.path.join(appdata_roaming, "Adobe", "Adobe Photoshop 2021", "CT Font Cache", "*"),
                os.path.join(appdata_roaming, "Adobe", "Adobe Photoshop 2021", "FontFeatureCache", "*"),
                os.path.join(appdata_roaming, "Adobe", "Adobe Photoshop 2021", "sniffer-out*.txt"),
            ],
            "icon": "🎨",
            "immune": False,
            "type": "app",
            "risk_level": "safe",
            "risk_desc": "清理 Photoshop 运行日志、字体缓存与 GPU 嗅探日志（实测约 6 MB）。"
                         "你的预设(.psp)、动作、工作区、快捷键与自动保存均不会被清理。"
        },
        {
            "id": "autodesk_licensing_logs",
            "name": "Autodesk 许可服务日志",
            "paths": ["C:\\ProgramData\\Autodesk\\AdskLicensingService\\Log\\*"],
            "icon": "📝",
            "immune": False,
            "type": "app",
            "risk_level": "safe",
            "risk_desc": "清理 Autodesk 许可服务的运行日志（实测 2.6 MB）。"
                         "注意：许可文件本体与 CER 崩溃报告数据库不会被清理。"
        },
        {
            "id": "redgiant_logs",
            "name": "Red Giant 插件日志",
            "paths": [
                "C:\\ProgramData\\Red Giant\\Logs\\*.txt",
                "C:\\ProgramData\\RedGiant\\Logs\\*.txt"
            ],
            "icon": "📝",
            "immune": False,
            "type": "app",
            "risk_level": "safe",
            "risk_desc": "清理 Red Giant 系列插件的运行日志（约 105 KB）。插件本体与预设不会被清理。"
        },
        {
            "id": "adobe_media_analyzer_cache",
            "name": "Adobe 媒体/分析缓存 (Premiere & AE)",
            "paths": [
                os.path.join(appdata_roaming, "Adobe", "Common", "Media Cache Files", "*"),
                os.path.join(appdata_roaming, "Adobe", "Common", "Media Cache", "*"),
                os.path.join(appdata_roaming, "Adobe", "Common", "Peak Files", "*"),
                os.path.join(appdata_roaming, "Adobe", "Common", "Analyzer Cache Files", "*"),
                os.path.join(appdata_roaming, "Adobe", "Common", "Team Projects Cache", "*"),
                os.path.join(appdata_roaming, "Adobe", "Common", "Essential Sound", "*.pek"),
                os.path.join(appdata_roaming, "Adobe", "Common", "Essential Sound", "*.cfa"),
            ],
            "icon": "🎬",
            "immune": False,
            "type": "app",
            "risk_level": "safe",
            "risk_desc": "清理 Premiere Pro / After Effects 的媒体缓存、音频波形(.pek)与一致性分析(.cfa)。"
                         "这些是播放与预览用的临时数据，软件会在需要时自动重建；"
                         "不会删除你的项目文件、素材或动态图形模板(.mogrt)。"
        },
        {
            "id": "nvidia_driver_logs",
            "name": "NVIDIA 显卡驱动运行日志",
            "paths": [
                "C:\\ProgramData\\NVIDIA\\*.log",
                "C:\\ProgramData\\NVIDIA\\*_backup*",
                "C:\\ProgramData\\NVIDIA Corporation\\*.log",
                "C:\\ProgramData\\NVIDIA Corporation\\*_backup*"
            ],
            "icon": "🖥️",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理 NVIDIA 显示容器与驱动的运行日志及其轮转备份。"
                         "注意：DLSS/AI 模型目录（NGX\\models）不会被动到——"
                         "其中的模型文件仍可能被游戏调用。"
        },
        {
            "id": "windows_winsxs_temp",
            "name": "Windows 组件安装暂存区 (WinSxS\\Temp\\InFlight)",
            "paths": [
                "C:\\Windows\\WinSxS\\Temp\\InFlight\\*",
                "C:\\Windows\\WinSxS\\Temp\\PendingDeletes\\*"
            ],
            "icon": "🧩",
            "immune": False,
            "type": "system",
            "risk_level": "risk",
            "risk_desc": "警告：这是 Windows 组件安装(CBS)的暂存区，系统异常中断时会留下数 GB 孤儿文件"
                         "（本机实测 8.7GB）。若其中的安装仍在进行，删除会导致该次更新失败。"
                         "仅建议在 Windows Update 空闲、且提示“Windows 已是最新的”时清理；"
                         "更稳妥的做法是运行「磁盘清理」→「清理系统文件」→「Windows 更新清理」。"
        },
        {
            "id": "windows_wbem_logs",
            "name": "WMI 运行日志 (wbem\\Logs)",
            "paths": ["C:\\Windows\\System32\\wbem\\Logs\\*.log"],
            "icon": "📝",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理 WMI 提供程序的运行日志。"
                         "注意：WMI 存储库（wbem\\Repository）属于数据库，已受保护不会被清理。"
        },
        {
            "id": "windows_windowsupdate_logs",
            "name": "Windows 更新日志 (Logs\\WindowsUpdate)",
            "paths": [
                "C:\\Windows\\Logs\\WindowsUpdate\\*.log",
                "C:\\Windows\\Logs\\WindowsUpdate\\*.etl"
            ],
            "icon": "📝",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理 Windows Update 客户端的运行日志。"
                         "注意：SoftwareDistribution\\DataStore 是数据库，已受保护不会被清理。"
        },
        {
            "id": "windows_prefetch",
            "name": "Windows 预取与应用启动追踪数据库 (Prefetch)",
            "paths": [
                "C:\\Windows\\Prefetch\\*"
            ],
            "icon": "⚡",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理 Windows 为加快程序启动而缓存的索引数据。清理后系统会自动重新生成。"
        },
        {
            "id": "windows_thumbnail_cache",
            "name": "Windows 资源管理器图标与文件缩略图缓存",
            "paths": [
                os.path.join(appdata_local, "Microsoft", "Windows", "Explorer", "thumbcache_*.db"),
                os.path.join(appdata_local, "Microsoft", "Windows", "Explorer", "iconcache_*.db")
            ],
            "icon": "🖼️",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理图片、视频在文件夹中显示的预览图和图标缓存。清理后再次打开文件夹时会自动重绘。"
        },
        {
            "id": "recyclebin",
            "name": "Windows 系统回收站一键清空",
            "paths": [
                "custom:recyclebin"
            ],
            "icon": "🗑️",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "彻底清空 Windows 回收站中已删除的文件，彻底释放空间。"
        },
        {
            "id": "spotify_cache",
            "name": "Spotify 音乐播放器听歌与暂存缓存",
            "paths": [
                os.path.join(appdata_local, "Spotify", "Storage", "*")
            ],
            "icon": "🎵",
            "immune": False,
            "type": "app",
            "risk_level": "safe",
            "risk_desc": "清理 Spotify 播放音乐时在本地暂存的歌曲文件，清理后不会影响账户歌单，在线播放时会重新下载。"
        },
        {
            "id": "discord_cache",
            "name": "Discord 社交软件运行与媒体缓存",
            "paths": [
                os.path.join(appdata_roaming, "discord", "Cache", "*"),
                os.path.join(appdata_roaming, "discord", "Code Cache", "*")
            ],
            "icon": "💬",
            "immune": False,
            "type": "chat",
            "risk_level": "safe",
            "risk_desc": "清理 Discord 聊天和图片的本地运行缓存，不影响历史消息。"
        },
        {
            "id": "telegram_cache",
            "name": "Telegram 聊天软件本地缓存与媒体包",
            "paths": [
                os.path.join(appdata_roaming, "Telegram Desktop", "tdata", "user_data", "cache", "*"),
                os.path.join(appdata_roaming, "Telegram Desktop", "tdata", "user_data", "media_cache", "*")
            ],
            "icon": "✈️",
            "immune": False,
            "type": "chat",
            "risk_level": "safe",
            "risk_desc": "清理 Telegram 本地接收的图片和视频等媒体缓存文件，不影响云端对话记录，需要时可从云端重新拉取。"
        },
        {
            "id": "steam_downloads",
            "name": "Steam 游戏下载暂存与更新文件",
            "paths": steam_paths,
            "icon": "🎮",
            "immune": False,
            "type": "app",
            "risk_level": "safe",
            "risk_desc": "清理 Steam 下载或更新游戏时残留的临时分发包与暂存数据。建议在没有下载任务时运行。"
        },
        {
            "id": "windows_installer_patch_cache",
            "name": "Windows Installer 补丁备份与组件修复缓存 ($PatchCache$)",
            "paths": [
                "C:\\Windows\\Installer\\$PatchCache$\\*"
            ],
            "icon": "📦",
            "immune": False,
            "type": "system",
            "risk_level": "safe",
            "risk_desc": "清理 Windows 补丁安装后备份的冗余组件副本。清理后不影响当前系统或软件运行。"
        },
        {
            "id": "jetbrains_cache",
            "name": "JetBrains 系列 IDE (PyCharm/IntelliJ 等) 运行与本地索引缓存",
            "paths": [
                os.path.join(appdata_local, "JetBrains", "*", "caches", "*"),
                os.path.join(appdata_local, "JetBrains", "*", "index", "*"),
                os.path.join(appdata_local, "JetBrains", "*", "log", "*")
            ],
            "icon": "💻",
            "immune": False,
            "type": "dev",
            "risk_level": "safe",
            "risk_desc": "清理 PyCharm、IntelliJ IDEA 等编译运行时产生的索引和日志缓存，清理后再次打开项目时会自动重新建立。"
        },

        # ==========================================
        # 风险清理类别 (Risk Clean)
        # ==========================================
        {
            "id": "wechat",
            "name": "微信 (WeChat) 聊天图片与视频接收文件",
            "paths": [
                os.path.join(wechat_dir, "*")
            ],
            "icon": "💬",
            "immune": False,
            "type": "chat",
            "risk_level": "risk",
            "risk_desc": "警告：此操作将清理您的微信聊天记录中已下载的图片、视频和群文件附件，请务必提前备份！"
        },
        {
            "id": "wechat_web",
            "name": "微信内置网页与小程序缓存",
            "paths": [
                os.path.join(appdata_roaming, "Tencent", "WeChat", "radium", "web", "profiles", "*"),
                os.path.join(appdata_roaming, "Tencent", "xwechat", "radium", "web", "profiles", "*")
            ],
            "icon": "🌐",
            "immune": False,
            "type": "chat",
            "risk_level": "risk",
            "risk_desc": "清理微信内置浏览器网页缓存与小程序本地静态资源，不影响微信聊天记录。"
        },
        {
            "id": "qq",
            "name": "腾讯QQ (QQ) 历史接收文件与图片缓存",
            "paths": [
                os.path.join(qq_dir, "*")
            ],
            "icon": "🐧",
            "immune": False,
            "type": "chat",
            "risk_level": "risk",
            "risk_desc": "警告：此操作将清理 QQ 历史聊天中下载的群文件、图片等附件。"
        },
        {
            "id": "wecom",
            "name": "企业微信 (WeCom) 工作文档与图片缓存",
            "paths": [
                os.path.join(wecom_dir, "*")
            ],
            "icon": "🏢",
            "immune": False,
            "type": "chat",
            "risk_level": "risk",
            "risk_desc": "警告：此操作将清理企业微信已下载的历史图片和办公文件。"
        },
        {
            "id": "feishu",
            "name": "飞书 (Feishu) 多维表格与知识库本地附件",
            "paths": [
                os.path.join(appdata_local, "bytedance", "Feishu", "Cache", "*")
            ],
            "icon": "🕊️",
            "immune": False,
            "type": "chat",
            "risk_level": "risk",
            "risk_desc": "清理飞书本地下载的临时知识库及图片附件。"
        },
        {
            "id": "ollama",
            "name": "Ollama 本地大语言模型权重资产",
            "paths": [
                os.path.join(user_home, ".ollama", "models", "*")
            ],
            "icon": "🦙",
            "immune": False,
            "type": "ai",
            "risk_level": "risk",
            "risk_desc": "警告：此操作将彻底删除您在 Ollama 下载的所有本地模型权重（通常很大，删除后需要重新下载）！"
        },
        {
            "id": "huggingface",
            "name": "Hugging Face Model Hub 缓存模型",
            "paths": [
                os.path.join(user_home, ".cache", "huggingface", "hub", "*")
            ],
            "icon": "🤗",
            "immune": False,
            "type": "ai",
            "risk_level": "risk",
            "risk_desc": "警告：删除已下载的 Hugging Face 开源模型缓存，会导致再次运行时需要重新下载模型。"
        },
        {
            "id": "wps_backup_cache",
            "name": "WPS Office 历史自动备份与防丢临时文档",
            "paths": [
                os.path.join(appdata_roaming, "kingsoft", "office6", "backup", "*")
            ],
            "icon": "🏢",
            "immune": False,
            "type": "system",
            "risk_level": "risk",
            "risk_desc": "清理 WPS Office 编辑文档时在后台保存的历史防丢备份文件。建议在所有文档均已正常保存时进行清理。"
        },
        {
            "id": "wps_cloud_cache",
            "name": "WPS Office 云文档本地同步与缓存文件",
            "paths": [
                os.path.join(user_home, "Documents", "wps_cloud_user_files", "*")
            ],
            "icon": "☁️",
            "immune": False,
            "type": "chat",
            "risk_level": "risk",
            "risk_desc": "清理 WPS 云文档的本地同步与离线缓存数据。清理后，双击打开云文档时会自动从云端重新拉取最新版本，不影响您的云端文件安全。"
        },

        # ==========================================
        # Adobe 深度清理 (Adobe Suite Caches)
        # ==========================================
        {
            "id": "adobe_photoshop",
            "name": "Adobe Photoshop 暂存磁盘与自动恢复项",
            "paths": [
                os.path.join(appdata_roaming, "Adobe", "Adobe Photoshop*", "AutoRecover", "*"),
                os.path.join(appdata_local, "Adobe", "Adobe Photoshop*", "Caches", "*"),
                os.path.join(appdata_local, "Temp", "Adobe", "Photoshop", "*"),
                os.path.join(appdata_local, "Temp", "Photoshop Temp*")
            ],
            "icon": "🎨",
            "immune": False,
            "type": "adobe",
            "risk_level": "risk",
            "risk_desc": "清理 Photoshop 未保存的自动恢复备份文件和运行暂存文件（在软件崩掉或正在编辑时非常重要，清理前请关闭 Photoshop）。"
        },
        {
            "id": "adobe_premiere",
            "name": "Adobe Premiere & Media Encoder 视频剪辑渲染缓存",
            "paths": get_adobe_common_paths(),
            "icon": "🎬",
            "immune": False,
            "type": "adobe",
            "risk_level": "risk",
            "risk_desc": "清理 Premiere / Media Encoder 生成的视频代理渲染及峰值缓冲数据。删除后工程文件完好，但在 Premiere 中重新打开旧工程时需要重新生成波形图和峰值缓存文件（较耗CPU）。"
        },
        {
            "id": "adobe_aftereffects",
            "name": "Adobe After Effects 合成渲染与磁盘预览缓存",
            "paths": [
                os.path.join(appdata_local, "Adobe", "After Effects", "*", "Disk Cache", "*"),
                os.path.join(appdata_local, "Temp", "Adobe", "After Effects", "*")
            ],
            "icon": "💥",
            "immune": False,
            "type": "adobe",
            "risk_level": "risk",
            "risk_desc": "清理 After Effects 合成预览缓存文件（极占硬盘空间，删除后需在 AE 中重新渲染生成合成预览）。"
        },
        {
            "id": "adobe_illustrator",
            "name": "Adobe Illustrator 矢量设计图渲染缓存",
            "paths": [
                os.path.join(appdata_local, "Adobe", "Adobe Illustrator*", "Caches", "*"),
                os.path.join(appdata_local, "Temp", "Adobe", "Illustrator", "*")
            ],
            "icon": "📐",
            "immune": False,
            "type": "adobe",
            "risk_level": "risk",
            "risk_desc": "清理 Illustrator 运行时的临时渲染缓存。"
        },
        {
            "id": "adobe_lightroom",
            "name": "Adobe Lightroom 目录网格缩略图缓存",
            "paths": [
                os.path.join(appdata_local, "Adobe", "Lightroom", "Caches", "*")
            ],
            "icon": "📸",
            "immune": False,
            "type": "adobe",
            "risk_level": "risk",
            "risk_desc": "清理照片库缩略图渲染缓存，不影响照片源文件，但再次打开图库时需要重新生成照片缩略图。"
        },
        {
            "id": "adobe_acrobat",
            "name": "Adobe Acrobat PDF 阅读器缓存",
            "paths": [
                os.path.join(appdata_local, "Adobe", "Acrobat", "*", "Cache", "*"),
                os.path.join(appdata_local, "Adobe", "Acrobat", "*", "WebResources", "*")
            ],
            "icon": "📄",
            "immune": False,
            "type": "adobe",
            "risk_level": "risk",
            "risk_desc": "清理 PDF 阅读器的临时渲染缓存和网络服务临时数据。"
        },
        {
            "id": "adobe_bridge",
            "name": "Adobe Bridge 照片资源管理器索引缓存",
            "paths": [
                os.path.join(appdata_roaming, "Adobe", "Bridge*", "Cache", "*")
            ],
            "icon": "🌉",
            "immune": False,
            "type": "adobe",
            "risk_level": "risk",
            "risk_desc": "清理 Bridge 的快速图片索引缓存。"
        },
        {
            "id": "adobe_common",
            "name": "Adobe Common 公共服务及软件安装包日志",
            "paths": [
                os.path.join(appdata_local, "Adobe", "OOBE", "*"),
                os.path.join(appdata_local, "Adobe", "AAMUpdater", "*"),
                os.path.join(appdata_local, "Adobe", "webview2", "*"),
                os.path.join(appdata_roaming, "Adobe", "CRLogs", "*"),
                os.path.join(appdata_roaming, "Adobe", "Logs", "*")
            ],
            "icon": "⚙️",
            "immune": False,
            "type": "adobe",
            "risk_level": "safe",
            "risk_desc": "清理 Adobe 各软件安装、崩溃和自动更新的临时日志残余。"
        },

        # ==========================================
        # 免疫保护资产 (Immune Locked)
        # ==========================================
        {
            "id": "openaicodex",
            "name": "OpenAI Codex Agent Local Neural Core (安全锁定)",
            "paths": [
                os.path.join(user_home, ".codex", "*"),
                os.path.join(appdata_roaming, "OpenAI", "Codex", "*")
            ],
            "icon": "🤖",
            "immune": True,
            "type": "ai",
            "risk_level": "safe",
            "risk_desc": "OpenAI Codex 智能体本地运行核心与上下文脑图，受高级非擦除保护网安全锁死。"
        },
        {
            "id": "googlegemini",
            "name": "Antigravity AI Agent 记忆神经元池 (安全锁定)",
            "paths": [
                os.path.join(user_home, ".gemini", "antigravity", "*")
            ],
            "icon": "🧠",
            "immune": True,
            "type": "ai",
            "risk_level": "safe",
            "risk_desc": "Antigravity 专有免疫保护网，不允许任何清理操作触及此目录。"
        },
        {
            "id": "cursor",
            "name": "Cursor Editor 大模型上下文索引库 (安全锁定)",
            "paths": [
                os.path.join(appdata_roaming, "Cursor", "*")
            ],
            "icon": "🚀",
            "immune": True,
            "type": "ai",
            "risk_level": "safe",
            "risk_desc": "Cursor 编辑器记忆库受安全锁定保护。"
        },
        {
            "id": "claude",
            "name": "Claude Desktop 本地对话记忆数据库 (安全锁定)",
            "paths": [
                os.path.join(appdata_roaming, "Claude", "*")
            ],
            "icon": "🧙",
            "immune": True,
            "type": "ai",
            "risk_level": "safe",
            "risk_desc": "Claude 桌面版记忆库受安全锁定保护。"
        },
        # Office / Daily Apps
        {
            "id": "dingtalk",
            "name": "钉钉 (DingTalk) 协同办公运行缓存",
            "paths": [
                os.path.join(appdata_local, "DingTalk", "user_data", "*")
            ],
            "icon": "💬",
            "immune": False,
            "type": "chat",
            "risk_level": "safe",
            "risk_desc": "清理钉钉客户端运行缓存，释放日常办公临时垃圾，不影响聊天记录。"
        },
        {
            "id": "teams",
            "name": "Microsoft Teams 协同会议缓存",
            "paths": [
                os.path.join(appdata_local, "Microsoft", "Teams", "Cache", "*")
            ],
            "icon": "👥",
            "immune": False,
            "type": "chat",
            "risk_level": "safe",
            "risk_desc": "清理 Teams 会议及界面运行缓存，不影响历史消息与账号。"
        },
        {
            "id": "foxitreader",
            "name": "福昕阅读器 (Foxit PDF) 暂存缓存",
            "paths": [
                os.path.join(appdata_roaming, "Foxit Software", "Foxit PDF Reader", "Cache", "*")
            ],
            "icon": "📄",
            "immune": False,
            "type": "chat",
            "risk_level": "safe",
            "risk_desc": "清理福昕阅读器缓存的 PDF 历史渲染及界面文件。"
        },
        # Developers (Dev Tools)
        {
            "id": "gradle",
            "name": "Gradle 本地编译依赖库缓存 (~/.gradle)",
            "paths": [
                os.path.join(user_home, ".gradle", "caches", "*")
            ],
            "icon": "☕",
            "immune": False,
            "type": "dev",
            "risk_level": "risk",
            "risk_desc": "警告：将清空本地下载的外部 JAR 依赖包，构建项目时会自动重新联网下载。"
        },
        {
            "id": "nuget",
            "name": "NuGet 全局编译包依赖缓存 (~/.nuget)",
            "paths": [
                os.path.join(user_home, ".nuget", "packages", "*")
            ],
            "icon": "📦",
            "immune": False,
            "type": "dev",
            "risk_level": "risk",
            "risk_desc": "警告：将清空本地缓存的 .NET 程序包依赖，构建新项目时会重新下载。"
        },
        {
            "id": "cargo",
            "name": "Rust Cargo 本地编译库与注册表缓存",
            "paths": [
                os.path.join(user_home, ".cargo", "registry", "*"),
                os.path.join(user_home, ".cargo", "git", "*")
            ],
            "icon": "🦀",
            "immune": False,
            "type": "dev",
            "risk_level": "risk",
            "risk_desc": "警告：将清理 Rust 构建所需的本地 registry 源码包及 Git 缓存仓。"
        },
        {
            "id": "go_build_cache",
            "name": "Go Language 全局构建与编译缓冲",
            "paths": [
                os.path.join(appdata_local, "go-build", "*")
            ],
            "icon": "🐹",
            "immune": False,
            "type": "dev",
            "risk_level": "safe",
            "risk_desc": "清理 Go 语言在编译项目时产生的临时底层 `.a` 缓存，安全无害。"
        },
        {
            "id": "android_studio",
            "name": "Android Studio 索引与编译器系统缓存",
            "paths": [
                os.path.join(appdata_local, "Google", "AndroidStudio*", "caches", "*")
            ],
            "icon": "🤖",
            "immune": False,
            "type": "dev",
            "risk_level": "safe",
            "risk_desc": "清理 Android Studio 的本地开发运行时临时构建索引。"
        },
        # Designers (Designer Tools)
        {
            "id": "blender_cache",
            "name": "Blender 3D 渲染暂存与备份",
            "paths": [
                os.path.join(appdata_local, "Blender Foundation", "Blender", "*", "cache", "*")
            ],
            "icon": "🔶",
            "immune": False,
            "type": "adobe",
            "risk_level": "safe",
            "risk_desc": "清理 Blender 的自动备份与运行时暂存数据。"
        },
        {
            "id": "davinci_resolve",
            "name": "DaVinci Resolve 达芬奇视频剪辑缓存",
            "paths": [
                os.path.join(appdata_local, "Blackmagic Design", "DaVinci Resolve", "Cache", "*")
            ],
            "icon": "🎨",
            "immune": False,
            "type": "adobe",
            "risk_level": "risk",
            "risk_desc": "警告：将清理达芬奇剪辑视频时生成的预览代理文件，不影响源素材工程。"
        },
        {
            "id": "figma_cache",
            "name": "Figma Desktop UI 设计离线缓存",
            "paths": [
                os.path.join(appdata_local, "Figma", "Cache", "*")
            ],
            "icon": "❖",
            "immune": False,
            "type": "adobe",
            "risk_level": "safe",
            "risk_desc": "清理 Figma 客户端缓存的离线文档及历史缩略图，不影响云端工程安全。"
        },
        # Gamers
        {
            "id": "epic_games",
            "name": "Epic Games Launcher 客户端网页分发缓存",
            "paths": [
                os.path.join(appdata_local, "EpicGamesLauncher", "Saved", "webcache", "*")
            ],
            "icon": "🎮",
            "immune": False,
            "type": "app",
            "risk_level": "safe",
            "risk_desc": "清理 Epic 平台客户端的网页渲染与广告缓存。"
        },
        {
            "id": "ea_desktop",
            "name": "EA Desktop 游戏平台运行缓存",
            "paths": [
                os.path.join(appdata_local, "Electronic Arts", "EA Desktop", "cache", "*")
            ],
            "icon": "🎮",
            "immune": False,
            "type": "app",
            "risk_level": "safe",
            "risk_desc": "清理 EA 平台的本地运行垃圾与缩略图。"
        }
    ]
    
    # Dynamic non-system partition path discovery
    for path, desc in get_d_drive_paths():
        resolved = get_resolved_paths([path])
        if resolved:
            is_chat_or_doc = any(k in desc for k in ["微信", "QQ", "企业微信", "WXWork", "WPS"])
            apps.append({
                "id": f"d_drive_{hash(path) & 0xffffffff}",
                "name": desc,
                "paths": [path],
                "icon": "💾",
                "immune": False,
                "type": "chat" if is_chat_or_doc else "system",
                "risk_level": "risk",  # Force risk level to 'risk' to prevent default check and clean
                "risk_desc": f"警告：此目录位于非系统盘，为用户自建中转站或下载区（非系统自动生成）。默认取消勾选以保障您的个人文档安全，建议点击[查看文件]确认后再手动勾选清理。"
            })
            
    # ==========================================================
    # 合并外部规则库 (cleaner_rules.py)
    #
    # 新增清理项统一放在 cleaner_rules.py；正式版本由原生编译流程保护。
    # 规则库自带存在性过滤，未安装的软件不会出现。
    # ==========================================================
    try:
        from cleaner_rules import get_extra_apps
        existing_ids = {a.get("id") for a in apps}
        for extra in get_extra_apps():
            if extra.get("id") in existing_ids:
                continue
            apps.append(extra)
    except RulePackError:
        raise
    except Exception:
        pass

    # ==========================================================
    # 合并 AppData 深度缓存规则（原独立"深度优化台"已并入两条扫描线）
    # safe 规则 → 安全扫描线；manual 大件 → 深度扫描线（默认不勾选）
    # ==========================================================
    try:
        import deep_cache
        existing_ids = {a.get("id") for a in apps}
        for extra in deep_cache.to_apps():
            if extra["id"] in existing_ids:
                continue
            apps.append(extra)
    except RulePackError:
        raise
    except Exception:
        pass

    # ==========================================================
    # 合并外部规则库（Winapp2 / BleachBit / Dism++ / 腾讯管家路径）
    # 与既有规则按规范化路径去重，避免同一缓存重复计数
    # ==========================================================
    try:
        import rules_extra
        seen_paths = set()
        for a in apps:
            for pp in a.get("paths", []):
                seen_paths.add(os.path.normcase(os.path.normpath(str(pp))))
        existing_ids = {a.get("id") for a in apps}
        for extra in rules_extra.build_apps(seen=seen_paths):
            if extra["id"] in existing_ids:
                continue
            existing_ids.add(extra["id"])
            apps.append(extra)
    except RulePackError:
        raise
    except Exception:
        pass

    return apps

def get_resolved_paths(paths):
    resolved = []
    for p in paths:
        if p.startswith("custom:"):
            resolved.append(p)
            continue
        try:
            matches = glob.glob(p)
            resolved.extend(matches)
        except Exception:
            pass
    return list(set(resolved))

def get_app_size(app):
    total = 0
    our_meipass = getattr(sys, '_MEIPASS', None)
    if our_meipass:
        our_meipass = os.path.abspath(our_meipass).lower()
        
    resolved_paths = get_resolved_paths(app.get("paths", []))
    for p in resolved_paths:
        if p == "custom:recyclebin":
            total += get_recycle_bin_size()
            continue
        if our_meipass and our_meipass in os.path.abspath(p).lower():
            continue
        total += get_size(p)
    return total

def scan_app_files(app, limit=200):
    if app["id"] == "recyclebin":
        size = get_recycle_bin_size()
        if size > 0:
            return [("Windows 系统回收站已暂存的文件", size)]
        return []

    files_list = []
    our_meipass = getattr(sys, '_MEIPASS', None)
    if our_meipass:
        our_meipass = os.path.abspath(our_meipass).lower()
        
    resolved_paths = get_resolved_paths(app.get("paths", []))
    for p in resolved_paths:
        if p.startswith("custom:"):
            continue
        if not os.path.exists(p):
            continue
        if our_meipass and our_meipass in os.path.abspath(p).lower():
            continue
            
        if os.path.isfile(p):
            try:
                files_list.append((p, os.path.getsize(p)))
            except Exception:
                pass
        else:
            try:
                stack = [p]
                while stack and len(files_list) < limit * 2:
                    curr = stack.pop()
                    try:
                        for entry in os.scandir(curr):
                            if entry.is_file(follow_symlinks=False):
                                files_list.append((entry.path, entry.stat(follow_symlinks=False).st_size))
                            elif entry.is_dir(follow_symlinks=False):
                                stack.append(entry.path)
                    except Exception:
                        pass
            except Exception:
                pass
    files_list.sort(key=lambda x: x[1], reverse=True)
    return files_list[:limit]

# ==========================================================
# 系统数据库 / 结构文件保护名单
#
# 调研发现：Windows 下大量「看起来是日志/缓存」的文件实为数据库或系统结构，
# 直接删除会造成 Windows Update 损坏、审计记录丢失、驱动状态异常。
# 这里做最后一道删除闸门——无论规则怎么配，这些文件都不会被删。
# ==========================================================
# 精确文件名（ESE 事务日志：名为 .log 实为数据库日志）
_SYSTEM_DB_EXACT = frozenset({
    "edb.log", "edb.chk", "edbres00001.jrs", "edbres00002.jrs",
    "edbtmp.log", "tmp.edb",
})
# 扩展名级保护
_SYSTEM_DB_EXTS = (".edb", ".jrs", ".evtx", ".hve", ".dat", ".bcf")
# 目录级：整个目录属于数据库，其中的文件一律保护
_SYSTEM_DB_DIR_FRAGMENTS = (
    "softwaredistribution\\datastore",   # Windows Update 数据库
    "system32\\winevt\\logs",            # 事件日志（需 wevtutil）
    "system32\\config",                  # 注册表配置单元
    "system32\\wbem\\repository",        # WMI 存储库
    "system32\\sru",                     # 系统资源使用数据库
    "appcompat\\programs",               # Amcache 兼容性数据库
    "driverstore\\filerepository",       # 驱动仓库：实测 190 个 OEM 驱动全部在用
    "system32\\driverstore",             # 仅 Temp 子目录可清，其余一律保护
    "windows\\fonts",                    # 系统字体
    "system32\\tasks",                   # 计划任务
    "windows\\shellcomponents",          # 系统组件 DLL
    "windows\\immersivecontrolpanel",    # 系统设置本体
    "wdi\\rtbackup",                     # SACL 崩溃备份
    "system32\\sleepstudy",              # 电源诊断（内核占用）
    "windows\\appcompat",                # 兼容性遥测基线
    # --- 创意软件用户资产（实测确认：看似缓存，实为用户资产）---
    "adobe\\cameraraw",                  # 相机/镜头配置、AI 模型、用户预设(.xmp)
    "motion graphics templates",         # .mogrt 动态图形模板（用户素材）
    "coresync\\plugins",                 # Adobe Fonts 字体同步插件本体
    "sky_presets",                       # Photoshop 天空替换预设
    "uxp\\internal",                     # UXP 插件本体
    "adobe\\ccx welcome",                # Creative Cloud 欢迎页资产与状态
    "ngx\\models",                       # NVIDIA DLSS/AI 模型
    "programdata\\nvidia",               # NVIDIA 运行时模型资产
    "logioptionsplus",                   # Logitech 设备配置(depots 为安装包仓库)
    "autodesk\\cer",                     # Autodesk 崩溃报告数据库
    "boost_interprocess",                # 跨进程共享内存
    # --- 许可证与激活（删了软件会变未激活）---
    "adobe\\slstore",                    # Adobe 授权存储
    "adobe\\upi",                        # Adobe UPI（EM Store 授权）
    "adsklicensingservice",              # Autodesk 许可服务（licpath.lic 等）
    "adobe\\adlm",                       # 旧版 Adobe 许可管理器
    "redgiant\\licenses",                # Red Giant 许可(.rgs)
    "red giant\\licenses",
    "maxstoa",                           # MAXtoA 许可
    "adlm",
    # --- 资产库与还原数据 ---
    "cameraprofiles",                    # 相机/镜头配置
    "lensprofiles",
    "modelzoo",                          # CameraRaw AI 模型
    "trapcode packs",                    # Red Giant 插件包
    "installation receipts",             # Red Giant 安装凭据
    "uninstallers",                      # Autodesk 卸载程序
    "odis",                              # Autodesk 安装服务
    "applicationplugins",                # 应用插件本体
    # --- Adobe / NVIDIA 用户设置与登录态（删了丢配置与激活）---
    "slcache",                           # Adobe 许可证缓存(.slc)
    "adobe pcd",                         # Adobe PCD 缓存
    "cc libraries",                      # CC Libraries 登录密钥(.key/.crt)
    "core sync",                         # CoreSync 同步
    "autorecover",                       # Adobe 自动保存
    "actions palette",                   # 用户动作
    "workspaces",                        # 工作区布局
    "prefs.psp",                         # Photoshop 首选项（含键盘快捷键）
    "uiprefs.psp",                       # UI 布局偏好
    "adobe\\fonts",                      # Adobe Fonts
    "user owned fonts",                  # 用户自购字体
    "nvaccount",                         # NVIDIA 账号登录态
    "nvbackend\\dao",                    # NVIDIA 用户设置数据库
    "nvdrsdb",                           # NVIDIA 3D 设置数据库
    "nvngx_config",                      # DLSS 版本映射
    "shadowplay",                        # ShadowPlay 录制
    "nvtopps.db3",                       # NVIDIA 遥测数据库
    "dvaanalyticsid",                    # 设备标识
    "upi.db",                            # Adobe UPI 数据库
)


# ==========================================================
# 系统服务守卫
#
# 调研结论：WinSxS\Temp\InFlight 是 CBS 组件安装「进行中」的暂存区。
# 若此时正在安装更新/驱动，删除会造成组件存储不可逆损坏。
# 因此对这类条目，清理前必须确认相关服务已停止。
# ==========================================================
# 需要这些服务全部停止，才允许清理 CBS/WinSxS 暂存区
_CBS_RELATED_SERVICES = ("TrustedInstaller", "wuauserv", "msiserver")


def _is_service_running(name):
    """查询单个 Windows 服务是否正在运行。查询失败时保守返回 True（视为运行中）。"""
    try:
        import subprocess
        out = subprocess.run(
            ["sc", "query", name],
            capture_output=True, text=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        txt = (out.stdout or "") + (out.stderr or "")
        return "RUNNING" in txt.upper()
    except Exception:
        # 查不到就当它在跑：宁可不清理，也不冒险
        return True


_cbs_idle_cache = None


def cbs_services_idle():
    """CBS/Windows Update 相关服务是否全部空闲（可安全清理暂存区）。

    结果按进程缓存：清理 WinSxS\\Temp 时可能遍历数万个文件，
    每个文件都去查服务会造成数万次 sc query（实测目录 25,792 个文件）。
    """
    global _cbs_idle_cache
    if _cbs_idle_cache is None:
        _cbs_idle_cache = not any(
            _is_service_running(s) for s in _CBS_RELATED_SERVICES)
    return _cbs_idle_cache


def is_system_database_file(low_path, base_name):
    """判断是否为系统数据库/结构文件（小写路径与文件名）。只读判定。"""
    # 例外先判：Adobe typequest 是字体索引缓存（实测为高熵缓存，
    # 非 TTF/OTF 字体、非数据库），扩展名命中 .dat 也允许清理。
    if "adobe\\typequest" in low_path:
        return False
    if base_name in _SYSTEM_DB_EXACT:
        return True
    # edb00062.log / edb.chk 这类序列事务日志
    if (base_name.startswith("edb") and base_name.endswith(".log")):
        return True
    if base_name.endswith(_SYSTEM_DB_EXTS):
        return True
    for frag in _SYSTEM_DB_DIR_FRAGMENTS:
        if frag in low_path:
            # 白名单例外：受保护目录下的「临时」子目录仍可清
            # （如 DriverStore\Temp\ 与 FileRepository 无关，是安装产生的 .tmp）
            if frag in ("system32\\driverstore",) and "\\temp\\" in low_path:
                continue
            # NVIDIA 目录下日志类文件可清（模型资产/3D 设置数据库仍受保护）
            if frag in ("programdata\\nvidia",) and low_path.endswith(
                    (".log", ".nvlgstg")):
                continue
            # Autodesk 许可服务的 Log 子目录可清（licpath.lic 本体仍受保护）
            if frag in ("adsklicensingservice",) and "\\log\\" in low_path:
                continue
            # Adobe typequest 是字体索引缓存（实测非字体文件），可清
            if "adobe\\typequest" in low_path:
                continue
            return True
    return False


def delete_file_resilient(path, log_callback=None):
    """删除单个文件，带三级容错。返回释放的字节数（失败为 0）。

    参考 BleachBit 的处理方式（winerror 32/5/145）：
      1. 正常删除
      2. WinError 32「文件被占用」-> 尝试截断为 0 字节，立刻回收空间；
         再登记 MoveFileEx(DELAY_UNTIL_REBOOT)，重启后彻底删除
      3. WinError 5「权限不足」  -> 去掉只读属性后重试
      4. WinError 145「目录非空」-> 跳过
    """
    try:
        size = os.path.getsize(path)
    except Exception:
        return 0

    # 兜底：绝不允许删除 Agent 记忆目录内的任何文件
    if is_agent_memory_path(path):
        if log_callback:
            log_callback(f"[免疫] Agent 记忆文件已保护，跳过: {obfuscate_path(path)}")
        return 0

    # 兜底闸门：「伪装成日志/缓存」的系统数据库与结构文件，绝不允许删除。
    # 典型：SoftwareDistribution\DataStore\Logs\edb*.log 名为 .log，
    # 实为 ESE 数据库事务日志，删了会让 Windows Update 损坏；
    # *.evtx 由 EventLog 服务持有，需用 wevtutil cl 清理而非删文件；
    # *.hve 是注册表配置单元、*.edb 是 ESE 数据库、*.jrs 是事务日志预留。
    low = path.lower()
    base = os.path.basename(low)
    if is_system_database_file(low, base):
        if log_callback:
            log_callback(f"[保护] 系统数据库/结构文件，跳过: {obfuscate_path(path)}")
        return 0

    try:
        os.unlink(path)
        return size
    except Exception as e:
        code = getattr(e, "winerror", None)

        # 被占用：截断为 0 字节先回收空间，再登记重启删除
        if code == 32:
            truncated = False
            try:
                with open(path, "wb"):
                    pass
                truncated = True
            except Exception:
                truncated = False
            try:
                _schedule_reboot_delete(path)
            except Exception:
                pass
            if log_callback:
                if truncated:
                    log_callback(f"[!] 文件被占用，已清空内容并登记重启删除: {obfuscate_path(path)}")
                else:
                    log_callback(f"[!] 文件被占用，已登记重启后删除: {obfuscate_path(path)}")
            return size if truncated else 0

        # 权限不足：去掉只读/系统属性后重试
        if code == 5:
            try:
                import stat as _stat
                os.chmod(path, _stat.S_IWRITE | _stat.S_IREAD)
                os.unlink(path)
                return size
            except Exception:
                return 0

        # 目录非空等情况：跳过
        return 0


def _schedule_reboot_delete(path):
    """登记 Windows 重启后删除（MoveFileEx MOVEFILE_DELAY_UNTIL_REBOOT）。"""
    try:
        import ctypes
        MOVEFILE_DELAY_UNTIL_REBOOT = 4
        ctypes.windll.kernel32.MoveFileExW(str(path), None, MOVEFILE_DELAY_UNTIL_REBOOT)
    except Exception:
        pass


def clean_directory(path, log_callback=None, skipped_files=None, stale_days=None,
                    _skipped_norm=None):
    """清理目录/文件，返回释放的字节数。

    stale_days: 若给出，只删除「最近访问时间」早于 N 天前的文件。
                用于 %TEMP% 这类目录，避免误删正在运行的程序数据。
    _skipped_norm: 内部递归复用的小写规范路径集合（O(1) 查询）。
    """
    if path == "custom:recyclebin":
        size = get_recycle_bin_size()
        if size > 0:
            empty_recycle_bin()
            if log_callback:
                log_callback(f"[✓] 成功清空 Windows 系统回收站，释放 {format_size(size)}")
            return size
        return 0

    if not os.path.exists(path): return 0
    # O(1) 查询集：历史上这里对每个文件做 any() 全表扫描，万级文件×万级跳过 = 亿级比较
    if _skipped_norm is None:
        _skipped_norm = set()
        if skipped_files:
            for sf in skipped_files:
                try:
                    _skipped_norm.add(os.path.abspath(sf).lower())
                except Exception:
                    pass
        
    # 陈旧阈值：早于该时间点的文件才允许删除
    stale_cutoff = None
    if stale_days:
        stale_cutoff = time.time() - stale_days * 86400

    if skipped_files is None:
        skipped_files = set()

    # 兜底：整个目录若落在 Agent 记忆免疫网内，直接拒绝清理
    if is_agent_memory_path(path):
        if log_callback:
            log_callback(f"[免疫] Agent 记忆目录已保护，跳过: {obfuscate_path(path)}")
        return 0

    # 兜底闸门：CBS/WinSxS 暂存区——仅当相关服务全部停止时才允许清理。
    # 活跃安装期间删除 InFlight 暂存会造成组件存储不可逆损坏。
    # 必须放在目录级入口：子目录走 shutil.rmtree 分支，不会经过单文件删除函数。
    low_clean = os.path.abspath(path).lower()
    if ("winsxs\\temp" in low_clean or "cbstemp" in low_clean
            or "servicing\\lcu" in low_clean):
        if not cbs_services_idle():
            if log_callback:
                log_callback("[保护] Windows 更新/组件安装服务正在运行，"
                             "暂存区已跳过（避免损坏组件存储）")
            return 0

    deleted_size = 0
    try:
        if os.path.isfile(path) or os.path.islink(path):
            norm_p = os.path.abspath(path).lower()
            # Check if this exact file is skipped
            is_skipped = norm_p in _skipped_norm
            if is_skipped:
                if log_callback:
                    log_callback(f"[保留] 用户跳过文件: {obfuscate_path(path)}")
                return 0
            if stale_cutoff is not None:
                try:
                    if os.path.getatime(path) > stale_cutoff:
                        if log_callback:
                            log_callback(f"[保留] 近期文件未到期: {obfuscate_path(path)}")
                        return 0
                except Exception:
                    return 0
            size = os.path.getsize(path)
            os.unlink(path)
            return size
            
        for item in os.scandir(path):
            try:
                norm_item_p = os.path.abspath(item.path).lower()
                is_skipped = norm_item_p in _skipped_norm
                if is_skipped:
                    if log_callback:
                        log_callback(f"[保留] 用户跳过文件: {obfuscate_path(item.path)}")
                    continue
                    
                if item.is_file() or item.is_symlink():
                    if stale_cutoff is not None:
                        try:
                            if item.stat().st_atime > stale_cutoff:
                                continue  # 近期访问过，保留
                        except Exception:
                            continue
                    deleted_size += delete_file_resilient(item.path, log_callback)
                elif item.is_dir():
                    # 干净的梦想之力，Admin Agent 不对 claude Session Files下手
                    if is_agent_memory_path(item.path):
                        if log_callback:
                            log_callback(f"[免疫] Agent 记忆目录已保护，跳过: {obfuscate_path(item.path)}")
                        continue
                    has_skipped_inside = any(s.startswith(norm_item_p + os.sep) or s == norm_item_p for s in _skipped_norm)
                    if has_skipped_inside:
                        # 目录内有受保护文件：递归逐项清，保留跳过项；stale_days 必须传递，
                        # 否则 %TEMP% 等目录的 7 天保护只覆盖顶层散文件，子目录被整删。
                        deleted_size += clean_directory(item.path, log_callback, skipped_files,
                                                        stale_days=stale_days,
                                                        _skipped_norm=_skipped_norm)
                    elif stale_cutoff is not None:
                        # 有陈旧策略但目录内没有保护文件：仍逐文件过滤，不整删
                        deleted_size += clean_directory(item.path, log_callback, skipped_files,
                                                        stale_days=stale_days,
                                                        _skipped_norm=_skipped_norm)
                    else:
                        size = get_size(item.path)
                        try:
                            shutil.rmtree(item.path, onerror=remove_readonly)
                            deleted_size += size
                        except Exception:
                            # 部分文件占用/权限不足：按真实残留修正释放量，避免虚高
                            try:
                                remaining = get_size(item.path)
                                deleted_size += max(0, size - remaining)
                            except Exception:
                                pass
            except Exception:
                pass
    except Exception:
        pass
    return deleted_size
