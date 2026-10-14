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


def clear_detail_panel(owner, title="📋 详情面板"):
    """清空右侧详情面板并设置标题（所有右侧视图的统一入口）。"""
    try:
        owner.detail_title.configure(text=title)
        for w in owner.detail_body.winfo_children():
            w.destroy()
    except Exception:
        pass
    refresh_detail_scroll(owner)


def show_item_detail(owner, app_id):
    """点击列表行 → 右侧显示该项细节。

    免疫项：显示全部覆盖路径（细项）+ 解锁入口（走 unlock_immunity 确认流，
    Agent 记忆免疫网在内核层硬性拒绝）。
    普通项：显示路径清单 + 手动上锁/解锁入口；细分勾选仍在左侧行内完成。
    """
    app = next((a for a in owner.apps_data if a["id"] == app_id), None)
    if app is None:
        return
    clear_detail_panel(owner, "🔍 项目细节")
    body = owner.detail_body
    locked = app["id"] in getattr(owner, "locked_ids", set())
    owner._detail_current = app_id

    # 头部：大图标 + 名称
    ctk.CTkLabel(body, text=app["icon"], font=F(UI_FAMILY, 34, "normal")
                 ).pack(pady=(14, 2))
    ctk.CTkLabel(body, text=app["name"], font=F(UI_FAMILY, 14, "bold"),
                 text_color="#f3f4f6", wraplength=270, justify="center"
                 ).pack(padx=12, pady=(0, 6))

    # 徽章 + 大小
    if app["immune"]:
        badge_text, badge_color, badge_bg = "🛡️ 系统免疫 · 锁定保护", "#3b82f6", "#172554"
    elif locked:
        badge_text, badge_color, badge_bg = "🛡️ 已上锁保护", "#22c55e", "#052e16"
    elif app["risk_level"] == "safe":
        badge_text, badge_color, badge_bg = "🧹 安全清理项", "#10b981", "#064e3b"
    else:
        badge_text, badge_color, badge_bg = "⚠️ 风险清理项", "#ef4444", "#450a0a"
    ctk.CTkLabel(body, text=badge_text, font=F(UI_FAMILY, 12, "bold"),
                 text_color=badge_color, fg_color=badge_bg,
                 corner_radius=6, height=28).pack(pady=(0, 4))
    ctk.CTkLabel(body, text=format_size(owner.sizes.get(app_id, 0)),
                 font=F(MONO_FAMILY, 20, "bold"), text_color="#fbbf24"
                 ).pack(pady=(0, 2))
    ctk.CTkLabel(body, text=app.get("risk_desc", ""),
                 font=F(UI_FAMILY, 11), text_color="#94a3b8",
                 wraplength=260, justify="center").pack(padx=12, pady=(0, 8))

    # 路径细项（免疫项的"查看细项"诉求在此满足）
    ctk.CTkLabel(body, text="─" * 26, text_color="#1e293b").pack(pady=(2, 2))
    ctk.CTkLabel(body, text="🗂️ 覆盖路径细项", font=F(UI_FAMILY, 12, "bold"),
                 text_color="#7dd3fc", anchor="w").pack(fill="x", padx=14, pady=(0, 2))
    paths = app.get("paths", []) or []
    choices = getattr(owner, "subpath_choices", {}).get(app_id, {})
    if not paths:
        ctk.CTkLabel(body, text="（无路径定义）", font=F(MONO_FAMILY, 11),
                     text_color="#475569", anchor="w").pack(fill="x", padx=18)
    for p in paths:
        ptxt = str(p)
        shown = ptxt if len(ptxt) <= 46 else ptxt[:45] + "…"
        mark = "" if app["immune"] else (
            "☑ " if choices.get(ptxt.lower(), True) else "☐ ")
        ctk.CTkLabel(body, text=mark + shown, font=F(MONO_FAMILY, 10),
                     text_color="#94a3b8", anchor="w", wraplength=265,
                     justify="left").pack(fill="x", padx=16, pady=1)
    # 已迁移标注：Junction 原路径，真实数据在目标盘
    try:
        import migrate_core as _mc
        seen_bases = set()
        for p in paths:
            base = str(p).split("*")[0].rstrip(chr(47) + chr(92))
            if not base or base in seen_bases:
                continue
            seen_bases.add(base)
            real = _mc._exp(base)
            if _mc.is_junction(real):
                tgt = _mc.migrated_target_of(real)
                if tgt:
                    drv = os.path.splitdrive(tgt)[0].upper()
                    ctk.CTkLabel(body, text=f"⤳ 已迁移 → {drv} 盘：{tgt}（C 盘不占用）",
                                 font=F(UI_FAMILY, 10), text_color="#34d399",
                                 anchor="w", wraplength=265,
                                 justify="left").pack(fill="x", padx=16, pady=(0, 2))
    except Exception:
        pass

    # 操作区
    btn_box = ctk.CTkFrame(body, fg_color="transparent")
    btn_box.pack(fill="x", padx=12, pady=(14, 12))
    if app["immune"]:
        ctk.CTkLabel(btn_box, text="该项为出厂默认保护，不参与任何清理。",
                     font=F(UI_FAMILY, 11), text_color="#64748b",
                     wraplength=260).pack(pady=(0, 6))
        ctk.CTkButton(
            btn_box, text="🔓 解锁此项（将随安全清理删除）",
            font=F(UI_FAMILY, 12, "bold"), height=36,
            fg_color="#7f1d1d", hover_color="#991b1b",
            command=lambda a=app: owner.unlock_immunity(a),
        ).pack(fill="x")
    else:
        lock_txt = "🔓 解除上锁（恢复参与清理）" if locked else "🔒 上锁保护（永不清理）"
        ctk.CTkButton(
            btn_box, text=lock_txt, font=F(UI_FAMILY, 12, "bold"), height=36,
            fg_color="#065f46" if locked else "#334155",
            hover_color="#b45309" if locked else "#7f1d1d",
            command=lambda a=app: (owner.toggle_lock(a),
                                   show_item_detail(owner, a["id"])),
        ).pack(fill="x")
        ctk.CTkLabel(btn_box, text="取消某条路径的勾选：在左侧该行点击「▸ 细分」。",
                     font=F(UI_FAMILY, 10), text_color="#475569",
                     wraplength=260).pack(pady=(6, 0))
    refresh_detail_scroll(owner)


def _style_scrollbar(sf, slot="#090d16", thumb="#1e293b", hover="#334155"):
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
    """为一个可清理项目创建一行，并把控件登记到 owner.app_rows 等映射里。

    v3.9.13 性能重写：此前每行 15-18 个 tk 窗口（CTk 控件内部还各含
    canvas/label），91 行 ≈ 1400 窗口，任何滚动/重建的重排成本都极高
    —— 这就是「列表非常卡」的根因。现在全部换成纯 tk 控件，每行
    7-9 个窗口，重排成本约降 3 倍。交互面完全保持：
      owner.app_rows[id] = {"size","badge","frame","fill"}   键不变
      owner.app_expand_btns[id]  → configure(text=) 兼容（tk.Label）
      owner.app_checkboxes[id]   → select/deselect 兼容（tk.Checkbutton）
    """
    row_bg = "#111827" if idx % 2 == 0 else "#1f2937"
    row_frame = _tk.Frame(owner.scroll_frame, bg=row_bg, height=52,
                          bd=0, highlightthickness=0)
    row_frame.pack(fill="x", padx=5, pady=4)
    # 统一行高：防止长名把行撑乱/控件重叠，也让滚动定位的 y 计算稳定
    row_frame.pack_propagate(False)

    locked = app["id"] in getattr(owner, "locked_ids", set())

    # ---- 左侧：勾选框 / 锁图标 ----
    if app["immune"]:
        _tk.Label(row_frame, text="\U0001F512", bg=row_bg, fg="#3b82f6",
                  font=(UI_FAMILY, 14), bd=0,
                  ).pack(side="left", padx=(15, 8))
    elif locked:
        # 用户手动上锁：绿锁，区分系统免疫的蓝锁。锁定 = 不参与清理。
        _tk.Label(row_frame, text="\U0001F512", bg=row_bg, fg="#22c55e",
                  font=(UI_FAMILY, 14), bd=0,
                  ).pack(side="left", padx=(15, 8))
    else:
        # 勾选状态持久化：重建列表（排序/扫描/清理后）时恢复用户上次的选择
        default_on = 1 if app["risk_level"] == "safe" else 0
        remembered = getattr(owner, "selection_state", {}).get(app["id"])
        var = ctk.IntVar(value=default_on if remembered is None else remembered)
        owner.app_checkbox_vars[app["id"]] = var
        chk = _tk.Checkbutton(
            row_frame, text="", variable=var, bg=row_bg, fg="#e2e8f0",
            activebackground=row_bg, activeforeground="#e2e8f0",
            selectcolor="#334155", highlightthickness=0, bd=0,
            relief="flat", cursor="hand2",
            command=lambda a=app: owner._remember_selection(a))
        chk.pack(side="left", padx=(15, 8))
        owner.app_checkboxes[app["id"]] = chk

    # 有垃圾容量的行在最左侧加一条 3px 橙色竖条，一眼可辨
    # （必须在可扩展的名称标签之前 pack，否则剩余宽度被吃光会显示不出来）
    app_size = owner.sizes.get(app["id"], 0)
    if app_size > 0 and not app["immune"] and not locked:
        _tk.Frame(row_frame, bg="#f59e0b", width=3, bd=0,
                  highlightthickness=0).pack(side="left", fill="y",
                                             padx=(0, 2))

    # ---- 右侧：细分 / 上锁 / 徽章 / 容量（先占位，名称最后吃剩余宽度）----
    if not app["immune"]:
        # 细分管理：展开该项的清理子路径清单，每条可独立勾选（可选状态）
        btn_expand = _tk.Label(
            row_frame, text="▸ 细分", bg="#312e81", fg="#c7d2fe",
            font=(UI_FAMILY, 11, "bold"), padx=9, pady=3, cursor="hand2")
        btn_expand.pack(side="right", padx=(6, 15))
        if not hasattr(owner, "app_expand_btns"):
            owner.app_expand_btns = {}
        owner.app_expand_btns[app["id"]] = btn_expand
        _hover_chip(btn_expand, base="#312e81", hover="#4338ca",
                    command=lambda a=app, b=None: owner.toggle_subpaths(a, b))
        if not locked:
            # 手动上锁开关：醒目底色，点击即锁定并持久记忆。
            btn_lock = _tk.Label(
                row_frame, text="\U0001F512 上锁", bg="#334155", fg="#e2e8f0",
                font=(UI_FAMILY, 11, "bold"), padx=9, pady=3, cursor="hand2")
            btn_lock.pack(side="right")
            _hover_chip(btn_lock, base="#334155", hover="#7f1d1d",
                        command=lambda a=app: owner.toggle_lock(a))
        else:
            # 已上锁行保留解锁入口：点击即解锁并清除持久记忆。
            btn_lock = _tk.Label(
                row_frame, text="\U0001F513 解锁", bg="#065f46", fg="#d1fae5",
                font=(UI_FAMILY, 11, "bold"), padx=9, pady=3, cursor="hand2")
            btn_lock.pack(side="right")
            _hover_chip(btn_lock, base="#065f46", hover="#b45309",
                        command=lambda a=app: owner.toggle_lock(a))
    else:
        # 免疫行：同样提供「细分」查看子路径清单（只读）+ 面板内解锁入口
        btn_expand = _tk.Label(
            row_frame, text="▸ 细分", bg="#1e3a5f", fg="#bfdbfe",
            font=(UI_FAMILY, 11, "bold"), padx=9, pady=3, cursor="hand2")
        btn_expand.pack(side="right", padx=(6, 15))
        if not hasattr(owner, "app_expand_btns"):
            owner.app_expand_btns = {}
        owner.app_expand_btns[app["id"]] = btn_expand
        _hover_chip(btn_expand, base="#1e3a5f", hover="#2563eb",
                    command=lambda a=app, b=None: owner.toggle_subpaths(a, b))

    if app["immune"]:
        badge_text, badge_color, badge_bg = "\U0001F6E1\uFE0F 锁定保护", "#3b82f6", "#172554"
    elif locked:
        badge_text, badge_color, badge_bg = "\U0001F6E1\uFE0F 已上锁保护", "#22c55e", "#052e16"
    elif app["risk_level"] == "safe":
        badge_text, badge_color, badge_bg = "\U0001F9F9 安全清理", "#10b981", "#064e3b"
    else:
        badge_text, badge_color, badge_bg = "⚠️ 风险清理", "#ef4444", "#450a0a"

    lbl_badge = _tk.Label(
        row_frame, text=badge_text, font=(UI_FAMILY, 11, "bold"),
        fg=badge_color, bg=badge_bg, padx=9, pady=3)
    lbl_badge.pack(side="right", padx=8)

    # 原版字节码 L668-673：建行时即回填已扫描大小，恢复时曾丢失。
    # 视觉区分：有垃圾容量 = 橙色加粗；无残留 = 暗灰弱化。
    if app_size > 0:
        size_text = "● " + format_size(app_size)
        size_color, size_weight = "#fbbf24", "bold"
    else:
        # 当前视图对应阶段已扫描完毕而容量为 0 → 无残留；否则显示等待。
        view = getattr(owner, "current_view", "safe")
        tier_state = owner.safe_state if view == "safe" else owner.risk_state
        scanned = tier_state in ("ready", "cleaning", "done")
        if scanned:
            size_text, size_color, size_weight = "✨ 无残留垃圾", "#475569", "normal"
        else:
            size_text, size_color, size_weight = "等待扫描...", "#9ca3af", "normal"

    lbl_size = _tk.Label(
        row_frame, text=size_text,
        font=(MONO_FAMILY, 12, size_weight), fg=size_color, bg=row_bg)
    lbl_size.pack(side="right", padx=8)

    # ---- 名称（含图标）：pack 顺序最后 + fill/expand，吃掉中间剩余宽度；
    # 超长名由 Tk 自动裁切，不会挤压右侧控件 ----
    lbl_name = _tk.Label(
        row_frame, text=f'{app["icon"]}  {app["name"]}', bg=row_bg,
        fg="#64748b" if locked else "#f3f4f6",
        font=(UI_FAMILY, 13, "bold"), anchor="w")
    lbl_name.pack(side="left", fill="x", expand=True, padx=(4, 8))

    # 清理进度填充层：整行作为进度底条，清理时从左到右填充可见效果。
    # place 挂在行上并沉底，不干扰 pack 布局。
    fill_bar = _tk.Frame(row_frame, bg="#14532d", bd=0, highlightthickness=0)
    fill_bar.place(relx=0, rely=0, relwidth=0.0, relheight=1.0)
    fill_bar.lower()

    owner.app_rows[app["id"]] = {
        "size": lbl_size,
        "badge": lbl_badge,
        "frame": row_frame,
        "fill": fill_bar,
    }

    # 行点击 → 右侧详情面板（按钮/勾选框自身事件不受影响；
    # fill_bar 沉底但仍是独立窗口，点击行空白落在此处，一并绑定）
    for w in (row_frame, fill_bar, lbl_name, lbl_size, lbl_badge):
        _bind_row_click(w, owner, app["id"])


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
            _fill_configure_color(fill, "#1e3a5f")   # 蓝灰：扫描中（低调）
            fill.place(relwidth=1.0)
            fill.lower()
            return
        # done：从 0 → 1 的填充动画（每帧 16ms，共约 0.4s）
        _fill_configure_color(fill, "#14532d")       # 绿：已完成
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
    """扫描/清理完成的结构化报告 → 右侧详情面板（不再弹窗）。

    板式：标题 → 大数字 → 分项 → TOP5 → 按钮行，全部渲染进 detail_body。
    """
    try:
        clear_detail_panel(owner, "📊 报告面板")
        body = owner.detail_body

        is_scan = (kind == "scan")
        is_safe = (tier_or_type == "safe")
        accent = "#22c55e" if (is_safe or not is_scan) else "#ef4444"
        title = (f"{'✅ 安全扫描完成' if is_safe else '🔥 深度扫描完成'}"
                 if is_scan else
                 f"{'🧹 安全清理完成' if is_safe else '🧹 深度清理完成'}")

        # 标题带
        ctk.CTkLabel(body, text=title, font=F(UI_FAMILY, 18, "bold"),
                     text_color=accent).pack(pady=(16, 2))
        ctk.CTkLabel(body, text=("以下为本次扫描的统计明细" if is_scan
                                 else "以下为本次清理的执行明细"),
                     font=F(UI_FAMILY, 11), text_color="#64748b").pack(pady=(0, 8))

        # 大数字区
        if is_scan:
            big = (owner.safe_bytes if is_safe else owner.risk_bytes)
            big_label = "本次可清理总量" if is_safe else "本次发现风险总量"
        else:
            big = freed_bytes or 0
            big_label = "本轮实际释放"
        ctk.CTkLabel(body, text=big_label, font=F(UI_FAMILY, 12),
                     text_color="#94a3b8").pack(pady=(8, 0))
        ctk.CTkLabel(body, text=format_size(big), font=F(UI_FAMILY, 28, "bold"),
                     text_color="#fbbf24" if is_scan else "#4ade80").pack(pady=(0, 8))

        # 分项明细（label 左 · 值右）
        if is_scan:
            if is_safe:
                stage_pool = [a for a in owner.get_filtered_apps()
                              if a["immune"] or a.get("risk_level") == "safe"]
            else:
                stage_pool = [a for a in owner.get_filtered_apps()
                              if (not a["immune"]) and a.get("risk_level") == "risk"]
            rows = [
                ("🛡️ 系统免疫（自动锁定·不清理）", getattr(owner, "total_immune_bytes", 0)),
                ("🔒 手动上锁（您锁定·不清理）", getattr(owner, "locked_user_bytes", 0)),
                ("📋 本次扫描项目数", f"{len(stage_pool)} 项"),
            ]
        else:
            detail = getattr(owner, "last_clean_detail", []) or []
            rows = [
                ("✨ 本轮已净化项目", f"{len(detail)} 项"),
                ("🧹 累计安全清理", format_size(getattr(owner, "freed_safe", 0)) if is_safe else format_size(getattr(owner, "freed_risk", 0))),
                ("🛡️ 系统免疫（未触碰）", format_size(getattr(owner, "total_immune_bytes", 0))),
            ]
        for label, val in rows:
            line = ctk.CTkFrame(body, fg_color="transparent")
            line.pack(fill="x", pady=2)
            ctk.CTkLabel(line, text=label, font=F(UI_FAMILY, 12),
                         text_color="#cbd5e1", anchor="w").pack(side="left")
            ctk.CTkLabel(line, text=str(val), font=F(MONO_FAMILY, 12, "bold"),
                         text_color="#e2e8f0", anchor="e").pack(side="right")

        # TOP5 区
        ctk.CTkLabel(body, text=("─" * 24), text_color="#1e293b").pack(pady=(8, 2))
        ctk.CTkLabel(body, text="📊 容量 TOP 5" if is_scan else "🏆 释放 TOP 5",
                     font=F(UI_FAMILY, 12, "bold"), text_color="#7dd3fc",
                     anchor="w").pack(fill="x", pady=(2, 4))
        if is_scan:
            if is_safe:
                pool = [a for a in owner.get_filtered_apps()
                        if a["immune"] or a.get("risk_level") == "safe"]
            else:
                pool = [a for a in owner.get_filtered_apps()
                        if (not a["immune"]) and a.get("risk_level") == "risk"]
            tops = sorted(pool, key=lambda a: owner.sizes.get(a["id"], 0), reverse=True)[:5]
            tops = [(a["name"], owner.sizes.get(a["id"], 0)) for a in tops if owner.sizes.get(a["id"], 0) > 0]
        else:
            tops = sorted(getattr(owner, "last_clean_detail", []) or [],
                          key=lambda t: t[1], reverse=True)[:5]
            tops = [(n, s) for n, s in tops if s > 0]
        if not tops:
            ctk.CTkLabel(body, text="（无明细数据）", font=F(UI_FAMILY, 11),
                         text_color="#475569").pack(anchor="w")
        for i, (name, size) in enumerate(tops, 1):
            line = ctk.CTkFrame(body, fg_color="transparent")
            line.pack(fill="x", pady=1)
            ctk.CTkLabel(line, text=f"{i}. {name}", font=F(MONO_FAMILY, 11),
                         text_color="#94a3b8", anchor="w").pack(side="left")
            ctk.CTkLabel(line, text=format_size(size), font=F(MONO_FAMILY, 11, "bold"),
                         text_color="#fbbf24" if is_scan else "#4ade80",
                         anchor="e").pack(side="right")

        # 按钮行
        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=(12, 10))
        if is_scan:
            ctk.CTkButton(btns, text=("🧹 开始安全清理" if is_safe else "🔴 确认深度清理"),
                          font=F(UI_FAMILY, 13, "bold"), height=40,
                          fg_color="#10b981" if is_safe else "#7f1d1d",
                          hover_color="#34d399" if is_safe else "#991b1b",
                          command=lambda: owner.start_cleanup_flow(
                              "safe" if is_safe else "risk")).pack(fill="x")
        else:
            ctk.CTkButton(btns, text="知道了", font=F(UI_FAMILY, 13, "bold"),
                          height=40, fg_color="#065f46", hover_color="#10b981",
                          command=lambda: clear_detail_panel(owner)).pack(fill="x")
    except Exception:
        pass
    refresh_detail_scroll(owner)


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

        head = ctk.CTkFrame(win, fg_color="#450a0a", corner_radius=0)
        head.pack(fill="x")
        ctk.CTkLabel(head, text="⚠️ 解除系统免疫", font=F(UI_FAMILY, 19, "bold"),
                     text_color="#f87171").pack(pady=(16, 4))

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=24)
        ctk.CTkLabel(body, text=f"项目：{app['name']}", font=F(UI_FAMILY, 14, "bold"),
                     text_color="#f3f4f6", anchor="w").pack(fill="x", pady=(14, 4))
        ctk.CTkLabel(body,
                     text="解除后此项将立即参与扫描与清理，\n"
                          "其缓存/日志/临时文件可能在下次清理中被删除。\n"
                          "此操作不可自动恢复（可重新扫描后再次手动上锁）。",
                     font=F(UI_FAMILY, 12), text_color="#94a3b8",
                     justify="left", anchor="w").pack(fill="x", pady=(0, 10))

        btns = ctk.CTkFrame(win, fg_color="transparent")
        btns.pack(fill="x", padx=24, pady=(2, 16))

        def _do():
            win.destroy()
            try:
                on_confirm(app)
            except Exception:
                pass
        ctk.CTkButton(btns, text="🔓 确认解除免疫", font=F(UI_FAMILY, 13, "bold"),
                      height=40, fg_color="#7f1d1d", hover_color="#b91c1c",
                      command=_do).pack(side="right", padx=(10, 0))
        ctk.CTkButton(btns, text="取消", font=F(UI_FAMILY, 13), height=40,
                      fg_color="#1e293b", hover_color="#334155",
                      command=win.destroy).pack(side="right")
    except Exception:
        pass


def show_auth_dialog(owner, hwid, clean_type):
    """授权拦截对话框：扫码付款 + 云端轮询自动解锁 + 手动粘贴密钥。"""
    dialog = ctk.CTkToplevel(owner)
    dialog.title("物理级操作安全拦截")
    dialog.geometry("520x550")
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    dialog.grab_set()

    ctk.CTkLabel(dialog, text="⚠️ 安全拦截: 需要数字签名授权",
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=18, weight="bold"),
                 text_color="#ef4444").pack(pady=(15, 5))

    desc = ("由于底层物理净化需要修改和删除系统内核缓存文件，\n"
            "必须激活特权数字证书方可继续。安全防护网已自动拦截此操作。")
    ctk.CTkLabel(dialog, text=desc,
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
                 text_color="#cbd5e1").pack(pady=2)

    qr_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    qr_frame.pack(pady=5)

    try:
        mobile_url = f"https://ppsai.chat/safecleaner/pay.html?hwid={hwid}"
        qr_api_url = f"https://ppsai.chat/api/qrcode?data={urllib.parse.quote(mobile_url)}"
        req = urllib.request.Request(qr_api_url, headers={"User-Agent": "SafeCleanerPro-Client"})
        with urllib.request.urlopen(req, timeout=4) as response:
            qr_img_data = response.read()
        from PIL import Image
        img = Image.open(io.BytesIO(qr_img_data))
        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(150, 150))
        ctk.CTkLabel(qr_frame, image=ctk_img, text="").pack()
    except Exception:
        ctk.CTkLabel(qr_frame,
                     text="[⚠️ 无法加载扫码二维码，请确保网络连接正常]",
                     text_color="#ef4444",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=11)).pack()

    guide_text = ("📱 极速推荐：请使用手机微信/支付宝扫描上方二维码\n"
                  "在手机上完成付款核销，电脑客户端将 1 秒钟瞬间解锁直接运行！")
    ctk.CTkLabel(dialog, text=guide_text,
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=11, weight="bold"),
                 text_color="#38bdf8").pack(pady=2)

    ctk.CTkLabel(dialog, text="🔄 正在实时感应云端付款状态，支付成功后此窗口将全自动解锁...",
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=10),
                 text_color="#10b981").pack(pady=2)

    hwid_frame = ctk.CTkFrame(dialog, fg_color="#1e293b", height=45)
    hwid_frame.pack(pady=5, padx=40, fill="x")
    hwid_frame.pack_propagate(False)
    ctk.CTkLabel(hwid_frame, text=f"设备 ID 指纹: {hwid}",
                 font=ctk.CTkFont(family="Consolas", size=10),
                 text_color="#94a3b8").pack(pady=6)

    fallback_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    fallback_frame.pack(pady=5, padx=40, fill="x")

    entry_key = ctk.CTkEntry(fallback_frame,
                             placeholder_text="或者在此手动粘贴激活秘钥 (License Key)...",
                             justify="center",
                             font=ctk.CTkFont(family="Microsoft YaHei UI", size=11))
    entry_key.pack(side="left", fill="x", expand=True, padx=(0, 10))

    def on_verify():
        key = entry_key.get().strip()
        valid = False
        if verify_license(hwid, key):
            valid = True
        else:
            try:
                from hwid_utils import get_hwid_wmic
                if verify_license(get_hwid_wmic(), key):
                    valid = True
            except Exception:
                pass

        if valid:
            save_license_key(key)
            owner.polling_active = False
            dialog.destroy()
            owner.append_log(">>> 数字签名核销通过！License 代码已存盘本地与全局目录。")
            if clean_type == "risk":
                owner.show_risk_confirmation(clean_type, lambda: owner.execute_cleaning(clean_type))
                return
            owner.execute_cleaning(clean_type)
            return

        owner.append_log(">>> 校验错误: 授权码无效或与当前 HWID 物理指纹不匹配。")

    ctk.CTkButton(fallback_frame, text="手动验证", width=80,
                  font=ctk.CTkFont(weight="bold"),
                  fg_color="#22c55e", hover_color="#4ade80",
                  command=on_verify).pack(side="right")

    owner.polling_active = True

    def poll_status():
        url = f"https://ppsai.chat/api/check_activation?hwid={hwid}"
        while owner.polling_active and dialog.winfo_exists():
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "SafeCleanerPro-Client"})
                with urllib.request.urlopen(req, timeout=3) as response:
                    if response.status == 200:
                        res_data = json.loads(response.read().decode("utf-8"))
                        if res_data.get("activated") and res_data.get("license_key"):
                            key = res_data["license_key"]
                            valid = False
                            if verify_license(hwid, key):
                                valid = True
                            else:
                                try:
                                    from hwid_utils import get_hwid_wmic
                                    if verify_license(get_hwid_wmic(), key):
                                        valid = True
                                except Exception:
                                    pass
                            if valid:
                                save_license_key(key)
                                owner.polling_active = False

                                def auto_activate():
                                    dialog.destroy()
                                    owner.append_log(">>> 云端自动感应核销成功！数字签名证书已下载并自动部署！")
                                    if clean_type == "risk":
                                        owner.show_risk_confirmation(
                                            clean_type, lambda: owner.execute_cleaning(clean_type))
                                        return
                                    owner.execute_cleaning(clean_type)

                                owner.after(0, auto_activate)
                                return
            except Exception:
                pass
            time.sleep(3)

    threading.Thread(target=poll_status, daemon=True).start()

    def on_close():
        owner.polling_active = False
        dialog.destroy()

    dialog.protocol("WM_DELETE_WINDOW", on_close)


def show_risk_confirmation(owner, clean_type, on_confirm):
    """风险清理前的二次确认。"""
    win = ctk.CTkToplevel(owner)
    win.title("⚠️ 高风险清理警告")
    win.geometry("640x400")
    win.resizable(False, False)
    win.grab_set()

    ctk.CTkLabel(win, text="⚠️ 高风险清理警告",
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=20, weight="bold"),
                 text_color="#ef4444").pack(pady=(24, 10))
    ctk.CTkLabel(win,
                 text="风险清理将删除被判定为非安全类别的缓存与残留文件。\n"
                      "此操作不可撤销，请确认你已备份重要数据。",
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=13),
                 text_color="#94a3b8", justify="center").pack(pady=(0, 18))

    def confirm():
        win.destroy()
        on_confirm()

    def cancel():
        win.destroy()

    bar = ctk.CTkFrame(win, fg_color="transparent")
    bar.pack(pady=8)
    ctk.CTkButton(bar, text="确认清理", fg_color="#ef4444", hover_color="#f87171",
                  command=confirm).pack(side="left", padx=8)
    ctk.CTkButton(bar, text="取消", command=cancel).pack(side="left", padx=8)


def show_protection_list(owner):
    """保护清单透明化 → 渲染进右侧详情面板（不再弹窗）。

    分项列出「系统免疫」与「手动上锁」每一项的名称与容量；
    免疫项行尾附「查看细项」入口（点开右侧该项详情，可解锁）。
    """
    try:
        clear_detail_panel(owner, "🛡️ 保护清单")
        body = owner.detail_body

        ctk.CTkLabel(body, text="🛡️ 核心安全锁定保护",
                     font=F(UI_FAMILY, 16, "bold"), text_color="#f8fafc"
                     ).pack(pady=(14, 2))
        ctk.CTkLabel(body, text="以下项目被永久保护，任何清理操作都不会触碰。",
                     font=F(UI_FAMILY, 10), text_color="#94a3b8",
                     wraplength=270, justify="center").pack(pady=(0, 6))

        by_name = {a["name"]: a for a in owner.apps_data}

        def section(title, color, items, note):
            ctk.CTkLabel(body, text=title, font=F(UI_FAMILY, 12, "bold"),
                         text_color=color, anchor="w",
                         wraplength=270, justify="left").pack(fill="x", padx=10,
                                                              pady=(12, 4))
            if not items:
                ctk.CTkLabel(body, text=note, font=F(UI_FAMILY, 11),
                             text_color="#64748b", anchor="w", wraplength=260,
                             justify="left").pack(fill="x", padx=20)
                return
            for name, size in sorted(items.items(), key=lambda kv: kv[1], reverse=True):
                row = ctk.CTkFrame(body, fg_color="#1e293b", corner_radius=6)
                row.pack(fill="x", padx=8, pady=2)
                ctk.CTkLabel(row, text=name, font=F(UI_FAMILY, 11),
                             text_color="#cbd5e1", anchor="w", wraplength=180,
                             justify="left").pack(side="left", padx=10, pady=8)
                ctk.CTkLabel(row, text=format_size(size), font=F(MONO_FAMILY, 11, "bold"),
                             text_color=color).pack(side="right", padx=10, pady=8)
                app = by_name.get(name)
                if app is not None and app.get("immune"):
                    ctk.CTkButton(row, text="细项", width=44, height=24,
                                  font=F(UI_FAMILY, 10, "bold"),
                                  fg_color="#1e3a5f", hover_color="#2563eb",
                                  command=lambda a=app: show_item_detail(owner, a["id"])
                                  ).pack(side="right", padx=(0, 4))

        section("🔒 系统免疫（Agent 记忆与工作区，出厂默认保护）", "#3b82f6",
                dict(getattr(owner, "immune_items", {})), "本轮扫描未统计到免疫项容量。")
        section("🔐 手动上锁（您亲手锁定的项目，跨启动记忆）", "#22c55e",
                dict(getattr(owner, "locked_items", {})),
                "暂无手动上锁项。点击列表任意行，在右侧详情中即可上锁。")
    except Exception:
        pass
    refresh_detail_scroll(owner)


def show_file_viewer(owner, app):
    """查看某项目的文件清单，可逐文件勾选/排除。"""
    dialog = ctk.CTkToplevel(owner)
    dialog.title(f'文件详情预览 - {app["name"]}')
    dialog.geometry("780x560")
    dialog.resizable(False, False)
    dialog.attributes("-topmost", True)
    dialog.grab_set()

    ctk.CTkLabel(dialog, text=f'📂 {app["name"]} - 文件清理清单',
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=18, weight="bold"),
                 text_color="#f8fafc").pack(pady=(15, 5))

    risk_color = "#ef4444" if app["risk_level"] == "risk" else "#10b981"
    risk_label_text = (f'风险等级: {"⚠️ 高风险项目" if app["risk_level"] == "risk" else "🟢 安全清理项目"}')

    info_frame = ctk.CTkFrame(dialog, fg_color="#0f172a")
    info_frame.pack(fill="x", padx=20, pady=5)

    ctk.CTkLabel(info_frame, text=risk_label_text,
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
                 text_color=risk_color).pack(anchor="w", padx=15, pady=(8, 2))
    ctk.CTkLabel(info_frame,
                 text=f'安全提示: {app.get("risk_desc", "本项清理无任何数据风险。")}',
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
                 text_color="#94a3b8").pack(anchor="w", padx=15, pady=(0, 8))

    files_scroll = ctk.CTkScrollableFrame(dialog, fg_color="#090d16",
                                          scrollbar_button_color="#1e293b",
                                          scrollbar_button_hover_color="#334155")
    _style_scrollbar(files_scroll, slot="#090d16")
    files_scroll.pack(fill="both", expand=True, padx=20, pady=6)

    loading_label = ctk.CTkLabel(files_scroll,
                                 text="正在分析文件清单，大目录可能需要片刻，请稍候...",
                                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=13),
                                 text_color="#38bdf8")
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
                ctk.CTkLabel(files_scroll, text="此项目目前没有扫描到任何冗余缓存废料。",
                             font=ctk.CTkFont(family="Microsoft YaHei UI", size=13),
                             text_color="#64748b").pack(pady=50)
                return

            summary = "共 %d 个文件 · 合计 %s" % (total_count, format_size(total_bytes))
            if total_count > len(shown):
                summary += "（仅展示最大的 %d 个）" % len(shown)
            ctk.CTkLabel(files_scroll, text=summary,
                         font=ctk.CTkFont(family="Consolas", size=11),
                         text_color="#38bdf8").pack(anchor="w", padx=12, pady=(2, 4))

            if any(is_personal_file(p) for p, _ in files):
                ctk.CTkLabel(
                    info_frame,
                    text="⚠️ 提示：检测到当前目录包含用户个人文档/媒体资产，已默认取消勾选以防误删！",
                    font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                    text_color="#fbbf24").pack(anchor="w", padx=15, pady=(2, 8))

            col_frame = ctk.CTkFrame(files_scroll, fg_color="transparent")
            col_frame.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(col_frame, text="要清理的文件路径 (已按大小降序排序)",
                         font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                         text_color="#64748b").pack(side="left")
            ctk.CTkLabel(col_frame, text="大小",
                         font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                         text_color="#64748b").pack(side="right", padx=(0, 20))

            for path, size in shown:
                file_row = ctk.CTkFrame(files_scroll, fg_color="#1e293b", corner_radius=4)
                file_row.pack(fill="x", padx=5, pady=2)

                is_personal = is_personal_file(path)
                display_path = ("⚠️ [用户数据] " if is_personal else "") + obfuscate_path(path)

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
                    font=ctk.CTkFont(family="Consolas", size=12),
                    text_color="#fbbf24" if is_personal else "#cbd5e1",
                    width=18, height=18,
                    command=make_toggle(path, var))
                chk_file.pack(side="left", padx=10, pady=6)

                if path not in owner.skipped_files:
                    chk_file.select()
                else:
                    chk_file.deselect()

                ctk.CTkLabel(file_row, text=format_size(size),
                             font=ctk.CTkFont(family="Consolas", size=12),
                             text_color="#fbbf24" if is_personal else "#94a3b8"
                             ).pack(side="right", padx=15, pady=6)

            files_scroll.update_idletasks()
            try:
                files_scroll._parent_canvas.configure(
                    scrollregion=files_scroll._parent_canvas.bbox("all"))
                files_scroll._parent_canvas.yview_moveto(0.0)
            except Exception:
                pass
            autohide_scrollbar(owner, files_scroll)

        owner.after(0, update_ui)

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
                  font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                  fg_color="#3b82f6", hover_color="#60a5fa",
                  width=110, height=32, command=select_all).pack(side="left", padx=5)
    ctk.CTkButton(bottom_frame, text="全部排除",
                  font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                  fg_color="#475569", hover_color="#64748b",
                  width=110, height=32, command=deselect_all).pack(side="left", padx=5)
    ctk.CTkButton(bottom_frame, text="确认保存设置",
                  font=ctk.CTkFont(family="Microsoft YaHei UI", size=12, weight="bold"),
                  fg_color="#10b981", hover_color="#34d399",
                  width=130, height=32, command=dialog.destroy).pack(side="right", padx=5)


def build_ui(owner, version):
    # Configure Grid Layout (2 columns: Sidebar & Main Panel)
    owner.grid_columnconfigure(0, weight=1, minsize=280)
    owner.grid_columnconfigure(1, weight=3, minsize=1020)
    owner.grid_rowconfigure(0, weight=1)

    # ==========================================
    # LEFT SIDEBAR FRAME
    # ==========================================
    owner.sidebar_frame = ctk.CTkFrame(owner, width=280, corner_radius=0, fg_color="#0f172a")
    owner.sidebar_frame.grid(row=0, column=0, sticky="nsew")
    owner.sidebar_frame.grid_rowconfigure(5, weight=1)  # spacer

    # Logo/Title
    owner.logo_label = ctk.CTkLabel(
        owner.sidebar_frame,
        text="SafeCleaner Pro",
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=28, weight="bold"),
        text_color="#00f0ff"
    )
    owner.logo_label.grid(row=0, column=0, padx=20, pady=(30, 8))

    owner.sub_logo = ctk.CTkLabel(
        owner.sidebar_frame,
        text="极客级深度物理引擎",
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=13),
        text_color="#64748b"
    )
    owner.sub_logo.grid(row=1, column=0, padx=20, pady=(0, 20))

    # Stat Card 1: Scanned Size（安全/深度两细分，均不含上锁与系统免疫项）
    owner.card_scanned = ctk.CTkFrame(owner.sidebar_frame, fg_color="#1e293b", corner_radius=10, height=118)
    owner.card_scanned.grid(row=2, column=0, padx=20, pady=8, sticky="ew")
    owner.card_scanned.grid_propagate(False)
    ctk.CTkLabel(owner.card_scanned, text="🔴 扫描垃圾总容量",
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=13),
                 text_color="#ef4444").pack(pady=(10, 0))
    owner.lbl_scanned_val = ctk.CTkLabel(owner.card_scanned, text="0.00 B",
                                        font=ctk.CTkFont(family="Microsoft YaHei UI", size=22, weight="bold"),
                                        text_color="#f87171")
    owner.lbl_scanned_val.pack()
    owner.lbl_scanned_breakdown = ctk.CTkLabel(
        owner.card_scanned,
        text="安全扫描: 0.00 B   深度扫描: 0.00 B",
        font=ctk.CTkFont(family="Consolas", size=10),
        text_color="#94a3b8")
    owner.lbl_scanned_breakdown.pack(pady=(1, 8))

    # Stat Card 2: Immune Size（系统免疫 + 用户手动上锁，均不会清理）
    owner.card_immune = ctk.CTkFrame(owner.sidebar_frame, fg_color="#1e293b", corner_radius=10, height=118)
    owner.card_immune.grid(row=3, column=0, padx=20, pady=8, sticky="ew")
    owner.card_immune.grid_propagate(False)
    ctk.CTkLabel(owner.card_immune, text="🔒 核心安全锁定保护",
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=13),
                 text_color="#3b82f6").pack(pady=(10, 0))
    owner.lbl_immune_val = ctk.CTkLabel(owner.card_immune, text="0.00 B",
                                       font=ctk.CTkFont(family="Microsoft YaHei UI", size=22, weight="bold"),
                                       text_color="#60a5fa")
    owner.lbl_immune_val.pack()
    owner.lbl_immune_breakdown = ctk.CTkLabel(
        owner.card_immune,
        text="系统免疫: 0.00 B   手动上锁: 0.00 B",
        font=ctk.CTkFont(family="Consolas", size=10),
        text_color="#94a3b8")
    owner.lbl_immune_breakdown.pack(pady=(1, 2))
    # 保护容量透明化入口：点击列出免疫/上锁每一项的明细
    owner.btn_protection = ctk.CTkButton(
        owner.card_immune,
        text="👁 查看保护清单",
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
        height=22,
        fg_color="#1e3a8a", hover_color="#2563eb",
        command=owner.show_protection_list)
    owner.btn_protection.pack(pady=(0, 8), padx=14, fill="x")

    # Stat Card 3: Cleaned Size（本次会话累计，安全/深度两细分）
    owner.card_cleaned = ctk.CTkFrame(owner.sidebar_frame, fg_color="#1e293b", corner_radius=10, height=118)
    owner.card_cleaned.grid(row=4, column=0, padx=20, pady=8, sticky="ew")
    owner.card_cleaned.grid_propagate(False)
    ctk.CTkLabel(owner.card_cleaned, text="🟢 安全净化释放容量",
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=13),
                 text_color="#22c55e").pack(pady=(10, 0))
    owner.lbl_cleaned_val = ctk.CTkLabel(owner.card_cleaned, text="0.00 B",
                                        font=ctk.CTkFont(family="Microsoft YaHei UI", size=22, weight="bold"),
                                        text_color="#4ade80")
    owner.lbl_cleaned_val.pack()
    owner.lbl_cleaned_breakdown = ctk.CTkLabel(
        owner.card_cleaned,
        text="安全清理: 0.00 B   深度清理: 0.00 B",
        font=ctk.CTkFont(family="Consolas", size=10),
        text_color="#94a3b8")
    owner.lbl_cleaned_breakdown.pack(pady=(1, 8))

    # Spacer
    owner.sidebar_spacer = ctk.CTkLabel(owner.sidebar_frame, text="")
    owner.sidebar_spacer.grid(row=5, column=0, sticky="nsew")

    # HWID / 查重台 / 检查更新
    owner.lbl_hwid = ctk.CTkLabel(
        owner.sidebar_frame,
        text="ID: " + get_hwid(),
        font=ctk.CTkFont(family="Consolas", size=11),
        text_color="#475569"
    )
    owner.lbl_hwid.grid(row=6, column=0, padx=20, pady=(10, 6))

    owner.btn_deep_opt = ctk.CTkButton(
        owner.sidebar_frame,
        text="🧽 AppData 深度优化",
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
        fg_color="#7c3aed",
        hover_color="#8b5cf6",
        command=owner.open_deep_optimize
    )
    owner.btn_deep_opt.grid(row=7, column=0, padx=20, pady=4, sticky="ew")

    owner.btn_dedup = ctk.CTkButton(
        owner.sidebar_frame,
        text="🔍 重复文件查重台",
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
        fg_color="#0e7490",
        hover_color="#0891b2",
        command=owner.open_dedup
    )
    owner.btn_dedup.grid(row=8, column=0, padx=20, pady=4, sticky="ew")

    owner.btn_migrate = ctk.CTkButton(
        owner.sidebar_frame,
        text="🧠 AI 记忆无损迁移",
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
        fg_color="#065f46",
        hover_color="#059669",
        command=owner.open_memory_migrate
    )
    owner.btn_migrate.grid(row=9, column=0, padx=20, pady=4, sticky="ew")

    owner.btn_check_update = ctk.CTkButton(
        owner.sidebar_frame,
        text="🔄 检查更新",
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
        command=owner.manual_check_update
    )
    owner.btn_check_update.grid(row=10, column=0, padx=20, pady=4, sticky="ew")

    # ==========================================
    # MAIN PANEL
    # ==========================================
    owner.main_frame = ctk.CTkFrame(owner, fg_color="#020617", corner_radius=0)
    owner.main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
    owner.main_frame.grid_columnconfigure(0, weight=1)
    # col1 详情面板：310 面板本体 + 25 右边距 = 335
    owner.main_frame.grid_columnconfigure(1, weight=0, minsize=335)
    owner.main_frame.grid_rowconfigure(3, weight=1)  # 列表区域伸展

    # Header
    owner.header_frame = ctk.CTkFrame(owner.main_frame, fg_color="transparent")
    owner.header_frame.grid(row=0, column=0, padx=25, pady=(20, 10), sticky="ew")

    owner.main_title = ctk.CTkLabel(
        owner.header_frame,
        text="🛡️ 雷达物理安全盾 & 优化矩阵 v" + version,
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=22, weight="bold"),
        text_color="#f8fafc"
    )
    owner.main_title.pack(side="left")

    # 目标磁盘选择：卡片式（盘符 + 可用/总容量 + 占用率迷你条，整卡点击切换）
    owner.drive_bar = ctk.CTkFrame(owner.main_frame, fg_color="transparent")
    owner.drive_bar.grid(row=1, column=0, padx=25, pady=(0, 8), sticky="ew")

    ctk.CTkLabel(owner.drive_bar, text="📀 目标磁盘",
                 font=ctk.CTkFont(family="Microsoft YaHei UI", size=13),
                 text_color="#94a3b8").pack(side="left", padx=(0, 10))

    import shutil as _shutil
    owner.drive_cards = {}

    def _drive_pallet(pct):
        if pct >= 0.9:
            return "#ef4444"
        if pct >= 0.75:
            return "#f59e0b"
        return "#22c55e"

    def _drive_card_refresh():
        for lt, cw in getattr(owner, "drive_cards", {}).items():
            sel = owner.drive_vars[lt].get() == 1
            try:
                cw["card"].configure(
                    fg_color="#0e2a3d" if sel else "#0b1220",
                    border_color="#22d3ee" if sel else "#1e293b")
                cw["letter"].configure(text_color="#22d3ee" if sel else "#f8fafc")
            except Exception:
                pass

    def _toggle_drive(letter):
        v = owner.drive_vars[letter]
        v.set(0 if v.get() == 1 else 1)
        _drive_card_refresh()
        try:
            owner.on_drive_changed()
        except Exception:
            pass

    for letter in owner.detected_drives:
        try:
            usage = _shutil.disk_usage(f"{letter}:\\")
            free_g = usage.free / (1024 ** 3)
            total_g = usage.total / (1024 ** 3)
            pct = (usage.total - usage.free) / usage.total if usage.total else 0
            cap_txt = "{:.0f}G / {:.0f}G".format(free_g, total_g)
        except Exception:
            pct, cap_txt = 0.0, f"{letter}盘"
        role = "系统盘" if letter == "C" else "本地磁盘"

        card = ctk.CTkFrame(owner.drive_bar, fg_color="#0b1220", corner_radius=10,
                            border_width=1, border_color="#1e293b",
                            width=100, height=64)
        card.pack_propagate(False)
        card.pack(side="left", padx=4)
        top = ctk.CTkFrame(card, fg_color="transparent", height=22)
        top.pack(fill="x", padx=8, pady=(6, 0))
        lbl_letter = ctk.CTkLabel(top, text=letter, width=20,
                                  font=ctk.CTkFont(family="Consolas", size=16, weight="bold"),
                                  text_color="#f8fafc")
        lbl_letter.pack(side="left")
        ctk.CTkLabel(top, text=role,
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=9),
                     text_color="#64748b").pack(side="right")
        ctk.CTkLabel(card, text=cap_txt,
                     font=ctk.CTkFont(family="Consolas", size=10),
                     text_color="#94a3b8").pack(anchor="w", padx=8, pady=(0, 2))
        mini = ctk.CTkProgressBar(card, height=6, fg_color="#1e293b",
                                  progress_color=_drive_pallet(pct))
        mini.pack(fill="x", padx=8, pady=(0, 8))
        try:
            mini.set(pct)
        except Exception:
            pass

        widgets = [card, top, lbl_letter] + list(top.winfo_children()) + list(card.winfo_children())
        for w in widgets:
            try:
                w.bind("<Button-1>", lambda e, lt=letter: _toggle_drive(lt))
            except Exception:
                pass
        owner.drive_cards[letter] = {
            "card": card, "top": top, "letter": lbl_letter,
            "cap": cap_txt, "pct": pct,
        }

    _drive_card_refresh()

    # 列表控制条：全选 / 全不选 / 排序 —— 放在列表下方（列表底部工具条）
    owner.list_ctrl_bar = ctk.CTkFrame(owner.main_frame, fg_color="transparent")
    owner.list_ctrl_bar.grid(row=4, column=0, padx=25, pady=(0, 2), sticky="ew")

    owner.btn_select_all_apps = ctk.CTkButton(
        owner.list_ctrl_bar, text="☑️ 全选所有项目", width=120,
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
        command=owner.select_all_apps
    )
    owner.btn_select_all_apps.pack(side="left")

    owner.btn_deselect_all_apps = ctk.CTkButton(
        owner.list_ctrl_bar, text="☒️ 全不选", width=100,
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
        command=owner.deselect_all_apps
    )
    owner.btn_deselect_all_apps.pack(side="left", padx=8)

    owner.sort_mode_var = ctk.StringVar(value="category")

    # 「显示所有项」开关：默认隐藏 0 大小/无内容项，只显示扫出来的垃圾项
    owner.show_all_items = False
    owner.showall_var = ctk.BooleanVar(value=False)

    def on_toggle_showall():
        owner.show_all_items = bool(owner.showall_var.get())
        scanning = (getattr(owner, "safe_state", "") in ("scanning", "cleaning")
                    or getattr(owner, "risk_state", "") in ("scanning", "cleaning"))
        if not scanning:
            owner.render_scroll_list()

    owner.chk_showall = ctk.CTkCheckBox(
        owner.list_ctrl_bar, text="显示所有项", variable=owner.showall_var,
        command=on_toggle_showall, width=110,
        checkbox_width=16, checkbox_height=16,
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
    )
    owner.chk_showall.pack(side="right", padx=8)

    def on_sort_changed(val):
        if val == "按类别分组":
            owner.sort_mode_var.set("category")
        else:
            owner.sort_mode_var.set("size")
        owner.render_scroll_list()

    owner.sort_menu = ctk.CTkOptionMenu(
        owner.list_ctrl_bar,
        values=["按类别分组", "按容量 ⬇️"],
        command=on_sort_changed,
        width=120,
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
        fg_color="#334155",
    )
    owner.sort_menu.pack(side="right")

    # 可清理项目列表
    owner.scroll_frame = ctk.CTkScrollableFrame(
        owner.main_frame,
        label_text="清理项目细分管理与可选状态",
        label_font=ctk.CTkFont(family="Microsoft YaHei UI", size=14, weight="bold"),
        fg_color="#090d16",
        scrollbar_button_color="#1e293b",
        scrollbar_button_hover_color="#334155",
    )
    _style_scrollbar(owner.scroll_frame, slot="#090d16")
    owner.scroll_frame.grid_columnconfigure(1, weight=1)

    owner.app_rows = {}
    owner.app_checkboxes = {}
    owner.app_checkbox_vars = {}
    owner._row_queue = []
    owner._row_index = 0
    owner._render_job = None
    owner._rows_started = False
    try:
        owner.scroll_frame.grid(row=3, column=0, padx=25, pady=5, sticky="nsew")
    except Exception:
        pass
    owner._show_placeholder()

    # ==========================================
    # RIGHT DETAIL PANEL（右侧详情面板）
    # 点击列表行 → 显示该项细节；扫描/清理完成报告与保护清单也在此呈现。
    # ==========================================
    owner.detail_panel = ctk.CTkFrame(owner.main_frame, fg_color="#0b1220",
                                      corner_radius=10, border_width=1,
                                      border_color="#1e293b")
    owner.detail_panel.grid(row=1, column=1, rowspan=5, sticky="nsew",
                            padx=(0, 25), pady=(0, 5))
    owner.detail_panel.grid_propagate(False)
    owner.detail_panel.grid_columnconfigure(0, weight=1)
    owner.detail_panel.grid_rowconfigure(1, weight=1)

    owner.detail_title = ctk.CTkLabel(
        owner.detail_panel, text="📋 详情面板",
        font=F(UI_FAMILY, 15, "bold"), text_color="#7dd3fc")
    owner.detail_title.grid(row=0, column=0, padx=14, pady=(12, 6), sticky="w")

    owner.detail_body = ctk.CTkScrollableFrame(
        owner.detail_panel, fg_color="transparent",
        scrollbar_button_color="#1e293b",
        scrollbar_button_hover_color="#334155")
    _style_scrollbar(owner.detail_body, slot="#0b1220")
    owner.detail_body.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 10))
    ctk.CTkLabel(
        owner.detail_body,
        text="点击左侧任意项目\n在此查看该项细节\n\n扫描/清理完成后，\n本面板显示结构化报告；\n「查看保护清单」也在这里展示。",
        font=F(UI_FAMILY, 12), text_color="#475569", justify="center",
    ).pack(pady=60, padx=10)

    # 视口尺寸变化（窗口缩放/面板重排）时重新判定滚动条显隐
    try:
        owner.detail_body._parent_canvas.bind(
            "<Configure>", lambda e: refresh_detail_scroll(owner), add="+")
    except Exception:
        pass
    refresh_detail_scroll(owner)

    # Controls Frame（主操作按钮 & 进度）——grid 固定排版：
    # col0 进度条(固定) | col1 状态/日志滚动文本(弹性·无底色) | col2 深度按钮 | col3 安全按钮
    owner.control_frame = ctk.CTkFrame(owner.main_frame, fg_color="transparent")
    owner.control_frame.grid(row=5, column=0, padx=25, pady=(6, 8), sticky="ew")
    # 显式定高（按钮行 40 + 状态行 32）：CTkFrame 高度传播滞后会让外部 grid
    # 仍按单行 40px 分配，导致第二行状态文本溢出并与页脚重叠。
    owner.control_frame.grid_propagate(False)
    owner.control_frame.configure(height=76)
    owner.control_frame.grid_columnconfigure(0, weight=0)
    owner.control_frame.grid_columnconfigure(1, weight=1)
    owner.control_frame.grid_columnconfigure(2, weight=0)
    owner.control_frame.grid_columnconfigure(3, weight=0)

    owner.progress_bar = ctk.CTkProgressBar(owner.control_frame, width=210)
    owner.progress_bar.grid(row=0, column=0, padx=(0, 16), sticky="w")
    owner.progress_bar.set(0)

    # 滚动日志/状态行：替代原底部日志台，无底色，随日志最新一行滚动。
    # 独占第二行（跨 col0-1）：主列 685px 内进度条+双按钮已占 ~585px，
    # 若同挤一行文本只剩 ~35px 会被裁成 2-3 个字（v3.9.13 反馈）。
    owner.lbl_progress_info = ctk.CTkLabel(
        owner.control_frame, text="就绪 — 点击「开始安全扫描」或「开始深度扫描」",
        font=F(UI_FAMILY, 12, "bold"), text_color="#fbbf24",
        fg_color="transparent", anchor="w", height=26)
    owner.lbl_progress_info.grid(row=1, column=0, columnspan=4,
                                 padx=(0, 4), pady=(6, 0), sticky="ew")

    # 双按钮状态机：安全线（扫描→清理）与深线（扫描→清理）各自独立
    owner.btn_action = ctk.CTkButton(
        owner.control_frame,
        text="🛡️ 开始安全扫描",
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=14, weight="bold"),
        width=170, height=40,
        command=owner.on_action_click
    )
    owner.btn_action.grid(row=0, column=3, padx=(8, 0))

    owner.btn_deep = ctk.CTkButton(
        owner.control_frame,
        text="🔥 开始深度扫描",
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=14, weight="bold"),
        width=170, height=40,
        fg_color="#7f1d1d", hover_color="#991b1b",
        command=owner.on_deep_click
    )
    owner.btn_deep.grid(row=0, column=2, padx=(0, 10))

    # 底部日志台已取消：日志改为控制条滚动文本显示（append_log 直刷 lbl_progress_info）
    owner.append_log("系统安全防护正常就绪。等待执行雷达深度扫描...")
    owner.flush_logs()

    # 页脚
    owner.footer_frame = ctk.CTkFrame(owner.main_frame, fg_color="transparent")
    owner.footer_frame.grid(row=6, column=0, padx=25, pady=(4, 12), sticky="ew")

    owner.footer_version = ctk.CTkLabel(
        owner.footer_frame,
        text=f"v{version}",
        font=ctk.CTkFont(family="Consolas", size=11),
        text_color="#475569"
    )
    owner.footer_version.pack(side="left")

    owner.footer_email = ctk.CTkLabel(
        owner.footer_frame,
        text="📧 vip@ppsai.chat",
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
        text_color="#94a3b8"
    )
    owner.footer_email.pack(side="right")
    owner.make_clickable(owner.footer_email, lambda: owner.open_url("mailto:vip@ppsai.chat"))

    owner.footer_website = ctk.CTkLabel(
        owner.footer_frame,
        text="🌐 官网",
        font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
        text_color="#38bdf8"
    )
    owner.footer_website.pack(side="right", padx=(0, 14))
    owner.make_clickable(owner.footer_website, lambda: owner.open_url("https://ppsai.chat/safecleaner/"))

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
    style.configure("Treeview",
                    background="#0d1526", fieldbackground="#0b1220",
                    foreground="#cbd5e1", rowheight=rowheight,
                    borderwidth=0, relief="flat", indent=16,
                    font=("Microsoft YaHei UI", 10))
    style.configure("Treeview.Heading",
                    background="#141f38", foreground="#00f0ff",
                    borderwidth=0, relief="flat", padding=(6, 7),
                    font=("Microsoft YaHei UI", 10, "bold"))
    style.map("Treeview.Heading", background=[("active", "#1b2a4a")])
    style.map("Treeview",
              background=[("selected", "#17335c")],
              foreground=[("selected", "#ffffff")])
    style.configure("Vertical.TScrollbar",
                    background="#1e293b", troughcolor="#0b1220",
                    bordercolor="#0b1220", arrowcolor="#64748b")
    style.map("Vertical.TScrollbar", background=[("active", "#334155")])

# ======================================================================
# 全局设计令牌 —— 所有窗口（含弹窗）统一取色/取字，禁止各自定义
# ======================================================================
BG      = "#0b1220"   # 窗口底色（深蓝黑）
BG_DEEP = "#020617"   # 主面板更深层底色
PANEL   = "#111827"   # 面板
CARD    = "#1e293b"   # 卡片
ACCENT  = "#00f0ff"   # 主强调色（青）
ACCENT2 = "#7c3aed"   # 次强调色（紫）
OK      = "#22c55e"
WARN    = "#f59e0b"
ERR     = "#f87171"
TEXT    = "#e2e8f0"
DIM     = "#94a3b8"


def app_icon_path():
    """统一软件图标（exe 资源 / 窗口标题栏 / 任务栏同源 logo.ico）。"""
    import sys as _sys
    base = getattr(_sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(base, "logo.ico")
    return p if os.path.exists(p) else None


def setup_popup(win, title):
    """弹窗统一外观：标题格式、底色、软件图标。

    iconbitmap 双设置：Windows 上 Toplevel 首帧图标常被吞，
    延迟 250ms 再设一次保证任务栏/标题栏稳定显示。
    """
    t = title if "SafeCleaner" in title else f"SafeCleaner Pro · {title}"
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
