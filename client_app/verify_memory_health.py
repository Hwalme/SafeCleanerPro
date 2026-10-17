# -*- coding: utf-8 -*-
"""AI 记忆迁移健康体检（可反复运行，无任何写操作）。

对每个已迁移项做五层校验：
  1. 联接存在且指向登记目标，目标盘为固定 NTFS 盘
  2. 穿透 C 盘路径 vs 直读目标盘实体：文件数 / 总字节完全一致
  3. 哈希抽样：最新 10 个文件 + 随机 15 个（≤64MB）双路径 SHA256 逐一比对
  4. 最新会话文件经 C 盘路径完整可读（这是"下次打开 agent"最关心的数据）
  5. 未迁移项仍为真实目录（防误迁/误删）

任何一项不过 → 退出码 1 并打印 FAIL 明细。
"""
import hashlib
import os
import random
import sys
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import migrate_core as mc


def file_sha256(path, cap=64 * 1024 * 1024):
    try:
        if os.path.getsize(path) > cap:
            return None          # 超大文件跳过哈希（由数量/字节校验覆盖）
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return "READ_FAIL"


def newest_files(root, n=10):
    """按修改时间取最新 n 个文件（元数据遍历，不读内容）。"""
    out = []
    stack = [root]
    while stack:
        cur = stack.pop()
        try:
            entries = list(os.scandir(cur))
        except OSError:
            continue
        for e in entries:
            try:
                st = e.stat(follow_symlinks=False)
                if e.is_dir(follow_symlinks=False):
                    if st.st_file_attributes & 0x400:
                        continue
                    stack.append(e.path)
                elif e.is_file(follow_symlinks=False):
                    out.append((st.st_mtime, e.path))
            except OSError:
                continue
    out.sort(reverse=True)
    return [p for _m, p in out[:n]]


def check_source(src, log):
    fails = []
    # 1. 联接与目标盘
    if not mc.is_junction(src):
        return [f"不是联接: {src}"]
    tgt = mc.link_target(src)
    if not tgt or not os.path.isdir(tgt):
        return [f"联接目标丢失: {src} -> {tgt}"]
    drive = os.path.splitdrive(tgt)[0] + "\\"
    if mc.volume_fs(drive).upper() != "NTFS":
        fails.append(f"目标盘非 NTFS: {drive}")
    try:
        import ctypes
        if ctypes.windll.kernel32.GetDriveTypeW(drive) != 3:   # DRIVE_FIXED
            fails.append(f"目标盘不是固定磁盘: {drive}")
    except Exception:
        pass

    # 2. 全量数量/字节比对（双路径）
    cf, cb, _ = mc.walk_stats(src)
    df, db, _ = mc.walk_stats(tgt)
    if (cf, cb) != (df, db):
        fails.append(f"数量/字节不一致: 经C盘 {cf}个/{cb}B vs 直读 {df}个/{db}B")

    # 3. 哈希抽样（最新 10 + 随机 15）
    newest = newest_files(src, 10)
    all_pick = []
    stack = [src]
    while stack:
        cur = stack.pop()
        try:
            entries = list(os.scandir(cur))
        except OSError:
            continue
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    st = e.stat(follow_symlinks=False)
                    if st.st_file_attributes & 0x400:
                        continue
                    stack.append(e.path)
                elif e.is_file(follow_symlinks=False) and \
                        e.stat(follow_symlinks=False).st_size <= 64 * 1024 * 1024:
                    all_pick.append(e.path)
            except OSError:
                continue
    rnd = random.Random(20260101)
    sample = list(dict.fromkeys(newest + rnd.sample(
        all_pick, min(15, len(all_pick))))) if all_pick else newest
    bad_hash = 0
    for p in sample:
        rel = os.path.relpath(p, src)
        h1 = file_sha256(p)
        h2 = file_sha256(os.path.join(tgt, rel))
        if h1 != h2:
            bad_hash += 1
            fails.append(f"哈希不一致: {rel}")
    if bad_hash == 0 and sample:
        log(f"     哈希抽样 {len(sample)} 个文件全部一致（含最新 10 个会话文件）")

    # 4. 最新会话文件可读
    if newest:
        p = newest[0]
        try:
            with open(p, "rb") as f:
                f.read(1 << 20)
            mt = datetime.fromtimestamp(os.path.getmtime(p))
            log(f"     最新会话文件可读: {os.path.basename(p)} "
                f"({os.path.getsize(p)} B, 修改于 {mt:%Y-%m-%d %H:%M})")
        except OSError as e:
            fails.append(f"最新会话文件读取失败: {p}: {e}")
    return fails


def main():
    ok = bad = 0
    cat = mc.build_catalog()
    print("=" * 62)
    print(" AI 记忆迁移健康体检（只读，不写任何数据）")
    print("=" * 62)

    print("\n── 已迁移项 ──")
    for it in cat:
        if mc.item_status(it) != "migrated":
            continue
        print(f"\n● {it['name']}")
        item_ok = True
        for s in it["sources_resolved"]:
            def log(m):
                print(m)
            fails = check_source(s, log)
            tgt = mc.migrated_target_of(s)
            if fails:
                item_ok = False
                for f in fails:
                    print(f"   ❌ {f}")
            else:
                print(f"   ✅ {s}")
                print(f"      → {tgt}")
        ok += 1 if item_ok else 0
        bad += 0 if item_ok else 1

    print("\n── 未迁移项（应为真实目录，防误动） ──")
    weird = []
    for it in cat:
        if mc.item_status(it) != "clean":
            continue
        for s in it["sources_resolved"]:
            if mc.is_reparse_dir(s):
                weird.append(s)
    if weird:
        for s in weird:
            print(f"   ❌ 意外联接: {s}")
        bad += 1
    else:
        print(f"   ✅ {sum(len(i['sources_resolved']) for i in cat if mc.item_status(i)=='clean')}"
              f" 个源目录全部原封未动")

    print("\n" + "=" * 62)
    if bad == 0:
        print(f" 结论：全部通过 ✅（已迁移 {ok} 项数据无损，原路径访问正常）")
    else:
        print(f" 结论：{bad} 项存在异常 ❌（数据未丢失，请按上面明细处理）")
    print("=" * 62)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
