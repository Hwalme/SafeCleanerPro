# 存储现状报告（人类可读版） · 2026-09-12

> 一句话结论：**机器上分散着 37 个 S/P 级凭据文件未受保护；Coding 一个月净增 29 项；2 个超大 zip 可疑。**

---

## 1. 三个数字

| 数字 | 含义 |
|---|---|
| **37** | S/P 级文件（密钥、私钥、cookies、解密库）—— 远超之前手动看到的 5 个 |
| **+29** | D:\Coding 顶层一个月净增（43 → 72），平均每天新加 1 个无主项 |
| **1.05GB** | 微信解密库（7 个 dec_MSG*.db）总大小，需按红线处理 |

## 2. 最该今天处理的 3 件事

1. **ai-creativity 项目**双重风险：105 个改动未提交 + SSH 私钥 `vps_ssh_key.pem` 未 `.gitignore`
   ```bash
   cd D:\Coding\ai-creativity
   git add -A && git commit -m "WIP: pre-org snapshot"
   echo "*.pem" >> .gitignore
   ```

2. **`Map\google_maps_api_key.txt`** 任何 .gitignore 都拦不住（不是 .env 格式）
   → 挪到 `Map\.env.local`，加 `.gitignore`，**轮换 key**（因为可能已暴露）

3. **微信解密库不动** —— 按 `[[SECURITY]]` §3 R2；只读 SHA256 已留痕

## 3. 待澄清的 2 个大文件

- `D:\Coding\PPSAI\pps_full_deploy.zip` (218.6 MB) — 这个项目 .git 损坏 + 有 218MB zip，建议**冻结**
- `D:\Coding\resume_upload.zip` (141.4 MB) — 检查 mtime，决定保留还是删

## 4. 完整数据看哪

| 想看 | 路径 |
|---|---|
| 完整结构（51 + 72 + 60 项） | `audit/2026-09-13_initial_scan.json` |
| S/P 文件清单 + SHA256 | `audit/operations/2026-09-13_initial_scan.json` |
| 详细分析（含按目录分布） | `research/2026-09-12_storage_landscape.md` |
| 知识库侧 | `E:\Obsidian\Hwalme\projects\_硬盘整理系统\扫描日志\2026-09-12_D盘初扫.md` |

## 5. 我没做什么（按 [[按需整理]] 原则）

- 没下载任何工具
- 没装任何软件
- 没动 D 盘任何文件
- 没读取任何密钥内容（SHA256 只算前 1KB）
- 没上传任何东西到外网

## 关联

- `[[../SECURITY]]`
- `[[../research/2026-09-12_storage_landscape]]`
- `[[../README]]`