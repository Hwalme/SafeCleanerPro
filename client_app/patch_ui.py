# -*- coding: utf-8 -*-
"""向 ui_theme.py 追加 DWM 窗口主题与弹窗前置助手。"""
import io

NL = chr(10)
P = "ui_theme.py"

s = io.open(P, encoding="utf-8").read()
if "def apply_window_chrome" in s:
    print("already present")
    raise SystemExit(0)

helper = NL + NL + '''# ----------------------------------------------------------------------
# DWM 窗口主题：深色标题栏 + 比背景深一档的标题栏色 + Win11 Mica 半透明
# ----------------------------------------------------------------------
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_BORDER_COLOR = 34
_DWMWA_CAPTION_COLOR = 35
_DWMWA_SYSTEMBACKDROP_TYPE = 38


def _colorref(hex_color):
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    return (b << 16) | (g << 8) | r


def apply_window_chrome(win, caption_hex="#060a12"):
    """标题栏跟随应用主题：比背景 #0b1220 再深一档；Win11 尝试 Mica 材质。"""
    import ctypes
    try:
        win.update_idletasks()
    except Exception:
        pass

    def _apply():
        try:
            hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        except Exception:
            return
        if not hwnd:
            return
        dwm = ctypes.windll.dwmapi
        dark = ctypes.c_int(_DWMWA_USE_IMMERSIVE_DARK_MODE)
        dwm.DwmSetWindowAttribute(hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE,
                                  ctypes.byref(dark), 4)
        cap = ctypes.c_int(_colorref(caption_hex))
        dwm.DwmSetWindowAttribute(hwnd, _DWMWA_CAPTION_COLOR,
                                  ctypes.byref(cap), 4)
        bord = ctypes.c_int(_colorref("#16213c"))
        dwm.DwmSetWindowAttribute(hwnd, _DWMWA_BORDER_COLOR,
                                  ctypes.byref(bord), 4)
        back = ctypes.c_int(2)          # 2 = Mica（系统主题半透明材质）
        dwm.DwmSetWindowAttribute(hwnd, _DWMWA_SYSTEMBACKDROP_TYPE,
                                  ctypes.byref(back), 4)

    _apply()
    try:
        win.after(260, _apply)          # 首帧后二次确认（窗口映射时机差异）
    except Exception:
        pass


def popup_front(win, master):
    """弹窗稳定前置：短暂置顶抢焦点，随后落回正常层。"""
    try:
        win.transient(master)
    except Exception:
        pass
    try:
        win.attributes("-topmost", True)
    except Exception:
        pass

    def _front():
        try:
            win.lift()
            win.focus_force()
        except Exception:
            pass

    try:
        win.after(10, _front)
        win.after(160, _front)
        win.after(500, lambda: win.attributes("-topmost", False))
    except Exception:
        pass
'''
s = s.rstrip(NL) + helper + NL
io.open(P, "w", encoding="utf-8", newline=NL).write(s)
print("ui_theme helpers added")
