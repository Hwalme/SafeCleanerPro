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
import io
import json
import os
import threading
import time
import shutil
import urllib.request
import ctypes
import tkinter as _tk
import customtkinter as ctk
from hwid_utils import get_hwid
from cleaner_core import format_size, get_app_drives, obfuscate_path, scan_app_files

# 字体族不是性能杠杆。真正的原因是 Tk 为自动定尺寸而测量 emoji 文字，
# 而这一点靠给图标标签固定 width/height 来规避。
UI_FAMILY = "Microsoft YaHei UI"
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
        lbl = ctk.CTkLabel(widget, text="", width=1, height=1)
        lbl.update_idletasks()
        lbl.destroy()
    except Exception:
        pass
    _emoji_warmed = True


def clear_detail_panel(owner, title=" 详情面板"):
    """清空右侧详情面板并设置标题（所有右侧视图的统一入口）。"""
    try:
        owner.detail_title.configure(text=title)
        for w in owner.detail_body.winfo_children():
            w.destroy()
    except Exception:
        pass
    refresh_detail_scroll(owner)


def show_item_detail(owner, app_id):
    from brand_ui import show_item_detail as show
    return show(owner, app_id)



def _style_scrollbar(sf, slot="#161C23", thumb="#1D252E", hover="#2A3541"):
    """统一 CTkScrollableFrame 滚动条外观。

    槽(fg_color)取容器底色 → 空内容/无滑块时几乎隐形，不再出现突兀的黑亮条；
    滑块(button_color)用低调暗色，hover 微亮。CTk 内部属性 _scrollbar，
    不同版本字段可能差异，全部 try 容错（失败仅回退主题默认色）。
    """
    try:
        sb = getattr(sf, "_scrollbar", None)
        if sb is None:
            return
        sb.configure(fg_color=slot, button_color=thumb, button_hover_color=hover)
    except Exception:
        try:
            sb.configure(button_color=thumb, button_hover_color=hover)
        except Exception:
            pass


def _fill_configure_color(fill, color_hex):
    """行进度底条着色：tk.Frame 走 bg，CTkFrame 走 fg_color（自动适配）。"""
    try:
        fill.configure(bg=color_hex)
        return
    except Exception:
        pass
    try:
        fill.configure(fg_color=color_hex)
    except Exception:
        pass


def style_row_badge(owner, app_id, text, fg, bg):
    """更新行徽章文本+配色（tk.Label 与 CTkLabel 双兼容）。"""
    info = owner.app_rows.get(app_id)
    if not info:
        return
    try:
        info["badge"].configure(text=text)
    except Exception:
        pass
    try:
        info["badge"].configure(fg=fg, bg=bg)
    except Exception:
        try:
            info["badge"].configure(text_color=fg, fg_color=bg)
        except Exception:
            pass


def _hover_chip(widget, base, hover, command):
    """tk.Label 拟物按钮：hover 变色 + 点击回调（CTkButton 的轻量替代）。

    每行省一个 CTkButton（CTkButton 内部含 canvas+label 两个 tk 窗口），
    91 行累计省 180+ 窗口；tk.Label 重排成本远低于 CTk 控件。
    """
    def _enter(_e):
        try:
            widget.configure(bg=hover)
        except Exception:
            pass

    def _leave(_e):
        try:
            widget.configure(bg=base)
        except Exception:
            pass

    try:
        widget.bind("<Enter>", _enter)
    except Exception:
        pass
    try:
        widget.bind("<Leave>", _leave)
    except Exception:
        pass
    try:
        widget.bind("<Button-1>", lambda e: command())
    except Exception:
        pass


def autohide_scrollbar(owner, sf, delays=(90, 380)):
    """CTkScrollableFrame 内容未溢出时隐藏滚动条，溢出时恢复（无损 grid_remove）。

    v3.9.13 反馈：详情/报告内容不长时滚动条也常驻，观感突兀。
    可视视口 = sf._parent_canvas.winfo_height()；内容需求高度 = sf.winfo_reqheight()。
    延迟判定两次：布局在渲染后 1-2 个 idle 周期才稳定。

    关键陷阱：Tk pack 在最后一个子控件销毁后不再触发 master 请求尺寸重算，
    winfo_reqheight() 会粘滞在清空前的旧值 → 判空优先：无子控件时 need=0。
    """
    def _fit():
        try:
            canvas = getattr(sf, "_parent_canvas", None)
            sb = getattr(sf, "_scrollbar", None)
            if canvas is None or sb is None:
                return
            kids = sf.winfo_children()
            if not kids:
                need = 0.0
            else:
                need = float(sf.winfo_reqheight())
            have = float(canvas.winfo_height())
            if need > have + 4:
                sb.grid()
            else:
                sb.grid_remove()
        except Exception:
            pass

    for d in delays:
        try:
            owner.after(d, _fit)
        except Exception:
            pass


def refresh_detail_scroll(owner):
    """详情面板专用滚动条自适应（每次右侧视图渲染完成后调用）。"""
    autohide_scrollbar(owner, getattr(owner, "detail_body", None))


def _bind_row_click(widget, owner, app_id):
    """行空白处点击 → 右侧详情（勾选框/按钮自身事件不受影响）。

    注意：CTkFrame 不支持 cursor 参数（configure 会抛 ValueError），
    所以光标与事件绑定分别独立容错——一处不支持不影响另一处。
    """
    try:
        widget.configure(cursor="hand2")
    except Exception:
        pass
    try:
        widget.bind("<Button-1>", lambda e: show_item_detail(owner, app_id))
    except Exception:
        pass


def build_app_row(owner, app, idx):
    from brand_ui import build_app_row as build
    return build(owner, app, idx)



def scroll_row_into_view(owner, app_id, only_if_hidden=False):
    """清理/扫描跟随：把当前行自动滚动到可视区（列表自动定位）。

    性能关键：本函数在扫描/清理热路径上被逐项调用。一次 moveto 会触发
    update_idletasks 强制全树几何重算 + 全部可视子窗口重排（366 行实测
    单次最高约 280ms），逐项调用 = 列表撕裂/卡死。
    双重节流：
      1. only_if_hidden=True 时，目标行已在可视区内则直接跳过（零重排）；
      2. 150ms after 合并：风暴中的多次请求只保留最后一次。
    """
    try:
        if only_if_hidden and _row_visible(owner, app_id):
            return
        pending = getattr(owner, "_scroll_job", None)
        if pending is not None:
            try:
                owner.after_cancel(pending)
            except Exception:
                pass
        owner._scroll_job = owner.after(
            150, lambda aid=app_id: _do_scroll_row_into_view(owner, aid))
    except Exception:
        pass


def _row_visible(owner, app_id):
    """目标行是否已完全在可视区内（不触发任何几何重算的快速判断）。"""
    try:
        info = owner.app_rows.get(app_id)
        if not info:
            return False
        canvas = getattr(owner.scroll_frame, "_parent_canvas", None)
        if canvas is None:
            return False
        inner = info["frame"].master
        content_h = float(inner.winfo_reqheight())
        view_h = float(canvas.winfo_height())
        if content_h <= 1 or view_h <= 1 or content_h <= view_h:
            return True                          # 不足一屏，视为可见
        yv0, yv1 = canvas.yview()
        row_top = info["frame"].winfo_y() / content_h
        row_frac = max(0.02, info["frame"].winfo_height() / content_h)
        return (yv0 <= row_top and row_top + row_frac <= yv1)
    except Exception:
        return False


def _do_scroll_row_into_view(owner, app_id):
    """scroll_row_into_view 的节流落地点（真正的滚动计算）。"""
    owner._scroll_job = None
    if _row_visible(owner, app_id):
        return                                   # 已可见：不做任何重排
    info = owner.app_rows.get(app_id)
    if not info:
        return
    try:
        row = info["frame"]
        inner = row.master                       # CTkScrollableFrame 的内容容器
        owner.scroll_frame.update_idletasks()    # 先让几何布局就绪
        canvas = getattr(owner.scroll_frame, "_parent_canvas", None)
        if canvas is None:
            return
        content_h = inner.winfo_reqheight()
        # 关键：可视高度必须取 canvas 实际高。CTkScrollableFrame 本体会被内容撑高
        # （winfo_height == 内容总高），用它作分母会得到 0 → frac 全部钳到 1.0，
        # 表现为"列表滚到底一次后就再也不跟随"。
        view_h = canvas.winfo_height()
        if content_h <= view_h:
            return                               # 内容不足一屏，无需滚动
        row_y = row.winfo_y()                    # 第一行也照常滚回顶部，不早退
        frac = row_y / max(1, content_h - view_h)
        canvas.yview_moveto(min(1.0, max(0.0, frac)))
    except Exception:
        pass


def animate_row_progress(owner, app_id, phase):
    """行级清理进度底条。

    phase='running': 琥珀色全宽 — 该项正在清理；
    phase='done':    绿色从左到右填充动画 — 该项净化完成；
    phase='scanning': 低调蓝灰全宽 — 该项正在扫描（区别于清理的琥珀）；
    phase='reset':   清空填充（新扫描时）。
    """
    info = owner.app_rows.get(app_id)
    if not info:
        return
    fill = info.get("fill")
    if fill is None:
        return
    try:
        if phase == "reset":
            fill.place(relwidth=0.0)
            return
        if phase == "running":
            _fill_configure_color(fill, "#78350f")   # 琥珀：处理中
            fill.place(relwidth=1.0)
            fill.lower()
            return
        if phase == "scanning":
            _fill_configure_color(fill, "#203640")   # 蓝灰：扫描中（低调）
            fill.place(relwidth=1.0)
            fill.lower()
            return
        # done：从 0 → 1 的填充动画（每帧 16ms，共约 0.4s）
        _fill_configure_color(fill, "#224334")       # 绿：已完成
        fill.lower()
        state = {"w": 0.0}

        def _step():
            state["w"] += 0.10
            if state["w"] >= 1.0:
                fill.place(relwidth=1.0)
                return
            fill.place(relwidth=state["w"])
            owner.after(16, _step)

        _step()
    except Exception:
        pass


def show_final_report(owner, kind, tier_or_type, freed_bytes=None):
    from brand_ui import show_report
    return show_report(owner, kind, tier_or_type, freed_bytes)



def show_unlock_confirm(owner, app, on_confirm):
    """解除系统免疫的红色警示确认框：解锁 = 该项参与扫描与清理，不可逆。"""
    try:
        win = ctk.CTkToplevel(owner)
        win.title("解除系统免疫确认")
        win.geometry("460x300")
        win.resizable(False, False)
        win.transient(owner)
        try:
            win.grab_set()
        except Exception:
            pass

        head = ctk.CTkFrame(win, fg_color="#3D282E", corner_radius=0)
        head.pack(fill="x")
        ctk.CTkLabel(head, text=" 解除系统免疫", font=F(UI_FAMILY, 19, "bold"),
                     text_color="#ECA0A6").pack(pady=(16, 4))

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24)
        ctk.CTkLabel(body, text=f"项目：{app['name']}", font=F(UI_FAMILY, 14, "bold"),
                     text_color="#F0F4F7", anchor="w").pack(fill="x", pady=(14, 4))
        ctk.CTkLabel(body,
                     text="解除后此项将立即参与扫描与清理，\n"
                          "其缓存/日志/临时文件可能在下次清理中被删除。\n"
                          "此操作不可自动恢复（可重新扫描后再次手动上锁）。",
                     font=F(UI_FAMILY, 12), text_color="#A3AFBD",
                     justify="left", anchor="w").pack(fill="x", pady=(0, 10))

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(fill="x", padx=24, pady=(2, 16))

        def _do():
            win.destroy()
            try:
                on_confirm(app)
            except Exception:
                pass
        ctk.CTkButton(btns, text=" 确认解除免疫", font=F(UI_FAMILY, 13, "bold"),
                      height=40, fg_color="#59353A", hover_color="#633A40",
                      command=_do).pack(side="right", padx=(10, 0))
        ctk.CTkButton(btns, text="取消", font=F(UI_FAMILY, 13), height=40,
                      fg_color="#1D252E", hover_color="#2A3541",
                      command=win.destroy).pack(side="right")
    except Exception:
        pass


def show_auth_dialog(owner, hwid, clean_type):
    from brand_ui import show_auth_dialog as show
    return show(owner, hwid, clean_type)



def show_risk_confirmation(owner, clean_type, on_confirm):
    from brand_ui import show_risk_confirmation as show
    return show(owner, clean_type, on_confirm)



def show_protection_list(owner):
    from brand_ui import navigate
    return navigate(owner, "protected")



def show_file_viewer(owner, app):
    """查看某项目的文件清单，可逐文件勾选/排除。"""
    import sys
    is_personal_file = sys.modules[owner.__class__.__module__].is_personal_file
    dialog = ctk.CTkToplevel(owner)
    setup_popup(dialog, f'文件清单 · {app["name"]}')
    dialog.geometry("780x560")
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    dialog.grab_set()

    ctk.CTkLabel(dialog, text=f' {app["name"]} - 文件清理清单',
                 font=F(UI_FAMILY, 18, "bold"),
                 text_color="#F0F4F7").pack(pady=(15, 5))

    risk_color = "#ECA0A6" if app["risk_level"] == "risk" else "#295443"
    risk_label_text = (f'风险等级: {" 高风险项目" if app["risk_level"] == "risk" else " 安全清理项目"}')

    info_frame = ctk.CTkFrame(dialog, fg_color="#0D1116")
    info_frame.pack(fill="x", padx=20, pady=5)

    ctk.CTkLabel(info_frame, text=risk_label_text,
                 font=F(UI_FAMILY, 13, "bold"),
                 text_color=risk_color).pack(anchor="w", padx=15, pady=(8, 2))
    ctk.CTkLabel(info_frame,
                 text=f'安全提示: {app.get("risk_desc", "本项清理无任何数据风险。")}',
                 font=F(UI_FAMILY, 12),
                 text_color="#A3AFBD").pack(anchor="w", padx=15, pady=(0, 8))

    files_scroll = ctk.CTkScrollableFrame(dialog, fg_color="#161C23",
                                          scrollbar_button_color="#1D252E",
                                          scrollbar_button_hover_color="#2A3541")
    _style_scrollbar(files_scroll, slot="#161C23")
    files_scroll.pack(fill="both", expand=True, padx=20, pady=6)

    loading_label = ctk.CTkLabel(files_scroll,
                                 text="正在分析文件清单，大目录可能需要片刻，请稍候...",
                                 font=F(UI_FAMILY, 13),
                                 text_color="#8CDEEF")
    loading_label.pack(pady=80)

    file_check_vars = {}

    MAX_RENDER_ROWS = 300  # 渲染上限：避免超大目录上千行 checkbox 卡死弹窗

    def load_files():
        # 优先使用扫描阶段已缓存的文件清单（秒开）；无缓存才现场遍历
        files = owner.file_cache.get(app["id"])
        if files is None:
            from cleaner_core import scan_app_files
            files = scan_app_files(app, limit=1000)
        files = sorted(files, key=lambda x: x[1], reverse=True)
        total_count = len(files)
        total_bytes = sum(s for _, s in files)
        shown = files[:MAX_RENDER_ROWS]

        def update_ui():
            try:
                loading_label.destroy()
            except Exception:
                pass

            if not files:
                ctk.CTkLabel(files_scroll, text="此项目没有扫描到可显示的文件。",
                             font=F(UI_FAMILY, 13),
                             text_color="#8795A5").pack(pady=50)
                return

            summary = "共 %d 个文件 · 合计 %s" % (total_count, format_size(total_bytes))
            if total_count > len(shown):
                summary += "（仅展示最大的 %d 个）" % len(shown)
            ctk.CTkLabel(files_scroll, text=summary,
                         font=F(MONO_FAMILY, 11),
                         text_color="#8CDEEF").pack(anchor="w", padx=12, pady=(2, 4))

            if any(is_personal_file(p) for p, _ in files):
                ctk.CTkLabel(
                    info_frame,
                    text=" 提示：检测到当前目录包含用户个人文档/媒体资产，已默认取消勾选以防误删！",
                    font=F(UI_FAMILY, 12, "bold"),
                    text_color="#E7BA7A").pack(anchor="w", padx=15, pady=(2, 8))

            col_frame = ctk.CTkFrame(files_scroll, fg_color="transparent")
            col_frame.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(col_frame, text="要清理的文件路径 (已按大小降序排序)",
                         font=F(UI_FAMILY, 12, "bold"),
                         text_color="#8795A5").pack(side="left")
            ctk.CTkLabel(col_frame, text="大小",
                         font=F(UI_FAMILY, 12, "bold"),
                         text_color="#8795A5").pack(side="right", padx=(0, 20))

            for path, size in shown:
                file_row = ctk.CTkFrame(files_scroll, fg_color="#1D252E", corner_radius=4)
                file_row.pack(fill="x", padx=5, pady=2)

                is_personal = is_personal_file(path)
                display_path = (" [用户数据] " if is_personal else "") + obfuscate_path(path)

                var = ctk.StringVar(
                    value="checked" if path not in owner.skipped_files else "unchecked")
                file_check_vars[path] = var

                def make_toggle(p=path, v=var):
                    def toggle():
                        if v.get() == "checked":
                            owner.skipped_files.discard(p)
                            return
                        owner.skipped_files.add(p)
                    return toggle

                chk_file = ctk.CTkCheckBox(
                    file_row, text=display_path,
                    variable=var, onvalue="checked", offvalue="unchecked",
                    font=F(MONO_FAMILY, 12),
                    text_color="#E7BA7A" if is_personal else "#CFD7E0",
                    width=18, height=18,
                    command=make_toggle(path, var))
                chk_file.pack(side="left", padx=10, pady=6)

                if path not in owner.skipped_files:
                    chk_file.select()
                else:
                    chk_file.deselect()

                ctk.CTkLabel(file_row, text=format_size(size),
                             font=F(MONO_FAMILY, 12),
                             text_color="#E7BA7A" if is_personal else "#A3AFBD"
                             ).pack(side="right", padx=15, pady=6)

            files_scroll.update_idletasks()
            try:
                files_scroll._parent_canvas.configure(
                    scrollregion=files_scroll._parent_canvas.bbox("all"))
                files_scroll._parent_canvas.yview_moveto(0.0)
            except Exception:
                pass
            autohide_scrollbar(owner, files_scroll)

        owner._post_ui(lambda: update_ui() if dialog.winfo_exists() else None)

    threading.Thread(target=load_files, daemon=True).start()

    bottom_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    bottom_frame.pack(fill="x", pady=10, padx=20)

    def select_all():
        for p in file_check_vars.keys():
            owner.skipped_files.discard(p)
        dialog.destroy()
        owner.show_file_viewer(app)

    def deselect_all():
        for p in file_check_vars.keys():
            owner.skipped_files.add(p)
        dialog.destroy()
        owner.show_file_viewer(app)

    ctk.CTkButton(bottom_frame, text="全部勾选",
                  font=F(UI_FAMILY, 12, "bold"),
                  fg_color="#8CDEEF", hover_color="#8CDEEF",
                  width=110, height=36, command=select_all).pack(side="left", padx=5)
    ctk.CTkButton(bottom_frame, text="全部排除",
                  font=F(UI_FAMILY, 12, "bold"),
                  fg_color="#1D252E", hover_color="#2A3541",
                  width=110, height=36, command=deselect_all).pack(side="left", padx=5)
    ctk.CTkButton(bottom_frame, text="确认保存设置",
                  font=F(UI_FAMILY, 12, "bold"),
                  fg_color="#295443", hover_color="#3C6D58",
                  width=130, height=36, command=dialog.destroy).pack(side="right", padx=5)


def build_ui(owner, version):
    from brand_ui import build_ui as build
    return build(owner, version)


def style_dark_treeview(rowheight=30):
    """深色 ttk.Treeview 主题。

    ttk 表格默认白底黑字，放在玻璃拟态暗色界面里既刺眼又让浅色
    状态文字（浅绿/浅黄）几乎不可读 —— 统一压成深色主题。
    注意 ttk.Style 是进程级全局，一次配置对所有 Treeview 生效。
    """
    import tkinter.ttk as _ttk
    style = _ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.layout("Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
    for direction, sticky in (("Vertical", "ns"), ("Horizontal", "ew")):
        name = direction + ".TScrollbar"
        style.layout(name, [(direction + ".Scrollbar.trough", {
            "sticky": sticky, "children": [(direction + ".Scrollbar.thumb", {"expand": "1", "sticky": "nswe"})]})])
        style.configure(name, background="#2A3541", troughcolor="#161C23",
                        bordercolor="#161C23", lightcolor="#2A3541", darkcolor="#2A3541",
                        borderwidth=0, arrowsize=0, gripcount=0, width=8)
        style.map(name, background=[("active", "#8795A5")])
    style.configure("Treeview",
                    background="#161C23", fieldbackground="#101419",
                    foreground="#CFD7E0", rowheight=max(36, rowheight),
                    borderwidth=0, relief="flat", indent=16,
                    font=(UI_FAMILY, 10))
    style.configure("Treeview.Heading",
                    background="#1D252E", foreground="#A3AFBD",
                    borderwidth=0, relief="flat", padding=(6, 7),
                    font=(UI_FAMILY, 10, "bold"))
    style.map("Treeview.Heading", background=[("active", "#2A3541")])
    style.map("Treeview",
              background=[("selected", "#203640")],
              foreground=[("selected", "#ffffff")])
    style.configure("Vertical.TScrollbar",
                    background="#1D252E", troughcolor="#101419",
                    bordercolor="#101419", arrowcolor="#8795A5")
    style.map("Vertical.TScrollbar", background=[("active", "#2A3541")])

# ======================================================================
# 全局设计令牌 —— 所有窗口（含弹窗）统一取色/取字，禁止各自定义
# ======================================================================
from brand_ui import (BG, PANEL, CARD, ACCENT, OK, WARN, ERR, TEXT, DIM,
                      MUTED, FAMILY)
BG_DEEP = BG
ACCENT2 = ACCENT
if UI_FAMILY != FAMILY:      # 字体族双定义防漂移（见 brand_ui.FAMILY 注释）
    raise RuntimeError(f"字体族令牌不一致: ui_theme.UI_FAMILY={UI_FAMILY!r} "
                       f"vs brand_ui.FAMILY={FAMILY!r}")


def app_icon_path():
    """统一软件图标（exe 资源 / 窗口标题栏 / 任务栏同源 logo.ico）。"""
    import sys as _sys
    base = getattr(_sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, "assets", "brand", "app.ico")
    if not os.path.exists(p):
        p = os.path.join(base, "logo.ico")
    return p if os.path.exists(p) else None


def setup_popup(win, title):
    """弹窗统一外观：标题格式、底色、软件图标。

    iconbitmap 双设置：Windows 上 Toplevel 首帧图标常被吞，
    延迟 250ms 再设一次保证任务栏/标题栏稳定显示。
    """
    t = title if "PPSAI Cleaner" in title else f"PPSAI Cleaner · {title}"
    try:
        win.title(t)
    except Exception:
        pass
    try:
        win.configure(fg_color=BG)
    except Exception:
        pass
    ico = app_icon_path()
    if ico:
        try:
            win.iconbitmap(ico)
            win.after(250, lambda: win.iconbitmap(ico))
        except Exception:
            pass

# ----------------------------------------------------------------------
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

# ----------------------------------------------------------------------
# 自绘标题栏：移除原生 WS_CAPTION（保留缩放边框/任务栏/最小化语义），
# 顶部绘制应用风格标题行：拖动移动、双击最大化、最小化/最大化/关闭。
# ----------------------------------------------------------------------


def install_custom_titlebar(win, title, on_close=None, bg="#060b16",
                            manager="pack", grid_span=2):
    """在窗口顶部安装自绘标题栏。manager: "pack" 或 "grid"。

    grid 模式占用第 0 行整行（调用方需把既有内容下移一行）。
    on_close：关闭按钮回调；缺省走 WM_DELETE_WINDOW 协议（保留关闭确认流）。
    """
    import ctypes
    win.update_idletasks()
    try:
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        GWL_STYLE = -16
        WS_CAPTION = 0x00C00000
        WS_THICKFRAME = 0x00040000
        WS_SYSMENU = 0x00080000
        WS_MINIMIZEBOX = 0x00020000
        WS_MAXIMIZEBOX = 0x00010000
        style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
        new = ((style & ~WS_CAPTION) | WS_THICKFRAME | WS_SYSMENU
               | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
        ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, new)
        SWP_FRAMECHANGED = 0x0020
        ctypes.windll.user32.SetWindowPos(
            hwnd, 0, 0, 0, 0, 0,
            SWP_FRAMECHANGED | 0x0001 | 0x0002 | 0x0004)  # NOSIZE|NOMOVE|NOZORDER
    except Exception:
        pass

    state = {"zoomed": False}

    def do_min():
        try:
            win.iconify()
        except Exception:
            pass

    def do_max():
        try:
            if state["zoomed"]:
                win.state("normal")
                state["zoomed"] = False
                maxbtn.configure(text="□")
            else:
                win.state("zoomed")
                state["zoomed"] = True
                maxbtn.configure(text="❐")
        except Exception:
            pass

    def do_close():
        if on_close:
            on_close()
            return
        try:
            handler = win.protocol("WM_DELETE_WINDOW")
            if handler:
                handler()
                return
        except Exception:
            pass
        win.destroy()

    bar = ctk.CTkFrame(win, fg_color=bg, height=36)
    win._titlebar = bar
    if manager == "grid":
        bar.grid(row=0, column=0, columnspan=grid_span, sticky="ew")
    elif manager == "place":
        # 与既有 pack/grid 内容互不干扰：固定尺寸后覆盖在顶部预留带上方
        spacer = ctk.CTkFrame(win, height=36, fg_color="transparent")
        spacer.pack(side="top", fill="x")
        bar.configure(width=1080, height=36)
        bar.place(x=0, y=0, relwidth=1.0)
    else:
        bar.pack(side="top", fill="x")
    try:
        spacer._is_title_spacer = True
    except Exception:
        pass
    tlabel = ctk.CTkLabel(bar, text=title, height=36,
                          font=ctk.CTkFont(family="Microsoft YaHei UI",
                                           size=12, weight="bold"),
                          text_color="#9fb3cc")
    tlabel.pack(side="left", padx=14)
    btns = ctk.CTkFrame(bar, fg_color="transparent", height=36)
    btns.pack(side="right", padx=6)

    def _btn(text, cmd, hover):
        b = ctk.CTkButton(btns, text=text, width=40, height=26, corner_radius=6,
                           fg_color="transparent", hover_color=hover,
                           text_color="#9fb3cc",
                           font=ctk.CTkFont(size=12, weight="bold"),
                           command=cmd)
        b.pack(side="left", padx=2)
        return b

    maxbtn = _btn("□", do_max, "#1c2942")
    _btn("—", do_min, "#1c2942")
    _btn("✕", do_close, "#c0392b")

    def start_move(e):
        win._tb_dx = e.x
        win._tb_dy = e.y

    def on_move(e):
        if state["zoomed"]:
            return
        try:
            win.geometry(f"+{e.x_root - win._tb_dx}+{e.y_root - win._tb_dy}")
        except Exception:
            pass

    for w in (bar, tlabel):
        w.bind("<Button-1>", start_move)
        w.bind("<B1-Motion>", on_move)
        w.bind("<Double-Button-1>", lambda e: do_max())
    return bar

