const API_URL = "/api";

document.addEventListener("DOMContentLoaded", () => {
    handleHwidFromUrl();
    setupPayButtons();
});

// Parse HWID from URL parameters and handle mobile/PC sync
let pollingInterval = null;
function handleHwidFromUrl() {
    const urlParams = new URLSearchParams(window.location.search);
    const hwid = urlParams.get('hwid');
    const isMobile = window.innerWidth <= 768;
    
    // Elements
    const hwidInput = document.getElementById('hwid-input');
    const pcPortal = document.getElementById('pc-sync-portal');
    const qrImg = document.getElementById('sync-qr-img');
    const payAlipay = document.getElementById('pay-alipay');
    const payWechat = document.getElementById('pay-wechat');
    
    if (hwid) {
        if (hwidInput) hwidInput.value = hwid;
        
        if (!isMobile) {
            // PC: Show mobile sync QR and hide direct pay buttons
            if (pcPortal && qrImg) {
                const mobileUrl = window.location.origin + '/safecleaner/?hwid=' + encodeURIComponent(hwid);
                qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=150x150&data=${encodeURIComponent(mobileUrl)}`;
                pcPortal.style.display = 'block';
            }
            if (payAlipay) payAlipay.style.display = 'none';
            if (payWechat) payWechat.style.display = 'none';
        } else {
            // Mobile: Hide sync QR, show direct pay buttons
            if (pcPortal) pcPortal.style.display = 'none';
            if (payAlipay) payAlipay.style.display = 'block';
            if (payWechat) payWechat.style.display = 'block';
        }
        
        // Auto-scroll smooth to payment section on both PC and Mobile
        setTimeout(() => {
            const downloadSection = document.getElementById('download');
            if (downloadSection) {
                downloadSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }
        }, 300);
        
        // Start polling cloud activation status
        startActivationPolling(hwid);
    } else {
        // No HWID parameter: Default view
        if (pcPortal) pcPortal.style.display = 'none';
        if (isMobile) {
            if (payAlipay) payAlipay.style.display = 'block';
            if (payWechat) payWechat.style.display = 'block';
        } else {
            if (payAlipay) payAlipay.style.display = 'none';
            if (payWechat) payWechat.style.display = 'none';
        }
    }
}

// Polling cloud status to see if activated on another device
function startActivationPolling(hwid) {
    if (pollingInterval) clearInterval(pollingInterval);
    
    pollingInterval = setInterval(async () => {
        try {
            const res = await fetch(`${API_URL}/check_activation?hwid=${encodeURIComponent(hwid)}`);
            if (res.ok) {
                const data = await res.json();
                if (data.activated) {
                    clearInterval(pollingInterval);
                    
                    // Update sync portal status if exists
                    const syncStatus = document.getElementById('sync-polling-status');
                    if (syncStatus) {
                        syncStatus.style.color = '#2ed573';
                        syncStatus.textContent = '✅ 已支付核销成功！您的电脑客户端已自动放行解锁。';
                    }
                    
                    // Populate license key for fallback display
                    const msgEl = document.getElementById('checkout-msg');
                    const licenseBox = document.getElementById('license-output-box');
                    const licenseArea = document.getElementById('generated-license');
                    
                    if (msgEl && licenseBox && licenseArea) {
                        msgEl.className = 'msg success';
                        msgEl.textContent = '✅ 支付成功！已为您签发终身永久特权授权码！';
                        licenseArea.value = data.license_key;
                        licenseBox.style.display = 'block';
                    }
                }
            }
        } catch (err) {
            console.error("Polling error", err);
        }
    }, 3000);
}

// Bind click handlers for EPay checkout buttons
function setupPayButtons() {
    const alipayBtn = document.getElementById('pay-alipay');
    const wechatBtn = document.getElementById('pay-wechat');
    
    if (alipayBtn) {
        alipayBtn.onclick = () => initiatePay('alipay');
    }
    if (wechatBtn) {
        wechatBtn.onclick = () => initiatePay('wxpay');
    }
}

async function initiatePay(type) {
    const hwidInput = document.getElementById('hwid-input');
    const hwid = hwidInput ? hwidInput.value.trim() : "";
    const msgEl = document.getElementById('checkout-msg');
    
    if (!hwid) {
        if (msgEl) {
            msgEl.className = 'msg error';
            msgEl.textContent = '❌ 错误：请先输入或粘贴您的客户端 HWID 设备指纹。';
        }
        return;
    }
    
    if (msgEl) {
        msgEl.className = 'msg';
        msgEl.textContent = '🚀 正在拉起安全支付收银台，请稍候...';
    }
    
    try {
        const res = await fetch(`${API_URL}/pay`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ hwid, type })
        });
        
        const data = await res.json();
        if (res.ok && data.success && data.redirect_url) {
            if (msgEl) {
                msgEl.className = 'msg success';
                msgEl.textContent = '✅ 收银台加载成功！正在跳转支付界面...';
            }
            // Redirect to EPay submit checkout page
            window.location.href = data.redirect_url;
        } else {
            if (msgEl) {
                msgEl.className = 'msg error';
                msgEl.textContent = '❌ ' + (data.error || '创建订单失败，请稍后重试。');
            }
        }
    } catch (err) {
        if (msgEl) {
            msgEl.className = 'msg error';
            msgEl.textContent = '❌ 网络错误：无法连接到云端服务，请检查网络。';
        }
    }
}
