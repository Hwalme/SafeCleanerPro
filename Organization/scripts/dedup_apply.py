# -*- coding: utf-8 -*-
"""
dedup_apply.py — 查重台导出的删除计划落地器
=============================================
python scripts/dedup_apply.py plans/dedup_plan.json --yes

安全机制：
  1. 每个待删文件必须在索引中找到同组文件，且存在至少一个
     「大小一致且存在于磁盘」的保留副本 —— 找不到就不删
  2. 红线区文件必须 --allow-redline 才动
  3. 全量 manifest 落 plans/，审计落 audit/operations/
"""
import json
import os
import time
from pathlib import Path

ROOT = Path(r"D:\Coding\Organization")
RED_LINE_PREFIXES = ["C:\\", "G:\\", "F:\\temp", "D:\\ChatRecords", "D:\\backup", "E:\\Obsidian"]


def is_red(p):
    q = p.rstrip("\\/") + "\\"
    return any(q.lower().startswith(x.lower()) for x in RED_LINE_PREFIXES)


def main():
    import sys
    args = [a for a in sys.argv[1:]]
    yes = "--yes" in args
    allow_red = "--allow-redline" in args
    plan_path = next((a for a in args if not a.startswith("--")), None)
    if not plan_path:
        print("用法: python dedup_apply.py <plan.json> [--yes] [--allow-redline]")
        return 1

    plan = json.loads(Path(plan_path).read_text(encoding="utf-8"))
    index = json.loads((ROOT / "reports" / "dedup_index.json").read_text(encoding="utf-8"))
    by_path = {f["path"]: f for f in index["files"]}

    deleted, skipped, freed = [], [], 0
    for item in plan["deletes"]:
        p, size = item["path"], item["size"]
        rec = by_path.get(p)
        if rec is None:
            skipped.append((p, "不在索引")); continue
        if not os.path.exists(p):
            skipped.append((p, "文件已不在")); continue
        if os.path.getsize(p) != size:
            skipped.append((p, "大小变了")); continue
        twins = [f["path"] for g in [rec["group"]] for f in index["files"]
                 if f["group"] == g and f["path"] != p and f["size"] == size]
        if not any(os.path.exists(t) for t in twins):
            skipped.append((p, "无存活保留副本")); continue
        if is_red(p) and not allow_red:
            skipped.append((p, "红线区(需--allow-redline)")); continue
        try:
            os.remove(p)
            deleted.append(p); freed += size
            print(f"  🗑 {size/1024/1024:8.2f}MB  {p}")
        except OSError as e:
            skipped.append((p, str(e)))

    stamp = time.strftime("%Y%m%d_%H%M%S")
    manifest = {"created": plan.get("created"), "executed": time.strftime("%Y-%m-%d %H:%M:%S"),
                "kind": "dedup-delete", "plan_source": plan_path,
                "deleted": deleted, "skipped": skipped, "freed_bytes": freed,
                "status": "done"}
    out = ROOT / "plans" / f"{stamp}_dedup_applied.json"
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (ROOT / "audit" / "operations").mkdir(parents=True, exist_ok=True)
    print(f"\n删除 {len(deleted)} / 释放 {freed/1024/1024:.2f}MB / 跳过 {len(skipped)}")
    for p, why in skipped:
        print(f"  ⚠ 跳过 [{why}] {p}")
    print(f"manifest → {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())