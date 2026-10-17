# 腾讯电脑管家 清理功能逆向报告

> 日期：2026-10-17
> 目标：提取腾讯电脑管家「垃圾清理」规则，供 safecleaner 参考（重点：腾讯系软件 QQ/微信）

## 一、安装包

- 来源：官网 `https://guanjia.qq.com/main.html` 页面源码中的直链
- URL：`https://pm.myapp.com/invc/xfspeed/qqpcmgr/versetup/portal/portal/(2in1)PCMgr_Setup_18_2_30833_214_7cfd59_1984.exe`
- 版本：18.2.30833.214
- 大小：413,279,680 字节（394MB），PE32

## 二、安装包结构（已完全解析外层）

```
QQPCMgr_Setup.exe (413MB, PE32)
├── PE 头 + stub 代码 (2.8MB)
├── 7z 覆盖层 → setup.xml + beacon_sdk.dll + QQPCDownload.dll (15MB)
│   └── 本质是下载器配置：offline_package=PCMgr_Setup.exe
├── 自定义 "Item" 容器
│   └── PCMgr_Setup.exe (243MB, PE32) ← 真正的安装器
│       ├── PE 头 + stub (2.8MB)
│       ├── 14字节 "zzd." 头 + 648KB 7z (安装配置: PacketEx/pluginCxx, plugin/)
│       └── 240MB 加密 payload ← ★ 清理模块在此，但强加密
```

### 容器格式细节

1. **外层 "Item" 格式**：魔数 `Item ` + 文件大小(u32) + 若干字段 + UTF-16 文件名
   - 如 `PCMgr_Setup.exe` 在偏移 12484180，大小 243,545,119
2. **内层 "zzd." 格式**：魔数 `zzd.` + 版本(u16) + 后续7z块大小(u32) + 7z数据
   - 如第一块：`7a 7a 64 2e 03 00 2d e4 09 00`（648,237 = 0x09e42d）

## 三、加密分析（已排除的方法）

| 方法 | 结果 |
|---|---|
| 7z 直接解 240MB payload | ❌ 熵 8.0，无文件签名，非压缩包 |
| 单字节 XOR 全密钥爆破 | ❌（payload 熵 8.0，不符合）|
| 已知 360 流密码 (`pt[i]=ct[i]^key`) | ❌ 不同算法体系 |
| stub 中的 XOR（密钥 `TXDLutm_2025`）| ❌ 仅用于遥测 JSON 配置（函数 `FUN_0052a210`），非 payload 解密 |
| Ghidra 逆向 payload 解密 | ❌ stub 导入 `CRYPT32.dll`/`ADVAPI32.dll` 的 `CryptCreateHash`/`CryptHashData`/`CryptDestroyKey`，确认为 **Windows CryptoAPI 强加密**，静态逆向需定位密钥派生逻辑，工作量超出本次范围 |

**结论**：240MB 主体为 CryptoAPI 强加密，需 Windows 动态调试（运行安装器、内存 dump）才能解密。静态分析到此为止。

## 四、腾讯系软件清理路径（公开资料整理，非逆向所得）

> 以下来自公开技术文章与腾讯官方文档，仅供 safecleaner 参考，需自行验证。
> 已存为 `tencent_app_paths.json`。

| 软件 | 缓存路径 | 说明 |
|---|---|---|
| QQ (PC) | `%USERPROFILE%\Documents\Tencent Files\<QQ号>\` | 子目录 `FileRecv`（接收文件）、`Image`（图片）、`Video`（视频）是清理大头；`Msg3.0.db`/`nt_msg.db` 是聊天记录**不可删** |
| 微信 (PC) | `%USERPROFILE%\Documents\WeChat Files\<wxid_>\` | `Cache`、`Video`、`Image` 可清；`Msg` 目录是聊天记录**不可删**；旧账号的 `wxid_` 文件夹（半年未修改）可整个删除 |
| QQ 浏览器 | `%LOCALAPPDATA%\Tencent\QQBrowser\` | User Data 缓存结构类似 Chromium |

与 360 规则的差异点：
- 360 的 `tracesweeper.dat`（910 条）覆盖的是**通用**浏览器/系统痕迹，对 QQ/微信只有泛泛的 `%APPDATA%\Tencent\` 条目
- 腾讯电脑管家理论上对自家软件（QQ/微信/腾讯视频/电脑管家自身升级缓存）有更细的规则，但因加密未能提取
- 建议 safecleaner 直接采用上表路径 + Winapp2.ini 社区规则补全

## 五、交付物

- `REPORT.md`（本文件）
- `tencent_app_paths.json`：腾讯系软件公开清理路径（结构化）
- `PCMgr_Setup.exe`：提取出的 243MB 内层安装器（供后续动态分析）
- `extracted/`：外层 7z 解出的安装器配置

## 六、后续建议

如需腾讯电脑管家的完整规则，需在 Windows 环境运行安装器并 dump 内存，或用 x64dbg 跟踪 `CryptDecrypt` 调用拿密钥。这是另一个专项任务。
