# -*- coding: utf-8 -*-
"""
dedup_server.py — 查重台本地服务
=================================
GET  /             → 查重台.html
GET  /api/index    → dedup_index.json
GET  /api/open?path=   → 用系统默认程序打开文件（仅限索引内路径）
GET  /api/reveal?path= → 资源管理器定位文件
每次 open/reveal 写审计日志。端口 8910。
"""
import json
import subprocess
import time
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs, unquote

# 目录自定位：本文件位于 <ROOT>/scripts/，因此 ROOT 是它的上一级。
# 这样整个 Organization 目录被移动/改名后无需再改这里。
ROOT = Path(__file__).resolve().parent.parent
INDEX_PATH = ROOT / "reports" / "dedup_index.json"
PAGE_PATH = ROOT / "reports" / "查重台.html"
AUDIT = ROOT / "audit" / "operations"

_paths = set()
_files = []


def load_index():
    global _paths, _files
    data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    _files = data["files"]
    _paths = {f["path"] for f in _files}
    return data


def delete_batch(paths):
    """逐条校验：在索引内 + 存活 + 大小一致 + 同组有存活保留副本。返回结果与 manifest。"""
    global _files
    deleted, skipped, freed = [], [], 0
    by_path = {f["path"]: f for f in _files}
    for p in paths:
        rec = by_path.get(p)
        if rec is None:
            skipped.append({"path": p, "reason": "不在索引"}); continue
        if not os.path.exists(p):
            skipped.append({"path": p, "reason": "文件已不在"}); continue
        try:
            if os.path.getsize(p) != rec["size"]:
                skipped.append({"path": p, "reason": "大小已变化"}); continue
        except OSError as e:
            skipped.append({"path": p, "reason": str(e)}); continue
        twins = [f["path"] for f in _files
                 if f["group"] == rec["group"] and f["path"] != p and f["size"] == rec["size"]]
        if not any(os.path.exists(t) for t in twins):
            skipped.append({"path": p, "reason": "同组无存活保留副本，拒绝删"}); continue
        try:
            os.remove(p)
        except OSError as e:
            skipped.append({"path": p, "reason": str(e)}); continue
        deleted.append(p)
        freed += rec["size"]
    stamp = time.strftime("%Y%m%d_%H%M%S")
    manifest = {"kind": "dedup-ui-delete", "executed": time.strftime("%Y-%m-%d %H:%M:%S"),
                "deleted": deleted, "skipped": skipped, "freed_bytes": freed}
    (ROOT / "plans" / f"{stamp}_dedup_ui_delete.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # 同步内存索引，防同一批里连删两份
    gone = set(deleted)
    _files = [f for f in _files if f["path"] not in gone]
    _paths = {f["path"] for f in _files}
    return {"deleted": deleted, "skipped": skipped, "freed": freed}


def log(action, path):
    AUDIT.mkdir(parents=True, exist_ok=True)
    fp = AUDIT / f"{time.strftime('%Y-%m-%d')}_dedup_ui.json"
    lines = json.loads(fp.read_text(encoding="utf-8")) if fp.exists() else []
    lines.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": action, "path": path})
    fp.write_text(json.dumps(lines, ensure_ascii=False, indent=1), encoding="utf-8")


class H(BaseHTTPRequestHandler):
    def _send(self, code, body: bytes, ctype="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        qs = parse_qs(u.query)
        try:
            if u.path == "/":
                self._send(200, PAGE_PATH.read_bytes(), "text/html; charset=utf-8")
            elif u.path == "/api/index":
                data = INDEX_PATH.read_bytes()
                self._send(200, data)
            elif u.path == "/api/open":
                p = unquote(qs.get("path", [""])[0])
                if p not in _paths:
                    self._send(403, b'{"err":"path not in index"}')
                    return
                log("open", p)
                os.startfile(p)
                self._send(200, b'{"ok":true}')
            elif u.path == "/api/reveal":
                p = unquote(qs.get("path", [""])[0])
                if p not in _paths:
                    self._send(403, b'{"err":"path not in index"}')
                    return
                log("reveal", p)
                subprocess.Popen(["explorer", "/select,", p])
                self._send(200, b'{"ok":true}')
            else:
                self._send(404, b'{"err":"not found"}')
        except Exception as e:
            self._send(500, json.dumps({"err": str(e)}).encode("utf-8"))

    def do_POST(self):
        try:
            u = urlparse(self.path)
            if u.path != "/api/delete":
                self._send(404, b'{"err":"not found"}'); return
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length).decode("utf-8"))
            paths = [str(p) for p in body.get("paths", [])]
            if not paths:
                self._send(400, b'{"err":"empty paths"}'); return
            result = delete_batch(paths)
            for p in result["deleted"]:
                log("delete", p)
            for s in result["skipped"]:
                log("delete-skip", f'{s["path"]} ({s["reason"]})')
            self._send(200, json.dumps(result, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self._send(500, json.dumps({"err": str(e)}).encode("utf-8"))

    def log_message(self, *a):
        pass


def main():
    data = load_index()
    s = data["stats"]
    print(f"[dedup台] 索引: {s['files']} 文件 / {s['groups']} 组 / "
          f"可释放 {s['reclaim_bytes']/1024/1024/1024:.2f}GB")
    print("[dedup台] http://127.0.0.1:8910")
    ThreadingHTTPServer(("127.0.0.1", 8910), H).serve_forever()


if __name__ == "__main__":
    main()