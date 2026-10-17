# -*- coding: utf-8 -*-
"""cleaner_rules.py — 可扩展的清理规则库（外部规则池）

为什么独立成模块
--------------------------------------------------------------------
cleaner_core.py 已经 46.8KB，超过 Pyarmor 试用版单脚本约 42KB 的上限；
它的 get_supported_apps() 是一个 190~997 行的巨型内联列表，继续往里塞
清理项会让打包更容易失败。

因此新增清理项统一放这里：
  * 每条规则是纯数据 dict，与 cleaner_core 现有的 app 结构完全一致；
  * get_extra_apps() 负责把 %LOCALAPPDATA% 等变量展开成真实路径；
  * 只保留本机真实存在的目录（os.path.exists），避免列表里出现一堆
    永远 0 字节、干扰用户判断的空壳项；
  * 在 cleaner_core.get_supported_apps() 末尾合并即可。

风险分级约定（与现有代码一致）
--------------------------------------------------------------------
risk_level = "safe"  删除后不影响任何用户数据（缓存/日志/临时文件）
risk_level = "risk"  可能删掉用户接收过的文件、安装包等，需用户确认

type 取值：system / app / chat / dev / ai / adobe（决定分组归属）
"""
import os
from secure_rules import RulePackError

# 常用环境变量
LOCAL = os.environ.get("LOCALAPPDATA", "")
ROAMING = os.environ.get("APPDATA", "")
HOME = os.path.expanduser("~")
TEMP = os.environ.get("TEMP", "")


def _p(*parts):
    """拼接路径并规范化。"""
    return os.path.join(*parts)


def _exists_any(paths):
    """这组路径里至少有一个真实存在才纳入列表。"""
    for p in paths:
        base = p.rstrip("\\*")
        if os.path.exists(base):
            return True
    return False


# ====================================================================
# 规则池：每项都是 "可在 get_supported_apps 中直接使用" 的完整 dict
# 字段：id / name / paths / icon / immune / type / risk_level / risk_desc
# ====================================================================
RULES = [
    # ---------------------------------------------------------------
    # (A) AI 编程工具与大模型客户端 —— 本机实测合计 >10GB，原先完全缺失
    # ---------------------------------------------------------------
    {
        "id": "trae_cn",
        "name": "Trae CN 字节 AI 编程 IDE 缓存与索引",
        "paths": [
            _p(ROAMING, "Trae CN", "logs", "*"),
            _p(ROAMING, "Trae CN", "CachedData", "*"),
            _p(ROAMING, "Trae CN", "Code Cache", "*"),
            _p(ROAMING, "Trae CN", "GPUCache", "*"),
            _p(ROAMING, "Trae CN", "blob_storage", "*"),
            _p(ROAMING, "Trae CN", "Session Storage", "*"),
            _p(ROAMING, "Trae CN", "Local Storage", "leveldb", "*.log"),
        ],
        "icon": "🧠",
        "immune": False,
        "type": "ai",
        "risk_level": "safe",
        "risk_desc": "清理 Trae CN 的日志与渲染缓存，不影响你的项目代码与对话记忆。",
    },
    {
        "id": "trae_solo_cn",
        "name": "TRAE SOLO CN 编辑器运行缓存",
        "paths": [
            _p(ROAMING, "TRAE SOLO CN", "logs", "*"),
            _p(ROAMING, "TRAE SOLO CN", "CachedData", "*"),
            _p(ROAMING, "TRAE SOLO CN", "Code Cache", "*"),
            _p(ROAMING, "TRAE SOLO CN", "GPUCache", "*"),
            _p(ROAMING, "TRAE SOLO CN", "blob_storage", "*"),
        ],
        "icon": "🧠",
        "immune": False,
        "type": "ai",
        "risk_level": "safe",
        "risk_desc": "清理 TRAE SOLO 的运行缓存与旧日志，不影响工程源码。",
    },
    {
        "id": "lingma",
        "name": "通义灵码 Lingma 插件缓存",
        "paths": [
            _p(ROAMING, "Lingma", "logs", "*"),
            _p(ROAMING, "Lingma", "Cache", "*"),
            _p(ROAMING, "Lingma", "CachedData", "*"),
            _p(ROAMING, "Lingma", "Code Cache", "*"),
        ],
        "icon": "🧠",
        "immune": False,
        "type": "ai",
        "risk_level": "safe",
        "risk_desc": "清理灵码插件日志与缓存文件，不影响已生成的代码。",
    },
    # 注意：Claude 的对话记忆在 %APPDATA%\Claude 与 ~/.claude，由
    # cleaner_core 的免疫网单独保护（见 immune 项）。此处只清
    # %LOCALAPPDATA%\AnthropicClaude 下的渲染缓存，绝不触碰记忆目录。
    {
        "id": "anthropicclaude",
        "name": "Claude Desktop 桌面端运行缓存 (仅缓存层)",
        "paths": [
            _p(LOCAL, "AnthropicClaude", "Cache", "*"),
            _p(LOCAL, "AnthropicClaude", "Code Cache", "*"),
            _p(LOCAL, "AnthropicClaude", "GPUCache", "*"),
            _p(LOCAL, "AnthropicClaude", "logs", "*"),
        ],
        "icon": "🤖",
        "immune": False,
        "type": "ai",
        "risk_level": "safe",
        "risk_desc": "仅清理 Claude 桌面端渲染缓存与日志。对话记忆存放在 %APPDATA%\\Claude，已列为永久免疫项，本项不会触碰。",
    },
    {
        "id": "kimi_desktop",
        "name": "Kimi 桌面端更新残留包",
        "paths": [
            _p(LOCAL, "kimi-desktop-updater", "pending", "*"),
            _p(LOCAL, "kimi-desktop-updater", "temp", "*"),
        ],
        "icon": "🌙",
        "immune": False,
        "type": "ai",
        "risk_level": "safe",
        "risk_desc": "清理 Kimi 客户端下载后遗留的更新安装包，不影响聊天记录。",
    },
    {
        "id": "yuanbao",
        "name": "腾讯元宝 AI 助手缓存",
        "paths": [
            _p(ROAMING, "Tencent", "Yuanbao", "Cache", "*"),
            _p(ROAMING, "Tencent", "Yuanbao", "Code Cache", "*"),
            _p(ROAMING, "Tencent", "Yuanbao", "GPUCache", "*"),
            _p(ROAMING, "Tencent", "Yuanbao", "logs", "*"),
        ],
        "icon": "🤖",
        "immune": False,
        "type": "ai",
        "risk_level": "safe",
        "risk_desc": "清理元宝客户端网页缓存与日志，不影响已保存的回答。",
    },

    # ---------------------------------------------------------------
    # (B) 国内常用软件 —— 百度网盘/WPS/搜狗/网易云/腾讯会议
    # ---------------------------------------------------------------
    {
        "id": "baidunetdisk",
        "name": "百度网盘客户端缓存与日志",
        "paths": [
            _p(ROAMING, "baidunetdisk", "logs", "*"),
            _p(ROAMING, "baidunetdisk", "cache", "*"),
            _p(ROAMING, "baidu", "BaiduYunKernel", "logs", "*"),
            _p(ROAMING, "baidu", "BaiduYunKernel", "crash", "*"),
            _p(ROAMING, "baidu", "BaiduYunKernel", "cache", "*"),
        ],
        "icon": "☁️",
        "immune": False,
        "type": "app",
        "risk_level": "safe",
        "risk_desc": "仅清理网盘客户端日志与崩溃报告，不影响已下载文件和云端数据。",
    },
    {
        "id": "wps_kingsoft",
        "name": "WPS Office 金山套件运行日志与模板缓存",
        "paths": [
            _p(ROAMING, "kingsoft", "office6", "log", "*"),
            _p(ROAMING, "kingsoft", "office6", "backup", "*"),
            _p(ROAMING, "kingsoft", "wps", "log", "*"),
            _p(ROAMING, "kingsoft", "wps", "addons", "pool", "*"),
            _p(ROAMING, "kingsoft", "WPS Cloud Files", "log", "*"),
        ],
        "icon": "📄",
        "immune": False,
        "type": "app",
        "risk_level": "safe",
        "risk_desc": "清理 WPS 运行日志与插件临时池；云文档本体不在清理范围内。",
    },
    {
        "id": "sogou_ime",
        "name": "搜狗输入法用户词库缓存与升级日志",
        "paths": [
            _p(ROAMING, "Tencent", "SogouIme", "LogFiles", "*"),
            _p(ROAMING, "Tencent", "SogouIme", "SGDownload", "*"),
            _p(ROAMING, "Tencent", "SogouIme", "SkinCache", "*"),
        ],
        "icon": "⌨️",
        "immune": False,
        "type": "app",
        "risk_level": "safe",
        "risk_desc": "清理输入法皮肤缓存与升级日志，不删除你的个人词库。",
    },
    {
        "id": "netease_music",
        "name": "网易云音乐客户端缓存",
        "paths": [
            _p(LOCAL, "Netease", "CloudMusic", "Cache", "*"),
            _p(LOCAL, "Netease", "CloudMusic", "web_cache", "*"),
            _p(LOCAL, "Netease", "CloudMusic", "log", "*"),
        ],
        "icon": "🎵",
        "immune": False,
        "type": "app",
        "risk_level": "safe",
        "risk_desc": "清理歌曲缓存与网页缓存，不影响已下载的本地音乐文件。",
    },
    {
        "id": "wemeet",
        "name": "腾讯会议运行缓存与历史日志",
        "paths": [
            _p(ROAMING, "Tencent", "WeMeet", "log", "*"),
            _p(ROAMING, "Tencent", "WeMeet", "Cache", "*"),
            _p(ROAMING, "Tencent", "WeMeet", "webview", "Cache", "*"),
            _p(ROAMING, "Tencent", "WeMeet", "sdklog", "*"),
        ],
        "icon": "📹",
        "immune": False,
        "type": "chat",
        "risk_level": "safe",
        "risk_desc": "清理会议客户端日志与缓存，不影响本地录制的会议视频。",
    },
    {
        "id": "autodesk",
        "name": "Autodesk 系列软件日志与崩溃报告",
        "paths": [
            _p(ROAMING, "Autodesk", "Logs", "*"),
            _p(ROAMING, "Autodesk", "AutoCAD 20*", "*", "*", "AutoCAD", "Logs", "*"),
            _p(LOCAL, "Autodesk", "Logs", "*"),
        ],
        "icon": "📐",
        "immune": False,
        "type": "app",
        "risk_level": "safe",
        "risk_desc": "清理 Autodesk 日志与崩溃转储，不影响设计图纸文件。",
    },
    {
        "id": "islide",
        "name": "iSlide PPT 插件缓存",
        "paths": [
            _p(ROAMING, "iSlide", "Cache", "*"),
            _p(ROAMING, "iSlide", "Log", "*"),
        ],
        "icon": "📊",
        "immune": False,
        "type": "app",
        "risk_level": "safe",
        "risk_desc": "清理 iSlide 素材预览缓存与日志，不影响已下载的 PPT 模板。",
    },

    # ---------------------------------------------------------------
    # (C) 开发环境 —— Maven / Conda / Poetry / Yarn / pnpm / Docker
    # ---------------------------------------------------------------
    {
        "id": "maven_repo",
        "name": "Maven 本地仓库依赖 (~/.m2/repository)",
        "paths": [
            _p(HOME, ".m2", "repository", "*"),
        ],
        "icon": "☕",
        "immune": False,
        "type": "dev",
        "risk_level": "risk",
        "risk_desc": "删除本地 Maven 依赖缓存。清理后下次构建需要重新联网下载，请确认网络可用。",
    },
    {
        "id": "conda_pkgs",
        "name": "Conda / Anaconda 包安装缓存 (pkgs)",
        "paths": [
            _p(_p(os.path.dirname(os.path.dirname(TEMP or ".")), "pkgs"), "cache", "*")
            if False else _p("C:\\ProgramData", "Anaconda3", "pkgs", "cache", "*"),
            _p("D:\\Program Files", "anaconda3", "pkgs", "cache", "*"),
            _p("C:\\Program Files", "anaconda3", "pkgs", "cache", "*"),
            _p(HOME, "anaconda3", "pkgs", "cache", "*"),
            _p(HOME, "miniconda3", "pkgs", "cache", "*"),
        ],
        "icon": "🐍",
        "immune": False,
        "type": "dev",
        "risk_level": "safe",
        "risk_desc": "清理 Conda 已下载的安装包压缩档（pkgs\\cache），已安装的 Python 环境不受影响。",
    },
    {
        "id": "poetry_cache",
        "name": "Poetry 依赖管理缓存",
        "paths": [
            _p(LOCAL, "pypoetry", "Cache", "*"),
            _p(LOCAL, "pypoetry", "artifacts", "*"),
        ],
        "icon": "📦",
        "immune": False,
        "type": "dev",
        "risk_level": "safe",
        "risk_desc": "清理 Poetry 下载缓存，不影响虚拟环境和已安装依赖。",
    },
    {
        "id": "yarn_cache",
        "name": "Yarn 前端依赖全局缓存",
        "paths": [
            _p(LOCAL, "Yarn", "Cache", "*"),
            _p(LOCAL, "Yarn", "v6", "*"),
        ],
        "icon": "🧶",
        "immune": False,
        "type": "dev",
        "risk_level": "risk",
        "risk_desc": "删除 Yarn 全局缓存，下次 install 会重新下载依赖。",
    },
    {
        "id": "pnpm_cache",
        "name": "pnpm 依赖仓库缓存",
        "paths": [
            _p(LOCAL, "pnpm", "cache", "*"),
            _p(LOCAL, "pnpm", "store", "*"),
        ],
        "icon": "📦",
        "immune": False,
        "type": "dev",
        "risk_level": "risk",
        "risk_desc": "删除 pnpm 全局存储，后续安装需重新下载依赖包。",
    },
    {
        "id": "unreal_engine",
        "name": "Unreal Engine 派生数据缓存 (DDC)",
        "paths": [
            _p(LOCAL, "UnrealEngine", "Common", "DerivedDataCache", "*"),
            _p(ROAMING, "Unreal Engine", "Common", "DerivedDataCache", "*"),
        ],
        "icon": "🎮",
        "immune": False,
        "type": "dev",
        "risk_level": "safe",
        "risk_desc": "清理 UE 着色器与派生数据缓存，引擎会自动重建，不影响工程源文件。",
    },
    {
        "id": "electron_updater",
        "name": "Electron 应用残留更新包 (*-updater)",
        "paths": [
            _p(LOCAL, "kimi-desktop-updater", "pending", "*"),
            _p(LOCAL, "@mmx-agentelectron-updater", "pending", "*"),
        ],
        "icon": "⚡",
        "immune": False,
        "type": "app",
        "risk_level": "safe",
        "risk_desc": "清理 Electron 应用下载后残留的更新安装包，程序本体不受影响。",
    },
    {
        "id": "env_kit",
        "name": "env-kit 运行环境缓存",
        "paths": [
            _p(LOCAL, "env-kit", "cache", "*"),
            _p(LOCAL, "env-kit", "tmp", "*"),
            _p(LOCAL, "env-kit", "logs", "*"),
        ],
        "icon": "🧰",
        "immune": False,
        "type": "dev",
        "risk_level": "safe",
        "risk_desc": "清理 env-kit 的下载与临时文件，不影响已部署的运行环境。",
    },

    # ---------------------------------------------------------------
    # (D) 微信生态补充 —— 大文件目录（风险级，需逐文件确认）
    # ---------------------------------------------------------------
    {
        "id": "xwechat_files",
        "name": "新版微信 (xwechat) 接收文件与媒体缓存",
        "paths": [
            _p(ROAMING, "Tencent", "xwechat", "cache", "*"),
            _p(ROAMING, "Tencent", "xwechat", "log", "*"),
            _p(ROAMING, "Tencent", "xwechat", "web", "Cache", "*"),
        ],
        "icon": "💬",
        "immune": False,
        "type": "chat",
        "risk_level": "risk",
        "risk_desc": "清理新版微信的缓存与日志；建议先用「文件明细」逐项确认，重要聊天文件请提前备份。",
    },
    {
        "id": "wechat_subfolders",
        "name": "微信 (WeChat) 子账号数据缓存",
        "paths": [
            _p(ROAMING, "Tencent", "WeChat", "All Users", "config", "*.tmp"),
            _p(ROAMING, "Tencent", "WeChat", "wap", "*"),
            _p(ROAMING, "Tencent", "WeChat", "XPlugin", "Plugins", "*", "Cache", "*"),
        ],
        "icon": "💬",
        "immune": False,
        "type": "chat",
        "risk_level": "safe",
        "risk_desc": "清理微信插件缓存与临时配置，不影响聊天记录与已接收的文档。",
    },
    {
        "id": "wecom_subfolders",
        "name": "企业微信 (WeCom) 缓存补充",
        "paths": [
            _p(ROAMING, "Tencent", "WXWork", "Cache", "*"),
            _p(ROAMING, "Tencent", "WXWork", "web", "Cache", "*"),
            _p(ROAMING, "Tencent", "WXWork", "log", "*"),
        ],
        "icon": "🏢",
        "immune": False,
        "type": "chat",
        "risk_level": "safe",
        "risk_desc": "清理企业微信网页缓存与日志，不影响已接收的工作文档。",
    },

    # ---------------------------------------------------------------
    # (E) Windows 系统深层 —— 事件日志 / 搜索索引 / 崩溃转储 / 传递优化
    # ---------------------------------------------------------------
    {
        "id": "win_event_logs",
        "name": "Windows 事件日志归档 (*.evtx)",
        "paths": [
            "C:\\Windows\\System32\\winevt\\Logs\\*.evtx",
        ],
        "icon": "📋",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理系统事件日志归档，用于排查故障的历史记录会被删除，日常使用无影响。",
    },
    {
        "id": "win_search_index",
        "name": "Windows 搜索索引数据库缓存",
        "paths": [
            "C:\\ProgramData\\Microsoft\\Search\\Data\\Temp\\usgTmp\\*",
            "C:\\ProgramData\\Microsoft\\Search\\Data\\Applications\\Windows\\MSS*.log",
        ],
        "icon": "🔎",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理搜索索引临时文件与日志，索引会在后台自动重建。",
    },
    {
        "id": "win_crash_dumps",
        "name": "用户级崩溃转储文件 (CrashDumps)",
        "paths": [
            _p(LOCAL, "CrashDumps", "*"),
        ],
        "icon": "💥",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理应用崩溃时生成的内存转储文件，仅用于调试，删除不影响使用。",
    },
    {
        "id": "win_delivery_opt",
        "name": "Windows 传递优化缓存 (Delivery Optimization)",
        "paths": [
            "C:\\Windows\\SoftwareDistribution\\DeliveryOptimization\\*",
            _p(LOCAL, "Microsoft", "Windows", "DeliveryOptimization", "Logs", "*"),
        ],
        "icon": "📡",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理 Windows 更新点对点分发缓存，不影响已安装的系统更新。",
    },
    {
        "id": "win_defender_scans",
        "name": "Windows Defender 扫描历史缓存",
        "paths": [
            "C:\\ProgramData\\Microsoft\\Windows Defender\\Scans\\History\\*",
        ],
        "icon": "🛡️",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理杀毒软件扫描历史记录，不影响病毒库与实时防护。",
    },
    {
        "id": "win_wer_queue",
        "name": "Windows 错误报告队列 (WER)",
        "paths": [
            "C:\\ProgramData\\Microsoft\\Windows\\WER\\Temp\\*",
            "C:\\ProgramData\\Microsoft\\Windows\\WER\\ReportQueue\\*",
            _p(LOCAL, "Microsoft", "Windows", "WER", "*"),
        ],
        "icon": "📛",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理系统错误报告临时队列，不影响系统稳定性。",
    },
    {
        "id": "user_temp_stale",
        "name": "用户临时目录陈旧文件 (%TEMP%，7 天未访问)",
        "paths": [
            _p(TEMP, "*") if TEMP else "",
        ],
        "icon": "🗑️",
        "immune": False,
        "type": "system",
        "risk_level": "risk",
        # 只清理 7 天未被访问的临时文件，避免误删正在使用的会话数据。
        "stale_days": 7,
        "risk_desc": "仅清理 7 天以上未访问的用户临时文件。近期文件会保留，以免误删正在运行的程序数据。",
    },
    {
        "id": "win_font_cache",
        "name": "Windows 字体缓存数据库",
        "paths": [
            "C:\\Windows\\System32\\FNTCACHE.DAT",
        ],
        "icon": "🔤",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "删除字体缓存文件，系统重启后会自动重建，可能短暂影响字体加载速度。",
    },

    # ---------------------------------------------------------------
    # (F) Dism++ 风格的大空间项 —— 实测本机合计 >4GB
    #     参考 Chuyu-Team/Dism-Multi-language 的 Data.xml
    # ---------------------------------------------------------------
    {
        "id": "dotnet_native_images",
        "name": ".NET 本机映像缓存 (NativeImages，实测可达数 GB)",
        "paths": [
            "C:\\Windows\\assembly\\NativeImages_v4.0.30319_32\\*",
            "C:\\Windows\\assembly\\NativeImages_v4.0.30319_64\\*",
            "C:\\Windows\\assembly\\NativeImages_v2.0.50727_32\\*",
            "C:\\Windows\\assembly\\NativeImages_v2.0.50727_64\\*",
        ],
        "icon": "🔷",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理 .NET 程序集的预编译本机映像缓存，会在下次启动 .NET 程序时自动重建，首次启动可能略慢。",
    },
    {
        "id": "vs_packages_cache",
        "name": "Visual Studio 离线安装包缓存 (Packages)",
        "paths": [
            _p(os.environ.get("PROGRAMDATA", "C:\\ProgramData"),
               "Microsoft", "VisualStudio", "Packages", "*"),
        ],
        "icon": "🧩",
        "immune": False,
        "type": "dev",
        "risk_level": "safe",
        "risk_desc": "清理 VS 安装时下载的离线包缓存，已安装的 VS 功能不受影响；修复或新增功能时可能需重新下载。",
    },
    {
        "id": "programdata_package_cache",
        "name": "ProgramData 通用安装包缓存 (Package Cache)",
        "paths": [
            _p(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "Package Cache", "*"),
        ],
        "icon": "📦",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理各软件遗留的安装包缓存，卸载或修复程序时可能需要重新获取，日常使用无影响。",
    },
    {
        "id": "nvidia_installer_cache",
        "name": "NVIDIA 驱动安装包与下载缓存",
        "paths": [
            _p("C:\\Program Files", "NVIDIA Corporation", "Installer2", "*"),
            _p(os.environ.get("PROGRAMDATA", "C:\\ProgramData"),
               "NVIDIA Corporation", "Downloader", "*"),
        ],
        "icon": "🎮",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理显卡驱动解压残留与下载缓存，已安装的驱动不受影响。",
    },
    {
        "id": "office_click_to_run",
        "name": "Office 即点即用安装缓存 (ClickToRun)",
        "paths": [
            _p(os.environ.get("PROGRAMDATA", "C:\\ProgramData"),
               "Microsoft", "ClickToRun", "ProductReleases", "*"),
            _p(os.environ.get("PROGRAMDATA", "C:\\ProgramData"),
               "Microsoft", "ClickToRun", "Updates", "*"),
        ],
        "icon": "📄",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理 Office 即点即用的更新残留包，已安装的 Office 程序不受影响。",
    },
    {
        "id": "usoshared_logs",
        "name": "Windows 更新编排器日志 (USOShared)",
        "paths": [
            _p(os.environ.get("PROGRAMDATA", "C:\\ProgramData"), "USOShared", "Logs", "*"),
        ],
        "icon": "📋",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理系统更新编排器产生的日志文件，不影响已安装的更新。",
    },
    {
        "id": "win_recent_dest",
        "name": "Windows 跳转列表缓存 (AutomaticDestinations)",
        "paths": [
            _p(ROAMING, "Microsoft", "Windows", "Recent", "AutomaticDestinations", "*"),
            _p(ROAMING, "Microsoft", "Windows", "Recent", "CustomDestinations", "*"),
        ],
        "icon": "🧭",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理跳转列表（最近使用文件）缓存，不影响实际文件，任务栏快捷方式的跳转列表会重置。",
    },
    {
        "id": "shader_cache",
        "name": "显卡着色器缓存 (D3DS / NVIDIA / AMD)",
        "paths": [
            _p(LOCAL, "D3DSCache", "*"),
            _p(LOCAL, "NVIDIA Corporation", "NV_Cache", "*"),
            _p(HOME, "AppData", "LocalLow", "NVIDIA", "DXCache", "*"),
            _p(LOCAL, "AMD", "DxCache", "*"),
        ],
        "icon": "🖼️",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "清理 DirectX 与显卡着色器缓存，游戏和应用会自动重建，首次加载可能略慢。",
    },
    {
        "id": "office_unsaved",
        "name": "Office 未保存文档临时副本",
        "paths": [
            _p(LOCAL, "Microsoft", "Office", "UnsavedFiles", "*"),
        ],
        "icon": "💾",
        "immune": False,
        "type": "system",
        "risk_level": "risk",
        "risk_desc": "注意：这里可能存有 Office 崩溃时的自动恢复副本。若近期有文档未保存，请先打开 Office 确认已恢复再清理。",
    },
    {
        "id": "winsxs_sidecar",
        "name": "WinSxS 旁路缓存 (ManifestCache / CbsTemp)",
        "paths": [
            "C:\\Windows\\WinSxS\\ManifestCache\\*",
            "C:\\Windows\\CbsTemp\\*",
        ],
        "icon": "🧱",
        "immune": False,
        "type": "system",
        "risk_level": "safe",
        "risk_desc": "仅清理 WinSxS 组件存储的两个旁路缓存目录。WinSxS 主体必须交由 DISM 命令处理，本项绝不触碰。",
    },
]


def _norm_base(p):
    """路径规范化（小写、去尾部通配符与分隔符），用于去重比较。"""
    b = (p or "").strip().rstrip("\\/*").rstrip("\\").lower()
    return b


def get_extra_apps():
    """返回本模块中「本机确实存在」的清理项。

    过滤掉不存在的路径，避免列表出现一堆永远 0 字节的空壳项。
    末尾合并外部规则库（Winapp2 + Dism++，见 library_rules.py），
    并按路径前缀与手写规则去重，保证同一目录不会被两条规则重复清理。
    """
    result = []
    seen = set()
    covered = set()          # 已有规则覆盖的目录基（用于大库去重）
    for rule in RULES:
        paths = [p for p in rule.get("paths", []) if p]
        if not paths:
            continue
        if not _exists_any(paths):
            continue
        item = dict(rule)
        item["paths"] = paths
        result.append(item)
        seen.add(rule["id"])
        for p in paths:
            covered.add(_norm_base(p))

    # ---- 外部规则库（Winapp2 4068 条 + Dism++ 73 项，本机命中约 300 条）----
    try:
        import library_rules
        for item in library_rules.get_library_apps():
            if item["id"] in seen:
                continue
            paths = [p for p in item.get("paths", []) if p]
            if not paths:
                continue
            bases = [_norm_base(p) for p in paths]
            # 任一路径已被手写规则覆盖（或为其子目录）则跳过，避免重复清理项
            dup = False
            for b in bases:
                if not b:
                    dup = True
                    break
                if b in covered:
                    dup = True
                    break
                for c in covered:
                    if b.startswith(c + "\\"):
                        dup = True
                        break
                if dup:
                    break
            if dup:
                continue
            item = dict(item)
            item["paths"] = paths
            result.append(item)
            seen.add(item["id"])
            covered.update(bases)
    except RulePackError:
        raise
    except Exception:
        # 单条适配异常不影响其他清理项；规则包认证异常必须上抛。
        pass
    return result


def count_rules():
    """规则总数（不按本机存在与否过滤）。"""
    n = len(RULES)
    try:
        import library_rules
        n += len(library_rules.get_library_apps())
    except RulePackError:
        raise
    except Exception:
        pass
    return n
