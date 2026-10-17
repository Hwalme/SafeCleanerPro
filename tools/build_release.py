"""Fail-closed Windows native release builder; never falls back to bytecode."""
import argparse
import ast
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "client_app"
sys.path.insert(0, str(APP))
from secure_rules import canonical_json, load_dataset, open_bundle, seal_bundle

MODULES = (
    "main", "brand_ui", "ui_theme", "cleaner_core", "cleaner_rules",
    "deep_cache", "deep_ui", "library_rules", "trace_rules_360", "dedup_core",
    "rules_extra",
    "dedup_ui", "migrate_core", "migrate_ui", "hwid_utils", "lock_store",
    "win_icons", "secure_rules", "release_entry",
)
FORBIDDEN_NAMES = {
    "rules_library.json", "trace_rules.json", "app_rule_mapping.json",
    "clean_categories.json", "trace_categories.json", "junk_file_extensions.txt",
    "_release_config.py", "private.pem", "signing-key.dpapi",
}


def key_path():
    local = os.environ.get("LOCALAPPDATA")
    if os.name != "nt" or not local:
        raise RuntimeError("Release signing requires Windows DPAPI")
    return Path(local) / "SafeCleanerPro" / "release-signing" / "signing-key.dpapi"


class DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def dpapi(data, *, decrypt=False):
    """Current-user DPAPI; no plaintext signing private key is written."""
    if os.name != "nt":
        raise RuntimeError("DPAPI requires Windows")
    buf = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    source, target = DataBlob(len(data), buf), DataBlob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(DataBlob), ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                         wintypes.DWORD, ctypes.POINTER(DataBlob)]
    function.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel.LocalFree(target.pbData)


def init_key():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    path = key_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    private = Ed25519PrivateKey.generate()
    raw = private.private_bytes(serialization.Encoding.Raw,
                                serialization.PrivateFormat.Raw,
                                serialization.NoEncryption())
    protected = dpapi(raw)
    with path.open("xb") as stream:
        stream.write(protected)
    print("Created current-user DPAPI signing key:", path)


def signing_key():
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    path = key_path()
    if not path.is_file():
        raise RuntimeError("Signing key missing. Run: python tools/build_release.py init-key")
    return Ed25519PrivateKey.from_private_bytes(dpapi(path.read_bytes(), decrypt=True))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_source_inventory(app=APP, modules=MODULES):
    """Do not silently omit local modules introduced by concurrent/future work."""
    allowed = set(modules) | {"_release_config"}
    missing = set()
    for name in modules:
        tree = ast.parse((app / (name + ".py")).read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports = [node.module.split(".")[0]]
            else:
                continue
            for imported in imports:
                if imported not in allowed and ((app / (imported + ".py")).is_file()
                                                or (app / imported / "__init__.py").is_file()):
                    missing.add(imported)
    if missing:
        raise RuntimeError("Local modules need protected-release integration: " + ", ".join(sorted(missing)))


def prepare():
    from cryptography.hazmat.primitives import serialization

    verify_source_inventory()
    private = signing_key()
    public = private.public_key().public_bytes(serialization.Encoding.Raw,
                                               serialization.PublicFormat.Raw)
    build_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:12]
    base = ROOT / "build" / "protected" / build_id
    stage = base / "stage"
    stage.mkdir(parents=True, exist_ok=False)
    for name in MODULES:
        shutil.copy2(APP / (name + ".py"), stage)
    for name in ("logo.ico", "splash_logo.png"):
        shutil.copy2(APP / name, stage)
    for sub in ("winapp2", "bleachbit", "qqpcmgr", "dism"):
        source_dir = APP / "rules" / sub
        if source_dir.is_dir():
            for source in source_dir.rglob("*.json"):
                target = stage / "rules" / sub / source.relative_to(source_dir)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    assets = APP / "assets"
    for source in assets.rglob("*"):
        if source.is_file() and source.suffix.lower() in {".png", ".jpg", ".jpeg", ".ico", ".webp"}:
            target = stage / "assets" / source.relative_to(assets)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    for name, source in (("LICENSE.txt", ROOT / "LICENSE"),
                         ("THIRD_PARTY_RULES.md", ROOT / "docs" / "THIRD_PARTY_RULES.md")):
        shutil.copy2(source, stage / name)
    bundle = {name: load_dataset(name) for name in ("library", "trace")}
    aes_key = os.urandom(32)
    packed = seal_bundle(bundle, aes_key, private, build_id)
    pack_hash = hashlib.sha256(packed).hexdigest()
    if open_bundle(packed, aes_key, public, build_id, pack_hash) != bundle:
        raise RuntimeError("Rule pack round-trip failed")
    (stage / "rules.scpack").write_bytes(packed)
    (stage / "_release_config.py").write_text(
        "# Generated build material. Never ship as source.\n"
        f"BUILD_ID = {build_id!r}\nAES_KEY = {aes_key!r}\n"
        f"PUBLIC_KEY = {public!r}\nPACK_SHA256 = {pack_hash!r}\n", encoding="utf-8")
    manifest = {"build_id": build_id, "mode": "prepared-only", "pack_sha256": pack_hash,
                "publisher_key_sha256": hashlib.sha256(public).hexdigest(),
                "sources": {p.name: sha256(p) for p in sorted(stage.glob("*.py"))
                            if p.name != "_release_config.py"},
                "rule_sources": {"rules_library.json": sha256(APP / "rules_library.json"),
                                 "trace_rules.json": sha256(APP / "rules/trace_rules.json")}}
    (base / "build-info.json").write_bytes(canonical_json(manifest))
    print("Prepared (NOT a distributable release):", base, flush=True)
    return base, stage, manifest


def audit_distribution(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise RuntimeError("Compiled distribution is missing")
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        if (path.name.lower() in FORBIDDEN_NAMES or
                path.suffix.lower() in {".py", ".pyc", ".pyo", ".pdb", ".pem", ".key", ".dpapi"}):
            raise RuntimeError("Forbidden release material: " + str(path.relative_to(directory)))
    if not (directory / "rules.scpack").is_file():
        raise RuntimeError("Encrypted rule pack missing from distribution")
    if not (directory / "SafeCleanerPro.exe").is_file():
        raise RuntimeError("Compiled executable missing from distribution")


def compiler_command(stage, output):
    args = [sys.executable, "-m", "nuitka", "--mode=standalone", "--mingw64",
            "--assume-yes-for-downloads", "--jobs=2", "--enable-plugin=tk-inter",
            "--include-package=customtkinter", "--include-package-data=customtkinter",
            "--python-flag=isolated", "--python-flag=no_docstrings",
            "--windows-console-mode=disable", "--windows-icon-from-ico=logo.ico",
            "--output-filename=SafeCleanerPro.exe", "--output-dir=" + str(output),
            "--report=" + str(output.parent / "compilation-report.xml")]
    for name in MODULES:
        if name != "release_entry":
            args.append("--include-module=" + name)
    args.append("--include-module=_release_config")
    for name in ("rules.scpack", "logo.ico", "splash_logo.png", "LICENSE.txt", "THIRD_PARTY_RULES.md"):
        args.append(f"--include-data-files={name}={name}")
    if (stage / "assets").is_dir():
        args.append("--include-data-dir=assets=assets")
    args.append("release_entry.py")
    return args


def audit_compilation(report):
    modules = {node.attrib.get("name"): node.attrib.get("kind")
               for node in ET.parse(report).getroot().findall("module")}
    for name in (*MODULES[:-1], "_release_config"):
        if modules.get(name) != "CompiledPythonModule":
            raise RuntimeError("Core module was not compiled: " + name)


def verify_executable(dist):
    """Positive and negative acceptance against the actual native program."""
    exe = str(dist / "SafeCleanerPro.exe")
    path = dist / "rules.scpack"
    packed = path.read_bytes()
    with tempfile.TemporaryDirectory(prefix="scpro_release_check_") as temp:
        # A hostile working directory must never supply replacement rules.
        Path(temp, "rules_library.json").write_text('{"winapp2":[],"dismpp":[]}')
        Path(temp, "trace_rules.json").write_text("[]")
        subprocess.run([exe, "--self-test"], cwd=temp, check=True, timeout=120)
        try:
            damaged = bytearray(packed)
            damaged[-1] ^= 1
            path.write_bytes(damaged)
            result = subprocess.run([exe, "--self-test"], cwd=temp, timeout=120)
            if result.returncode != 2:
                raise RuntimeError("Native program accepted a damaged rule pack")
            path.unlink()
            result = subprocess.run([exe, "--self-test"], cwd=temp, timeout=120)
            if result.returncode != 2:
                raise RuntimeError("Native program accepted missing rules")
        finally:
            path.write_bytes(packed)
        subprocess.run([exe, "--self-test"], cwd=temp, check=True, timeout=120)


def finish_build(base, manifest):
    dist = base / "native" / "release_entry.dist"
    audit_compilation(base / "compilation-report.xml")
    audit_distribution(dist)
    verify_executable(dist)
    manifest.update(mode="nuitka-standalone", self_test="passed",
                    negative_self_tests="tampered/missing/cwd-injection rejected",
                    exe_sha256=sha256(dist / "SafeCleanerPro.exe"))
    (base / "build-info.json").write_bytes(canonical_json(manifest))
    archive = shutil.make_archive(str(base / "SafeCleanerPro-protected"), "zip", dist)
    print("Verified release:", archive)
    print("Verified release:", archive)

    # —— 交付：刷新 client_app/latest（唯一最新版入口，防开错版本）——
    dist_dir = None
    for cand in sorted(Path(ROOT, "build", "protected").glob(
            "*/native/release_entry.dist"), key=lambda p: p.stat().st_mtime,
            reverse=True):
        exe = cand / "SafeCleanerPro.exe"
        if exe.is_file():
            dist_dir = cand
            break
    if dist_dir:
        latest = ROOT / "client_app" / "latest"

        def _onerr(func, path, exc):
            import stat as _stat
            try:
                os.chmod(path, _stat.S_IWRITE)
                func(path)
            except OSError:
                pass
        if latest.exists():
            shutil.rmtree(latest, onerror=_onerr)
        latest.mkdir(parents=True, exist_ok=True)
        for item in dist_dir.rglob("*"):
            target = latest / item.relative_to(dist_dir)
            if item.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
        version = "unknown"
        m = re.search(r'CURRENT_VERSION\s*=\s*"([0-9.]+)"',
                      (APP / "main.py").read_text(encoding="utf-8"))
        if m:
            version = m.group(1)
        (latest / "build_info.txt").write_text(
            "version = " + version + chr(10) +
            "built = " + datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ") + chr(10),
            encoding="utf-8")
        print("Delivered latest:", latest)
    print("Keep stage/native build sources private. Distribute ONLY this ZIP.")


def build():
    if importlib.util.find_spec("nuitka") is None:
        raise RuntimeError("Nuitka missing. Install tools/requirements-release.txt first")
    base, stage, manifest = prepare()
    subprocess.run(compiler_command(stage, base / "native"), cwd=stage, check=True)
    finish_build(base, manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("init-key", "prepare", "build"))
    args = parser.parse_args()
    try:
        {"init-key": init_key, "prepare": prepare, "build": build}[args.action]()
    except (OSError, RuntimeError, subprocess.SubprocessError, ValueError, SyntaxError, ET.ParseError) as exc:
        print("Protected release STOPPED:", exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
