# C:\ProgramData\ 创意/专业软件域 — 规则补全报告

**扫描方式**：只读（`Get-ChildItem -Force -Recurse` + 文件头内容判读 + 扩展名体积普查）
**扫描时间**：本机实测
**域范围**：Adobe / Autodesk / Red Giant / RedGiant / Blackmagic Design / BorisFX / Exposure Software / LogiOptionsPlus
**总计**：8,359.1 MB / 39,701 files（8 个根目录求和）

---

## ⚠️ 结论先行（最重要的发现）

**这个域里几乎没有可删的缓存。** 逐目录实测后，8 个软件根目录中：

- 体量最大的目录**全部是程序本体、插件二进制、预设库、AI 模型、LUT、许可证** —— 属 X 级
- 唯一明确 S 级的只有 2 处：`Red Giant\Logs\*.txt`（14 个 2018 年前的安装日志，共 0.1 MB）和 `Autodesk\AdskLicensingService\Log\*`（2.6 MB 服务日志）
- **严格来说，整个域的可安全回收空间 < 3 MB**

特别打断的既有假设：
1. `C:\ProgramData\Adobe\CameraRaw` **不含任何缓存** —— 它是相机配置文件（.dcp）、镜头配置文件（.lcp）、AI 模型（ModelZoo .data）和预设（.xmp）。它占 Adobe 全部体量的 **99.1%**。
2. `C:\ProgramData\Red Giant` **不含任何缓存** —— 是插件本体、预设、渲染资源。唯一叫 "cache" 的 `Link\cacheData` 是 2018 年的 Python pickle 状态文件。
3. `C:\ProgramData\BorisFX` **不含任何缓存** —— 是 Continuum 插件本体 + 预设 + 纹理素材。
4. `C:\ProgramData\LogiOptionsPlus\cache` **存在但完全空**（0 文件 / 0 字节）。
5. `C:\ProgramData\LogiOptionsPlus\depots` 不是缓存 —— 是**完整安装包仓库**，删了会导致 Logi Options+ 无法自修复/更新。

---

## 1. 明细表

### 1.1 Adobe — 2,325.5 MB / 8,702 files

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `Adobe\CameraRaw` | 2,304.6 MB | 8,470 | 是 | **X** | 相机原始数据支持库总目录 | — |
| `Adobe\CameraRaw\CameraProfiles` | 824.2 MB | 4,199 | 是 | **X** | 相机色彩配置文件（.dcp）。`Adobe Standard\` 136.2MB/1366、`Camera\` 687.3MB/2832、`Index.dat` 0.7MB。缺失→所有相机 RAW 无法正确解码/显色 | 需重装 |
| `Adobe\CameraRaw\LensProfiles` | 439.6 MB | 3,281 | 是 | **X** | 镜头校正配置文件（.lcp, 3280 个）+ `Index.dat` 2.8MB。缺失→镜头畸变/暗角校正失效 | 需重装 |
| `Adobe\CameraRaw\ModelZoo` | 992.0 MB | 66 | 是 | **X** | **AI 模型权重库**，33 个子模型：`dereflect` 221.4MB、`denoise` 132.4MB、`depth_estimation` 78.6MB、`depth_estimation_refinement_guided` 77.9MB、`metacaf` 77.2MB、`stuff_mask_generator` 69.8MB、`select_sky` 50.5MB、`object_selection` 39.3MB 等。缺失→AI 去噪/去反光/选择主体/选择天空全部失效且需联网重下 | 需重装/重下 |
| `Adobe\CameraRaw\Settings` | 39.0 MB | 921 | 是 | **X** | `Adobe\Presets`（.xmp 预设 611 个 / 37.8MB）、`Adobe\Profiles`、`Premium` 1.2MB/302、`Apple`、`Google`、`SamsungLooks`。**是内置预设库，不是缓存** | 需重装 |
| `Adobe\CameraRaw\Libraries` | 9.7 MB | 1 | 是 | **X** | `adobe_c2pa.dll` 内容凭证运行库 | 需重装 |
| `Adobe\CameraRaw\SaveOptions` | 0.0 MB | 2 | 是 | **X** | `Save as DNG.xmp` / `Save as JPEG.xmp` 保存预设 | 需重装 |
| `Adobe\OOBE\ffc` | 13.9 MB | 1 | 是 | **X** | Creative Cloud 首次运行欢迎资产包（单文件 13.94MB）。删除→CC 首次启动向导素材缺失 | 会重下 |
| `Adobe\Installer` | 4.9 MB | 172 | 是 | C | `Icons\`（172 个安装器图标，含 AEFT/PPRO/PHSP 等多版本）+ `Summary.htm`。纯装饰，删除仅影响控制面板卸载列表图标 | 不重建 |
| `Adobe\UPI\Log\EMCL.log` | 0.0 MB | 1 | 是 | C | 23KB 日志，可删但无收益 | 会重建 |
| `Adobe\UPI` (其余) | 1.3 MB | 4 | 是 | **X** | `Configuration\DB\UPISys.db` 184KB 数据库 + `XManConfigV2.xml` 568KB 配置 + `EM Store\` 各产品清单 | 不重建 |
| `Adobe\UPI\EM Store` | 0.0 MB | 0 | 是 | **X** | AE/AU/AI/PS/PR/AME 授权模块存放点 | 不重建 |
| `Adobe\SLStore` | 0.0 MB | 2 | 是 | **X** | `5DE5DF676F9B`（20 字节序列号/授权标识）+ `Adobe01.bmp`。**许可证存储** | 不重建 |
| `Adobe\PINF\xpuinfo.json` | 0.0 MB | 1 | 是 | **X** | XPU 硬件加速探测状态 | 会重建 |
| `Adobe\Adobe PDF` | 0.7 MB | 23 | 是 | **X** | Distiller/Extras/Settings 配置文件 | 需重装 |
| `Adobe\Common\PTX\RTE` | 0.0 MB | 28 | 是 | **X** | AE GPU 着色器缓存（.aeroresource），删除→AE 首启重编译着色器 | 会重建（但建议保留） |
| `Adobe\Lightroom` | 0.0 MB | 0 | 是 | X | 空目录 | — |

> **无 `CCX Welcome` 目录存在于 ProgramData 下**（该资产在 `Adobe\OOBE\ffc`）。**无独立的 TypeSupport 字体缓存目录**（字体缓存位于用户 AppData）。

### 1.2 Autodesk — 1,604.6 MB / 6,968 files

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `Autodesk\ApplicationPlugins` | 1,439.3 MB | 6,020 | 是 | **X** | 3ds Max 插件本体总目录 | — |
| `...\3dsmax-civilview-2025-1.2.2.0` | 836.3 MB | 5,310 | 是 | **X** | Civil View 插件（Contents\ 全部二进制） | 需重装 |
| `...\MAXtoA_2025` | 422.5 MB | 456 | 是 | **X** | Arnold 渲染器 for 3ds Max。含 `license\` 41.4MB、`bin\` 236.6MB、`plugins\` 68.8MB | 需重装 |
| `...\Retopology3dsMax2025` | 70.7 MB | 46 | 是 | **X** | 重拓扑插件 | 需重装 |
| `...\ChaosScatter3dsMax2025` | 48.3 MB | 75 | 是 | **X** | Chaos Scatter 散布插件 | 需重装 |
| `...\Phoenix3dsMax2025` | 37.5 MB | 19 | 是 | **X** | Phoenix FD 流体插件 | 需重装 |
| `...\AdvancedModeling3dsMax2025` | 13.6 MB | 42 | 是 | **X** | 高级建模插件 | 需重装 |
| `...\SubstanceIn3dsMax2025` | 4.7 MB | 68 | 是 | **X** | Substance 插件（含 `license\`） | 需重装 |
| `...\CityscapePro3dsMax` / `SuperGrass3dsMax2025` | 5.6 MB | 4 | 是 | **X** | Cityscape / V-Ray 草地插件 | 需重装 |
| `Autodesk\Uninstallers` | 111.7 MB | 110 | 是 | C | 12 个产品的卸载程序备份（每个 6–9MB）。删除→这些产品无法通过"应用和功能"正常卸载，须手动清理 | 不重建 |
| `Autodesk\ODIS` | 35.1 MB | 550 | 是 | **X** | 安装部署服务数据库：`data.mdb` 10MB、`Package.db` 5.9MB、`Install.db` 0.4MB、`LocalCache.db`、`metadata\` 18.7MB/541。**禁删**，删除→Autodesk 无法安装/更新/修复 | 不重建 |
| `Autodesk\ADPSDK` | 10.9 MB | 33 | 是 | **X** | 桌面平台 SDK + 用户同意记录 `UserConsent\` | 不重建 |
| `Autodesk\AdskLicensingService` | 3.6 MB | 35 | 是 | **X** | **授权服务**。含 `Log\` 2.6MB/26（唯一可删部分）、`AdskLicensingService.data`、`.sds` 0.5MB | 日志会重建 |
| `Autodesk\AdskLicensingService\Log` | 2.6 MB | 26 | 是 | **S** | 授权服务运行日志（纯 .log） | ✅ 自动重建 |
| `Autodesk\CER` | 2.7 MB | 5 | 是 | **X** | **崩溃报告提交系统**（非纯日志）：`cer.db` 1.3MB 数据库 + `service.log` 1.5MB + `pending_tasks\`（待上传崩溃包）。删除→未上传的崩溃报告丢失 | 不重建 |
| `Autodesk\Adlm` | 0.4 MB | 22 | 是 | **X** | **授权管理核心**：`R23`–`R37\AdlmErrorCodes.xml`（每个 66KB）、`ASR\*.asr` 授权状态文件（6 个）、`CascadeInfo.cas`、**`ProductInformation.pit`**（二进制授权信息）。删任何一项→CAD/3dsMax 掉激活 | 不重建 |
| `Autodesk\Genuine Autodesk Service` | 0.2 MB | 3 | 是 | **X** | 正版校验服务 `source.dat` + 配置 | 不重建 |
| `Autodesk\IDSDK` | 0.4 MB | 95 | 是 | **X** | 身份 SDK，目录名 `41646D696E6973747261746F72` 是 **"Administrator" 的十六进制**，内含 boost_interprocess 命名管道 | 不重建 |
| `Autodesk\Synergy` | 0.0 MB | 91 | 是 | C | 3ds Max 2025 跨进程同步（`Max2025.27.0.64.syncfg` + 90 个 boost 共享内存文件）。删除→Max 重启后重建，运行中删除可能致其异常 | 会重建 |
| `Autodesk\Downloads` | 0.0 MB | 1 | 是 | **X** | `pasjournal.bin` 安装事务日志 | 不重建 |
| `Autodesk\LicensingAnalyticsClient` | 0.0 MB | 0 | 是 | **X** | 许可遥测客户端（`Logs\` 空） | — |
| `Autodesk\Revit Interoperability 2022` | 0.0 MB | 0 | 是 | X | 空目录 | — |
| `Autodesk\AcNGEN` | 0.0 MB | 0 | 是 | X | 空目录 | — |
| `Autodesk\ACD-2024.0.0.F-background.png` 等 2 文件 | 0.0 MB | 2 | 是 | C | AutoCAD 安装器图标/背景图 | 不重建 |
| `Autodesk\Genuine_ID.dat` | 0.0 MB | 1 | 是 | **X** | 正版标识数据 | 不重建 |

### 1.3 Red Giant — 1,463.1 MB / 4,018 files

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `Red Giant\Trapcode Packs` | 751.0 MB | 2,420 | 是 | **X** | Trapcode 预设包（`TC14` 734.1MB/2267、`TC15` 15.5MB/132、`TC16` 1.3MB/21）。`.xbxs` 104.5MB/524 + `.xbxc` 24MB/301 + `.pak` 30MB/58 | 需重装 |
| `Red Giant\Knoll Light Factory` | 335.8 MB | 655 | 是 | **X** | 光晕插件资源：`Presets\` 231.8MB/379、`LFRender\` 76.1MB/158、`Elements\` 28MB/107、`LensDesigner\` | 需重装 |
| `Red Giant\Red Giant Service` | 154.8 MB | 119 | 是 | **X** | `FuseWindow\` 149.4MB/72（Fusion 窗口运行时）+ `Resources\` 5.4MB | 需重装 |
| `Red Giant\Trapcode` | 88.9 MB | 4 | 是 | **X** | `DesignerCore\` 插件核心 | 需重装 |
| `Red Giant\ProductAtlas` | 48.1 MB | 296 | 是 | **X** | `plugins\` 48.1MB/293 产品清单数据库 | 不重建 |
| `Red Giant\Trapcode Particular` | 42.5 MB | 2 | 是 | **X** | `Tools\` 2 个大文件 | 需重装 |
| `Red Giant\Universe` | 22.6 MB | 40 | 是 | **X** | Universe 插件：`Libraries\` 19MB/35 + `Fonts\` 3.6MB/5 | 需重装 |
| `Red Giant\Supercomp` | 10.2 MB | 172 | 是 | **X** | `NxApp\` Supercomp 运行时 | 需重装 |
| `Red Giant\Common\Libraries` | 4.2 MB | 2 | 是 | **X** | 共享运行库 | 需重装 |
| `Red Giant\Installation Receipts` | 1.3 MB | 190 | 是 | **X** | 190 个安装回执 XML + `EULA\`。**卸载器依赖它们** | 不重建 |
| `Red Giant\Red Giant App\Content` | 1.1 MB | 44 | 是 | C | App 界面资源 | 需重装 |
| `Red Giant\Documentation\Acknowledgements` | 0.7 MB | 23 | 是 | C | 开源致谢文档 | 需重装 |
| `Red Giant\uninstall` | 0.8 MB | 14 | 是 | **X** | 12 个卸载 .bat 脚本 + Link | 不重建 |
| `Red Giant\Content Service\Extensions` | 0.7 MB | 1 | 是 | **X** | 内容服务扩展 | 需重装 |
| `Red Giant\.rgdeploy\history` | 0.1 MB | 18 | 是 | **X** | 部署清单（`*_rgmanifest.xml`），App Manager 据此判断已装版本 | 不重建 |
| `Red Giant\.service\products.db` | 0.1 MB | 1 | 是 | **X** | **产品数据库**（SQLite 131KB，改于 2026/6） | 不重建 |
| `Red Giant\Logs\*.txt` | 0.1 MB | 14 | 是 | **S** | 14 个安装日志，**全部时间戳为 2018–2019 年**（Trapcode/VFX installer logs） | ✅ 新装时另建 |
| `Red Giant\Link\cacheData` | 0.0 MB | 1 | 是 | **X** | 名字叫 cache，实为 2018/1/11 的 Python pickle（`(dp0`）状态文件，13.8KB。**看似缓存实为状态** | 不重建 |
| `Red Giant\xtsync\111Z14Y0.DS` | 0.0 MB | 1 | 是 | **X** | 13 字节同步标识（2018 年） | 不重建 |
| `Red Giant\.rgltokens` | 0.0 MB | 1 | 是 | **X** | 79 字节，内容为 `{"com.redgiant.adobe-licensing.warning":...}` —— **Adobe 授权警告令牌** | 不重建 |
| `Red Giant\Red Giant App` (其余) | 0.0 MB | 0 | 是 | X | — | — |

### 1.4 RedGiant（无空格）— 275.8 MB / 433 files

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `RedGiant\KnollLightFactory` | 275.8 MB | 380 | 是 | **X** | KLF 插件资源：`Presets\` 171.8MB/104、`LFRender\` 76.1MB/158（.lfp 199.8MB/211）、`Elements\` 28MB/107、`Tif` 75.4MB/18 | 需重装 |
| `RedGiant\Licenses` | 0.0 MB | 53 | 是 | **X** | **52 个 .rgs 许可证文件**（二进制加密）+ `MagicBulletLooks.wk`。覆盖 Trapcode Suite / Magic Bullet / VFX / Primatte / PluralEyes 等全套。**任何一个都禁删** | 不重建 |

### 1.5 Blackmagic Design — 796.8 MB / 481 files

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `Blackmagic Design\DaVinci Resolve\Support\plugins` | 622.7 MB | 17 | 是 | **X** | OFX 插件二进制（17 个 .bin/.dll，最大 198.8MB、138.3MB、80.1MB）. **不是缓存，是插件本体** | 需重装 |
| `Blackmagic Design\DaVinci Resolve\Support\LUT` | 98.5 MB | 123 | 是 | **X** | 123 个色彩查找表（.cube 92.4MB/108）。按厂商：ACES/Arri/Astrodesign/Blackmagic/DCI/DJI/Film Looks/HDR/Olympus 等 | 需重装 |
| `Blackmagic Design\DaVinci Resolve\Support\Libraries` | 42.1 MB | 23 | 是 | **X** | 共享运行库 | 需重装 |
| `Blackmagic Design\DaVinci Resolve\Support\BMDFirmware` | 19.4 MB | 5 | 是 | **X** | 硬件固件（DeckLink/UltraStudio 等） | 需重装 |
| `Blackmagic Design\DaVinci Resolve\Support\trim_lut0.dpx` | 7.9 MB | 1 | 是 | **X** | 系统内置 LUT 基准图 | 需重装 |
| `Blackmagic Design\DaVinci Resolve\Support\Developer` | 4.6 MB | 204 | 是 | **X** | SDK：CodecPlugin/Fusion Fuse/Fusion Templates/OpenFX/Scripting/Workflow Integrations 等开发接口 | 需重装 |
| `Blackmagic Design\DaVinci Resolve\Support\easyDCP` | 0.7 MB | 77 | 是 | **X** | DCP 打包库 | 需重装 |
| `Blackmagic Design\DaVinci Resolve\Support\Fairlight` | 0.4 MB | 8 | 是 | **X** | 音频面板配置（Euphonix 等） | 需重装 |
| `Blackmagic Design\DaVinci Resolve\Support\Certificates` | 0.2 MB | 2 | 是 | **X** | 数字证书 | 不重建 |
| `Blackmagic Design\DaVinci Resolve\Support\License` | 0.1 MB | 7 | 是 | **X** | 第三方开源许可证文本（LGPL/openssl/magick 等）。与激活无关但**属 License 目录，规则应整体豁免** | 需重装 |
| `Blackmagic Design\DaVinci Resolve\Support\log-conf.xml` | 0.0 MB | 1 | 是 | **X** | **日志配置文件**（不是日志本身） | 需重装 |
| `Blackmagic Design\DaVinci Resolve\Support\logs` | 0.0 MB | 0 | 是 | **S** | 空目录，日志实际写入用户 AppData。**可加入规则但当前 0 收益** | ✅ 会重建 |
| `Blackmagic Design\DaVinci Resolve\Support\config.bin` / `default-config.dat` / `default_cm_config.bin` | 0.2 MB | 3 | 是 | **X** | 色彩管理默认配置 | 不重建 |
| `Blackmagic Design\DaVinci Resolve\Fusion\*` (14 个空子目录) | 0.0 MB | 0 | 是 | **X** | Brushes/Config/LUTs/Macros/Settings/Templates 等。**是用户内容的官方落点，禁删**（用户可能已放入素材） | — |
| `Blackmagic Design\DaVinci Resolve\Preferences\EuphonixPanelDaemon.xml` | 0.0 MB | 1 | 是 | **X** | 调音台守护进程配置 | 会重建 |

> **重要澄清**：`C:\ProgramData\Blackmagic Design` 下**没有** Cache / Gallery 静帧 / 项目文件（.drp）/ 数据库。
> - **Cache** 位于用户级 `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\CacheClip`
> - **Gallery 静帧** 位于 `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\.gallery`
> - **项目库（.drp / disk db）** 位于 `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\Resolve Disk Database`
>
> 这些都不在本域的 ProgramData 路径下，**不要在此域建规则覆盖它们**。

### 1.6 BorisFX — 388.9 MB / 13,989 files

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `BorisFX\ContinuumAE\12` | 293.6 MB | 9,607 | 是 | **X** | Continuum 12：`BorisFX\` 157.5MB/4866（插件本体）+ `Presets\` 136.1MB/4740 + `Log\usage_data_borisfx_ae.txt` 7.8KB | 需重装 |
| `BorisFX\ContinuumAE\11` | 95.3 MB | 4,382 | 是 | **X** | Continuum 11：`Presets\` 75.7MB/4275 + `Grunge Texture\` 11.7MB/24 + `Image Collection - Particle\` 7.7MB/71 + `Workspaces\` 0.2MB/12（13 个 .tsws 工作区布局） | 需重装 |
| `BorisFX\EmitterLibraries` | 0.0 MB | 0 | 是 | **X** | 空目录（粒子发射器库官方落点） | — |
| `BorisFX\ContinuumAE\12\Log\usage_data_borisfx_ae.txt` | 0.0 MB | 1 | 是 | **C** | 7.8KB 用量统计。可删，无收益 | 会重建 |

> **结构陷阱**：`12\Presets\` 与 `12\BorisFX\ContinuumAE\12\Presets\` 是**同一批预设的两份拷贝**（例如 `LT_NumericsGlowTrail.bsp` 11.3MB 各存一份）。这造成 13,989 的超高文件数，**但两份都属 X 级** —— 删任一份都可能让插件找不到预设。

### 1.7 Exposure Software — 515.6 MB / 2,768 files

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `Exposure Software\Exposure X7\Textures` | 367.6 MB | 1,301 | 是 | **X** | **纹理素材库**：608 个 .jpg（357.2MB）胶片边框/颗粒/光晕底图 + `_thumb.png` 327 个 | 需重装 |
| `Exposure Software\Exposure X7\LUTs` | 132.3 MB | 660 | 是 | **X** | 330 个 .cube（88.8MB）+ 330 个 .cubebin（43.5MB）GUID 命名 LUT | 需重装 |
| `Exposure Software\Exposure X7\Exposure` | 8.3 MB | 570 | 是 | **X** | **570 个 .f1s 内置预设**（B&W Films / Cinema / Cross Processing / Lo-Fi / Polaroid 等全系列） | 需重装 |
| `Exposure Software\Exposure X7\*.presets` (17 个) | 0.1 MB | 17 | 是 | **X** | 用户可编辑预设：AspectRatio/Brush/ColorEdit/Destination/Export/FileNaming/FileType/FilterSort/ImageSizing/LUT/MetadataExport/Print/Shortcuts/Watermark/Workspace 等 | 不重建 |
| `Exposure Software\Exposure X7\CameraProfiles.db` | 2.0 MB | 1 | 是 | **X** | 相机配置文件数据库 | 不重建 |
| `Exposure Software\Exposure X7\LensProfiles.db` | 3.2 MB | 1 | 是 | **X** | 镜头配置文件数据库 | 不重建 |
| `Exposure Software\Exposure X7\{BokehLens,BrushEffect,ColorConversion,...}` 12 个目录 | 0.5 MB | ~200 | 是 | **X** | 各效果类别的参数预设库 | 需重装 |
| `Exposure Software\Exposure X7\Test` | 0.0 MB | 0 | 是 | X | 空目录 | — |
| `Exposure Software\Exposure X7\*.qm` (7 个) | 1.5 MB | 7 | 是 | **X** | 德语/法语/中文界面语言包 | 需重装 |
| `Exposure Software\entityresolver.guid` | 0.0 MB | 1 | 是 | **X** | 36 字节实体解析 GUID | 不重建 |

> **注意**：Exposure X7 **整个目录树里没有任何预览缓存**。Exposure 的缩略图/预览缓存位于用户级 `%LOCALAPPDATA%\Exposure Software\` 或 catalog 数据库旁，不在 ProgramData。**本域无可删项。**

### 1.8 LogiOptionsPlus — 999.3 MB / 3,149 files

| 路径 | 体积 | 文件数 | 存在 | 等级 | 说明 | 重建 |
|---|---|---|---|---|---|---|
| `LogiOptionsPlus\depots\652491` | 998.0 MB | 3,141 | 是 | **X** | **软件仓库（不是缓存）**：`logioptionsplus\` 484.4MB/624（主程序 + locales 37.4MB + resources 72.5MB + thumbnails 41.5MB + data 9MB）、`logivoice\` 205.6MB/813、`logi_plugin_service\LogiPluginServiceInstaller.msi` 107.3MB、`plugin_installer\` 67.3MB（VSTO 45.4MB）、`right_sight\LogiRS4WebCamsInstaller.msi` 24.4MB、`mx_mechanical\` 23.5MB（含 9.2MB/6.1MB gif）、`88b73d28-...\lpsUiFeatureTour\` 17.8MB、`plugin_cep\LogiOptionsPlusAdobe\` 2.9MB/1313 | 会重下 |
| `LogiOptionsPlus\depots\652491\features_config\features.json` | 0.0 MB | 1 | 是 | **X** | 功能开关配置 | 会重建 |
| `LogiOptionsPlus\depots\652491\software_events_virtual_device` | 0.0 MB | 4 | 是 | **X** | 虚拟设备动态槽位定义 | 会重建 |
| `LogiOptionsPlus\cache` | 0.0 MB | **0** | **是** | **S** | **目录存在但完全空**（`dir /a /s` 确认 0 文件 0 字节）。已是可删状态，无需操作 | ✅ |
| `LogiOptionsPlus\devices.json` | 0.3 MB | 1 | 是 | **X** | **设备配置**：Flow hostCount=3、电池状态、SmartShift 模式(RATCHET)、滚轮速度/力度/sensitivity=83 等。**删了 = 丢失全部鼠标自定义设置** | 不重建 |
| `LogiOptionsPlus\installation.json` | 0.7 MB | 1 | 是 | **X** | **安装清单**，App 据此判断已装组件 | 不重建 |
| `LogiOptionsPlus\current.json` | 0.4 MB | 1 | 是 | **X** | 当前状态/版本指针 | 会重建 |
| `LogiOptionsPlus\keys.json` | 0.0 MB | 1 | 是 | **X** | **按键映射/宏绑定**（用户配置） | 不重建 |
| `LogiOptionsPlus\groups.json` | 0.0 MB | 1 | 是 | **X** | 设备分组配置 | 不重建 |
| `LogiOptionsPlus\features_cache.json` | 0.0 MB | 1 | 是 | C | 名字含 cache，但**仅 1KB 功能开关缓存**，删除收益为零且可能触发重新拉取 | 会重建 |
| `LogiOptionsPlus\next.json` | 0.0 MB | 1 | 是 | **X** | 待应用更新状态 | 会重建 |
| `LogiOptionsPlus\periodic_check.json` | 0.0 MB | 1 | 是 | **X** | 更新检查周期状态 | 会重建 |

> **LogiOptionsPlus 没有任何日志目录**。日志位于 `%LOCALAPPDATA%\Logi\LogiOptionsPlus\`。本域无可删项。

---

## 2. 建议加入规则库清单

> **总计可回收空间：约 2.7 MB**。本域**不建议**加入任何"大容量清理"规则。
> 以下每条路径均精确到子目录并带通配符。

### 2.1 safe 级（纯日志，软件自动重建，零风险）

| # | 路径（带通配） | 实测体积 | risk | 理由 |
|---|---|---|---|---|
| 1 | `C:\ProgramData\Red Giant\Logs\*.txt` | 0.1 MB / 14 | **safe** | 2018–2019 年的安装日志，纯文本，软件不再读写 |
| 2 | `C:\ProgramData\Autodesk\AdskLicensingService\Log\*` | 2.6 MB / 26 | **safe** | 授权服务轮转日志（.log）。**注意只匹配 `Log\` 子目录，绝不匹配父目录** |

### 2.2 risk 级（需用户确认；建议默认关闭，仅"深度清理"模式启用）

| # | 路径（带通配） | 实测体积 | risk | 理由与后果 |
|---|---|---|---|---|
| 3 | `C:\ProgramData\Adobe\UPI\Log\*.log` | <0.1 MB / 1 | **risk** | 只有 `EMCL.log` 23KB。删除→Adobe 授权模块排障信息丢失 |
| 4 | `C:\ProgramData\BorisFX\ContinuumAE\*\Log\usage_data_borisfx_ae.txt` | <0.1 MB / 2 | **risk** | 用量统计文本。删除→BorisFX 用量分析重置（不影响功能） |
| 5 | `C:\ProgramData\Adobe\Installer\Icons\*` | 4.9 MB / 172 | **risk** | 卸载列表图标。删除→控制面板中 Adobe 产品显示空白图标，**不重建**。这是本域唯一有"可见体积"的可选项，但需明示后果 |
| 6 | `C:\ProgramData\LogiOptionsPlus\features_cache.json` | <0.1 MB / 1 | **risk** | 功能开关缓存。删除会触发一次重新拉取，收益近零，**建议不收录** |

### 2.3 明确不建议收录（列出以免误判为缓存）

| 路径 | 看起来像 | 实际是 |
|---|---|---|
| `C:\ProgramData\Adobe\CameraRaw\*` | 缓存 | 相机/镜头配置文件 + AI 模型（2.30 GB） |
| `C:\ProgramData\Red Giant\Link\cacheData` | 缓存 | 2018 年 Python pickle 状态文件 |
| `C:\ProgramData\LogiOptionsPlus\cache\*` | 缓存 | 确实是缓存目录，但**当前为空**，收录无收益 |
| `C:\ProgramData\LogiOptionsPlus\depots\*` | 缓存 | **完整安装包仓库**（998 MB），删后无法自修复 |
| `C:\ProgramData\Autodesk\CER\*` | 崩溃日志 | 崩溃报告数据库 + 待上传队列 |
| `C:\ProgramData\Autodesk\Synergy\boost_interprocess\*` | 临时文件 | 跨进程共享内存，运行中删除可致 Max 异常 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\logs\*` | 日志 | 目录为空，日志在用户 AppData |
| `C:\ProgramData\Exposure Software\Exposure X7\LUTs\*` | LUT 缓存 | 是用户可用 LUT 资产（.cube） |
| `C:\ProgramData\BorisFX\ContinuumAE\1[12]\Presets\*` | 预设缓存 | 是插件预设，删除后效果器无预设可用 |

---

## 3. X 级禁删清单

> **实现要求：以下路径必须在规则匹配前短路返回，且不得被任何上级目录的通配规则"继承删除"。**

### 3.1 许可证 / 激活 / 授权（最高优先级）

| 路径 | 为什么禁删 |
|---|---|
| `C:\ProgramData\Adobe\SLStore\*` | Adobe 授权存储（`5DE5DF676F9B` 序列号标识 + `Adobe01.bmp`）。删除→Adobe 全系掉激活/需重新登录 |
| `C:\ProgramData\Adobe\UPI\EM Store\**` | 各 Adobe 产品（AE/AU/AI/PS/PR/AME）授权模块存放点 |
| `C:\ProgramData\Adobe\UPI\Configuration\DB\UPISys.db` | 授权配置数据库 |
| `C:\ProgramData\Adobe\UPI\Configuration\XManConfigV2.xml` | 授权管理配置 |
| `C:\ProgramData\Autodesk\Adlm\**` | **Autodesk 授权核心**：`ProductInformation.pit`（二进制授权信息）、`ASR\*.asr`（6 个授权状态）、`CascadeInfo.cas`、`R23`–`R37\AdlmErrorCodes.xml`。删任何一项→AutoCAD/3ds Max/Maya 掉激活 |
| `C:\ProgramData\Autodesk\AdskLicensingService\657P1_2024.0.0.F\licpath.lic` | **Autodesk 许可文件路径**。删→授权服务找不到 license |
| `C:\ProgramData\Autodesk\AdskLicensingService\AdskLicensingService.data` | 授权服务数据 |
| `C:\ProgramData\Autodesk\AdskLicensingService\AdskLicensingService.sds` | 授权服务签名数据 |
| `C:\ProgramData\Autodesk\AdskLicensingSettings.json` | 授权服务设置 |
| `C:\ProgramData\Autodesk\Genuine Autodesk Service\**` | 正版校验服务 + `source.dat` |
| `C:\ProgramData\Autodesk\Genuine_ID.dat` | 正版标识 |
| `C:\ProgramData\RedGiant\Licenses\*` | **52 个 .rgs 加密许可证**（TrapcodeSuite/MagicBullet*/VfxSuite/PrimatteKeyer/PluralEyes/KnollLightFactory 等全套）。删任何一个→对应插件变试用/失效 |
| `C:\ProgramData\Red Giant\.rgltokens` | Adobe 授权警告令牌（JSON） |
| `C:\ProgramData\Autodesk\MAXtoA_2025\license\*` | Arnold 渲染器许可（41.4 MB） |
| `C:\ProgramData\Autodesk\ApplicationPlugins\SubstanceIn3dsMax2025\license\*` | Substance 插件许可 |
| `C:\ProgramData\Exposure Software\entityresolver.guid` | 实体解析 GUID（授权/身份关联） |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\License\*` | 许可证文本目录 —— 虽为开源声明，但**"License" 目录应整体豁免**以避免规则误伤 |

### 3.2 用户配置 / 偏好设置

| 路径 | 为什么禁删 |
|---|---|
| `C:\ProgramData\LogiOptionsPlus\devices.json` | **全部设备配置**：SmartShift 模式、滚轮速度/力度/sensitivity、Flow 主机数、电池/按键能力。删除→鼠标设置全部重置 |
| `C:\ProgramData\LogiOptionsPlus\keys.json` | **按键映射与宏绑定**（用户配置） |
| `C:\ProgramData\LogiOptionsPlus\groups.json` | 设备分组配置 |
| `C:\ProgramData\LogiOptionsPlus\installation.json` | 安装清单，App 据此判断已装组件 |
| `C:\ProgramData\LogiOptionsPlus\current.json` | 当前状态/版本指针 |
| `C:\ProgramData\LogiOptionsPlus\next.json` | 待应用更新状态 |
| `C:\ProgramData\LogiOptionsPlus\periodic_check.json` | 更新检查周期状态 |
| `C:\ProgramData\Adobe\PINF\xpuinfo.json` | XPU 硬件加速探测状态 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Preferences\*` | Resolve 偏好设置（Euphonix 面板等） |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\config.bin` | Resolve 主配置 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\default-config.dat` | 默认配置 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\default_cm_config.bin` | 色彩管理默认配置 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\log-conf.xml` | 日志配置（不是日志！） |
| `C:\ProgramData\Autodesk\Synergy\Max2025.27.0.64.syncfg` | 3ds Max 2025 同步配置 |
| `C:\ProgramData\Red Giant\Red Giant Service\preferences\*` | Red Giant 服务偏好 |
| `C:\ProgramData\Exposure Software\Exposure X7\*.presets` (17 个) | 用户可编辑预设（AspectRatio/Shortcuts/Workspace/Export 等） |

### 3.3 预设 / 素材 / 资产库（"看似缓存实为资产"核心区）

| 路径 | 为什么禁删 |
|---|---|
| `C:\ProgramData\Adobe\CameraRaw\Settings\**` | 921 个 .xmp 内置预设与配置文件（含 Adobe/Premium/Apple/Google/SamsungLooks）。删除→Camera Raw/Lightroom 预设全空 |
| `C:\ProgramData\Adobe\CameraRaw\CameraProfiles\**` | 4,199 个 .dcp 相机色彩配置。删除→RAW 无法正确显色 |
| `C:\ProgramData\Adobe\CameraRaw\LensProfiles\**` | 3,281 个 .lcp 镜头配置。删除→镜头校正失效 |
| `C:\ProgramData\Adobe\CameraRaw\ModelZoo\**` | 992 MB AI 模型权重（去噪/去反光/景深/选择主体天空等 33 个模型） |
| `C:\ProgramData\Adobe\CameraRaw\SaveOptions\**` | 保存预设（.xmp） |
| `C:\ProgramData\Adobe\CameraRaw\Libraries\adobe_c2pa.dll` | 内容凭证运行库 |
| `C:\ProgramData\Adobe\OOBE\ffc` | CC 首次欢迎资产（13.94 MB） |
| `C:\ProgramData\Red Giant\Trapcode Packs\**` | 751 MB Trapcode 预设包 |
| `C:\ProgramData\Red Giant\Knoll Light Factory\Presets\**` | 231.8 MB KLF 预设 |
| `C:\ProgramData\Red Giant\Trapcode\**` / `Universe\**` / `Supercomp\**` / `Trapcode Particular\**` | 插件本体与运行时 |
| `C:\ProgramData\RedGiant\KnollLightFactory\**` | 275.8 MB KLF 插件资源与预设 |
| `C:\ProgramData\BorisFX\ContinuumAE\11\Presets\**` | 4,275 个 BCC 预设 |
| `C:\ProgramData\BorisFX\ContinuumAE\12\Presets\**` | 4,740 个 BCC 预设（含 11.3 MB .bsp 粒子预设） |
| `C:\ProgramData\BorisFX\ContinuumAE\12\BorisFX\**` | 157.5 MB Continuum 插件本体 |
| `C:\ProgramData\BorisFX\ContinuumAE\11\Grunge Texture\**` | 11.7 MB 纹理素材 |
| `C:\ProgramData\BorisFX\ContinuumAE\11\Image Collection - Particle\**` | 7.7 MB 粒子素材 |
| `C:\ProgramData\BorisFX\ContinuumAE\11\Workspaces\*.tsws` | 13 个用户工作区布局 |
| `C:\ProgramData\Exposure Software\Exposure X7\Textures\**` | 367.6 MB 纹理素材库（608 jpg + 327 thumb） |
| `C:\ProgramData\Exposure Software\Exposure X7\LUTs\*.cube` / `*.cubebin` | 330 组 LUT（132.3 MB） |
| `C:\ProgramData\Exposure Software\Exposure X7\Exposure\**` | 570 个内置 .f1s 预设 |
| `C:\ProgramData\Exposure Software\Exposure X7\CameraProfiles.db` | 相机配置数据库 |
| `C:\ProgramData\Exposure Software\Exposure X7\LensProfiles.db` | 镜头配置数据库 |
| `C:\ProgramData\Exposure Software\Exposure X7\{BokehLens,BrushEffect,ColorConversion,ColorFilter,ColorSaturation,Focus,Grain,IR,SplitToning,Tone,Vignette}\**` | 各效果类别参数预设库 |
| `C:\ProgramData\Exposure Software\Exposure X7\*.qm` | 7 个界面语言包 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT\**` | 123 个内置 LUT（98.5 MB） |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\plugins\**` | 622.7 MB OFX 插件本体 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Libraries\**` | 42.1 MB 运行库 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\BMDFirmware\**` | 硬件固件 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\trim_lut0.dpx` | 系统 LUT 基准图 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\**` | SDK（Fuse/OpenFX/Scripting 等接口） |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\easyDCP\**` | DCP 库 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Fairlight\**` | 音频面板配置 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Fusion\**` | 用户内容官方落点（Brushes/Config/LUTs/Macros/Settings/Templates 等 14 个子目录） |
| `C:\ProgramData\Adobe\Common\PTX\**` | AE GPU 着色器资源（会重建但重编译耗时） |
| `C:\ProgramData\Adobe\Adobe PDF\**` | Distiller 配置与设置 |

### 3.4 数据库 / 状态 / 安装还原点

| 路径 | 为什么禁删 |
|---|---|
| `C:\ProgramData\Autodesk\ODIS\**` | 安装部署数据库（data.mdb / Package.db / Install.db / LocalCache.db / metadata 18.7 MB）。删除→Autodesk 无法安装/更新/修复 |
| `C:\ProgramData\Autodesk\ADPSDK\**` | 桌面平台 SDK + 用户同意记录 |
| `C:\ProgramData\Autodesk\IDSDK\**` | 身份 SDK（`41646D696E6973747261746F72` = "Administrator" 的十六进制） |
| `C:\ProgramData\Autodesk\Downloads\pasjournal.bin` | 安装事务日志 |
| `C:\ProgramData\Autodesk\LicensingAnalyticsClient\**` | 许可遥测客户端 |
| `C:\ProgramData\Red Giant\.service\products.db` | 产品数据库（SQLite） |
| `C:\ProgramData\Red Giant\.rgdeploy\history\**` | 部署清单，App Manager 据此判断已装版本 |
| `C:\ProgramData\Red Giant\Installation Receipts\**` | 190 个安装回执 + EULA，**卸载器依赖** |
| `C:\ProgramData\Red Giant\uninstall\**` | 12 个卸载脚本 |
| `C:\ProgramData\Red Giant\ProductAtlas\**` | 产品图谱数据库 |
| `C:\ProgramData\Red Giant\Content Service\**` | 内容服务扩展 |
| `C:\ProgramData\Red Giant\xtsync\*.DS` | 授权/同步标识 |
| `C:\ProgramData\Red Giant\Link\cacheData` | 名为 cache，实为状态 pickle |
| `C:\ProgramData\Autodesk\CER\**` | 崩溃报告数据库 + 待上传队列 |
| `C:\ProgramData\LogiOptionsPlus\depots\**` | 完整安装包仓库（998 MB） |
| `C:\ProgramData\Autodesk\Uninstallers\**` | 12 个产品的卸载程序（111.7 MB）—— 删后无法正常卸载 |
| `C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Certificates\**` | 数字证书 |

### 3.5 整目录级红线

❌ **禁止对以下任一目录建立"整目录删除"规则**（会连带删掉上述所有 X 级内容）：

```
C:\ProgramData\Adobe\**
C:\ProgramData\Autodesk\**
C:\ProgramData\Red Giant\**
C:\ProgramData\RedGiant\**
C:\ProgramData\Blackmagic Design\**
C:\ProgramData\BorisFX\**
C:\ProgramData\Exposure Software\**
C:\ProgramData\LogiOptionsPlus\**
```

❌ **同样禁止对以下"中间层"目录整删**（子目录内含 X 级资产）：

```
C:\ProgramData\Adobe\CameraRaw\**
C:\ProgramData\Adobe\UPI\**
C:\ProgramData\Autodesk\ApplicationPlugins\**
C:\ProgramData\Autodesk\AdskLicensingService\**   ← 只能删 Log\ 子目录
C:\ProgramData\Autodesk\Adlm\**
C:\ProgramData\Red Giant\Link\**
C:\ProgramData\RedGiant\Licenses\**
C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\**   ← 只能删 logs\ 子目录
C:\ProgramData\BorisFX\ContinuumAE\**
C:\ProgramData\Exposure Software\Exposure X7\**
C:\ProgramData\LogiOptionsPlus\depots\**
```

---

## 4. 权限与完整性说明

- **ACCESS_DENIED：无**。全部 8 个根目录均成功递归读取，无权限拒绝。
- 全部数字为本机 `Get-ChildItem -Force -Recurse -File` 实测值，非估算。
- 根目录体积复核（实测 vs 任务给出）：

| 目录 | 实测 | 任务给出 | 差异说明 |
|---|---|---|---|
| Adobe | 2,325.5 MB / 8,702 | 2,325.1 / 8,691 | 基本一致（含任务扫描后新增文件） |
| Autodesk | 1,604.6 MB / 6,968 | 1,604.6 / 6,968 | 一致 |
| Red Giant | 1,463.1 MB / 4,018 | 1,463.1 / 4,018 | 一致 |
| RedGiant | 275.8 MB / 433 | 275.8 / 433 | 一致 |
| Blackmagic Design | 796.8 MB / 481 | 796.8 / 481 | 一致 |
| BorisFX | 388.9 MB / 13,989 | 388.9 / 13,989 | 一致 |
| Exposure Software | 515.6 MB / 2,768 | 515.6 / 2,768 | 一致 |
| LogiOptionsPlus | 999.3 MB / 3,149 | 999.3 / 3,149 | 一致 |

- **未执行任何写操作**：无删除、无移动、无修改、无 ACL 变更。全部为读取与统计。

---

## 5. 给规则引擎的实施建议

1. **本域整体归类为"高资产密度域"**，建议在 UI 中标注为"创意软件资产区"，默认**不参与一键清理**。
2. **白名单机制优于黑名单**：本域只有 2 条 safe 规则，建议直接硬编码白名单（`Red Giant\Logs\*.txt`、`Autodesk\AdskLicensingService\Log\*`），其余一律拒绝，而非枚举 X 级黑名单。
3. **通配符必须锚定到具体子目录**：禁止 `**` 跨越 2 层以上。例如允许 `...\AdskLicensingService\Log\*`，但禁止 `...\AdskLicensingService\**`。
4. **大小写不敏感匹配**：Windows 下 `Red Giant` 与 `RedGiant` 是两个真实共存的目录，且 `redgiant` 大小写变体也存在。规则匹配应统一转小写，但**输出路径必须保留原始大小写**。
5. **DaVinci 域外提醒**：真正的 Resolve 缓存/Gallery/项目库在 `%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\{CacheClip,.gallery,Resolve Disk Database}`，应在**用户 AppData 域**另立规则，本域不要覆盖。
