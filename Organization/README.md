# README.md · Organization 硬盘整理系统 · 入口

> **入口页。** 系统本体 = `org.py`（单一入口，内置安全规则）。

---

## 0. 快速上手（org.py）

```bash
cd D:\Coding\Organization

python org.py status              # 体检：PC-Plan映射 + git健康 + 敏感文件 + 磁盘余量（约7秒）
python org.py map                 # PC-Plan 归位映射表：哪些东西该去哪
python org.py scan <路径> --depth 2 --seconds 30      # 只读结构扫描（带护栏）
python org.py big  <路径> --mb 100                    # 大文件清单
python org.py dup  <路径> --seconds 120               # 重复文件（czkawka，自动排除权重目录）
python org.py plan-move <源> <目标> [--exclude *.log] # 生成移动计划（不执行）
python org.py apply <计划.json> --yes                  # 保护区摘除→复制→校验→删源
python org.py undo  <计划.json>                        # 一键回滚
python org.py snapshot <路径>                          # 快照到 snapshots/
```

**内置护栏（不用记，系统强制）**：
- 红线区永不写：`C:\` `G:\` `F:\temp` `D:\ChatRecords` `D:\backup` `E:\Obsidian`
- 敏感文件（`.env`/`_key`/`cookies`/`.pem`/`all_keys.json`/`dec_MSG*`）自动摘入 `_preserved/`，永不读内容
- 所有扫描带深度上限 + 时间预算 + 重目录排除（seed-vc/RVC-WebUI/node_modules…），不会再卡机
- 写动作三步走：plan → apply --yes → 可 undo

---

## 1. 我在哪里 / 数据在哪里 / 规则在哪里

```
你（人）现在看的 ← 本文件 (D:\Coding\Organization\README.md)
                          │
                          ├── AGENTS.md            系统规则（工作流）
                          ├── SECURITY.md          红线（更优先）
                          ├── scripts\             可复用脚本
                          ├── tools\               装在此处的 exe
                          ├── research\            存储现状研究
                          ├── audit\               不可变证据链
                          ├── reports\             人类可读报告
                          ├── logs\                脚本日志
                          ├── snapshots\           备份镜像
                          └── _pending_actions\    待执行清单

D 盘的所有其他目录       ← 你的原始数据（**不在本系统内**）
                              D:\Coding\      代码仓库
                              D:\ChatRecords\  微信解密
                              D:\KimiData\     Kimi 对话
                              D:\AI\           模型/本地 RAG
                              D:\TkPath\       特效素材
                              D:\backup\       旧版本回滚
                              D:\Antigravity_* IDE 缓存
                              D:\_tmp_*        临时文件
```

E 盘                      ← 知识库 + 工作区
                              E:\Obsidian\Hwalme\              第二大脑
                              E:\Obsidian\Hwalme\projects\_硬盘整理系统\  知识库侧整理系统
                              E:\Obsidian\.skills\             通用方法库

---

## 2. 第一次接入必读（4 篇，按顺序）

1. **[SECURITY.md](SECURITY.md)** —— 数据保护红线（S/P/I/R/P' 五级）
2. **[AGENTS.md](AGENTS.md)** —— 系统工作流（7 步流程）
3. **[research/2026-09-12_storage_landscape.md](research/2026-09-12_storage_landscape.md)** —— 你电脑现状
4. **[reports/2026-09-12_storage_landscape.md](reports/2026-09-12_storage_landscape.md)** —— 报告（人类可读版）

---

## 3. 工具清单（tools/）

| 工具 | 用途 | 状态 |
|---|---|---|
| fselect 0.10.3 (Win) | SQL 式查文件 | ⏸ 待装 |
| czkawka 12.0.2 CLI (Win) | 去重/空文件夹/大文件 | ⏸ 待装 |
| bge-small-zh-v1.5 (95MB) | 中文嵌入（落 D:\AI\LocalRAG\models\） | ⏸ 待装 |

**为什么都还没装**：按需原则。等真到了"需要查 SQL/找重复/做嵌入"那一步再装。

详细对比见知识库 `[[DiskUsageTools]]` `[[backup-dedup-tools]]` `[[bge-small-zh-v1.5]]` 等材料页。

---

## 4. 脚本清单（scripts/）

| 脚本 | 用途 | 状态 |
|---|---|---|
| `scan_storage_landscape.py` | 跑存储现状全景扫描 | ✅ v1 已验证 |
| `_audit_readonly.py` | D/Coding/E 顶层概览（v0 简单版） | ✅ 已在 |

详细用法见各脚本头部 docstring。

---

## 5. 报告索引（reports/）

| 日期 | 主题 | 链接 |
|---|---|---|
| 2026-09-12 | 存储现状全景（首次研究） | [[reports/2026-09-12_storage_landscape]] |

---

## 6. 证据链索引（audit/）

| 日期 | 主题 | 链接 |
|---|---|---|
| 2026-09-12 | 首次只读扫描证据 | `audit/2026-09-12_initial_scan.json` |

---

## 7. 待执行清单（_pending_actions/）

当前无（所有变更已完成 = 无需 backlog）。

如出现新需求，AI 会把清单写到 `_pending_actions/YYYY-MM-DD_主题.md`，等你 `OK` 才执行。

---

## 8. 与知识库的双向链接

```
Organization/AGENTS.md  ←→  E:\Obsidian\Hwalme\projects\_硬盘整理系统\AGENTS.md
Organization/SECURITY.md ←→  E:\Obsidian\Hwalme\projects\_硬盘整理系统\AGENTS.md §6
Organization/research/   →   Hwalme/wiki/sources/  (新发现入仓)
Organization/reports/    →   Hwalme/projects/_硬盘整理系统/扫描日志/
Organization/scripts/    ←   Hwalme/projects/_硬盘整理系统/_整理脚本库/
```

---

## 9. 我（Hwalme）现在能做什么

| 我想... | 走哪 |
|---|---|
| 看研究结果 | [[research/2026-09-12_storage_landscape]] |
| 看报告（人类版） | [[reports/2026-09-12_storage_landscape]] |
| 装某个工具 | 告诉我"装 fselect" / "装 czkawka" / "装 bge" |
| 跑一次扫描 | 告诉我"扫 X 目录" |
| 准备一个整理动作 | 我会先生成 `_pending_actions/*.md` 给你看 |
| 紧急停止 | 说"停"——立刻 kill 所有 + 留紧急记录 |

---

## 关联

- [SECURITY.md](SECURITY.md) —— 红线
- [AGENTS.md](AGENTS.md) —— 工作流
- [research/](research/) —— 存储研究
- [reports/](reports/) —— 报告
- [audit/](audit/) —— 证据链
- `E:\Obsidian\Hwalme\projects\_硬盘整理系统\系统总览` —— 知识库侧入口