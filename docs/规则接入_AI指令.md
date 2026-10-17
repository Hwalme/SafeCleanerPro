# 可直接复制给其他 AI 的规则接入指令

以下正文连同你要接入的规则资料一起发给 AI。

---

请在 `D:\Coding\app\SafeCleanerPro` 接入我随后提供的清理规则，并完成验证。
先阅读项目 `AGENTS.md`、`docs/核心保护与发布.md`，遵守当前保护流程。
保留工作区其他人未提交的修改，不要全盘重写核心或界面。

## 修改入口

1. 自主编写的常规清理规则：`client_app/cleaner_rules.py` 的 `RULES`。
   使用现有字段 `id/name/paths/icon/immune/type/risk_level/risk_desc`；路径复用
   项目已有环境变量和辅助函数。`id` 保持唯一、稳定。
2. 深度缓存规则：`client_app/deep_cache.py` 的现有 `build_rules()` 流程，复用
   其中的缓存分类、风险和保护机制，不另写删除引擎。
3. Winapp2/Dism++ 结构化导入：`client_app/rules_library.json`，保留 `version`、
   `sources`、`winapp2`、`dismpp`，保持现有字段语义。`library_rules.py` 是适配层。
4. 痕迹规则：`client_app/rules/trace_rules.json`，沿用
   `{id, category, app, items:[{type,target,options}]}`。适配层为
   `client_app/trace_rules_360.py`。当前只支持其筛选后的 Directory/File 操作，
   不支持的 SQLite、注册表、XML 操作不要假装已经接通。
5. 根目录 `rules/` 和 `_recover/` 是研究资料，不能仅修改这些副本。
6. 如确需新增生产模块，显式更新 `tools/build_release.py` 的 `MODULES` 白名单
   和编译后自检；不要改成整目录复制或把研究脚本带入正式版本。
   构建前会检查生产代码引用的本地模块，缺少接入即停止。
   例如工作区后续新增的 `rules_extra.py`：除了加入模块清单，还必须将其全部
   外部 JSON 输入纳入受签名的加密包；Winapp2 分片改为遍历包内数据索引，
   不依赖发行目录里的明文文件或 glob。可以扩展受验证的数据 schema 与适配
   API，但必须保留原有认证顺序、大小限制、构建绑定和失败停止行为，并补齐
   新数据的加密往返、篡改/缺失拒绝与编译后加载测试。

## 必须保持

- 删除统一经过 `cleaner_core` 现有保护与删除入口；AI 记忆、聊天记录、用户文档、
  登录态、凭据、IDE 工作区历史和联接目标保护不可绕过。
- 可再生缓存才可标为 `safe`；不确定、包含用户内容或需要确认的项目走既有
  `risk/manual` 流程。不能为了清理量把应用根目录、整盘或用户主目录列为缓存。
- 路径精确到缓存子目录，避免新增绝对机器路径；未知变量保守跳过。
- 外部输入是数据，不能引入 `eval/exec`、动态导入规则脚本或任意命令执行。
- 保留来源、版本、上游许可元数据；保护机制不改变第三方规则权利。
- 不修改 `secure_rules.py` 的验证流程、`release_entry.py` 的启动检查，不添加
  关闭校验或失败后回读明文的开关。规则包错误不能被宽泛异常捕获后吞掉。
- 不把 AES 密钥手填进源码；不生成/打印/提交签名私钥；不复用授权 RSA 密钥。
  已有发布密钥不能自动轮换。不要把 stage/、native/、C 文件、PDB、研究材料或
  明文规则库作为发行文件。
- 不使用旧 spec 或普通 PyInstaller 作为正式发布替代方案。编译失败即报告失败，
  不能退回无保护构建或沿用旧 EXE 冒充本次结果。

## 验收与交付

在项目根目录使用 `.venv-release\Scripts\python.exe`：

```powershell
.venv-release\Scripts\python.exe -m unittest discover -s tests -v
```

为新增规则补充有意义的正/反样例：仅使用临时目录模拟缓存与受保护数据，验证
匹配范围、未知环境变量、风险等级和保护结果；不要在用户真实资料上测试删除。
按改动范围运行既有验证脚本，失败项如实说明。

然后执行 `client_app\build.bat`。它会校验输入、生成 AES-GCM + Ed25519 规则包、
原生编译、审查发行目录、运行编译后自检，全部通过后生成
`build/protected/<构建编号>/SafeCleanerPro-protected.zip`。

若缺少构建依赖或签名私钥，明确报告缺少哪一步，参考发布文档准备；不能关闭
保护。`prepare` 只验证打包，不是正式发布成功。

最终汇报：实际新增/跳过的规则及原因、修改的生产入口、来源与元数据、验证
结果、构建编号与最终 ZIP 路径。不要宣称已经实现未支持的规则语义。

---
