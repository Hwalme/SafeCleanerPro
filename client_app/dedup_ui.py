# -*- coding: utf-8 -*-
"""
dedup_ui.py — SafeCleanerPro 查重台窗口
========================================
DedupWindow(parent) 弹窗:
  左列: 盘符快选(系统盘标注) / 位置列表(可加文件夹可移除) /
        选项(增量跳过·扫描系统盘) / 开始·强制重扫 / 进度·日志
  右侧: 统计卡 + 结果表(组 状态 大小 创建 修改 类别 文件名 文件夹 哈希)
        打开 / 定位 / 右键菜单 / 删除选中冗余(引擎校验同组副本)
"""
import os
import time
import queue
import threading
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from dedup_core import DedupEngine, logical_drives, system_drive, category_of, SYSTEM_DIR_EXCLUDE

from ui_theme import (ACCENT, CARD as PANEL, DIM, BG, UI_FAMILY, F,
                      setup_popup)

# 结果筛选条：类型 / 大小 / 日期（只过滤视图显示，不动数据与删除校验）
CAT_FILTERS = ["全部类型", "图片", "视频", "音频", "文档",
               "压缩包", "安装包", "数据", "代码", "其他"]
SIZE_FILTERS = {"全部大小": 0, "≥ 1 MB": 1048576, "≥ 10 MB": 10485760,
                "≥ 100 MB": 104857600, "≥ 1 GB": 1073741824}
DATE_FILTERS = {"全部日期": None, "24 小时内": 86400, "7 天内": 7 * 86400,
                "30 天内": 30 * 86400, "90 天内": 90 * 86400,
                "一年内": 365 * 86400, "一年前（旧文件）": -365 * 86400}


def fmt_b(n):
    for u in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024:
            return f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} PB"


def fmt_t(t):
    import time as _t
    return _t.strftime("%Y-%m-%d %H:%M", _t.localtime(t))


class DedupWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        setup_popup(self, "重复文件查重台")
        self.geometry("1380x860")
        self.minsize(1120, 740)
        self.resizable(True, True)   # 布局为固定两列，锁定尺寸防抖动
        self.after(50, self.lift)
        self.attributes("-topmost", True)
        from ui_theme import popup_front, apply_window_chrome
        apply_window_chrome(self)
        self.after(260, lambda: apply_window_chrome(self))
        self.after(200, lambda: self.attributes("-topmost", False))

        self.master_app = master
        self.engine = DedupEngine(os.path.join(os.path.dirname(__file__), "dedup_data"))
        self.scopes = []
        self.result = None      # 当前展示的 groups
        self.scanning = False
        self.cancel = {"stop": False}
        self.row_paths = {}     # iid -> path

        self._build()
        self._load_last_result()

    # ---------------- UI ----------------
    def _build(self):
        from ui_theme import style_dark_treeview
        style_dark_treeview(rowheight=34)
        self.grid_columnconfigure(0, weight=0, minsize=300)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)
        from brand_ui import popup_header
        banner = ctk.CTkFrame(self, fg_color="transparent")
        banner.grid(row=0, column=0, columnspan=2, sticky="ew")
        popup_header(banner, "重复文件", "按内容比对跨文件夹副本。删除前会再次校验，并保留每组至少一份。")

        # ===== 左列 =====
        # v3.9.13 防抖：左列锁宽 300 + 关闭几何传播，长状态文本不再把列撑宽
        # （否则扫描中状态文字长度变化 → 左列 325↔425 摆动，右列跟着挤压）
        left = ctk.CTkScrollableFrame(self, fg_color=PANEL, corner_radius=12, width=280,
                                       scrollbar_button_color="#2A3541", scrollbar_button_hover_color="#8795A5")
        left.grid(row=1, column=0, sticky="nsew", padx=(24, 12), pady=(0, 24))

        ctk.CTkLabel(left, text="选择比对位置",
                     font=F(UI_FAMILY, 14, "bold"),
                     text_color=ACCENT).pack(anchor="w", padx=14, pady=(12, 0))
        ctk.CTkLabel(left, text="所有位置互相比对（不限同一目录/同一盘），同一内容仅保留一份",
                     font=F(UI_FAMILY, 10),
                     text_color=DIM, wraplength=272, justify="left", anchor="nw",
                     height=32).pack(anchor="w", padx=14, pady=(0, 4))

        # 盘符快选
        self.drive_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.drive_frame.pack(fill="x", padx=14)
        sysd = system_drive()
        for i, letter in enumerate(logical_drives()):
            txt = f"{letter}盘" + ("（系统盘·默认排除）" if letter == sysd else "")
            ctk.CTkButton(
                self.drive_frame, text=txt, height=32,
                fg_color="#2A3541", hover_color="#2A3541",
                font=F(UI_FAMILY, 12),
                command=lambda l=letter, s=txt: self.add_scope(f"{l}:\\", s),
            ).grid(row=i // 2, column=i % 2, padx=3, pady=3, sticky="ew")
        self.drive_frame.grid_columnconfigure(0, weight=1)
        self.drive_frame.grid_columnconfigure(1, weight=1)

        # 位置列表
        ctk.CTkLabel(left, text="已添加位置（双击移除）", font=F(UI_FAMILY, 12),
                     text_color=DIM).pack(anchor="w", padx=14, pady=(8, 2))
        self.scope_box = ctk.CTkTextbox(left, height=90, font=F(UI_FAMILY, 12))
        self.scope_box.pack(fill="x", padx=14)
        self.scope_box.insert("1.0", "（尚未添加位置，点上方盘符或下方按钮）")
        self.scope_box.configure(state="disabled")
        self.scope_box._textbox.bind("<Double-Button-1>", self.remove_scope_at)

        ctk.CTkButton(left, text="＋ 添加文件夹…", height=34,
                      command=self.add_folder).pack(fill="x", padx=14, pady=(6, 0))

        # 选项
        self.var_increment = ctk.BooleanVar(value=True)
        self.var_sysdrive = ctk.BooleanVar(value=False)
        self.var_excl_sysdir = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(left, text="增量模式（跳过没变过的文件）", variable=self.var_increment,
                        font=F(UI_FAMILY, 12)).pack(anchor="w", padx=14, pady=(10, 0))
        ctk.CTkCheckBox(left, text="扫描系统盘（默认排除C盘）", variable=self.var_sysdrive,
                        font=F(UI_FAMILY, 12)).pack(anchor="w", padx=14, pady=(4, 0))
        ctk.CTkCheckBox(left, text="排除系统目录/系统文件", variable=self.var_excl_sysdir,
                        font=F(UI_FAMILY, 12)).pack(anchor="w", padx=14, pady=(4, 0))

        # 开始
        self.btn_start = ctk.CTkButton(left, text=" 开始查重", height=38,
                                       font=F(UI_FAMILY, 14, "bold"),
                                       fg_color=ACCENT, hover_color="#B1ECF7", text_color="#101419",
                                       command=self.start_scan)
        self.btn_start.pack(fill="x", padx=14, pady=(12, 4))
        self.btn_force = ctk.CTkButton(left, text=" 强制重扫（忽略缓存）", height=34,
                                       fg_color="#1D252E", hover_color="#2A3541",
                                       command=lambda: self.start_scan(force=True))
        self.btn_force.pack(fill="x", padx=14, pady=(0, 4))
        self.btn_stop = ctk.CTkButton(left, text="停止扫描", height=34, fg_color="#59353A",
                                      hover_color="#74434A", command=self.stop_scan)
        self.btn_stop.pack(fill="x", padx=14, pady=(0, 6))

        self.progress = ctk.CTkProgressBar(left)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=14)
        # wraplength=272 折行 + 固定两行高：状态文本可任意长而不撑宽/抖高左列
        self.lbl_status = ctk.CTkLabel(left, text="就绪", font=F(UI_FAMILY, 12),
                                       text_color=DIM, anchor="nw", justify="left",
                                       wraplength=272, height=34)
        self.lbl_status.pack(fill="x", padx=14, pady=(2, 4))

        # 历史
        ctk.CTkLabel(left, text="扫描历史", font=F(UI_FAMILY, 12),
                     text_color=DIM).pack(anchor="w", padx=14, pady=(6, 2))
        self.hist_combo = ctk.CTkComboBox(left, values=self._history_labels(),
                                          command=self.load_history)
        self.hist_combo.pack(fill="x", padx=14)

        self.log_box = ctk.CTkTextbox(left, height=140, font=F(UI_FAMILY, 11))
        self.log_box.pack(fill="both", expand=True, padx=14, pady=(8, 12))
        self.log_box.insert("end", "PPSAI Cleaner 查重引擎就绪。\n")
        self.log_box.configure(state="disabled")

        # ===== 右侧 =====
        right = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        right.grid(row=1, column=1, sticky="nsew", padx=(0, 24), pady=(0, 24))
        right.grid_rowconfigure(3, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # 统计卡
        cards = ctk.CTkFrame(right, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        # wraplength=860 折行 + 固定两行高：统计文本不撑宽右列
        self.lbl_stat = ctk.CTkLabel(cards, text="尚未扫描 · 载入上次结果或开始新扫描",
                                     font=F(UI_FAMILY, 13), text_color=DIM,
                                     anchor="nw", justify="left", wraplength=860, height=36)
        self.lbl_stat.pack(anchor="w", fill="x")

        # 操作条
        bar = ctk.CTkFrame(right, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkButton(bar, text=" 打开", width=76, height=32, command=self.open_sel).pack(side="left", padx=(0, 6))
        ctk.CTkButton(bar, text=" 定位", width=76, height=32, command=self.reveal_sel).pack(side="left", padx=6)
        # 一键选冗余：无需再一个个手动点选
        ctk.CTkButton(bar, text=" 一键选冗余", width=110, height=32, fg_color="#294652",
                      hover_color="#395C68", command=self.select_redundant).pack(side="left", padx=6)
        ctk.CTkButton(bar, text=" 取消选择", width=90, height=32, fg_color="#1D252E",
                      hover_color="#2A3541", command=self.deselect_all).pack(side="left", padx=6)
        self.btn_delete = ctk.CTkButton(bar, text=" 删除选中冗余", width=140, height=32,
                                        fg_color="#633A40", hover_color="#7A454D",
                                        command=self.delete_selected)
        self.btn_delete.pack(side="left", padx=6)
        ctk.CTkLabel(bar, text="红行=冗余副本 · 每组保留 1 份",
                     font=F(UI_FAMILY, 11), text_color=DIM).pack(side="right")

        # 筛选条：类型 / 大小 / 日期（只过滤视图，扫描中和扫描后均可随时切换）
        self.filter = {"cat": "全部类型", "size": 0, "date": None}
        fbar = ctk.CTkFrame(right, fg_color="transparent")
        fbar.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkLabel(fbar, text="筛选:", font=F(UI_FAMILY, 12),
                     text_color=DIM).pack(side="left", padx=(0, 4))
        self.om_cat = ctk.CTkOptionMenu(fbar, values=CAT_FILTERS, width=86, height=32,
                                        font=F(UI_FAMILY, 12),
                                        command=lambda v: self._set_filter("cat", v))
        self.om_cat.pack(side="left", padx=3)
        self.om_size = ctk.CTkOptionMenu(fbar, values=list(SIZE_FILTERS.keys()), width=96, height=32,
                                         font=F(UI_FAMILY, 12),
                                         command=lambda v: self._set_filter("size", v))
        self.om_size.pack(side="left", padx=3)
        self.om_date = ctk.CTkOptionMenu(fbar, values=list(DATE_FILTERS.keys()), width=140, height=32,
                                         font=F(UI_FAMILY, 12),
                                         command=lambda v: self._set_filter("date", v))
        self.om_date.pack(side="left", padx=3)
        ctk.CTkButton(fbar, text=" 清除筛选", width=78, height=32, fg_color="#1D252E",
                      hover_color="#2A3541", command=self.clear_filter).pack(side="left", padx=6)
        # 默认隐藏 0 字节项（空文件副本无清理价值）；勾选后显示全部
        self.show_all = False
        self.chk_showall = ctk.CTkCheckBox(fbar, text="显示所有项", width=96, height=32,
                                           checkbox_width=16, checkbox_height=16,
                                           font=F(UI_FAMILY, 12),
                                           command=self._toggle_showall)
        self.chk_showall.pack(side="left", padx=6)
        self.lbl_fcount = ctk.CTkLabel(fbar, text="显示 0/0 行",
                                       font=F(UI_FAMILY, 11),
                                       text_color=DIM)
        self.lbl_fcount.pack(side="right")

        # 结果表
        wrap = ctk.CTkFrame(right, fg_color=PANEL, corner_radius=10)
        wrap.grid(row=3, column=0, sticky="nsew")
        cols = ("grp", "state", "size", "ctime", "mtime", "cat", "name", "folder", "hash")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="extended")
        widths = {"grp": 60, "state": 52, "size": 82, "ctime": 112, "mtime": 112,
                  "cat": 54, "name": 260, "folder": 300, "hash": 110}
        anchors = {"size": "e", "grp": "center", "state": "center", "cat": "center"}
        for c in cols:
            self.tree.heading(c, text={"grp": "组", "state": "状态", "size": "大小",
                                       "ctime": "创建时间", "mtime": "修改时间", "cat": "类别",
                                       "name": "文件名", "folder": "所在文件夹",
                                       "hash": "哈希"}[c],
                              command=lambda cc=c: self.sort_by(cc))
            self.tree.column(c, width=widths[c], anchor=anchors.get(c, "w"), stretch=(c in ("name", "folder")))
        self.tree.tag_configure("redundant", background="#32242A", foreground="#ECA0A6")
        self.tree.tag_configure("keep", background="#20332C", foreground="#91D5B6")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        # 横向滚动兜底：九列总宽超出可视区时可横向滚动，避免内容被裁
        hsb = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y", pady=6, padx=(0, 6))
        hsb.pack(side="bottom", fill="x", padx=(6, 12), pady=(0, 6))
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._refresh_actions())
        self.tree.bind("<Double-1>", lambda e: self.open_sel())
        self.tree.bind("<Button-3>", self._popup_menu)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label=" 全选冗余副本", command=self.select_redundant)
        self.menu.add_command(label=" 取消选择", command=self.deselect_all)
        self.menu.add_separator()
        self.menu.add_command(label=" 打开", command=self.open_sel)
        self.menu.add_command(label=" 定位", command=self.reveal_sel)
        self.menu.add_command(label=" 复制路径", command=self.copy_path)

        self._refresh_actions()

    def _refresh_actions(self):
        active = self.scanning or getattr(self, "deleting", False)
        self.btn_start.configure(state="normal" if self.scopes and not active else "disabled")
        self.btn_force.configure(state="normal" if self.scopes and not active else "disabled")
        self.btn_stop.configure(state="normal" if self.scanning else "disabled")
        self.btn_delete.configure(state="normal" if self.tree.selection() and not active else "disabled")

    def remove_scope_at(self, event):
        if self.scanning or getattr(self, "deleting", False): return "break"
        line = int(self.scope_box._textbox.index(f"@{event.x},{event.y}").split(".")[0]) - 1
        if 0 <= line < len(self.scopes):
            self.scopes.pop(line)
            self._render_scopes()
        return "break"

    # ---------------- 范围管理 ----------------
    def add_scope(self, path, label=""):
        norm = os.path.normpath(path)
        if norm not in self.scopes:
            self.scopes.append(norm)
        self._render_scopes()

    def add_folder(self):
        from tkinter import filedialog
        d = filedialog.askdirectory(parent=self, title="选择要查重的文件夹")
        if d:
            self.add_scope(d)

    def _render_scopes(self):
        self.scope_box.configure(state="normal")
        self.scope_box.delete("1.0", "end")
        for i, s in enumerate(self.scopes, 1):
            mark = "" if s.upper().startswith(system_drive()) else ""
            self.scope_box.insert("end", f"{i}. {s} {mark}\n")
        if not self.scopes:
            self.scope_box.insert("1.0", "（尚未添加位置）")
        self.scope_box.configure(state="disabled")
        self._refresh_actions()

    # ---------------- 扫描 ----------------
    def start_scan(self, force=False):
        from brand_ui import workspace_available
        if not workspace_available(self):
            return
        if self.scanning or not self.scopes:
            if not self.scopes:
                self.log(" 先添加范围（点盘符或添加文件夹）")
            return
        if not self.var_excl_sysdir.get():
            SYSTEM_DIR_EXCLUDE.clear()   # 用户显式关闭系统目录排除
        self.scanning = True
        self._refresh_actions()
        self.cancel["stop"] = False
        self.btn_start.configure(state="disabled")
        # 枚举阶段总量未知 → 进度条用流动动画；指纹阶段再切精确百分比
        self._det_progress = False
        self._last_pct = 0
        try:
            self.progress.stop()
        except Exception:
            pass
        self.progress.configure(mode="indeterminate", progress_color="#395C68")
        self.progress.start()
        self.lbl_status.configure(text=" 阶段 1/3 枚举文件中…", text_color=DIM)
        base_title = "PPSAI Cleaner · 重复文件"
        if self.title() != base_title:
            self.title(base_title)
        # 实时结果容器: 组在扫描中即时上屏，可随时操作
        self.result = {"stats": {"files": 0, "groups": 0, "redundant": 0,
                                 "reclaim_bytes": 0, "duration": 0, "mode": "扫描中"},
                       "groups": [], "scan_id": None}
        self.tree.delete(*self.tree.get_children())
        self.row_paths.clear()
        self.lbl_stat.configure(text=(
            "扫描中… 三阶段：①枚举文件 → ②指纹比对 → ③确认重复组；"
            "组一确认就出现在下方列表，可随时打开/定位/删除"))
        self.log(f"—— 开始扫描（{'强制重扫' if force else '增量'}）——")
        scopes = list(self.scopes)
        incremental = self.var_increment.get() and not force
        excl = not self.var_sysdrive.get()
        t = threading.Thread(target=self._scan_thread,
                             args=(scopes, incremental, excl, force), daemon=True)
        t.start()

    def stop_scan(self):
        self.cancel["stop"] = True
        self.log("停止扫描指令已发…")

    def _scan_thread(self, scopes, incremental, excl, force):
        def log(m):
            self.after(0, self.log, m)

        def prog(v):
            self.after(0, self._ui_progress, v)

        def stat(m):
            self.after(0, lambda: self._set_status(m))

        try:
            r = self.engine.run(scopes, incremental=incremental,
                                exclude_system=excl, progress_cb=prog,
                                log_cb=log, cancel=self.cancel,
                                on_group=lambda g: self.after(0, self._add_group_live, g),
                                status_cb=stat)
        except Exception as e:
            self.after(0, self.log, f" 引擎异常: {e}")
            self.after(0, self._scan_done)
            return
        if r.get("scan_id"):
            # 结果行已随组流式上屏 → 只归档统计，绝不清表重建（避免列表闪没）
            self.after(0, lambda: self._finalize_result(r))
        else:
            self.after(0, lambda: self._stopped_state())
        self.after(0, self._scan_done)

    def _ui_progress(self, v):
        """引擎进度 → 进度条。枚举阶段（v≤0.08）保持流动动画；
        指纹阶段首次到达时切为精确百分比模式。"""
        self._last_pct = max(self._last_pct, v)
        if v > 0.08 and not self._det_progress:
            self._det_progress = True
            try:
                self.progress.stop()
                self.progress.configure(mode="determinate", progress_color="#395C68")
            except Exception:
                pass
        if self._det_progress:
            self.progress.set(v)

    def _set_status(self, m):
        """引擎阶段状态实时打到状态行；扫描中自动带百分比前缀。"""
        try:
            text = f"{int(self._last_pct * 100):>3d}%  {m}" if self.scanning else m
            self.lbl_status.configure(text=text)
        except Exception:
            pass

    def _finalize_result(self, r):
        """扫描完成：醒目终态（绿色状态行/满进度条/提示音/标题标记）+ 统计归档。"""
        if self.result is None:
            self.result = r
        else:
            self.result["stats"] = r["stats"]
            self.result["scan_id"] = r.get("scan_id")
        s = r["stats"]
        self.lbl_stat.configure(text=(
            f" 扫描完成 · {s['files']} 文件 · {s['groups']} 组重复 · 冗余 {s['redundant']} · "
            f"可释放 {fmt_b(s['reclaim_bytes'])} · {s['duration']}s（{s['mode']}）"))
        self._finish_visuals(
            ok=True,
            msg=(f" 扫描完成：共 {s['groups']} 组重复 · 冗余 {s['redundant']} 个 · "
                 f"可释放 {fmt_b(s['reclaim_bytes'])} —— 点【 一键选冗余】清理"))

    def _stopped_state(self):
        """用户主动停止：红色终态，已确认组保留。"""
        self._finish_visuals(
            ok=False,
            msg=f"已停止（进度 {int(self._last_pct * 100)}%）—— 已确认的重复组保留在右侧列表")

    def _finish_visuals(self, ok, msg, title_mark=None):
        try:
            self.progress.stop()
            self.progress.configure(mode="determinate",
                                    progress_color="#91D5B6" if ok else "#ECA0A6")
            self.progress.set(1.0 if ok else self._last_pct)
        except Exception:
            pass
        try:
            self.lbl_status.configure(text=msg,
                                      text_color="#91D5B6" if ok else "#ECA0A6")
        except Exception:
            pass
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
        # 标题短暂标记，任务栏切走也能注意到完成
        if title_mark is None:
            title_mark = " 扫描完成" if ok else "已停止"
        base_title = "PPSAI Cleaner · 重复文件"
        try:
            if hasattr(self, "_title_job") and self._title_job:
                self.after_cancel(self._title_job)
            self.title(base_title + " —— " + title_mark)
            self._title_job = self.after(6000, lambda: self.title(base_title))
        except Exception:
            pass

    def _add_group_live(self, g):
        """扫描中每确认一组重复立即上屏（按当前筛选显示），可随时操作"""
        if self.result is None:
            return
        self.result["groups"].append(g)
        gi = len(self.result["groups"])
        for f in g["files"]:
            self._insert_row(f, gi)
        s = self.result["stats"]
        s["groups"] += 1
        s["redundant"] += g["count"] - 1
        s["reclaim_bytes"] += g["size"] * (g["count"] - 1)
        self.lbl_stat.configure(text=(
            f"扫描中… 已确认 {s['groups']} 组 / 冗余 {s['redundant']} / "
            f"可释放 {fmt_b(s['reclaim_bytes'])}（列表实时更新，可随时操作）"))

    def _scan_done(self):
        self.scanning = False
        self._refresh_actions()
        self.btn_start.configure(state="normal")
        self.hist_combo.configure(values=self._history_labels())
        try:
            self.progress.stop()          # 兜底停掉 indeterminate 动画
            if not self._det_progress:    # 引擎未进入指纹阶段就结束（无文件/取消）
                self.progress.configure(mode="determinate", progress_color="#395C68")
                self.progress.set(1.0 if self.result and self.result.get("scan_id")
                                  else 0)
        except Exception:
            pass

    # ---------------- 结果 ----------------
    def _show_result(self, r):
        self.result = r
        self.tree.delete(*self.tree.get_children())
        self.row_paths.clear()
        s = r["stats"]
        self.lbl_stat.configure(text=(
            f"扫描 {s['files']} 文件 · {s['groups']} 组重复 · 冗余 {s['redundant']} · "
            f"可释放 {fmt_b(s['reclaim_bytes'])} · {s['duration']}s（{s['mode']}）"))
        n = 0
        for gi, g in enumerate(r["groups"], 1):
            for f in g["files"]:
                self._insert_row(f, gi)
                n += 1
                if n % 800 == 0:
                    self.update_idletasks()
        self._apply_filter()

    def _load_last_result(self):
        import glob
        files = sorted(glob.glob(os.path.join(self.engine.dir, "results_*.json")))
        if files:
            try:
                import json
                r = json.loads(open(files[-1], encoding="utf-8").read())
                r["scan_id"] = files[-1].split("results_")[-1].replace(".json", "")
                self._show_result(r)
                self.log(f"已载入上次结果 {r['scan_id']}")
            except Exception:
                pass

    def load_history(self, choice):
        # choice: "20260913_0145xx | 增量 | 3组..." 取 id 部分
        sid = choice.split(" ")[0]
        p = os.path.join(self.engine.dir, f"results_{sid}.json")
        if os.path.exists(p):
            import json
            r = json.loads(open(p, encoding="utf-8").read())
            r["scan_id"] = sid
            self._show_result(r)

    def _history_labels(self):
        labels = []
        for h in reversed(self.engine.history[-30:]):
            labels.append(f"{h['id']} | {h.get('mode','')} | {h['groups']}组 | "
                          f"{fmt_b(h['reclaim_bytes'])}")
        return labels or ["（无记录）"]

    # ---------------- 结果筛选（类型/大小/日期，仅过滤视图显示） ----------------
    def _set_filter(self, key, value):
        if key == "cat":
            self.filter["cat"] = value
        elif key == "size":
            self.filter["size"] = SIZE_FILTERS.get(value, 0)
        elif key == "date":
            self.filter["date"] = DATE_FILTERS.get(value)
        self._apply_filter()

    def clear_filter(self):
        self.filter = {"cat": "全部类型", "size": 0, "date": None}
        self.om_cat.set("全部类型")
        self.om_size.set("全部大小")
        self.om_date.set("全部日期")
        self._apply_filter()

    def _toggle_showall(self):
        """「显示所有项」开关：默认隐藏 0 字节项，勾选后全量显示。"""
        self.show_all = bool(self.chk_showall.get())
        self._apply_filter()

    def _row_visible(self, f):
        # 默认隐藏 0 字节项（空文件副本无清理价值）
        if not self.show_all and f.get("size", 0) <= 0:
            return False
        ft = self.filter
        if ft["cat"] != "全部类型" and f.get("category", "其他") != ft["cat"]:
            return False
        if f.get("size", 0) < ft["size"]:
            return False
        d = ft["date"]
        if d is not None:
            age = time.time() - f.get("mtime", 0)
            if d >= 0:
                if age > d:
                    return False
            elif age <= -d:          # 一年前（旧文件）
                return False
        return True

    def _insert_row(self, f, gi):
        """按当前筛选插入一行；被过滤的行不显示（数据仍在 result 里）。"""
        if not self._row_visible(f):
            return False
        iid = self.tree.insert("", "end", values=(
            gi, "冗余" if f["redundant"] else "保留",
            fmt_b(f["size"]), fmt_t(f["ctime"]), fmt_t(f["mtime"]),
            f["category"], f["name"], f["folder"], f["hash"]),
            tags=("redundant",) if f["redundant"] else ("keep",))
        self.row_paths[iid] = f
        return True

    def _apply_filter(self):
        """按筛选条件重建结果视图（随时可切，不影响数据与删除校验）。"""
        self.tree.delete(*self.tree.get_children())
        self.row_paths.clear()
        total = 0
        if self.result:
            for gi, g in enumerate(self.result["groups"], 1):
                for f in g["files"]:
                    total += 1
                    self._insert_row(f, gi)
        try:
            self.lbl_fcount.configure(
                text=f"显示 {len(self.tree.get_children())}/{total} 行")
        except Exception:
            pass

    # ---------------- 行操作 ----------------
    def select_redundant(self):
        """一键选中列表中全部冗余副本（跨文件夹组同样适用），
        配合「删除选中冗余」即可一键清理，无需逐行手选。"""
        red = list(self.tree.tag_has("redundant"))
        if not red:
            self.log(" 当前列表没有冗余副本（先扫描出重复组）")
            return
        self.tree.selection_set(red)
        self.tree.see(red[0])
        total = sum(self.row_paths[i]["size"] for i in red if i in self.row_paths)
        cross = sum(1 for g in (self.result or {}).get("groups", [])
                    if len({os.path.dirname(f["path"]) for f in g["files"]}) > 1)
        self.log(f" 已选中全部 {len(red)} 个冗余副本（合计 {fmt_b(total)}）"
                 + (f" · {cross} 组为跨文件夹重复" if cross else "")
                 + " —— 点「 删除选中冗余」一键清理（每组保留副本受保护）")

    def deselect_all(self):
        self.tree.selection_remove(*self.tree.get_children(""))

    def _sel_files(self, only_redundant=False):
        out = []
        for iid in self.tree.selection():
            f = self.row_paths.get(iid)
            if f and (f["redundant"] or not only_redundant):
                out.append(f)
        return out

    def open_sel(self):
        for f in self._sel_files()[:3]:
            os.startfile(f["path"])

    def reveal_sel(self):
        import subprocess
        for f in self._sel_files()[:3]:
            path = os.path.normpath(f["path"])
            if os.path.isfile(path):
                subprocess.Popen('explorer /select,"' + path + '"')
            elif os.path.isdir(path):
                os.startfile(path)

    def copy_path(self):
        f = self._sel_files()
        if f:
            self.clipboard_clear()
            self.clipboard_append("\n".join(x["path"] for x in f))

    def _popup_menu(self, event):
        iid = self.tree.identify_row(event.y)
        if iid:
            if iid not in self.tree.selection():
                self.tree.selection_set(iid)
            self.menu.post(event.x_root, event.y_root)

    def sort_by(self, col):
        items = [(self.tree.set(k, col), k) for k in self.tree.get_children("")]
        try:
            items.sort(key=lambda t: float(t[0].replace(" ", "") or 0), reverse=True)
        except ValueError:
            items.sort()
        for i, (_, k) in enumerate(items):
            self.tree.move(k, "", i)

    def delete_selected(self):
        """后台线程删除 + 逐文件进度显示（进度条/状态行/完成终态），不冻结界面。"""
        from brand_ui import workspace_available
        if not workspace_available(self):
            return
        if getattr(self, "deleting", False):
            self.log("⏳ 删除正在进行中，请稍候…")
            return
        if self.scanning:
            self.log(" 扫描进行中，请等扫描结束再删除")
            return
        files = self._sel_files(only_redundant=True)
        if not files:
            self.log(" 选中项里没有冗余副本（保留副本受保护）")
            return
        bytes_n = sum(f["size"] for f in files)
        if not __import__("tkinter").messagebox.askyesno(
                "确认删除",
                f"删除 {len(files)} 个冗余副本，释放 {fmt_b(bytes_n)}？\n"
                f"引擎校验：同组保留副本存活才删。"):
            return
        groups = self.result["groups"] if self.result else []
        paths = [f["path"] for f in files]
        self.deleting = True
        self._refresh_actions()
        self.btn_delete.configure(state="disabled", text=" 删除中…")
        try:
            self.progress.stop()
            self.progress.configure(mode="determinate", progress_color="#E7BA7A")
            self.progress.set(0)
        except Exception:
            pass
        try:
            self.lbl_status.configure(
                text=f" 删除准备中… 共 {len(paths)} 个冗余副本",
                text_color="#fb923c")
        except Exception:
            pass
        self.log(f" 开始删除 {len(paths)} 个冗余副本…")
        self._delq = queue.Queue()
        threading.Thread(target=self._delete_thread, args=(paths, groups),
                         daemon=True).start()
        self.after(60, self._poll_delete)

    def _poll_delete(self):
        """主线程泵：把删除线程的进度/结果搬到 UI（线程安全，不跨线程碰 Tk）。"""
        try:
            while True:
                item = self._delq.get_nowait()
                tag = item[0]
                if tag == "prog":
                    self._delete_progress(*item[1:])
                elif tag == "done":
                    self._delete_done(*item[1:])
                    return
                elif tag == "error":
                    self._delete_error(item[1])
                    return
        except queue.Empty:
            pass
        if getattr(self, "deleting", False):
            self.after(60, self._poll_delete)

    def _delete_thread(self, paths, groups):
        last = [0.0]          # 节流：进度入队每 100ms 至多一次，防队列风暴

        def cb(done, total, cur, freed):
            now = time.monotonic()
            if done >= total or now - last[0] >= 0.1:
                last[0] = now
                self._delq.put(("prog", done, total,
                                os.path.basename(cur), freed))

        try:
            deleted, skipped, freed = self.engine.delete_redundant(
                paths, groups, progress_cb=cb)
        except Exception as e:
            self._delq.put(("error", str(e)))
            return
        self._delq.put(("done", deleted, skipped, freed))

    def _delete_progress(self, done, total, name, freed):
        try:
            self.progress.set(done / max(total, 1))
            self.lbl_status.configure(
                text=(f" 删除中 {done}/{total} · 已释放 {fmt_b(freed)}"
                      f" · {name[:44]}"),
                text_color="#fb923c")
        except Exception:
            pass

    def _delete_done(self, deleted, skipped, freed):
        self.deleting = False
        self._refresh_actions()
        try:
            self.btn_delete.configure(state="normal", text=" 删除选中冗余")
        except Exception:
            pass
        self.log(f" 删除 {len(deleted)} / 释放 {fmt_b(freed)}"
                 + (f" / 跳过 {len(skipped)}" if skipped else ""))
        # 从结果里移除已删行并刷新（尾部 _apply_filter 同步计数）
        gone = set(deleted)
        if self.result:
            for g in self.result["groups"]:
                g["files"] = [f for f in g["files"] if f["path"] not in gone]
            self.result["groups"] = [g for g in self.result["groups"]
                                     if len(g["files"]) > 1]
            self._show_result(self.result)
        msg = (f" 删除完成：成功 {len(deleted)} 个 · 释放 {fmt_b(freed)}"
               + (f" · 跳过 {len(skipped)}（文件被占用或已不在）" if skipped else ""))
        self._finish_visuals(True, msg, title_mark=" 删除完成")

    def _delete_error(self, e):
        self.deleting = False
        self._refresh_actions()
        try:
            self.btn_delete.configure(state="normal", text=" 删除选中冗余")
        except Exception:
            pass
        self.log(f" 删除出错: {e}")
        self._finish_visuals(False, f" 删除出错：{e}", title_mark=" 删除出错")

    def log(self, m):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", m + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        if m.startswith(("", "", "", "", "")):
            self.lbl_status.configure(text=m)