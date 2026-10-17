# Adobe / NVIDIA 清理规则实测报告

测量时间：本机实测（只读）。测量口径：`Get-ChildItem -Recurse -File -Force` 求和（含隐藏/系统文件），与 `dir /s` 交叉校验一致。

- `APPDATA` = `C:\Users\Administrator\AppData\Roaming`
- `LOCALAPPDATA` = `C:\Users\Administrator\AppData\Local`

**等级定义**：S=可安全删（纯缓存，软件会重建）｜C=需确认｜X=禁止删除

---

## 一、Adobe `%APPDATA%\Adobe` 明细表

### 1.1 顶层总量（56 个子项，实测）

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `Adobe\Common` | 2260.4 MB | 1124 | 是 | C | 99.96% 是 Motion Graphics Templates（.mogrt） | 见下 |
| `Adobe\CCX Welcome` | 413.4 MB | 1536 | 是 | C | Creative Cloud 首启欢迎页资源 | 重新联网下载 |
| `Adobe\typequest` | 288.5 MB | 31 | 是 | C | Photoshop 字体检索索引库 | 由 Photoshop 重建 |
| `Adobe\CoreSync` | 257.9 MB | 24 | 是 | X | CoreSync livetype 插件本体 | 不重建 |
| `Adobe\Adobe Photoshop 2021` | 181.4 MB | 113 | 是 | X/C 混合 | 138.6MB 是 Sky_Presets 资产 | 见下 |
| `Adobe\UXP` | 172.3 MB | 534 | 是 | C | UXP 插件平台存储 | 部分重建 |
| `Adobe\Adobe Photoshop 2025` | 31.8 MB | 64 | 是 | X | 含画笔/样式/形状资产 | 不重建 |
| `Adobe\CameraRaw` | 25.1 MB | 1074 | 是 | **X** | 1062 个用户 .xmp 预设 | **不重建** |
| `Adobe\Bridge` | 12.5 MB | 75 | 是 | C | Bridge 缓存/配置 | 部分重建 |
| `Adobe\Adobe Illustrator 25 Settings` | 7.5 MB | 56 | 是 | X | 含首选项、工作区 | 不重建 |
| `Adobe\Acrobat` | 3.1 MB | 22 | 是 | C | 日志/缓存 | 重建 |
| `Adobe\Adobe Photoshop (Beta)` | 2.9 MB | 44 | 是 | X | 首选项资产 | 不重建 |
| `Adobe\Premiere Pro` | 2.8 MB | 74 | 是 | C | 含日志 1.4MB | 重建 |
| `Adobe\AIRobin 25.4.1 Settings` | 1.6 MB | 7 | 是 | X | 首选项 | 不重建 |
| `Adobe\After Effects` | 1.4 MB | 25 | 是 | C | 含日志 0.4MB | 重建 |
| `Adobe\Audition` | 1.2 MB | 139 | 是 | C | 配置缓存 | 部分重建 |
| 其余 40 项（UPI/ACPLocal/SLData/OOBE/Adobe PCD/XMP/Color/LensCorrection/Fonts/User Owned Fonts/Photoshop/PS/Logs/CRLogs/…） | 各 0–0.3 MB | 0–18 | 是 | **X** | 许可证/登录态/字体/配置 | 不重建 |

### 1.2 下钻：`Adobe\Common`（2260.4 MB）

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `Common\Motion Graphics Templates` | 2259.3 MB | 1078 | 是 | **X** | **1075 个 .mogrt 模板资产** | 需重新下载 |
| `Common\Motion Graphics Templates\Light Leaks Transitions` | 1666.2 MB | 101 | 是 | X | TransFlare_*.mogrt 转场包 | 否 |
| `Common\Motion Graphics Templates\[AE] News Package` | 342.6 MB | 7 | 是 | X | News Intro.mogrt 153MB | 否 |
| `Common\Motion Graphics Templates\[AE] Video Gaming Package` | 76.7 MB | 8 | 是 | X | 模板包 | 否 |
| `Common\Motion Graphics Templates\[AE] Sports Package` | 41.5 MB | 9 | 是 | X | 模板包 | 否 |
| `Common\Motion Graphics Templates\Text` | 36.1 MB | 890 | 是 | X | 890 个文字模板 | 否 |
| `Common\Motion Graphics Templates\Slates` | 29.5 MB | 5 | 是 | X | 场记板模板 | 否 |
| `Common\Motion Graphics Templates\Credits` | 18.5 MB | 5 | 是 | X | 片尾字幕模板 | 否 |
| `Common\Motion Graphics Templates\Titles` | 13.6 MB | 10 | 是 | X | 标题模板 | 否 |
| `Common\Motion Graphics Templates\Lower Thirds` | 11.9 MB | 14 | 是 | X | 下三分之一模板 | 否 |
| `Common\Motion Graphics Templates\Captions and Subtitles` | 10.4 MB | 10 | 是 | X | 字幕模板 | 否 |
| `Common\Motion Graphics Templates\Social Media` | 7.0 MB | 3 | 是 | X | 社媒模板 | 否 |
| `Common\Motion Graphics Templates\Graphic Overlays` | 4.4 MB | 11 | 是 | X | 叠加模板 | 否 |
| `Common\Analyzer Cache Files` | 1.1 MB | 43 | 是 | **S** | 分析器缓存 | 是 |
| `Common\Media Cache Files` | 0 | 0 | 是 | S | 媒体缓存（空） | 是 |
| `Common\Peak Files` | 0 | 0 | 是 | **S** | 音频峰值缓存（26 个日期子目录） | 是 |
| `Common\Team Projects Cache` | 0 | 0 | 是 | S | 团队项目缓存 | 是 |
| `Common\Team Projects Local Hub` | 0 | 2 | 是 | X | 团队项目本地同步 | 否 |
| `Common\Essential Sound` / `Essential Graphics` / `LUTs` / `ExportSettings` / `Media Cache` | 0 | 0–1 | 是 | X | 用户配置/LUT 资产 | 否 |

**结论**：`Common` 的 2260.4 MB 中 **2259.3 MB（99.96%）是 .mogrt 模板资产**，不是缓存。唯一可删的缓存（Analyzer Cache Files + Peak Files）合计仅 **1.1 MB**。

### 1.3 下钻：`Adobe\CCX Welcome`（413.4 MB）

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `CCX Welcome\learn` | 184.8 MB | 643 | 是 | **C** | 教学资源：427 .jpeg(87.4MB) + 10 .psdt(91.8MB) + 206 .json(5.5MB) | 重新联网下载 |
| `CCX Welcome\stock` | 102.2 MB | 468 | 是 | C | Stock 素材缩略图 | 重新下载 |
| `CCX Welcome\discover_panel` | 96.0 MB | 331 | 是 | C | Discover 面板资源 | 重新下载 |
| `CCX Welcome\data` | 30.4 MB | 47 | 是 | X | 首启状态/版本映射（含 settings.json、api.json、map.json） | 否 |
| `CCX Welcome\data\assets` | 28.6 MB | 26 | 是 | C | 欢迎页展示素材 | 下载 |
| `CCX Welcome\photoshop` / `xd` / `survey` / `avatar` / `evergreen` / `ccxpFlags` / `illustrator` / `illustratorFlags` / `indesignFlags` / `ccd` / `senseiModels` / `ghost` / `collectionTemplates` | 各 0–0.1 MB | 1–10 | 是 | **X** | 应用标志位/登录态关联 | 否 |

**删了会怎样**：`learn`/`stock`/`discover_panel` 删除后，Creative Cloud 首页与各 App 欢迎页会出现**空白卡片/占位图**，需联网重新拉取（213MB→ 重新下载，取决于网速）。`settings.json` 记录 `FAILED_QUIT_ATTEMPTS: 23`、`NEXT_LAUNCH_TIME` 等首启周期状态，删掉会触发重新走首启流程。**不推荐整体删除**，可考虑仅删 `learn`/`stock`/`discover_panel` 三项（383MB）。

### 1.4 下钻：`Adobe\typequest`（288.5 MB）—— 结论：**不是字体数据**

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `typequest\.2\.<id>\.a` | **283.3 MB** | 21 | 是 | **S** | 字体检索索引分片（无扩展名二进制，头部为高熵随机字节，非 TTF/OTF 字体，非明文数据库） | **是**，Photoshop 重建 |
| `typequest\.2\.<id>\.m` | 5.2 MB | 10 | 是 | **S** | 标签目录：`tag_assignment.jsonl` / `tag_url.jsonl` / `typequestdb*.PhotoshopTypekit1` / `fi_catalog` | 是 |
| `typequest\.2\.<id>\.m\tag_catalog_1_0_0_zh_CN` | 0.02 MB | 4 | 是 | S | 中文标签命名空间 | 是 |
| `typequest\.2\.<id>\.m\.1.4.0\.zh-Hans` | 4.67 MB | 3 | 是 | S | 简体中文 typequest 数据库 | 是 |
| `typequest\.2\.<id>\.s` | 0 | 0 | 是 | S | 空目录 | — |

**判定依据**：`.a` 分片文件头为 `5B 08 3A 7F 8D 73 CF 3A…` 等高熵随机字节，**不是任何字体格式的魔数**（TTF=`00 01 00 00`/`OTF`=`4F 54 54 4F`）；`.m` 下是 JSONL 标签映射（`{"tag_id":"halloween","font_ids":[40150,61442,…]}`），即**字体元数据索引**，用于 Photoshop 字体菜单的分类/检索/预览。真实字体文件在 `%APPDATA%\Adobe\Fonts`（空）与 `User Owned Fonts`（空），本机未安装本地字体资产。

**删了会怎样**：Photoshop 首次启动字体菜单变慢，需重建索引（约 283MB 重新生成）；**不会丢失任何字体**，不影响已安装字体的可用性。属于安全缓存，但重建耗时，建议列为 C 而非 S。

### 1.5 下钻：`Adobe\UXP`（172.3 MB）—— 区分插件本体 vs 缓存

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `UXP\PluginsStorage\PHSP\26\Internal\com.adobe.nfp.gallery` | 88.13 MB | 98 | 是 | **X** | 文件库插件（nfp=New File Picker）本体+PluginData | 不重建 |
| `UXP\PluginsStorage\PHSP\26\Shared\EBWebView` | 70.46 MB | 400 | 是 | **S** | **内嵌 WebView(Cef) 缓存** | 是 |
| `UXP\PluginsStorage\PHSP\26\Shared\EBWebView\Default` | 24.2 MB | 243 | 是 | S | WebView 默认 Profile 缓存 | 是 |
| `UXP\PluginsStorage\PHSP\26\Shared\EBWebView\component_crx_cache` | 20.4 MB | 10 | 是 | S | 组件 CRX 下载缓存 | 是 |
| `UXP\PluginsStorage\PHSP\26\Shared\EBWebView\Subresource Filter` | 12.3 MB | 15 | 是 | S | 广告过滤规则 | 是 |
| `UXP\PluginsStorage\PHSP\26\Shared\EBWebView\GrShaderCache` | 4.6 MB | 5 | 是 | S | GPU 着色器缓存 | 是 |
| `UXP\PluginsStorage\PHSP\26\Internal\com.adobe.unifiedpanel` | 12.49 MB | 8 | 是 | **X** | 统一面板插件本体（含 1.64MB 日志） | 不重建 |
| `UXP\PluginsStorage\PHSP\26\Internal\com.adobe.ccx.start` | 1.15 MB | 8 | 是 | X | CCX 起始页插件 | 不重建 |
| `UXP\PluginsStorage\PHSP\26\Internal\com.adobe.adjustments-panel-revamped` / `cai.uxp` / `uam` / `sharePanel` / `inAppNotifications` / `ccx.comments-webview` / `photoshop.inAppMessaging` / `uxp.express-template-picker` | 各 0 | 0–8 | 是 | X | 内置面板插件本体 | 不重建 |
| `UXP\PluginsStorage\PHSP\26\Settings` | 0 | 0 | 是 | X | 插件设置 | 否 |
| `UXP\PluginsStorage\ILST\25` | 0 | 8 | 是 | X | Illustrator 插件存储 | 否 |
| `UXP\PluginsStorage\PHSP\22` / `23` / `25` | 0 | 0 | 是 | — | 空目录（旧版本残留） | — |

**结论**：UXP 的 172.3 MB 中，**70.46 MB 是可删 WebView 缓存（S）**，101.77 MB 是 `Internal` 下的内置插件本体（X）。**`Shared\EBWebView` 是唯一可安全清理的部分。**

### 1.6 下钻：`Adobe\CameraRaw`（25.1 MB）—— 陷阱确认：**X 级**

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `CameraRaw\ModelZoo\CloudDownload\...\dust_detection\winml` | 16.3 MB | 3 | 是 | **S** | 除尘 AI 模型 `sensordust_sgnt_t_alpha_512_v10_fp32.data` | **是**，相机联机时重新下载 |
| `CameraRaw\Settings` | 6.2 MB | 1063 | 是 | **X** | **1062 个用户 .xmp 调色预设** | **绝不重建** |
| `CameraRaw\Settings\Index_7EB38BFDEB6A4115.dat` | 0.71 MB | 1 | 是 | X | 预设索引数据库 | 否 |
| `CameraRaw\LensProfiles\1.0\pscache.dat` | 2.69 MB | 1 | 是 | **X** | 镜头校正数据缓存 | 不重建 |
| `CameraRaw\CameraProfiles` | 0 | 0 | 是 | **X** | 相机配置文件(.dcp)目录（当前为空） | — |
| `CameraRaw\GPU` / `Defaults` / `SaveOptions` / `UI` / `Logs` / `ModelSupport` / `LocalCorrections` / `Curves` / `LensProfileDefaults` / `ImportedSettings` | 0 | 0–3 | 是 | X | 配置/日志 | 否 |

**⚠️ 陷阱验证**：`CameraRaw\Settings` 下 1062 个文件**全部是用户导入的第三方调色预设**，实测文件名包含：
- `001-滨田英明调色 [霜绝预设].xmp` ~ `115-日本木川调色 [霜绝预设].xmp`（115 个霜绝预设）
- `海天之恋婚纱摄影出品*.xmp`（约 40 个婚纱摄影预设）
- `人物肖像-VSCO*.xmp`、`哑光磨砂 (1)~(76).xmp`、`婚礼 (1)~(56).xmp`
- `风景-胶片预设 (1)~(128).xmp`、`食物预设 (1)~(128).xmp`、`黑白预设 (1)~(55).xmp`

这些是**用户花钱/花时间收集的创作资产**，删除后无法从 Adobe 服务器恢复。**必须列入 X 级禁删清单。**

### 1.7 下钻：Photoshop 版本目录（陷阱：预设 vs 日志）

**`Adobe Photoshop 2025\`（31.8 MB / 64 文件）**

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `…2025\Adobe Photoshop 2025 Settings\Styles.psp` | 10.35 MB | 1 | 是 | **X** | 用户样式库 | 否 |
| `…\Patterns.psp` | 8.20 MB | 1 | 是 | **X** | 用户图案库 | 否 |
| `…\MachinePrefs.psp` | 2.77 MB | 1 | 是 | X | 机器首选项 | 否 |
| `…\CustomShapes.psp` | 2.20 MB | 1 | 是 | **X** | 自定义形状 | 否 |
| `…\Brushes.psp` | 1.18 MB | 1 | 是 | **X** | 用户画笔 | 否 |
| `…\Gradients.psp` / `Swatches.psp` / `Actions Palette.psp` / `Workspace Prefs.psp` / `Default Type Styles.psp` | 0.01–0.13 MB | 各 1 | 是 | **X** | 渐变/色板/**动作**/工作区/字符样式 | 否 |
| `…\WorkSpaces (Modified)` | 0.07 MB | — | 是 | **X** | 用户修改的工作区 | 否 |
| `…\Adjustments_Presets` | 0.02 MB | — | 是 | **X** | 调整预设 | 否 |
| `…\Adobe Photoshop 2025 Prefs.psp` / `UIPrefs.psp` / `DialogPreferences.psp` / `镜头校正首选项.psp` / `液化首选项.psp` / `Save for Web Prefs.psp` | 0–0.24 MB | 各 1 | 是 | **X** | 首选项（含**键盘快捷键**相关） | 否 |
| `…\MRUBrushes.psp` / `MRUSwatches.psp` / `MRU New Doc Sizes.json` / `New Doc Sizes.json` | 0–0.01 MB | 各 1 | 是 | X | 最近使用记录 | 否 |
| `…\PluginCache.psp` | 0.80 MB | 1 | 是 | **S** | 插件扫描缓存 | **是** |
| `…\FMCache.psp` | 0 | 1 | 是 | S | 字体菜单缓存 | 是 |
| `…\PSErrorLog.txt` | 0.02 MB | — | 是 | S | 错误日志 | 是 |
| `…\sniffer-out.txt` / `sniffer-out1~4.txt` | 各 0.01 MB | 5 | 是 | **S** | GPU 嗅探调试日志 | 是 |
| `…\QuitEndFlag.psp` / `LaunchEndFlag.psp` | 0 | 各 1 | 是 | X | 启动/退出状态标志 | 否 |
| `Adobe Photoshop 2025\Logs` | 3.7 MB | 11 | 是 | **S** | 运行日志（10 个 .log，3.53MB） | 是 |
| `Adobe Photoshop 2025\CT Font Cache` | 1.0 MB | 6 | 是 | **S** | CoreText 字体缓存 | 是 |
| `Adobe Photoshop 2025\FontFeatureCache` | 0.9 MB | 13 | 是 | **S** | 字体特性缓存 | 是 |
| `Adobe Photoshop 2025\Presets` / `Generator` | 0 | 0 | 是 | X | 用户预设/生成器 | 否 |

**`Adobe Photoshop 2021\`（181.4 MB / 113 文件）**

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `…2021\Adobe Photoshop 2021 Settings\Sky_Presets` | **138.58 MB** | — | 是 | **X** | **天空替换预设资产**（2300+ 张天空图） | **绝不重建** |
| `…\Patterns.psp` | 16.39 MB | 1 | 是 | X | 图案库 | 否 |
| `…\Styles.psp` | 10.31 MB | 1 | 是 | X | 样式库 | 否 |
| `…\CustomShapes.psp` | 6.61 MB | 1 | 是 | X | 自定义形状 | 否 |
| `…\MachinePrefs.psp` / `Brushes.psp` / `Gradients.psp` / `Actions Palette.psp` / `WorkSpaces (Modified)` / 各首选项 .psp | 0.01–1.72 MB | — | 是 | X | 首选项/**动作**/工作区 | 否 |
| `…\web-cache-temp` | 0.66 MB | — | 是 | **S** | Web 缓存临时文件 | 是 |
| `Adobe Photoshop 2021\Logs` | 2.4 MB | 7 | 是 | **S** | 运行日志 | 是 |
| `Adobe Photoshop 2021\FontFeatureCache` | 1.1 MB | 13 | 是 | **S** | 字体特性缓存 | 是 |
| `Adobe Photoshop 2021\CT Font Cache` | 1.0 MB | 6 | 是 | **S** | CoreText 字体缓存 | 是 |
| `Adobe Photoshop 2021\Presets` / `AutoRecover` / `Generator` | 0 | 0 | 是 | X | 用户预设/自动恢复 | 否 |

**`Adobe Photoshop 2023`（0 MB / 4 文件）**：`CT Font Cache`(1 文件)、`Settings`(3 文件) — 无体积，可保留。
**`Adobe Photoshop 2024`（0 MB / 0 文件）**：空目录 — 无清理价值。
**`Adobe Photoshop (Beta)`（2.9 MB / 44 文件）**：`Settings` 1.1MB + `FontFeatureCache` 0.9MB(S) + `CT Font Cache` 0.9MB(S) + `Logs` 0.9MB(S)。字体缓存合计 **1.8 MB 可删**。

### 1.8 下钻：`Adobe\CoreSync`（257.9 MB）—— X 级

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `CoreSync\plugins\livetype` | 257.9 MB | 24 | 是 | **X** | CoreSync LiveType 插件本体（字体同步组件） | 不重建 |

### 1.9 其他 Adobe 关键路径

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `Adobe\Creative Cloud Libraries\LIBS\settings.json` | 191.6 KB | 1 | 是 | **X** | CC 库同步配置 | 部分 |
| `Adobe\Creative Cloud Libraries\LIBS\identity\*.key/.crt/.dcrt` | 3.9 KB | 3 | 是 | **X** | **登录态证书/密钥** | **否** |
| `Adobe\Creative Cloud Libraries\LIBS\<id>_AdobeID\*` | ~40 KB | — | 是 | X | 用户库数据 | 否 |
| `Adobe\UPI\Configuration\DB\UPI.db` | 156 KB | 1 | 是 | **X** | 更新器产品安装状态库 | 否 |
| `Adobe\UPI\Log\EMCL.log` | 141 KB | 1 | 是 | S | 更新器日志 | 是 |
| `Adobe\SLData\SLCache\*.slc` | 0.8 KB | 2 | 是 | **X** | **许可证缓存** | **否** |
| `Adobe\SLData\SLStore\5DE5DF676F9B` | 0 | 1 | 是 | **X** | **许可证存储** | **否** |
| `Adobe\Adobe PCD\cache\F116F0D63404` | 0 | 1 | 是 | **X** | **产品许可数据(Adobe PCD)** | **否** |
| `Adobe\OOBE\dlcanalytics.db` | 16 KB | 1 | 是 | X | 首启分析 | 否 |
| `Adobe\ACPLocal\<id>*_GUDE\sqliteResumeTransfer.db` | 各 44 KB | 8 | 是 | C | 断点续传 DB（历史版本，2023–2024） | 是 |
| `Adobe\Adobe Analysis Server\1.2\logs` + `Debug Database.txt` + `Trace Database.txt` | ~1.0 MB | 5 | 是 | **S** | 分析服务日志 | 是 |
| `Adobe\PseudoFontsCache\AdobeFnt_PseudoFonts.lst` | 5.4 KB | 1 | 是 | S | 伪字体列表缓存 | 是 |
| `Adobe\User Owned Fonts` (hidden) | 0 | 0 | 是 | **X** | **用户自有字体目录**（空，但为容器） | 否 |
| `Adobe\Fonts` | 0 | 0 | 是 | **X** | 字体目录 | 否 |
| `Adobe\XMP` / `Color` / `LensCorrection` / `Lumetri` / `GUDE` | 0 | 0–2 | 是 | **X** | 色彩/XMP/镜头配置 | 否 |
| `Adobe\dvaAnalyticsID.dat` / `dvaAnalyticsPS.dat` / `MZUtilMID.dat` | 各 0 | 3 | 是 | **X** | **设备标识/遥测 ID** | 否 |
| `Adobe\Logs` / `CRLogs` / `LogTransport2CC` | 0 | 0–1 | 是 | S | 日志目录 | 是 |
| `Adobe\*.TEMP_<guid>`（4 个） | 0 | 4 | 是 | **S** | settings.json 写入残留临时文件 | 是 |
| `Adobe\Adobe Illustrator 25 Settings\zh_CN\x64\*.log` | 0.16 MB | 3 | 是 | S | Illustrator 日志 | 是 |

---

## 二、NVIDIA 明细表

### 2.1 `C:\ProgramData\NVIDIA`（1.15 GB）—— 核心结论：**不是缓存，是驱动组件**

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `NVIDIA\NGX` | **1153.6 MB** | 172 | 是 | **X / C 混合** | DLSS/NGX AI 模型仓库 | 见下 |
| `NVIDIA\NGX\models\dlss` | 650.2 MB | 34 | 是 | **C** | DLSS 超分模型，含 15 个历史版本 | 部分 |
| `NVIDIA\NGX\models\dlssd` | 393.0 MB | 6 | 是 | **C** | DLSS **光线重建**模型，6 个版本 | 部分 |
| `NVIDIA\NGX\models\dlssg` | 43.0 MB | 6 | 是 | **C** | DLSS **帧生成**模型 | 部分 |
| `NVIDIA\NGX\models\dlisp` | 18.9 MB | 8 | 是 | C | DLISP 模型 | 部分 |
| `NVIDIA\NGX\models\dlss_override` | 10.2 MB | 24 | 是 | C | DLSS 覆盖版本 | 部分 |
| `NVIDIA\NGX\models\sl_*`（22 个：sl_nis_0/sl_common_0/sl_nvperf_0/sl_dlss_0/sl_reflex_0/sl_pcl_0/sl_deepdvc_0/sl_sdk_0 及各自 override） | 各 0–7.9 MB | 1–8 | 是 | C | Streamline SDK 运行库 | 部分 |
| `NVIDIA\NGX\models\nvngx_config.txt` | 0 | 1 | 是 | **X** | NGX **应用→模型版本映射配置** | 否 |
| `NVIDIA\NGX\models\config` | 0 | 3 | 是 | X | NGX 配置 | 否 |
| `NVIDIA\*.log`（NVDisplay.ContainerLocalSystem / Watchdog / DisplaySessionContainer1 / NvcDispCorePlugin + backup1） | 0.1 MB | 9 | 是 | **S** | 显示驱动容器日志 | 是 |

**关键判定**：`NGX\models` 是 **DLSS 运行必需的模型仓库**，不是可丢弃缓存。但其中包含**大量历史版本**：

| 模型 | 版本 | 体积 | 时间 |
|---|---|---|---|
| `dlss` | 20318081 / 20318464 / 20317696 / 20317440 / 20317442 / 20316928 | 70.8+70.8+70.6+70.4+70.4+46.7 MB | 2025-11 ~ 2026-09 |
| `dlss` | 131356 / 66157 / 65644 / 131529 / 131599 / 66158 / 131357 / 131347 / 66410 | 67.4+44.8+43+42.7+13.8+11.2+11.2+11.2+5.3 MB | 2023-02 ~ 2024-06 |
| `dlssd` | 20318081 / 20318464 / 20316928 / 20317442 / 20317440 / 20317696 | 76+76+69.6+57.1+57.1+57.1 MB | 2025-11 ~ 2026-09 |

`nvngx_config.txt` 显示当前活动版本为 `app_E658700 = 310.9.0`（dlss/dlssd/dlssg override）。**2023 年的旧版本（131356/66157/65644 等，合计约 250 MB）属于历史残留**，但删除需谨慎——旧游戏可能锁定旧版 DLSS 版本。建议列为 **C 级**，且**必须在 NVIDIA app 关闭时操作**。

### 2.2 `C:\ProgramData\NVIDIA Corporation`（71.0 MB 可读 + 2 处 ACCESS_DENIED）

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `NVIDIA Corporation\NVIDIA app\Logs` | 13.7 MB | 6 | 是 | **S** | NVIDIA app 日志 | 是 |
| `NVIDIA Corporation\NVIDIA app\Installer` | 5.8 MB | 3 | 是 | **C** | 安装器残留（含 `Installer\Logs`） | 是 |
| `NVIDIA Corporation\NVIDIA app\UpdateFramework` | 1.4 MB | 13 | 是 | C | OTA 更新框架（ota-artifacts/plugins/profile-catalog/registry/status） | 是 |
| `NVIDIA Corporation\NVIDIA app\NvBackend` | 0 | 1 | 是 | **X** | 后端配置 | 否 |
| `NVIDIA Corporation\NVIDIA app\NvConfig` / `NvContainer` / `MessageBus` / `UXD` / `SessionLogs` | 0 | — | 是 | **X** | 驱动配置/容器总线 | 否 |
| `NVIDIA Corporation\NvDriverDiagnostics\storage` | **ACCESS_DENIED** | — | 是 | **X** | 驱动诊断存储（权限拒绝，无法测量） | — |
| `NVIDIA Corporation\nvtopps\nct\nvlog.nvlgstg` | **19.09 MB** | 1 | 是 | **S** | 遥测日志存储 | 是 |
| `NVIDIA Corporation\nvtopps\nvtopps.log` | 4.53 MB | 1 | 是 | **S** | nvtopps 日志 | 是 |
| `NVIDIA Corporation\nvtopps\nvtopps.db3` | 0.21 MB | 1 | 是 | **C** | 遥测数据库 | 是 |
| `NVIDIA Corporation\NvProfileUpdaterPlugin` | 12.2 MB | 23 | 是 | X | 3D 配置文件更新插件（`drs`/`optimus` 子目录） | 否 |
| `NVIDIA Corporation\Drs\nvdrsdb0.bin` + `nvdrsdb1.bin` | 4.94 MB | 2 | 是 | **X** | **驱动 3D 设置数据库（各游戏优化配置）** | **否** |
| `NVIDIA Corporation\Drs\nvAppTimestamps` / `nvdrssel.bin` / `update.bin` / `nvdrswr.lk` | 0.15 MB | 4 | 是 | X | Drs 辅助文件 | 否 |
| `NVIDIA Corporation\ShadowPlay\ShadowPlay` | 4.7 MB | 1 | 是 | X | ShadowPlay 配置 | 否 |
| `NVIDIA Corporation\NvTelemetry` | **ACCESS_DENIED** | — | 是 | X | 遥测目录（权限拒绝，无法测量） | — |
| `NVIDIA Corporation\Downloader`（含 8389b6f6…/cf26f24b…/config/latest/PostProcessing） | 0 | 0 | 是 | **C** | **驱动下载目录（当前为空）** | — |
| `NVIDIA Corporation\NVIDIA GeForce Experience\Logs` | 0 | 0 | 是 | S | GFE 日志（空） | 是 |
| `NVIDIA Corporation\umdlogs` | 0 | 0 | 是 | **S** | UMD 日志（空） | 是 |
| `NVIDIA Corporation\CrashDumps` | 0 | 0 | 是 | **S** | 崩溃转储（空） | 是 |
| `NVIDIA Corporation\DisplayDriverRAS\NvTelemetry\feedbacks` | 0.1 MB | 3 | 是 | S | 驱动 RAS 反馈 | 是 |
| `NVIDIA Corporation\GameSessionTelemetry` | 0 | 2 | 是 | S | 游戏会话遥测 | 是 |
| `NVIDIA Corporation\FrameViewSDK` / `GfnRuntimeSdk` / `NvVAD` | 0 | 0–13 | 是 | X | SDK 运行时 | 否 |

### 2.3 `%LOCALAPPDATA%\NVIDIA Corporation`（293.9 MB）

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `NVIDIA Corporation\NVIDIA app` | 170.8 MB | 1871 | 是 | C 混合 | NVIDIA app 用户数据 | 见下 |
| `NVIDIA Corporation\NVIDIA app\CefCache` | **125.7 MB** | 1647 | 是 | **S** | **内嵌浏览器(Cef)缓存** | **是** |
| `NVIDIA Corporation\NVIDIA app\CefCache\Default` | 40.7 MB | 1057 | 是 | S | Cef 默认 Profile | 是 |
| `NVIDIA Corporation\NVIDIA app\CefCache\component_crx_cache` | 26.8 MB | 19 | 是 | S | 组件 CRX 缓存 | 是 |
| `NVIDIA Corporation\NVIDIA app\CefCache\WidevineCdm` | 18.5 MB | 6 | 是 | S | DRM 模块缓存 | 是 |
| `NVIDIA Corporation\NVIDIA app\CefCache\OnDeviceHeadSuggestModel` | 7.6 MB | 4 | 是 | S | 输入建议模型 | 是 |
| `NVIDIA Corporation\NVIDIA app\CefCache\extensions_crx_cache` | 5.4 MB | 2 | 是 | S | 扩展 CRX 缓存 | 是 |
| `NVIDIA Corporation\NVIDIA app\CefCache\GrShaderCache` | 5.3 MB | 44 | 是 | **S** | GPU 着色器缓存 | 是 |
| `NVIDIA Corporation\NVIDIA app\CefCache\BrowserMetrics` | 4.0 MB | 1 | 是 | S | 浏览器指标 | 是 |
| `NVIDIA Corporation\NVIDIA app\CefCache\Service Worker` | 3.0 MB | 89 | 是 | S | Service Worker 缓存 | 是 |
| `NVIDIA Corporation\NVIDIA app\CefCache\CertificateRevocation` | 2.5 MB | 10 | 是 | S | 证书吊销列表 | 是 |
| `NVIDIA Corporation\NVIDIA app\CefCache\hyphen-data` / `ZxcvbnData` / `OptimizationHints` / `Subresource Filter` / `PKIMetadata` / `ShaderCache` / `GPUCache` / `GraphiteDawnCache` / 其余 | 各 0–1.7 MB | — | 是 | S | 浏览器组件缓存 | 是 |
| `NVIDIA Corporation\NVIDIA app\NvBackend\backend.log.bak` | **20.0 MB** | 1 | 是 | **S** | **后端日志备份** | 是 |
| `NVIDIA Corporation\NVIDIA app\NvBackend\backend.log` | 3.1 MB | 1 | 是 | **S** | 后端日志 | 是 |
| `NVIDIA Corporation\NVIDIA app\NvBackend\ApplicationOntology` | 9.3 MB | 40 | 是 | C | 应用本体库（游戏识别） | 是 |
| `NVIDIA Corporation\NVIDIA app\NvBackend\DAO` | 8.4 MB | 6 | 是 | **X** | **数据访问对象（用户设置）** | 否 |
| `NVIDIA Corporation\NVIDIA app\NvBackend\Recommendations` | 1.2 MB | 128 | 是 | C | 游戏推荐配置 | 是 |
| `NVIDIA Corporation\NVIDIA app\NvBackend\*.json` / `*.dat` / `*.xml`（QuietModeSupportState/nis2settings/ngxdlssoverridestate/batteryboost2/config.xml/DriverRecommendations.dat 等） | 各 0 | — | 是 | **X** | 用户设置/状态 | 否 |
| `NVIDIA Corporation\NVIDIA app\NvAccount` | 0 | 1 | 是 | **X** | **账号登录态** | **否** |
| `NVIDIA Corporation\NVIDIA app\UXD` / `assets` / `Diagnostics` / `_deleteOldUpdateFrameworkLocation` | 0–0.1 MB | 0–1 | 是 | X | app 资源/诊断 | 否 |
| `NVIDIA Corporation\NVIDIA Overlay` | 123.1 MB | 1849 | 是 | C 混合 | Overlay 用户数据 | 见下 |
| `NVIDIA Corporation\NVIDIA Overlay\CefCache` | **121.0 MB** | 1842 | 是 | **S** | **Overlay 内嵌浏览器缓存** | **是** |
| `NVIDIA Corporation\NVIDIA Overlay\CefCache\Default` | 34.6 MB | 1325 | 是 | S | Cef 默认 Profile | 是 |
| `NVIDIA Corporation\NVIDIA Overlay\CefCache\component_crx_cache` | 25.8 MB | 19 | 是 | S | 组件 CRX 缓存 | 是 |
| `NVIDIA Corporation\NVIDIA Overlay\CefCache\WidevineCdm` | 18.5 MB | 6 | 是 | S | DRM 缓存 | 是 |
| `NVIDIA Corporation\NVIDIA Overlay\CefCache\OnDeviceHeadSuggestModel` | 7.6 MB | 4 | 是 | S | 输入建议模型 | 是 |
| `NVIDIA Corporation\NVIDIA Overlay\CefCache\extensions_crx_cache` | 5.2 MB | 2 | 是 | S | 扩展缓存 | 是 |
| `NVIDIA Corporation\NVIDIA Overlay\CefCache\Cache` | 4.6 MB | 5 | 是 | S | HTTP 缓存 | 是 |
| `NVIDIA Corporation\NVIDIA Overlay\CefCache\GrShaderCache` | 4.6 MB | 5 | 是 | S | 着色器缓存 | 是 |
| `NVIDIA Corporation\NVIDIA Overlay\CefCache\BrowserMetrics` | 4.0 MB | 1 | 是 | S | 浏览器指标 | 是 |
| `NVIDIA Corporation\NVIDIA Overlay\CefCache\CertificateRevocation` | 3.4 MB | 25 | 是 | S | 证书吊销列表 | 是 |
| `NVIDIA Corporation\NVIDIA Overlay\CefCache\OptimizationHints` | 1.8 MB | 16 | 是 | S | 优化提示 | 是 |
| `NVIDIA Corporation\NVIDIA Overlay\CefCache\IndexedDB` / `Local Storage` / `Session Storage` / `databases` / `Safe Browsing` 等其余 | 0 | — | 是 | S | 浏览器存储 | 是 |
| `NVIDIA Corporation\NVIDIA Overlay\AppConfigs\v2` | 0 | 1 | 是 | **X** | **Overlay 应用配置** | 否 |
| `NVIDIA Corporation\FrameViewSDK` / `GfnRuntimeSdk` | 0 | 0–2 | 是 | X | SDK 运行时 | 否 |

### 2.4 `ProgramData\NVIDIA` vs `ProgramData\NVIDIA Corporation` —— 重复性查明

**结论：两者不重复，职责完全不同。**

| 维度 | `C:\ProgramData\NVIDIA` | `C:\ProgramData\NVIDIA Corporation` |
|---|---|---|
| 实测体积 | 1153.7 MB | 71.0 MB（可读部分） |
| 内容 | `NGX\models` — DLSS/NGX AI 模型二进制 | 配置、日志、遥测、Drs 数据库 |
| 主要文件 | `*.bin` 模型权重（70MB/个） | `*.log`、`.db3`、`.bin` 配置 |
| 清理价值 | 仅旧版本可删（C 级，~250MB） | 日志约 42MB（S 级） |
| 重叠 | **无重叠**，无一字节重复 | — |

两者是 NVIDIA 驱动的**不同组件约定**：`NVIDIA` 存放运行时模型资产，`NVIDIA Corporation` 存放应用配置与日志。旧版驱动可能遗留 `ProgramData\NVIDIA Corporation\Downloader` 中的安装包，本机实测该目录**为空**（0 字节 / 0 文件）。

### 2.5 着色器缓存（DXCache / GLCache）说明

本机 `%LOCALAPPDATA%\NVIDIA\`（DXCache/GLCache 传统位置）**不存在**。实测存在的着色器缓存仅有两类，且都属于 **NVIDIA app / Overlay 内嵌 Cef 浏览器**的缓存，**不是游戏 DXCache**：

| 路径 | 体积 | 文件数 | 等级 | 后果 |
|---|---|---|---|---|
| `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA app\CefCache\GrShaderCache` | 5.3 MB | 44 | S | NVIDIA app 界面首次打开时重新编译界面着色器（毫秒级） |
| `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA app\CefCache\ShaderCache` | 0 | — | S | 同上 |
| `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA app\CefCache\GPUCache` / `GraphiteDawnCache` | 0 | — | S | 同上 |
| `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA Overlay\CefCache\GrShaderCache` | 4.6 MB | 5 | S | Overlay 界面着色器重新编译 |
| `%APPDATA%\Adobe\UXP\PluginsStorage\PHSP\26\Shared\EBWebView\GrShaderCache` | 4.6 MB | 5 | S | Photoshop 内嵌浏览器着色器重新编译 |

**游戏着色器缓存（`%LOCALAPPDATA%\NVIDIA\DXCache`）在本机不存在** — 不要为不存在的路径编写规则。

---

## 三、建议加入规则库清单（仅 S / C）

### S 级（risk=low，可直接清理）

| # | 路径（通配） | 体积 | 等级 | risk | 重建/后果 |
|---|---|---|---|---|---|
| 1 | `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA app\CefCache\*` | 125.7 MB | S | low | NVIDIA app 界面缓存重新生成；**保留父目录**，勿删 `NvAccount`/`NvBackend\DAO` |
| 2 | `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA Overlay\CefCache\*` | 121.0 MB | S | low | Overlay 界面缓存重新生成；**保留** `AppConfigs` |
| 3 | `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA app\NvBackend\backend.log*` | 23.1 MB | S | low | 日志重建，无功能影响 |
| 4 | `C:\ProgramData\NVIDIA Corporation\nvtopps\nvlog.nvlgstg` | 19.09 MB | S | low | 遥测日志重建，无功能影响 |
| 5 | `C:\ProgramData\NVIDIA Corporation\NVIDIA app\Logs\*` | 13.7 MB | S | low | 日志重建 |
| 6 | `C:\ProgramData\NVIDIA Corporation\nvtopps\nvtopps.log` | 4.53 MB | S | low | 日志重建 |
| 7 | `%APPDATA%\Adobe\UXP\PluginsStorage\PHSP\26\Shared\EBWebView\*` | 70.46 MB | S | low | Photoshop 内嵌浏览器缓存重建；**必须保留同级 `Internal\`** |
| 8 | `%APPDATA%\Adobe\Adobe Photoshop 20*\Logs\*` | 6.0 MB | S | low | Photoshop 日志重建 |
| 9 | `%APPDATA%\Adobe\Adobe Photoshop 20*\CT Font Cache\*` | 2.9 MB | S | low | 字体缓存重建，首次启动字体列表略慢 |
| 10 | `%APPDATA%\Adobe\Adobe Photoshop 20*\FontFeatureCache\*` | 2.9 MB | S | low | 字体特性缓存重建 |
| 11 | `%APPDATA%\Adobe\Common\Analyzer Cache Files\*` | 1.1 MB | S | low | 分析器缓存重建 |
| 12 | `%APPDATA%\Adobe\Common\Peak Files\*` | 0 MB | S | low | 音频峰值文件重建（Premiere/Audition 首次播放略慢） |
| 13 | `%APPDATA%\Adobe\Adobe Analysis Server\*\logs\*` | 1.0 MB | S | low | 分析服务日志重建 |
| 14 | `%APPDATA%\Adobe\Adobe Photoshop 2021\web-cache-temp\*` | 0.66 MB | S | low | Web 缓存重建 |
| 15 | `%APPDATA%\Adobe\CameraRaw\ModelZoo\CloudDownload\*\dust_detection\*` | 16.3 MB | S | low | 除尘 AI 模型，相机联机时重新下载 |
| 16 | `%APPDATA%\Adobe\CCX Welcome\*.TEMP_*` | 0 MB | S | low | 写入残留临时文件 |
| 17 | `%APPDATA%\Adobe\Adobe Photoshop 20*\sniffer-out*.txt` | 0.05 MB | S | low | GPU 嗅探调试日志 |
| 18 | `C:\ProgramData\NVIDIA\*.log` + `*_backup1` | 0.1 MB | S | low | 显示驱动容器日志 |
| 19 | `%APPDATA%\Adobe\Adobe Photoshop 20*\PluginCache.psp` | 0.8 MB | S | low | 插件扫描缓存，下次启动重建 |

**S 级合计约 412.5 MB**

### C 级（risk=medium，需用户确认）

| # | 路径（通配） | 体积 | 等级 | risk | 重建/后果 |
|---|---|---|---|---|---|
| 20 | `%APPDATA%\Adobe\typequest\.2\.*\.a\*` | 283.3 MB | C | medium | 字体检索索引分片重建（首次启动字体菜单变慢）；**不丢字体** |
| 21 | `%APPDATA%\Adobe\CCX Welcome\learn\*` | 184.8 MB | C | medium | 欢迎页教学卡片变空，需联网重新拉取 |
| 22 | `%APPDATA%\Adobe\CCX Welcome\stock\*` | 102.2 MB | C | medium | Stock 缩略图变空，需联网重新拉取 |
| 23 | `%APPDATA%\Adobe\CCX Welcome\discover_panel\*` | 96.0 MB | C | medium | Discover 面板资源变空，需联网重新拉取 |
| 24 | `C:\ProgramData\NVIDIA\NGX\models\dlss\versions\{131356,66157,65644,131529,131599,66158,131357,131347,66410,66150,65637,66405,66154}` | ~250 MB | C | medium | **2023–2024 历史 DLSS 版本**；当前活动版本为 310.9.0，旧游戏若锁定旧版会触发重新下载。**必须在 NVIDIA app 关闭时操作** |
| 25 | `C:\ProgramData\NVIDIA\NGX\models\dlssd\versions\{20316928,20317440,20317442,20317696}` | ~240 MB | C | medium | DLSS 光线重建旧版本；后果同上 |
| 26 | `C:\ProgramData\NVIDIA\NGX\models\dlssg\versions\{20316928,20317440,20317442,20317696}` | ~29 MB | C | medium | DLSS 帧生成旧版本 |
| 27 | `C:\ProgramData\NVIDIA Corporation\Downloader\*` | 0 MB | C | medium | 驱动下载残留（当前为空，规则预留） |
| 28 | `C:\ProgramData\NVIDIA Corporation\NVIDIA app\Installer\Logs\*` | 5.8 MB | C | medium | 安装器日志 |
| 29 | `C:\ProgramData\NVIDIA Corporation\NVIDIA app\UpdateFramework\ota-artifacts\*` | 1.4 MB | C | medium | OTA 更新残留 |
| 30 | `%APPDATA%\Adobe\ACPLocal\*_GUDE\` (2023–2024 历史版本) | 0.35 MB | C | medium | 断点续传 DB（仅历史版本条目） |
| 31 | `C:\ProgramData\NVIDIA Corporation\nvtopps\nvtopps.db3` | 0.21 MB | C | medium | 遥测数据库重建 |
| 32 | `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA app\NvBackend\ApplicationOntology\*` | 9.3 MB | C | medium | 游戏识别本体库重新下载 |
| 33 | `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA app\NvBackend\Recommendations\*` | 1.2 MB | C | medium | 游戏推荐配置重新拉取 |

**C 级合计约 1204 MB（其中 NGX 旧版本约 519 MB 风险最高）**

---

## 四、X 级禁删清单

### 4.1 Adobe —— 用户创作资产（**绝不重建**）

| 路径 | 体积 | 原因 |
|---|---|---|
| `%APPDATA%\Adobe\CameraRaw\Settings\*` | 6.2 MB / 1062 文件 | **用户导入的第三方调色预设(.xmp)**：霜绝预设 115 个、海天之恋婚纱摄影 40+ 个、VSCO 人像、哑光磨砂 76 个、婚礼 56 个、风景/食物胶片预设各 128 个、黑白预设 55 个。**Adobe 服务器无法恢复** |
| `%APPDATA%\Adobe\CameraRaw\LensProfiles\1.0\pscache.dat` | 2.69 MB | 镜头校正数据缓存（删除后镜头自动校正失效并需重下） |
| `%APPDATA%\Adobe\CameraRaw\CameraProfiles\*` | 0 MB | **相机配置文件(.dcp)目录** — 当前为空，规则须为禁删以免将来误清 |
| `%APPDATA%\Adobe\Common\Motion Graphics Templates\*` | 2259.3 MB / 1075 .mogrt | **动态图形模板资产**：Light Leaks 转场 1.6GB、News Package 342MB 等，需从 Adobe Stock 重新下载 |
| `%APPDATA%\Adobe\Adobe Photoshop 2021\...\Sky_Presets\*` | 138.58 MB | **天空替换预设资产**（2300+ 天空图）|
| `%APPDATA%\Adobe\Adobe Photoshop 2025\...\Styles.psp` / `Patterns.psp` / `CustomShapes.psp` / `Brushes.psp` / `Gradients.psp` / `Swatches.psp` | 23.1 MB | **用户样式/图案/形状/画笔/渐变/色板库** |
| `%APPDATA%\Adobe\Adobe Photoshop 2021\...\Patterns.psp` / `Styles.psp` / `CustomShapes.psp` / `Brushes.psp` / `Gradients.psp` | 34.5 MB | **同上（2021 版本）** |
| `%APPDATA%\Adobe\Adobe Photoshop *\...\Actions Palette.psp` | 0.06 MB | **用户动作(Actions)面板** |
| `%APPDATA%\Adobe\Adobe Photoshop *\...\WorkSpaces*` | 0.18 MB | **用户工作区布局** |
| `%APPDATA%\Adobe\Adobe Photoshop *\...\Adobe Photoshop * Prefs.psp` + `UIPrefs.psp` + `Workspace Prefs.psp` + `DialogPreferences.psp` | 0.4 MB | **首选项（含键盘快捷键相关设置）** |
| `%APPDATA%\Adobe\Adobe Photoshop *\Presets\` | 0 MB | 用户预设目录 |
| `%APPDATA%\Adobe\Adobe Photoshop *\AutoRecover\` | 0 MB | **自动恢复数据**（崩溃后可救回未保存作品）|

### 4.2 Adobe —— 许可证 / 登录态 / 身份（**绝不重建**）

| 路径 | 体积 | 原因 |
|---|---|---|
| `%APPDATA%\Adobe\SLData\SLCache\*.slc` | 0.8 KB | **许可证缓存** — 删除需重新激活 |
| `%APPDATA%\Adobe\SLData\SLStore\*` | 0 KB | **许可证存储** |
| `%APPDATA%\Adobe\Adobe PCD\cache\*` | 0 KB | **产品许可数据(Adobe PCD)** |
| `%APPDATA%\Adobe\Creative Cloud Libraries\LIBS\identity\*.key` / `*.crt` / `*.dcrt` | 3.9 KB | **登录态证书与私钥** — 删除需重新登录 |
| `%APPDATA%\Adobe\Creative Cloud Libraries\LIBS\settings.json` | 191.6 KB | CC 库同步配置 |
| `%APPDATA%\Adobe\Creative Cloud Libraries\LIBS\*_AdobeID\*` | ~40 KB | 用户云库数据 |
| `%APPDATA%\Adobe\UPI\Configuration\DB\UPI.db` | 156 KB | 更新器产品安装/激活状态库 |
| `%APPDATA%\Adobe\OOBE\dlcanalytics.db` | 16 KB | 首启状态 |
| `%APPDATA%\Adobe\dvaAnalyticsID.dat` / `dvaAnalyticsPS.dat` / `MZUtilMID.dat` | 0 KB | **设备身份/遥测标识** |
| `%APPDATA%\Adobe\Adobe Analysis Server\*\*.txt` | 0.8 MB | 分析服务数据库（非日志部分） |

### 4.3 Adobe —— 字体数据（**非缓存**）

| 路径 | 体积 | 原因 |
|---|---|---|
| `%APPDATA%\Adobe\Fonts\*` | 0 MB | 字体目录（容器，禁删） |
| `%APPDATA%\Adobe\User Owned Fonts\*` (hidden) | 0 MB | **用户自有字体目录**（容器，禁删） |
| `%APPDATA%\Adobe\CoreSync\plugins\livetype\*` | 257.9 MB | CoreSync 字体同步插件**本体**，删除破坏 Adobe Fonts 同步 |

### 4.4 Adobe —— UXP 插件本体（**非缓存**）

| 路径 | 体积 | 原因 |
|---|---|---|
| `%APPDATA%\Adobe\UXP\PluginsStorage\PHSP\26\Internal\*` | 101.77 MB | 内置面板插件**本体**（nfp.gallery 88MB / unifiedpanel 12.5MB / ccx.start 1.15MB 等），删除导致 Photoshop 面板丢失 |
| `%APPDATA%\Adobe\UXP\PluginsStorage\PHSP\26\Settings\*` | 0 MB | 插件设置 |
| `%APPDATA%\Adobe\UXP\PluginsStorage\ILST\25\*` | 0 MB | Illustrator 插件存储 |

### 4.5 Adobe —— 其他配置

| 路径 | 体积 | 原因 |
|---|---|---|
| `%APPDATA%\Adobe\Adobe Illustrator 25 Settings\*` | 7.5 MB | Illustrator 首选项/工作区 |
| `%APPDATA%\Adobe\Adobe Photoshop (Beta)\...\Settings\*` | 1.1 MB | Beta 首选项资产 |
| `%APPDATA%\Adobe\AIRobin 25.4.1 Settings\*` | 1.6 MB | AIR 运行时首选项 |
| `%APPDATA%\Adobe\XMP\*` / `Color\*` / `LensCorrection\*` / `Lumetri\*` / `GUDE\*` | 0 MB | **XMP 元数据/色彩管理/镜头校正/Lumetri 调色**配置 |
| `%APPDATA%\Adobe\Common\LUTs\*` / `Essential Sound\*` / `Essential Graphics\*` / `ExportSettings\*` | 0 MB | LUT/音频/图形/导出预设资产 |
| `%APPDATA%\Adobe\Common\Team Projects Local Hub\*` | 0 MB | 团队项目同步数据 |
| `%APPDATA%\Adobe\CCX Welcome\settings.json` / `client_settings_home.json` / `data\*.json` | 30.4 MB | 首启状态机（含 FAILED_QUIT_ATTEMPTS、NEXT_LAUNCH_TIME 周期跟踪） |
| `%APPDATA%\Adobe\CCX Welcome\{ccd,xd,survey,avatar,evergreen,ccxpFlags,illustrator,illustratorFlags,indesignFlags,senseiModels,ghost,collectionTemplates,photoshop}\*` | 0.1 MB | 应用标志位/登录态关联 |

### 4.6 NVIDIA —— 驱动本体 / 配置 / 账号

| 路径 | 体积 | 原因 |
|---|---|---|
| `C:\ProgramData\NVIDIA\NGX\models\nvngx_config.txt` | 0 KB | **NGX 应用→DLSS 模型版本映射**，删除破坏 DLSS 版本选择 |
| `C:\ProgramData\NVIDIA\NGX\models\config\*` | 0 KB | NGX 配置 |
| `C:\ProgramData\NVIDIA\NGX\models\{dlss,dlssd,dlssg,dlisp,dlss_override,sl_*}\versions\<当前版本>\*` | ~640 MB | **当前活动 DLSS 模型**（310.9.0 / 2.14.0），删除导致所有 DLSS 游戏失效并需重下 |
| `C:\ProgramData\NVIDIA Corporation\Drs\nvdrsdb0.bin` + `nvdrsdb1.bin` | 4.94 MB | **驱动 3D 设置数据库**（各游戏优化配置、全局 3D 设置） |
| `C:\ProgramData\NVIDIA Corporation\Drs\nvAppTimestamps` / `nvdrssel.bin` / `update.bin` | 0.15 MB | Drs 辅助索引 |
| `C:\ProgramData\NVIDIA Corporation\NVIDIA app\NvConfig\*` / `NvContainer\*` / `MessageBus\*` | 0 KB | **驱动配置 / 容器总线**（NVIDIA Container 运行时） |
| `C:\ProgramData\NVIDIA Corporation\NVIDIA app\NvBackend\*` | 0 KB | 后端配置（含 ngxdlssoverridestate.json、nis2settings.json 等用户设置） |
| `C:\ProgramData\NVIDIA Corporation\ShadowPlay\ShadowPlay\*` | 4.7 MB | ShadowPlay 配置 |
| `C:\ProgramData\NVIDIA Corporation\NvProfileUpdaterPlugin\*` | 12.2 MB | 3D 配置文件更新插件（drs/optimus） |
| `C:\ProgramData\NVIDIA Corporation\FrameViewSDK\*` / `GfnRuntimeSdk\*` / `NvVAD\*` | 0 KB | SDK 运行时组件 |
| `C:\ProgramData\NVIDIA Corporation\NvDriverDiagnostics\storage` | **ACCESS_DENIED** | 驱动诊断存储（受保护，无法测量） |
| `C:\ProgramData\NVIDIA Corporation\NvTelemetry` | **ACCESS_DENIED** | 遥测目录（受保护，无法测量） |
| `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA app\NvAccount\*` | 0 KB | **NVIDIA 账号登录态** |
| `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA app\NvBackend\DAO\*` | 8.4 MB | **数据访问对象（用户设置持久化）** |
| `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA app\NvBackend\*.json` / `*.dat` / `*.xml` | 0 KB | 用户设置与状态 |
| `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA Overlay\AppConfigs\v2\*` | 0 KB | **Overlay 应用配置** |
| `%LOCALAPPDATA%\NVIDIA Corporation\NVIDIA app\UXD\*` / `assets\*` | 0.1 MB | app 界面资源 |

---

## 五、实测汇总

| 域 | 实测总量 | S 级可清理 | C 级可清理 | X 级受保护 |
|---|---|---|---|---|
| `%APPDATA%\Adobe` | 3585.0 MB | ~104 MB | ~667 MB | ~2814 MB |
| `C:\ProgramData\NVIDIA` | 1153.7 MB | 0.1 MB | ~519 MB | ~634 MB |
| `C:\ProgramData\NVIDIA Corporation` | 71.0 MB（+2 处 ACCESS_DENIED） | 37.3 MB | 7.4 MB | ~26 MB |
| `%LOCALAPPDATA%\NVIDIA Corporation` | 293.9 MB | 270.4 MB | 10.5 MB | ~13 MB |
| **合计** | **~5103.6 MB** | **~412 MB** | **~1204 MB** | **~3487 MB** |

### 关键结论

1. **Adobe 的 3.58 GB 中 2814 MB（78%）是资产，不是缓存** —— `Common\Motion Graphics Templates`（2259 MB .mogrt）、`CoreSync\livetype`（258 MB）、`Photoshop 2021\Sky_Presets`（139 MB）三项就占 2656 MB。
2. **`CameraRaw\Settings` 的 1062 个 .xmp 确认是用户调色预设**（霜绝/海天之恋/VSCO/哑光磨砂等），必须 X 级。
3. **`typequest` 不是字体数据** —— `.a` 分片头部为高熵随机字节（非 TTF/OTF 魔数），`.m` 是 JSONL 标签索引（`tag_id` → `font_ids`），属于可重建的字体检索索引（C 级）。
4. **`CCX Welcome` 删了会怎样** —— `learn`/`stock`/`discover_panel`（383 MB）删除后欢迎页/首页卡片变空，需联网重新拉取；`settings.json` 记录首启周期与失败退出计数，删除会触发重新走首启流程。
5. **`UXP` 中 70.46 MB 的 `Shared\EBWebView` 是唯一可安全清理的缓存**，其余 101.77 MB 是插件本体。
6. **NVIDIA `ProgramData\NVIDIA` 的 1.15 GB 几乎全是 DLSS/NGX 模型**（dlss 650MB + dlssd 393MB），不是缓存；仅 2023–2024 历史版本约 519 MB 可作为 C 级清理。
7. **`ProgramData\NVIDIA` 与 `ProgramData\NVIDIA Corporation` 无重复** —— 前者是运行时模型资产，后者是配置/日志/遥测。
8. **DXCache/GLCache 在本机不存在** —— 不要为 `%LOCALAPPDATA%\NVIDIA\DXCache` 编写规则；实际存在的着色器缓存只是 Cef 浏览器的 GrShaderCache（合计 14.5 MB）。
9. **`ProgramData\NVIDIA Corporation\Downloader` 实测为空**（0 字节）—— 无驱动安装包可清，规则可预留但当前无收益。
10. 两处 **ACCESS_DENIED**：`NVIDIA app\NvDriverDiagnostics\storage`、`NvTelemetry`（UnauthorizedAccessException），已如实标注，未估算数字。
