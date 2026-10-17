---
title: "_pending_actions · 2026-09-13 阶段2 D:\\Coding\\Music\\ 迁移"
type: pending-action
created: "2026-09-13"
status: pending-approval
risk: medium
estimated_time: 10-30 min
tags: [pending-action, 阶段2, 迁移, Music, PC-Plan落地]
---

# 2026-09-13 · 阶段 2 · `D:\Coding\Music\` 迁移

> **按你 2026-09-13 决策：整体挪到 `F:\Date\Music\Tools\`**
> 目标位置：`F:\Date\Music\Tools\`（与 PC-Plan 的 Music 对齐）

---

## 为什么这个动作

- `D:\Coding\Music\` 不是普通 Coding 项目，是**你 Hwalme 配音产线工作区**
- 知识库 `[[D-Coding 代码资产盘点]]` 已识别这是配音产线（不在 Coding 该有的范围内）
- 你 2026-09-13 拍板：移到 `F:\Date\Music\Tools\`
- **注意**：F 盘的 Music 已有音乐素材，**Tools 是新分类**

---

## 源 vs 目标

**源（待移）**：
```
D:\Coding\Music\
├── 01_自然说话.m4a (1.1 MB)
├── 02_03_04.m4a (15 MB)
├── RVC-WebUI/ (35 项，~2 GB)
├── analysis_output/ (53 项，含图+视频)
├── archive_and_clean_tool.py (你的脚本)
├── backups/Music_Code_And_Configs.zip
├── human_pitch_workflow/
├── identity_singing_bridge/ (12 项)
├── identity_test/ (11 项)
├── prepare_voice_dataset_v2.py (你的脚本)
├── seed-vc/ (31 项，~9 GB - 知识库已记录)
├── seed_vc_finetune/ (5 项)
├── seed_vc_test/ (6 项)
├── separated/htdemucs/
├── voice_dataset/asr+raw
├── voice_dataset_v2/ (28 项)
├── voice_test/ (7 项)
├── 启动_RVC_WebUI.bat
├── 启动_Seed-VC_WebUI.bat
├── 回到从前_重制方案与声音采集稿.md
├── 声音采集.m4a (1.8 MB)
├── 瘦身与备份工具.bat
├── 真人修音方案/
└── 第二轮声音采集稿_自然歌声训练.md
```

**目标**：
```
F:\Date\Music\Tools\
├── RVC-WebUI/
├── seed-vc/
├── seed_vc_finetune/
├── seed_vc_test/
├── voice_dataset/
├── voice_dataset_v2/
├── voice_test/
├── analysis_output/
├── separated/
├── identity_singing_bridge/
├── identity_test/
├── human_pitch_workflow/
├── 真人修音方案/
├── backups/
├── *.py / *.bat / *.md / *.m4a 顶层文件
└── README.md  ← 我会加一个迁移说明
```

---

## 风险与回滚

| 风险点 | 处置 |
|---|---|
| seed-vc 9GB 移动耗时 | **robocopy** 多线程镜像，移动完才删源；预计 5-10 min |
| 移动中脚本/工具失败 | 回滚 = 整个目录已 robocopy 完成，删除目标即可 |
| 启动 .bat 路径引用 | 启动 .bat 是相对路径，**移动后无影响**（不引用绝对路径） |
| 移动后源 Coding 仍有 Music/ 空目录 | 我会**检查并清空空目录** |

---

## 不做的事

- ❌ 不改任何文件内容
- ❌ 不动 .git 仓库（Music 没 git，所以无影响）
- ❌ 不动 Coding 其它项目
- ❌ 不动 F:\Date\Music\ 现有内容（只新建 Tools 子目录）
- ❌ 不删源前不确认

---

## 执行方式（**双保险**）

```
[1] robocopy D:\Coding\Music\ F:\Date\Music\Tools\ /MIR /E /Z /MT:8
    → 镜像复制（含所有子目录、空目录、隐藏文件）
    → 进度可见，失败会标记
[2] 验证：du / robocopy 输出比对文件数
[3] 等你二次 OK → 才执行 rmdir /S /Q D:\Coding\Music
```

**默认不删源**——robocopy 完成后等你 `OK 删源` 才删。

---

## 你的决策点

请回答：

1. **整体迁移**你 OK 吗？（默认 ✅）
2. **删源时机**：
   - A. 验证完成后**立刻删源**（节省 25GB Coding 空间）
   - B. **保留源 7 天**再删（手动确认无误）
   - C. **永久保留源**（只 copy 不 move）

---

## 关联

- `[[2026-09-13_phase1_zero_risk]]`
- `[[../SECURITY]]` §1.2
- 知识库 `[[D-Coding 代码资产盘点]]` §1 配音产线
- `E:\Hrycg\PC-Plan.png` — Music 在 PC-Plan 中的位置