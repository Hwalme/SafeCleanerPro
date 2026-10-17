# -*- coding: utf-8 -*-
"""ui_theme.py — 共享字体缓存与 emoji 相关的 Tk 性能处理

从 main.py 拆出，原因有二：
1. main.py 已接近 Pyarmor trial 的单脚本上限（约 42KB），拆分后每个脚本都在限额内；
2. 这些是全 UI 通用的底层设置，与窗口业务逻辑无关。

性能背景（实测于本机）
--------------------------------------------------------------------
CTkLabel 会按文字自动测量宽度来定尺寸。当文字含 emoji 时，Tk 会走
emoji 字体回退链，每遇到一个新的字形约 200ms（进程内第一次更是约 2.2s）。
主界面散布约 57 个不同 emoji，因此 build_ui() 曾阻塞主线程 18,400ms。

给 CTkLabel 显式传 width（单字形图标再传 height）可让 CustomTkinter
完全跳过文字测量：16 个图标由 5,853ms 降到 16ms。注意 width 只固定
外框，不会截断文字。
"""
import customtkinter as ctk

# 字体族不是性能杠杆。真正的原因是 Tk 为自动定尺寸而测量 emoji 文字，
# 而这一点靠给图标标签固定 width/height 来规避。
UI_FAMILY = "Microsoft YaHei"
MONO_FAMILY = "Consolas"

_FONT_CACHE = {}

# 单字形 CTkLabel 的外框。同时固定宽高才能让 Tk 跳过（对 emoji 极慢的）
# 文字测量。
ICON_W = 32
ICON_H = 30

# 含 emoji 的**文本**标签所用外框宽度。给了 width 就跳过文字测量，
# 而字符串本身不受影响。
EMOJI_LABEL_W = 320


def F(family=UI_FAMILY, size=12, weight="normal"):
    """返回该规格对应的共享 CTkFont。

    原先每个控件都自建 ctk.CTkFont(...)（共 50 次），按
    (family, size, weight) 缓存后只剩几十个对象，并减少了 build_ui
    期间的 Tk 往返。
    """
    if family == "Microsoft YaHei UI":
        family = UI_FAMILY
    key = (family, size, weight)
    font = _FONT_CACHE.get(key)
    if font is None:
        font = ctk.CTkFont(family=family, size=size, weight=weight)
        _FONT_CACHE[key] = font
    return font


_emoji_warmed = False


def warm_emoji_glyphs(widget=None):
    """在窗口显示前，先付掉 Tk 一次性的 emoji 回退初始化（约 2.2s）。

    只预热这一个字形：逐个预热每个字形反而要 ~200ms × N，比问题本身更糟。
    """
    global _emoji_warmed
    if _emoji_warmed:
        return
    try:
        lbl = ctk.CTkLabel(widget, text="\U0001F534", width=1, height=1)
        lbl.update_idletasks()
        lbl.destroy()
    except Exception:
        pass
    _emoji_warmed = True


def build_app_row(owner, app, idx):
    """为一个可清理项目创建一行，并把控件登记到 owner.app_rows 等映射里。

    从 main.py 搬过来：一是 main.py 受 Pyarmor trial 单脚本上限约束，
    二是这属于纯 UI 构建，和窗口业务状态无关。

    图标标签固定 width/height 是性能关键（见模块开头说明）。
    """
    row_frame = ctk.CTkFrame(
        owner.scroll_frame,
        fg_color="#111827" if idx % 2 == 0 else "#1f2937",
        corner_radius=6,
    )
    row_frame.pack(fill="x", padx=5, pady=4)

    left_container = ctk.CTkFrame(row_frame, fg_color="transparent")
    left_container.pack(side="left", fill="y", padx=5)

    if app["immune"]:
        lbl_lock = ctk.CTkLabel(
            left_container, width=ICON_W, height=ICON_H, text="\U0001F512",
            font=F(UI_FAMILY, 14, "normal"), text_color="#3b82f6",
        )
        lbl_lock.pack(side="left", padx=(15, 8))
    else:
        var = ctk.IntVar(value=1 if app["risk_level"] == "safe" else 0)
        owner.app_checkbox_vars[app["id"]] = var
        chk = ctk.CTkCheckBox(left_container, text="", variable=var, width=20, height=20)
        chk.pack(side="left", padx=(15, 8))
        owner.app_checkboxes[app["id"]] = chk

    lbl_icon = ctk.CTkLabel(
        left_container, text=app["icon"], width=ICON_W, height=ICON_H,
        font=F(UI_FAMILY, 22, "normal"),
    )
    lbl_icon.pack(side="left", padx=(6, 6), pady=10)

    lbl_name = ctk.CTkLabel(
        left_container, text=app["name"],
        font=F(UI_FAMILY, 14, "bold"), text_color="#f3f4f6",
    )
    lbl_name.pack(side="left", padx=6, pady=10)

    if not app["immune"]:
        btn_details = ctk.CTkButton(
            row_frame, text="\U0001F4C4 \u67E5\u770B\u6587\u4EF6",
            font=F(UI_FAMILY, 12, "normal"), width=90, height=28,
            fg_color="#1e293b", hover_color="#334155",
            command=lambda a=app: owner.show_file_viewer(a),
        )
        btn_details.pack(side="right", padx=(6, 15), pady=10)
    else:
        ctk.CTkLabel(row_frame, text="", width=90).pack(side="right", padx=(6, 15), pady=10)

    if app["immune"]:
        badge_text, badge_color, badge_bg = "\U0001F6E1\uFE0F \u9501\u5B9A\u4FDD\u62A4", "#3b82f6", "#172554"
    elif app["risk_level"] == "safe":
        badge_text, badge_color, badge_bg = "\U0001F9F9 \u5B89\u5168\u6E05\u7406", "#10b981", "#064e3b"
    else:
        badge_text, badge_color, badge_bg = "\u26A0\uFE0F \u98CE\u9669\u6E05\u7406", "#ef4444", "#450a0a"

    lbl_badge = ctk.CTkLabel(
        row_frame, text=badge_text, font=F(UI_FAMILY, 12, "bold"),
        text_color=badge_color, fg_color=badge_bg, corner_radius=4,
        width=100, height=26,
    )
    lbl_badge.pack(side="right", padx=8, pady=10)

    lbl_size = ctk.CTkLabel(
        row_frame, text="\u7B49\u5F85\u626B\u63CF...",
        font=F(MONO_FAMILY, 13, "normal"), text_color="#9ca3af",
    )
    lbl_size.pack(side="right", padx=8, pady=10)

    owner.app_rows[app["id"]] = {
        "size": lbl_size,
        "badge": lbl_badge,
        "frame": row_frame,
    }
