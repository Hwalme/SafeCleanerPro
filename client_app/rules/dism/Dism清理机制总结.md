# Dism++ 系统级清理机制技术总结

> 供 safecleaner 项目参考
> 仓库：`https://github.com/Chuyu-Team/Dism-Multi-language`（语言资源+规则仓库，浅克隆）
> 注意：此仓库只含 **Data.xml 规则文件**，Dism++ 主程序 C++ 源码不公开。
> 但 Data.xml（452KB，73 个清理项）本身就是完整的清理规则库，价值极高。

---

## 一、规则体系架构

Dism++ 的清理规则全部在 `Data.xml` 的 `<CleanCollection4>` 下，是**声明式规则**，清理引擎解析执行：

```xml
<Item Name="#被取代的WinSxS组件" Level="2">
  <Description>#清理被取代的组件并减少组件存储的大小。</Description>
  <Group>#过期文件</Group>
  <ScanCollection>
    <Scan Work="15">
      <Applicable>          <!-- 适用条件：OS版本、在线/离线等 -->
        <OSVersion Compare="&lt;">10.0</OSVersion>
      </Applicable>
      <Warning>#清理后将无法卸载更新…</Warning>
      <Activate>
        <Custom ProcName="DismComponentCleanup" Flags="#1"/>  <!-- 或 General -->
      </Activate>
    </Scan>
  </ScanCollection>
</Item>
```

**两种动作类型**（共 163 个动作）：

| 类型 | 数量 | 说明 |
|---|---|---|
| `General` | 147 | 路径规则：`RootPath` + `Query` 文件匹配，直接删文件/目录 |
| `Custom` | 15 | 调用内置 C++ 函数（复杂逻辑，如 WinSxS、驱动存储） |
| `ExplorerNotify` | 1 | 通知资源管理器刷新 |

**Level 含义**：0=默认不勾选（危险/较慢），1=谨慎，2=常规，3=安全。safecleaner 可照抄这套分级。

---

## 二、73 个清理项一览（按分组）

| 分组 | 数量 | 代表项 |
|---|---|---|
| 过期文件 | 14 | 被取代的WinSxS组件、以前的Windows系统、过期驱动、过期Appx |
| 系统相关 | 11 | Windows事件、Installer目录、系统还原点、CompactOs、硬链接合并 |
| 缓存文件 | 19 | Windows下载缓存、传递优化缓存、缩略图缓存、WinINet缓存 |
| 应用程序 | 7 | Package Cache、VS安装源、Office安装源、iTunes备份 |
| 备份文件 | 4 | Boot备份、硬链接备份 |
| 临时文件 | 18 | 临时文件、QQ/YY临时数据、dmp崩溃文件、各类日志 |

---

## 三、核心机制 1：Custom 内置函数（12 个）

这些是 Dism++ 真正的"黑科技"，对应 C++ 实现（源码未公开，但功能可从描述+公开 API 推断）：

| 函数名 | 清理项 | 原理（推断） | safecleaner 可借鉴的公开 API |
|---|---|---|---|
| `DismComponentCleanup` | 被取代的WinSxS组件 | 清理被取代的 CBS 组件。Vista~8.1 与 Win10 在线/离线走不同分支 | `Dism.exe /Online /Cleanup-Image /StartComponentCleanup [/ResetBase]`；或调用 `DismAPI.dll` 的 `DismCleanupImage`。Flags=#1 疑似 ResetBase 模式 |
| `DismDriverCleanup` | 过期驱动 | 删除驱动存储池中不用的旧版驱动 | `pnputil /delete-driver <oemNN.inf> /uninstall`；枚举 `DriverStore\FileRepository` 比对当前使用 |
| `DismAppxsCleanup` | 系统自带Appx / 过期Appx | 移除 Appx（在线用 PowerShell，离线操作镜像） | `Get-AppxPackage \| Remove-AppxPackage`；`Dism /Remove-ProvisionedAppxPackage` |
| `DismCompactOs` | CompactOs | 对只读系统文件做哈夫曼压缩（CompactOS） | `compact.exe /CompactOs:always` |
| `DismHardLinkMerge` | 硬链接合并 | 用 NTFS 硬链接合并内容相同的文件 | `FSCTL_DUPLICATE_EXTENTS_TO_FILE` 或自行实现 |
| `NCInstallerFolderCleanup` | Installer目录 | 清理 `%SystemRoot%\Installer` 中被取代的 .msp 补丁 | 需解析 msp 与产品码的映射（Windows Installer API `MsiGetPatchInfo`），实验性功能 |
| `NCSRPointOnlineCleanup` | 系统还原点 | 删全部还原点后新建一个 | `vssadmin delete shadows /all` + `wmic` 创建；或 `SRRemoveRestorePoint` API |
| `NCWinEventLogOnlineCleanup` | Windows事件 | 清空事件日志 | `wevtutil cl <LogName>` / `EvtClearLog` API |
| `NCDOCacheOnlineCleanup` | 传递优化缓存 | 清 Delivery Optimization 缓存 | 停 `DoSvc` 服务后删 `SoftwareDistribution\DeliveryOptimization` |
| `NCPackageCacheFolderCleanup` | Package Cache | 清 WiX 安装源缓存 | `%ProgramData%\Package Cache\`，注意保留卸载所需（Dism++ 有警告） |
| `NCVSPackageCacheCleanup` | VS安装源缓存 | 清 VS2017+ 安装源 | `%ProgramData%\Microsoft\VisualStudio\Packages\` |
| `NCCorruptedAppXOnlineCleanup` | 损坏的Appx | 清理损坏的 Appx 注册 | 枚举 Appx 包状态，删 `Staged` 失败项 |

**关键洞察**：Dism++ 把"难删的系统级垃圾"封装成 Custom 函数，"好删的路径垃圾"用 General 规则。这种**双轨制**值得 safecleaner 照抄。

---

## 四、核心机制 2：General 路径规则

### 4.1 路径变量

| 变量 | 含义 |
|---|---|
| `%SystemDrive%` / `%SystemRoot%` / `%System%` | 系统盘 / Windows 目录 / System32 |
| `%Temp%` / `%APPDATA%` / `%ProgramData%` | 标准环境变量 |
| `%0%` | Dism++ 自身目录（清自己的缓存/旧组件） |
| `?GetRegSz(HKLM\...,值名)` | **从注册表动态解析路径**，如 Chrome 安装目录 |

`?GetRegSz` 是精髓：很多软件的老版本备份目录位置不固定，Dism++ 先读注册表拿安装路径，再按 `*.*.*.*`（版本号目录通配）匹配删除。safecleaner 清理"XX软件老版本备份"时可照抄此模式。

### 4.2 关键系统路径（直接可用）

**Windows 更新相关**：
- `%SystemRoot%\SoftwareDistribution\Download` — 更新下载缓存
- `%SystemRoot%\SoftwareDistribution\DataStore` — 更新数据库
- `%SystemRoot%\SoftwareDistribution\DeliveryOptimization` — 传递优化缓存
- `%SystemRoot%\WinSxS\ManifestCache`、`%SystemRoot%\CbsTemp\` — WinSxS 临时文件

**错误报告**：
- `%SystemDrive%\Users\*\AppData\Local\Microsoft\Windows\WER\`
- `%ProgramData%\Microsoft\Windows\WER\`
- `%SystemRoot%\LiveKernelReports` — 内核崩溃报告

**事件日志**：
- `%System%\winevt\Logs`（配合 `wevtutil cl` 更干净）

**旧系统**：
- `%SystemDrive%\Windows.old*` — 大版本升级残留

**临时目录（多用户/多服务全覆盖）**：
- `%Temp%`、`?GetRegSz(HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment,TEMP)`
- `%SystemDrive%\Users\*\AppData\Local\Packages\*\AC\Temp\` — UWP 应用临时
- `%SystemRoot%\ServiceProfiles\*\AppData\Local\Temp\` — 服务账户临时
- `%System%\config\systemprofile\AppData\Local\Temp\` — SYSTEM 账户临时

**其他**：
- `%ProgramData%\Microsoft\Windows\RetailDemo\` — 零售演示内容
- `%USERPROFILE%\.nuget` — NuGet 包缓存
- 缩略图：`%LocalAppData%\Microsoft\Windows\Explorer\thumbcache_*.db`

---

## 五、WinSxS / CBS 清理详解（safecleaner 必看）

Dism++ 对 WinSxS 做了**三分支**处理（`Applicable` 条件）：

1. **Vista ~ 8.1**：`DismComponentCleanup`（等价于 `dism /online /cleanup-image /spsuperseded`）
2. **Win10+ 在线**：`DismComponentCleanup Flags="#1"`（带 ResetBase，警告"无法卸载更新、与系统重置冲突"）
3. **Win10+ 离线**：`DismComponentCleanup`（无 ResetBase，避免离线重启麻烦）

**safecleaner 实现建议**：
- 最稳：调用 `Dism.exe /Online /Cleanup-Image /AnalyzeComponentStore` 先分析，再 `/StartComponentCleanup`
- 更底层：P/Invoke `DismAPI.dll`（`DismInitialize` → `DismOpenSession` → `DismCleanupImage`），避免拉起外部进程
- 务必先做适用性检查：只有 `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\SideBySide\Configuration` 允许且 CBS 未损坏时才执行；提供"分析"与"清理"两步，ResetBase 默认关闭

---

## 六、safecleaner 可直接借鉴的点

1. **规则文件外置**：Data.xml 证明"清理引擎 + XML 规则"架构可行，规则可热更新、可社区贡献。safecleaner 的规则也放 JSON/XML，别硬编码。
2. **Level 分级**：0=危险默认关，3=安全默认开。照抄。
3. **Applicable 条件**：按 OS 版本/在线离线切换规则，避免 Win7 规则跑到 Win11 上翻车。
4. **Warning 文案**：每个危险项配一段后果说明（如"清理后无法卸载更新"），这是专业度的体现。
5. **?GetRegSz 动态路径**：对付安装位置不固定的软件，比写死路径 robust 得多。
6. **双轨制**：路径删除走通用规则；WinSxS/驱动/Appx/还原点走专用函数（调系统 API）。
7. **先分析后清理**：WinSxS、驱动清理都先给"可清理量"，用户确认再动手。

---

## 七、关键文件位置

| 文件 | 说明 |
|---|---|
| `repo/Data.xml` | 全部 73 项清理规则（452KB），`<CleanCollection4>` |
| `work/dism/dism_rules.json` | 已解析为 JSON（本任务产出），73 项 × 163 动作 |
| `repo/HeplerDism.md` | 赞助名单（无技术内容） |
| `repo/Languages/zh-Hans.xml` | 中文文案（清理项显示名） |
| 主程序源码 | **未公开**（Custom 函数实现不可见） |

## 八、局限

- Dism++ 主程序闭源，`DismComponentCleanup` 等 12 个 Custom 函数的具体实现只能从规则描述+公开 Windows API 反推，无法逐行对照。
- Data.xml 中部分规则带 `(by xxx)` 社区贡献标记，质量参差，safecleaner 引用时建议按 Level≥2 优先。
