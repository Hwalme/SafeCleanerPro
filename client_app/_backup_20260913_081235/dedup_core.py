# -*- coding: utf-8 -*-
"""
dedup_core.py — SafeCleanerPro 重复文件查重引擎
================================================
特性:
  - 多位置: 整盘 / 指定盘 / 指定文件夹, 任意组合
  - 扫描历史: history.json + 结果快照 results_<id>.json
  - 增量跳过: cache.json 记录 path→(size,mtime,哈希), 未变化文件零IO复用
  - 强制重扫: incremental=False 忽略缓存
  - 系统排除: 系统盘在"整盘模式"自动排除; 系统目录/系统文件始终跳过
  - 三阶段: 体积分组 → 首尾64KB部分哈希 → 仅部分碰撞组做全量SHA256
  - 删除校验: 同组保留副本存活才删, 防删空
"""
import hashlib
import json
import os
import string
import time
from pathlib import Path

CHUNK = 64 * 1024

SYSTEM_DIR_EXCLUDE = {
    "$recycle.bin", "system volume information", "config.msi", "$winreagent",
    "recovery", "windows", "program files", "program files (x86)", "programdata",
    "appdata", "node_modules", "__pycache__", ".git", ".venv", "venv", ".pnpm-store",
}
SYSTEM_FILE_EXCLUDE = {
    "pagefile.sys", "hiberfil.sys", "swapfile.sys", "dumpstack.log",
    "dumpstack.log.tmp", "desktop.ini", "thumbs.db", "amtag.bin",
}

CAT_MAP = {
    "图片": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".tiff", ".tif", ".heic", ".svg", ".ico", ".raw", ".cr2", ".nef", ".arw", ".dng", ".psd"},
    "视频": {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".ts", ".m4v", ".mpg", ".mpeg", ".3gp", ".webm", ".rmvb"},
    "音频": {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma", ".ape", ".opus"},
    "文档": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".csv", ".rtf", ".xmind", ".vcf"},
    "压缩包": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "安装包": {".exe", ".msi", ".apk", ".appx"},
    "数据": {".json", ".xml", ".db", ".sqlite", ".yaml", ".yml", ".ini", ".cfg"},
    "代码": {".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp", ".go", ".rs", ".sh", ".bat", ".ps1", ".ipynb"},
}


def category_of(ext):
    e = ext.lower()
    for cat, exts in CAT_MAP.items():
        if e in exts:
            return cat
    return "其他"


def system_drive():
    return os.environ.get("SystemDrive", "C:").rstrip("\\:").upper()


def logical_drives():
    out = []
    for letter in string.ascii_uppercase:
        d = f"{letter}:\\"
        if os.path.exists(d):
            try:
                os.scandir(d).close()
                out.append(letter)
            except PermissionError:
                pass
    return out


class DedupEngine:
    def __init__(self, data_dir):
        self.dir = Path(data_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.cache_path = self.dir / "cache.json"
        self.history_path = self.dir / "history.json"
        self.cache = self._load(self.cache_path, {})
        self.history = self._load(self.history_path, [])

    @staticmethod
    def _load(p, default):
        try:
            return json.loads(Path(p).read_text(encoding="utf-8"))
        except Exception:
            return default

    @staticmethod
    def _save(p, obj):
        Path(p).write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8")

    # ---------- 哈希 ----------
    @staticmethod
    def _partial(path, size):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            h.update(f.read(CHUNK))
            f.seek(max(0, size - CHUNK))
            h.update(f.read(CHUNK))
        h.update(str(size).encode())
        return h.hexdigest()

    @staticmethod
    def _full(path):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                b = f.read(1024 * 1024)
                if not b:
                    break
                h.update(b)
        return h.hexdigest()

    def _signature(self, path, size):
        """返回 (sig, is_full)。小文件(≤128KB)部分哈希即全量"""
        try:
            if size <= CHUNK * 2:
                with open(path, "rb") as f:
                    return "F:" + hashlib.sha256(f.read()).hexdigest(), True
            if size <= 1024 * 1024 * 8:
                return "P:" + self._partial(path, size), False
            # >8MB: 部分哈希截断到1KB首尾, 进一步省IO
            h = hashlib.sha256()
            with open(path, "rb") as f:
                h.update(f.read(1024))
                f.seek(max(0, size - 1024))
                h.update(f.read(1024))
            h.update(str(size).encode())
            return "P:" + h.hexdigest(), False
        except OSError:
            return f"E:{path}", False

    # ---------- 扫描 ----------
    def run(self, scopes, incremental=True, exclude_system=True,
            progress_cb=None, log_cb=None, cancel=None, on_group=None):
        t0 = time.time()
        log_cb = log_cb or (lambda m: None)
        progress_cb = progress_cb or (lambda v: None)
        cancel = cancel or {"stop": False}
        sysd = system_drive()
        empty = {"stats": {}, "groups": [], "scan_id": None}

        roots = []
        for s in scopes:
            s = os.path.normpath(s)
            if not os.path.exists(s):
                log_cb(f"⚠ 范围不存在，跳过: {s}")
                continue
            if exclude_system and len(s) <= 3 and s.upper().startswith(sysd):
                log_cb(f"🛡 系统盘 {s} 已自动排除（勾选'扫描系统盘'可强制包含）")
                continue
            roots.append(s)
        if not roots:
            return empty

        # 1) 游走
        log_cb(f"📂 扫描 {len(roots)} 个位置: {', '.join(roots)}")
        all_files = []
        excluded = 0
        for root in roots:
            for base, dirs, files in os.walk(root):
                if cancel["stop"]:
                    log_cb("⏹ 已取消"); return empty
                dirs[:] = [d for d in dirs if d.lower() not in SYSTEM_DIR_EXCLUDE]
                for f in files:
                    if f.lower() in SYSTEM_FILE_EXCLUDE:
                        excluded += 1
                        continue
                    p = os.path.join(base, f)
                    try:
                        st = os.stat(p)
                    except OSError:
                        continue
                    all_files.append((p, st.st_size, int(st.st_mtime)))
                    if len(all_files) % 2000 == 0:
                        log_cb(f"📂 已发现 {len(all_files)} 文件…")
                        progress_cb(min(0.1, len(all_files) / 200000))
        log_cb(f"📂 共 {len(all_files)} 个文件（跳过系统文件 {excluded} 个）")
        meta = {p: (sz, mt) for p, sz, mt in all_files}

        # 2) 体积分组
        by_size = {}
        for p, sz, _ in all_files:
            if sz > 0:
                by_size.setdefault(sz, []).append(p)
        cand = [(sz, ps) for sz, ps in by_size.items() if len(ps) > 1]
        cand_n = sum(len(ps) for _, ps in cand)
        log_cb(f"🔗 体积重嫌疑 {cand_n} 个文件（{len(cand)} 个体积组）")

        # 3) 部分哈希（增量跳过）
        partial_map = {}
        done = 0
        cache_dirty = False
        for sz, paths in cand:
            for p in paths:
                if cancel["stop"]:
                    log_cb("⏹ 已取消"); return empty
                done += 1
                if done % 30 == 0 or done == cand_n:
                    progress_cb(0.1 + 0.9 * done / max(cand_n, 1))
                cur_sz, cur_mt = meta[p]
                cached = self.cache.get(p)
                if incremental and cached and cached[0] == cur_sz and cached[1] == cur_mt:
                    sig = cached[2]
                else:
                    sig, _ = self._signature(p, sz)
                    self.cache[p] = [cur_sz, cur_mt, sig]
                    cache_dirty = True
                partial_map.setdefault(sig, []).append(p)

        # 4) 成组: F:哈希直接确认; P:碰撞组全量确认后即刻吐出（流式）
        def build_group(sig, paths):
            sz = meta[paths[0]][0]
            recs = []
            for p in paths:
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                name = os.path.basename(p)
                recs.append({
                    "path": p, "name": name, "ext": os.path.splitext(name)[1],
                    "folder": os.path.dirname(p), "drive": os.path.splitdrive(p)[0] + "\\",
                    "size": st.st_size, "ctime": int(st.st_ctime), "mtime": int(st.st_mtime),
                    "category": category_of(os.path.splitext(name)[1]),
                    "redundant": False, "hash": sig[3:19],
                })
            recs.sort(key=lambda r: (len(r["path"]), r["path"]))
            for i, r in enumerate(recs):
                r["redundant"] = i > 0
            return {"sig": sig, "size": sz, "count": len(recs),
                    "category": recs[0]["category"], "files": recs}

        groups = []
        on_group = on_group or (lambda g: None)
        for sig, paths in partial_map.items():
            if cancel["stop"]:
                log_cb("⏹ 已取消"); return empty
            if sig.startswith("F:"):
                if len(paths) >= 2:
                    g = build_group(sig, paths)
                    groups.append(g); on_group(g)          # ← 边扫边吐
            elif len(paths) > 1:
                log_cb(f"🔬 {len(paths)} 个文件部分碰撞，全量确认…")
                full_tmp = {}
                for p in paths:
                    full = "F:" + self._full(p)
                    self.cache[p] = [*self.cache.get(p, [0, 0])[:2], full]
                    cache_dirty = True
                    full_tmp.setdefault(full, []).append(p)
                for fp, fps in full_tmp.items():
                    if len(fps) >= 2:
                        g = build_group(fp, fps)
                        groups.append(g); on_group(g)      # ← 边扫边吐
        progress_cb(1.0)

        # 6) 历史落档
        scan_id = time.strftime("%Y%m%d_%H%M%S")
        redundant = sum(g["count"] - 1 for g in groups)
        reclaim = sum(g["size"] * (g["count"] - 1) for g in groups)
        stats = {"files": len(all_files), "groups": len(groups),
                 "redundant": redundant, "reclaim_bytes": reclaim,
                 "duration": round(time.time() - t0, 1),
                 "mode": "增量" if incremental else "全量重扫"}
        self.history.append({"id": scan_id, "time": scan_id,
                             "scopes": roots, **stats})
        self._save(self.history_path, self.history[-100:])
        (self.dir / f"results_{scan_id}.json").write_text(
            json.dumps({"stats": stats, "groups": groups}, ensure_ascii=False), encoding="utf-8")
        if cache_dirty:
            self._save(self.cache_path, self.cache)
        log_cb(f"✅ 完成: {len(groups)} 组 / 冗余 {redundant} / "
               f"可释放 {reclaim/1024/1024:.1f}MB / 耗时 {stats['duration']}s（{stats['mode']}）")
        return {"stats": stats, "groups": groups, "scan_id": scan_id}

    # ---------- 删除 ----------
    def delete_redundant(self, paths, groups):
        sig_of = {}
        for g in groups:
            for f in g["files"]:
                sig_of[f["path"]] = (g["sig"], f["size"])
        deleted, skipped, freed = [], [], 0
        for p in paths:
            info = sig_of.get(p)
            if not info:
                skipped.append({"path": p, "reason": "不在结果中"}); continue
            sig, size = info
            if not os.path.exists(p):
                skipped.append({"path": p, "reason": "已不在"}); continue
            alive = any(q != p and sig_of.get(q, ("", 0))[0] == sig
                        and os.path.exists(q) and os.path.getsize(q) == size
                        for q in sig_of)
            if not alive:
                skipped.append({"path": p, "reason": "同组无存活副本，拒绝"}); continue
            try:
                os.remove(p)
                deleted.append(p); freed += size
            except OSError as e:
                skipped.append({"path": p, "reason": str(e)})
        return deleted, skipped, freed


if __name__ == "__main__":
    import sys
    eng = DedupEngine(Path(__file__).parent / "dedup_data")
    r = eng.run(sys.argv[1:] or [r"D:\Coding\app\SafeCleanerPro\docs"],
                incremental=True, log_cb=print)
    print(r["stats"])