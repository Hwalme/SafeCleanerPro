# AGENTS.md · Organization 硬盘整理系统 · 协作规则

> **任何 AI 接入本目录第一件事读它。**
> 上位规则：`D:\Coding\Organization\SECURITY.md`（**先读那个**）。

---

## 0. 这是什么

本目录 `D:\Coding\Organization\` 是**Hwalme 的硬盘整理工作台**：
- 系统骨架在这里（AGENTS / SECURITY / 脚本 / 工具）
- 研究在这里（research/）
- 所有报告在这里（audit/ reports/）
- **不存放任何原始数据**（D 盘的其他目录才是数据）

---

## 1. 目录约定（9 个区）

```
D:\Coding\Organization\
├── AGENTS.md            ← 本规则（先读）
├── SECURITY.md          ← 数据保护规范（更优先）
├── README.md            ← 入口（人在哪里、AI 在哪里、数据在哪里）
├── scripts\             ← 可复用 Python/Shell 脚本（只读为主）
├── tools\               ← 装在此处的 exe（不污染系统 PATH）
├── research\            ← 存储现状研究（分布/风险/能量）
├── audit\               ← 不可变证据链（只追加，永不删）
│   └── operations\      ← 每次操作的 JSON 记录
├── reports\             ← 人类可读的扫描报告（markdown）
├── logs\                ← 脚本运行日志（保留 90 天）
├── snapshots\           ← 动文件前的备份镜像
└── _pending_actions\    ← 准备动但还没动的清单（执行后清）
```

---

## 2. 工作流（与知识库 `[[_硬盘整理系统 AGENTS]]` 同源）

```
[1] RESEARCH（research/）
    ↓ 只读扫描 + 现状分析
[2] REPORT（reports/ + audit/）
    ↓ 出报告 + 落证据
[3] PROPOSE（_pending_actions/）
    ↓ 列出"准备动什么"
[4] BACKUP（snapshots/）
    ↓ 写动作前先快照
[5] APPROVAL（你点头）
    ↓ 改 status: approved
[6] EXECUTE
    ↓ 按清单执行 + 实时记录
[7] VERIFY
    ↓ 验证结果 + 更新 audit
```

---

## 3. 规则（4 条核心）

### 3.1 只读优先
- **默认所有脚本只读**。写动作必须先有 `_pending_actions/*.md` approved
- 即使是"小动作"（改一个 txt）也要走流程
- 例外：写入本目录自身 + 写入 `audit/ logs/ snapshots/`

### 3.2 不发明规则
- **整理动作必须服务一个具体问题**——按 `[[按需整理]]` 的 7 步流程
- 不按网上固定 SOP 整理
- 不"心情好整理一下"

### 3.3 沉淀一切
- 每次扫描 → 报告落 `audit/` + `reports/`
- 每个工具 → 装到 `tools/` + 在 `tools/README.md` 登记
- 每个新发现的风险 → 进 `research/findings/`
- 每个被执行的写动作 → 进 `audit/operations/` + 写摘要到 `reports/`

### 3.4 可回滚
- 每个写动作前必有 `snapshots/` 镜像
- `audit/operations/` 是回滚的"说明书"
- `snapshots/` 保留 30 天后自动归档到 `D:\Coding\Organization\_archive\`

---

## 4. 与知识库的关系（双向）

```
D:\Coding\Organization\   ↔   E:\Obsidian\Hwalme\projects\_硬盘整理系统\
         系统骨架                       知识沉淀
         工程实现                       方法论
         数据/扫描/证据                  概念/材料/报告
```

**同步规则**：
- 知识库的"按需整理"方法论 → 本目录"工作流"的基础
- 本目录的"新工具/新发现" → 知识库的 `wiki/sources/` 新材料
- 本目录的"扫描报告" → 知识库的 `projects/_硬盘整理系统/扫描日志/`
- **本目录修改 SECURITY 时**，知识库对应章节同步更新

**当前同步状态**：✅ v1 已对齐（2026-09-12）

---

## 5. AI 接入清单

任何 AI（Claude Code / Codex / DeepSeek Harness / ZCode）接入本目录必读：

1. **第一读**：`SECURITY.md`（红线）
2. **第二读**：`AGENTS.md`（本文件，工作流）
3. **第三读**：`README.md`（入口地图）
4. **第四读**：最近一份 `audit/operations/*.json`（上次发生了什么）
5. **第五读**：`_pending_actions/` 里 approved 的清单（待执行）

接入后**第一次动作**必须是只读扫描（在 `audit/operations/` 留首条记录）。

---

## 6. 错误处理

| 情况 | 处置 |
|---|---|
| 脚本抛异常 | 写 `audit/operations/ERROR_<ts>.json`，不重试 |
| 发现 S 级数据外露 | 立刻停手 + 写 `audit/operations/SECURITY_INCIDENT_<ts>.json` + 报警 |
| 用户说"停" | 立即 kill 所有子进程 + 写紧急停止记录 |
| snapshot 失败 | **不执行写动作**，先排查 snapshot 问题 |
| 用户没批准就有人动 | **回滚** + 追责 |

---

## 7. 当前进度（2026-09-12）

- ✅ 系统骨架（9 个目录 + SECURITY.md + AGENTS.md + README.md）
- ✅ 首次存储研究：`research/2026-09-12_storage_landscape.md`
- ✅ 首次扫描脚本：`scripts/scan_storage_landscape.py`
- ✅ 首次只读扫描报告：`audit/2026-09-12_initial_scan.json` + `reports/2026-09-12_storage_landscape.md`
- ✅ 知识库双向链接建立

---

## 8. 修改历史

| 日期 | 改动 |
|---|---|
| 2026-09-12 | v1 建立 |

---

## 关联

- `[[SECURITY]]` —— 更优先的红线文件
- `[[README]]` —— 入口
- `E:\Obsidian\Hwalme\projects\_硬盘整理系统\AGENTS.md`
- `E:\Obsidian\Hwalme\wiki\concepts\按需整理.md`