# -*- coding: utf-8 -*-
"""五项 UI/UX 修复的综合补丁（brand_ui / main / dedup_ui / migrate_ui）。"""
import io

NL = chr(10)
OK = []
MISS = []


def patch(path, pairs):
    s = io.open(path, encoding="utf-8").read()
    for old, new in pairs:
        if old in s:
            s = s.replace(old, new, 1)
            OK.append(path.split(NL)[0] + " :: " + old.strip()[:46])
        else:
            MISS.append(path + " :: " + old.strip().split(NL)[0][:60])
    io.open(path, "w", encoding="utf-8", newline=NL).write(s)


# ═══ brand_ui.py ═══
B = "brand_ui.py"
patch(B, [
    # 导航：移除 应用缓存 / 保护中心 两页；空间清理 → 安全清理
    ('    nav = [("safe", "空间清理", "scan"), ("risk", "深度清理", "layers"),\n'
     '           ("dedup", "重复文件", "copy"), ("migrate", "记忆迁移", "move"),\n'
     '           ("deep", "应用缓存", "disk"), ("protected", "保护中心", "shield")]',
     '    nav = [("safe", "安全清理", "scan"), ("risk", "深度清理", "layers"),\n'
     '           ("dedup", "重复文件", "copy"), ("migrate", "记忆迁移", "move")]'),
    ('    owner.btn_protection = owner.nav_buttons["protected"]\n', ""),
    # navigate：deep 不再是弹窗工具
    ('    if key in ("dedup", "migrate", "deep"):', '    if key in ("dedup", "migrate"):'),
    # navigate：扫描中也允许切换工作区
    ('    if busy(owner) and key != owner.current_view:\n'
     '        owner.lbl_progress_info.configure(text="当前任务进行中，完成后可切换工作区。", text_color=WARN)\n'
     '        return\n', ""),
    # navigate：protected 分支与文案移除
    ('        titles = {"safe": ("让工作空间，轻盈如初。", "扫描缓存与临时文件，重要内容始终由你掌控。"),\n'
     '                  "risk": ("把每一份空间，看得更清楚。", "深度项目默认不选中。查看路径与说明后，再决定清理。"),\n'
     '                  "protected": ("重要的内容，始终有归处。", "查看系统免疫与手动上锁的项目，了解每一项保护范围。")}\n'
     '        title, sub = titles[key]\n'
     '        owner.main_title.configure(text=title); owner.main_subtitle.configure(text=sub)\n'
     '        if key == "protected":\n'
     '            owner.render_scroll_list()\n'
     '            show_protection(owner)\n'
     '        elif getattr(owner, key + "_state") == "idle" and not owner.search_var.get() and not owner.show_all_items:',
     '        titles = {"safe": ("让工作空间，轻盈如初。", "扫描缓存与临时文件，重要内容始终由你掌控。"),\n'
     '                  "risk": ("把每一份空间，看得更清楚。", "受保护项也在这里：默认不选中，支持上锁与解锁。")}\n'
     '        title, sub = titles.get(key, titles["risk"])\n'
     '        owner.main_title.configure(text=title); owner.main_subtitle.configure(text=sub)\n'
     '        if getattr(owner, key + "_state") == "idle" and not owner.search_var.get() and not owner.show_all_items:'),
    # 头部「保护已启用」按钮 → 深度清理
    ('button(head, "保护已启用", lambda: navigate(owner, "protected"), width=132, height=34,',
     'button(head, "🛡 受保护项在深度清理", lambda: navigate(owner, "risk"), width=190, height=34,'),
    # sync_actions：导航按钮扫描中保持可用
    ('        _configure_if_changed(b, state="disabled" if active and key != view else "normal",',
     '        _configure_if_changed(b, state="normal",'),
    # sync_actions：移除 protected 文案分支
    ('    if view == "protected":\n'
     '        text = "保护中的项目不参与清理"\n'
     '    elif other_tools_active:\n'
     '        text = "其他空间工具正在执行任务"\n',
     '    if other_tools_active:\n'
     '        text = "其他空间工具正在执行任务"\n'),
    # glyph：protected 特例移除
    ('    glyph = "shield" if owner.current_view == "protected" else "scan"',
     '    glyph = "scan"'),
    # 主窗口主题应用（brand build 尾部）
])

# 主窗口 DWM 主题：挂到 brand build 的 refresh_live 启动前
s = io.open(B, encoding="utf-8").read()
if "apply_window_chrome(owner)" not in s:
    anchor = "    owner.after(300, lambda: refresh_live(owner))"
    if anchor in s:
        s = s.replace(anchor,
                      "    from ui_theme import apply_window_chrome\n"
                      "    apply_window_chrome(owner)\n"
                      "    owner.after(260, lambda: apply_window_chrome(owner))\n" + anchor, 1)
        OK.append("brand_ui :: root chrome")
    else:
        MISS.append("brand_ui :: refresh_live anchor")
io.open(B, "w", encoding="utf-8", newline=NL).write(s)

# ═══ main.py：视图过滤（受保护项并入深度线）+ 渐进建行视图分流 ═══
M = "main.py"
patch(M, [
    ('            if view == "protected":\n'
     '                apps = [a for a in apps if a["immune"] or a["id"] in self.locked_ids]\n'
     '                view_banner = "保护中的项目"\n'
     '            elif view == "risk":\n'
     '                apps = [a for a in apps\n'
     '                        if not a["immune"] and a.get("risk_level") == "risk"]\n'
     '                view_banner = "缓存、日志与临时文件"',
     '            if view == "risk":\n'
     '                apps = [a for a in apps\n'
     '                        if a["immune"] or a.get("risk_level") == "risk"]\n'
     '                view_banner = "深度清理与受保护项（默认不选中 · 支持解锁）"'),
    ('            else:\n'
     '                apps = [a for a in apps\n'
     '                        if a["immune"] or a.get("risk_level") == "safe"]\n'
     '                view_banner = ("缓存、日志与临时文件")',
     '            else:\n'
     '                apps = [a for a in apps\n'
     '                        if a.get("risk_level") == "safe"]\n'
     '                view_banner = ("缓存、日志与临时文件")'),
    # Round M：受保护项常显；切视图时按已发现垃圾过滤（避免 781 行重建卡顿）
    ('            if not show_all and not busy and view != "protected":\n'
     '                visible = [a for a in apps if self.sizes.get(a["id"], 0) > 0]\n'
     '                self._hidden_zero_count = len(apps) - len(visible)\n'
     '                apps = visible',
     '            scanning_view = ("safe" if self.safe_state == "scanning" else\n'
     '                             ("risk" if self.risk_state == "scanning" else None))\n'
     '            if not show_all and not (busy and view == scanning_view):\n'
     '                visible = [a for a in apps if a["immune"] or\n'
     '                           self.sizes.get(a["id"], 0) > 0]\n'
     '                self._hidden_zero_count = len(apps) - len(visible)\n'
     '                apps = visible'),
    # 渐进建行：按当前视图分流（另一线的项等切换视图时由渲染呈现）
    ('                if app_id not in self.app_rows and app is not None:\n'
     '                    build_app_row(self, app, getattr(self, "_row_index", 0))\n'
     '                    self._row_index = getattr(self, "_row_index", 0) + 1',
     '                stage_view = "safe" if (app.get("immune") or app.get("risk_level") == "safe") else "risk"\n'
     '                if app_id not in self.app_rows and app is not None \\\n'
     '                        and self.current_view == stage_view:\n'
     '                    build_app_row(self, app, getattr(self, "_row_index", 0))\n'
     '                    self._row_index = getattr(self, "_row_index", 0) + 1'),
])

# ═══ dedup_ui.py：定位修复 + 前置/主题 ═══
D = "dedup_ui.py"
patch(D, [
    ('    def reveal_sel(self):\n'
     '        for f in self._sel_files()[:3]:\n'
     '            os.system(f\'explorer /select,"{f["path"]}"\')',
     '    def reveal_sel(self):\n'
     '        import subprocess\n'
     '        for f in self._sel_files()[:3]:\n'
     '            path = os.path.normpath(f["path"])\n'
     '            if os.path.isfile(path):\n'
     '                subprocess.Popen(\'explorer /select,"\' + path + \'"\')\n'
     '            elif os.path.isdir(path):\n'
     '                os.startfile(path)'),
])
s = io.open(D, encoding="utf-8").read()
old = '''        self.after(200, lambda: self.attributes("-topmost", False))'''
if old in s:
    new = '''        from ui_theme import popup_front, apply_window_chrome
        popup_front(self, master)
        apply_window_chrome(self)
        self.after(260, lambda: apply_window_chrome(self))
        self.after(200, lambda: self.attributes("-topmost", False))'''
    s = s.replace(old, new, 1)
    io.open(D, "w", encoding="utf-8", newline=NL).write(s)
    OK.append("dedup_ui :: front+chrome")
else:
    MISS.append("dedup_ui :: topmost anchor")

# ═══ migrate_ui.py：前置 + 主题 ═══
G = "migrate_ui.py"
s = io.open(G, encoding="utf-8").read()
old = '''        self.after(200, lambda: self.state("zoomed"))'''
if old in s:
    new = '''        from ui_theme import popup_front, apply_window_chrome
        popup_front(self, master)
        apply_window_chrome(self)
        self.after(260, lambda: apply_window_chrome(self))
        self.after(200, lambda: self.state("zoomed"))'''
    s = s.replace(old, new, 1)
    io.open(G, "w", encoding="utf-8", newline=NL).write(s)
    OK.append("migrate_ui :: front+chrome")
else:
    MISS.append("migrate_ui :: zoomed anchor")

print(NL + "== 结果 ==")
for x in OK:
    print("  OK  ", x[:80])
for x in MISS:
    print("  MISS", x[:80])
