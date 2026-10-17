# -*- coding: utf-8 -*-
"""migrate_core 冒烟测试（无 UI，全部在临时沙盒内进行，不碰真实用户目录）。

用例：
  A. walk_stats / verify_same 基础统计
  B. 正常迁移：联接生效、穿透可读、C 盘备份清理、manifest 入账
  C. 双源项：第二源被锁定 → 整体回滚，第一源恢复原位，数据无损
  D. 取消：cancel() 立即中止 → 源原封不动
  E. 迁回：真实目录回到原位，目标盘数据清除，manifest 移除
  F. 状态机：clean → migrated → (迁回) clean
  G. 中文 + 空格路径（源与目标都含，默认目标根即中文）
  H. 跨盘迁移（源 C: → 另一固定盘；机器无第二固定盘则跳过）
  I. 非 NTFS 目标盘拒绝（monkeypatch volume_fs）
  J. 目标与已迁移条目重叠 → 拒绝且源无损
"""
import json
import os
import shutil
import sys
import tempfile
import time
import traceback

import migrate_core as mc

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print(f"  [PASS] {name}")
    else:
        FAIL.append((name, detail))
        print(f"  [FAIL] {name}  {detail}")


def make_tree(root, n_files=40):
    """造一棵假记忆树：嵌套目录 + 随机内容文件 + 只读文件 + 空目录。"""
    import random
    rnd = random.Random(42)
    total = 0
    for i in range(n_files):
        sub = os.path.join(root, f"proj{i % 3}", f"sub{i % 2}")
        os.makedirs(sub, exist_ok=True)
        p = os.path.join(sub, f"f{i}.bin")
        data = bytes(rnd.getrandbits(8) for _ in range(100 + i * 37))
        with open(p, "wb") as f:
            f.write(data)
        total += len(data)
    os.makedirs(os.path.join(root, "empty_dir"), exist_ok=True)
    ro = os.path.join(root, "proj0", "readonly.txt")
    ro_data = "readonly"
    with open(ro, "w") as f:
        f.write(ro_data)
    total += len(ro_data.encode())
    os.chmod(ro, 0o444)
    return total


def tree_signature(root):
    """内容签名：relpath -> bytes（穿透真实目录收集）。"""
    sig = {}
    for cur, _dirs, files in os.walk(root):
        for fn in files:
            p = os.path.join(cur, fn)
            rel = os.path.relpath(p, root).lower()
            with open(p, "rb") as f:
                sig[rel] = f.read()
    return sig


def main():
    sandbox = tempfile.mkdtemp(prefix="scp_mig_test_")
    src_a = os.path.join(sandbox, "home", ".claude_like")
    src_b = os.path.join(sandbox, "home", ".codex_like")
    target_root = os.path.join(sandbox, "vault", "migrated")
    os.makedirs(src_a)
    os.makedirs(src_b)
    bytes_a = make_tree(src_a)
    make_tree(src_b, 15)

    # manifest 重定向到沙盒
    manifest_file = os.path.join(sandbox, "move_map.json")
    mc._manifest_path = lambda: manifest_file

    try:
        print("== A. 统计 / 比对 ==")
        f, b, r = mc.walk_stats(src_a)
        check("A1 walk_stats 文件数", f == 41, f"got {f}")   # 40 + readonly
        check("A2 walk_stats 字节数", b == bytes_a, f"got {b} want {bytes_a}")
        check("A3 verify_same 自身一致", mc.verify_same(src_a, src_a) is None)

        print("== B. 正常迁移（单源） ==")
        item = {"id": "claude_code", "name": "Claude Code 会话记忆",
                "sources_resolved": [src_a]}
        logs = []
        sig_before = tree_signature(src_a)
        res = mc.migrate_item(item, target_root,
                              log=logs.append,
                              progress=lambda *a: None)
        check("B1 返回体积", res["bytes"] == bytes_a, str(res))
        check("B2 原路径存在", os.path.isdir(src_a))
        check("B3 原路径已是联接", mc.is_junction(src_a))
        tgt = mc.link_target(src_a)
        check("B4 联接指向目标盘", bool(tgt) and tgt.startswith(
            os.path.normcase(target_root)), str(tgt))
        check("B5 穿透读内容一致", tree_signature(src_a) == sig_before)
        bak = src_a + mc.BACKUP_SUFFIX
        check("B6 C 盘备份已清理", not os.path.lexists(bak))
        check("B7 manifest 已入账", any(
            m["source"].lower() == os.path.normcase(src_a)
            for m in mc.load_manifest()))
        check("B8 状态=migrated", mc.source_status(src_a) == mc.ST_MIGRATED)
        # 联接路径下写入新文件 = 写穿到目标盘
        with open(os.path.join(src_a, "write_through.txt"), "w") as f2:
            f2.write("hello")
        check("B9 联接写入落到目标盘", os.path.isfile(
            os.path.join(tgt, "write_through.txt")))

        print("== C. 第二源锁定 → 整体回滚 ==")
        item2 = {"id": "codex", "name": "Codex",
                 "sources_resolved": [src_b]}
        # 复制 src_b 到 target 后、换位阶段：占住 src_b 内一个文件
        # f5 → proj{i%3}=proj2 / sub{i%2}=sub1；占住一个文件（无
        # FILE_SHARE_DELETE → 阻断父目录原子改名）
        lock_path = os.path.join(src_b, "proj2", "sub1", "f5.bin")
        hold = open(lock_path, "r+b")
        rolled = False
        try:
            mc.migrate_item(item2, target_root, log=logs.append,
                            progress=lambda *a: None)
        except mc.LockedError:
            rolled = True
        except Exception as e:
            print(f"    (非预期异常类型: {type(e).__name__}: {e})")
        finally:
            hold.close()
        check("C1 抛出 LockedError", rolled)
        check("C2 第一源此前未动（本用例单源被锁）",
              not mc.is_junction(src_b) and os.path.isdir(src_b))
        check("C3 锁定源数据完整", len(tree_signature(src_b)) == 16)
        # 锁定阶段发生在复制之后：目标盘应有续传缓存（可接受，非必须断言）

        print("== D. 取消 ==")
        cancelled = {"flag": True}
        try:
            mc.migrate_item(item2, target_root, log=logs.append,
                            progress=lambda *a: None,
                            cancel=lambda: cancelled["flag"])
            check("D1 抛出 MigrateError", False)
        except mc.MigrateError:
            check("D1 抛出 MigrateError", True)
        check("D2 源未动", not mc.is_reparse_dir(src_b))

        print("== E. 释放锁后迁移 + 迁回 ==")
        res2 = mc.migrate_item(item2, target_root, log=logs.append,
                               progress=lambda *a: None)
        check("E1 第二源迁移成功", mc.is_junction(src_b))
        check("E2 穿透读一致", len(tree_signature(src_b)) == 16)
        mc.restore_item(item2, log=logs.append, progress=lambda *a: None)
        check("E3 迁回后原位为真实目录",
              os.path.isdir(src_b) and not mc.is_reparse_dir(src_b))
        check("E4 迁回后内容完整", len(tree_signature(src_b)) == 16)
        check("E5 目标盘数据已清", not os.path.exists(
            os.path.join(target_root, "codex", "00_.codex_like")))
        check("E6 manifest 已移除", not any(
            m["source"].lower() == os.path.normcase(src_b)
            for m in mc.load_manifest()))
        check("E7 状态回到 clean", mc.source_status(src_b) == mc.ST_CLEAN)

        print("== F. restore 后再迁移（regression） ==")
        mc.migrate_item(item2, target_root, log=logs.append,
                        progress=lambda *a: None)
        check("F1 可再次迁移", mc.is_junction(src_b))

        # ------------------------------------------------------------------
        print("== G. 中文 + 空格路径 ==")
        cn_src = os.path.join(sandbox, "AI 记忆 测试", ".codex 中文")
        os.makedirs(cn_src)
        make_tree(cn_src, 8)
        cn_root = os.path.join(sandbox, "目标 盘 AI记忆")
        cn_item = {"id": "cn_case", "name": "中文路径项",
                   "sources_resolved": [cn_src]}
        mc.migrate_item(cn_item, cn_root, log=logs.append,
                        progress=lambda *a: None)
        check("G1 中文路径联接建立", mc.is_junction(cn_src))
        cn_tgt = mc.migrated_target_of(cn_src)
        check("G2 联接指向中文目标", bool(cn_tgt) and
              cn_tgt.startswith(os.path.normcase(cn_root)), str(cn_tgt))
        check("G3 中文路径穿透内容一致", len(tree_signature(cn_src)) == 9)
        with open(os.path.join(cn_src, "写穿.txt"), "w", encoding="utf-8") as f:
            f.write("中文写入")
        check("G4 中文写穿到目标盘", os.path.isfile(
            os.path.join(cn_tgt, "写穿.txt")))
        cn_item_r = dict(cn_item)
        cn_item_r["sources_resolved"] = [cn_src]
        mc.restore_item(cn_item_r, log=logs.append, progress=lambda *a: None)
        # 9 个原始文件 + G4 写穿的「写穿.txt」= 10（写穿数据随迁回完整带回）
        check("G5 中文项迁回无损",
              len(tree_signature(cn_src)) == 10 and not mc.is_reparse_dir(cn_src)
              and os.path.isfile(os.path.join(cn_src, "写穿.txt")))

        # ------------------------------------------------------------------
        print("== H. 跨盘迁移（C: → 另一固定 NTFS 盘） ==")
        x_drives = [d for d in mc.list_target_drives()]
        if x_drives:
            xdrv = x_drives[0]
            x_root = os.path.join(xdrv, f"scp_mig_xvc_{int(time.time())}")
            x_src = os.path.join(sandbox, "home", ".xvc_like")
            os.makedirs(x_src)
            make_tree(x_src, 12)
            x_item = {"id": "xvc", "name": "跨盘项",
                      "sources_resolved": [x_src]}
            mc.migrate_item(x_item, x_root, log=logs.append,
                            progress=lambda *a: None)
            x_tgt = mc.migrated_target_of(x_src)
            check("H1 跨盘联接建立", mc.is_junction(x_src))
            check("H2 联接指向另一盘", bool(x_tgt) and
                  x_tgt.startswith(os.path.normcase(xdrv)), str(x_tgt))
            check("H3 跨盘穿透内容一致", len(tree_signature(x_src)) == 13)
            try:
                mc.restore_item(x_item, log=logs.append,
                                progress=lambda *a: None)
                check("H4 跨盘迁回无损", len(tree_signature(x_src)) == 13)
            finally:
                try:
                    shutil.rmtree(x_root, onerror=lambda f, p, e: None)
                except Exception:
                    pass
        else:
            print("  [SKIP] 无第二固定 NTFS 盘，跳过跨盘用例")

        # ------------------------------------------------------------------
        print("== I. 非 NTFS 目标盘拒绝 ==")
        orig_vfs = mc.volume_fs
        i_src = os.path.join(sandbox, "home", ".exfat_like")
        os.makedirs(i_src)
        make_tree(i_src, 5)
        i_item = {"id": "exfat", "name": "非NTFS项",
                  "sources_resolved": [i_src]}
        mc.volume_fs = lambda p: "exFAT"
        try:
            mc.migrate_item(i_item, os.path.join(sandbox, "vault", "x2"),
                            log=logs.append, progress=lambda *a: None)
            check("I1 抛出 MigrateError", False)
        except mc.MigrateError as e:
            check("I1 抛出 MigrateError", "NTFS" in str(e), str(e))
        finally:
            mc.volume_fs = orig_vfs
        check("I2 源无损未动", not mc.is_reparse_dir(i_src) and
              len(tree_signature(i_src)) == 6)

        # ------------------------------------------------------------------
        print("== J. 目标与已迁移条目重叠拒绝 ==")
        live_tgt = mc.migrated_target_of(src_b)          # F 中 src_b 已迁移
        check("J0 前置：src_b 已迁移", bool(live_tgt))
        j_src = os.path.join(sandbox, "home", ".overlap_like")
        os.makedirs(j_src)
        make_tree(j_src, 5)
        j_item = {"id": "overlap", "name": "重叠项",
                  "sources_resolved": [j_src]}
        try:
            # 目标根压在已迁移条目目标内部 → 必须拒绝
            mc.migrate_item(j_item, live_tgt, log=logs.append,
                            progress=lambda *a: None)
            check("J1 重叠目标被拒绝", False)
        except mc.MigrateError as e:
            check("J1 重叠目标被拒绝", "重叠" in str(e), str(e))
        check("J2 拒绝后源无损", not mc.is_reparse_dir(j_src) and
              len(tree_signature(j_src)) == 6)

        # ------------------------------------------------------------------
        print("== K. 复制间隙源文件消失（AI 工具滚动删 bak 的真实场景） ==")
        k_src = os.path.join(sandbox, "home", ".vanish_like")
        os.makedirs(k_src)
        make_tree(k_src, 10)
        victim = os.path.join(k_src, "proj1", "sub0", "f4.bin")
        orig_copy = mc._copy_file

        def _vanish_copy(src, dst):
            # 复制到指定文件时，先把源删掉（模拟 Codex 正在滚动清理 bak）
            if os.path.abspath(src) == os.path.abspath(victim):
                try:
                    os.remove(victim)
                except OSError:
                    pass
            return orig_copy(src, dst)

        mc._copy_file = _vanish_copy
        try:
            k_item = {"id": "vanish", "name": "消失文件项",
                      "sources_resolved": [k_src]}
            res_k = mc.migrate_item(k_item, target_root, log=logs.append,
                                    progress=lambda *a: None)
            check("K1 消失文件不阻断迁移", mc.is_junction(k_src))
            # 源侧重算 11-1=10 文件（10+readonly-victim），目标应一致
            check("K2 迁移后两侧一致", mc.verify_same(
                mc.migrated_target_of(k_src), k_src) is None)
            check("K3 释放体积=源现值", res_k["bytes"] == mc.walk_stats(k_src)[1])
        finally:
            mc._copy_file = orig_copy
        mc.restore_item({"id": "vanish", "name": "x",
                         "sources_resolved": [k_src]},
                        log=logs.append, progress=lambda *a: None)
        check("K4 迁回正常", not mc.is_reparse_dir(k_src))

        # ------------------------------------------------------------------
        print("== L. VSCode 家族自动发现 ==")
        fake_roaming = os.path.join(sandbox, "fake_roaming")
        for fam in ("Qoder", "Lingma", "Code"):          # Code 与目录册无冲突
            for sub in ("User/History", "User/workspaceStorage", "User/globalStorage"):
                os.makedirs(os.path.join(fake_roaming, fam, *sub.split("/")),
                            exist_ok=True)
        disc = mc._discover_vscode_family(roaming=fake_roaming)
        ids = {d["id"] for d in disc}
        check("L1 发现 Qoder", "vsf_qoder" in ids, str(ids))
        check("L2 发现 Lingma", "vsf_lingma" in ids, str(ids))
        check("L3 发现 VS Code(Copilot 记忆)", "vsf_code" in ids, str(ids))
        q = next(d for d in disc if d["id"] == "vsf_qoder")
        check("L4 Qoder 三记忆子目录", len(q["sources"]) == 3 and
              all("User" in s for s in q["sources"]))
        # build_catalog 集成：monkeypatch ROAMING 指向沙盒
        real_roaming = mc.ROAMING
        mc.ROAMING = fake_roaming
        try:
            cat = mc.build_catalog()
            cat_ids = {x["id"] for x in cat}
            check("L5 build_catalog 含自动发现项", "vsf_qoder" in cat_ids)
            check("L6 目录册显式项不受影响", "claude_code" in cat_ids)
        finally:
            mc.ROAMING = real_roaming

        # dot 目录自动发现
        print("== L2. dot Agent 目录自动发现 ==")
        fake_home = os.path.join(sandbox, "fake_home")
        for d, n in ((".trae-cn", 10), (".tiny", 1)):     # .tiny 低于体量阈值
            dr = os.path.join(fake_home, d)
            os.makedirs(dr, exist_ok=True)
            for i in range(n):
                with open(os.path.join(dr, f"f{i}.dat"), "wb") as f:
                    f.write(b"x" * 100)
        junc = os.path.join(fake_home, ".junc_agent")
        os.makedirs(os.path.join(fake_home, ".real_target"), exist_ok=True)
        mc.create_junction(junc, os.path.join(fake_home, ".real_target"))
        disc2 = mc._discover_dot_agents(home=fake_home)
        ids2 = {d["id"] for d in disc2}
        check("L7 发现 .trae-cn", "dot_trae_cn" in ids2, str(ids2))
        check("L8 低体量目录被过滤", "dot_tiny" not in ids2, str(ids2))
        check("L9 联接目录被跳过", "dot_junc_agent" not in ids2, str(ids2))

        # ------------------------------------------------------------------
        print("== M. 联接改址（retarget） ==")
        # M1 同卷：F1 中 src_b 已迁移至 target_root，改址到沙盒内新位置
        new_loc = os.path.join(sandbox, "vault2")
        res_m = mc.retarget_junction(src_b, os.path.join(new_loc, "codex"),
                                     log=logs.append)
        check("M1 同卷改名零拷贝", res_m["mode"] == "rename", str(res_m))
        check("M2 联接指向新位置", mc.link_target(src_b) ==
              os.path.normcase(os.path.join(new_loc, "codex")),
              str(mc.link_target(src_b)))
        check("M3 穿透内容一致", len(tree_signature(src_b)) == 16)
        check("M4 旧位置已空", not os.path.exists(
            os.path.join(target_root, "codex", "00_.codex_like")))
        check("M5 台账已更新", any(
            m.get("target", "").lower() == os.path.normcase(
                os.path.join(new_loc, "codex"))
            for m in mc.load_manifest()))
        # M2 跨卷：若有第二块固定 NTFS 盘
        x_drives2 = mc.list_target_drives()
        if x_drives2:
            xd = x_drives2[0]
            x_new = os.path.join(xd, f"scp_mig_retgt_{int(time.time())}")
            res_x = mc.retarget_junction(src_b, os.path.join(x_new, "codex"),
                                         log=logs.append)
            check("M6 跨卷复制改址", res_x["mode"] == "copy", str(res_x))
            check("M7 跨卷穿透一致", len(tree_signature(src_b)) == 16)
            check("M8 旧位置已清", not os.path.exists(
                os.path.join(new_loc, "codex")))
            mc.retarget_junction(src_b, os.path.join(new_loc, "codex"),
                                 log=logs.append)   # 改回同卷，便于后续用例
        # M3 非联接源拒绝
        try:
            mc.retarget_junction(src_a + "_nonexistent", new_loc)
            check("M9 非联接拒绝", False)
        except mc.MigrateError:
            check("M9 非联接拒绝", True)
        # M4 目标根持久化
        cfg = os.path.join(new_loc, "cfg")
        mc._target_config_path = lambda: os.path.join(new_loc, "tgt.json")
        mc.save_target_root(cfg)
        check("M10 目标根读写", mc.load_target_root() == cfg)

        # ------------------------------------------------------------------
        print("== N. C 盘常规目录（Shell Folder）迁移 ==")
        # 注册表读写重定向到沙盒字典，绝不碰真实 HKCU
        fake_reg = {}
        reg_writes = []
        orig_read, orig_write = mc.read_shell_folders, mc.write_shell_folder

        def fake_read():
            return dict(fake_reg)

        def fake_write(value_name, path):
            reg_writes.append((value_name, path))
            fake_reg[value_name] = path

        mc.read_shell_folders = fake_read
        mc.write_shell_folder = fake_write
        shell_root = os.path.join(sandbox, "vault3")
        try:
            fake_home = os.path.join(sandbox, "shellhome")
            dt = os.path.join(fake_home, "Desktop")
            dc = os.path.join(fake_home, "Documents")
            fv = os.path.join(fake_home, "Favorites")
            for d in (dt, dc, fv):
                os.makedirs(d)
            make_tree(dt, 6)
            make_tree(dc, 4)
            with open(os.path.join(fv, "link.url"), "w") as f:
                f.write("[InternetShortcut]\nURL=https://example.com\n")

            items_n = mc.build_shell_items(home=fake_home)
            by_id = {x["id"]: x for x in items_n}
            it_dt = by_id["shell_desktop"]
            it_dc = by_id["shell_documents"]
            it_fv = by_id["shell_favorites"]
            check("N0 常规目录册生成", len(items_n) >= 3, str([x["id"] for x in items_n]))
            check("N0.1 标准态=clean",
                  mc.shell_item_status(it_dt)[0] == mc.ST_CLEAN)

            # ---- N1 标准 clean 迁移（桌面） ----
            sig_dt = tree_signature(dt)
            res_n = mc.unify_shell_item(it_dt, shell_root,
                                        log=logs.append, progress=lambda *a: None)
            tgt_dt = os.path.join(shell_root, "桌面")
            check("N1 桌面原路径已是联接", mc.is_junction(dt))
            check("N2 联接指向 桌面 目录",
                  mc.link_target(dt) == os.path.normcase(tgt_dt),
                  str(mc.link_target(dt)))
            check("N3 穿透内容一致", tree_signature(dt) == sig_dt)
            check("N4 目标文件夹自动建立", os.path.isdir(tgt_dt))
            with open(os.path.join(dt, "new_on_desktop.txt"), "w") as f:
                f.write("x")
            check("N5 桌面新文件写穿到目标盘", os.path.isfile(
                os.path.join(tgt_dt, "new_on_desktop.txt")))
            check("N6 未动注册表（非 foreign 不写回）", reg_writes == [])
            check("N7 台账登记为 shell", any(
                m.get("kind") == "shell" and
                m["source"].lower() == os.path.normcase(dt)
                for m in mc.load_manifest()))
            check("N8 状态=migrated",
                  mc.shell_item_status(it_dt)[0] == mc.ST_MIGRATED)
            # 已迁移再迁 → 拒绝
            try:
                mc.unify_shell_item(it_dt, shell_root)
                check("N9 重复迁移拒绝", False)
            except mc.MigrateError:
                check("N9 重复迁移拒绝", True)

            # ---- N10 foreign_dup：360 式他迁 + 两侧重复（文档） ----
            f360 = os.path.join(sandbox, "360move", "Users", "me", "Documents")
            os.makedirs(f360)
            fake_reg[it_dc["value_name"]] = f360        # 模拟 360 改过的注册表
            # C 侧与 D 侧：同名同内容（应去重）+ 同名不同内容（应共存）
            with open(os.path.join(dc, "same.txt"), "w", encoding="utf-8") as f:
                f.write("identical")
            with open(os.path.join(f360, "same.txt"), "w", encoding="utf-8") as f:
                f.write("identical")
            with open(os.path.join(dc, "doc1.txt"), "w", encoding="utf-8") as f:
                f.write("C-side")
            with open(os.path.join(f360, "doc1.txt"), "w", encoding="utf-8") as f:
                f.write("360-side-different")
            check("N10 识别为 foreign_dup",
                  mc.shell_item_status(it_dc)[0] == mc.SST_FOREIGN_DUP)
            reg_writes.clear()
            res_dc = mc.unify_shell_item(it_dc, shell_root,
                                         log=logs.append,
                                         progress=lambda *a: None)
            tgt_dc = os.path.join(shell_root, "文档")
            check("N11 文档原路径已是联接", mc.is_junction(dc))
            check("N12 注册表改回 C 盘原路径",
                  reg_writes == [(it_dc["value_name"],
                                  os.path.abspath(dc))], str(reg_writes))
            check("N13 C 侧内容全部并入",
                  os.path.isfile(os.path.join(tgt_dc, "doc1.txt")) and
                  open(os.path.join(tgt_dc, "doc1.txt")).read() == "C-side")
            check("N14 他处内容也并入（同名共存 doc1(2).txt）",
                  os.path.isfile(os.path.join(tgt_dc, "doc1(2).txt")) and
                  open(os.path.join(tgt_dc, "doc1(2).txt")).read()
                  == "360-side-different")
            check("N15 同名同内容去重（same.txt 仅一份）",
                  os.path.isfile(os.path.join(tgt_dc, "same.txt")) and
                  not os.path.exists(os.path.join(tgt_dc, "same(2).txt")))
            check("N16 合并后穿透统计=文档全部文件",
                  len(tree_signature(dc)) == len(tree_signature(tgt_dc)))
            check("N17 状态回到 migrated",
                  mc.shell_item_status(it_dc)[0] == mc.ST_MIGRATED)
            # 360 旧位置数据保留未删（让用户确认后手动删）
            check("N18 原迁移位置保留", os.path.isfile(
                os.path.join(f360, "doc1.txt")))

            # ---- N19 OneDrive 接管：拒绝迁移 ----
            fake_reg[it_fv["value_name"]] = os.path.join(
                fake_home, "OneDrive", "Favorites")
            check("N19 识别 OneDrive 接管",
                  mc.shell_item_status(it_fv)[0] == mc.SST_ONEDRIVE)
            try:
                mc.unify_shell_item(it_fv, shell_root)
                check("N20 OneDrive 拒绝迁移", False)
            except mc.MigrateError:
                check("N20 OneDrive 拒绝迁移", True)
            fake_reg.pop(it_fv["value_name"])

            # ---- N21 未勾选自动建立 + 目标不存在 → 拒绝 ----
            try:
                mc.unify_shell_item(it_fv, os.path.join(shell_root, "nope"),
                                    auto_mkdir=False)
                check("N21 未勾选自动建立被拒", False)
            except mc.MigrateError:
                check("N21 未勾选自动建立被拒", True)

            # ---- N22 迁回（桌面） ----
            mc.restore_item({"id": it_dt["id"], "name": it_dt["name"],
                             "sources_resolved": [dt]},
                            log=logs.append, progress=lambda *a: None)
            check("N22 桌面迁回为真实目录",
                  os.path.isdir(dt) and not mc.is_reparse_dir(dt))
            check("N23 迁回内容完整（含写穿文件）",
                  len(tree_signature(dt)) == len(sig_dt) + 1 and
                  "new_on_desktop.txt" in tree_signature(dt))
            check("N24 目标盘桌面数据已清", not os.path.exists(tgt_dt))
        finally:
            mc.read_shell_folders = orig_read
            mc.write_shell_folder = orig_write

        # ------------------------------------------------------------------
        print("== O. 子项自定义目标 + 双根配置 ==")
        # O1 AI 项单源 + item_target：精确落到该路径，不自动加子文件夹
        o_src = os.path.join(sandbox, "home", ".custom_tgt_like")
        os.makedirs(o_src)
        make_tree(o_src, 5)
        o_exact = os.path.join(sandbox, "vault4", "我的AI记忆")
        o_item = {"id": "custom_tgt", "name": "自定义目标项",
                  "sources_resolved": [o_src]}
        mc.migrate_item(o_item, os.path.join(sandbox, "vault4"),
                        item_target=o_exact, log=logs.append,
                        progress=lambda *a: None)
        check("O1 精确落位（无 01_ 前缀子目录）",
              mc.is_junction(o_src) and
              mc.link_target(o_src) == os.path.normcase(o_exact),
              str(mc.link_target(o_src)))
        check("O2 穿透内容一致", len(tree_signature(o_src)) == 6)
        mc.restore_item(o_item, log=logs.append, progress=lambda *a: None)

        # O3 多源 + item_target：路径内按 <序号_目录名> 分放
        o_m1 = os.path.join(sandbox, "home", ".multi_a")
        o_m2 = os.path.join(sandbox, "home", ".multi_b")
        os.makedirs(o_m1)
        os.makedirs(o_m2)
        make_tree(o_m1, 3)
        make_tree(o_m2, 3)
        o_multi_root = os.path.join(sandbox, "vault4", "多源目录")
        mc.migrate_item({"id": "multi", "name": "多源项",
                         "sources_resolved": [o_m1, o_m2]},
                        os.path.join(sandbox, "vault4"),
                        item_target=o_multi_root,
                        log=logs.append, progress=lambda *a: None)
        check("O3 多源在自定义路径内分子目录",
              mc.is_junction(o_m1) and mc.is_junction(o_m2) and
              mc.link_target(o_m1) == os.path.normcase(
                  os.path.join(o_multi_root, "00_.multi_a")) and
              mc.link_target(o_m2) == os.path.normcase(
                  os.path.join(o_multi_root, "01_.multi_b")),
              f"{mc.link_target(o_m1)} | {mc.link_target(o_m2)}")
        mc.restore_item({"id": "multi", "name": "x",
                         "sources_resolved": [o_m1, o_m2]},
                        log=logs.append, progress=lambda *a: None)

        # O4 shell 项 target_dir 覆盖：精确路径 + 注册表照常归位
        fake_reg2 = {}
        orig_read2, orig_write2 = mc.read_shell_folders, mc.write_shell_folder
        mc.read_shell_folders = lambda: dict(fake_reg2)
        reg2_writes = []

        def _fw2(name, path):
            reg2_writes.append((name, path))
            fake_reg2[name] = path

        mc.write_shell_folder = _fw2
        try:
            fake_home2 = os.path.join(sandbox, "shellhome2")
            dl = os.path.join(fake_home2, "Downloads")
            os.makedirs(dl)
            make_tree(dl, 4)
            # 模拟他迁（注册表指向别处且有内容）+ 自定义目标：两者叠加
            f360dl = os.path.join(sandbox, "360move", "Downloads")
            os.makedirs(f360dl)
            with open(os.path.join(f360dl, "setup.exe"), "wb") as f:
                f.write(b"from-360")
            it_dl = next(x for x in mc.build_shell_items(home=fake_home2)
                         if x["id"] == "shell_downloads")
            fake_reg2[it_dl["value_name"]] = f360dl
            o_dl = os.path.join(sandbox, "vault5", "我的下载仓")
            mc.unify_shell_item(it_dl, os.path.join(sandbox, "vault5"),
                                target_dir=o_dl, log=logs.append,
                                progress=lambda *a: None)
            check("O4 常规目录精确落位（无「下载」子文件夹）",
                  mc.is_junction(dl) and
                  mc.link_target(dl) == os.path.normcase(o_dl),
                  str(mc.link_target(dl)))
            check("O5 注册表照常改回 C 盘原路径", reg2_writes == [
                (it_dl["value_name"], os.path.abspath(dl))])
            check("O6 穿透统计一致（含他处并入文件）",
                  len(tree_signature(dl)) == 6 and
                  os.path.isfile(os.path.join(dl, "setup.exe")))
        finally:
            mc.read_shell_folders = orig_read2
            mc.write_shell_folder = orig_write2

        # O7 双根配置：旧单 root 兼容为 AI 根；增量保存互不覆盖
        cfgp = os.path.join(sandbox, "cfg", "migrate_target.json")
        mc._target_config_path = lambda: cfgp
        os.makedirs(os.path.dirname(cfgp), exist_ok=True)
        with open(cfgp, "w", encoding="utf-8") as f:
            json.dump({"root": "E:\\temp\\Agent"}, f)
        cfg = mc.load_target_config()
        check("O7 旧 root 兼容为 AI 根",
              cfg["root_ai"] == "E:\\temp\\Agent" and
              cfg["root_shell"] == "")
        mc.save_target_config(root_shell="D:\\C盘迁移\\常规目录")
        cfg = mc.load_target_config()
        check("O8 增量保存（AI 根不被冲掉）",
              cfg["root_ai"] == "E:\\temp\\Agent" and
              cfg["root_shell"] == "D:\\C盘迁移\\常规目录")
        mc.save_target_config(custom_targets={"shell_desktop": "X:\\桌面仓"})
        cfg = mc.load_target_config()
        check("O9 子项目标持久化",
              cfg["custom_targets"].get("shell_desktop") == "X:\\桌面仓"
              and cfg["root_ai"] == "E:\\temp\\Agent")
        check("O10 load_target_root 兼容旧接口",
              mc.load_target_root() == "E:\\temp\\Agent")

    except Exception:
        traceback.print_exc()
        FAIL.append(("UNEXPECTED", traceback.format_exc()))
    finally:
        # 只读文件可能挡删除
        for cur, dirs, files in os.walk(sandbox):
            for fn in files:
                try:
                    os.chmod(os.path.join(cur, fn), 0o666)
                except OSError:
                    pass
        try:
            shutil.rmtree(sandbox, onerror=lambda f, p, e: None)
        except Exception:
            pass

    print(f"\n===== 结果：{len(PASS)} 通过 / {len(FAIL)} 失败 =====")
    for name, detail in FAIL:
        print(f"  FAIL: {name}  {detail}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
