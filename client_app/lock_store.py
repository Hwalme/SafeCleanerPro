# -*- coding: utf-8 -*-
"""锁定状态持久化。

用户在列表中对某清理项「上锁」后，该锁定要跨启动记忆：
存 %LOCALAPPDATA%/SafeCleanerPro/lock_state.json（与 license.key 同目录）。
锁定 = 该项永远不参与清理（等于不被勾选的状态），容量计入
「核心安全锁定保护」中的「手动上锁」细分。
"""
import json
import os


def _lock_file_path():
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    app_dir = os.path.join(base, "SafeCleanerPro")
    try:
        os.makedirs(app_dir, exist_ok=True)
    except Exception:
        pass
    return os.path.join(app_dir, "lock_state.json")


def load_locks():
    """返回已锁定项 id 集合；文件缺失/损坏时返回空集合。"""
    try:
        p = _lock_file_path()
        if not os.path.exists(p):
            return set()
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            ids = data.get("locked_ids", [])
        elif isinstance(data, list):
            ids = data
        else:
            ids = []
        if isinstance(ids, list):
            return {str(x) for x in ids}
    except Exception:
        pass
    return set()


def save_locks(locked_ids):
    """原子写回锁定集合（先写临时文件再替换）。"""
    try:
        p = _lock_file_path()
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"locked_ids": sorted(str(x) for x in locked_ids)},
                      f, ensure_ascii=False, indent=1)
        os.replace(tmp, p)
        return True
    except Exception:
        return False
