const API_URL = "/api/admin";

let token = localStorage.getItem("scpro_admin_token");

document.addEventListener("DOMContentLoaded", () => {
    if (token) {
        showDashboard();
    } else {
        document.getElementById("login-screen").style.display = "block";
    }
});

document.getElementById("login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const username = document.getElementById("username").value;
    const password = document.getElementById("password").value;
    const msg = document.getElementById("login-msg");
    
    msg.textContent = "Logging in...";
    
    try {
        const res = await fetch(`${API_URL}/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        
        if (res.ok) {
            token = data.token;
            localStorage.setItem("scpro_admin_token", token);
            showDashboard();
        } else {
            msg.textContent = "❌ " + data.error;
        }
    } catch (err) {
        msg.textContent = "❌ Server error";
    }
});

document.getElementById("logout-btn").addEventListener("click", () => {
    localStorage.removeItem("scpro_admin_token");
    token = null;
    document.getElementById("dashboard-screen").style.display = "none";
    document.getElementById("login-screen").style.display = "block";
});

async function showDashboard() {
    document.getElementById("login-screen").style.display = "none";
    document.getElementById("dashboard-screen").style.display = "block";
    await loadApplications();
    await loadOrders();
    setupQrUploads();
}

async function loadOrders() {
    try {
        const res = await fetch(`${API_URL}/orders`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        const data = await res.json();
        const tbody = document.getElementById("order-list");
        tbody.innerHTML = "";
        
        data.orders.forEach(order => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${order.id}</td>
                <td style="color: #2ed573; font-weight: bold;">${order.transaction_id}</td>
                <td>${order.hwid}</td>
                <td title="${order.license_key}">${order.license_key.substring(0, 20)}...</td>
                <td>${order.created_at}</td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Failed to load orders", err);
    }
}

function setupQrUploads() {
    ['wechat', 'alipay'].forEach(type => {
        const form = document.getElementById(`${type}-qr-form`);
        const statusDiv = document.getElementById(`${type}-status`);
        
        form.onsubmit = async (e) => {
            e.preventDefault();
            const fileInput = document.getElementById(`${type}-file`);
            const file = fileInput.files[0];
            if (!file) return;
            
            statusDiv.innerHTML = "正在上传...";
            const formData = new FormData();
            formData.append('file', file);
            formData.append('type', type);
            
            try {
                const res = await fetch(`/api/admin/upload_qrcode`, {
                    method: 'POST',
                    headers: { 'Authorization': `Bearer ${token}` },
                    body: formData
                });
                const data = await res.json();
                if (res.ok) {
                    statusDiv.innerHTML = `✅ ${type === 'wechat' ? '微信' : '支付宝'}收款码上传成功！`;
                } else {
                    statusDiv.innerHTML = `❌ 上传失败: ${data.error}`;
                }
            } catch (err) {
                statusDiv.innerHTML = "❌ 网络错误";
            }
        };
    });
}

async function loadApplications() {
    try {
        const res = await fetch(`${API_URL}/applications`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (res.status === 401) {
            document.getElementById("logout-btn").click();
            return;
        }
        
        const data = await res.json();
        const tbody = document.getElementById("app-list");
        tbody.innerHTML = "";
        
        data.applications.forEach(app => {
            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td>${app.id}</td>
                <td>${app.hwid}</td>
                <td>${app.contact}</td>
                <td><span style="color: ${app.status === 'approved' ? '#2ed573' : '#ffa502'}">${app.status}</span></td>
                <td>
                    ${app.status === 'pending' 
                        ? `<button class="btn primary small" onclick="issueLicense(${app.id}, '${app.hwid}')">生成授权码</button>`
                        : `<button class="btn outline small" onclick="showLicense('${app.license_key}')">查看授权码</button>`
                    }
                </td>
            `;
            tbody.appendChild(tr);
        });
    } catch (err) {
        console.error("Failed to load apps", err);
    }
}

async function issueLicense(appId, hwid) {
    if (!confirm(`Confirm generation for HWID: ${hwid} ?`)) return;
    
    try {
        const res = await fetch(`${API_URL}/issue`, {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`
            },
            body: JSON.stringify({ id: appId, hwid })
        });
        const data = await res.json();
        
        if (res.ok) {
            showLicense(data.license_key);
            loadApplications(); // reload list
        } else {
            alert("Error: " + data.error);
        }
    } catch(err) {
        alert("Server error");
    }
}

function showLicense(key) {
    document.getElementById('license-result').value = key;
    document.getElementById('license-modal').style.display = 'flex';
}

document.getElementById('close-modal').addEventListener('click', () => {
    document.getElementById('license-modal').style.display = 'none';
});
