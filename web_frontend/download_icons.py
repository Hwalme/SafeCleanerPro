import os
import urllib.request
import urllib.error

# Directory to save icons
ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")
os.makedirs(ICONS_DIR, exist_ok=True)

# 36 Icons mapping to download URLs (using jsDelivr / GitHub repositories for high quality colored SVGs)
icon_mapping = {
    # Row 1: Social
    "wechat": [
        "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/svg/wechat.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/wechat.svg"
    ],
    "qq": [
        "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/svg/qq.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/qq.svg"
    ],
    "wecom": [
        "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/svg/wecom.svg",
        "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/svg/wechat-work.svg"
    ],
    "dingtalk": [
        "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/svg/dingtalk.svg"
    ],
    "feishu": [
        "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/svg/feishu.svg",
        "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/svg/lark.svg"
    ],
    "tencentmeeting": [
        "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/svg/tencent.svg"
    ],

    # Row 2: AI & LLM
    "googlegemini": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/google-gemini.svg"
    ],
    "cursor": [
        "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/svg/cursor.svg"
    ],
    "claude": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/claude.svg"
    ],
    "openai": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/openai-icon.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/openai.svg"
    ],
    "ollama": [
        "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/svg/ollama.svg"
    ],
    "huggingface": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/huggingface.svg"
    ],

    # Row 3: Adobe & Design
    "adobephotoshop": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/adobe-photoshop.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/photoshop.svg"
    ],
    "adobepremierepro": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/adobe-premiere.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/premiere.svg"
    ],
    "adobeaftereffects": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/adobe-after-effects.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/after-effects.svg"
    ],
    "adobeillustrator": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/adobe-illustrator.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/illustrator.svg"
    ],
    "davinciresolve": [
        "https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/svg/davinci-resolve.svg"
    ],
    "blender": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/blender.svg"
    ],

    # Row 4: Coding & Dev
    "visualstudiocode": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/visual-studio-code.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/vscode.svg"
    ],
    "intellijidea": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/intellij-idea.svg"
    ],
    "pycharm": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/pycharm.svg"
    ],
    "webstorm": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/webstorm.svg"
    ],
    "docker": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/docker.svg"
    ],
    "npm": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/npm.svg"
    ],

    # Row 5: Package & Browsers
    "python": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/python.svg"
    ],
    "git": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/git-icon.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/git.svg"
    ],
    "googlechrome": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/chrome.svg"
    ],
    "microsoftedge": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/microsoft-edge.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/edge.svg"
    ],
    "firefox": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/firefox.svg"
    ],
    "steam": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/steam.svg"
    ],

    # Row 6: Games & System
    "epicgames": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/epic-games.svg"
    ],
    "unity": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/unity.svg"
    ],
    "slack": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/slack-icon.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/slack.svg"
    ],
    "nodedotjs": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/nodejs-icon.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/nodejs.svg"
    ],
    "windows": [
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/microsoft-windows.svg",
        "https://cdn.jsdelivr.net/gh/gilbarbara/logos/logos/windows.svg"
    ]
}

# Fallback configurations for generating beautiful SVG icons
fallback_config = {
    "wechat": ("#09BB07", "WX"),
    "qq": ("#1296DB", "QQ"),
    "wecom": ("#1877F2", "WC"),
    "dingtalk": ("#007FFF", "DT"),
    "feishu": ("#3370FF", "FS"),
    "tencentmeeting": ("#0052D9", "TM"),
    "googlegemini": ("#8E75FF", "GE"),
    "cursor": ("#00F0FF", "CU"),
    "claude": ("#D97706", "CL"),
    "openai": ("#10B981", "AI"),
    "ollama": ("#000000", "OL"),
    "huggingface": ("#FFCC00", "HF"),
    "adobephotoshop": ("#31A8FF", "PS"),
    "adobepremierepro": ("#9999FF", "PR"),
    "adobeaftereffects": ("#D292FF", "AE"),
    "adobeillustrator": ("#FF9A00", "AI"),
    "davinciresolve": ("#E11D48", "DR"),
    "blender": ("#EA580C", "BL"),
    "visualstudiocode": ("#007ACC", "VS"),
    "intellijidea": ("#FE2857", "IJ"),
    "pycharm": ("#21D4FD", "PC"),
    "webstorm": ("#00CDFE", "WS"),
    "docker": ("#2496ED", "DK"),
    "npm": ("#CB3837", "NP"),
    "python": ("#3776AB", "PY"),
    "git": ("#F05032", "GT"),
    "googlechrome": ("#4285F4", "CH"),
    "microsoftedge": ("#0078D7", "ED"),
    "firefox": ("#FF7139", "FF"),
    "steam": ("#171A21", "ST"),
    "epicgames": ("#313131", "EP"),
    "unity": ("#222C37", "UN"),
    "slack": ("#4A154B", "SL"),
    "nodedotjs": ("#339933", "JS"),
    "windows": ("#0078D7", "WN")
}

def generate_fallback_svg(color, initials):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" width="100" height="100">
    <rect width="100" height="100" rx="22" fill="{color}"/>
    <text x="50%" y="54%" font-family="'Segoe UI', Roboto, Helvetica, sans-serif" font-weight="800" font-size="38" fill="#FFFFFF" dominant-baseline="middle" text-anchor="middle">{initials}</text>
</svg>"""

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

print("Starting icon download and check...")

for key, urls in icon_mapping.items():
    success = False
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as response:
                content = response.read()
                # Simple validation that it's SVG
                if b"<svg" in content or b"<SVG" in content:
                    save_path = os.path.join(ICONS_DIR, f"{key}.svg")
                    with open(save_path, "wb") as f:
                        f.write(content)
                    print(f"[{key}] Successfully downloaded from {url}")
                    success = True
                    break
        except Exception as e:
            continue
            
    if not success:
        # Generate beautiful fallback SVG
        color, initials = fallback_config.get(key, ("#334155", "APP"))
        svg_content = generate_fallback_svg(color, initials)
        save_path = os.path.join(ICONS_DIR, f"{key}.svg")
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(svg_content)
        print(f"[{key}] Failed downloading, generated beautiful fallback SVG (Color: {color}, Initials: {initials})")

print("All icons processed and verified!")
