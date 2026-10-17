# -*- coding: utf-8 -*-
"""从本机已安装软件的 exe 提取真实图标 → PNG 字节（供 tk.PhotoImage 使用）。

纯 ctypes + PIL，不依赖 pywin32：
  SHDefExtractIconW 取 HICON → GetIconInfo/GetDIBits 读 BGRA 位图 → PIL 转 PNG。
取不到（软件没装/图标提取失败）返回 None，调用方退回 emoji 文本，不影响功能。
"""
import ctypes
import glob
import io
import os
from ctypes import wintypes

_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32
_shell32 = ctypes.windll.shell32

HOME = os.path.expanduser("~")
LOCAL = os.environ.get("LOCALAPPDATA", "") or ""

# 常见安装根（按用户本机实际情况：大量 AI IDE 装在 D:\Program Files）
_INSTALL_ROOTS = [
    r"D:\Program Files",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    os.path.join(LOCAL, "Programs"),
    os.path.join(LOCAL, "AnthropicClaude"),
]

# 迁移项 id → 安装目录/主程序关键字（best-effort，找不到就回退 emoji）
_ITEM_EXE_KEYWORDS = {
    "claude_code": ["claude"],
    "claude_desktop": ["claude"],
    "gemini": ["gemini", "antigravity"],
    "codex": ["codex", "openai"],
    "zcode": ["zcode"],
    "zcode_desktop": ["zcode"],
    "cursor": ["cursor"],
    "dot_cursor": ["cursor"],
    "windsurf": ["windsurf", "devin"],
    "dot_windsurf": ["windsurf"],
    "vsf_devin": ["windsurf", "devin"],
    "vsf_code": ["microsoft vs code", "vs code"],
    "trae": ["trae"],
    "vsf_trae": ["trae"],
    "dot_trae": ["trae"],
    "dot_trae_cn": ["trae"],
    "dot_trae_aicc": ["trae"],
    "ollama_models": ["ollama"],
    "hf_cache": ["huggingface"],
    "antigravity_cli": ["antigravity"],
    "vsf_antigravity": ["antigravity"],
    "vsf_antigravity_ide": ["antigravity"],
    "dot_antigravity_ide": ["antigravity"],
    "opencode": ["opencode"],
    "qwen_cli": ["qwen"],
    "dot_qwenworkcn": ["qwen"],
    "cherry_studio": ["cherry"],
    "ima": ["ima"],
    "doubao_desktop": ["doubao"],
    "minimax_desktop": ["minimax"],
    "dot_minimax": ["minimax"],
    "dot_kimi_work": ["kimi"],
    "dot_kimi_webbridge": ["kimi"],
    "vsf_codebuddy_cn": ["codebuddy"],
    "dot_codebuddy": ["codebuddy"],
    "dot_codebuddycn": ["codebuddy"],
    "vsf_comate": ["comate"],
    "dot_comate": ["comate"],
    "dot_comate_engine": ["comate"],
    "vsf_lingma": ["lingma"],
    "dot_lingma": ["lingma"],
    "vsf_qoder": ["qoder"],
    "dot_qoder": ["qoder"],
    "dot_qoder_cli": ["qoder"],
    "dot_qoder_cn": ["qoder"],
    "dot_workbuddy": ["workbuddy"],
}


class _ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wintypes.BOOL),
                ("xHotspot", wintypes.DWORD),
                ("yHotspot", wintypes.DWORD),
                ("hbmMask", wintypes.HBITMAP),
                ("hbmColor", wintypes.HBITMAP)]


class _BITMAP(ctypes.Structure):
    _fields_ = [("bmType", wintypes.LONG),
                ("bmWidth", wintypes.LONG),
                ("bmHeight", wintypes.LONG),
                ("bmWidthBytes", wintypes.LONG),
                ("bmPlanes", wintypes.WORD),
                ("bmBitsPixel", wintypes.WORD),
                ("bmBits", wintypes.LPVOID)]


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD),
                ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG),
                ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD),
                ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD),
                ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG),
                ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER),
                ("bmiColors", wintypes.DWORD * 3)]


# 句柄必须按 64 位指针传：不声明 argtypes 时 ctypes 默认按 32 位 int 处理，
# 句柄值超过 2^31 会 OverflowError（曾导致图标提取随机失败）。
_shell32.SHDefExtractIconW.argtypes = [
    wintypes.LPCWSTR, ctypes.c_int, wintypes.UINT,
    ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.HICON),
    wintypes.UINT]
_shell32.SHDefExtractIconW.restype = ctypes.c_long
_user32.GetIconInfo.argtypes = [wintypes.HICON, ctypes.POINTER(_ICONINFO)]
_user32.GetIconInfo.restype = wintypes.BOOL
_user32.DestroyIcon.argtypes = [wintypes.HICON]
_user32.DestroyIcon.restype = wintypes.BOOL
_user32.GetDC.argtypes = [wintypes.HWND]
_user32.GetDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_user32.ReleaseDC.restype = ctypes.c_int
_gdi32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID]
_gdi32.GetObjectW.restype = ctypes.c_int
_gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT,
                             wintypes.UINT, wintypes.LPVOID,
                             ctypes.POINTER(_BITMAPINFO), wintypes.UINT]
_gdi32.GetDIBits.restype = ctypes.c_int
_gdi32.DeleteObject.argtypes = [wintypes.HANDLE]
_gdi32.DeleteObject.restype = wintypes.BOOL


def hicon_to_png_bytes(hicon):
    """HICON → 18x18 PNG 字节。失败返回 None。"""
    info = _ICONINFO()
    if not _user32.GetIconInfo(hicon, ctypes.byref(info)):
        return None
    try:
        bmp = _BITMAP()
        if not _gdi32.GetObjectW(info.hbmColor, ctypes.sizeof(_BITMAP),
                                 ctypes.byref(bmp)):
            return None
        w, h = bmp.bmWidth, bmp.bmHeight
        if w <= 0 or h <= 0 or w > 512 or h > 512:
            return None
        hdc = _user32.GetDC(0)
        try:
            bi = _BITMAPINFO()
            bi.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
            bi.bmiHeader.biWidth = w
            bi.bmiHeader.biHeight = -h          # 自上而下
            bi.bmiHeader.biPlanes = 1
            bi.bmiHeader.biBitCount = 32
            bi.bmiHeader.biCompression = 0      # BI_RGB
            buf = ctypes.create_string_buffer(w * h * 4)
            if not _gdi32.GetDIBits(hdc, info.hbmColor, 0, h, buf,
                                    ctypes.byref(bi), 0):
                return None
        finally:
            _user32.ReleaseDC(0, hdc)
        from PIL import Image
        img = Image.frombuffer("RGBA", (w, h), buf.raw, "raw", "BGRA", 0, 1)
        img = img.resize((18, 18), Image.LANCZOS)
        out = io.BytesIO()
        img.save(out, "PNG")
        return out.getvalue()
    except Exception:
        return None
    finally:
        if info.hbmColor:
            _gdi32.DeleteObject(info.hbmColor)
        if info.hbmMask:
            _gdi32.DeleteObject(info.hbmMask)


_PNG_CACHE = {}


def extract_exe_png(exe_path, size=48):
    """提取 exe 第一个图标 → PNG 字节；失败返回 None（结果缓存）。"""
    key = (str(exe_path), size)
    if key in _PNG_CACHE:
        return _PNG_CACHE[key]
    try:
        hicon = wintypes.HICON()
        # LOWORD(nIconSize)=大图标尺寸
        if _shell32.SHDefExtractIconW(str(exe_path), 0, 0,
                                      ctypes.byref(hicon), None,
                                      size & 0xFFFF) != 0:
            _PNG_CACHE[key] = None
            return None
        try:
            png = hicon_to_png_bytes(hicon)
            _PNG_CACHE[key] = png
            return png
        finally:
            _user32.DestroyIcon(hicon)
    except Exception:
        return None


def find_app_exe(keywords):
    """在常见安装根下按关键字找主程序 exe。

    打分制：目录名/文件名与关键字越贴合越好；Update/Installer/卸载器/
    崩溃上报等辅助程序一律降权；同级再比体积（主程序通常最大）。
    """
    best = None          # (score, size, path)
    for root in _INSTALL_ROOTS:
        if not os.path.isdir(root):
            continue
        scan_dirs = []
        try:
            root_base = os.path.basename(root.rstrip("\\/")).lower()
            if any(k in root_base for k in keywords):
                scan_dirs.append(root)          # 根本身就是目标（如 AnthropicClaude）
            for name in os.listdir(root):
                low = name.lower()
                if any(k in low for k in keywords):
                    scan_dirs.append(os.path.join(root, name))
        except OSError:
            continue
        for d in scan_dirs:
            if not os.path.isdir(d):
                continue
            cands = []
            for pat in (os.path.join(d, "*.exe"),
                        os.path.join(d, "app*", "*.exe"),
                        os.path.join(d, "bin", "*.exe")):
                cands += glob.glob(pat)
            dlow = os.path.basename(d.rstrip("\\/")).lower()
            for exe in cands:
                try:
                    size = os.path.getsize(exe)
                except OSError:
                    continue
                elow = os.path.basename(exe).lower()
                score = 0
                stem = os.path.splitext(elow)[0]
                if any(k == stem or stem in k or k in stem for k in keywords):
                    score += 100                # 主程序名与关键字直接对应
                if any(k == stem for k in keywords):
                    score += 160                # 文件名精确等于关键字（ollama.exe）
                if dlow in keywords or any(k == dlow for k in keywords):
                    score += 40                 # 安装目录名精确等于关键字
                score += min(size // (1024 * 1024), 50)   # 大文件加分（主程序）
                for bad in ("update", "installer", "setup", "uninstall",
                            "crashpad", "crash", "modifier", "unins",
                            "helper", "updater"):
                    if bad in elow:
                        score -= 200            # 辅助程序强降权
                if best is None or score > best[0]:
                    best = (score, size, exe)
    return best[2] if best else None


def resolve_item_png(item_id):
    """迁移项 id → 该软件真实图标 PNG 字节；找不到返回 None。"""
    kws = _ITEM_EXE_KEYWORDS.get(item_id)
    if not kws:
        return None
    exe = find_app_exe(kws)
    if not exe:
        return None
    return extract_exe_png(exe)
