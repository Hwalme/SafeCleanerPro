# -*- coding: utf-8 -*-
"""AppData 深度优化台：独立窗口。

- 扫描 AppData 下的**纯缓存**（浏览器/Electron/开发/系统/游戏）并按体积排序
- 另列 AppData 下的**大文件**供手动确认（默认不勾选）
- 保护闸门：Cookies/登录态/sqlite/AI 记忆/微信聊天数据一律不可清
- 清理复用 cleaner_core.clean_directory（内含免疫网校验），不另写删除逻辑
"""
import os
import queue
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk

import customtkinter as ctk

import deep_cache as dc
from cleaner_core import clean_directory, format_size

from ui_theme import BG, PANEL, CARD, ACCENT, OK, WARN, DIM, setup_popup


def _fmt_time(ts):
    if not ts:
        return "-"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return "-"


class DeepOptimizeWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        setup_popup(self, "AppData 深度优化台")
        self.geometry("1300x820")
        self.minsize(1120, 740)

        self.items = []          # 缓存项
        self.large = []          # 大文件项
        self.checked = set()     # 勾选的 key
        self.scanning = False
        self.cleaning = False
        self.q = queue.Queue()

        self._build()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    # ------------------------------------------------------------------
    # 界面
    # ------------------------------------------------------------------
    def _build(self):
        from ui_theme import style_dark_treeview
        style_dark_treeview(rowheight=28)
        from brand_ui import popup_header, button
        head = popup_header(self, "应用缓存", "查看 AppData 缓存与大文件，保留登录态、配置和 Agent 记忆。")
        self.btn_scan = button(head, "开始扫描", self.start_scan, True, width=140, height=40)
        self.btn_scan.pack(side="right", padx=(16, 0))

        # 汇总卡
        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill="x", padx=24, pady=(0, 8))
        self.card_total = self._card(cards, "可清理缓存", "0 B")
        self.card_items = self._card(cards, "命中项目", "0")
        self.card_large = self._card(cards, "大文件(≥100MB)", "0")
        self.card_sel = self._card(cards, "已选中", "0 B")

        # 进度
        self.prog = ctk.CTkProgressBar(self, height=3, progress_color=ACCENT)
        self.prog.pack(fill="x", padx=24, pady=(0, 6))
        self.prog.set(0)
        self.lbl_status = ctk.CTkLabel(self, text="点击「开始扫描」分析 AppData 缓存",
                                       font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
                                       text_color=WARN)
        self.lbl_status.pack(anchor="w", padx=24, pady=(0, 6))

        # 表格
        wrap = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=10)
        wrap.pack(fill="both", expand=True, padx=24, pady=(0, 6))
        cols = ("sel", "cat", "name", "size", "files", "mtime", "path")
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        heads = {"sel": "选择", "cat": "类别", "name": "项目", "size": "体积",
                 "files": "文件数", "mtime": "最近修改", "path": "路径"}
        widths = {"sel": 52, "cat": 110, "name": 210, "size": 92,
                  "files": 74, "mtime": 132, "path": 520}
        for c in cols:
            self.tree.heading(c, text=heads[c])
            anchor = "w" if c in ("cat", "name", "path") else "center"
            self.tree.column(c, width=widths[c], anchor=anchor, stretch=(c == "path"))
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        vs.pack(side="right", fill="y")
        hs = ttk.Scrollbar(wrap, orient="horizontal", command=self.tree.xview)
        self.tree.configure(xscrollcommand=hs.set)
        hs.pack(side="bottom", fill="x")
        self.tree.pack(fill="both", expand=True, padx=8, pady=8)
        self.tree.tag_configure("large", foreground="#ECA0A6")
        self.tree.tag_configure("sel", foreground="#91D5B6")
        self.tree.bind("<ButtonRelease-1>", self._on_click)

        # 底部操作条
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(fill="x", padx=24, pady=(0, 14))
        ctk.CTkButton(bar, text=" 全选缓存项", width=120, height=30, fg_color="#294652",
                      hover_color="#395C68", command=lambda: self._select_all(True)).pack(side="left")
        ctk.CTkButton(bar, text=" 全不选", width=100, height=30, fg_color="#1D252E",
                      hover_color="#2A3541", command=lambda: self._select_all(False)).pack(side="left", padx=8)
        ctk.CTkButton(bar, text=" 查看明细", width=110, height=30, fg_color="#1D252E",
                      hover_color="#2A3541", command=self._show_detail).pack(side="left")
        self.btn_clean = ctk.CTkButton(bar, text=" 清理选中项", width=140, height=30,
                                       fg_color="#633A40", hover_color="#7A454D",
                                       command=self.clean_selected)
        self.btn_clean.pack(side="left", padx=8)
        self.btn_clean.configure(state="disabled")
        ctk.CTkLabel(bar, text="大文件：仅  可安全删 能勾选 ·  不建议删 = 程序本体/依赖/模型",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
                     text_color=DIM).pack(side="right")

    def _card(self, parent, title, value):
        f = ctk.CTkFrame(parent, fg_color="transparent", corner_radius=0, width=230, height=78)
        f.pack(side="left", fill="x", expand=True, padx=(0, 14))
        f.pack_propagate(False)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(family="Microsoft YaHei UI", size=11),
                     text_color=DIM).pack(pady=(8, 0))
        lbl = ctk.CTkLabel(f, text=value, font=ctk.CTkFont(family="Microsoft YaHei UI", size=26, weight="bold"),
                           text_color="#F0F4F7")
        lbl.pack()
        return lbl

    # ------------------------------------------------------------------
    # 扫描
    # ------------------------------------------------------------------
    def start_scan(self):
        from brand_ui import workspace_available
        if not workspace_available(self):
            return
        if self.scanning or self.cleaning:
            return
        self.scanning = True
        self.items = []
        self.large = []
        self.checked = set()
        self._clear_tree()
        self.btn_scan.configure(state="disabled", text="扫描中...")
        self.btn_clean.configure(state="disabled")
        self.lbl_status.configure(text=" 正在扫描 AppData 缓存目录...", text_color=WARN)
        self.prog.set(0.05)
        threading.Thread(target=self._scan_thread, daemon=True).start()
        self.after(80, self._poll)

    def _scan_thread(self):
        try:
            rules = dc.build_rules()
            total = len(rules)

            def emit(item):
                # 每条规则扫到有体积就立刻上屏（流式）
                self.q.put(("item", item))

            for idx, _name in enumerate(dc.scan_rules_stream(rules, emit=emit)):
                self.q.put(("prog", idx + 1, total, _name))
            large = dc.find_large_files(dc.scan_roots(), min_mb=100, limit=60)
            self.q.put(("large", large))
            self.q.put(("done",))
        except Exception as e:
            self.q.put(("error", str(e)))

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                tag = msg[0]
                if tag == "prog":
                    _, done, total, name = msg
                    self.prog.set(min(0.9, 0.05 + 0.7 * done / max(1, total)))
                    self.lbl_status.configure(text=f" 扫描中 {done}/{total} · {name}")
                elif tag == "item":
                    # 流式上屏：扫到一个就插入一行，并按体积重排
                    it = msg[1]
                    self.items.append(it)
                    self._insert_item(it)
                    self._update_cards()
                elif tag == "large":
                    self.large = msg[1]
                    self._render()
                elif tag == "done":
                    self._finish_scan()
                    return
                elif tag == "error":
                    self.scanning = False
                    self.btn_scan.configure(state="normal", text=" 开始深度体检")
                    self.lbl_status.configure(text=f" 扫描失败：{msg[1]}", text_color="#ECA0A6")
                    return
        except queue.Empty:
            pass
        if self.scanning:
            self.after(90, self._poll)

    def _finish_scan(self):
        self.scanning = False
        self._render()
        self.btn_scan.configure(state="normal", text=" 重新体检")
        self.btn_clean.configure(state="normal" if self.checked else "disabled")
        total = sum(i["size"] for i in self.items)
        self.prog.set(1.0)
        self.lbl_status.configure(
            text=f" 体检完成：可清缓存 {format_size(total)} · 命中 {len(self.items)} 项 · "
                 f"大文件 {len(self.large)} 个（默认不勾选）",
            text_color=OK)

    def _insert_item(self, it):
        """流式插入一行：插到体积比它小的第一行之前（保持降序）。"""
        key = "c:" + it["id"]
        pos = ""
        try:
            for iid in self.tree.get_children():
                if not iid.startswith("c:"):
                    continue
                other = next((x for x in self.items if "c:" + x["id"] == iid), None)
                if other is not None and other["size"] < it["size"]:
                    pos = iid
                    break
        except Exception:
            pos = ""
        self.tree.insert("", "end" if not pos else self.tree.index(pos), iid=key,
                         tags=("normal",), values=(
                             "已选" if key in self.checked else "选择", it["cat_name"], it["name"], format_size(it["size"]),
                             it["files"], _fmt_time(it["mtime"]),
                             it["paths"][0]["path"] if it["paths"] else ""))

    def _clear_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

    def _render(self):
        self._clear_tree()
        for it in self.items:
            key = "c:" + it["id"]
            self.tree.insert("", "end", iid=key, tags=("normal",), values=(
                "已选" if key in self.checked else "选择", it["cat_name"], it["name"], format_size(it["size"]),
                it["files"], _fmt_time(it["mtime"]),
                it["paths"][0]["path"] if it["paths"] else ""))
        for idx, f in enumerate(self.large):
            key = f"f:{idx}"
            grade = f.get("grade", "unknown")
            label = {"safe": " 可安全删", "unknown": " 自行判断",
                     "unsafe": " 不建议删"}.get(grade, " 自行判断")
            tags = ("large",) if grade != "safe" else ("normal",)
            self.tree.insert("", "end", iid=key, tags=tags, values=(
                "已选" if key in self.checked else "选择" if grade == "safe" else "—", label, os.path.basename(f["path"]), format_size(f["size"]),
                1, _fmt_time(f["mtime"]), f["path"]))
        self._update_cards()

    def _update_cards(self):
        total = sum(i["size"] for i in self.items)
        self.card_total.configure(text=format_size(total))
        self.card_items.configure(text=str(len(self.items)))
        self.card_large.configure(text=str(len(self.large)))
        sel = 0
        for k in self.checked:
            if k.startswith("c:"):
                it = next((x for x in self.items if "c:" + x["id"] == k), None)
                if it:
                    sel += it["size"]
            else:
                idx = int(k.split(":")[1])
                if idx < len(self.large):
                    sel += self.large[idx]["size"]
        self.card_sel.configure(text=format_size(sel))
        self.btn_clean.configure(state="normal" if self.checked and not self.scanning and not self.cleaning else "disabled")

    # ------------------------------------------------------------------
    # 交互
    # ------------------------------------------------------------------
    def _on_click(self, _e=None):
        sel = self.tree.selection()
        if not sel:
            return
        key = sel[0]
        if key.startswith("f:") and key not in self.checked:
            idx = int(key.split(":")[1])
            if idx < len(self.large):
                grade = self.large[idx].get("grade", "unknown")
                if grade != "safe":
                    self.lbl_status.configure(
                        text=" 该文件属于程序本体/依赖/模型，删除会破坏运行环境，不可勾选",
                        text_color="#ECA0A6")
                    return
        if key in self.checked:
            self.checked.discard(key)
            self.tree.set(key, "sel", "选择")
        else:
            self.checked.add(key)
            self.tree.set(key, "sel", "已选")
        self._update_cards()

    def _select_all(self, on):
        self.checked = set()
        if on:
            for it in self.items:
                if it.get("risk") == "manual":
                    continue    # 手动确认档不随「全选」勾上
                self.checked.add("c:" + it["id"])
            # 只自动选「判定为可安全删」的大文件
            for idx, f in enumerate(self.large):
                if f.get("grade") == "safe":
                    self.checked.add(f"f:{idx}")
        for iid in self.tree.get_children():
            self.tree.set(iid, "sel", "已选" if iid in self.checked else "选择")
        self._update_cards()

    def _show_detail(self):
        sel = self.tree.selection()
        if not sel:
            return
        key = sel[0]
        lines = []
        if key.startswith("c:"):
            it = next((x for x in self.items if "c:" + x["id"] == key), None)
            if not it:
                return
            lines.append(f"{it['name']}  ·  {format_size(it['size'])}  ·  {it['files']} 个文件")
            lines.append("说明：" + it.get("desc", ""))
            lines.append("")
            for p in sorted(it["paths"], key=lambda x: -x["size"]):
                lines.append(f"  {format_size(p['size']):>10}  {p['files']:>6} 个  {p['path']}")
        else:
            idx = int(key.split(":")[1])
            if idx >= len(self.large):
                return
            f = self.large[idx]
            lines.append(f"大文件：{f['path']}")
            lines.append(f"体积：{format_size(f['size'])}   修改时间：{_fmt_time(f['mtime'])}")
        win = ctk.CTkToplevel(self)
        win.title("明细")
        win.geometry("900x520")
        win.configure(fg_color=BG)
        box = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Consolas", size=12), fg_color=PANEL)
        box.pack(fill="both", expand=True, padx=12, pady=12)
        box.insert("1.0", "\n".join(lines))
        box.configure(state="disabled")

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------
    def clean_selected(self):
        from brand_ui import workspace_available
        if not workspace_available(self):
            return
        if self.cleaning or self.scanning:
            return
        if not self.checked:
            self.lbl_status.configure(text=" 未选中任何项目", text_color=WARN)
            return
        targets = []
        for k in self.checked:
            if k.startswith("c:"):
                it = next((x for x in self.items if "c:" + x["id"] == k), None)
                if it:
                    targets += [p["path"] for p in it["paths"]]
            else:
                idx = int(k.split(":")[1])
                if idx < len(self.large):
                    targets.append(self.large[idx]["path"])
        if not targets:
            return
        total = 0
        for k in self.checked:
            if k.startswith("c:"):
                it = next((x for x in self.items if "c:" + x["id"] == k), None)
                if it:
                    total += it["size"]
            else:
                idx = int(k.split(":")[1])
                if idx < len(self.large):
                    total += self.large[idx]["size"]
        try:
            import tkinter.messagebox as mb
            if not mb.askyesno("确认清理",
                               f"即将清理 {len(self.checked)} 项，预计释放 {format_size(total)}。\n\n"
                               f"仅清理缓存类文件；登录态、配置、数据库与 AI 记忆不会被删除。\n\n确定继续？"):
                return
        except Exception:
            pass

        self.cleaning = True
        self.btn_clean.configure(state="disabled", text="清理中...")
        self.btn_scan.configure(state="disabled")
        self.lbl_status.configure(text=f" 正在清理 {len(targets)} 个目标...", text_color=WARN)
        self.prog.set(0)
        self._targets = targets
        self._done_n = 0
        self._freed = 0
        threading.Thread(target=self._clean_thread, args=(targets,), daemon=True).start()
        self.after(90, self._poll_clean)

    def _clean_thread(self, targets):
        freed = [0]
        for idx, p in enumerate(targets):
            try:
                if os.path.isdir(p):
                    got = clean_directory(p, log_callback=None)
                    if isinstance(got, (int, float)):
                        freed[0] += got
                elif os.path.isfile(p):
                    try:
                        sz = os.path.getsize(p)
                        os.remove(p)
                        freed[0] += sz
                    except Exception:
                        pass
            except Exception:
                pass
            try:
                self.q.put(("cprog", idx + 1, len(targets), freed[0], p))
            except Exception:
                pass
        self.q.put(("cdone", freed[0], len(targets)))

    def _poll_clean(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "cprog":
                    _, done, total, freed, p = msg
                    self.prog.set(done / max(1, total))
                    self.lbl_status.configure(
                        text=f" 清理中 {done}/{total} · 已释放 {format_size(freed)} · {os.path.basename(p)}")
                elif msg[0] == "cdone":
                    self._finish_clean(msg[1])
                    return
                elif msg[0] == "error":
                    self.cleaning = False
                    self.btn_clean.configure(state="normal" if self.checked else "disabled", text="清理选中项")
                    self.btn_scan.configure(state="normal")
                    self.lbl_status.configure(text=f" 清理失败：{msg[1]}", text_color="#ECA0A6")
                    return
        except queue.Empty:
            pass
        if self.cleaning:
            self.after(100, self._poll_clean)

    def _finish_clean(self, freed):
        self.cleaning = False
        self.btn_clean.configure(state="normal" if self.checked else "disabled", text="清理选中项")
        self.btn_scan.configure(state="normal")
        self.prog.set(1.0)
        self.lbl_status.configure(text=f" 清理完成：释放 {format_size(freed)}", text_color=OK)
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass
        if getattr(self.master_app, "append_log", None):
            try:
                self.master_app.append_log(f">>> AppData 深度优化完成，释放 {format_size(freed)}")
            except Exception:
                pass
        # 清理后自动复扫，更新真实剩余
        self.after(400, self.start_scan)
