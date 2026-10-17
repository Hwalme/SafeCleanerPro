"""Only entry point supported for protected releases."""
import sys

from secure_rules import RulePackError, initialise_release


def run():
    self_test = sys.argv[1:] == ["--self-test"]
    try:
        initialise_release()  # Before UI imports, scanning or any deletion.
        import main
        if self_test:
            # Exercise real adapters and all lazily opened workstation modules.
            import library_rules
            import trace_rules_360
            import cleaner_rules
            import deep_cache
            import dedup_ui
            import migrate_ui
            import deep_ui
            if not library_rules._load_lib() or trace_rules_360._load_json() is None:
                raise RulePackError("Rule adapter self-test failed")
            if not cleaner_rules.RULES or not deep_cache.PROTECTED_AI_DIRS:
                raise RulePackError("Core module self-test failed")
            return 0
        app = main.SafeCleanerApp()
        app.withdraw()
        main.SplashScreen(app)
        app.mainloop()
        return 0
    except RulePackError:
        if not self_test:
            from tkinter import messagebox
            messagebox.showerror("SafeCleanerPro", "规则包缺失或校验失败，程序已停止。请重新下载完整的正式版本。")
        return 2


if __name__ == "__main__":
    sys.exit(run())
