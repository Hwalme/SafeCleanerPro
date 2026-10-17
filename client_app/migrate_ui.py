# -*- coding: utf-8 -*-
"""C 盘无损迁移台：独立窗口。

把 C 盘上最占空间的两类内容整体搬到其他数据盘，原位置留 NTFS Junction ——
程序按原路径照常读写，无感知、可迁回：

- 常规目录：桌面 / 下载 / 文档 / 图片 / 视频 / 音乐 / 收藏夹…
  （被其他软件迁移过、出现"多桌面/多文档"重复的，自动检测并统一迁移，
   同名文件自动重命名共存；被 OneDrive 接管的目录只展示不迁移）
- AI 记忆：Claude / Gemini / Codex / Cursor / 本地模型…（migrate_core.CATALOG）

迁移全程走 migrate_core 安全流水线（复制 → 校验 → 换位 → 联接 → 穿透校验
→ 清备份），任何一步失败自动回滚，原路径数据从未消失。
"""
import base64
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk, filedialog

import customtkinter as ctk

import migrate_core as mc
import win_icons
from cleaner_core import format_size
from ui_theme import style_dark_treeview

from ui_theme import (BG, PANEL, CARD, ACCENT, OK, WARN, ERR, DIM,
                      UI_FAMILY as FONT, setup_popup)

# item 运行期状态 ， (显示文本, 颜色)
_ROW_STATUS = {
    "clean": ("未迁移", DIM),
    "migrated": (" 已迁移", OK),
    "partial": ("部分迁移", WARN),
    "broken": (" 联接悬空!", ERR),
    "scanning": ("… 统计中", WARN),
    "foreign": ("已他迁·可统一", WARN),
    "foreign_dup": ("重复!建议统一", ERR),
    "onedrive": ("OneDrive 管理", DIM),
    "missing": (" 不存在", DIM),
}

# 可勾选迁移的状态（onedrive / missing / broken 不可迁）
_MIGRATABLE = ("clean", "foreign", "foreign_dup")

# 分组显示顺序与组名
_CAT_ORDER = ["常规目录", "编程助手", "编辑器记忆", "编辑器记忆(自动发现)",
              "Agent 记忆(自动发现)", "AI 助手", "本地模型"]
_CAT_DISPLAY = {
    "常规目录": " 常规目录（桌面 / 下载 / 文档…）",
    "编程助手": " AI 记忆 · 编程助手",
    "编辑器记忆": " AI 记忆 · 编辑器记忆",
    "编辑器记忆(自动发现)": " AI 记忆 · 编辑器记忆 · 自动发现",
    "Agent 记忆(自动发现)": " AI 记忆 · Agent 记忆 · 自动发现",
    "AI 助手": " AI 记忆 · AI 助手",
    "本地模型": " AI 记忆 · 本地模型",
}


def _cat_sort_key(cat):
    return (_CAT_ORDER.index(cat) if cat in _CAT_ORDER
            else len(_CAT_ORDER), cat)


class MemoryMigrateWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        setup_popup(self, "C 盘无损迁移台")
        self.geometry("1300x820")
        self.minsize(1120, 740)

        self.items = []            # 常规目录 + AI 记忆 全部迁移项
        self.info = {}             # id -> {files, bytes, status}
        self.checked = set()       # 勾选的 item id
        self.working = False       # 扫描或迁移进行中
        self.q = queue.Queue()
        self._cancel = False
        self._icons = {}           # id -> tk.PhotoImage（真实软件图标）
        self._icon_stop = False

        self._build()
        from ui_theme import popup_front, apply_window_chrome
        popup_front(self, master)
        apply_window_chrome(self)
        self.after(260, lambda: apply_window_chrome(self))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(150, self.start_scan)
        self.after(500, self._load_icons_async)

    # ------------------------------------------------------------------
    # 界面
    # ------------------------------------------------------------------
    def _build(self):
        from brand_ui import popup_header, button
        head = popup_header(self, "C盘迁移",
                            "桌面、下载、文档与 AI 记忆整体搬离 C 盘。"
                            "原路径入口保留，之后放桌面/下载的东西自动存到新盘，无感、可迁回。")
        self.btn_rescan = button(head, "刷新状态", self.start_scan, width=120, height=40)
        self.btn_rescan.pack(side="right", padx=(16, 0))

        # 汇总卡
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x", padx=24, pady=(0, 8))
        self.card_free = self._card(cards, "C 盘可释放", "…")
        self.card_hits = self._card(cards, "迁移项", "0")
        self.card_done = self._card(cards, "已迁移", "0")
        self.card_tfree = self._card(cards, "目标盘剩余", "-")

        # 目标位置：常规目录 / AI 记忆 各自独立的目标根（默认两条总路径）
        tgt = ctk.CTkFrame(self, fg_color="transparent")
        tgt.pack(fill="x", padx=24, pady=(0, 2))
        ctk.CTkLabel(tgt, text="常规目录迁移到：",
                     font=F(UI_FAMILY, 13, "bold"),
                     text_color=DIM).pack(side="left")
        self.var_drive_shell = tk.StringVar()
        self.om_drive_shell = ctk.CTkOptionMenu(
            tgt, variable=self.var_drive_shell, width=170, height=30,
            fg_color=PANEL, button_color="#2A3541", button_hover_color="#2A3541",
            text_color=ACCENT,
            command=self._on_drive_changed_shell)
        self.om_drive_shell.pack(side="left", padx=(8, 8))
        self.var_root_shell = tk.StringVar()
        self.ent_root_shell = ctk.CTkEntry(tgt, textvariable=self.var_root_shell,
                                           width=330, height=30, fg_color=PANEL,
                                           border_color="#2A3541",
                                           text_color="#F0F4F7")
        self.ent_root_shell.pack(side="left", padx=(0, 0))
        ctk.CTkButton(tgt, text="浏览", width=52, height=30,
                      fg_color="#294652", hover_color="#395C68",
                      command=lambda: self._browse_root("shell")
                      ).pack(side="left", padx=(8, 0))

        tgt2 = ctk.CTkFrame(self, fg_color="transparent")
        tgt2.pack(fill="x", padx=24, pady=(4, 6))
        ctk.CTkLabel(tgt2, text="AI 记忆迁移到：",
                     font=F(UI_FAMILY, 13, "bold"),
                     text_color=DIM).pack(side="left")
        self.var_drive_ai = tk.StringVar()
        self.om_drive_ai = ctk.CTkOptionMenu(
            tgt2, variable=self.var_drive_ai, width=170, height=30,
            fg_color=PANEL, button_color="#2A3541", button_hover_color="#2A3541",
            text_color=ACCENT,
            command=self._on_drive_changed_ai)
        self.om_drive_ai.pack(side="left", padx=(8, 8))
        self.var_root_ai = tk.StringVar()
        self.ent_root_ai = ctk.CTkEntry(tgt2, textvariable=self.var_root_ai,
                                        width=330, height=30, fg_color=PANEL,
                                        border_color="#2A3541",
                                        text_color="#F0F4F7")
        self.ent_root_ai.pack(side="left")
        ctk.CTkButton(tgt2, text="浏览", width=52, height=30,
                      fg_color="#294652", hover_color="#395C68",
                      command=lambda: self._browse_root("ai")
                      ).pack(side="left", padx=(8, 0))
        self.var_auto = tk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            tgt2, text="自动建立对应文件夹", variable=self.var_auto, height=30,
            checkbox_width=18, checkbox_height=18,
            font=F(UI_FAMILY, 12), text_color="#C4CFDB",
            fg_color="#294652", hover_color="#395C68",
            border_color="#3A4A58").pack(side="left", padx=(14, 0))
        ctk.CTkLabel(tgt2, text="右键项目行可单独指定目标",
                     font=F(UI_FAMILY, 11), text_color=MUTED
                     ).pack(side="right")

        # 进度 + 状态
        self.prog = ctk.CTkProgressBar(self, height=3, progress_color=ACCENT)
        self.prog.pack(fill="x", padx=24, pady=(4, 6))
        self.prog.set(0)
        self.lbl_status = ctk.CTkLabel(
            self, text="正在统计 C 盘迁移项体积（常规目录 + AI 记忆）…",
            font=ctk.CTkFont(family=FONT, size=12), text_color=WARN,
            anchor="w")
        self.lbl_status.pack(fill="x", padx=24, pady=(0, 6))

        # 表格（树形分组：分组行可折叠，点击分组行整组勾选）
        style_dark_treeview(rowheight=32)
        wrap = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10)
        wrap.pack(fill="both", expand=True, padx=24, pady=(0, 6))
        cols = ("sel", "size", "files", "status", "path")
        self.tree = ttk.Treeview(wrap, columns=cols, show="tree headings",
                                 selectmode="none")
        self.tree.heading("#0", text="分组 / 项目")
        self.tree.column("#0", width=340, anchor="w", stretch=False, minwidth=280)
        heads = {"sel": "选择", "size": "体积", "files": "文件数",
                 "status": "状态", "path": "位置"}
        widths = {"sel": 52, "size": 96, "files": 70, "status": 118,
                  "path": 490}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            anchor = "center" if c in ("sel", "size", "files", "status") else "w"
            self.tree.column(c, width=widths[c], anchor=anchor,
                             stretch=(c == "path"))
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=hs.set)
        hs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.tag_configure("group", foreground=ACCENT, background="#203640")
        self.tree.tag_configure("migrated", foreground="#91D5B6")
        self.tree.tag_configure("broken", foreground="#ECA0A6")
        self.tree.tag_configure("partial", foreground="#E7BA7A")
        self.tree.tag_configure("clean", foreground="#F0F4F7")
        self.tree.bind("<ButtonRelease-1>", self._on_click)

        # 底部操作条
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=24, pady=(0, 4))
        ctk.CTkButton(bar, text=" 全选未迁移", width=118, height=30,
                      fg_color="#294652", hover_color="#395C68",
                      command=lambda: self._select_all("clean")).pack(side="left")
        ctk.CTkButton(bar, text=" 全不选", width=88, height=30,
                      fg_color="#1D252E", hover_color="#2A3541",
                      command=lambda: self._select_all(None)).pack(side="left", padx=8)
        self.btn_migrate = ctk.CTkButton(bar, text="迁移选中项", width=150,
                                         height=30, fg_color="#294652",
                                         hover_color="#395C68",
                                         command=self.start_migrate)
        self.btn_migrate.pack(side="left", padx=8)
        self.btn_restore = ctk.CTkButton(bar, text="迁回 C 盘", width=120,
                                         height=30, fg_color="#294652",
                                         hover_color="#395C68",
                                         command=self.start_restore)
        self.btn_restore.pack(side="left", padx=8)
        ctk.CTkLabel(bar, text="点击「分组行」整组勾选/取消 · 组可折叠 · "
                               "迁移前请关闭对应软件，占用会自动回滚",
                     font=ctk.CTkFont(family=FONT, size=11),
                     text_color=DIM).pack(side="right")

        # 日志
        self.txt_log = ctk.CTkTextbox(self, height=112, fg_color=PANEL,
                                      text_color="#A3AFBD",
                                      font=ctk.CTkFont(family="Consolas", size=12))
        self.txt_log.pack(fill="x", padx=24, pady=(4, 14))
        self.txt_log.insert("1.0", "› 原理：把桌面/下载/文档与 AI 记忆整体搬到目标盘，"
                                   "原位置建立 NTFS 目录联接，所有程序仍按原路径访问"
                                   "（指向新位置），无需管理员权限。\n"
                                   "› 重复桌面/文档急救：被其他软件迁过、两边都有内容的，"
                                   "勾选后自动合并（同名文件重命名共存），注册表归位，只留一张桌面。\n"
                                   "› OneDrive 接管的目录不迁移（避免破坏同步）。\n")
        self.txt_log.configure(state="disabled")
        self.var_root.trace_add("write", lambda *_: self._update_buttons())
        self.var_drive.trace_add("write", lambda *_: self._update_buttons())
        self._update_buttons()

    def _card(self, parent, title, value):
        f = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0, width=230, height=78)
        f.pack(side="left", fill="x", expand=True, padx=(0, 14))
        f.pack_propagate(False)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(family=FONT, size=11),
                     text_color=DIM).pack(pady=(8, 0))
        lbl = ctk.CTkLabel(f, text=value,
                           font=ctk.CTkFont(family=FONT, size=26, weight="bold"),
                           text_color="#F0F4F7")
        lbl.pack()
        return lbl

    # ------------------------------------------------------------------
    # 目标盘选择
    # ------------------------------------------------------------------
    def _drive_options(self):
        opts = []
        for d in mc.list_target_drives():
            free = mc.get_dir_free_space(d)
            opts.append((d, f"{d}  (剩余 {format_size(free)})"))
        return opts

    def _populate_drives(self):
        opts = self._drive_options()
        if not opts:
            for var in (self.var_drive_shell, self.var_drive_ai):
                var.set("未发现可用目标盘")
            for om in (self.om_drive_shell, self.om_drive_ai):
                om.configure(values=["未发现可用目标盘"], state="disabled")
            self.var_root_shell.set("")
            self.var_root_ai.set("")
            self.lbl_status.configure(text="未发现可用目标盘，请连接其他本地磁盘后刷新。", text_color=WARN)
            self._update_buttons()
            return
        vals = [label for _d, label in opts]
        self.om_drive_shell.configure(values=vals, state="normal")
        self.om_drive_ai.configure(values=vals, state="normal")
        # 两条默认总路径：常规目录 / AI 记忆 各自独立、互不混放；
        # 记忆的上次位置优先，否则选剩余空间最大的盘
        cfg = mc.load_target_config()
        best = max(opts, key=lambda x: mc.get_dir_free_space(x[0]))
        for var_drive, var_root, key, default_tail in (
                (self.var_drive_shell, self.var_root_shell, "root_shell",
                 os.path.join("C盘迁移", "常规目录")),
                (self.var_drive_ai, self.var_root_ai, "root_ai",
                 os.path.join("C盘迁移", "AI记忆"))):
            saved = cfg.get(key, "")
            sd = os.path.splitdrive(saved)[0].lower() if saved else ""
            match = next((d for d, _l in opts
                          if d.lower().rstrip("\\") == sd), None) \
                if saved else None
            if match:
                var_drive.set(next(l for d, l in opts if d == match))
                var_root.set(saved)
            else:
                var_drive.set(best[1])
                drive = self._label_drive(best[1])
                var_root.set(os.path.join(drive, default_tail) if drive else "")
        self._load_custom_targets()
        self._update_buttons()

    def _load_custom_targets(self):
        """载入各子项自定义目标路径（右键设置过的一次生效）。"""
        self.custom_targets = dict(
            mc.load_target_config().get("custom_targets", {}))

    def _label_drive(self, label):
        if label and len(label) >= 2 and label[1] == ":":
            return label[:2] + "\\"
        return None

    def _on_drive_changed_shell(self, _label=None):
        drive = self._label_drive(self.var_drive_shell.get())
        if drive and not self._root_on_drive(self.var_root_shell.get(), drive):
            self.var_root_shell.set(os.path.join(drive, "C盘迁移", "常规目录"))

    def _on_drive_changed_ai(self, _label=None):
        drive = self._label_drive(self.var_drive_ai.get())
        if drive and not self._root_on_drive(self.var_root_ai.get(), drive):
            self.var_root_ai.set(os.path.join(drive, "C盘迁移", "AI记忆"))

    @staticmethod
    def _root_on_drive(root, drive):
        return bool(root) and \
            os.path.splitdrive(os.path.abspath(root))[0].lower() == \
            drive.lower().rstrip("\\")

    def _browse_root(self, kind):
        if kind == "shell":
            var, title = self.var_root_shell, "选择「常规目录」目标根（将自动建立 桌面/下载… 等文件夹）"
            drive = self._label_drive(self.var_drive_shell.get())
        else:
            var, title = self.var_root_ai, "选择「AI 记忆」目标根"
            drive = self._label_drive(self.var_drive_ai.get())
        picked = filedialog.askdirectory(parent=self, title=title,
                                         initialdir=drive or "C:\\")
        if picked:
            var.set(os.path.normpath(picked))

    def _selected_root_shell(self):
        return self._norm_root(self.var_root_shell.get(),
                               self._label_drive(self.var_drive_shell.get()))

    def _selected_root_ai(self):
        return self._norm_root(self.var_root_ai.get(),
                               self._label_drive(self.var_drive_ai.get()))

    @staticmethod
    def _norm_root(root, drive):
        root = (root or "").strip().strip('"')
        if not root or not drive:
            return None
        if not root.upper().startswith(drive.upper()):
            root = os.path.join(drive,
                                os.path.splitdrive(root)[1].lstrip("\\/"))
        return os.path.abspath(root)

    # ------------------------------------------------------------------
    # 扫描（统计体积 / 状态）
    # ------------------------------------------------------------------
    def start_scan(self):
        from brand_ui import workspace_available
        if not workspace_available(self):
            return
        if self.working:
            return
        self.working = True
        self.checked = set()
        self._cancel = False
        self.tree.delete(*self.tree.get_children())
        self.btn_rescan.configure(state="disabled", text="统计中…")
        self.btn_migrate.configure(state="disabled")
        self.btn_restore.configure(state="disabled")
        self.prog.set(0.03)
        self.lbl_status.configure(text=" 正在统计 C 盘迁移项体积（常规目录 + AI 记忆）…",
                                  text_color=WARN)
        self._populate_drives()
        threading.Thread(target=self._scan_thread, daemon=True).start()
        self.after(80, self._poll)

    def _scan_thread(self):
        try:
            self.items = mc.build_shell_items() + mc.build_catalog()
            total = len(self.items)
            # 并行统计（walk 是 IO 密集；.gemini 21GB 单项要几十秒，串行等不起）
            from concurrent.futures import ThreadPoolExecutor, as_completed

            def measure(it):
                if self._cancel:
                    return None
                try:
                    if it.get("kind") == "shell":
                        f, b, status, _ex = mc.shell_item_stats(it)
                        return it, {"status": status, "files": f,
                                    "bytes": b, "extras": _ex}
                    stat = {"status": mc.item_status(it), "files": 0, "bytes": 0}
                    if stat["status"] == "clean":
                        f = b = 0
                        for s in it["sources_resolved"]:
                            sf, sb, _sr = mc.walk_stats(s)
                            f += sf
                            b += sb
                        stat["files"], stat["bytes"] = f, b
                    elif stat["status"] == "migrated":
                        f = b = 0
                        for s in it["sources_resolved"]:
                            tgt = mc.migrated_target_of(s)
                            if tgt:
                                sf, sb, _sr = mc.walk_stats(tgt)
                                f += sf
                                b += sb
                        stat["files"], stat["bytes"] = f, b
                    return it, stat
                except Exception:
                    return it, {"status": mc.item_status(it)
                                if it.get("kind") != "shell" else "missing",
                                "files": 0, "bytes": 0}

            done = 0
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = [pool.submit(measure, it) for it in self.items]
                for fut in as_completed(futures):
                    res = fut.result()
                    if res is None:
                        continue
                    it, stat = res
                    self.info[it["id"]] = stat
                    done += 1
                    self.q.put(("item", it, done, total))
            self.q.put(("done",))
        except Exception as e:
            self.q.put(("error", str(e)))

    # ------------------------------------------------------------------
    # 分组树：分组行（g:类别）+ 项目行（iid=项 id）
    # ------------------------------------------------------------------
    def _group_values(self, cat):
        its = [it for it in self.items if it.get("category", "") == cat]
        n = len(its)
        tot_b = sum(self.info.get(it["id"], {}).get("bytes", 0) for it in its)
        tot_f = sum(self.info.get(it["id"], {}).get("files", 0) for it in its)
        checked_n = sum(1 for it in its if it["id"] in self.checked)
        mark = "全选" if (n and checked_n == n) else ("部分" if checked_n else "选择")
        clean_n = sum(1 for it in its
                      if self.info.get(it["id"], {}).get("status") in _MIGRATABLE)
        mig_n = sum(1 for it in its
                    if self.info.get(it["id"], {}).get("status") == "migrated")
        return (mark, format_size(tot_b), tot_f,
                f"待迁 {clean_n} · 已迁 {mig_n}", "点击整组勾选/取消")

    def _ensure_group(self, cat):
        gid = "g:" + cat
        if not self.tree.exists(gid):
            disp = _CAT_DISPLAY.get(cat, cat)
            n = sum(1 for it in self.items if it.get("category", "") == cat)
            self.tree.insert("", "end", iid=gid, open=True, tags=("group",),
                             text=f"{disp}（{n} 项）",
                             values=self._group_values(cat))
        return gid

    def _row_values(self, it):
        stat = self.info.get(it["id"], {})
        status = stat.get("status", "clean")
        label, _c = _ROW_STATUS.get(status, (status, DIM))
        if it.get("kind") == "shell":
            path = it["c_path"]
            if status in ("foreign", "foreign_dup"):
                ex = stat.get("extras") or {}
                c_n, r_n = ex.get("c_files", 0), ex.get("reg_files", 0)
                if status == "foreign_dup":
                    path = (f"注册表 → {it['reg_path']}"
                            f"（重复：C 盘原位 {c_n} 个 · 他处 {r_n} 个文件）")
                else:
                    path = f"注册表 → {it['reg_path']}"
        else:
            path = it["sources_resolved"][0]
            if len(it["sources_resolved"]) > 1:
                path = f"{path}  (+{len(it['sources_resolved']) - 1} 处)"
        return ("已选" if it["id"] in self.checked else
                ("不可" if status in ("onedrive", "missing", "broken") else "选择"),
                format_size(stat.get("bytes", 0)),
                stat.get("files", 0), label, path)

    def _row_tag(self, it):
        status = self.info.get(it["id"], {}).get("status", "clean")
        return {"migrated": "migrated", "broken": "broken",
                "partial": "partial", "foreign": "partial",
                "foreign_dup": "broken"}.get(status, "clean")

    def _insert_row(self, it, gid=None):
        if gid is None:
            gid = self._ensure_group(it.get("category", ""))
        img = self._icons.get(it["id"])
        kw = {"text": it["name"] if img else f'{it.get("icon", "")} {it["name"]}',
              "values": self._row_values(it), "tags": (self._row_tag(it),)}
        if img:
            kw["image"] = img
        self.tree.insert(gid, "end", iid=it["id"], **kw)

    def _render_tree(self):
        """按类别分组、组内按体积降序重建整棵列表。"""
        self.tree.delete(*self.tree.get_children(""))
        cats = {}
        for it in self.items:
            cats.setdefault(it.get("category", ""), []).append(it)
        for cat in sorted(cats, key=_cat_sort_key):
            gid = "g:" + cat
            its = sorted(cats[cat],
                         key=lambda x: -self.info.get(x["id"], {}).get("bytes", 0))
            disp = _CAT_DISPLAY.get(cat, cat)
            self.tree.insert("", "end", iid=gid, open=True, tags=("group",),
                             text=f"{disp}（{len(its)} 项）",
                             values=self._group_values(cat))
            for it in its:
                self._insert_row(it, gid)

    def _load_icons_async(self):
        """后台提取各软件真实图标，就绪后经队列上屏（不阻塞扫描）。"""
        def work():
            # 等扫描线程建好目录册（build_catalog 需要全盘统计，较慢）
            t0 = time.time()
            while not self.items and not self._icon_stop and \
                    time.time() - t0 < 60:
                time.sleep(0.2)
            for it in list(self.items):
                if self._icon_stop:
                    return
                try:
                    png = win_icons.resolve_item_png(it["id"])
                except Exception:
                    png = None
                if png:
                    self.q.put(("icon", it["id"], png))
        threading.Thread(target=work, daemon=True).start()

    def _refresh_row(self, iid):
        it = next((x for x in self.items if x["id"] == iid), None)
        if not it or not self.tree.exists(iid):
            return
        self.tree.item(iid, values=self._row_values(it), tags=(self._row_tag(it),))

    def _refresh_group(self, gid):
        if gid and gid.startswith("g:") and self.tree.exists(gid):
            self.tree.item(gid, values=self._group_values(gid[2:]))

    def _on_click(self, event):
        if self.working:
            return
        row = self.tree.identify_row(event.y)
        if not row:
            return
        if row.startswith("g:"):
            # 整组勾选/取消（OneDrive 管理等不可迁项自动跳过）
            cat = row[2:]
            its = [it for it in self.items if it.get("category", "") == cat
                   and self.info.get(it["id"], {}).get("status", "clean")
                   in _MIGRATABLE + ("migrated",)]
            if not its:
                return
            all_on = all(it["id"] in self.checked for it in its)
            if all_on:
                self.checked -= {it["id"] for it in its}
            else:
                self.checked |= {it["id"] for it in its}
            for it in its:
                self._refresh_row(it["id"])
            self._refresh_group(row)
            self._update_buttons()
            return
        if row not in {it["id"] for it in self.items}:
            return
        status = self.info.get(row, {}).get("status", "clean")
        if status not in _MIGRATABLE and status != "migrated":
            return          # OneDrive 管理 / 不存在 / 悬空：不可勾选
        if row in self.checked:
            self.checked.discard(row)
        else:
            self.checked.add(row)
        self._refresh_row(row)
        self._refresh_group(self.tree.parent(row))
        self._update_buttons()

    def _select_all(self, mode):
        if self.working:
            return
        self.checked = set()
        if mode == "clean":
            for it in self.items:
                if self.info.get(it["id"], {}).get("status") in _MIGRATABLE:
                    self.checked.add(it["id"])
        elif mode == "migrated":
            for it in self.items:
                if self.info.get(it["id"], {}).get("status") == "migrated":
                    self.checked.add(it["id"])
        for it in self.items:
            self._refresh_row(it["id"])
        for gid in self.tree.get_children(""):
            self._refresh_group(gid)
        self._update_buttons()

    def _update_buttons(self):
        if self.working:
            self.btn_migrate.configure(state="disabled")
            self.btn_restore.configure(state="disabled")
            return
        has_clean = any(
            self.info.get(i, {}).get("status") in _MIGRATABLE
            for i in self.checked)
        has_mig = any(
            self.info.get(i, {}).get("status") == "migrated" for i in self.checked)
        self.btn_migrate.configure(state="normal" if has_clean and self._selected_drive() and self._selected_root() else "disabled")
        self.btn_restore.configure(state="normal" if has_mig else "disabled")

    def _update_cards(self):
        total_b = sum(v.get("bytes", 0) for v in self.info.values()
                      if v.get("status") == "clean")
        mig = sum(1 for v in self.info.values() if v.get("status") == "migrated")
        self.card_free.configure(text=format_size(total_b))
        self.card_hits.configure(text=str(len(self.items)))
        self.card_done.configure(text=str(mig))
        root = self._selected_root()
        if root:
            self.card_tfree.configure(text=format_size(mc.get_dir_free_space(root)))

    # ------------------------------------------------------------------
    # 迁移
    # ------------------------------------------------------------------
    def start_migrate(self):
        from brand_ui import workspace_available
        if not workspace_available(self):
            return
        targets = [it for it in self.items
                   if it["id"] in self.checked
                   and self.info.get(it["id"], {}).get("status") in _MIGRATABLE]
        if not targets or self.working:
            return
        root = self._selected_root()
        if not root:
            self._toast("请先选择目标盘与目标根目录", WARN)
            return
        mc.save_target_root(root)          # 记住本次目标位置，下次自动带上
        total_b = sum(self.info[it["id"]].get("bytes", 0) for it in targets)
        if not self._confirm_dialog(targets, root, total_b):
            return
        self._run("migrate", targets, root)

    def start_restore(self):
        from brand_ui import workspace_available
        if not workspace_available(self):
            return
        targets = [it for it in self.items
                   if it["id"] in self.checked
                   and self.info.get(it["id"], {}).get("status") == "migrated"]
        if not targets or self.working:
            return
        names = "\n".join(f"    {it.get('icon')}  {it['name']}" for it in targets)
        if not messagebox.askyesno(
                "确认迁回 C 盘",
                "将把以下已迁移项目的数据迁回 C 盘原位\n"
                f"(需 C 盘有足够空间)：\n\n{names}\n\n"
                "过程同样自动校验，失败会保持联接不动。继续？",
                parent=self):
            return
        self._run("restore", targets, None)

    def _run(self, kind, targets, root):
        self.working = True
        self._cancel = False
        self.btn_migrate.configure(state="disabled")
        self.btn_restore.configure(state="disabled")
        self.btn_rescan.configure(state="disabled")
        self._select_all(None)
        self.prog.set(0.02)
        verb = " 迁移中" if kind == "migrate" else "迁回中"
        self.lbl_status.configure(text=f"{verb} 0/{len(targets)} 项…", text_color=WARN)
        threading.Thread(target=self._work_thread,
                         args=(kind, targets, root), daemon=True).start()
        self.after(80, self._poll)

    def _work_thread(self, kind, targets, root):
        total = len(targets)
        done_count = 0
        failed = []          # (名称, 错误, "locked"|"")
        for idx, it in enumerate(targets):
            if self._cancel:
                self.q.put(("finish", kind, done_count, total,
                            "已取消（已完成项保持不动）", failed))
                return

            def log(m, it=it):
                self.q.put(("log", f"[{it['name']}] {m}"))

            def progress(cur_src, done_f, total_f, done_b, total_b,
                         idx=idx, total=total, it=it):
                if total_b > 0 and done_b >= 0:
                    frac = done_b / total_b
                    detail = f"{format_size(done_b)}/{format_size(total_b)}"
                else:
                    frac = 1.0
                    detail = "…"
                self.q.put(("prog", (idx + min(1.0, frac)) / total,
                            f"[{idx + 1}/{total}] {it['name']} {detail}"))

            try:
                if kind == "migrate":
                    self.q.put(("log", f"── 开始迁移：{it['name']} ──"))
                    if it.get("kind") == "shell":
                        res = mc.unify_shell_item(
                            it, root, sub_name=it["name"],
                            auto_mkdir=self.var_auto.get(),
                            log=log, progress=progress,
                            cancel=lambda: self._cancel)
                        n_ren = len(res.get("renames", []))
                        extra = (f"，{n_ren} 个同名文件已重命名共存"
                                 if n_ren else "")
                        self.q.put(("log",
                                    f" {it['name']} 完成：释放 C 盘 "
                                    f"{format_size(res['bytes'])}"
                                    f"（{res['files']} 个文件）{extra}"))
                    else:
                        res = mc.migrate_item(it, root, log=log,
                                              progress=progress,
                                              cancel=lambda: self._cancel)
                        self.q.put(("log", f" {it['name']} 完成：释放 C 盘 "
                                           f"{format_size(res['bytes'])}"
                                           f"（{res['files']} 个文件）"))
                else:
                    self.q.put(("log", f"── 开始迁回：{it['name']} ──"))
                    mc.restore_item(it, log=log, progress=progress,
                                    cancel=lambda: self._cancel)
                    self.q.put(("log", f" {it['name']} 已迁回 C 盘原位"))
                done_count += 1
                self.q.put(("item_done", it["id"], kind))
            except mc.LockedError as e:
                failed.append((it["name"], str(e), "locked"))
                self.q.put(("log", f" [{it['name']}] {e}"))
                self.q.put(("item_failed", it["id"]))
            except mc.MigrateError as e:
                failed.append((it["name"], str(e), ""))
                self.q.put(("log", f" [{it['name']}] {e}"))
                self.q.put(("item_failed", it["id"]))
            except Exception as e:
                failed.append((it["name"], f"{type(e).__name__}: {e}", ""))
                self.q.put(("log", f" [{it['name']}] {type(e).__name__}: {e}"))
                self.q.put(("item_failed", it["id"]))
        # 逐项容错：单项失败不中断队列，最后汇总
        self.q.put(("finish", kind, done_count, total, None, failed))

    # ------------------------------------------------------------------
    # 消息泵
    # ------------------------------------------------------------------
    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                tag = msg[0]
                if tag == "item":
                    _, it, idx, total = msg
                    self._insert_row(it)
                    self.prog.set(min(0.9, 0.03 + 0.85 * (idx + 1) / max(1, total)))
                    self.lbl_status.configure(
                        text=f" 统计中 {idx + 1}/{total} · {it['name']}")
                elif tag == "prog":
                    _, frac, text = msg
                    self.prog.set(0.02 + 0.93 * min(1.0, frac))
                    self.lbl_status.configure(text=f" {text}", text_color=WARN)
                elif tag == "log":
                    self._log(msg[1])
                elif tag == "item_done":
                    _, iid, kind = msg
                    it = next((x for x in self.items if x["id"] == iid), None)
                    if it:
                        base = self.info.get(iid, {})
                        if kind == "migrate":
                            self.info[iid] = {"status": "migrated",
                                              "files": base.get("files", 0),
                                              "bytes": base.get("bytes", 0)}
                        else:
                            self.info[iid] = {"status": "clean",
                                              "files": base.get("files", 0),
                                              "bytes": base.get("bytes", 0)}
                        self._refresh_row(iid)
                        self._refresh_group(self.tree.parent(iid))
                    self._update_cards()
                elif tag == "item_failed":
                    _, iid = msg
                    it = next((x for x in self.items if x["id"] == iid), None)
                    if it:
                        base = self.info.get(iid, {})
                        self.info[iid] = {"status": mc.item_status(it),
                                          "files": base.get("files", 0),
                                          "bytes": base.get("bytes", 0)}
                        self._refresh_row(iid)
                        self._refresh_group(self.tree.parent(iid))
                elif tag == "icon":
                    _, iid, png = msg
                    try:
                        img = tk.PhotoImage(
                            data=base64.b64encode(png).decode("ascii"))
                        self._icons[iid] = img
                        if self.tree.exists(iid):
                            it = next((x for x in self.items
                                       if x["id"] == iid), None)
                            if it:
                                self.tree.item(iid, image=img, text=it["name"])
                    except Exception:
                        pass
                elif tag == "finish":
                    self._finish_work(msg)
                    return
                elif tag == "done":
                    self._finish_scan()
                    return
                elif tag == "error":
                    self._work_error(msg[1])
                    return
        except queue.Empty:
            pass
        if self.working:
            self.after(90, self._poll)

    def _finish_scan(self):
        self.working = False
        self.prog.set(1.0)
        self.btn_rescan.configure(state="normal", text=" 刷新状态")
        self._update_cards()
        self._update_buttons()
        self._render_tree()          # 分组排序：类别分组 + 组内体积降序
        clean = sum(1 for v in self.info.values() if v.get("status") == "clean")
        mig = sum(1 for v in self.info.values() if v.get("status") == "migrated")
        self.lbl_status.configure(
            text=f" 统计完成：{len(self.items)} 项（未迁移 {clean} · 已迁移 {mig}）"
                 f" · 点分组行整组勾选",
            text_color=OK)
        self._log(f" 统计完成：未迁移 {clean} 项 · 已迁移 {mig} 项")
        if not self.q.empty():       # 图标消息可能仍在队列，继续泵
            self.after(90, self._poll)
        # 列明已迁移项及其联接目标，避免「为什么显示已迁移」的困惑
        for it in self.items:
            if self.info.get(it["id"], {}).get("status") != "migrated":
                continue
            tgt = next((t for t in (mc.migrated_target_of(s)
                                    for s in it["sources_resolved"]) if t), "?")
            self._log(f"{it['name']} 早已迁移 ， {tgt}")

    def _finish_work(self, msg):
        kind, done, total, err = msg[1], msg[2], msg[3], msg[4]
        failed = msg[5] if len(msg) > 5 else []
        self.working = False
        if not err and not failed:
            self.prog.set(1.0)
        self.btn_rescan.configure(state="normal", text=" 刷新状态")
        self._update_buttons()
        self._update_cards()
        if err:                                  # 用户取消
            self.lbl_status.configure(text=f" {err}", text_color=WARN)
            self._log(f" {err}")
        elif failed:
            verb = "迁移" if kind == "migrate" else "迁回"
            n_lock = sum(1 for _n, _e, f in failed if f == "locked")
            head = (f" {verb}完成 {done}/{total} 项，"
                    f"失败 {len(failed)} 项"
                    + (f"（其中 {n_lock} 项因软件占用）" if n_lock else ""))
            self.lbl_status.configure(text=head + " · 详情见下方日志",
                                      text_color=WARN)
            self._log(head)
            for name, e, flag in failed:
                self._log(f"   {name}: {e}")
            if n_lock:
                self._log("  提示：被占用项请先关闭对应软件，再次勾选迁移即可"
                          "断点续传；其余项不受影响，数据均无损伤。")
        else:
            verb = "迁移" if kind == "migrate" else "迁回"
            self.lbl_status.configure(
                text=f" {verb}完成 {done}/{total} 项 · 原路径全部可用 · 数据校验通过",
                text_color=OK)
            self._log(f" {verb}流程全部完成。")
        if not self.q.empty():
            self.after(90, self._poll)

    def _work_error(self, text):
        self.working = False
        self.btn_rescan.configure(state="normal", text=" 刷新状态")
        self.lbl_status.configure(text=f" 扫描失败：{text}", text_color=ERR)
        self._log(f" 扫描失败：{text}")

    # ------------------------------------------------------------------
    # 确认弹窗 / 小工具
    # ------------------------------------------------------------------
    def _confirm_dialog(self, targets, root, total_b):
        lines = []
        for it in targets:
            size = format_size(self.info[it["id"]].get("bytes", 0))
            if it.get("kind") == "shell":
                lines.append(f"    {it.get('icon')}  {it['name']}"
                             f"（{size}）→ {os.path.join(root, it['name'])}")
            else:
                lines.append(f"    {it.get('icon')}  {it['name']}  ({size})")
        names = "\n".join(lines)
        auto_txt = ("将自动建立对应文件夹（桌面、下载、文档…）"
                    if self.var_auto.get()
                    else "未勾选自动建立：目标位置必须已存在对应文件夹")
        dlg = ctk.CTkToplevel(self)
        dlg.title("确认迁移")
        dlg.geometry("680x560")
        dlg.configure(fg_color=PANEL)
        dlg.attributes("-topmost", True)
        dlg.grab_set()
        box = ctk.CTkFrame(dlg, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=24, pady=20)
        ctk.CTkLabel(box, text=" 确认迁移以下项目？",
                     font=ctk.CTkFont(family=FONT, size=17, weight="bold"),
                     text_color=ACCENT).pack(anchor="w")
        txt = ctk.CTkTextbox(box, fg_color=CARD, text_color="#F0F4F7",
                             font=ctk.CTkFont(family=FONT, size=13))
        txt.pack(fill="both", expand=True, pady=12)
        txt.insert("1.0",
                   f"迁移到：{root}\n"
                   f"合计：{len(targets)} 项 · 约 {format_size(total_b)}\n"
                   f"{auto_txt}\n\n{names}\n\n"
                   "━━ 迁移过程（全自动，逐项执行）━━\n"
                   "  1. 复制到目标盘 ， 文件