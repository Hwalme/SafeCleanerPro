import os
import sys
import shutil
import stat
import time
import glob
import winreg
import ctypes
import string

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
    for d in drives:
        if d.lower() == "c:\\":
            continue
        # Common temp folders
        paths.append((f"{d}Temp\\*", f"非系统盘临时过渡垃圾 ({d}Temp)"))
        paths.append((f"{d}Tmp\\*", f"非系统盘临时垃圾 ({d}Tmp)"))
        # Common downloads
        paths.append((f"{d}Downloads\\*", f"非系统盘大文件下载暂存 ({d}Downloads)"))
        paths.append((f"{d}下载\\*", f"非系统盘下载暂存 ({d}下载)"))
        # Redirected documents
        paths.append((f"{d}WeChat Files\\*", f"非系统盘微信聊天媒体 ({d}WeChat Files)"))
        paths.append((f"{d}Tencent Files\\*", f"非系统盘QQ缓存 ({d}Tencent Files)"))
        paths.append((f"{d}WXWork\\*", f"非系统盘企业微信缓存 ({d}WXWork)"))
        paths.append((f"{d}wps_cloud_user_files\\*", f"非系统盘WPS云同步缓存 ({d}wps_cloud_user_files)"))
        paths.append((f"{d}Documents\\WeChat Files\\*", f"非系统盘微信聊天媒体 ({d}Documents\\WeChat Files)"))
        paths.append((f"{d}Documents\\Tencent Files\\*", f"非系统盘QQ缓存 ({d}Documents\\Tencent Files)"))
        paths.append((f"{d}Documents\\WXWork\\*", f"非系统盘企业微信缓存 ({d}Documents\\WXWork)"))
        paths.append((f"{d}Documents\\wps_cloud_user_files\\*", f"非系统盘WPS云同步缓存 ({d}Documents\\wps_cloud_user_files)"))
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

def clean_directory(path, log_callback=None, skipped_files=None):
    if path == "custom:recyclebin":
        size = get_recycle_bin_size()
        if size > 0:
            empty_recycle_bin()
            if log_callback:
                log_callback(f"[✓] 成功清空 Windows 系统回收站，释放 {format_size(size)}")
            return size
        return 0

    if not os.path.exists(path): return 0
    if skipped_files is None:
        skipped_files = set()
        
    deleted_size = 0
    try:
        if os.path.isfile(path) or os.path.islink(path):
            norm_p = os.path.abspath(path).lower()
            # Check if this exact file is skipped
            is_skipped = any(os.path.abspath(sf).lower() == norm_p for sf in skipped_files)
            if is_skipped:
                if log_callback:
                    log_callback(f"[保留] 用户跳过文件: {obfuscate_path(path)}")
                return 0
            size = os.path.getsize(path)
            os.unlink(path)
            return size
            
        for item in os.scandir(path):
            try:
                norm_item_p = os.path.abspath(item.path).lower()
                is_skipped = any(os.path.abspath(sf).lower() == norm_item_p for sf in skipped_files)
                if is_skipped:
                    if log_callback:
                        log_callback(f"[保留] 用户跳过文件: {obfuscate_path(item.path)}")
                    continue
                    
                if item.is_file() or item.is_symlink():
                    size = item.stat().st_size
                    os.unlink(item.path)
                    deleted_size += size
                elif item.is_dir():
                    has_skipped_inside = any(os.path.abspath(sf).lower().startswith(norm_item_p + os.sep) or os.path.abspath(sf).lower() == norm_item_p for sf in skipped_files)
                    if has_skipped_inside:
                        deleted_size += clean_directory(item.path, log_callback, skipped_files)
                    else:
                        size = get_size(item.path)
                        shutil.rmtree(item.path, onerror=remove_readonly)
                        deleted_size += size
            except Exception:
                pass
    except Exception:
        pass
    return deleted_size
