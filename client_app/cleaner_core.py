import os
import sys
import shutil
import stat
import time
import glob
import winreg
import ctypes
import string

def get_size(path):
    total = 0
    try:
        if not os.path.exists(path): return 0
        if os.path.isfile(path):
            return os.path.getsize(path)
        for dirpath, dirnames, filenames in os.walk(path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp):
                    try:
                        total += os.path.getsize(fp)
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

def get_supported_apps():
    user_home = os.path.expanduser("~")
    appdata_roaming = os.path.join(user_home, 'AppData', 'Roaming')
    appdata_local = os.path.join(user_home, 'AppData', 'Local')
    
    wechat_dir = get_wechat_path()
    qq_dir = get_qq_path()
    wecom_dir = get_wecom_path()
    
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
        }
    ]
    return apps

def get_resolved_paths(paths):
    resolved = []
    for p in paths:
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
        if our_meipass and our_meipass in os.path.abspath(p).lower():
            continue
        total += get_size(p)
    return total

def scan_app_files(app, limit=200):
    files_list = []
    our_meipass = getattr(sys, '_MEIPASS', None)
    if our_meipass:
        our_meipass = os.path.abspath(our_meipass).lower()
        
    resolved_paths = get_resolved_paths(app.get("paths", []))
    for p in resolved_paths:
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
                for root, dirs, files in os.walk(p):
                    for f in files:
                        fp = os.path.join(root, f)
                        if not os.path.islink(fp):
                            try:
                                files_list.append((fp, os.path.getsize(fp)))
                            except Exception:
                                pass
                            if len(files_list) > limit * 5:
                                break
            except Exception:
                pass
    files_list.sort(key=lambda x: x[1], reverse=True)
    return files_list[:limit]

def clean_directory(path, log_callback=None, skipped_files=None):
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
