---
title: "_pending_actions · 2026-09-13 阶段1 零风险动作清单"
type: pending-action
created: "2026-09-13"
status: pending-approval
risk: zero
estimated_time: 30 min
tags: [pending-action, 阶段1, 零风险, 安全加固]
---

# 2026-09-13 · 阶段 1 · 零风险动作清单

> **本文按 `D:\Coding\Organization\SECURITY.md` §1.2 三步走生成**
> 你点 `OK` 才执行。每一项都有：动作 / 风险 / 回滚 / 验证。

---

## 总览

- **风险等级**：🟢 零
- **预计耗时**：30 分钟
- **不动数据**：只动 .gitignore 文件 + 创建空 .env.local + git commit
- **回滚**：`git reset --hard HEAD~1`（仅 ai-creativity 提交）

---

## 动作清单（4 项）

### 动作 1️⃣ `ai-creativity` 加 `*.pem` 到 .gitignore

| 字段 | 值 |
|---|---|
| **动作** | 在 `D:\Coding\ai-creativity\.gitignore` 末尾追加 `*.pem` `*.key` `id_rsa*` |
| **为什么** | 现在 `vps_ssh_key.pem` 是 untracked，加 gitignore 后**永远不会被提交** |
| **风险** | 🟢 零（只改 gitignore 文本文件） |
| **回滚** | `git checkout .gitignore` |
| **验证** | `cat .gitignore \| grep pem` 应有 `*.pem` |

### 动作 2️⃣ `ai-creativity` 提交 168 个变更

| 字段 | 值 |
|---|---|
| **动作** | `git add -A && git commit -m "WIP: pre-organization snapshot 2026-09-13"` |
| **为什么** | 知识库 P0 已挂 32 天；168 个改动 = **机器硬盘坏了归零** |
| **风险** | 🟢 零（vps_ssh_key.pem 是 untracked，**不会被提交**） |
| **回滚** | `git reset --hard HEAD~1`（不丢工作，只丢这次 commit） |
| **注意** | 这是 `commit`，**不是 `push`**——你没设 remote 吗？如没有，**纯本地 commit**，不暴露 |
| **验证** | `git log --oneline -2` |

### 动作 3️⃣ `Map\google_maps_api_key.txt` 挪到 `.env.local`

| 字段 | 值 |
|---|---|
| **动作** | ① 复制 `D:\Coding\Map\google_maps_api_key.txt` 内容到 `D:\Coding\Map\.env.local`<br>② 删除原 `google_maps_api_key.txt`<br>③ 创建 `.gitignore` 含 `google_maps_api_key.txt` 和 `.env.local`<br>④ `git init && git add .gitignore && git commit -m "initial: protect API key"` |
| **为什么** | 知识库 P0（已挂 32 天）—— Map 还没 git 仓库，必须建一个 |
| **风险** | 🟡 低（涉及删除原文件，但内容已复制） |
| **回滚** | 从 `.env.local` 重新生成 `google_maps_api_key.txt` |
| **⚠️ 关键问题** | **google maps key 早已明文 32 天，强烈建议轮换 key**（在 Google Cloud Console 撤销旧的、生成新的，再填进 `.env.local`） |
| **轮换决策** | 你拍板：① 现在轮换（5 min，+0 风险）；② 不轮换（接受"已暴露"事实） |

### 动作 4️⃣ 复核 4 个 `.env` 都在 .gitignore 内

| 字段 | 值 |
|---|---|
| **动作** | 检查 `D:\Coding\Contract\.gitignore` `Learning\.gitignore` `rss\.gitignore` 是否含 `.env` |
| **风险** | 🟢 零 |
| **回滚** | N/A（不改） |
| **验证** | 输出每个 .gitignore 的 .env 相关行 |

---

## 不做的事（明示）

- ❌ 不改 D 盘任何数据文件
- ❌ 不动 Coding 任何项目源码
- ❌ 不动 ChatRecords / backup / F 盘 / E 盘知识库
- ❌ 不推 git remote（即使有）
- ❌ 不读任何 S 级文件内容（只读 gitignore 文本）

---

## 执行顺序

如果全部 4 项你都 OK：

```
[1] 动作 1: 加 *.pem 到 ai-creativity/.gitignore
   ↓
[2] 动作 2: ai-creativity git add -A && git commit
   ↓
[3] 动作 3: Map key 挪位 + 建 git 仓库（轮换决策见上）
   ↓
[4] 动作 4: 复核 4 个 .gitignore（只读不改）
   ↓
[5] audit/operations/2026-09-13_phase1.json 留痕
```

---

## 你的决策点

请回答：

1. **动作 1、2、4** 你 OK 吗？（默认 ✅）
2. **动作 3 的轮换决策**：
   - A. 轮换 google maps key（推荐）
   - B. 不轮换，只挪位置

---

## 关联

- `[[../SECURITY]]` §1.2 三步走
- `[[../reports/2026-09-12_storage_landscape]]`
- 知识库 `[[D-Coding 代码资产盘点]]` P0 项