# safecleaner 规则库总览

> 四大来源 + 360，共五套清理规则，2026-10-17 整理

## 目录结构

```
safecleanerpro/
├── README_规则库总览.md          ← 本文件
├── docs/
│   └── 360清理规则逆向报告.md    ← 360 逆向方法与发现
├── decrypt_syssweeper.py        ← 360 .dat 解密脚本
└── rules/
    ├── 360/                     ← 360安全卫士（逆向）
    │   ├── trace_rules.json         910条痕迹规则（浏览器/注册表/SQLite）
    │   ├── trace_categories.json    13类
    │   ├── clean_categories.json    5大类20小类
    │   ├── app_rule_mapping.json    75款软件映射
    │   └── junk_file_extensions.txt 36种垃圾扩展名
    ├── winapp2/                 ← CCleaner社区规则（公开，明文）
    │   ├── winapp2_rules.json       4,068节 / 3,358款应用 / 14,121 FileKey
    │   ├── stats.txt                统计
    │   └── README.txt               格式说明（CC-BY-SA-4.0，需署名）
    ├── dism/                    ← Dism++ 系统级清理（开源）
    │   ├── dism_rules.json          73项163动作（WinSxS/更新缓存/驱动等）
    │   └── Dism清理机制总结.md      API与原理（DismAPI/CBS/compact等）
    ├── bleachbit/               ← BleachBit（开源，GPL）
    │   └── bleachbit_rules.json     107款软件 / 369项 / 1816动作
    └── qqpcmgr/                 ← 腾讯电脑管家（逆向未果，公开资料补）
        ├── REPORT.md                逆向过程（CryptoAPI强加密，未解出）
        └── tencent_app_paths.json   9条QQ/微信清理路径（公开资料整理）
```

（注：360 的 5 个文件在 rules/ 根目录历史原因未移入 360/ 子目录，内容不变。）

## 规则量对比

| 来源 | 规则规模 | 特点 | 许可/备注 |
|---|---|---|---|
| Winapp2.ini | 4,068节，14,121文件规则 | 应用覆盖最广，社区15年积累 | CC-BY-SA-4.0，分发需署名 |
| 360痕迹库 | 910条 | 浏览器/SQLite精细清理 | 逆向所得 |
| BleachBit | 1,816动作 | 跨平台，隐私痕迹细 | GPL |
| Dism++ | 73项163动作 | 系统级（WinSxS/CBS）独家 | 规则公开 |
| 腾讯管家 | 9条路径 | QQ/微信专用 | 公开资料整理 |

## 给 safecleaner 的集成建议

1. **先吃 Winapp2.ini**：量最大、格式最标准（Detect/FileKey/RegKey），写个解析器直接转你的规则格式。
2. **Dism++ 补系统级**：WinSxS 清理是 C 盘瘦身的核心，照抄它的 `DismComponentCleanup` 三分支逻辑。
3. **360 补浏览器深度**：SQLite 按表清理（如 Firefox places.sqlite 排除书签）是 360 独有的精细活。
4. **去重**：Winapp2 和 360/BleachBit 有大量重叠（如 Chrome 缓存），合并时按"路径+匹配"去重，优先保留带 SQL 条件的最精细规则。
5. **许可**：Winapp2（CC-BY-SA）和 BleachBit（GPL）再分发要注意开源许可；自用研究无碍。
