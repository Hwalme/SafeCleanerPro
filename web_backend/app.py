import os
import sys
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import hashlib
import config
from database import (
    init_db, add_application, get_applications, update_application_status,
    add_order, get_orders, is_transaction_used,
    add_pending_payment, get_pending_payment, update_pending_payment_status
)

# For RSA signing
import base64
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256

app = Flask(__name__)
CORS(app)  # Allow all domains for simplicity in this separation

# Admin Credentials (In production, use env variables)
ADMIN_USER = "admin"
ADMIN_PASS = "pps88888"
ADMIN_TOKEN = "secret-admin-token-xyz" # Simple static token for demo

# Upload Folder for QR Codes
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Initialize DB on startup
init_db()

def get_private_key():
    # The private key must be copied to web_backend/keys/private.pem
    current_dir = os.path.dirname(os.path.abspath(__file__))
    key_path = os.path.join(current_dir, 'keys', 'private.pem')
    if not os.path.exists(key_path):
        return None
    with open(key_path, 'rb') as f:
        return RSA.import_key(f.read())

def generate_license(hwid):
    private_key = get_private_key()
    if not private_key:
        raise Exception("Private key not found on server.")
    h = SHA256.new(hwid.encode('utf-8'))
    signature = pkcs1_15.new(private_key).sign(h)
    return base64.b64encode(signature).decode('utf-8')

# =======================
# PUBLIC API (Frontend)
# =======================
@app.route('/api/apply', methods=['POST'])
def apply_license():
    data = request.json
    hwid = data.get('hwid')
    contact = data.get('contact')
    
    if not hwid or not contact:
        return jsonify({"error": "HWID and Contact are required"}), 400
        
    add_application(hwid, contact)
    
    # Optional: Trigger Webhook notification here (Feishu/Telegram)
    # requests.post(WEBHOOK_URL, json={"text": f"New application from {contact}"})
    
    return jsonify({"message": "Application submitted successfully"}), 200

import time

# Simple in-memory rate limiting dictionary for anti-brute-force
# Key: ip_or_hwid, Value: {"failed_count": X, "lockout_time": Y}
failed_attempts = {}

def check_rate_limit(key):
    now = time.time()
    if key in failed_attempts:
        record = failed_attempts[key]
        if record["lockout_time"] > now:
            remaining = int(record["lockout_time"] - now)
            return False, f"尝试次数过多。操作已被锁定，请在 {remaining} 秒后再试。"
        if record["failed_count"] >= 5:
            # Lockout expired, reset
            failed_attempts[key] = {"failed_count": 0, "lockout_time": 0}
    return True, ""

def record_failed_attempt(key):
    now = time.time()
    if key not in failed_attempts:
        failed_attempts[key] = {"failed_count": 1, "lockout_time": 0}
    else:
        failed_attempts[key]["failed_count"] += 1
        if failed_attempts[key]["failed_count"] >= 5:
            # Lockout for 15 minutes (900 seconds)
            failed_attempts[key]["lockout_time"] = now + 900

def clear_failed_attempts(key):
    if key in failed_attempts:
        del failed_attempts[key]

def validate_transaction_format(tx_id):
    tx_id = tx_id.strip()
    if not tx_id.isdigit():
        return False, "交易单号格式错误：单号必须全部为纯数字"
    
    # WeChat transaction ID is exactly 28 digits (starts with 1000 or 42000)
    # Alipay transaction ID is typically 28 or 32 digits
    if len(tx_id) not in [28, 32]:
        return False, "交易单号格式错误：请输入有效的28位或32位纯数字交易单号"
        
    return True, ""

# Automated Pay Gate 核销与卡密签发接口
@app.route('/api/checkout', methods=['POST'])
def checkout_license():
    data = request.json
    hwid = data.get('hwid')
    transaction_id = data.get('transaction_id')
    client_ip = request.remote_addr
    
    if not hwid or not transaction_id:
        return jsonify({"error": "设备指纹 HWID 和交易单号是必需的"}), 400
        
    # Rate limit check on both IP and HWID
    ip_ok, ip_msg = check_rate_limit(client_ip)
    if not ip_ok:
        return jsonify({"error": ip_msg}), 429
        
    hwid_ok, hwid_msg = check_rate_limit(hwid)
    if not hwid_ok:
        return jsonify({"error": hwid_msg}), 429

    transaction_id = transaction_id.strip()
    
    # Strict Format Check
    fmt_ok, fmt_msg = validate_transaction_format(transaction_id)
    if not fmt_ok:
        record_failed_attempt(client_ip)
        record_failed_attempt(hwid)
        return jsonify({"error": fmt_msg}), 400
        
    # 判断交易单号是否已被其他机器核销过
    if is_transaction_used(transaction_id):
        record_failed_attempt(client_ip)
        record_failed_attempt(hwid)
        return jsonify({"error": "此交易单号已被使用，请勿重复核销"}), 400
        
    try:
        # 秒级签发 RSA 卡密
        license_key = generate_license(hwid)
        # 将核销的订单记录存盘
        add_order(transaction_id, hwid, license_key)
        
        # Clear rate-limit attempts on success
        clear_failed_attempts(client_ip)
        clear_failed_attempts(hwid)
        
        return jsonify({
            "success": True,
            "message": "支付核销成功，已为您签发终身永久特权授权码！",
            "license_key": license_key
        }), 200
    except Exception as e:
        return jsonify({"error": f"签发授权码失败: {str(e)}"}), 500

# 客户端/网页轮询检测 HWID 是否已被核销激活的接口
@app.route('/api/check_activation', methods=['GET'])
def check_activation():
    hwid = request.args.get('hwid')
    if not hwid:
        return jsonify({"activated": False, "error": "设备指纹 HWID 是必需的"}), 400
    
    hwid = hwid.strip()
    import sqlite3
    from database import DB_PATH
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT license_key FROM orders WHERE hwid = ? ORDER BY created_at DESC LIMIT 1', (hwid,))
        row = c.fetchone()
        conn.close()
        
        if row:
            return jsonify({
                "activated": True,
                "license_key": row[0],
                "message": "激活验证成功！已经放行！"
            }), 200
        else:
            return jsonify({"activated": False}), 200
    except Exception as e:
        return jsonify({"activated": False, "error": str(e)}), 500

# 客户端版本更新检查接口
@app.route('/api/check_update', methods=['GET'])
def check_update():
    client_version = request.args.get('version', '3.5')
    latest_version = "3.6"
    download_url = f"{config.API_BASE_URL}/safecleaner/downloads/SafeCleanerPro.rar"
    changelog = (
        "1. 升级深度垃圾扫描算法，增加多款 Adobe 软件垃圾扫描 (Photoshop/Illustrator/After Effects/Premiere/Acrobat等)\\n"
        "2. 增加可选清理和风险提示功能，分为[安全清理]与[风险清理]两个维度\\n"
        "3. 支持查看具体清理文件详情，可自主剔除或保留特定文件\\n"
        "4. 支持永久保存授权密钥到本地 AppData，防止软件版本升级时丢失激活凭证"
    )
    
    try:
        cv_f = float(client_version)
        lv_f = float(latest_version)
        has_update = lv_f > cv_f
    except Exception:
        has_update = latest_version != client_version

    return jsonify({
        "has_update": has_update,
        "latest_version": latest_version,
        "download_url": download_url,
        "changelog": changelog
    }), 200

def md5_sign(params, key):
    # Sort parameters alphabetically by key
    sorted_keys = sorted(params.keys())
    # Exclude empty values, 'sign', and 'sign_type'
    kv_pairs = []
    for k in sorted_keys:
        val = str(params[k]).strip()
        if k not in ['sign', 'sign_type'] and val != '':
            kv_pairs.append(f"{k}={val}")
    
    sign_str = "&".join(kv_pairs)
    # Append key
    sign_str += key
    # Generate MD5 hash
    return hashlib.md5(sign_str.encode('utf-8')).hexdigest()

# Universal EPay V1 Payment Redirect URL Generator
@app.route('/api/pay', methods=['POST'])
def initiate_payment():
    data = request.json
    hwid = data.get('hwid')
    pay_type = data.get('type')  # 'alipay' or 'wxpay'
    
    if not hwid or not pay_type:
        return jsonify({"error": "设备指纹 HWID 和支付方式是必需的"}), 400
        
    if pay_type not in ['alipay', 'wxpay']:
        return jsonify({"error": "暂不支持的支付方式，仅支持 alipay 或 wxpay"}), 400
        
    # Generate unique trade number
    import time
    import random
    trade_no = f"PAY_{int(time.time())}_{random.randint(1000, 9999)}"
    
    # Save pending order in database
    add_pending_payment(trade_no, hwid)
    
    # Build EPay V1 request parameters
    params = {
        "pid": config.EPAY_PID,
        "type": pay_type,
        "out_trade_no": trade_no,
        "notify_url": f"{config.API_BASE_URL}/api/pay_callback",
        "return_url": f"{config.API_BASE_URL}/safecleaner/pay.html",
        "name": "SafeCleanerPro",
        "money": "1.99"
    }
    
    # Sign parameters
    sign = md5_sign(params, config.EPAY_KEY)
    params["sign"] = sign
    params["sign_type"] = "MD5"
    
    # Build redirect URL
    import urllib.parse
    query_string = urllib.parse.urlencode(params)
    redirect_url = f"{config.EPAY_API_URL}submit.php?{query_string}"
    
    return jsonify({
        "success": True,
        "trade_no": trade_no,
        "redirect_url": redirect_url
    }), 200

# EPay Asynchronous Webhook Notification
@app.route('/api/pay_callback', methods=['GET', 'POST'])
def payment_callback():
    # EPay may send data via GET or POST parameters
    req_data = request.args if request.method == 'GET' else request.form
    req_dict = req_data.to_dict()
    
    sign = req_dict.get('sign')
    trade_no = req_dict.get('out_trade_no')
    trade_status = req_dict.get('trade_status')
    
    if not sign or not trade_no or not trade_status:
        return "fail", 400
        
    # Verify MD5 signature from EPay
    expected_sign = md5_sign(req_dict, config.EPAY_KEY)
    if expected_sign != sign:
        return "fail_sign", 400
        
    # Check if payment was successful
    if trade_status == 'TRADE_SUCCESS':
        # Retrieve the pending payment order
        pending = get_pending_payment(trade_no)
        if pending and pending["status"] == 'pending':
            hwid = pending["hwid"]
            try:
                # Issue the permanent RSA license key for this HWID
                license_key = generate_license(hwid)
                # Save it in official orders table (so check_activation will detect it)
                add_order(trade_no, hwid, license_key)
                # Mark pending payment as paid
                update_pending_payment_status(trade_no, 'paid')
                return "success", 200
            except Exception as e:
                return f"fail_license_generation_{str(e)}", 500
        else:
            return "success", 200  # Already processed
            
    return "fail_status", 400

# 获取当前的支付二维码
@app.route('/api/qrcodes', methods=['GET'])
def get_qrcodes():
    wechat_exists = os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], 'wechat.png'))
    alipay_exists = os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], 'alipay.png'))
    return jsonify({
        "wechat": "/api/uploads/wechat.png" if wechat_exists else None,
        "alipay": "/api/uploads/alipay.png" if alipay_exists else None
    }), 200

# 高可靠反向代理二维码生成接口 (确保客户端 100% 成功加载二维码)
@app.route('/api/qrcode', methods=['GET'])
def get_qrcode_image():
    import urllib.parse
    import urllib.request
    data = request.args.get('data')
    if not data:
        return "Missing data", 400
        
    try:
        url = f"https://api.qrserver.com/v1/create-qr-code/?size=150x150&data={urllib.parse.quote(data)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            qr_data = response.read()
        return qr_data, 200, {'Content-Type': 'image/png'}
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/api/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# =======================
# ADMIN API (Dashboard)
# =======================
def check_auth(req):
    auth_header = req.headers.get("Authorization")
    if auth_header == f"Bearer {ADMIN_TOKEN}":
        return True
    return False

@app.route('/api/admin/login', methods=['POST'])
def login():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    if username == ADMIN_USER and password == ADMIN_PASS:
        return jsonify({"token": ADMIN_TOKEN}), 200
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/api/admin/applications', methods=['GET'])
def list_applications():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    
    status = request.args.get('status')
    apps = get_applications(status)
    return jsonify({"applications": apps}), 200

@app.route('/api/admin/issue', methods=['POST'])
def issue_license():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    app_id = data.get('id')
    hwid = data.get('hwid')
    
    if not app_id or not hwid:
        return jsonify({"error": "ID and HWID required"}), 400
        
    try:
        license_key = generate_license(hwid)
        update_application_status(app_id, 'approved', license_key)
        return jsonify({"message": "License generated", "license_key": license_key}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 订单管理 API
@app.route('/api/admin/orders', methods=['GET'])
def list_orders():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    orders = get_orders()
    return jsonify({"orders": orders}), 200

# 上传支付二维码 API
@app.route('/api/admin/upload_qrcode', methods=['POST'])
def upload_qrcode():
    if not check_auth(request): return jsonify({"error": "Unauthorized"}), 401
    
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    qr_type = request.form.get('type') # 'wechat' or 'alipay'
    
    if not qr_type or qr_type not in ['wechat', 'alipay']:
        return jsonify({"error": "Invalid type"}), 400
        
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
        
    filename = f"{qr_type}.png"
    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
    return jsonify({"success": True, "message": f"{qr_type} QR Code uploaded"}), 200

if __name__ == '__main__':
    # Make sure keys directory exists
    os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keys'), exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)
