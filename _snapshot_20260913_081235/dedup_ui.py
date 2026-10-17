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
import threading
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from dedup_core import DedupEngine, logical_drives, system_drive, category_of, SYSTEM_DIR_EXCLUDE

ACCENT = "#00f0ff"
BG = "#020617"
PANEL = "#1e293b"
DIM = "#64748b"


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
        self.title("SafeCleaner Pro · 重复文件查重台")
        self.geometry("1280x760")
        self.configure(fg_color=BG)
        self.after(50, self.lift)
        self.attributes("-topmost", True)
        self.after(200, lambda: self.attributes("-topmost", False))

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
        self.grid_columnconfigure(0, weight=0, minsize=300)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ===== 左列 =====
        left = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10)
        left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        ctk.CTkLabel(left, text="🔍 查重范围", font=ctk.CTkFont(family="Microsoft YaHei UI", size=14, weight="bold"),
                     text_color=ACCENT).pack(anchor="w", padx=14, pady=(12, 4))

        # 盘符快选
        self.drive_frame = ctk.CTkFrame(left, fg_color="transparent")
        self.drive_frame.pack(fill="x", padx=14)
        sysd = system_drive()
        for i, letter in enumerate(logical_drives()):
            txt = f"{letter}盘" + ("（系统盘·默认排除）" if letter == sysd else "")
            ctk.CTkButton(
                self.drive_frame, text=txt, height=26,
                fg_color="#334155", hover_color="#475569",
                font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
                command=lambda l=letter, s=txt: self.add_scope(f"{l}:\\", s),
            ).grid(row=i // 2, column=i % 2, padx=3, pady=3, sticky="ew")
        self.drive_frame.grid_columnconfigure(0, weight=1)
        self.drive_frame.grid_columnconfigure(1, weight=1)

        # 位置列表
        ctk.CTkLabel(left, text="已添加位置（点×移除）", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
                     text_color=DIM).pack(anchor="w", padx=14, pady=(8, 2))
        self.scope_box = ctk.CTkTextbox(left, height=90, font=ctk.CTkFont(family="Microsoft YaHei UI", size=12))
        self.scope_box.pack(fill="x", padx=14)
        self.scope_box.insert("1.0", "（尚未添加位置，点上方盘符或下方按钮）")
        self.scope_box.configure(state="disabled")

        ctk.CTkButton(left, text="＋ 添加文件夹…", height=28,
                      command=self.add_folder).pack(fill="x", padx=14, pady=(6, 0))

        # 选项
        self.var_increment = ctk.BooleanVar(value=True)
        self.var_sysdrive = ctk.BooleanVar(value=False)
        self.var_excl_sysdir = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(left, text="增量模式（跳过没变过的文件）", variable=self.var_increment,
                        font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)).pack(anchor="w", padx=14, pady=(10, 0))
        ctk.CTkCheckBox(left, text="扫描系统盘（默认排除C盘）", variable=self.var_sysdrive,
                        font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)).pack(anchor="w", padx=14, pady=(4, 0))
        ctk.CTkCheckBox(left, text="排除系统目录/系统文件", variable=self.var_excl_sysdir,
                        font=ctk.CTkFont(family="Microsoft YaHei UI", size=12)).pack(anchor="w", padx=14, pady=(4, 0))

        # 开始
        self.btn_start = ctk.CTkButton(left, text="🚀 开始查重", height=38,
                                       font=ctk.CTkFont(family="Microsoft YaHei UI", size=14, weight="bold"),
                                       fg_color="#0891b2", hover_color="#06b6d4",
                                       command=self.start_scan)
        self.btn_start.pack(fill="x", padx=14, pady=(12, 4))
        self.btn_force = ctk.CTkButton(left, text="🔁 强制重扫（忽略缓存）", height=28,
                                       fg_color="#475569", hover_color="#64748b",
                                       command=lambda: self.start_scan(force=True))
        self.btn_force.pack(fill="x", padx=14, pady=(0, 4))
        self.btn_stop = ctk.CTkButton(left, text="⏹ 停止", height=28, fg_color="#7f1d1d",
                                      hover_color="#991b1b", command=self.stop_scan)
        self.btn_stop.pack(fill="x", padx=14, pady=(0, 6))

        self.progress = ctk.CTkProgressBar(left)
        self.progress.set(0)
        self.progress.pack(fill="x", padx=14)
        self.lbl_status = ctk.CTkLabel(left, text="就绪", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
                                       text_color=DIM, anchor="w")
        self.lbl_status.pack(fill="x", padx=14, pady=(2, 4))

        # 历史
        ctk.CTkLabel(left, text="扫描历史", font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
                     text_color=DIM).pack(anchor="w", padx=14, pady=(6, 2))
        self.hist_combo = ctk.CTkComboBox(left, values=self._history_labels(),
                                          command=self.load_history)
        self.hist_combo.pack(fill="x", padx=14)

        self.log_box = ctk.CTkTextbox(left, height=140, font=ctk.CTkFont(family="Microsoft YaHei UI", size=11))
        self.log_box.pack(fill="both", expand=True, padx=14, pady=(8, 12))
        self.log_box.insert("end", "SafeCleanerPro 查重引擎就绪。\n")
        self.log_box.configure(state="disabled")

        # ===== 右侧 =====
        right = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
        right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)
        right.grid_rowconfigure(2, weight=1)
        right.grid_columnconfigure(0, weight=1)

        # 统计卡
        cards = ctk.CTkFrame(right, fg_color="transparent")
        cards.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        self.lbl_stat = ctk.CTkLabel(cards, text="尚未扫描 · 载入上次结果或开始新扫描",
                                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=13), text_color=DIM, anchor="w")
        self.lbl_stat.pack(anchor="w")

        # 操作条
        bar = ctk.CTkFrame(right, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        ctk.CTkButton(bar, text="📂 打开", width=80, height=26, command=self.open_sel).pack(side="left", padx=(0, 6))
        ctk.CTkButton(bar, text="📁 定位", width=80, height=26, command=self.reveal_sel).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="🗑 删除选中冗余", width=140, height=26, fg_color="#b91c1c",
                      hover_color="#dc2626", command=self.delete_selected).pack(side="left", padx=6)
        ctk.CTkLabel(bar, text="提示: 双击行=打开 · 右键=菜单 · 红行=冗余副本",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=11), text_color=DIM).pack(side="right")

        # 结果表
        wrap = ctk.CTkFrame(right, fg_color=PANEL, corner_radius=10)
        wrap.grid(row=2, column=0, sticky="nsew")
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
        self.tree.tag_configure("redundant", background="#2a1215", foreground="#fca5a5")
        self.tree.tag_configure("keep", background="#0f2417", foreground="#86efac")
        vsb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=6)
        vsb.pack(side="right", fill="y", pady=6, padx=(0, 6))
        self.tree.bind("<Double-1>", lambda e: self.open_sel())
        self.tree.bind("<Button-3>", self._popup_menu)
        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="📂 打开", command=self.open_sel)
        self.menu.add_command(label="📁 定位", command=self.reveal_sel)
        self.menu.add_command(label="📋 复制路径", command=self.copy_path)

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

    # ---------------- 扫描 ----------------
    def start_scan(self, force=False):
        if self.scanning or not self.scopes:
            if not self.scopes:
                self.log("⚠ 先添加范围（点盘符或添加文件夹）")
            return
        if not self.var_excl_sysdir.get():
            SYSTEM_DIR_EXCLUDE.clear()   # 用户显式关闭系统目录排除
        self.scanning = True
        self.cancel["stop"] = False
        self.btn_start.configure(state="disabled")
        self.progress.set(0)
        # 实时结果容器: 组在扫描中即时上屏，可随时操作
        self.result = {"stats": {"files": 0, "groups": 0, "redundant": 0,
                                 "reclaim_bytes": 0, "duration": 0, "mode": "扫描中"},
                       "groups": [], "scan_id": None}
        self.tree.delete(*self.tree.get_children())
        self.row_paths.clear()
        self.lbl_stat.configure(text="扫描中…（结果实时出现，可随时打开/定位/删除）")
        self.log(f"—— 开始扫描（{'强制重扫' if force else '增量'}）——")
        scopes = list(self.scopes)
        incremental = self.var_increment.get() and not force
        excl = not self.var_sysdrive.get()
        t = threading.Thread(target=self._scan_thread,
                             args=(scopes, incremental, excl, force), daemon=True)
        t.start()

    def stop_scan(self):
        self.cancel["stop"] = True
        self.log("⏹ 停止指令已发…")

    def _scan_thread(self, scopes, incremental, excl, force):
        def log(m):
            self.after(0, self.log, m)

        def prog(v):
            self.after(0, lambda: self.progress.set(v))

        try:
            r = self.engine.run(scopes, incremental=incremental,
                                exclude_system=excl, progress_cb=prog,
                                log_cb=log, cancel=self.cancel,
                                on_group=lambda g: self.after(0, self._add_group_live, g))
        except Exception as e:
            self.after(0, self.log, f"❌ 引擎异常: {e}")
            self.after(0, self._scan_done)
            return
        # 关闭系统目录排除后恢复默认集合（下次扫描生效）
        if r.get("scan_id"):
            self.after(0, lambda: self._show_result(r))
        self.after(0, self._scan_done)

    def _add_group_live(self, g):
        """扫描中每确认一组重复立即上屏，可随时操作"""
        if self.result is None:
            return
        self.result["groups"].append(g)
        gi = len(self.result["groups"])
        for f in g["files"]:
            iid = self.tree.insert("", "end", values=(
                gi, "冗余" if f["redundant"] else "保留",
                fmt_b(f["size"]), fmt_t(f["ctime"]), fmt_t(f["mtime"]),
                f["category"], f["name"], f["folder"], f["hash"]),
                tags=("redundant",) if f["redundant"] else ("keep",))
            self.row_paths[iid] = f
        s = self.result["stats"]
        s["groups"] += 1
        s["redundant"] += g["count"] - 1
        s["reclaim_bytes"] += g["size"] * (g["count"] - 1)
        self.lbl_stat.configure(text=(
            f"扫描中… 已确认 {s['groups']} 组 / 冗余 {s['redundant']} / "
            f"可释放 {fmt_b(s['reclaim_bytes'])}（列表实时更新，可随时操作）"))

    def _scan_done(self):
        self.scanning = False
        self.btn_start.configure(state="normal")
        self.hist_combo.configure(values=self._history_labels())

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
                iid = self.tree.insert("", "end", values=(
                    gi, "冗余" if f["redundant"] else "保留",
                    fmt_b(f["size"]), fmt_t(f["ctime"]), fmt_t(f["mtime"]),
                    f["category"], f["name"], f["folder"], f["hash"]),
                    tags=("redundant",) if f["redundant"] else ("keep",))
                self.row_paths[iid] = f
                n += 1
                if n % 800 == 0:
                    self.update_idletasks()

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

    # ---------------- 行操作 ----------------
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
        for f in self._sel_files()[:3]:
            os.system(f'explorer /select,"{f["path"]}"')

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
        files = self._sel_files(only_redundant=True)
        if not files:
            self.log("⚠ 选中项里没有冗余副本（保留副本受保护）")
            return
        bytes_n = sum(f["size"] for f in files)
        if not __import__("tkinter").messagebox.askyesno(
                "确认删除",
                f"删除 {len(files)} 个冗余副本，释放 {fmt_b(bytes_n)}？\n"
                f"引擎校验：同组保留副本存活才删。"):
            return
        groups = self.result["groups"] if self.result else []
        paths = [f["path"] for f in files]
        deleted, skipped, freed = self.engine.delete_redundant(paths, groups)
        self.log(f"🗑 删除 {len(deleted)} / 释放 {fmt_b(freed)}"
                 + (f" / 跳过 {len(skipped)}" if skipped else ""))
        # 从结果里移除已删行并刷新
        gone = set(deleted)
        if self.result:
            for g in self.result["groups"]:
                g["files"] = [f for f in g["files"] if f["path"] not in gone]
            self.result["groups"] = [g for g in self.result["groups"] if len(g["files"]) > 1]
            self._show_result(self.result)

    def log(self, m):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", m + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        if m.startswith(("📂", "🔗", "🔬", "✅", "❌")):
            self.lbl_status.configure(text=m)