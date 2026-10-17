Winapp2.ini 清理规则库（解析版）
================================

来源: https://github.com/MoscaDotTo/Winapp2
版本: 260915（2026-09-15），仓库内 Winapp2.ini（4,068 节，34,898 行）
许可: CC-BY-SA-4.0（使用/再分发需署名 winapp2 项目并同样共享）

文件说明:
- winapp2_rules.json : 全部规则的结构化 JSON，每节含：
    name        完整节名，如 "Google Chrome Caches *"
    app         应用名（启发式提取），如 "Google Chrome"
    category    类别（启发式提取），如 "Caches" / "Web Browsing History"
    lang_secref CCleaner 语言区段编号
    detect      检测条件数组，如 "DetectFile=%LocalAppData%\\Google\\Chrome*"
                （Detect=注册表存在性检测，DetectFile=文件/目录存在性检测）
    file_keys   文件清理规则数组，格式: 路径|匹配|标志
                如 "%LocalAppData%\\Google\\Chrome*\\User Data\\*|*|REMOVESELF"
                常用标志: RECURSE（递归子目录）、REMOVESELF（删目录本身）
    reg_keys    注册表清理数组，如 "HKCU\\Software\\...\\TypedURLs"
    exclude_keys 排除项（白名单）
- stats.txt : 规则统计
- repo/ : 原始 GitHub 仓库（含 Winapp3/、Non-CCleaner/ 变体，未解析）

路径变量（safecleaner 需自行展开）:
  %LocalAppData% %AppData% %ProgramFiles% %WinDir% %SystemDrive% 等
  通配符 * 可出现在路径任意位置（含目录名）。

与 360 规则的对照:
  FileKey ≈ 360 的 Directory/File 类型规则
  RegKey  ≈ 360 的 RegKey/RegValue 类型规则
  Detect  ≈ 360 的软件安装检测（SoftCheck.dat）
  注意 Winapp2 没有 360 式的 SQLite 按表清理，浏览器 SQLite 需整库删或自行实现。

解析脚本逻辑见任务记录；app/category 为启发式切分，仅供分组参考，
精确匹配请以 name/detect/file_keys 为准。
