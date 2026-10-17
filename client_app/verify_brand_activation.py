# -*- coding: utf-8 -*-
"""Offline activation/scope UI regression. No service calls or license writes."""
import time
from unittest.mock import patch
import customtkinter as ctk
import main as m
import brand_ui as ui
from verify_brand_ui import pump, capture, check


def descendants(widget):
    for child in widget.winfo_children():
        yield child
        yield from descendants(child)


def main():
    m.SafeCleanerApp.check_for_updates = lambda self: None
    app = m.SafeCleanerApp(); app.build_ui(); pump(app)
    errors = []
    app.report_callback_exception = lambda *info: errors.append(str(info[1]))
    app.safe_state = app.risk_state = "ready"
    app.safe_bytes = 1000
    app.sizes = {a["id"]: 123 for a in app.apps_data}
    app.on_drive_changed(); pump(app)
    check("changed scope requires fresh scan", app.safe_state == app.risk_state == "idle")
    check("stale findings invalidated", not any(app.sizes.values()) and app.safe_bytes == 0)

    with patch("urllib.request.urlopen", side_effect=OSError("offline UI test")), \
         patch.object(m, "verify_license", side_effect=lambda hwid, key: key == "VALID-DEMO-ONLY"), \
         patch.object(m, "save_license_key", return_value=True) as save, \
         patch("hwid_utils.get_hwid_wmic", return_value="DEMO-HWID"), \
         patch.object(app, "execute_cleaning") as execute:
        start = time.monotonic()
        win = ui.show_auth_dialog(app, "DEMO-HWID", "safe")
        check("activation opens without network blocking", time.monotonic() - start < 2)
        controls = list(descendants(win))
        entry = next(w for w in controls if isinstance(w, ctk.CTkEntry))
        submit = next(w for w in controls if isinstance(w, ctk.CTkButton) and w.cget("text") == "验证并继续")
        submit.invoke(); pump(app)
        check("empty key receives inline feedback", any(isinstance(w, ctk.CTkLabel) and w.cget("text") == "请先粘贴授权码。" for w in controls))
        entry.insert(0, "INVALID-DEMO-ONLY"); submit.invoke(); pump(app, .4)
        check("invalid key cannot start cleaning", execute.call_count == 0 and save.call_count == 0)
        check("invalid key can retry", submit.cget("state") == "normal")
        capture(win, "desktop-activation.png")
        entry.delete(0, "end"); entry.insert(0, "VALID-DEMO-ONLY"); submit.invoke(); pump(app, .4)
        check("valid key saved once", save.call_count == 1)
        check("verified activation resumes selected flow", execute.call_args.args == ("safe",))
        check("activation polling cancels on close", not app.polling_active)
    check("no activation callback errors", not errors)
    fixture = dict(id="file-demo", name="文件排除验收", paths=[], risk_level="safe", risk_desc="演示数据，仅验证勾选排除。")
    path = r"C:\PPSAI-UI-TEST\cache.tmp"
    app.file_cache[fixture["id"]] = [(path, 4096)]
    import ui_theme
    ui_theme.show_file_viewer(app, fixture); pump(app, .4)
    viewer = next(w for w in app.winfo_children() if isinstance(w, ctk.CTkToplevel))
    checkbox = next(w for w in descendants(viewer) if isinstance(w, ctk.CTkCheckBox))
    checkbox.toggle()
    check("individual file exclusion reaches engine skip set", path in app.skipped_files)
    checkbox.toggle()
    check("individual file can be included again", path not in app.skipped_files)
    capture(viewer, "desktop-file-exclusions.png")
    viewer.destroy()
    app.destroy()
    print("Activation and changed-scope regression passed.", flush=True)


if __name__ == "__main__":
    main()
