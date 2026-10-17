# SECURITY.md · 数据保护高规格规范

> **本目录的最高规则文件。任何 AI 接入、人操作前必须先读本文件。**
> 修改本文件需经你（Hwalme）书面确认，并留下 commit / 时间戳。

---

## 0. 核心承诺

**任何脚本、任何 AI、任何工具，对你电脑里以下数据的接触必须遵循本规范。违反 = 系统失信，立刻停手。**

被保护的数据等级（从高到低）：

| 等级 | 数据类型 | 例 | 允许动作 |
|---|---|---|---|
| 🔴 **S**（Secret） | 密钥、Cookie、明文凭据、私钥 | `.env` / `_key.txt` / `cookies.txt` | **只读取也要记日志；写入 = 禁止；传输 = 禁止** |
| 🔴 **P**（Private） | 解密库、原始聊天记录、商业合同 | `D:\ChatRecords\`、`Contract\` | **只读；移动/删除 = 需你书面 OK + 备份先行** |
| 🟡 **I**（Important） | 未版本控制、未推送的创作 | `ai-creativity\`、自建项目 | **动之前必有备份快照** |
| 🟡 **R**（Reproducible） | 模型权重、开源 zip、IDE 缓存 | seed-vc/ ViiTorVoice/ Antigravity 备份 | **可清可删（不心疼），但要列清单** |
| 🟢 **P'**（Public） | 公共素材、开源项目（无改） | `*.github.io`、官方文档 | **安全** |

---

## 1. 不可变证据链（每次操作必留痕）

任何动文件 / 动数据 / 跑扫描的动作，都必须生成一条 `audit/operations/<YYYY-MM-DD>_<action>.json`，**包含**：

```json
{
  "action": "scan_coding_top",
  "actor": "agent:claude-opus-4",
  "ts_start": "2026-09-12T23:55:00Z",
  "ts_end":   "2026-09-12T23:55:03Z",
  "scope":    ["D:\\Coding"],
  "files_touched": 0,           // 只读 = 0
  "files_read": 72,
  "data_classifications": {     // 触碰到哪些等级
    "S": 0,
    "P": 0,
    "I": 0,
    "R": 12,
    "P'": 60
  },
  "sha256_evidence": {
    "D:\\Coding\\Map\\google_maps_api_key.txt": "<hash>",   // 触碰到密钥时必留
    ...
  },
  "user_approval": "pending|granted|denied",
  "rollback_plan": null|"<how to revert>"
}
```

**关键约束**：
- `user_approval=pending` 时**禁止执行任何写动作**
- 触碰 S/P/I 数据时，必须有完整 sha256 证据
- `audit/` 目录本身**只追加，不修改、不删**

---

## 2. 备份前置原则（写动作三步走）

任何**写**动作（移动、删除、改名、修改内容）必须走完：

```
[1] SNAPSHOT（快照）
    snapshots/<YYYY-MM-DD>_<scope>_<reason>/
    镜像被影响目录（robocopy /MIR 或 git clone）

[2] REPORT（清单 + 预计影响）
    _pending_actions/<YYYY-MM-DD>_<action>.md
    列每个被影响的文件、新位置、回滚方式、预计耗时

[3] APPROVAL（你点头）
    改 _pending_actions 文件 frontmatter: status: approved
    只有 approved 后才能执行
```

**例外**（不需要走三步）：
- 仅写入 `D:\Coding\Organization\` 自身（系统目录）
- 仅写入 `audit/ logs/ snapshots/`（系统产出）
- 已有 git 版本控制的**已提交**文件（git revert 就够）

---

## 3. 🔴 红线（违反任意一条 = 立刻停手 + 报警）

| 编号 | 红线 | 例 |
|---|---|---|
| **R1** | **不删 S 级文件** | 密钥、私钥 |
| **R2** | **不外传 P 级数据** | 微信解密库、商单合同 |
| **R3** | **不覆盖 I 级未提交内容** | ai-creativity 在 `git add` 之前 |
| **R4** | **不在公开网络传输 P/I 级数据** | 不上传到云 LLM |
| **R5** | **不在日志/报告里复述密钥原文** | `all_keys.json` 内容只能引用 hash |
| **R6** | **不执行"恢复出厂"类操作** | `rm -rf /d` 等 |
| **R7** | **不修改 Hwalme 知识库结构** | 知识库 AGENTS.md 之外的变动要 OK |
| **R8** | **不动软链本体** | `fgdata_isolated_*` 软链不能改 |

---

## 4. 🔒 S/P 级数据发现规则（默认不读取）

| 规则 | 实现 |
|---|---|
| 默认**不读** `.env` / `_key` / `cookies` / `*secret*` / `*.pem` | 扫描脚本里加 denylist，命中即跳过 + 报警 |
| 默认**不读** `D:\ChatRecords\` 内的密钥文件 | 同上 |
| 报告里出现这些文件时，**只列路径 + 大小 + sha256**，不复述内容 | 模板强制 |

---

## 5. 🤖 AI 操作约束

| 约束 | 说明 |
|---|---|
| **任何 AI 都先读本文件** | AGENTS.md 第一段强制 |
| **AI 不直接执行写动作** | 只生成清单（`_pending_actions/*.md`），由你审核 |
| **AI 不主动 `rm`** | 任何删除必须先列清单 |
| **AI 不复制 P 级数据到 Organization/** | `audit/` `logs/` `snapshots/` 除外 |
| **AI 不上传任何文件** | 除非你显式 `upload <path>` |
| **AI 的所有 bash / python 调用必须可审计** | 落 `audit/operations/*.json` |

---

## 6. 🛡️ 工具层防护（脚本内嵌）

所有 `scripts/*.py` 必须满足：

```python
# 必须有的头部
DENY_PATTERNS = [
    r"\.env$", r"_key\.txt$", r"_secret", r"cookies\.txt$",
    r"\.pem$", r"\.key$", r"id_rsa", r"all_keys\.json$",
    r"\.wxdump$", r"dec_MSG"
]

def is_protected(path: str) -> bool:
    """检查路径是否命中 S/P 级"""
    return any(re.search(p, path, re.IGNORECASE) for p in DENY_PATTERNS)
```

**不满足此约束的脚本禁止入库**。

---

## 7. 📋 审计报告留痕规则

- 所有 `audit/operations/*.json` 必须留 90 天
- 每月 1 日 `git diff --stat audit/` 看是否有异常
- **审计日志本身永不删除**

---

## 8. 🚨 紧急停止机制

如果你对任何动作说"停"，立刻：
1. 停所有运行中的脚本（kill PID 写 `audit/operations/EMERGENCY_STOP_<ts>.json`）
2. 不重试、不"先做一步再说"
3. 把现场快照到 `snapshots/EMERGENCY_<ts>/`
4. 等你下一步指令

---

## 9. 与知识库的关系

- 本规范 = `E:\Obsidian\Hwalme\projects\_硬盘整理系统\SECURITY` 的工程镜像（更严）
- 知识库 `[[_硬盘整理系统 AGENTS]]` §6 的红线 → 本文件 §3 的来源
- 知识库 `[[按需整理]]` 的"安全原则" → 本文件 §1-§2 的来源
- **本文件修改时**，知识库对应章节必须同步更新；反之亦然

---

## 10. 修改历史

| 日期 | 改动人 | 改动 |
|---|---|---|
| 2026-09-12 | Hwalme + AI（ZCode）首次落定 | 建立完整规范 v1 |

---

## 关联

- `[[AGENTS.md]]` —— 系统规则（与本文件配合使用）
- `[[README.md]]` —— 系统入口
- `E:\Obsidian\Hwalme\projects\_硬盘整理系统\AGENTS.md`
- `E:\Obsidian\Hwalme\wiki\concepts\按需整理.md`