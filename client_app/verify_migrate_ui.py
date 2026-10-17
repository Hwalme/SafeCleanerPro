# -*- coding: utf-8 -*-
"""migrate_ui 真实环境 GUI 冒烟：实例化迁移台，跑一轮真实扫描（只读，不迁移）。

校验：
  1. 窗口能构建、扫描线程能完成
  2. 表格行数 == 常规目录 + build_catalog() 命中数
  3. 全选待迁按钮逻辑（含可统一的他迁/重复项）、迁移按钮可用性
  4. 常规目录分组置顶、目标根默认含「C盘迁移」
  5. 不触发任何写操作（不点迁移）
"""
import sys
import time

import customtkinter as ctk

import migrate_core as mc
from migrate_ui import _MIGRATABLE, MemoryMigrateWindow


def main():
    class _StubOwner(ctk.CTk):
        """主窗口桩：只提供 brand_ui.workspace_available 需要的状态。"""
        safe_state = "idle"
        risk_state = "idle"

        def __init__(self):
            super().__init__()
            self.withdraw()
            self._tool_windows = {}

    app = _StubOwner()
    win = MemoryMigrateWindow(app)

    deadline = time.time() + 300
    while time.time() < deadline:
        win.update()
        if not win.working:
            break
        time.sleep(0.03)
    else:
        print("[FAIL] 扫描超时")
        sys.exit(1)

    expect = len(mc.build_shell_items()) + len(mc.build_catalog())
    groups = win.tree.get_children("")
    rows = sum(len(win.tree.get_children(g)) for g in groups)
    first_group = groups[0] if groups else ""
    ok_rows = (rows == expect and len(groups) >= 4
               and first_group == "g:常规目录")
    print(f"[{'PASS' if ok_rows else 'FAIL'}] 分组 {len(groups)} 个 / "
          f"项目行 {rows} / 期望 {expect} / 首分组 {first_group}")

    migratable = {it["id"] for it in win.items
                  if win.info.get(it["id"], {}).get("status") in _MIGRATABLE}
    win._select_all("clean")
    ok_sel = win.checked == migratable
    print(f"[{'PASS' if ok_sel else 'FAIL'}] 全选待迁 = {len(win.checked)} 项"
          f"（含可统一的他迁/重复项）")

    mig_btn_state = win.btn_migrate.cget("state")
    ok_btn = (str(mig_btn_state) == "normal") if migratable else True
    print(f"[{'PASS' if ok_btn else 'FAIL'}] 迁移按钮状态 = {mig_btn_state}")

    root_shell = win._selected_root_shell()
    root_ai = win._selected_root_ai()
    cfg = mc.load_target_config()
    # 两条默认总路径互相独立：常规目录/AI记忆 各有各的根（记忆位置优先）
    ok_root = (
        bool(root_shell) and bool(root_ai)
        and root_shell != root_ai
        and (root_shell == cfg.get("root_shell")
             or root_shell.endswith(os.path.join("C盘迁移", "常规目录")))
        and (root_ai == cfg.get("root_ai")
             or root_ai.endswith(os.path.join("C盘迁移", "AI记忆"))))
    print(f"[{'PASS' if ok_root else 'FAIL'}] 双目标根独立："
          f"常规目录={root_shell} · AI记忆={root_ai}")

    # 右键自定义子项目标：设置后 _effective_target 精确指向、行内可见
    if win.items:
        it0 = next((x for x in win.items
                    if win.info.get(x["id"], {}).get("status") in _MIGRATABLE),
                   None)
        if it0:
            probe = os.path.join(os.path.expanduser("~"), "_scp_probe_tgt")
            win.custom_targets[it0["id"]] = probe
            ok_eff = win._effective_target(it0) == probe
            win.custom_targets.pop(it0["id"], None)
            print(f"[{'PASS' if ok_eff else 'FAIL'}] 子项目标自定义 "
                  f"（{it0['name']} → 精确路径生效）")
        else:
            ok_eff = True
    else:
        ok_eff = False

    drive_ok = bool(mc.list_target_drives())
    print(f"[{'PASS' if drive_ok else 'FAIL'}] 目标盘候选 = {mc.list_target_drives()}")

    onedrive = [it["name"] for it in win.items
                if win.info.get(it["id"], {}).get("status") == "onedrive"]
    dup = [it["name"] for it in win.items
           if win.info.get(it["id"], {}).get("status") == "foreign_dup"]
    print(f"[INFO] OneDrive 管理（不可迁）= {onedrive}")
    print(f"[INFO] 检测到重复目录（建议统一）= {dup}")

    win._select_all(None)
    win.destroy()
    app.destroy()

    fails = [n for n, v in [("rows", ok_rows), ("select", ok_sel),
                            ("button", ok_btn), ("roots", ok_root),
                            ("custom", ok_eff),
                            ("drives", drive_ok)] if not v]
    print(f"===== GUI 冒烟：{6 - len(fails)} 通过 / {len(fails)} 失败 =====")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
