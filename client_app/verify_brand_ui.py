# -*- coding: utf-8 -*-
"""Non-destructive native UI acceptance: synthetic findings, no cleaning/scanning user data."""
import ctypes
import os
from pathlib import Path
import time
from unittest.mock import patch

from PIL import ImageGrab

import main as m
import brand_ui as ui

OUT = Path(__file__).resolve().parents[1] / ".impeccable" / "review"
OUT.mkdir(parents=True, exist_ok=True)
passed = []
errors = []


def check(name, value):
    if not value:
        raise AssertionError(name)
    passed.append(name)
    print("PASS", name, flush=True)


def pump(app, duration=.2):
    end = time.monotonic() + duration
    while time.monotonic() < end:
        app.update()
        time.sleep(.005)


def capture(win, name):
    win.attributes("-topmost", True)
    win.deiconify(); win.lift(); win.update()
    pump(win, .2)
    rect = (win.winfo_rootx(), win.winfo_rooty(),
            win.winfo_rootx() + win.winfo_width(), win.winfo_rooty() + win.winfo_height())
    ImageGrab.grab(bbox=rect).save(OUT / name)
    win.attributes("-topmost", False)


def widget_texts(root):
    texts = []
    for child in root.winfo_children():
        try:
            text = child.cget("text")
            if text:
                texts.append(text)
        except Exception:
            pass
        texts.extend(widget_texts(child))
    return texts


def direct_widget_texts(root):
    texts = []
    for child in root.winfo_children():
        try:
            text = child.cget("text")
            if text:
                texts.append(text)
        except Exception:
            pass
    return texts


def contains_widget(root, target):
    for child in root.winfo_children():
        if child is target or contains_widget(child, target):
            return True
    return False


def main():
    m.SafeCleanerApp.check_for_updates = lambda self: None
    app = m.SafeCleanerApp()
    app.report_callback_exception = lambda *info: errors.append(str(info[1]))
    app.geometry("1380x860+32+32")
    app.build_ui(); pump(app)
    check("brand title", "PPSAI Cleaner" in app.title())
    check("all workspace and settings navigation destinations", len(app.nav_buttons) == 7)
    check("initial scan action", app.btn_action.cget("text") == "开始扫描")
    check("sidebar and workspace share one graphite background",
          app.sidebar_frame.cget("fg_color") == app.main_frame.cget("fg_color") == ui.BG)
    support_text = direct_widget_texts(app.btn_settings.master)
    check("sidebar footer contains only the version label",
          support_text == ["设置与关于", f"v{m.CURRENT_VERSION}"])
    check("transparent logo alpha is preserved", app._brand_mark._light_image.mode == "RGBA")
    capture(app, "desktop.png")
    nav = app.nav_buttons["safe"]
    nav_configure = nav.configure
    nav_redraws = []
    nav.configure = lambda **kwargs: (nav_redraws.append(kwargs), nav_configure(**kwargs))[1]
    ui.sync_actions(app)
    nav.configure = nav_configure
    check("idle refresh does not redraw unchanged sidebar buttons", not nav_redraws)
    ui.navigate(app, "settings"); pump(app)
    check("update check exists in settings", contains_widget(app.settings_frame, app.btn_check_update))
    check("sidebar has no repeated update link or slogan",
          "检查更新" not in widget_texts(app.sidebar_frame)
          and "为重要的内容，留出空间。" not in widget_texts(app.sidebar_frame))
    ui.navigate(app, "safe"); pump(app)
    app.geometry("1120x740+32+32"); pump(app)
    capture(app, "desktop-compact.png")
    check("compact window width", abs(app._reverse_window_scaling(app.winfo_width()) - 1120) < 2)
    app.geometry("1380x860+32+32"); pump(app)

    original = app.apps_data
    names = ["Windows 临时文件", "浏览器缓存", "Adobe 渲染缓存", "开发工具日志",
             "软件安装残留", "下载缓存", "会话归档", "Agent 记忆与工作区"]
    app.apps_data = [dict(id=f"demo-{i}", name=name, paths=[rf"C:\PPSAI-UI-TEST\{i}"],
                          icon="", immune=i == 7, type=("system", "app", "adobe", "dev")[i % 4],
                          risk_level="risk" if i == 6 else "safe",
                          risk_desc="演示数据，仅用于交互与布局验收。") for i, name in enumerate(names)]
    app.sizes = {a["id"]: (i+1)*167772160 for i, a in enumerate(app.apps_data)}
    app.safe_state = "ready"
    app.safe_bytes = sum(app.sizes[a["id"]] for a in app.apps_data[:6])
    app.total_immune_bytes = app.sizes["demo-7"]
    app.main_subtitle.configure(text="演示数据 · 验证项目列表、容量、选择与详情布局")
    app.render_scroll_list(); pump(app, .5); app.update_stat_cards(); app._set_buttons()
    check("safe results rendered", len(app.app_rows) == 7)
    check("immune result not selectable", "demo-7" not in app.app_checkbox_vars)
    ui.show_item_detail(app, "demo-2"); pump(app)
    capture(app, "desktop-results.png")

    app.app_checkbox_vars["demo-0"].set(0)
    app._remember_selection(app.apps_data[0])
    chosen = ui.selection_summary(app)
    app.search_var.set("浏览器"); pump(app, .5)
    check("search filters only visible rows", list(app.app_rows) == ["demo-1"])
    check("search preserves chosen capacity", ui.selection_summary(app) == chosen)
    app.search_var.set(""); pump(app, .5)
    check("selection survives rebuilding", not app.app_checkbox_vars["demo-0"].get())
    app.sort_mode_var.set("size"); app.render_scroll_list(); pump(app, .5)
    check("sort preserves selection", not app.app_checkbox_vars["demo-0"].get())

    ui.navigate(app, "risk"); app.risk_state = "ready"; app.risk_bytes = app.sizes["demo-6"]
    app.render_scroll_list(); pump(app, .5)
    check("risk defaults to unselected", not app.app_checkbox_vars["demo-6"].get())
    app._set_buttons()
    check("risk cannot clean an empty selection", app.btn_deep.cget("state") == "disabled")
    app.app_checkbox_vars["demo-6"].set(1); app._remember_selection(app.apps_data[6]); app._set_buttons()
    ui.show_risk_confirmation(app, "risk", lambda: None); pump(app)
    confirm = next(w for w in app.winfo_children() if isinstance(w, m.ctk.CTkToplevel))
    capture(confirm, "risk-confirmation.png"); confirm.destroy()

    ui.navigate(app, "protected"); pump(app, .5)
    check("protection has no checkboxes", len(app.app_checkbox_vars) == 0)
    capture(app, "desktop-protection.png")
    ui.navigate(app, "settings"); pump(app)
    check("settings retains current navigation state", app.btn_settings.cget("fg_color") == ui.TINT)
    capture(app, "desktop-settings.png")
    ui.navigate(app, "safe"); pump(app, .5)
    app.safe_state = "scanning"; app._set_buttons()
    old_drive = next(iter(app.drive_vars))
    before = app.drive_vars[old_drive].get()
    ui.toggle_drive(app, old_drive)
    check("scope frozen while busy", app.drive_vars[old_drive].get() == before)
    check("conflicting actions disabled", app.btn_deep.cget("state") == "disabled")
    ui.navigate(app, "risk")
    check("navigation frozen while busy", app.current_view == "safe")
    app.safe_state = "ready"
    with patch.object(m.threading, "Thread") as worker:
        app.execute_cleaning("safe")
        check("clean uses main-thread selection snapshot", len(app._clean_snapshot) == 5)
        check("worker scheduled once", worker.return_value.start.call_count == 1)
    app.safe_state = "ready"
    app._scan_failed("safe", "test error"); pump(app)
    check("scan failure can retry", app.safe_state == "idle")

    # Exercise the actual scan worker with inert synthetic paths and mocked size/file probes.
    app.apps_data = app.apps_data[:3]
    app.sizes = {a["id"]: 0 for a in app.apps_data}
    app.selection_state = {}; app.safe_state = "idle"
    with patch("cleaner_core.get_app_size", return_value=4096), patch("cleaner_core.scan_app_files", return_value=[]):
        app.start_scan("safe")
        until = time.monotonic() + 8
        while app.safe_state == "scanning" and time.monotonic() < until:
            pump(app, .05)
        pump(app, .2)
    check("background scan reaches ready", app.safe_state == "ready")
    check("background scan totals", app.safe_bytes == 12288)
    app.apps_data = original
    app.safe_state = "idle"; app.risk_state = "idle"
    app._set_buttons()

    from deep_ui import DeepOptimizeWindow
    from migrate_ui import MemoryMigrateWindow
    from dedup_ui import DedupWindow
    with patch.object(MemoryMigrateWindow, "start_scan", lambda self: None), \
         patch.object(MemoryMigrateWindow, "_load_icons_async", lambda self: None), \
         patch.object(DedupWindow, "_load_last_result", lambda self: None), \
         patch.object(DedupWindow, "_history_labels", lambda self: ["暂无历史记录"]):
        for key, cls, filename in [("deep", DeepOptimizeWindow, "desktop-app-cache.png"),
                                   ("migrate", MemoryMigrateWindow, "desktop-migration.png"),
                                   ("dedup", DedupWindow, "desktop-duplicates.png")]:
            win = cls(app)
            app._tool_windows[key] = win
            win.geometry("1300x820+48+48")
            pump(app, .25)
            check(key + " branded title", win.title().startswith("PPSAI Cleaner"))
            if key == "deep":
                win.items = [dict(id="demo-cache", cat_name="开发工具", name="演示缓存（验收）",
                                  size=503316480, files=48, mtime=0, risk="safe",
                                  paths=[dict(path=r"C:\PPSAI-UI-TEST\cache", size=503316480, files=48)])]
                win.checked = {"c:demo-cache"}
                win._render()
                win._select_all(False)
                check("cache clean disabled with no selection", win.btn_clean.cget("state") == "disabled")
                win._select_all(True)
                check("cache clean enabled after selection", win.btn_clean.cget("state") == "normal")
                win.lbl_status.configure(text="演示数据 · 验证选择状态与表格布局")
                check("cache selection visibly marked", win.tree.set("c:demo-cache", "sel") == "已选")
            elif key == "migrate":
                win.items = [dict(id="demo-memory", name="演示记忆（验收）", category="AI Agent",
                                  sources_resolved=[r"C:\PPSAI-UI-TEST\memory"], icon="")]
                win.info = {"demo-memory": dict(bytes=2147483648, files=120, status="clean")}
                win.checked = {"demo-memory"}; win._render_tree()
                with patch.object(win, "_drive_options", return_value=[]):
                    win._populate_drives()
                check("migration unavailable without target", win.btn_migrate.cget("state") == "disabled")
                win.lbl_status.configure(text="演示数据 · 未发现可用目标盘，迁移操作暂不可用")
                check("migration selection visibly marked", win.tree.set("demo-memory", "sel") == "已选")
            else:
                check("duplicates cannot scan empty scope", win.btn_start.cget("state") == "disabled")
                check("duplicates stop disabled at rest", win.btn_stop.cget("state") == "disabled")
                win.add_scope(r"C:\PPSAI-UI-TEST")
                check("duplicates scan enabled after scope", win.btn_start.cget("state") == "normal")
                win.lbl_stat.configure(text="演示数据 · 验证跨文件夹副本列表，未执行真实扫描")
                win.tree.insert("", "end", iid="demo-keep", values=(1, "保留", "32 MB", "—", "—", "文档", "演示文档.pdf", r"C:\PPSAI-UI-TEST\source", "demo"), tags=("keep",))
                win.tree.insert("", "end", iid="demo-copy", values=(1, "冗余", "32 MB", "—", "—", "文档", "演示文档副本.pdf", r"C:\PPSAI-UI-TEST\copy", "demo"), tags=("redundant",))
            capture(win, filename)
            win.destroy()
    with patch.object(ui.BrandSplash, "_prepare", lambda self: None):
        splash = ui.BrandSplash(app)
        capture(splash, "desktop-splash.png")
        splash.destroy()
    check("no Tk callback errors", not errors)
    app.destroy()
    print(f"Passed {len(passed)} assertions. Screenshots: {OUT}", flush=True)


if __name__ == "__main__":
    main()
