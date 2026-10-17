# -*- coding: utf-8 -*-
"""PPSAI Cleaner desktop presentation. Engine and persistence live elsewhere."""
import os
import sys
import tkinter as tk
from collections import deque

import customtkinter as ctk
from PIL import Image, ImageDraw

BG = "#101419"
RAIL = BG
PANEL = "#161C23"
CARD = "#1D252E"
LINE = "#2A3541"
TEXT = "#F0F4F7"
DIM = "#A3AFBD"
MUTED = "#8795A5"
ACCENT = "#8CDEEF"
HOVER = "#B1ECF7"
TINT = "#203640"
OK = "#91D5B6"
WARN = "#E7BA7A"
ERR = "#ECA0A6"
FAMILY = "Microsoft YaHei UI"


def asset(name):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", "brand", name)


def font(size=13, bold=False):
    return ctk.CTkFont(family=FAMILY, size=size, weight="bold" if bold else "normal")


def image(name, size):
    with Image.open(asset(name)) as source:
        im = source.convert("RGBA")
    return ctk.CTkImage(light_image=im, dark_image=im, size=size)


_icons = {}


def install_theme():
    """Native controls use the same palette even when no explicit color is passed."""
    changes = {
        "CTk": dict(fg_color=BG),
        "CTkToplevel": dict(fg_color=BG),
        "CTkFrame": dict(fg_color=PANEL, top_fg_color=CARD, border_color=LINE, corner_radius=12),
        "CTkLabel": dict(text_color=TEXT),
        "CTkButton": dict(fg_color=CARD, hover_color=LINE, text_color=TEXT,
                          text_color_disabled=MUTED, border_color=LINE, corner_radius=8),
        "CTkEntry": dict(fg_color=RAIL, border_color=LINE, text_color=TEXT, placeholder_text_color=MUTED),
        "CTkCheckBox": dict(fg_color=ACCENT, hover_color=TINT, border_color=MUTED,
                            checkmark_color=BG, text_color=TEXT, corner_radius=4),
        "CTkProgressBar": dict(fg_color=CARD, progress_color=ACCENT),
        "CTkOptionMenu": dict(fg_color=CARD, button_color=CARD, button_hover_color=LINE, text_color=TEXT),
        "CTkTextbox": dict(fg_color=RAIL, text_color=DIM, border_color=LINE),
        "CTkScrollbar": dict(fg_color="transparent", button_color=LINE, button_hover_color=MUTED),
    }
    for cls, values in changes.items():
        ctk.ThemeManager.theme[cls].update(values)


def icon(name, color=DIM, size=20):
    """Small, consistently stroked icons; no font fallback or emoji measuring."""
    key = (name, color, size)
    if key in _icons:
        return _icons[key]
    scale = 4
    im = Image.new("RGBA", (24 * scale, 24 * scale))
    d = ImageDraw.Draw(im)
    def line(points):
        d.line([(int(x * scale), int(y * scale)) for x, y in points], fill=color,
               width=2 * scale, joint="curve")
    def rect(box, radius=1):
        d.rounded_rectangle(tuple(int(x * scale) for x in box), radius=radius * scale,
                            outline=color, width=2 * scale)
    if name == "clean":
        line([(4, 6), (20, 6)]); line([(7, 3), (17, 3)])
        rect((5, 6, 19, 21), 3); line([(9, 10), (9, 17)]); line([(15, 10), (15, 17)])
    elif name == "scan":
        d.ellipse((4*scale, 3*scale, 17*scale, 16*scale), outline=color, width=2*scale)
        line([(16, 15), (21, 21)])
    elif name == "layers":
        for y in (5, 11, 17):
            line([(3, y), (12, y+4), (21, y), (12, y-4), (3, y)])
    elif name == "copy":
        rect((8, 8, 21, 21), 2); line([(16, 5), (16, 3), (3, 3), (3, 16), (5, 16)])
    elif name == "move":
        line([(3, 7), (18, 7), (14, 3)]); line([(18, 7), (14, 11)])
        line([(21, 17), (6, 17), (10, 13)]); line([(6, 17), (10, 21)])
    elif name == "shield":
        line([(12, 2), (21, 6), (20, 15), (17, 19), (12, 22), (7, 19), (4, 15), (3, 6), (12, 2)])
        line([(8, 12), (11, 15), (17, 9)])
    elif name == "disk":
        rect((3, 5, 21, 19), 3); line([(4, 14), (20, 14)])
        d.ellipse((16*scale, 16*scale, 18*scale, 18*scale), fill=color)
    elif name == "settings":
        for x, y in ((7, 7), (17, 17)):
            line([(x, 3), (x, 21)]); rect((x-3, y-2, x+3, y+2), 1)
    elif name == "log":
        rect((4, 3, 20, 21), 2)
        for y in (8, 12, 16): line([(8, y), (16, y)])
    elif name == "check":
        line([(5, 12), (10, 17), (20, 6)])
    elif name == "arrow":
        line([(4, 12), (20, 12), (14, 6)]); line([(20, 12), (14, 18)])
    else:
        rect((4, 4, 20, 20), 3)
    im = im.resize((size, size), Image.Resampling.LANCZOS)
    result = ctk.CTkImage(light_image=im, dark_image=im, size=(size, size))
    _icons[key] = result
    return result


def label(parent, text, size=13, color=TEXT, bold=False, **kw):
    return ctk.CTkLabel(parent, text=text, font=font(size, bold), text_color=color, **kw)


def button(parent, text, command, primary=False, **kw):
    defaults = dict(height=36, corner_radius=8, font=font(13, primary),
                    fg_color=ACCENT if primary else CARD,
                    hover_color=HOVER if primary else LINE,
                    text_color=BG if primary else TEXT,
                    text_color_disabled=MUTED, command=command)
    defaults.update(kw)
    b = ctk.CTkButton(parent, text=text, **defaults)
    b._canvas.configure(takefocus=1)
    b._canvas.bind("<Return>", lambda e: b.invoke())
    b._canvas.bind("<space>", lambda e: b.invoke())
    b._canvas.bind("<FocusIn>", lambda e: b.configure(border_width=1, border_color=ACCENT))
    b._canvas.bind("<FocusOut>", lambda e: b.configure(border_width=0))
    return b


def popup_header(parent, title, subtitle):
    """Shared branded heading for secondary native workspaces."""
    head = ctk.CTkFrame(parent, fg_color="transparent")
    head.pack(fill="x", padx=24, pady=(22, 18))
    try:
        mark = image("app-mark-transparent.png", (46, 46))
        badge = ctk.CTkLabel(head, text="", image=mark)
        badge.pack(side="left", padx=(0, 14))
    except OSError:
        pass
    titles = ctk.CTkFrame(head, fg_color="transparent")
    titles.pack(side="left", fill="x", expand=True)
    label(titles, title, 23, bold=True, anchor="w").pack(fill="x")
    label(titles, subtitle, 12, DIM, anchor="w").pack(fill="x", pady=(2, 0))
    return head


def build_ui(owner, version):
    if getattr(owner, "_brand_built", False):
        return
    owner._brand_built = True
    owner.configure(fg_color=BG)
    owner.grid_columnconfigure(0, weight=0, minsize=200)
    owner.grid_columnconfigure(1, weight=1, minsize=860)
    owner.grid_rowconfigure(0, weight=1)
    owner._tool_windows = {}
    owner.search_var = tk.StringVar()
    owner._search_job = None
    owner.log_history = getattr(owner, "log_history", deque(maxlen=500))

    rail = owner.sidebar_frame = ctk.CTkFrame(owner, width=200, corner_radius=0, fg_color=RAIL)
    rail.grid(row=0, column=0, sticky="nsew")
    rail.grid_propagate(False)
    rail.grid_columnconfigure(0, weight=1)
    rail.grid_rowconfigure(9, weight=1)
    brand = ctk.CTkFrame(rail, fg_color="transparent")
    brand.grid(row=0, column=0, sticky="ew", padx=18, pady=(28, 28))
    try:
        owner._brand_mark = image("app-mark-transparent.png", (48, 48))
        ctk.CTkLabel(brand, text="", image=owner._brand_mark, width=48).pack(side="left", padx=(0, 9))
    except OSError:
        pass
    word = ctk.CTkFrame(brand, fg_color="transparent")
    word.pack(side="left")
    owner.logo_label = label(word, "PPSAI", 20, bold=True)
    owner.logo_label.pack(anchor="w")
    owner.sub_logo = label(word, "Cleaner", 13, DIM)
    owner.sub_logo.pack(anchor="w")

    owner.nav_buttons = {}
    nav = [("safe", "安全清理", "scan"), ("risk", "深度清理", "layers"),
           ("dedup", "重复文件", "copy"), ("migrate", "C盘迁移", "move")]
    for row, (key, text, glyph) in enumerate(nav, 1):
        b = button(rail, text, lambda k=key: navigate(owner, k), height=44,
                   fg_color="transparent", hover_color=PANEL, text_color=DIM,
                   image=icon(glyph), anchor="w", width=164, compound="left", border_spacing=12)
        b.grid(row=row, column=0, sticky="ew", padx=14, pady=3)
        owner.nav_buttons[key] = b
    owner.btn_dedup = owner.nav_buttons["dedup"]
    owner.btn_migrate = owner.nav_buttons["migrate"]

    support = ctk.CTkFrame(rail, fg_color="transparent")
    support.grid(row=10, column=0, padx=20, pady=(12, 20), sticky="ew")
    owner.btn_settings = button(support, "设置与关于", lambda: navigate(owner, "settings"),
                                 fg_color="transparent", image=icon("settings", DIM, 18),
                                 anchor="w", width=156)
    owner.btn_settings.pack(fill="x")
    owner.nav_buttons["settings"] = owner.btn_settings
    label(support, f"v{version}", 10, MUTED).pack(anchor="w", pady=(12, 0))

    main = owner.main_frame = ctk.CTkFrame(owner, fg_color=BG, corner_radius=0)
    main.grid(row=0, column=1, sticky="nsew")
    main.grid_columnconfigure(0, weight=1, minsize=500)
    main.grid_columnconfigure(1, weight=0, minsize=284)
    main.grid_rowconfigure(4, weight=1)
    head = owner.header_frame = ctk.CTkFrame(main, fg_color="transparent")
    head.grid(row=0, column=0, columnspan=2, padx=28, pady=(22, 12), sticky="ew")
    head.grid_columnconfigure(0, weight=1)
    owner.main_title = label(head, "让工作空间，轻盈如初。", 28, bold=True, anchor="w")
    owner.main_title.grid(row=0, column=0, sticky="w")
    owner.main_subtitle = label(head, "扫描缓存与临时文件，重要内容始终由你掌控。", 13, DIM, anchor="w")
    owner.main_subtitle.grid(row=1, column=0, sticky="w", pady=(5, 0))
    button(head, "🛡 受保护项在深度清理", lambda: navigate(owner, "risk"), width=190, height=34,
           fg_color=TINT, text_color=ACCENT, image=icon("shield", ACCENT, 17)).grid(row=0, column=1, rowspan=2, padx=(16, 0))

    stats = ctk.CTkFrame(main, fg_color="transparent")
    stats.grid(row=1, column=0, columnspan=2, sticky="ew", padx=28, pady=(0, 12))
    for col in range(3): stats.grid_columnconfigure(col, weight=1, uniform="metrics")
    for col, (name, title, color, note) in enumerate([
        ("scanned", "扫描发现", TEXT, "安全扫描与深度扫描合计"),
        ("immune", "已保护内容", ACCENT, "系统免疫与手动上锁"),
        ("cleaned", "本次已释放", OK, "本次会话累计释放空间")]):
        box = ctk.CTkFrame(stats, fg_color="transparent", corner_radius=0)
        box.grid(row=0, column=col, sticky="nsew", padx=(0 if col == 0 else 24, 0))
        setattr(owner, "card_" + name, box)
        label(box, title, 12, DIM, anchor="w").pack(fill="x")
        val = label(box, "0 B", 29, color, True, anchor="w")
        val.pack(fill="x", pady=(2, 2))
        setattr(owner, "lbl_" + name + "_val", val)
        detail = label(box, note, 10, MUTED, anchor="w")
        detail.pack(fill="x")
        setattr(owner, "lbl_" + name + "_breakdown", detail)
    ctk.CTkFrame(stats, height=1, fg_color=LINE).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(10, 0))

    drive_wrap = ctk.CTkFrame(main, fg_color="transparent")
    drive_wrap.grid(row=2, column=0, sticky="ew", padx=(28, 16), pady=(0, 8))
    drive_heading = ctk.CTkFrame(drive_wrap, fg_color="transparent")
    drive_heading.pack(fill="x", pady=(0, 8))
    label(drive_heading, "扫描范围", 13, bold=True).pack(side="left")
    button(drive_heading, "下一组", lambda: owner.drive_bar._parent_canvas.xview_scroll(1, "pages"),
           width=66, height=24, font=font(10), fg_color="transparent", text_color=DIM).pack(side="right")
    button(drive_heading, "上一组", lambda: owner.drive_bar._parent_canvas.xview_scroll(-1, "pages"),
           width=66, height=24, font=font(10), fg_color="transparent", text_color=DIM).pack(side="right")
    owner.drive_bar = ctk.CTkScrollableFrame(drive_wrap, orientation="horizontal", height=76,
                                          fg_color="transparent", corner_radius=0,
                                          scrollbar_button_color=LINE, scrollbar_button_hover_color=CARD)
    owner.drive_bar.pack(fill="x")
    owner.drive_cards = {}
    import shutil
    for idx, letter in enumerate(owner.detected_drives):
        card = ctk.CTkFrame(owner.drive_bar, width=152, height=70, corner_radius=9,
                           fg_color=PANEL, border_color=LINE, border_width=1)
        card.grid(row=0, column=idx, padx=(0, 8), sticky="ns")
        card.pack_propagate(False)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(8, 0))
        letter_label = label(top, f"{letter}:", 15, bold=True)
        letter_label.pack(side="left")
        check = label(top, "", 12, ACCENT)
        check.pack(side="right")
        try:
            usage = shutil.disk_usage(f"{letter}:\\")
            pct = usage.used / usage.total if usage.total else 0
            cap = f"可用 {usage.free / 1024**3:.0f} / {usage.total / 1024**3:.0f} GB"
        except OSError:
            pct, cap = 0, "磁盘暂不可用"
        label(card, cap, 10, DIM).pack(anchor="w", padx=12)
        bar = ctk.CTkProgressBar(card, height=3, fg_color=LINE,
                                 progress_color=WARN if pct > .85 else ACCENT)
        bar.pack(fill="x", padx=12, pady=(4, 7)); bar.set(pct)
        owner.drive_cards[letter] = {"card": card, "letter": letter_label, "check": check}
        def bind_disk(w, lt=letter):
            w.bind("<Button-1>", lambda e: toggle_drive(owner, lt))
            for child in w.winfo_children():
                if isinstance(child, (ctk.CTkFrame, ctk.CTkLabel, ctk.CTkProgressBar)):
                    bind_disk(child, lt)
        bind_disk(card)
        card._canvas.configure(takefocus=1)
        card._canvas.bind("<Return>", lambda e, lt=letter: toggle_drive(owner, lt))
        card._canvas.bind("<space>", lambda e, lt=letter: toggle_drive(owner, lt))
        def focus_disk(e, c=card, index=idx):
            c.configure(border_width=2)
            canvas = owner.drive_bar._parent_canvas
            canvas.xview_moveto(index / max(1, len(owner.detected_drives)))
        card._canvas.bind("<FocusIn>", focus_disk)
        card._canvas.bind("<FocusOut>", lambda e, c=card: c.configure(border_width=1))
    refresh_drives(owner)

    ctrl = owner.list_ctrl_bar = ctk.CTkFrame(main, fg_color="transparent")
    ctrl.grid(row=3, column=0, sticky="ew", padx=(28, 16), pady=(0, 10))
    ctrl.grid_columnconfigure(0, weight=1)
    owner.search_entry = ctk.CTkEntry(ctrl, textvariable=owner.search_var, placeholder_text="搜索项目名称",
                                     height=34, fg_color=PANEL, border_color=LINE, border_width=1,
                                     text_color=TEXT, placeholder_text_color=MUTED, font=font(12))
    owner.search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
    owner.sort_mode_var = tk.StringVar(value="category")
    def sort_changed(v):
        owner.sort_mode_var.set("category" if v == "按类别" else "size")
        if not busy(owner): owner.render_scroll_list()
    owner.sort_menu = ctk.CTkOptionMenu(ctrl, values=["按类别", "按容量"], width=105, height=34,
                                       font=font(12), fg_color=CARD, button_color=CARD,
                                       button_hover_color=LINE, text_color=DIM, command=sort_changed)
    owner.sort_menu.grid(row=0, column=1)
    choices = ctk.CTkFrame(ctrl, fg_color="transparent")
    choices.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    owner.btn_select_all_apps = button(choices, "全选", owner.select_all_apps, width=58, height=28,
                                       fg_color="transparent", text_color=DIM)
    owner.btn_select_all_apps.pack(side="left")
    owner.btn_deselect_all_apps = button(choices, "取消选择", owner.deselect_all_apps, width=80, height=28,
                                         fg_color="transparent", text_color=DIM)
    owner.btn_deselect_all_apps.pack(side="left", padx=4)
    owner.show_all_items = False
    owner.showall_var = tk.BooleanVar(value=False)
    def showall():
        owner.show_all_items = bool(owner.showall_var.get())
        if not busy(owner): owner.render_scroll_list()
    owner.chk_showall = ctk.CTkCheckBox(choices, text="显示空项目", variable=owner.showall_var,
                                     command=showall, width=114, height=26, checkbox_width=16,
                                     checkbox_height=16, corner_radius=4, fg_color=ACCENT,
                                     checkmark_color=BG, border_color=MUTED, text_color=DIM,
                                     hover_color=TINT, font=font(11))
    owner.chk_showall.pack(side="right")
    owner.search_var.trace_add("write", lambda *_: schedule_search(owner))
    owner.scroll_frame = ctk.CTkScrollableFrame(main, fg_color=PANEL, corner_radius=12,
                                               scrollbar_button_color=LINE, scrollbar_button_hover_color=MUTED)
    owner.scroll_frame.grid(row=4, column=0, sticky="nsew", padx=(28, 16), pady=(0, 16))
    owner.app_rows = {}; owner.app_checkboxes = {}; owner.app_checkbox_vars = {}
    owner.app_expand_btns = {}; owner._row_queue = []; owner._row_index = 0
    owner._render_job = None; owner._rows_started = False
    owner._show_placeholder()

    detail = owner.detail_panel = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=12, width=268)
    detail.grid(row=2, column=1, rowspan=3, sticky="nsew", padx=(0, 28), pady=(0, 16))
    detail.grid_propagate(False)
    detail.grid_columnconfigure(0, weight=1); detail.grid_rowconfigure(1, weight=1)
    owner.detail_title = label(detail, "清理说明", 14, bold=True, anchor="w")
    owner.detail_title.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 10))
    owner.detail_body = ctk.CTkScrollableFrame(detail, fg_color="transparent",
                                            scrollbar_button_color=LINE, scrollbar_button_hover_color=MUTED)
    owner.detail_body.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 10))
    show_intro(owner)

    dock = owner.control_frame = ctk.CTkFrame(main, fg_color=PANEL, corner_radius=12, height=92)
    dock.grid(row=5, column=0, columnspan=2, sticky="ew", padx=28, pady=(0, 18))
    dock.grid_propagate(False); dock.grid_columnconfigure(0, weight=1)
    owner.selection_label = label(dock, "选择磁盘，开始第一次扫描", 13, bold=True, anchor="w")
    owner.selection_label.grid(row=0, column=0, sticky="ew", padx=18, pady=(14, 0))
    owner.lbl_progress_info = label(dock, "扫描只分析文件，清理会在你确认后执行。", 11, DIM, anchor="w")
    owner.lbl_progress_info.grid(row=1, column=0, sticky="ew", padx=18, pady=(0, 6))
    owner.btn_rescan = button(dock, "重新扫描", lambda: rescan(owner), width=100, height=40)
    owner.btn_rescan.grid(row=0, column=1, rowspan=2, padx=(10, 8))
    owner.btn_action = button(dock, "开始扫描", owner.on_action_click, True, width=156, height=40,
                               image=icon("arrow", BG, 18), compound="right")
    owner.btn_action.grid(row=0, column=2, rowspan=2, padx=(0, 18))
    owner.btn_deep = button(dock, "开始深度扫描", owner.on_deep_click, True, width=156, height=40)
    owner.btn_deep.grid(row=0, column=2, rowspan=2, padx=(0, 18)); owner.btn_deep.grid_remove()
    owner.progress_bar = ctk.CTkProgressBar(dock, height=3, corner_radius=0, fg_color=CARD, progress_color=ACCENT)
    owner.progress_bar.grid(row=2, column=0, columnspan=3, sticky="ew", padx=18, pady=(0, 12))
    owner.progress_bar.set(0)

    footer = ctk.CTkFrame(main, fg_color="transparent", height=25)
    footer.grid(row=6, column=0, columnspan=2, sticky="ew", padx=28, pady=(0, 10))
    owner.scope_label = label(footer, "", 10, MUTED)
    owner.scope_label.pack(side="left")
    button(footer, "活动记录", lambda: show_activity(owner), height=24, width=84,
           fg_color="transparent", text_color=DIM, font=font(10)).pack(side="right")
    owner._active_page = "safe"
    owner._brand_layout_width = None
    owner.bind("<Control-f>", lambda e: owner.search_entry.focus_set())
    owner.bind("<Control-1>", lambda e: navigate(owner, "safe"))
    owner.bind("<Control-2>", lambda e: navigate(owner, "risk"))
    owner.bind("<F5>", lambda e: rescan(owner))
    owner.protocol("WM_DELETE_WINDOW", lambda: request_close(owner))
    owner._set_buttons()
    owner.after(200, lambda: refresh_live(owner))
    owner.flush_logs()


def busy(owner):
    return owner.safe_state in ("scanning", "cleaning") or owner.risk_state in ("scanning", "cleaning")


def tools_busy(owner, excluding=None):
    return any(w is not excluding and w is not None and w.winfo_exists() and
               any(getattr(w, state, False) for state in ("scanning", "cleaning", "working", "deleting"))
               for w in getattr(owner, "_tool_windows", {}).values())


def workspace_available(window):
    owner = getattr(window, "master_app", window.master)
    if busy(owner) or tools_busy(owner, excluding=window):
        from tkinter import messagebox
        messagebox.showinfo("PPSAI Cleaner", "另一项空间任务正在进行，完成后再开始此操作。", parent=window)
        return False
    return True


def toggle_drive(owner, letter):
    if busy(owner): return
    var = owner.drive_vars[letter]
    var.set(0 if var.get() else 1)
    refresh_drives(owner)
    owner.on_drive_changed()
    owner._set_buttons()


def refresh_drives(owner):
    for letter, widgets in owner.drive_cards.items():
        selected = bool(owner.drive_vars[letter].get())
        widgets["card"].configure(fg_color=TINT if selected else PANEL,
                                   border_color=ACCENT if selected else LINE)
        widgets["letter"].configure(text_color=ACCENT if selected else TEXT)
        widgets["check"].configure(text="已选" if selected else "")


def schedule_search(owner):
    if owner._search_job:
        owner.after_cancel(owner._search_job)
    def run():
        owner._search_job = None
        if not busy(owner): owner.render_scroll_list()
    owner._search_job = owner.after(200, run)


def navigate(owner, key):
    if key in ("dedup", "migrate"):
        open_tool(owner, key)
        return
    owner._active_page = key
    settings = getattr(owner, "settings_frame", None)
    if key == "settings":
        owner.main_frame.grid_remove()
        show_settings(owner)
    else:
        if settings is not None: settings.grid_remove()
        owner.main_frame.grid()
        owner.current_view = key
        titles = {"safe": ("让工作空间，轻盈如初。", "扫描缓存与临时文件，重要内容始终由你掌控。"),
                  "risk": ("把每一份空间，看得更清楚。", "受保护项也在这里：默认不选中，支持上锁与解锁。")}
        title, sub = titles.get(key, titles["risk"])
        owner.main_title.configure(text=title); owner.main_subtitle.configure(text=sub)
        if getattr(owner, key + "_state") == "idle" and not owner.search_var.get() and not owner.show_all_items:
            # Rebuild through the normal queue to keep selection state and pending jobs coherent.
            owner.render_scroll_list()
            show_intro(owner)
        else:
            owner.render_scroll_list(); show_intro(owner)
        owner._set_buttons()
    for page, b in owner.nav_buttons.items():
        selected = page == key
        _configure_if_changed(b, fg_color=TINT if selected else "transparent",
                              text_color=ACCENT if selected else DIM)


def open_tool(owner, key):
    old = owner._tool_windows.get(key)
    if old is not None and old.winfo_exists():
        old.deiconify(); old.lift(); old.focus_force(); return
    if busy(owner) or tools_busy(owner):
        owner.lbl_progress_info.configure(text="请等待当前任务完成，再打开其他空间工具。", text_color=WARN)
        return
    if key == "dedup":
        from dedup_ui import DedupWindow
        win = DedupWindow(owner)
    elif key == "migrate":
        from migrate_ui import MemoryMigrateWindow
        win = MemoryMigrateWindow(owner)
    else:
        from deep_ui import DeepOptimizeWindow
        win = DeepOptimizeWindow(owner)
    owner._tool_windows[key] = win
    original_close = win._on_close if hasattr(win, "_on_close") else win.destroy
    def close():
        if any(getattr(win, state, False) for state in ("scanning", "cleaning", "working", "deleting")):
            from tkinter import messagebox
            messagebox.showinfo("PPSAI Cleaner", "任务仍在进行，请等待完成后关闭窗口。", parent=win)
            return
        original_close()
    win.protocol("WM_DELETE_WINDOW", close)


def rescan(owner):
    if owner.current_view not in ("safe", "risk") or busy(owner) or tools_busy(owner) or not owner.get_selected_drives(): return
    owner.start_scan(owner.current_view)


def _configure_if_changed(widget, **options):
    """Avoid redrawing CustomTk controls when the periodic state poll is unchanged."""
    last = getattr(widget, "_brand_sync_values", {})
    changed = {key: value for key, value in options.items() if last.get(key, object()) != value}
    if changed:
        widget.configure(**changed)
        last.update(changed)
        widget._brand_sync_values = last


def _set_grid_visible(widget, visible):
    managed = widget.winfo_manager() == "grid"
    if visible and not managed:
        widget.grid()
    elif not visible and managed:
        widget.grid_remove()


def sync_actions(owner):
    if not getattr(owner, "_brand_built", False): return
    view = owner.current_view
    other_tools_active = tools_busy(owner)
    active = busy(owner) or other_tools_active
    state = getattr(owner, view + "_state", "idle")
    if not active and view in ("safe", "risk") and state == "ready":
        selected_count, selected_bytes = selection_summary(owner)
    else:
        selected_count, selected_bytes = 0, 0
    for key, b in (("safe", owner.btn_action), ("risk", owner.btn_deep)):
        state = getattr(owner, key + "_state")
        wording = {"idle": "开始扫描" if key == "safe" else "开始深度扫描",
                   "scanning": "正在扫描…", "ready": "清理所选项目" if key == "safe" else "检查并清理",
                   "cleaning": "正在清理…", "done": "再次扫描"}[state]
        disabled = active or not owner.get_selected_drives() or (state == "ready" and not selected_count)
        _configure_if_changed(b, text=wording, fg_color=WARN if key == "risk" else ACCENT,
                              hover_color="#F3D5AD" if key == "risk" else HOVER,
                              text_color=BG, state="disabled" if disabled else "normal")
        _set_grid_visible(b, view == key)
    _set_grid_visible(owner.btn_rescan, view in ("safe", "risk") and state == "ready")
    _configure_if_changed(owner.btn_rescan,
                          state="disabled" if active or not owner.get_selected_drives() else "normal")
    for widget in (owner.btn_select_all_apps, owner.btn_deselect_all_apps, owner.chk_showall, owner.sort_menu, owner.search_entry):
        _configure_if_changed(widget, state="disabled" if active else "normal")
    for key, b in owner.nav_buttons.items():
        selected = key == owner._active_page
        _configure_if_changed(b, state="normal",
                              fg_color=TINT if selected else "transparent",
                              text_color=ACCENT if selected else DIM)
    if other_tools_active:
        text = "其他空间工具正在执行任务"
    elif active:
        text = "正在分析所选磁盘" if "scanning" in (owner.safe_state, owner.risk_state) else "正在释放所选空间"
    elif state == "ready":
        from cleaner_core import format_size
        text = f"已选 {selected_count} 项  ·  {format_size(selected_bytes)}"
    elif state == "done": text = "清理已完成，可以再次扫描"
    else: text = "选择磁盘，开始第一次扫描"
    _configure_if_changed(owner.selection_label, text=text)
    _configure_if_changed(owner.scope_label, text="扫描范围  " + ("  ·  ".join(f"{d}:" for d in sorted(owner.get_selected_drives())) or "尚未选择磁盘") + "    /    Ctrl+F 搜索")


def selection_summary(owner):
    apps = selected_apps(owner)
    return len(apps), sum(owner.sizes.get(a["id"], 0) for a in apps)


def selected_apps(owner, tier=None):
    tier = tier or owner.current_view
    selected = []
    for app in owner.get_filtered_apps():
        var = owner.app_checkbox_vars.get(app["id"])
        chosen = var.get() if var is not None else owner.selection_state.get(app["id"], 1 if tier == "safe" else 0)
        if app["immune"] or app["id"] in owner.locked_ids or not chosen: continue
        if app.get("risk_level") != tier: continue
        amount = owner.sizes.get(app["id"], 0)
        if amount > 0: selected.append(app)
    return selected


def refresh_live(owner):
    if not owner.winfo_exists(): return
    sync_actions(owner)
    width = owner._reverse_window_scaling(owner.winfo_width())
    compact = width < 1200
    if compact != owner._brand_layout_width:
        owner._brand_layout_width = compact
        owner.main_title.configure(font=font(23 if compact else 28, True))
        owner.main_frame.grid_columnconfigure(1, minsize=264 if compact else 284)
        owner.detail_panel.configure(width=252 if compact else 268)
    from ui_theme import apply_window_chrome
    apply_window_chrome(owner)
    owner.after(260, lambda: apply_window_chrome(owner))
    owner.after(300, lambda: refresh_live(owner))


def show_placeholder(owner):
    box = ctk.CTkFrame(owner.scroll_frame, fg_color="transparent")
    box.pack(fill="both", expand=True, pady=14, padx=16)
    glyph = "scan"
    ctk.CTkLabel(box, text="", image=icon(glyph, ACCENT, 44), height=56).pack(pady=(8, 12))
    query = getattr(owner, "search_var", None)
    searched = bool(query and query.get().strip())
    state = getattr(owner, owner.current_view + "_state", "idle")
    if searched:
        title, desc = "没有匹配的项目", "试试其他名称，或清空搜索。"
    elif state in ("ready", "done"):
        title, desc = "当前范围没有可显示的项目", "可以切换磁盘重新扫描，或显示空项目。"
    else:
        title, desc = "空间整理，从一次扫描开始", "选择上方磁盘，再点击「开始扫描」。\n扫描完成后，项目与容量会在这里呈现。"
    label(box, title, 18, bold=True).pack(pady=(0, 8))
    label(box, desc, 12, DIM, wraplength=380, justify="center").pack()
    owner._placeholder = box


def show_intro(owner):
    from ui_theme import clear_detail_panel
    clear_detail_panel(owner, "清理说明" if owner.current_view != "risk" else "深度清理说明")
    body = owner.detail_body
    ctk.CTkLabel(body, text="", image=icon("shield", ACCENT, 32)).pack(anchor="w", padx=12, pady=(10, 16))
    for title, text in [("先看清，再清理", "扫描只分析容量。查看项目与文件路径，再选择要释放的空间。"),
                        ("为记忆保留空间", "Agent 记忆与工作区由现有免疫规则保护；手动上锁的项目也会跳过。"),
                        ("每一步，都有依据", "点击列表项目查看范围与说明，完成后在这里查看扫描和清理报告。")]:
        label(body, title, 13, TEXT, True, anchor="w").pack(fill="x", padx=12, pady=(0, 4))
        label(body, text, 12, DIM, wraplength=216, justify="left", anchor="w").pack(fill="x", padx=12, pady=(0, 20))


def show_item_detail(owner, app_id):
    from ui_theme import clear_detail_panel, refresh_detail_scroll
    from cleaner_core import format_size, obfuscate_path
    app = next((a for a in owner.apps_data if a["id"] == app_id), None)
    if app is None: return
    clear_detail_panel(owner, "项目详情")
    owner._detail_current = app_id
    b = owner.detail_body
    locked = bool(app["immune"] or app_id in owner.locked_ids)
    label(b, app["name"], 18, TEXT, True, wraplength=220, justify="left", anchor="w").pack(fill="x", padx=12, pady=(8, 8))
    label(b, "系统免疫" if app["immune"] else "手动保护" if locked else "需确认" if app["risk_level"] == "risk" else "常规缓存",
          11, ACCENT if locked else WARN if app["risk_level"] == "risk" else OK, anchor="w").pack(fill="x", padx=12)
    amount = owner.sizes.get(app_id, 0)
    label(b, format_size(amount), 25, TEXT, True, anchor="w").pack(fill="x", padx=12, pady=(14, 4))
    label(b, app.get("risk_desc", ""), 12, DIM, wraplength=216, justify="left", anchor="w").pack(fill="x", padx=12, pady=(0, 18))
    label(b, "覆盖路径", 12, TEXT, True, anchor="w").pack(fill="x", padx=12, pady=(0, 8))
    for path in app.get("paths", []):
        label(b, obfuscate_path(str(path)), 11, DIM, wraplength=216, justify="left", anchor="w").pack(fill="x", padx=12, pady=(0, 9))
    try:
        from migrate_core import is_junction, migrated_target_of, _exp
        for path in app.get("paths", []):
            base = str(path).split("*")[0].rstrip("/\\")
            target = migrated_target_of(_exp(base)) if base and is_junction(_exp(base)) else None
            if target:
                label(b, "已迁移至 " + target, 11, OK, wraplength=216, justify="left").pack(fill="x", padx=12, pady=6)
    except (OSError, ValueError):
        pass
    if not app["immune"]:
        button(b, "查看文件清单", lambda: owner.show_file_viewer(app), height=34).pack(fill="x", padx=12, pady=(12, 6))
        button(b, "调整清理范围", lambda: owner.toggle_subpaths(app), height=34).pack(fill="x", padx=12, pady=6)
        button(b, "解除手动保护" if locked else "上锁保护此项目",
               lambda: (owner.toggle_lock(app), show_item_detail(owner, app_id)), height=34,
               text_color=ACCENT).pack(fill="x", padx=12, pady=6)
    else:
        label(b, "此项目不会参与清理。", 11, ACCENT, wraplength=216).pack(padx=12, pady=16)
        button(b, "查看保护范围", lambda: owner.toggle_subpaths(app)).pack(fill="x", padx=12)
    refresh_detail_scroll(owner)


def show_protection(owner):
    from ui_theme import clear_detail_panel
    clear_detail_panel(owner, "保护中心")
    b = owner.detail_body
    ctk.CTkLabel(b, text="", image=icon("shield", ACCENT, 40)).pack(anchor="w", padx=12, pady=(12, 18))
    label(b, "把重要内容留好", 18, TEXT, True, anchor="w").pack(fill="x", padx=12)
    label(b, "系统免疫与手动上锁的项目不会参与清理。点击项目，查看受保护的路径。",
          12, DIM, wraplength=216, justify="left").pack(fill="x", padx=12, pady=(10, 20))
    for title, count in [("系统免疫", sum(bool(a["immune"]) for a in owner.apps_data)),
                         ("手动上锁", len(owner.locked_ids))]:
        label(b, f"{title}    {count} 项", 13, ACCENT, anchor="w").pack(fill="x", padx=12, pady=6)


def show_report(owner, kind, tier, freed_bytes=None):
    from ui_theme import clear_detail_panel
    from cleaner_core import format_size
    scan = kind == "scan"
    clear_detail_panel(owner, "扫描报告" if scan else "清理报告")
    b = owner.detail_body
    label(b, "扫描完成" if scan else "空间已释放", 20, TEXT, True, anchor="w").pack(fill="x", padx=12, pady=(12, 6))
    amount = (owner.safe_bytes if tier == "safe" else owner.risk_bytes) if scan else (freed_bytes or 0)
    label(b, format_size(amount), 30, ACCENT if scan else OK, True, anchor="w").pack(fill="x", padx=12, pady=(8, 4))
    label(b, "发现的项目容量，实际释放以清理结果为准。" if scan else "本轮实际释放的空间。",
          11, DIM, wraplength=216, justify="left", anchor="w").pack(fill="x", padx=12, pady=(0, 20))
    if scan:
        pool = [a for a in owner.get_filtered_apps() if not a["immune"] and a["id"] not in owner.locked_ids and a["risk_level"] == tier]
        tops = [(a["name"], owner.sizes.get(a["id"], 0)) for a in pool]
    else: tops = getattr(owner, "last_clean_detail", [])
    tops = sorted(tops, key=lambda v: v[1], reverse=True)
    label(b, "容量较大的项目", 12, TEXT, True, anchor="w").pack(fill="x", padx=12, pady=(0, 10))
    for name, size in [(n, s) for n, s in tops if s > 0][:5]:
        label(b, name, 12, DIM, wraplength=216, anchor="w", justify="left").pack(fill="x", padx=12)
        label(b, format_size(size), 12, TEXT, True, anchor="w").pack(fill="x", padx=12, pady=(0, 10))
    if not amount: label(b, "当前范围无需清理。", 12, DIM).pack(pady=12)
    label(b, "在底部操作栏确认所选项目后继续。" if scan else "可以再次扫描，或前往其他空间工具。",
          11, DIM, wraplength=216, justify="left").pack(fill="x", padx=12, pady=(20, 10))


def show_activity(owner):
    win = getattr(owner, "_activity_window", None)
    if win is not None and win.winfo_exists(): win.lift(); return
    win = owner._activity_window = ctk.CTkToplevel(owner)
    from ui_theme import setup_popup
    setup_popup(win, "活动记录")
    win.geometry("760x500"); win.minsize(540, 360)
    popup_header(win, "活动记录", "本次会话中的扫描与清理记录")
    box = ctk.CTkTextbox(win, fg_color=PANEL, text_color=DIM, font=font(12), corner_radius=12)
    box.pack(fill="both", expand=True, padx=24, pady=(0, 24))
    def refresh():
        if not win.winfo_exists(): return
        content = "\n".join(owner.log_history) or "暂时没有活动记录。"
        box.configure(state="normal"); box.delete("1.0", "end"); box.insert("1.0", content)
        box.configure(state="disabled"); box.see("end")
        win.after(1000, refresh)
    refresh()


def show_settings(owner):
    if getattr(owner, "settings_frame", None) is not None:
        owner.settings_frame.grid(); return
    frame = owner.settings_frame = ctk.CTkScrollableFrame(owner, fg_color=BG, corner_radius=0)
    frame.grid(row=0, column=1, sticky="nsew")
    popup_header(frame, "设置与关于", "版本更新、保护策略与本地数据说明")
    for title, desc in [("清理保护", "系统免疫由清理内核执行。手动上锁记录跨启动保留，可在保护中心查看。"),
                        ("显示与操作", "深色工作台随窗口伸缩。Ctrl+1 空间清理，Ctrl+2 深度清理，Ctrl+F 搜索项目，F5 重新扫描。"),
                        ("数据与兼容", "品牌升级沿用现有授权与本地记录。扫描不会自动开始，清理需主动确认。")]:
        block = ctk.CTkFrame(frame, fg_color=PANEL, corner_radius=12)
        block.pack(fill="x", padx=24, pady=8)
        label(block, title, 16, TEXT, True, anchor="w").pack(fill="x", padx=20, pady=(18, 6))
        label(block, desc, 13, DIM, anchor="w", wraplength=680, justify="left").pack(fill="x", padx=20, pady=(0, 18))
    info = ctk.CTkFrame(frame, fg_color="transparent")
    info.pack(fill="x", padx=24, pady=24)
    from hwid_utils import get_hwid
    owner.lbl_hwid = label(info, "设备 ID  " + get_hwid(), 11, MUTED, anchor="w")
    owner.lbl_hwid.pack(fill="x", pady=8)
    owner.btn_check_update = button(info, "检查更新", owner.manual_check_update, width=130)
    owner.btn_check_update.pack(anchor="w")


def request_close(owner):
    if busy(owner) or tools_busy(owner):
        from tkinter import messagebox
        messagebox.showinfo("PPSAI Cleaner", "任务仍在进行，请等待完成后再退出。", parent=owner)
        return
    owner.destroy()


def build_app_row(owner, app, idx):
    """Lightweight rows preserve the engine's existing widget contract."""
    from cleaner_core import format_size
    row = tk.Frame(owner.scroll_frame, bg=PANEL, height=64, bd=0)
    row.pack(fill="x", padx=5, pady=1)
    row.pack_propagate(False)
    locked = app["immune"] or app["id"] in owner.locked_ids
    tk.Frame(row, bg=LINE, height=1).pack(side="bottom", fill="x")
    if locked:
        lock = tk.Canvas(row, bg=PANEL, width=22, height=26, bd=0, highlightthickness=0)
        lock.pack(side="left", padx=(8, 12))
        lock.create_arc(7, 3, 17, 17, start=0, extent=180, outline=ACCENT, width=1.5, style="arc")
        lock.create_rectangle(5, 10, 19, 22, outline=ACCENT, width=1.5)
    else:
        remembered = owner.selection_state.get(app["id"])
        var = tk.IntVar(value=(1 if app["risk_level"] == "safe" else 0) if remembered is None else remembered)
        owner.app_checkbox_vars[app["id"]] = var
        check = tk.Checkbutton(row, variable=var, text="", bg=PANEL, fg=ACCENT,
                               activebackground=PANEL, selectcolor=CARD, bd=0,
                               highlightthickness=1, highlightbackground=PANEL, highlightcolor=ACCENT,
                               cursor="hand2", command=lambda: owner._remember_selection(app))
        check.pack(side="left", padx=(7, 9))
        owner.app_checkboxes[app["id"]] = check
    more = tk.Button(row, text="范围", bg=CARD, fg=DIM, activebackground=LINE,
                     activeforeground=TEXT, relief="flat", bd=0, padx=10, pady=5,
                     font=(FAMILY, 10), cursor="hand2", highlightthickness=1,
                     highlightbackground=CARD, highlightcolor=ACCENT,
                     command=lambda: owner.toggle_subpaths(app))
    more.pack(side="right", padx=(8, 10))
    owner.app_expand_btns[app["id"]] = more
    badge_text = "免疫保护" if app["immune"] else "已上锁" if locked else "需确认" if app["risk_level"] == "risk" else "常规缓存"
    badge = tk.Label(row, text=badge_text, width=8, bg=PANEL,
                     fg=ACCENT if locked else WARN if app["risk_level"] == "risk" else OK,
                     font=(FAMILY, 10))
    badge.pack(side="right", padx=3)
    amount = owner.sizes.get(app["id"], 0)
    state = getattr(owner, owner.current_view + "_state", "idle")
    size = tk.Label(row, text=format_size(amount) if amount else ("无残留" if state in ("ready", "done") else "待扫描"),
                    width=11, bg=PANEL, fg=TEXT if amount else MUTED, anchor="e", font=(FAMILY, 11))
    size.pack(side="right", padx=3)
    title = tk.Label(row, text=app["name"], bg=PANEL, fg=TEXT, anchor="w", font=(FAMILY, 12))
    title.pack(side="left", fill="x", expand=True, padx=(0, 6))
    fill = tk.Frame(row, bg=TINT, bd=0)
    fill.place(relx=0, rely=0, relwidth=0, relheight=1); fill.lower()
    owner.app_rows[app["id"]] = {"size": size, "badge": badge, "frame": row, "fill": fill}
    for widget in (row, title, size, badge, fill):
        widget.bind("<Button-1>", lambda e, aid=app["id"]: show_item_detail(owner, aid))
        widget.configure(cursor="hand2")


def show_risk_confirmation(owner, clean_type, on_confirm):
    from ui_theme import setup_popup
    from cleaner_core import format_size
    selected = selected_apps(owner, "risk")
    if not selected: return
    win = ctk.CTkToplevel(owner)
    setup_popup(win, "确认深度清理")
    win.geometry("600x540"); win.minsize(560, 500); win.transient(owner); win.grab_set()
    popup_header(win, "确认这次清理", "深度项目需要你确认具体范围。")
    total = sum(owner.sizes.get(a["id"], 0) for a in selected)
    label(win, f"{len(selected)} 个项目  ·  扫描容量 {format_size(total)}", 18, WARN, True).pack(anchor="w", padx=24, pady=(0, 12))
    box = ctk.CTkScrollableFrame(win, fg_color=PANEL, height=150)
    box.pack(fill="both", expand=True, padx=24, pady=(0, 12))
    for app in selected:
        label(box, app["name"], 13, TEXT, True, anchor="w").pack(fill="x", padx=8, pady=(8, 2))
        label(box, app.get("risk_desc", ""), 11, DIM, wraplength=480, justify="left", anchor="w").pack(fill="x", padx=8, pady=(0, 8))
    accepted = tk.BooleanVar(value=False)
    confirm = button(win, "确认清理", lambda: (win.destroy(), on_confirm()), True, state="disabled", fg_color=WARN)
    ctk.CTkCheckBox(win, text="已核对所选项目，了解删除后无法撤销", variable=accepted,
                    command=lambda: confirm.configure(state="normal" if accepted.get() else "disabled"),
                    font=font(12), text_color=DIM, fg_color=ACCENT, checkmark_color=BG).pack(anchor="w", padx=24, pady=12)
    confirm.pack(side="right", padx=(8, 24), pady=(0, 24))
    button(win, "返回检查", win.destroy).pack(side="right", padx=8, pady=(0, 24))


class BrandSplash(ctk.CTkToplevel):
    """Real startup phases, no invented percentage timer or fixed loading delay."""
    def __init__(self, master_app):
        super().__init__(master_app)
        self.master_app = master_app
        self.overrideredirect(True); self.configure(fg_color=BG)
        w, h = 760, 475
        self.geometry(f"{w}x{h}+{(self.winfo_screenwidth()-w)//2}+{(self.winfo_screenheight()-h)//2}")
        try:
            self._art = image("splash.png", (w, h))
            ctk.CTkLabel(self, text="", image=self._art, width=w, height=h).place(x=0, y=0)
        except OSError:
            label(self, "PPSAI Cleaner", 36, TEXT, True).place(relx=.5, rely=.45, anchor="center")
        self.lbl_status = label(self, "正在加载工作台", 12, DIM, fg_color=BG)
        self.lbl_status.place(x=46, y=h-82)
        self.progress = ctk.CTkProgressBar(self, width=w-92, height=3, fg_color=LINE, progress_color=ACCENT)
        self.progress.place(x=46, y=h-46); self.progress.set(.15)
        self.attributes("-topmost", True)
        self.after(30, self._prepare)

    def _prepare(self):
        self.lbl_status.configure(text="正在准备扫描范围与保护规则")
        self.progress.set(.4)
        self.after_idle(self._build)

    def _build(self):
        try:
            self.master_app.build_ui()
            self.progress.set(1)
            self.lbl_status.configure(text="工作台已就绪")
            self.after_idle(self._finish)
        except Exception:
            self.destroy()
            self.master_app.destroy()
            raise

    def _finish(self):
        self.master_app.deiconify()
        self.master_app.lift()
        self.destroy()


def show_auth_dialog(owner, hwid, clean_type):
    """Responsive activation UI; retains the existing RSA and service contract."""
    import io
    import json
    import threading
    import urllib.parse
    import urllib.request
    from ui_theme import setup_popup
    module = sys.modules[owner.__class__.__module__]
    verify = module.verify_license
    save = module.save_license_key
    stop = threading.Event()
    state = {"closed": False, "activated": False}
    win = ctk.CTkToplevel(owner)
    setup_popup(win, "授权激活")
    win.geometry("640x590"); win.resizable(False, False); win.transient(owner); win.grab_set()
    popup_header(win, "激活 PPSAI Cleaner", "扫描结果已保留，激活后继续清理所选项目。")
    content = ctk.CTkFrame(win, fg_color=PANEL, corner_radius=12)
    content.pack(fill="x", padx=24, pady=(0, 18))
    qr = ctk.CTkFrame(content, width=174, height=174, fg_color=CARD, corner_radius=10)
    qr.pack(side="left", padx=18, pady=18); qr.pack_propagate(False)
    qr_label = label(qr, "正在加载二维码…", 11, DIM, wraplength=140)
    qr_label.pack(expand=True)
    words = ctk.CTkFrame(content, fg_color="transparent")
    words.pack(side="left", fill="both", expand=True, padx=(0, 18), pady=22)
    label(words, "扫码激活", 17, TEXT, True, anchor="w").pack(fill="x", pady=(0, 8))
    label(words, "使用手机扫码完成授权。\n客户端会自动检查激活状态。", 12, DIM,
          wraplength=260, justify="left", anchor="w").pack(fill="x")
    status = label(words, "等待激活", 11, ACCENT, wraplength=250, justify="left", anchor="w")
    status.pack(fill="x", pady=(16, 0))
    label(win, "已有授权码", 13, TEXT, True, anchor="w").pack(fill="x", padx=24, pady=(0, 8))
    entry = ctk.CTkEntry(win, placeholder_text="在此粘贴设备授权码", height=40, font=font(12),
                         fg_color=PANEL, border_color=LINE)
    entry.pack(fill="x", padx=24)
    feedback = label(win, "", 11, ERR, anchor="w", wraplength=580, justify="left", height=38)
    feedback.pack(fill="x", padx=24, pady=(4, 0))
    label(win, "设备 ID  " + hwid, 10, DIM, anchor="w").pack(fill="x", padx=24, pady=(6, 16))
    actions = ctk.CTkFrame(win, fg_color="transparent")
    actions.pack(fill="x", padx=24, pady=(0, 24))

    def alive():
        return not state["closed"] and bool(win.winfo_exists())

    def close():
        state["closed"] = True; stop.set(); owner.polling_active = False
        win.destroy()

    def finish(key):
        if not alive() or state["activated"]: return
        if not save(key):
            feedback.configure(text="无法保存授权，请检查本地目录是否可写。")
            validate_btn.configure(state="normal", text="验证并继续")
            return
        state["activated"] = True
        close()
        owner.append_log("设备授权验证成功并已保存。")
        if clean_type == "risk":
            owner.show_risk_confirmation(clean_type, lambda: owner.execute_cleaning(clean_type))
        else:
            owner.execute_cleaning(clean_type)

    def valid_key(key):
        if verify(hwid, key): return True
        from hwid_utils import get_hwid_wmic
        return verify(get_hwid_wmic(), key)

    def manual():
        key = entry.get().strip()
        if not key:
            feedback.configure(text="请先粘贴授权码。")
            entry.focus_set(); return
        validate_btn.configure(state="disabled", text="正在验证…")
        feedback.configure(text="")
        def work():
            try: valid = valid_key(key)
            except Exception: valid = False
            def result():
                if not alive(): return
                if valid: finish(key)
                else:
                    feedback.configure(text="授权码无效或与此设备不匹配，请核对后重试。")
                    validate_btn.configure(state="normal", text="验证并继续")
            owner._post_ui(result)
        threading.Thread(target=work, daemon=True).start()

    validate_btn = button(actions, "验证并继续", manual, True, width=150, height=40)
    validate_btn.pack(side="right")
    button(actions, "返回工作台", close, width=130, height=40).pack(side="right", padx=10)
    win.protocol("WM_DELETE_WINDOW", close)
    win.bind("<Escape>", lambda e: close())
    entry.bind("<Return>", lambda e: manual())
    owner.polling_active = True
    mobile = f"https://ppsai.chat/safecleaner/pay.html?hwid={hwid}"

    def load_qr():
        try:
            url = "https://ppsai.chat/api/qrcode?data=" + urllib.parse.quote(mobile)
            req = urllib.request.Request(url, headers={"User-Agent": "SafeCleanerPro-Client"})
            with urllib.request.urlopen(req, timeout=4) as response: data = response.read()
            with Image.open(io.BytesIO(data)) as source: picture = source.convert("RGB")
            def show():
                if not alive(): return
                art = ctk.CTkImage(light_image=picture, dark_image=picture, size=(150, 150))
                qr_label.configure(text="", image=art)
            owner._post_ui(show)
        except Exception:
            def error():
                if alive(): qr_label.configure(text="二维码暂不可用\n可在下方输入授权码")
            owner._post_ui(error)

    def poll():
        while not stop.is_set():
            try:
                url = f"https://ppsai.chat/api/check_activation?hwid={hwid}"
                req = urllib.request.Request(url, headers={"User-Agent": "SafeCleanerPro-Client"})
                with urllib.request.urlopen(req, timeout=3) as response:
                    data = json.loads(response.read().decode("utf-8"))
                key = data.get("license_key")
                if data.get("activated") and key and valid_key(key):
                    owner._post_ui(lambda k=key: finish(k))
                    return
            except Exception:
                pass
            if stop.wait(3): return
    threading.Thread(target=load_qr, daemon=True).start()
    threading.Thread(target=poll, daemon=True).start()
    return win
