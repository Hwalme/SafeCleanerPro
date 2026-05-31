import os
import sys
import base64
import time
import threading
import json
import io
import urllib.request
import urllib.parse
from PIL import Image
import customtkinter as ctk
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

from hwid_utils import get_hwid
from cleaner_core import (
    get_supported_apps, get_size, format_size, clean_directory,
    obfuscate_path, get_resolved_paths
)

# Theme Settings
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

CURRENT_VERSION = "3.6"

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
    try:
        public_key = RSA.import_key(PUBLIC_KEY_PEM)
        signature = base64.b64decode(license_key_b64)
        h = SHA256.new(hwid.encode('utf-8'))
        pkcs1_15.new(public_key).verify(h, signature)
        return True
    except:
        return False

def get_license_paths():
    paths = ["license.key"]
    appdata_local = os.environ.get('LOCALAPPDATA')
    if appdata_local:
        app_dir = os.path.join(appdata_local, 'SafeCleanerPro')
        paths.append(os.path.join(app_dir, 'license.key'))
    return paths

def load_license_key():
    for p in get_license_paths():
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    key = f.read().strip()
                    if key:
                        return key, p
            except:
                pass
    return "", ""

def save_license_key(key):
    try:
        with open("license.key", "w") as f:
            f.write(key)
    except Exception:
        pass
    appdata_local = os.environ.get('LOCALAPPDATA')
    if appdata_local:
        try:
            app_dir = os.path.join(appdata_local, 'SafeCleanerPro')
            os.makedirs(app_dir, exist_ok=True)
            with open(os.path.join(app_dir, 'license.key'), "w") as f:
                f.write(key)
        except Exception:
            pass

class SafeCleanerApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title(f"SafeCleaner Pro - 终极安全进化版 v{CURRENT_VERSION}")
        self.geometry("1150x760")
        self.resizable(False, False)
        
        # State variables
        self.apps_data = get_supported_apps()
        self.sizes = {app["id"]: 0 for app in self.apps_data}
        self.total_scanned_bytes = 0
        self.total_immune_bytes = 0
        self.total_cleaned_bytes = 0
        self.skipped_files = set()  # Set of files skipped by details toggles
        
        self.build_ui()
        
        # Check updates in background after UI is loaded
        self.after(1000, self.check_for_updates)
        
    def build_ui(self):
        # Configure Grid Layout (2 columns: Sidebar & Main Panel)
        self.grid_columnconfigure(0, weight=1, minsize=280)
        self.grid_columnconfigure(1, weight=3, minsize=870)
        self.grid_rowconfigure(0, weight=1)
        
        # ==========================================
        # LEFT SIDEBAR FRAME
        # ==========================================
        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color="#0f172a")
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")
        self.sidebar_frame.grid_rowconfigure(5, weight=1) # spacer
        
        # Logo/Title
        self.logo_label = ctk.CTkLabel(
            self.sidebar_frame, 
            text="SafeCleaner Pro", 
            font=ctk.CTkFont(family="Outfit", size=28, weight="bold"), 
            text_color="#00f0ff"
        )
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 8))
        
        self.sub_logo = ctk.CTkLabel(
            self.sidebar_frame, 
            text="极客级深度物理引擎", 
            font=ctk.CTkFont(size=13), 
            text_color="#64748b"
        )
        self.sub_logo.grid(row=1, column=0, padx=20, pady=(0, 20))
        
        # Stat Card 1: Scanned Size
        self.card_scanned = ctk.CTkFrame(self.sidebar_frame, fg_color="#1e293b", corner_radius=10, height=95)
        self.card_scanned.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
        self.card_scanned.grid_propagate(False)
        ctk.CTkLabel(self.card_scanned, text="🔴 扫描垃圾总容量", font=ctk.CTkFont(size=13), text_color="#ef4444").pack(pady=(15, 2))
        self.lbl_scanned_val = ctk.CTkLabel(self.card_scanned, text="0.00 B", font=ctk.CTkFont(size=24, weight="bold"), text_color="#f87171")
        self.lbl_scanned_val.pack()
        
        # Stat Card 2: Immune Size
        self.card_immune = ctk.CTkFrame(self.sidebar_frame, fg_color="#1e293b", corner_radius=10, height=95)
        self.card_immune.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
        self.card_immune.grid_propagate(False)
        ctk.CTkLabel(self.card_immune, text="🔒 核心安全锁定保护", font=ctk.CTkFont(size=13), text_color="#3b82f6").pack(pady=(15, 2))
        self.lbl_immune_val = ctk.CTkLabel(self.card_immune, text="0.00 B", font=ctk.CTkFont(size=24, weight="bold"), text_color="#60a5fa")
        self.lbl_immune_val.pack()
        
        # Stat Card 3: Cleaned Size
        self.card_cleaned = ctk.CTkFrame(self.sidebar_frame, fg_color="#1e293b", corner_radius=10, height=95)
        self.card_cleaned.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
        self.card_cleaned.grid_propagate(False)
        ctk.CTkLabel(self.card_cleaned, text="🟢 安全净化释放容量", font=ctk.CTkFont(size=13), text_color="#22c55e").pack(pady=(15, 2))
        self.lbl_cleaned_val = ctk.CTkLabel(self.card_cleaned, text="0.00 B", font=ctk.CTkFont(size=24, weight="bold"), text_color="#4ade80")
        self.lbl_cleaned_val.pack()
        
        # Spacer
        self.sidebar_spacer = ctk.CTkLabel(self.sidebar_frame, text="")
        self.sidebar_spacer.grid(row=5, column=0, sticky="nsew")
        
        # HWID Label in sidebar
        self.lbl_hwid = ctk.CTkLabel(
            self.sidebar_frame, 
            text=f"ID: {get_hwid()}", 
            font=ctk.CTkFont(family="Consolas", size=11), 
            text_color="#475569"
        )
        self.lbl_hwid.grid(row=6, column=0, padx=15, pady=(5, 15))
        
        # ==========================================
        # RIGHT MAIN PANEL FRAME
        # ==========================================
        self.main_frame = ctk.CTkFrame(self, fg_color="#020617", corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1) # scrollable list grows
        
        # Main Header / Title
        self.header_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, padx=25, pady=(20, 10), sticky="ew")
        
        self.main_title = ctk.CTkLabel(
            self.header_frame, 
            text="🛡️ 雷达物理安全盾 & 优化矩阵", 
            font=ctk.CTkFont(size=22, weight="bold"), 
            text_color="#f8fafc"
        )
        self.main_title.pack(side="left")
        
        # Scrollable list for compatible software
        self.scroll_frame = ctk.CTkScrollableFrame(self.main_frame, label_text="清理项目细分管理与可选状态", label_font=ctk.CTkFont(size=14, weight="bold"), fg_color="#090d16")
        self.scroll_frame.grid(row=2, column=0, padx=25, pady=5, sticky="nsew")
        self.scroll_frame.grid_columnconfigure(1, weight=1)
        
        # Build rows in scroll list
        self.app_rows = {}
        self.app_checkboxes = {}
        self.app_checkbox_vars = {}
        
        for idx, app in enumerate(self.apps_data):
            row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#111827" if idx % 2 == 0 else "#1f2937", corner_radius=6)
            row_frame.pack(fill="x", padx=5, pady=4)
            
            # Left container to host check/lock, icon and name
            left_container = ctk.CTkFrame(row_frame, fg_color="transparent")
            left_container.pack(side="left", fill="y", padx=5)
            
            if app["immune"]:
                lbl_lock = ctk.CTkLabel(left_container, text="🔒", font=ctk.CTkFont(size=14), text_color="#3b82f6")
                lbl_lock.pack(side="left", padx=(15, 8))
            else:
                var = ctk.IntVar(value=1 if app["risk_level"] == "safe" else 0)
                self.app_checkbox_vars[app["id"]] = var
                
                chk = ctk.CTkCheckBox(left_container, text="", variable=var, width=20, height=20)
                chk.pack(side="left", padx=(15, 8))
                self.app_checkboxes[app["id"]] = chk
            
            # Icon
            lbl_icon = ctk.CTkLabel(left_container, text=app["icon"], font=ctk.CTkFont(size=22))
            lbl_icon.pack(side="left", padx=(6, 6), pady=10)
            
            # App Name
            lbl_name = ctk.CTkLabel(left_container, text=app["name"], font=ctk.CTkFont(size=14, weight="bold"), text_color="#f3f4f6")
            lbl_name.pack(side="left", padx=6, pady=10)
            
            # Right Layout - We pack from right to left
            # View details button (only for non-immune)
            if not app["immune"]:
                def make_details_cmd(a=app):
                    return lambda: self.show_file_viewer(a)
                btn_details = ctk.CTkButton(
                    row_frame, 
                    text="📄 查看文件", 
                    font=ctk.CTkFont(size=12),
                    width=90, 
                    height=28, 
                    fg_color="#1e293b", 
                    hover_color="#334155",
                    command=make_details_cmd(app)
                )
                btn_details.pack(side="right", padx=(6, 15), pady=10)
            else:
                # Spacer
                lbl_spacer = ctk.CTkLabel(row_frame, text="", width=90)
                lbl_spacer.pack(side="right", padx=(6, 15), pady=10)
                
            # Status Badge
            badge_text = "🛡️ 锁定保护" if app["immune"] else ("🧹 安全清理" if app["risk_level"] == "safe" else "⚠️ 风险清理")
            badge_color = "#3b82f6" if app["immune"] else ("#10b981" if app["risk_level"] == "safe" else "#ef4444")
            badge_bg = "#172554" if app["immune"] else ("#064e3b" if app["risk_level"] == "safe" else "#450a0a")
            
            lbl_badge = ctk.CTkLabel(
                row_frame, 
                text=badge_text, 
                font=ctk.CTkFont(size=12, weight="bold"), 
                text_color=badge_color,
                fg_color=badge_bg,
                corner_radius=4,
                width=100,
                height=26
            )
            lbl_badge.pack(side="right", padx=8, pady=10)
            
            # Size value
            lbl_size = ctk.CTkLabel(row_frame, text="等待扫描...", font=ctk.CTkFont(family="Consolas", size=13), text_color="#9ca3af")
            lbl_size.pack(side="right", padx=8, pady=10)
            
            self.app_rows[app["id"]] = {
                "size": lbl_size,
                "badge": lbl_badge,
                "frame": row_frame
            }
            
        # Controls Frame (Buttons & Progress)
        self.control_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.control_frame.grid(row=3, column=0, padx=25, pady=15, sticky="ew")
        
        self.progress_bar = ctk.CTkProgressBar(self.control_frame, width=260)
        self.progress_bar.pack(side="left", padx=(0, 20))
        self.progress_bar.set(0)
        
        self.btn_scan = ctk.CTkButton(
            self.control_frame, 
            text="🛡️ 开始深度扫描", 
            font=ctk.CTkFont(size=14, weight="bold"),
            width=140, 
            height=40, 
            command=self.start_scan
        )
        self.btn_scan.pack(side="right", padx=4)
        
        self.btn_safe_clean = ctk.CTkButton(
            self.control_frame, 
            text="🟢 安全清理", 
            font=ctk.CTkFont(size=14, weight="bold"),
            width=140, 
            height=40, 
            fg_color="#10b981", 
            hover_color="#34d399", 
            state="disabled", 
            command=lambda: self.start_cleanup_flow("safe")
        )
        self.btn_safe_clean.pack(side="right", padx=4)
        
        self.btn_risk_clean = ctk.CTkButton(
            self.control_frame, 
            text="🔴 风险清理", 
            font=ctk.CTkFont(size=14, weight="bold"),
            width=140, 
            height=40, 
            fg_color="#ef4444", 
            hover_color="#f87171", 
            state="disabled", 
            command=lambda: self.start_cleanup_flow("risk")
        )
        self.btn_risk_clean.pack(side="right", padx=4)
        
        # Terminal/Log console frame
        self.log_frame = ctk.CTkFrame(self.main_frame, fg_color="#090d16", corner_radius=8)
        self.log_frame.grid(row=4, column=0, padx=25, pady=(5, 20), sticky="ew")
        
        self.log_box = ctk.CTkTextbox(
            self.log_frame, 
            height=140, 
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color="transparent",
            text_color="#10b981"
        )
        self.log_box.pack(fill="both", expand=True, padx=12, pady=8)
        self.log_box.configure(state="disabled")
        
        self.append_log("系统安全防护正常就绪。等待执行雷达深度扫描...")
        
    def append_log(self, message):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", message + "\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")
        
    def update_progress(self, val):
        self.progress_bar.set(val)
        
    def start_scan(self):
        self.btn_scan.configure(state="disabled")
        self.btn_safe_clean.configure(state="disabled")
        self.btn_risk_clean.configure(state="disabled")
        self.progress_bar.set(0)
        
        # Clear log console
        self.log_box.configure(state="normal")
        self.log_box.delete("0.0", "end")
        self.log_box.configure(state="disabled")
        
        self.total_scanned_bytes = 0
        self.total_immune_bytes = 0
        self.lbl_scanned_val.configure(text="0.00 B")
        self.lbl_immune_val.configure(text="0.00 B")
        
        for app_id, row in self.app_rows.items():
            row["size"].configure(text="正在分析...")
            row["badge"].configure(text="🔍 正在扫描", text_color="#ffa502", fg_color="#431407")
            
        threading.Thread(target=self._scan_thread, daemon=True).start()
        
    def _scan_thread(self):
        self.append_log(">>> 启动引擎: SafeCleaner Pro 物理雷达深度分析...")
        self.append_log(">>> 安全协议: 核心路径物理指纹加密脱敏已开启。")
        time.sleep(0.3)
        
        from cleaner_core import get_app_size
        
        total_items = len(self.apps_data)
        for idx, app in enumerate(self.apps_data):
            self.append_log(f"[*] 正在分析: {app['name']}")
            
            app_size = get_app_size(app)
            size_str = format_size(app_size)
            self.app_rows[app["id"]]["size"].configure(text=size_str)
            
            if app["immune"]:
                self.app_rows[app["id"]]["badge"].configure(text="🛡️ 已锁定", text_color="#3b82f6", fg_color="#172554")
                self.total_immune_bytes += app_size
            else:
                if app_size > 0:
                    badge_text = "🧹 待安全清理" if app["risk_level"] == "safe" else "⚠️ 待风险清理"
                    badge_color = "#10b981" if app["risk_level"] == "safe" else "#ef4444"
                    badge_bg = "#064e3b" if app["risk_level"] == "safe" else "#450a0a"
                    self.app_rows[app["id"]]["badge"].configure(text=badge_text, text_color=badge_color, fg_color=badge_bg)
                else:
                    self.app_rows[app["id"]]["badge"].configure(text="✨ 无残留垃圾", text_color="#10b981", fg_color="#064e3b")
            
            self.sizes[app["id"]] = app_size
            self.total_scanned_bytes += app_size
            
            self.lbl_scanned_val.configure(text=format_size(self.total_scanned_bytes))
            self.lbl_immune_val.configure(text=format_size(self.total_immune_bytes))
            
            self.progress_bar.set((idx + 1) / total_items)
            time.sleep(0.1) # Smooth UX animation
            
        self.append_log(f"\n[✓] 深度物理雷达扫描完成！发现可清理废料: {format_size(self.total_scanned_bytes - self.total_immune_bytes)}")
        self.append_log(f"🛡️ 自动免疫锁定大模型上下文与微信数据目录: {format_size(self.total_immune_bytes)}")
        
        self.btn_scan.configure(state="normal")
        self.btn_safe_clean.configure(state="normal")
        self.btn_risk_clean.configure(state="normal")
        
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
        else:
            self.append_log(">>> 授权验证成功：尊贵的特权用户，已放行底层物理清除权限！")
            if clean_type == "risk":
                self.show_risk_confirmation(lambda: self.execute_cleaning(clean_type))
            else:
                self.execute_cleaning(clean_type)
                
    def show_auth_dialog(self, hwid, clean_type):
        dialog = ctk.CTkToplevel(self)
        dialog.title("物理级操作安全拦截")
        dialog.geometry("520x550")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="⚠️ 安全拦截: 需要数字签名授权", font=ctk.CTkFont(size=18, weight="bold"), text_color="#ef4444").pack(pady=(15, 5))
        
        desc = ("由于底层物理净化需要修改和删除系统内核缓存文件，\n"
                "必须激活特权数字证书方可继续。安全防护网已自动拦截此操作。")
        ctk.CTkLabel(dialog, text=desc, font=ctk.CTkFont(size=11), text_color="#cbd5e1").pack(pady=2)
        
        # QR Frame
        qr_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        qr_frame.pack(pady=5)
        
        qr_loaded = False
        try:
            mobile_url = f"http://ppsai.chat/safecleaner/pay.html?hwid={hwid}"
            qr_api_url = f"http://ppsai.chat/api/qrcode?data={urllib.parse.quote(mobile_url)}"
            
            req = urllib.request.Request(qr_api_url, headers={'User-Agent': 'SafeCleanerPro-Client'})
            with urllib.request.urlopen(req, timeout=4) as response:
                qr_img_data = response.read()
                
            img = Image.open(io.BytesIO(qr_img_data))
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(150, 150))
            
            lbl_qr_img = ctk.CTkLabel(qr_frame, image=ctk_img, text="")
            lbl_qr_img.pack()
            qr_loaded = True
        except Exception as e:
            ctk.CTkLabel(qr_frame, text="[⚠️ 无法加载扫码二维码，请确保网络连接正常]", text_color="#ef4444", font=ctk.CTkFont(size=11)).pack()
            
        guide_text = "📱 极速推荐：请使用手机微信/支付宝扫描上方二维码\n在手机上完成付款核销，电脑客户端将 1 秒钟瞬间解锁直接运行！"
        ctk.CTkLabel(dialog, text=guide_text, font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(pady=2)
        
        status_label = ctk.CTkLabel(dialog, text="🔄 正在实时感应云端付款状态，支付成功后此窗口将全自动解锁...", font=ctk.CTkFont(size=10), text_color="#10b981")
        status_label.pack(pady=2)
        
        hwid_frame = ctk.CTkFrame(dialog, fg_color="#1e293b", height=45)
        hwid_frame.pack(pady=5, padx=40, fill="x")
        hwid_frame.pack_propagate(False)
        ctk.CTkLabel(hwid_frame, text=f"设备 ID 指纹: {hwid}", font=ctk.CTkFont(family="Consolas", size=10), text_color="#94a3b8").pack(pady=10)
        
        fallback_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        fallback_frame.pack(pady=5, padx=40, fill="x")
        
        entry_key = ctk.CTkEntry(fallback_frame, placeholder_text="或者在此手动粘贴激活秘钥 (License Key)...", justify="center", font=ctk.CTkFont(size=11))
        entry_key.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        def on_verify():
            key = entry_key.get().strip()
            valid = False
            active_hwid = hwid
            if verify_license(hwid, key):
                valid = True
            else:
                from hwid_utils import get_hwid_wmic
                hwid_wmic = get_hwid_wmic()
                if verify_license(hwid_wmic, key):
                    active_hwid = hwid_wmic
                    valid = True
                    
            if valid:
                save_license_key(key)
                self.polling_active = False
                dialog.destroy()
                self.append_log(">>> 数字签名核销通过！License 代码已存盘本地与全局目录。")
                if clean_type == "risk":
                    self.show_risk_confirmation(lambda: self.execute_cleaning(clean_type))
                else:
                    self.execute_cleaning(clean_type)
            else:
                self.append_log(">>> 校验错误: 授权码无效或与当前 HWID 物理指纹不匹配。")
                
        btn_verify = ctk.CTkButton(fallback_frame, text="手动验证", width=80, font=ctk.CTkFont(weight="bold"), fg_color="#22c55e", hover_color="#4ade80", command=on_verify)
        btn_verify.pack(side="right")
        
        self.polling_active = True
        
        def poll_status():
            url = f"http://ppsai.chat/api/check_activation?hwid={hwid}"
            while self.polling_active and dialog.winfo_exists():
                try:
                    req = urllib.request.Request(url, headers={'User-Agent': 'SafeCleanerPro-Client'})
                    with urllib.request.urlopen(req, timeout=3) as response:
                        if response.status == 200:
                            res_data = json.loads(response.read().decode('utf-8'))
                            if res_data.get("activated") and res_data.get("license_key"):
                                key = res_data["license_key"]
                                
                                valid = False
                                active_hwid = hwid
                                if verify_license(hwid, key):
                                    valid = True
                                else:
                                    from hwid_utils import get_hwid_wmic
                                    hwid_wmic = get_hwid_wmic()
                                    if verify_license(hwid_wmic, key):
                                        active_hwid = hwid_wmic
                                        valid = True
                                        
                                if valid:
                                    save_license_key(key)
                                    self.polling_active = False
                                    
                                    def auto_activate():
                                        dialog.destroy()
                                        self.append_log(">>> 云端自动感应核销成功！数字签名证书已下载并自动部署！")
                                        if clean_type == "risk":
                                            self.show_risk_confirmation(lambda: self.execute_cleaning(clean_type))
                                        else:
                                            self.execute_cleaning(clean_type)
                                    self.after(0, auto_activate)
                                    break
                except:
                    pass
                time.sleep(3)
                
        threading.Thread(target=poll_status, daemon=True).start()
        
        def on_close():
            self.polling_active = False
            dialog.destroy()
        dialog.protocol("WM_DELETE_WINDOW", on_close)

    def show_risk_confirmation(self, on_confirm):
        dialog = ctk.CTkToplevel(self)
        dialog.title("风险清理安全确认")
        dialog.geometry("520x280")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog, 
            text="⚠️ 高风险清理警告", 
            font=ctk.CTkFont(size=20, weight="bold"), 
            text_color="#ef4444"
        ).pack(pady=(20, 10))
        
        msg_text = (
            "风险清理将彻底物理删除已勾选的高风险垃圾项目\n"
            "(这可能包含微信已下载图片视频、本地大模型权重或Adobe设计软件暂存)\n"
            "建议清理前使用[查看文件]功能预览要删除的具体路径。\n"
            "\n是否确认开始物理深度粉碎？"
        )
        ctk.CTkLabel(
            dialog, 
            text=msg_text, 
            font=ctk.CTkFont(size=13), 
            text_color="#cbd5e1",
            justify="center"
        ).pack(pady=10)
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        def confirm():
            dialog.destroy()
            on_confirm()
            
        def cancel():
            dialog.destroy()
            
        ctk.CTkButton(
            btn_frame, 
            text="确认物理粉碎", 
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#ef4444", 
            hover_color="#f87171",
            width=140,
            height=36,
            command=confirm
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame, 
            text="我再想想", 
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#475569", 
            hover_color="#64748b",
            width=140,
            height=36,
            command=cancel
        ).pack(side="left", padx=10)

    def show_file_viewer(self, app):
        dialog = ctk.CTkToplevel(self)
        dialog.title(f"文件详情预览 - {app['name']}")
        dialog.geometry("780x560")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog, 
            text=f"📂 {app['name']} - 文件清理清单", 
            font=ctk.CTkFont(size=18, weight="bold"), 
            text_color="#f8fafc"
        ).pack(pady=(15, 5))
        
        risk_color = "#ef4444" if app["risk_level"] == "risk" else "#10b981"
        risk_label_text = f"风险等级: {'⚠️ 高风险项目' if app['risk_level'] == 'risk' else '🟢 安全清理项目'}"
        
        info_frame = ctk.CTkFrame(dialog, fg_color="#0f172a", height=65)
        info_frame.pack(fill="x", padx=20, pady=5)
        info_frame.pack_propagate(False)
        
        ctk.CTkLabel(
            info_frame, 
            text=risk_label_text, 
            font=ctk.CTkFont(size=13, weight="bold"), 
            text_color=risk_color
        ).pack(anchor="w", padx=15, pady=(8, 2))
        
        ctk.CTkLabel(
            info_frame, 
            text=f"安全提示: {app.get('risk_desc', '本项清理无任何数据风险。')}", 
            font=ctk.CTkFont(size=12), 
            text_color="#94a3b8"
        ).pack(anchor="w", padx=15, pady=(0, 8))
        
        loading_label = ctk.CTkLabel(
            dialog, 
            text="正在极速遍历分析本地缓存文件结构，请稍候...", 
            font=ctk.CTkFont(size=13), 
            text_color="#38bdf8"
        )
        loading_label.pack(pady=60)
        
        files_scroll = ctk.CTkScrollableFrame(dialog, fg_color="#090d16")
        file_check_vars = {}
        
        def load_files():
            from cleaner_core import scan_app_files
            files = scan_app_files(app, limit=200)
            
            def update_ui():
                loading_label.pack_forget()
                files_scroll.pack(fill="both", expand=True, padx=20, pady=10)
                
                if not files:
                    ctk.CTkLabel(
                        files_scroll, 
                        text="此项目目前没有扫描到任何冗余缓存废料。", 
                        font=ctk.CTkFont(size=13), 
                        text_color="#64748b"
                    ).pack(pady=50)
                    return
                
                # Column labels
                col_frame = ctk.CTkFrame(files_scroll, fg_color="transparent")
                col_frame.pack(fill="x", padx=10, pady=2)
                ctk.CTkLabel(col_frame, text="要清理的文件路径", font=ctk.CTkFont(size=12, weight="bold"), text_color="#64748b").pack(side="left")
                ctk.CTkLabel(col_frame, text="大小", font=ctk.CTkFont(size=12, weight="bold"), text_color="#64748b").pack(side="right", padx=(0, 20))
                
                for path, size in files:
                    file_row = ctk.CTkFrame(files_scroll, fg_color="#1e293b", corner_radius=4)
                    file_row.pack(fill="x", padx=5, pady=2)
                    
                    display_path = obfuscate_path(path)
                    
                    var = ctk.StringVar(value="checked" if path not in self.skipped_files else "unchecked")
                    file_check_vars[path] = var
                    
                    def make_toggle(p=path, v=var):
                        def toggle():
                            if v.get() == "checked":
                                self.skipped_files.discard(p)
                            else:
                                self.skipped_files.add(p)
                        return toggle
                    
                    chk_file = ctk.CTkCheckBox(
                        file_row, 
                        text=display_path, 
                        font=ctk.CTkFont(family="Consolas", size=12),
                        width=18,
                        height=18,
                        command=make_toggle(path, var)
                    )
                    chk_file.pack(side="left", padx=10, pady=6)
                    if path not in self.skipped_files:
                        chk_file.select()
                    else:
                        chk_file.deselect()
                        
                    ctk.CTkLabel(
                        file_row, 
                        text=format_size(size), 
                        font=ctk.CTkFont(family="Consolas", size=12), 
                        text_color="#94a3b8"
                    ).pack(side="right", padx=15, pady=6)
                    
            self.after(0, update_ui)
            
        threading.Thread(target=load_files, daemon=True).start()
        
        # Bottom controls
        bottom_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        bottom_frame.pack(fill="x", pady=10, padx=20)
        
        def select_all():
            for p in file_check_vars.keys():
                self.skipped_files.discard(p)
            dialog.destroy()
            self.show_file_viewer(app)
            
        def deselect_all():
            for p in file_check_vars.keys():
                self.skipped_files.add(p)
            dialog.destroy()
            self.show_file_viewer(app)
            
        ctk.CTkButton(
            bottom_frame, 
            text="全部勾选", 
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#3b82f6", 
            hover_color="#60a5fa",
            width=110,
            height=32,
            command=select_all
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            bottom_frame, 
            text="全部排除", 
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#475569", 
            hover_color="#64748b",
            width=110,
            height=32,
            command=deselect_all
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            bottom_frame, 
            text="确认保存设置", 
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#10b981", 
            hover_color="#34d399",
            width=130,
            height=32,
            command=dialog.destroy
        ).pack(side="right", padx=5)

    def execute_cleaning(self, clean_type):
        self.btn_scan.configure(state="disabled")
        self.btn_safe_clean.configure(state="disabled")
        self.btn_risk_clean.configure(state="disabled")
        
        self.progress_bar.set(0)
        self.progress_bar.configure(mode="indeterminate")
        self.progress_bar.start()
        
        threading.Thread(target=self._clean_thread, args=(clean_type,), daemon=True).start()
        
    def _clean_thread(self, clean_type):
        self.append_log(f">>> 启动特权模式: 执行物理底层粉碎 [{ '安全清理' if clean_type == 'safe' else '风险清理' }]...")
        self.total_cleaned_bytes = 0
        
        # Filter checked and matching risk level
        cleanable_apps = []
        for app in self.apps_data:
            if app["immune"]:
                continue
            chk_var = self.app_checkbox_vars.get(app["id"])
            if chk_var and chk_var.get() == 1:
                if app["risk_level"] == clean_type:
                    cleanable_apps.append(app)
                    
        if not cleanable_apps:
            self.append_log("\n[!] 没有勾选任何属于当前清理分类的软件项。")
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(1)
            self.btn_scan.configure(state="normal")
            self.btn_safe_clean.configure(state="normal")
            self.btn_risk_clean.configure(state="normal")
            return
            
        our_meipass = getattr(sys, '_MEIPASS', None)
        if our_meipass:
            our_meipass = os.path.abspath(our_meipass).lower()
            
        for app in cleanable_apps:
            app_id = app["id"]
            self.append_log(f"[*] 正在抹除: {app['name']}")
            
            resolved_paths = get_resolved_paths(app.get("paths", []))
            deleted_size = 0
            
            for p in resolved_paths:
                if our_meipass and our_meipass in os.path.abspath(p).lower():
                    continue
                deleted_size += clean_directory(p, self.append_log, self.skipped_files)
                
            # Update UI elements
            self.sizes[app_id] = 0
            self.app_rows[app_id]["size"].configure(text="0.00 B")
            self.app_rows[app_id]["badge"].configure(text="✨ 已安全净化", text_color="#22c55e", fg_color="#064e3b")
            
            self.total_cleaned_bytes += deleted_size
            self.lbl_cleaned_val.configure(text=format_size(self.total_cleaned_bytes))
            time.sleep(0.3)
            
        self.progress_bar.stop()
        self.progress_bar.configure(mode="determinate")
        self.progress_bar.set(1)
        
        self.append_log("\n[✓] 物理粉碎清理完成！")
        self.append_log(f"✅ 成功物理粉碎释放容量: {format_size(self.total_cleaned_bytes)}")
        self.append_log("----------------------------------------------------------------------")
        
        self.btn_scan.configure(state="normal")
        self.btn_safe_clean.configure(state="normal")
        self.btn_risk_clean.configure(state="normal")

    def check_for_updates(self):
        def run_check():
            try:
                url = f"http://ppsai.chat/api/check_update?version={CURRENT_VERSION}"
                req = urllib.request.Request(url, headers={'User-Agent': 'SafeCleanerPro-Client'})
                with urllib.request.urlopen(req, timeout=4) as response:
                    if response.status == 200:
                        data = json.loads(response.read().decode('utf-8'))
                        if data.get("has_update"):
                            self.after(0, lambda: self.show_update_dialog(data))
            except Exception as e:
                print(f"Check update failed: {e}")
                
        threading.Thread(target=run_check, daemon=True).start()

    def show_update_dialog(self, update_info):
        dialog = ctk.CTkToplevel(self)
        dialog.title("系统版本升级推送")
        dialog.geometry("480x340")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grab_set()
        
        ctk.CTkLabel(
            dialog, 
            text="🚀 发现新版本 SafeCleaner Pro", 
            font=ctk.CTkFont(size=20, weight="bold"), 
            text_color="#38bdf8"
        ).pack(pady=(20, 10))
        
        ctk.CTkLabel(
            dialog, 
            text=f"最新版本: v{update_info['latest_version']}   (当前版本: v{CURRENT_VERSION})", 
            font=ctk.CTkFont(size=13, weight="bold"), 
            text_color="#94a3b8"
        ).pack(pady=2)
        
        changelog_frame = ctk.CTkFrame(dialog, fg_color="#090d16")
        changelog_frame.pack(fill="both", expand=True, padx=25, pady=10)
        
        tb = ctk.CTkTextbox(changelog_frame, fg_color="transparent", font=ctk.CTkFont(size=12), text_color="#cbd5e1")
        tb.pack(fill="both", expand=True, padx=10, pady=5)
        raw_log = update_info.get("changelog", "")
        formatted_log = raw_log.replace("\\n", "\n")
        tb.insert("0.0", "升级日志：\n" + formatted_log)
        tb.configure(state="disabled")
        
        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=15)
        
        def download():
            import webbrowser
            webbrowser.open(update_info.get("download_url", "http://ppsai.chat/safecleaner/"))
            dialog.destroy()
            
        ctk.CTkButton(
            btn_frame, 
            text="立即获取最新版", 
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#38bdf8", 
            hover_color="#7dd3fc",
            width=140,
            height=36,
            command=download
        ).pack(side="left", padx=10)
        
        ctk.CTkButton(
            btn_frame, 
            text="暂不升级", 
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#475569", 
            hover_color="#64748b",
            width=140,
            height=36,
            command=dialog.destroy
        ).pack(side="left", padx=10)

if __name__ == "__main__":
    app = SafeCleanerApp()
    app.mainloop()
