# -*- coding: utf-8 -*-
"""v3.9.11 GUI 冒烟：真实 Tk 环境走一遍新 UI 面，不触碰任何清理按钮"""
import io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
import customtkinter as ctk
import main
from ui_theme import build_app_row

app = main.SafeCleanerApp()
app.withdraw()
app.build_ui()
assert app.selection_state == {} and app.subpath_choices == {}
print("[1] build_ui + new state OK")

# 造一行真实 app，测试细分面板展开/收起
fake_app = {"id": "smoke_x", "name": "冒烟测试项", "type": "app", "immune": False,
            "risk_level": "safe", "icon": "🧪",
            "paths": ["C:\\__SMOKE__\\Temp\\*", "C:\\__SMOKE__\\Logs\\*"]}
app.sizes["smoke_x"] = 12345
app.render_scroll_list()
app.update()
app._row_queue = []  # 阻断懒加载泵，直接手工建一行
build_app_row(app, fake_app, 0)
app.update()
assert "smoke_x" in app.app_rows and "smoke_x" in app.app_expand_btns
print("[2] row + expand btn OK")

app.toggle_subpaths(fake_app)
app.update()
p = app._subpath_panel
assert p is not None and p.winfo_exists(), "panel not created"
kids = [w for w in p.winfo_children()]
assert len(kids) >= 3, f"panel rows missing: {len(kids)}"
print("[3] expand panel OK")

app.toggle_subpaths(fake_app)   # 再次点击 = 收起
app.update()
assert app._subpath_panel is None
print("[4] collapse panel OK")

# 勾选记忆
app._remember_selection(fake_app)
assert app.selection_state.get("smoke_x") == 1  # safe 默认勾选
app.app_checkbox_vars["smoke_x"].set(0)
app._remember_selection(fake_app)
assert app.selection_state.get("smoke_x") == 0
# 重建行应恢复 0
build_app_row(app, fake_app, 0)
assert app.app_checkbox_vars["smoke_x"].get() == 0, "selection not restored"
print("[5] selection persistence OK")

# toast 不崩溃即视为通过（自动淡出由 after 驱动）
app._show_toast("冒烟提示", "#064e3b", "#22c55e", duration_ms=200)
app.update()
print("[6] toast OK")

# splash 满铺实例化
sp = main.SplashScreen(app)
app.update()
assert sp.lbl_bg.winfo_exists() and sp.progress.winfo_exists()
sp.destroy()
print("[7] splash cover OK")

app.destroy()
print("SMOKE ALL PASS")
