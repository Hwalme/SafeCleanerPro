# -*- coding: utf-8 -*-
"""SafeCleaner Pro - 终极安全进化版 (v3.9.7)

源码丢失后依据原始字节码(main.pyc)重建：CPython 3.12 的 dis 反汇编给出了
全部函数名/行号/参数签名/字符串常量/控制流，见 client_app/_recover/。

与原版一致的功能：RSA 授权校验 + 双 HWID 回退、SplashScreen 启动动画、
查重台入口、目标磁盘选择、排序与分类分组、全选/全不选、页脚、检查更新、
扫描时保护个人文件、单按钮状态机(btn_action)。

同时保留启动性能修复：列表行按需创建（见 ROWS_PER_TICK）。
"""
import os
import sys
import base64
import time
import threading
import json
import io
from queue import SimpleQueue, Empty
import urllib.request
import urllib.parse
import customtkinter as ctk

from hwid_utils import get_hwid
from lock_store import load_locks, save_locks
from cleaner_core import (
    get_supported_apps, get_size, format_size, clean_directory,
    obfuscate_path, get_resolved_paths, get_logical_drives, get_app_drives
)
from ui_theme import (
    F, warm_emoji_glyphs, build_app_row, build_ui, show_auth_dialog,
    app_icon_path,
    show_risk_confirmation, show_file_viewer, show_protection_list, show_final_report,
    show_unlock_confirm, show_item_detail, style_row_badge,
    UI_FAMILY, MONO_FAMILY,
    ICON_W, ICON_H, EMOJI_LABEL_W, animate_row_progress, scroll_row_into_view,
)

import ctypes
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

ctk.set_widget_scaling(1.0)
ctk.set_window_scaling(1.0)
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")
from brand_ui import install_theme
install_theme()

CURRENT_VERSION = "3.9.14"

PUBLIC_KEY_PEM = """-----BEGIN PUBLIC KEY-----
MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEAtUqIHJXNmIG3kIcQo+I8
8PvV4IPQUcEHf7irMvgegIF4y74qrZX3VPCCzIHTOquUYq0abI5iciHuGFcjf1Y5
riB4czvUldEOht2cz8pv3Btv/LI8mpTTn3MIM4zx9lpZxHHskOhowmset9/JSsOc
Ouhaj+hjIKLdmHS5UPGx/Zk+C14wrC04+3QEolPPvz9w8DiAzU5Pr6esQh88isZf
26sW8v4UkLLeKYPdiSVtYTSEiNnuO0i6Ji2z6cRiudo/0bGkCk012TSy88K9ytz2
6jW2gVVRZaTPdyVfVTZ3e3sRe5ScT/5lZMk9Kyf7+e1NUi+cN1/b30luI+Jlih5v
awIDAQAB
-----END PUBLIC KEY-----"""


def verify_license(hwid, license_key_b64):
    """RSA-2048 / PKCS1-v1_5 / SHA256 校验授权码与本机硬件 ID。"""
    from Crypto.PublicKey import RSA
    from Crypto.Signature import pkcs1_15
    from Crypto.Hash import SHA256
    try:
        public_key = RSA.import_key(PUBLIC_KEY_PEM)
        signature = base64.b64decode(license_key_b64)
        h = SHA256.new(hwid.encode('utf-8'))
        pkcs1_15.new(public_key).verify(h, signature)
        return True
    except Exception:
        return False


def get_license_paths():
    """授权文件的候选路径列表（当前目录优先，其次 LOCALAPPDATA）。"""
    paths = ['license.key']
    appdata_local = os.environ.get('LOCALAPPDATA')
    if appdata_local:
        app_dir = os.path.join(appdata_local, 'SafeCleanerPro')
        paths.append(os.path.join(app_dir, 'license.key'))
    return paths


def load_license_key():
    """读取已保存的授权码，返回 (key, path) 或 (None, None)。"""
    for p in get_license_paths():
        if not os.path.exists(p):
            continue
        with open(p, 'r') as f:
            key = f.read().strip()
            if key:
                return (key, p)
    return (None, None)


def save_license_key(key):
    """保存授权码到首选路径。"""
    p = get_license_paths()[0]
    try:
        d = os.path.dirname(p)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(p, 'w') as f:
            f.write(key)
        return True
    except Exception:
        return False


class SafeCleanerApp(ctk.CTk):
    # ------------------------------------------------------------------
    # 列表行按需创建（启动性能修复）
    #
    # 启动时一次性建 64 行意味着约 1,400 个控件，Tk 首次绘制它们实测要
    # 21,172 ms 才能看到窗口（代码早已跑完，界面却卡着）。分批"创建"无效：
    # 绘制总是覆盖已建好的全部控件。
    #
    # 因此列表初始为空，首次扫描时才逐批建行。
    #   启动即建全部行 : 21,172 ms 才画出窗口
    #   按需建行       :  4,535 ms 才画出窗口
    #
    # ROWS_PER_TICK 决定最长卡顿，真实 mainloop 下实测（最坏间隔）：
    #   1->840ms, 2->350ms, 4->639ms, 8->1145ms，中位数均约 20ms。
    # ------------------------------------------------------------------
    ROWS_PER_TICK = 2

    def __init__(self):
        super().__init__()

        self.title(f"PPSAI Cleaner · v{CURRENT_VERSION}")
        self.geometry("1380x860")
        self.minsize(1120, 740)
        self.resizable(True, True)
        ico = app_icon_path()
        if ico:
            try:
                self.iconbitmap(ico)
                self.after(250, lambda: self.iconbitmap(ico))
            except Exception:
                pass

        # State variables
        self.apps_data = get_supported_apps()
        self.sizes = {app["id"]: 0 for app in self.apps_data}
        self.total_scanned_bytes = 0
        self.total_immune_bytes = 0
        self.total_cleaned_bytes = 0
        # 双阶段统计：安全/深度分桶（不含锁定项），锁定项单独计入手动上锁桶
        self.safe_bytes = 0
        self.risk_bytes = 0
        self.locked_user_bytes = 0
        self.freed_safe = 0
        self.freed_risk = 0
        # 用户手动上锁（跨启动持久记忆）
        self.locked_ids = load_locks()
        # 透明化：保护清单分项（系统免疫/手动上锁）与文件清单缓存（查看文件秒开）
        self.immune_items = {}    # {项目名: 字节数}
        self.locked_items = {}    # {项目名: 字节数}
        self.file_cache = {}      # {app_id: [(path, size), ...]}
        self.skipped_files = set()   # Set of files skipped by details toggles
        self.app_checkbox_vars = {}
        # 细分管理与可选状态：
        #   selection_state  行勾选意图（列表重建后恢复用户选择）
        #   subpath_choices  每条细分路径的可选状态 {app_id: {pattern_lower: bool}}
        self.selection_state = {}
        self.subpath_choices = {}
        self._subpath_panel = None
        self.ui_state = "pre_scan"
        # 双线状态：safe/risk 各自 idle -> scanning -> ready -> cleaning -> done
        self.safe_state = "idle"
        self.risk_state = "idle"
        self.current_view = "safe"   # 列表当前显示的安全/深度项目
        self.log_queue = []
        self._ui_events = SimpleQueue()
        self.after(25, self._drain_ui)

        # 目标磁盘（跳过 A/B 软驱）
        self.detected_drives = []
        for d in get_logical_drives():
            letter = d[0].upper()
            if letter in ("A", "B"):
                continue
            self.detected_drives.append(letter)
        self.drive_vars = {}
        for letter in self.detected_drives:
            self.drive_vars[letter] = ctk.IntVar(value=1 if letter == "C" else 0)

        self.after(2000, self.check_for_updates)

    # ------------------------------------------------------------------
    # 日志与进度
    # ------------------------------------------------------------------
    def _post_ui(self, callback, *args):
        """Workers enqueue events without touching Tcl/Tk."""
        self._ui_events.put((callback, args))

    def _drain_ui(self):
        for _ in range(40):
            try:
                callback, args = self._ui_events.get_nowait()
            except Empty:
                break
            try:
                callback(*args)
            except Exception:
                self.report_callback_exception(*sys.exc_info())
        self.after(25, self._drain_ui)

    def append_log(self, message):
        from collections import deque
        if not hasattr(self, "log_history"):
            self.log_history = deque(maxlen=500)
        self.log_history.append(str(message))
        self.log_queue.append(message)

    @staticmethod
    def _truncate_log(text, limit=38):
        """单行截断：控制条第二行约 600px 可显示 ~38 个中文字符，超长以 … 收尾。"""
        text = " ".join(str(text).split())
        return text if len(text) <= limit else text[: limit - 1] + "…"

    def flush_logs(self):
        """日志台已取消：最新一行刷到控制条滚动文本（无底色），其余仅入队保留。"""
        try:
            lbl = getattr(self, "lbl_progress_info", None)
            status_locked = getattr(self, "_status_line_locked", False)
            # 锁定期间（扫描/清理状态行显示中）不消费队列，日志积压待解锁后展示
            if lbl is not None and not status_locked and self.log_queue:
                latest = self.log_queue[-1]
                self.log_queue = []
                color = "#91D5B6" if "[]" in latest else "#E7BA7A" \
                    if not latest.startswith(">>>") else "#B1ECF7"
                try:
                    lbl.configure(text=self._truncate_log(latest), text_color=color)
                except Exception:
                    pass
        except Exception:
            pass
        self.after(80, self.flush_logs)

    def update_progress(self, val):
        self.progress_bar.set(val)

    def make_clickable(self, widget, callback):
        """让标签（及其子控件）可点击：手型光标 + 左键回调。"""
        widget.configure(cursor="hand2")
        widget.bind("<Button-1>", lambda e: callback())
        for child in widget.winfo_children():
            child.configure(cursor="hand2")
            child.bind("<Button-1>", lambda e: callback())

    def open_url(self, url):
        """用 explorer 打开 URL，失败则回退 webbrowser。"""
        try:
            import subprocess
            subprocess.Popen(f'explorer "{url}"', shell=True)
        except Exception:
            try:
                import webbrowser
                webbrowser.open(url)
            except Exception:
                pass

    def open_dedup(self):
        from brand_ui import open_tool
        open_tool(self, "dedup")


    def open_memory_migrate(self):
        from brand_ui import open_tool
        open_tool(self, "migrate")


    def manual_check_update(self):
        self.btn_check_update.configure(text="正在检查…", state="disabled")
        self.append_log(">>> 正在连接云端服务器检测版本更新...")

        def do_check():
            try:
                api_url = f"https://ppsai.chat/api/check_update?version={CURRENT_VERSION}"
                req = urllib.request.Request(api_url, headers={"User-Agent": "SafeCleanerPro"})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode("utf-8"))

                def on_result():
                    self.btn_check_update.configure(text="检查更新", state="normal")
                    if data.get("has_update"):
                        self.append_log(f">>> 发现新版本 v{data['latest_version']}！正在弹出升级窗口...")
                        self.show_update_dialog(data)
                        return
                    self.append_log(f">>> 当前版本 v{CURRENT_VERSION} 已是最新版本，无需更新。")

                self._post_ui(on_result)
            except Exception:
                def on_error():
                    self.btn_check_update.configure(text="检查更新", state="normal")
                    self.append_log(">>> 版本检查失败：网络连接异常或服务器未响应。")

                self._post_ui(on_error)

        threading.Thread(target=do_check, daemon=True).start()

    # ------------------------------------------------------------------
    # 磁盘筛选与列表构建
    # ------------------------------------------------------------------
    def get_selected_drives(self):
        """返回当前勾选的盘符集合。"""
        return {letter for letter, var in self.drive_vars.items() if var.get() == 1}

    def get_filtered_apps(self, selected_drives=None):
        """只返回路径位于至少一个已选磁盘上的项目。

        selected_drives：后台扫描线程应传入主线程预先读取的结果，
        避免跨线程读 Tk 变量。

        注意：这里只做盘符过滤，是**扫描池/清理池/全选**的数据源。
        绝不能按大小过滤 —— 扫描前 sizes 全为 0，一过滤扫描池就被清空
        （Round M 曾因此让深度扫描扫到 0 项，必须保持纯净）。
        列表显示的 0 大小隐藏由 render_scroll_list 的显示层单独处理。
        """
        if selected_drives is None:
            selected = self.get_selected_drives()
        else:
            selected = selected_drives
        if not selected:
            return []
        filtered = []
        for app in self.apps_data:
            if not (get_app_drives(app) & selected):
                continue
            filtered.append(app)
        return filtered

    def on_drive_changed(self):
        """A changed scope invalidates findings; cleaning always follows a fresh scan."""
        from brand_ui import busy
        if busy(self):
            return
        self.safe_state = self.risk_state = "idle"
        self.safe_bytes = self.risk_bytes = self.total_immune_bytes = self.locked_user_bytes = 0
        self.sizes = {app["id"]: 0 for app in self.apps_data}
        self.file_cache = {}
        self.immune_items = {}
        self.locked_items = {}
        self.update_stat_cards()
        self.render_scroll_list()
        selected = self.get_selected_drives()
        self._status_line_locked = True
        self.lbl_progress_info.configure(
            text="扫描范围已更新，请重新扫描。" if selected else "请至少选择一个磁盘。",
            text_color="#A3AFBD" if selected else "#E7BA7A")
        self._set_buttons()


    def select_all_apps(self):
        for app in self.get_filtered_apps():
            if app["immune"]:
                continue
            var = self.app_checkbox_vars.get(app["id"])
            if not var:
                continue
            var.set(1)
            # tk.Checkbutton.select() 不触发 command → 显式同步勾选记忆，
            # 否则列表重建（排序/扫描后）会回退到旧选择
            self.selection_state[app["id"]] = 1
        for chk in self.app_checkboxes.values():
            try:
                chk.select()
            except Exception:
                pass

    def deselect_all_apps(self):
        for app in self.get_filtered_apps():
            if app["immune"]:
                continue
            var = self.app_checkbox_vars.get(app["id"])
            if not var:
                continue
            var.set(0)
            self.selection_state[app["id"]] = 0
        for chk in self.app_checkboxes.values():
            try:
                chk.deselect()
            except Exception:
                pass

    def _pump_rows(self):
        """逐批建行，每批之间交还事件循环以便绘制（性能修复）。

        队列项为 ("h", text, color, pady) 分组标题 或 ("r", app) 数据行。
        标题也入队列：它同样含 emoji，会触发 Tk 字形测量。
        """
        self._render_job = None
        built = 0
        while self._row_queue and built < self.ROWS_PER_TICK:
            item = self._row_queue.pop(0)
            try:
                if item[0] == "h":
                    _, text, color, pady = item
                    ctk.CTkLabel(
                        self.scroll_frame,
                        text=text,
                        font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
                        text_color=color,
                    ).pack(anchor="w", padx=10, pady=pady)
                else:
                    build_app_row(self, item[1], self._row_index)
                    self._row_index += 1
            except Exception:
                pass
            built += 1

        if self._row_queue:
            try:
                self.scroll_frame.update_idletasks()
            except Exception:
                pass
            self._render_job = self.after(1, self._pump_rows)
        else:
            self._finish_rows()

    def _show_placeholder(self):
        from brand_ui import show_placeholder
        show_placeholder(self)


    def _hide_placeholder(self):
        try:
            if getattr(self, "_placeholder", None) is not None:
                self._placeholder.destroy()
                self._placeholder = None
        except Exception:
            pass

    def build_rows_on_demand(self):
        """按需建行。幂等，可从任意处理函数安全调用。"""
        if getattr(self, "_rows_started", False):
            return
        self._rows_started = True
        self._hide_placeholder()
        self._row_queue = list(self.get_filtered_apps())
        self._row_index = 0
        self._pump_rows()

    def _finish_rows(self):
        """所有行就绪后，确定滚动区域。"""
        # 隐藏提示：默认视图下 0 大小项被折叠，告知数量与查看方式
        try:
            if getattr(self, "_hidden_zero_count", 0) > 0 and not getattr(self, "show_all_items", False):
                ctk.CTkLabel(
                    self.scroll_frame,
                    text=f"已隐藏 {self._hidden_zero_count} 个空项目",
                    font=ctk.CTkFont(family="Microsoft YaHei UI", size=12),
                    text_color="#8795A5",
                ).pack(pady=(6, 14))
        except Exception:
            pass
        try:
            self.scroll_frame.update_idletasks()
            canvas = self.scroll_frame._parent_canvas
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.yview_moveto(0.0)
        except Exception:
            pass

    def render_scroll_list(self):
        """按当前排序/筛选重建滚动列表（惰性：只排队列，由 _pump_rows 逐批建）。

        v3.9.13 性能重写：
        1) 展示数据源不再按盘符过滤 —— 盘符只决定扫描/清理范围；
           点盘符零重建（此前每点一次盘符就全量销毁+重建 1400 个控件）；
        2) 销毁旧行改为分批（每拍 8 个）：数千 tk 窗口同步 destroy 会把
           界面冻结数秒且无任何提示 —— 「扫描/清理完成瞬间卡死无提示」
           的主因就是这条同步销毁循环。
        """
        try:
            if self._render_job is not None:
                try:
                    self.after_cancel(self._render_job)
                except Exception:
                    pass
                self._render_job = None

            old_widgets = list(self.scroll_frame.winfo_children())
            self._placeholder = None
            self.app_rows = {}
            self.app_checkboxes = {}
            self.app_checkbox_vars = {}
            self._subpath_panel = None
            job = getattr(self, "_scroll_job", None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except Exception:
                    pass
                self._scroll_job = None
            # 细分面板随列表销毁；selection_state / subpath_choices 保留（用户选择跨重建记忆）

            mode = "category"
            try:
                mode = self.sort_mode_var.get()
            except Exception:
                pass

            # 展示 = 全部项目 + 视图过滤；盘符过滤只作用于扫描/清理池（get_filtered_apps）
            apps = list(self.apps_data)
            # 双阶段互斥展示：安全视图只列安全项(+系统免疫)，深度视图只列风险项。
            # 上锁项保留在各自视图中（锁定样式，无法勾选），便于查看与解锁。
            view = getattr(self, "current_view", "safe")
            if view == "protected":
                apps = [a for a in apps if a["immune"] or a["id"] in self.locked_ids]
                view_banner = "保护中的项目"
            elif view == "risk":
                apps = [a for a in apps
                        if not a["immune"] and a.get("risk_level") == "risk"]
                view_banner = ("深度项目 · 默认不选中")
            else:
                apps = [a for a in apps
                        if a["immune"] or a.get("risk_level") == "safe"]
                view_banner = ("缓存、日志与临时文件")
            # Round M：默认只显示「扫出来有内容」的垃圾项（0 大小/未扫描隐藏）。
            # 只能在**显示层**过滤，且**扫描/清理进行中不过滤** —— 扫描刚开始时
            # sizes 还没写入（全为 0），此时过滤会让列表瞬间清空。
            self._hidden_zero_count = 0
            show_all = getattr(self, "show_all_items", False)
            busy = (getattr(self, "safe_state", "") in ("scanning", "cleaning")
                    or getattr(self, "risk_state", "") in ("scanning", "cleaning"))
            query = self.search_var.get().strip().casefold() if hasattr(self, "search_var") else ""
            if query:
                apps = [a for a in apps if query in a["name"].casefold()]
            if not show_all and not busy and view != "protected":
                visible = [a for a in apps if self.sizes.get(a["id"], 0) > 0]
                self._hidden_zero_count = len(apps) - len(visible)
                apps = visible
            queue = []

            if mode == "size":
                apps = sorted(apps, key=lambda a: self.sizes.get(a["id"], 0), reverse=True)
                for a in apps:
                    queue.append(("r", a))
            else:
                groups = [
                    (["system"], "Windows 系统", "#8CDEEF"),
                    (["app", "adobe"], "应用与创意工具", "#295443"),
                    (["chat"], "通讯与协作", "#E7BA7A"),
                    (["dev", "ai"], "开发与 AI 工具", "#A3AFBD"),
                ]
                for types, title, color in groups:
                    matched = [a for a in apps if a.get("type", "app") in types]
                    if not matched:
                        continue
                    queue.append(("h", title, "#A3AFBD", (18, 6)))
                    for a in matched:
                        queue.append(("r", a))

            if not apps:
                queue = []
            self._row_queue = queue
            self._row_index = 0
            self._rows_started = True

            # 先分批销毁旧行，销毁完成后再进入建行（避免新旧行视觉重复）
            self._render_job = self.after(
                1, lambda: self._teardown_old_rows(old_widgets))
        except Exception:
            pass

    def _teardown_old_rows(self, old):
        """分批销毁旧行（每拍 8 个）：销毁完转入 _pump_rows 或占位符。"""
        self._render_job = None
        for w in old[:8]:
            try:
                w.destroy()
            except Exception:
                pass
        del old[:8]
        if old:
            self._render_job = self.after(1, lambda: self._teardown_old_rows(old))
            return
        if not self._row_queue:
            self._show_placeholder()
            self._finish_rows()
            return
        self._pump_rows()

    # ------------------------------------------------------------------
    # 界面
    # ------------------------------------------------------------------
    def build_ui(self):
        """构建主界面（实现在 ui_theme，避免单脚本超过 Pyarmor 试用版上限）。"""
        build_ui(self, CURRENT_VERSION)

    # ------------------------------------------------------------------
    # 主操作状态机（安全线 btn_action / 深度线 btn_deep 双按钮独立）
    #   idle -> scanning -> ready(显示"xx清理") -> cleaning -> done(重新扫描)
    # ------------------------------------------------------------------
    def _other_busy(self, tier):
        """另一条线正在扫描/清理时返回 True（同一时刻只允许一条线运行）。"""
        other = self.risk_state if tier == "safe" else self.safe_state
        return other in ("scanning", "cleaning")

    def _set_buttons(self):
        from brand_ui import sync_actions
        sync_actions(self)


    def on_action_click(self):
        """安全线按钮：扫描 -> 安全清理 -> 重新扫描。"""
        if self._other_busy("safe"):
            return
        if self.safe_state in ("idle", "done"):
            self.start_scan("safe")
        elif self.safe_state == "ready":
            self.start_cleanup_flow("safe")

    def on_deep_click(self):
        """深度线按钮：扫描 -> 深度清理 -> 重新扫描。"""
        if self._other_busy("risk"):
            return
        if self.risk_state in ("idle", "done"):
            self.start_scan("risk")
        elif self.risk_state == "ready":
            self.start_cleanup_flow("risk")

    def _is_locked(self, app):
        return app["id"] in self.locked_ids

    def toggle_lock(self, app):
        """手动上锁/解锁：持久记忆 + 刷新统计与列表。"""
        from brand_ui import busy
        if busy(self):
            return
        app_id = app["id"]
        if app_id in self.locked_ids:
            self.locked_ids.discard(app_id)
            self.append_log(f" 已解锁保护: {app['name']}（可重新参与清理）")
        else:
            self.locked_ids.add(app_id)
            self.append_log(f" 已上锁保护: {app['name']}（永不参与清理，重启后保持）")
        save_locks(self.locked_ids)
        self.update_stat_cards()
        self.render_scroll_list()
        # 右侧详情面板正显示该项时同步刷新（锁定徽章/按钮互换）
        if getattr(self, "_detail_current", None) == app_id:
            show_item_detail(self, app_id)

    def unlock_immunity(self, app):
        """请求解除某项的系统免疫（免疫细项面板内发起）。

        硬底线：Agent 记忆免疫网（.gemini/antigravity、Cursor、Claude 等）内的
        项目不可解锁——这是内核级保护，任何 UI 操作都无效。
        其余免疫项弹红色警示确认后，降级为普通项参与扫描/清理。
        """
        from cleaner_core import is_agent_memory_path
        try:
            paths = app.get("paths", []) or []
            if any(is_agent_memory_path(str(p)) for p in paths):
                self.append_log(f" {app['name']} 位于 Agent 记忆免疫网，内核级保护不可解锁")
                self._show_toast(" Agent 记忆免疫网不可解锁", "#3D282E", "#ECA0A6")
                return
            show_unlock_confirm(self, app, self._do_unlock_immunity)
        except Exception:
            pass

    def _do_unlock_immunity(self, app):
        """确认后的免疫解除落地：降级 + 统计同步 + 列表重建。"""
        try:
            app_id = app["id"]
            app["immune"] = False
            if hasattr(self, "immune_apps") and app_id in getattr(self, "immune_apps", {}):
                self.immune_apps.pop(app_id, None)
            freed_imm = getattr(self, "immune_items", {}).pop(app["name"], 0)
            try:
                self.total_immune_bytes = max(0, self.total_immune_bytes - (freed_imm or 0))
            except Exception:
                pass
            self.append_log(f" 已解除系统免疫: {app['name']}（解锁后立即解除，重启后保持）")
            self.update_stat_cards()
            self.render_scroll_list()
            # 右侧详情面板正显示该项时同步刷新（解锁后徽章/按钮/勾选框变化）
            if getattr(self, "_detail_current", None) == app_id:
                show_item_detail(self, app_id)
            self._show_toast(f" 已解锁: {app['name']}", "#203B30", "#3C6D58")
        except Exception:
            pass

    def update_stat_cards(self):
        """左栏三卡片总数值 + 细分行（线程安全：只能在主线程调）。"""
        try:
            self.total_scanned_bytes = self.safe_bytes + self.risk_bytes
            self.total_cleaned_bytes = self.freed_safe + self.freed_risk
            locked_total = self.total_immune_bytes + self.locked_user_bytes
            self.lbl_scanned_val.configure(text=format_size(self.total_scanned_bytes))
            self.lbl_immune_val.configure(text=format_size(locked_total))
            self.lbl_cleaned_val.configure(text=format_size(self.total_cleaned_bytes))
            self.lbl_scanned_breakdown.configure(text=(
                f"安全扫描: {format_size(self.safe_bytes)}   "
                f"深度扫描: {format_size(self.risk_bytes)}"))
            self.lbl_immune_breakdown.configure(text=(
                f"系统免疫: {format_size(self.total_immune_bytes)}   "
                f"手动上锁: {format_size(self.locked_user_bytes)}"))
            self.lbl_cleaned_breakdown.configure(text=(
                f"安全清理: {format_size(self.freed_safe)}   "
                f"深度清理: {format_size(self.freed_risk)}"))
        except Exception:
            pass

    def start_scan(self, tier):
        """tier: 'safe' 安全扫描 / 'risk' 深度扫描。只列并只扫对应项目。"""
        from brand_ui import busy, tools_busy
        if busy(self) or tools_busy(self) or not self.get_selected_drives():
            return
        self.current_view = tier
        self._active_page = tier
        if tier == "safe":
            self.safe_state = "scanning"
            self.safe_bytes = 0
        else:
            self.risk_state = "scanning"
            self.risk_bytes = 0
            self.locked_user_bytes = 0
        self.total_immune_bytes = 0 if tier == "safe" else self.total_immune_bytes
        self._set_buttons()
        self.progress_bar.set(0)
        self._status_line_locked = False
        try:
            self.lbl_progress_info.configure(
                text=" 准备扫描...", text_color="#E7BA7A")
        except Exception:
            pass
        # 渐进式列表：扫描期间不再一次性构建全部行（781 行全量建行曾致
        # 严重卡顿与显示错乱）。清空列表，垃圾项在扫到的瞬间逐行出现，
        # 扫描完成后由 _ui_scan_done 渲染最终整理好的列表。
        try:
            if getattr(self, "_subpath_panel", None) is not None:
                self._subpath_panel.destroy()
        except Exception:
            pass
        self._subpath_panel = None
        self.app_rows = {}
        self.app_checkbox_vars = {}
        self.app_expand_btns = {}
        self._row_queue = []
        self._row_index = 0
        self._rows_started = False
        self._last_scan_row = None
        self._scan_found_bytes = 0
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self._scan_placeholder = ctk.CTkLabel(
            self.scroll_frame,
            text=" 正在扫描，垃圾项会在这里陆续出现…",
            font=F(UI_FAMILY, 13), text_color="#8795A5")
        self._scan_placeholder.pack(pady=40)

        # 主线程先取盘符（后台线程读 Tk 变量跨线程不安全）
        selected_drives = self.get_selected_drives()
        threading.Thread(target=self._scan_worker, args=(tier, selected_drives),
                         daemon=True).start()

    def _scan_worker(self, tier, selected_drives):
        try:
            self._scan_thread(tier, selected_drives)
        except Exception as error:
            message = str(error)
            self._post_ui(lambda: self._scan_failed(tier, message))

    def _scan_failed(self, tier, message):
        setattr(self, tier + "_state", "idle")
        self._status_line_locked = True
        self.lbl_progress_info.configure(text="扫描未完成，请重试或查看活动记录。", text_color="#ECA0A6")
        self.append_log("扫描未完成：" + message)
        self.render_scroll_list()
        self._set_buttons()

    def _scan_thread(self, tier, selected_drives=None):
        if selected_drives is None:
            selected_drives = self.get_selected_drives()
        drives_str = ", ".join(f"{d}:" for d in sorted(selected_drives))
        tier_name = "安全扫描" if tier == "safe" else "深度扫描"
        self.append_log(f"启动 PPSAI Cleaner 扫描[{tier_name}]...")
        self.append_log(f">>> 目标磁盘: [{drives_str}]")
        self.append_log("受保护的记忆与工作区不会参与清理。")
        time.sleep(0.3)

        from cleaner_core import get_app_size

        # 只扫描当前阶段的项目：
        #   safe 阶段 = 安全项 + 系统免疫项（免疫容量在此阶段刷新）
        #   risk 阶段 = 风险项（含已被手动上锁的风险项，其容量计入"手动上锁"）
        def in_stage(app):
            if tier == "safe":
                return app["immune"] or app.get("risk_level") == "safe"
            return (not app["immune"]) and app.get("risk_level") == "risk"

        scan_apps = [a for a in self.get_filtered_apps(selected_drives)
                     if in_stage(a)]
        # 每轮扫描重置分项账本，保证卡片细分与保护清单弹窗数据同源
        self.file_cache = {}
        self.immune_items = {}
        self.locked_items = {}
        total_items = len(scan_apps) if scan_apps else 1
        for idx, app in enumerate(scan_apps):
            self.append_log(f'[*] 正在分析: {app["name"]}')

            # 先测体积；扫出垃圾才建文件清单（空项省一次全目录遍历）
            app_size = get_app_size(app)
            self.sizes[app["id"]] = app_size
            if not app["immune"] and not self._is_locked(app) and app_size > 0:
                from cleaner_core import scan_app_files
                file_list = scan_app_files(app, limit=800)
                self.file_cache[app["id"]] = file_list
                for filepath, _ in file_list:
                    if is_personal_file(filepath):
                        self.skipped_files.add(filepath)

            if app["immune"]:
                self.total_immune_bytes += app_size
                self.immune_items[app["name"]] = app_size
            elif self._is_locked(app):
                self.locked_user_bytes += app_size
                self.locked_items[app["name"]] = app_size
            elif app["risk_level"] == "safe":
                self.safe_bytes += app_size
            else:
                self.risk_bytes += app_size

            # 统计卡片每 15 项刷一次（781 项逐项刷会拖慢主线程）
            if idx % 15 == 0 or idx == total_items - 1:
                self._post_ui(self.update_stat_cards)
            self._post_ui(lambda i=idx, n=total_items, name=app["name"],
                       aid=app["id"], sz=app_size, a=app:
                       self._ui_scan_progress(i, n, name, aid, sz, a))
            time.sleep(0.01)

        if tier == "safe":
            self.append_log(f"\n[] 安全扫描完成！可放心清理: {format_size(self.safe_bytes)}")
            self.append_log(f" 自动免疫锁定大模型上下文与微信数据目录: {format_size(self.total_immune_bytes)}")
        else:
            self.append_log(f"\n[] 深度扫描完成！风险项目: {format_size(self.risk_bytes)}（默认不勾选，请确认后再清理）")
        self.append_log("═" * 46)
        done_text = (f" 安全扫描完成，可清理 {format_size(self.safe_bytes)}"
                     if tier == "safe" else
                     f" 深度扫描完成，发现风险项 {format_size(self.risk_bytes)}")
        self._post_ui(lambda: self._ui_scan_done(tier, done_text))

    def _ui_scan_progress(self, idx, total, name, app_id=None, size=0, app=None):
        """主线程侧扫描进度：进度条 + 状态行；扫出垃圾的项逐行出现。"""
        try:
            self.progress_bar.set((idx + 1) / max(1, total))
            self._status_line_locked = True
            self.lbl_progress_info.configure(
                text=self._truncate_log(f" 正在扫描: {name}  ({idx + 1}/{total})"))
            if app_id and size:
                # 渐进式建行：只建扫出垃圾的行（Round M 口径），零大小项不建
                self._scan_found_bytes = getattr(self, "_scan_found_bytes", 0) + size
                if app_id not in self.app_rows and app is not None:
                    build_app_row(self, app, getattr(self, "_row_index", 0))
                    self._row_index = getattr(self, "_row_index", 0) + 1
                info = self.app_rows.get(app_id)
                if info:
                    info["size"].configure(text="● " + format_size(size),
                                           fg="#E7BA7A", font=(MONO_FAMILY, 12, "bold"))
                ph = getattr(self, "_scan_placeholder", None)
                if ph is not None and ph.winfo_exists():
                    ph.configure(text=f" 扫描中… 已发现垃圾 {format_size(self._scan_found_bytes)}"
                                      f"（{idx + 1}/{total}）— 完成后自动整理列表")
        except Exception:
            pass

    def _ui_scan_done(self, tier, text):
        setattr(self, tier + "_state", "ready")
        """扫描完成强提示：提示音 + 浮动结果卡 + 报告弹窗 + 状态复位。"""
        try:
            self._status_line_locked = False
            self._last_scan_row = None
            self.update_stat_cards()
            self._set_buttons()
            self.render_scroll_list()
            self.lbl_progress_info.configure(
                text=f"{text}  → 请核对底部已选容量后继续",
                text_color="#91D5B6")
            self._show_toast(text, "#203B30", "#91D5B6")
            self.show_final_report("scan", tier)
        except Exception:
            pass

    def _show_toast(self, text, bg, fg, duration_ms=2600):
        self._status_line_locked = True
        self.lbl_progress_info.configure(text=text, text_color=fg)


    def on_clean_finished(self, clean_type, freed_bytes):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1.0)
        self.append_log(f"\n[] {clean_type} 清理完成，共释放 {format_size(freed_bytes)}。")
        self.append_log("═" * 46)
        if clean_type == "safe":
            self.freed_safe += freed_bytes
            self.safe_state = "done"
            done_text = f" 安全清理完成，共释放 {format_size(freed_bytes)}"
        else:
            self.freed_risk += freed_bytes
            self.risk_state = "done"
            done_text = f" 深度清理完成，共释放 {format_size(freed_bytes)}"
        self._status_line_locked = False
        self.update_stat_cards()
        self._set_buttons()
        self.render_scroll_list()
        try:
            self.lbl_progress_info.configure(
                text=f"{done_text}（可重新扫描）", text_color="#91D5B6")
        except Exception:
            pass
        self._show_toast(done_text, "#203B30", "#91D5B6")
        self.show_final_report("clean", clean_type, freed_bytes)

    # ------------------------------------------------------------------
    # 清理流程（含授权校验）
    # ------------------------------------------------------------------
    def start_cleanup_flow(self, clean_type):
        from brand_ui import selected_apps, busy, tools_busy
        if busy(self) or tools_busy(self) or not selected_apps(self, clean_type):
            return
        hwid = get_hwid()
        license_key, _ = load_license_key()

        valid = False
        active_hwid = hwid
        if license_key:
            if verify_license(hwid, license_key):
                valid = True
            else:
                # 主板/CPU 两种取法可能不同，回退再验一次
                try:
                    from hwid_utils import get_hwid_wmic
                    hwid_wmic = get_hwid_wmic()
                    if verify_license(hwid_wmic, license_key):
                        active_hwid = hwid_wmic
                        valid = True
                except Exception:
                    pass

        if not valid:
            self.show_auth_dialog(hwid, clean_type)
            return

        self.append_log("授权验证成功，准备清理所选项目。")
        if clean_type == "risk":
            self.show_risk_confirmation(clean_type, lambda: self.execute_cleaning(clean_type))
            return

        self.execute_cleaning(clean_type)

    def execute_cleaning(self, clean_type):
        from brand_ui import selected_apps, busy, tools_busy
        if busy(self) or tools_busy(self):
            return
        self._clean_snapshot = tuple(selected_apps(self, clean_type))
        if not self._clean_snapshot:
            return
        if clean_type == "safe":
            self.safe_state = "cleaning"
        else:
            self.risk_state = "cleaning"
        self._set_buttons()
        # 确定性进度条：随清理项推进（配合列表自动定位与行底条填充）
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(0)
        self._status_line_locked = False
        try:
            self.lbl_progress_info.configure(
                text=" 准备清理...", text_color="#E7BA7A")
        except Exception:
            pass
        threading.Thread(target=self._clean_worker, args=(clean_type,), daemon=True).start()

    def _clean_worker(self, clean_type):
        try:
            self._clean_thread(clean_type)
        except Exception as error:
            message = str(error)
            self._post_ui(lambda: self._clean_failed(clean_type, message))

    def _clean_failed(self, clean_type, message):
        setattr(self, clean_type + "_state", "done")
        self._status_line_locked = True
        self.lbl_progress_info.configure(text="清理中断，请重新扫描后核对剩余项目。", text_color="#ECA0A6")
        self.append_log("清理中断：" + message)
        self.render_scroll_list()
        self.update_stat_cards()
        self._set_buttons()

    def _clean_thread(self, clean_type):
        self.append_log(f"正在清理所选项目 [{'安全清理' if clean_type == 'safe' else '风险清理'}]...")
        # 累计唯一入口：循环内只加局部 stage_freed，收尾由 on_clean_finished 统一入账。
        # 历史 Bug：循环里逐项加过 freed_safe/freed_risk，收尾又加 stage_freed → 总量翻倍。
        stage_freed = 0
        freed_base = self.freed_safe + self.freed_risk
        self.last_clean_detail = []   # [(项目名, 本项释放字节)] 供完成报告 TOP5

        cleanable_apps = list(getattr(self, "_clean_snapshot", ()))

        if not cleanable_apps:
            self.append_log("\n[!] 没有勾选任何属于当前清理分类的软件项。")
            self._post_ui(lambda: self.on_clean_finished(clean_type, 0))
            return

        # 绝不清理自身运行目录（打包后的临时解压目录）
        our_meipass = getattr(sys, "_MEIPASS", None)
        if our_meipass:
            our_meipass = os.path.abspath(our_meipass).lower()

        total_items = len(cleanable_apps)
        for idx, app in enumerate(cleanable_apps):
            app_id = app["id"]
            self.append_log(f'[*] 正在抹除: {app["name"]}')
            # 跟随反馈：列表自动滚到该项 + 行底条琥珀色(处理中) + 总进度条
            self._post_ui(lambda aid=app_id, i=idx, n=total_items:
                       self._ui_clean_row_state(aid, "running", i, n, freed_base))
            time.sleep(0.05)

            deleted_size = 0
            # 细分管理：按用户在「细分」面板中的可选状态过滤（未设置的路径默认参与清理）
            sub_choices = getattr(self, "subpath_choices", {}).get(app_id, {})
            for pattern in app.get("paths", []):
                try:
                    if not sub_choices.get(str(pattern).lower(), True):
                        self.append_log(f"    [细分跳过] {obfuscate_path(str(pattern))}")
                        continue
                except Exception:
                    pass
                for p in get_resolved_paths([pattern]):
                    if our_meipass and our_meipass in os.path.abspath(p).lower():
                        continue
                    deleted_size += clean_directory(
                        p, self.append_log, self.skipped_files,
                        stale_days=app.get("stale_days"))

            self.sizes[app_id] = 0   # 数据侧清零（UI 文本在主线程 done 分支更新）
            stage_freed += deleted_size
            self.last_clean_detail.append((app["name"], deleted_size))
            # 完成反馈：行底条绿色从左到右填充 + 徽章更新 + 实时释放量
            self._post_ui(lambda aid=app_id, i=idx, n=total_items,
                       freed=freed_base + stage_freed, name=app["name"]:
                       self._ui_clean_row_state(aid, "done", i, n, freed, name))
            time.sleep(0.3)

        self._post_ui(lambda: self.on_clean_finished(clean_type, stage_freed))

    def _ui_clean_row_state(self, app_id, phase, idx, total, freed_base, app_name=None):
        """主线程侧的清理跟随 UI：滚动定位 + 行底条 + 徽章 + 实时释放量。"""
        try:
            # only_if_hidden：正在清理的行可见时不做滚动重排（消除列表卡顿）
            scroll_row_into_view(self, app_id, only_if_hidden=True)
            animate_row_progress(self, app_id, phase)
            if total > 0:
                self.progress_bar.set((idx + (1 if phase == "done" else 0)) / total)
            try:
                self._status_line_locked = True
                self.lbl_progress_info.configure(
                    text=self._truncate_log(
                        f" 正在清理: {app_name or app_id}  ({idx + 1}/{total})"
                        if phase == "running" else
                        f" 清理进度 {idx + 1}/{total} · 已释放 {format_size(freed_base)}"),
                    text_color="#E7BA7A")
            except Exception:
                pass
            if phase == "done":
                self.lbl_cleaned_val.configure(text=format_size(freed_base))
                if app_id in self.app_rows:
                    self.app_rows[app_id]["size"].configure(text="0.00 B")
                    style_row_badge(self, app_id, " 已安全净化", "#91D5B6", "#203B30")
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 细分管理与可选状态：行内展开子路径清单，每条可独立勾选；
    # 行勾选状态跨列表重建记忆（排序/扫描/清理后不丢用户选择）
    # ------------------------------------------------------------------
    def _remember_selection(self, app):
        """行勾选框变化时记录用户意图，供列表重建时恢复。"""
        try:
            var = self.app_checkbox_vars.get(app["id"])
            if var is not None:
                self.selection_state[app["id"]] = int(var.get())
        except Exception:
            pass

    def toggle_subpaths(self, app, btn=None):
        """展开/收起该项目的清理子路径面板（同刻只展开一个）。

        免疫行：面板只读展示子路径（不参与清理，无勾选框），底部提供
        「解锁此项」入口（Agent 记忆免疫网项目显示不可解锁）。
        """
        from brand_ui import busy
        if busy(self):
            return
        app_id = app["id"]
        is_immune = bool(app.get("immune"))
        try:
            if getattr(self, "_subpath_panel", None) is not None:
                old = self._subpath_panel
                self._subpath_panel = None
                try:
                    old.master_row_btn.configure(text="▸ 细分")
                except Exception:
                    pass
                old.destroy()
                if getattr(old, "panel_app_id", None) == app_id:
                    return   # 再次点击同一项 = 收起
            choices = self.subpath_choices.setdefault(app_id, {})
            panel = ctk.CTkFrame(self.scroll_frame, fg_color="#101419",
                                 corner_radius=6, border_width=1,
                                 border_color="#203640" if is_immune else "#203640")
            panel.panel_app_id = app_id
            if is_immune:
                ctk.CTkLabel(panel, text=f" {app['name']} · 系统免疫明细（只读，不参与清理）",
                             font=F(UI_FAMILY, 12, "bold"), text_color="#8CDEEF",
                             ).pack(anchor="w", padx=10, pady=(6, 2))
            else:
                ctk.CTkLabel(panel, text=f" {app['name']} · 细分清理范围（取消勾选的路径本次不清理）",
                             font=F(UI_FAMILY, 12, "bold"), text_color="#B1ECF7",
                             ).pack(anchor="w", padx=10, pady=(6, 2))
            patterns = app.get("paths", []) or []
            if not patterns:
                ctk.CTkLabel(panel, text="（该项未定义细分路径）",
                             font=F(UI_FAMILY, 12), text_color="#8795A5",
                             ).pack(anchor="w", padx=14, pady=(0, 6))
            for pat in patterns:
                key = str(pat).lower()
                row = ctk.CTkFrame(panel, fg_color="transparent")
                row.pack(fill="x", padx=10)
                if is_immune:
                    ctk.CTkLabel(row, text="", width=18,
                                 font=F(UI_FAMILY, 11)).pack(side="left", padx=(4, 6), pady=2)
                else:
                    svar = ctk.BooleanVar(value=choices.get(key, True))
                    ctk.CTkCheckBox(row, text="", variable=svar, width=18, height=18,
                                    command=lambda k=key, v=svar, a=app_id:
                                    self.subpath_choices.setdefault(a, {}).__setitem__(k, bool(v.get()))
                                    ).pack(side="left", padx=(4, 6), pady=2)
                ctk.CTkLabel(row, text=obfuscate_path(str(pat)),
                             font=F(MONO_FAMILY, 11), text_color="#CFD7E0",
                             anchor="w").pack(side="left", fill="x", expand=True)
            # 已迁移记忆标注：原路径是 Junction 入口，真实数据在目标盘，
            # 避免误读为"C 盘仍占用"
            try:
                from migrate_core import is_junction, migrated_target_of, _exp
                seen_bases = set()
                for pat in patterns:
                    base = str(pat).split("*")[0].rstrip(chr(47) + chr(92))
                    if not base or base in seen_bases:
                        continue
                    seen_bases.add(base)
                    real = _exp(base)
                    if is_junction(real):
                        tgt = migrated_target_of(real)
                        if tgt:
                            drv = os.path.splitdrive(tgt)[0].upper()
                            ctk.CTkLabel(
                                panel, text=(f"⤳ 已迁移：{real} 现存于 {tgt}"
                                             f"（数据在 {drv} 盘，C 盘不占用）"),
                                font=F(UI_FAMILY, 11), text_color="#3C6D58",
                                anchor="w", wraplength=780,
                                justify="left").pack(anchor="w", padx=14, pady=(2, 0))
            except Exception:
                pass
            if is_immune:
                from cleaner_core import is_agent_memory_path
                agent_protected = any(is_agent_memory_path(str(p)) for p in patterns)
                foot = ctk.CTkFrame(panel, fg_color="transparent")
                foot.pack(fill="x", padx=10, pady=(4, 8))
                if agent_protected:
                    ctk.CTkLabel(foot, text=" Agent 记忆免疫网 · 内核级保护，不可解锁",
                                 font=F(UI_FAMILY, 12, "bold"),
                                 text_color="#ECA0A6").pack(side="left")
                else:
                    ctk.CTkLabel(foot, text="解锁后此项将参与扫描与清理",
                                 font=F(UI_FAMILY, 11),
                                 text_color="#A3AFBD").pack(side="left")
                    ctk.CTkButton(foot, text=" 解锁此项并允许清理",
                                  font=F(UI_FAMILY, 12, "bold"), width=180, height=28,
                                  fg_color="#59353A", hover_color="#74434A",
                                  command=lambda a=app: self.unlock_immunity(a)
                                  ).pack(side="right")
            panel.pack(fill="x", padx=(14, 14), pady=(0, 6), after=self.app_rows.get(app_id, {}).get("frame"))
            panel.master_row_btn = getattr(self, "app_expand_btns", {}).get(app_id)
            try:
                panel.master_row_btn.configure(text="▾ 细分")
            except Exception:
                pass
            self._subpath_panel = panel
        except Exception:
            pass

    # ------------------------------------------------------------------
    # 对话框
    # ------------------------------------------------------------------
    def show_auth_dialog(self, hwid, clean_type):
        """授权拦截对话框（实现在 ui_theme，避免单脚本过大）。"""
        show_auth_dialog(self, hwid, clean_type)

    def show_risk_confirmation(self, clean_type, on_confirm):
        """风险清理二次确认（实现在 ui_theme）。"""
        show_risk_confirmation(self, clean_type, on_confirm)

    def show_file_viewer(self, app):
        """文件清单预览（实现在 ui_theme）。"""
        from brand_ui import busy
        if busy(self):
            return
        show_file_viewer(self, app)

    def show_protection_list(self):
        """保护清单透明化：系统免疫 + 手动上锁 分项明细（实现在 ui_theme）。"""
        show_protection_list(self)

    def show_final_report(self, kind, tier_or_type, freed_bytes=None):
        """扫描/清理完成的结构化报告弹窗（实现在 ui_theme）。"""
        show_final_report(self, kind, tier_or_type, freed_bytes)

    def show_grouped_details(self, filter_type, title_text):
        """按类别展示容量明细。"""
        win = ctk.CTkToplevel(self)
        win.title(title_text)
        win.geometry("760x520")
        win.resizable(False, False)
        win.grab_set()

        box = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Consolas", size=12))
        box.pack(fill="both", expand=True, padx=14, pady=14)

        apps = self.apps_data
        if filter_type == "immune":
            apps = [a for a in apps if a.get("immune")]
        elif filter_type == "cleaned":
            apps = [a for a in apps if self.sizes.get(a["id"], 0) == 0]
        else:
            apps = [a for a in apps if not a.get("immune") and self.sizes.get(a["id"], 0) > 0]

        for a in apps:
            box.insert("end", f"{a['name']}  —  {format_size(self.sizes.get(a['id'], 0))}\n")
        box.configure(state="disabled")
        ctk.CTkButton(win, text="关闭", command=win.destroy).pack(pady=(0, 12))

    def show_scanned_details(self):
        self.show_grouped_details("scan", "已扫描垃圾明细")

    def show_safe_clean_details(self):
        self.show_grouped_details("cleaned", "已安全清理明细")

    def show_immune_details(self):
        self.show_grouped_details("immune", "核心安全锁定保护明细")

    def clean_single_app(self, app_to_clean, parent_dialog):
        """在明细对话框中清理单个项目。"""
        def run_single():
            freed = 0
            for p in get_resolved_paths(app_to_clean.get("paths", [])):
                try:
                    freed += clean_directory(
                        p, self.append_log, self.skipped_files,
                        stale_days=app_to_clean.get("stale_days"))
                except Exception:
                    pass

            def done():
                self.sizes[app_to_clean["id"]] = 0
                self.freed_safe += freed
                self.update_stat_cards()
                self.append_log(f"[] {app_to_clean['name']} 清理完成，释放 {format_size(freed)}。")
                if parent_dialog is not None:
                    try:
                        parent_dialog.destroy()
                    except Exception:
                        pass

            self._post_ui(done)

        threading.Thread(target=run_single, daemon=True).start()

    def check_for_updates(self):
        def run_check():
            try:
                url = f"https://ppsai.chat/api/check_update?version={CURRENT_VERSION}"
                req = urllib.request.Request(url, headers={"User-Agent": "SafeCleanerPro-Client"})
                with urllib.request.urlopen(req, timeout=4) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode("utf-8"))
                        if data.get("has_update"):
                            self._post_ui(lambda: self.show_update_dialog(data))
            except Exception as e:
                print(f"Check update failed: {e}")

        threading.Thread(target=run_check, daemon=True).start()

    def show_update_dialog(self, update_info):
        win = ctk.CTkToplevel(self)
        win.title(" 发现新版本 PPSAI Cleaner")
        win.geometry("680x520")
        win.resizable(False, False)
        win.grab_set()
        try:
            win.attributes("-topmost", True)
        except Exception:
            pass

        ctk.CTkLabel(win, text=" 发现新版本 PPSAI Cleaner",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=19, weight="bold"),
                     text_color="#8CDEEF").pack(pady=(20, 8))
        ctk.CTkLabel(win,
                     text=f"最新版本: v{update_info.get('latest_version', '')}   "
                          f"(当前版本: v{CURRENT_VERSION})",
                     font=ctk.CTkFont(family="Microsoft YaHei UI", size=13),
                     text_color="#A3AFBD").pack(pady=(0, 10))

        box = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Microsoft YaHei UI", size=12))
        box.pack(fill="both", expand=True, padx=20, pady=6)
        notes = update_info.get("release_notes") or "（无更新说明）"
        if isinstance(notes, list):
            notes = "\n".join(str(n) for n in notes)
        box.insert("0.0", str(notes).replace("\\n", "\n"))
        box.configure(state="disabled")

        def download():
            self.open_url(update_info.get("download_url") or "https://ppsai.chat/safecleaner/")

        ctk.CTkButton(win, text="立即下载更新", command=download,
                      font=ctk.CTkFont(family="Microsoft YaHei UI", size=13, weight="bold"),
                      fg_color="#295443", hover_color="#3C6D58").pack(pady=10)
        ctk.CTkButton(win, text="稍后再说", command=win.destroy).pack(pady=(0, 12))


def is_personal_file(filepath):
    """判断路径是否属于个人文档/桌面/下载等敏感区域。

    关键口径：\\Users\\ 下的 AppData 是应用缓存（垃圾大头），不是个人文档。
    历史缺陷：仅凭 \\users\\ 命中就把 AppData 缓存全判为个人文件跳过，
    导致安全扫描 33 GB 而实际只清得动 Windows\\Temp 等少数目录。
    """
    try:
        low = str(filepath).lower()
        if "\\appdata\\" in low:
            return False  # 应用数据/缓存目录：属于可清理垃圾，不属于个人文档
        if "\\users\\" not in low:
            return False
        marks = ("\\documents\\", "\\desktop\\", "\\downloads\\",
                 "\\pictures\\", "\\videos\\", "\\music\\")
        return any(m in low for m in marks)
    except Exception:
        return False


def get_resource_path(filename):
    """PyInstaller 打包后从 _MEIPASS 取资源，否则用本地路径。"""
    try:
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, filename)
    except Exception:
        return filename


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


from brand_ui import BrandSplash as SplashScreen



if __name__ == "__main__":
    app = SafeCleanerApp()
    app.withdraw()
    splash = SplashScreen(app)
    app.mainloop()
