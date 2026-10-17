    def append_log(self, message):
        self.log_queue.append(message)

    def update_progress(self, val):
        self.progress_bar.set(val)

    def manual_check_update(self):
        self.btn_check_update.configure(text='⏳ 检查中...', state='disabled')
        self.append_log('>>> 正在连接云端服务器检测版本更新...')

        def do_check():
            try:
                api_url = f'http://ppsai.chat:5000/api/check_update?version={CURRENT_VERSION}'
                req = urllib.request.Request(api_url, headers={'User-Agent': 'SafeCleanerPro'})
                with urllib.request.urlopen(req, timeout=8) as resp:
                    data = json.loads(resp.read().decode('utf-8'))

                def on_result():
                    self.btn_check_update.configure(text='🔄 检查更新', state='normal')
                    if data.get('has_update'):
                        self.append_log(f">>> 发现新版本 v{data['latest_version']}！正在弹出升级窗口...")
                        self.show_update_dialog(data)
                        return
                    self.append_log(f">>> 当前版本 v{CURRENT_VERSION} 已是最新版本，无需更新。")

                self.after(0, on_result)
            except Exception as e:
                def on_error():
                    self.btn_check_update.configure(text='🔄 检查更新', state='normal')
                    self.append_log('>>> 版本检查失败：网络连接异常或服务器未响应。')

                self.after(0, on_error)

        threading.Thread(target=do_check, daemon=True).start()

    def start_scan(self):
        self.ui_state = 'scanning'
        self.btn_action.configure(state='disabled', text='🔍 正在雷达扫描...')
        self.progress_bar.set(0)

        self.log_box.configure(state='normal')
        self.log_box.delete('0.0', 'end')
        self.log_box.configure(state='disabled')

        self.total_scanned_bytes = 0
        self.total_immune_bytes = 0
        self.total_cleaned_bytes = 0
        self.lbl_scanned_val.configure(text='0.00 B')
        self.lbl_immune_val.configure(text='0.00 B')
        self.lbl_cleaned_val.configure(text='0.00 B')

        self.render_scroll_list()

        threading.Thread(target=self._scan_thread, daemon=True).start()

    def _scan_thread(self):
        selected_drives = self.get_selected_drives()
        drives_str = ', '.join(f'{d}:' for d in sorted(selected_drives))
        self.append_log('>>> 启动引擎: SafeCleaner Pro 物理雷达深度分析...')
        self.append_log(f'>>> 目标磁盘: [{drives_str}]')
        self.append_log('>>> 安全协议: 核心路径物理指纹加密脱敏已开启。')
        time.sleep(0.3)

        from cleaner_core import get_app_size

        scan_apps = self.get_filtered_apps()
        total_items = len(scan_apps) if scan_apps else 1
        for idx, app in enumerate(scan_apps):
            self.append_log(f'[*] 正在分析: {app["name"]}')

            if not app['immune']:
                from cleaner_core import scan_app_files
                for filepath, _ in scan_app_files(app, limit=5000):
                    if is_personal_file(filepath):
                        self.skipped_files.add(filepath)

            app_size = get_app_size(app)
            self.sizes[app['id']] = app_size

            if app['immune']:
                self.total_immune_bytes += app_size
            else:
                self.total_scanned_bytes += app_size

            self.lbl_scanned_val.configure(text=format_size(self.total_scanned_bytes))
            self.lbl_immune_val.configure(text=format_size(self.total_immune_bytes))
            self.progress_bar.set((idx + 1) / total_items)
            time.sleep(0.04)

        self.append_log(f'\n[✓] 深度物理雷达扫描完成！发现可清理废料: {format_size(self.total_scanned_bytes)}')
        self.append_log(f'🛡️ 自动免疫锁定大模型上下文与微信数据目录: {format_size(self.total_immune_bytes)}')
        self.ui_state = 'safe_clean_ready'

        def update_ui_after_scan():
            self.btn_action.configure(
                state='normal',
                text='🟢 开始安全清理',
                fg_color='#10b981',
                hover_color='#34d399'
            )
            self.render_scroll_list()

        self.after(0, update_ui_after_scan)

    def start_cleanup_flow(self, clean_type):
        hwid = get_hwid()
        license_key, _ = load_license_key()

        valid = False
        active_hwid = hwid
        if license_key:
            if verify_license(hwid, license_key):
                valid = True
            else:
                from hwid_utils import get_hwid_wmic
                hwid_wmic = get_hwid_wmic()
                if verify_license(hwid_wmic, license_key):
                    active_hwid = hwid_wmic
                    valid = True

        if not valid:
            self.show_auth_dialog(hwid, clean_type)
            return

        self.append_log('>>> 授权验证成功：尊贵的特权用户，已放行底层物理清除权限！')
        if clean_type == 'risk':
            self.show_risk_confirmation(clean_type, lambda: self.execute_cleaning(clean_type))
            return

        self.execute_cleaning(clean_type)

    def execute_cleaning(self, clean_type):
        self.btn_action.configure(state='disabled', text='🧹 正在物理抹除中...')

        self.progress_bar.set(0)
        self.progress_bar.configure(mode='indeterminate')
        self.progress_bar.start()

        threading.Thread(target=self._clean_thread, args=(clean_type,), daemon=True).start()

    def _clean_thread(self, clean_type):
        self.append_log(f">>> 启动特权模式: 执行物理底层粉碎 [{'安全清理' if clean_type == 'safe' else '风险清理'}]...")
        self.total_cleaned_bytes = 0

        cleanable_apps = []
        for app in self.get_filtered_apps():
            if app['immune']:
                continue
            chk_var = self.app_checkbox_vars.get(app['id'])
            if not chk_var:
                continue
            if chk_var.get() != 1:
                continue
            if app['risk_level'] != clean_type:
                continue
            cleanable_apps.append(app)

        if not cleanable_apps:
            self.append_log('\n[!] 没有勾选任何属于当前清理分类的软件项。')
            self.after(0, lambda: self.on_clean_finished(clean_type, 0))
            return

        our_meipass = getattr(sys, '_MEIPASS', None)
        if our_meipass:
            our_meipass = os.path.abspath(our_meipass).lower()

        for app in cleanable_apps:
            app_id = app['id']
            self.append_log(f'[*] 正在抹除: {app["name"]}')

            resolved_paths = get_resolved_paths(app.get('paths', []))
            deleted_size = 0
            for p in resolved_paths:
                if our_meipass and our_meipass in os.path.abspath(p).lower():
                    continue
                deleted_size += clean_directory(p, self.append_log, self.skipped_files)

            self.sizes[app_id] = 0
            if app_id in self.app_rows:
                self.app_rows[app_id]['size'].configure(text='0.00 B')
                self.app_rows[app_id]['badge'].configure(text='✨ 已安全净化', text_color='#22c55e', fg_color='#064e3b')

            self.total_cleaned_bytes += deleted_size
            self.lbl_cleaned_val.configure(text=format_size(self.total_cleaned_bytes))
            time.sleep(0.3)

        self.after(0, lambda: self.on_clean_finished(clean_type, self.total_cleaned_bytes))

    def check_for_updates(self):
        def run_check():
            try:
                url = f'http://ppsai.chat/api/check_update?version={CURRENT_VERSION}'
                req = urllib.request.Request(url, headers={'User-Agent': 'SafeCleanerPro-Client'})
                with urllib.request.urlopen(req, timeout=4) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode('utf-8'))
                        if data.get('has_update'):
                            self.after(0, lambda: self.show_update_dialog(data))
            except Exception as e:
                print(f'Check update failed: {e}')

        threading.Thread(target=run_check, daemon=True).start()
