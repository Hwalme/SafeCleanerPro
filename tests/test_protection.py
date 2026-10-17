import hashlib
import os
from pathlib import Path
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "client_app"))
sys.path.insert(0, str(ROOT / "tools"))
import secure_rules as sr
import build_release as builder
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class ProtectionTests(unittest.TestCase):
    def setUp(self):
        self.private = Ed25519PrivateKey.generate()
        self.public = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.aes = os.urandom(32)
        self.build_id = "test-build"
        self.bundle = {"library": {"sources": {}, "winapp2": [], "dismpp": []}, "trace": []}
        self.packed = sr.seal_bundle(self.bundle, self.aes, self.private, self.build_id)
        sr._BUNDLE = None

    def tearDown(self):
        sr._BUNDLE = None

    def decode(self, packed=None, **overrides):
        packed = self.packed if packed is None else packed
        args = dict(aes_key=self.aes, public_key=self.public, build_id=self.build_id,
                    expected_sha256=hashlib.sha256(packed).hexdigest())
        args.update(overrides)
        return sr.open_bundle(packed, **args)

    def custom_pack(self, compressed, header=None):
        header = sr.canonical_json(header or {"schema": 1, "build_id": self.build_id,
                                              "plain_sha256": "0" * 64})
        aad = sr.MAGIC + struct.pack(">I", len(header)) + header
        nonce = os.urandom(12)
        body = aad + nonce + AESGCM(self.aes).encrypt(nonce, compressed, aad)
        return body + self.private.sign(body)

    def config(self):
        return types.SimpleNamespace(AES_KEY=self.aes, PUBLIC_KEY=self.public,
                                     BUILD_ID=self.build_id,
                                     PACK_SHA256=hashlib.sha256(self.packed).hexdigest())

    def test_roundtrip_and_unicode(self):
        self.bundle["library"]["sources"]["note"] = "测试规则来源"
        packed = sr.seal_bundle(self.bundle, self.aes, self.private, self.build_id)
        self.assertEqual(self.decode(packed), self.bundle)

    def test_random_nonce(self):
        self.assertNotEqual(self.packed, sr.seal_bundle(self.bundle, self.aes, self.private, self.build_id))

    def test_exact_build_digest(self):
        with self.assertRaises(sr.RulePackError):
            self.decode(expected_sha256="0" * 64)

    def test_ciphertext_tamper_even_with_recomputed_digest(self):
        packed = bytearray(self.packed)
        packed[-70] ^= 1
        with self.assertRaises(sr.RulePackError):
            self.decode(bytes(packed))

    def test_signature_tamper(self):
        with self.assertRaises(sr.RulePackError):
            self.decode(self.packed[:-1] + bytes([self.packed[-1] ^ 1]))

    def test_wrong_publisher(self):
        other = Ed25519PrivateKey.generate().public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        with self.assertRaises(sr.RulePackError):
            self.decode(public_key=other)

    def test_wrong_aes_key(self):
        with self.assertRaises(sr.RulePackError):
            self.decode(aes_key=os.urandom(32))

    def test_wrong_build_id(self):
        with self.assertRaises(sr.RulePackError):
            self.decode(build_id="older-release")

    def test_truncation_and_oversize(self):
        for data in (b"", self.packed[:50], self.packed[:-64]):
            with self.subTest(size=len(data)), self.assertRaises(sr.RulePackError):
                self.decode(data)
        with patch.object(sr, "MAX_PACK", 10), self.assertRaises(sr.RulePackError):
            self.decode()

    def test_signed_oversize_header(self):
        body = sr.MAGIC + struct.pack(">I", sr.MAX_HEADER + 1) + b"x" * 100
        with self.assertRaises(sr.RulePackError):
            self.decode(body + self.private.sign(body))

    def test_signed_wrong_schema(self):
        pack = self.custom_pack(zlib.compress(b"{}"), {"schema": 2, "build_id": self.build_id})
        with self.assertRaises(sr.RulePackError):
            self.decode(pack)

    def test_aead_tag_even_with_valid_signature(self):
        body = bytearray(self.packed[:-64])
        body[-1] ^= 1
        body = bytes(body)
        with self.assertRaises(sr.RulePackError):
            self.decode(body + self.private.sign(body))

    def test_bounded_decompression(self):
        pack = self.custom_pack(zlib.compress(b"x" * 4096))
        with patch.object(sr, "MAX_PLAIN", 128), self.assertRaises(sr.RulePackError):
            self.decode(pack)

    def test_compressed_trailing_and_truncated_data(self):
        for compressed in (zlib.compress(b"{}") + b"extra", zlib.compress(b"{}")[:-2]):
            with self.subTest(compressed=compressed), self.assertRaises(sr.RulePackError):
                self.decode(self.custom_pack(compressed))

    def test_signed_content_digest_mismatch(self):
        with self.assertRaises(sr.RulePackError):
            self.decode(self.custom_pack(zlib.compress(b"{}")))

    def test_invalid_rule_contract(self):
        for value in ({}, {"library": [], "trace": []}, {"library": {"sources": {}}, "trace": []}):
            with self.subTest(value=value), self.assertRaises(sr.RulePackError):
                sr.seal_bundle(value, self.aes, self.private, self.build_id)

    def test_real_project_rules_match_after_encryption(self):
        bundle = {name: sr.load_dataset(name) for name in ("library", "trace")}
        packed = sr.seal_bundle(bundle, self.aes, self.private, self.build_id)
        self.assertEqual(self.decode(packed), bundle)

    def test_source_ignores_working_directory_rules(self):
        expected = sr.load_dataset("library")
        old = Path.cwd()
        with tempfile.TemporaryDirectory() as temp:
            try:
                Path(temp, "rules_library.json").write_text('{"attacker":true}')
                os.chdir(temp)
                self.assertEqual(sr.load_dataset("library"), expected)
            finally:
                os.chdir(old)

    def test_compiled_mode_loads_pack_only(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "rules.scpack").write_bytes(self.packed)
            Path(temp, "rules_library.json").write_text('{"attacker":true}')
            with patch.object(sys, "frozen", True, create=True), \
                    patch.object(sys, "_MEIPASS", temp, create=True), \
                    patch.dict(sys.modules, {"_release_config": self.config()}):
                self.assertEqual(sr.load_dataset("library"), self.bundle["library"])

    def test_missing_pack_never_falls_back_to_json(self):
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "rules_library.json").write_text('{"winapp2":[],"dismpp":[]}')
            with patch.object(sys, "frozen", True, create=True), \
                    patch.object(sys, "_MEIPASS", temp, create=True), \
                    patch.dict(sys.modules, {"_release_config": self.config()}), \
                    self.assertRaises(sr.RulePackError):
                sr.load_dataset("library")

    def test_missing_config_never_enters_development_mode(self):
        with patch.object(sys, "frozen", True, create=True), \
                patch.dict(sys.modules, {"_release_config": None}), \
                self.assertRaises(sr.RulePackError):
            sr.load_dataset("trace")

    def test_nuitka_mode_detected_without_sys_frozen(self):
        with patch.dict(sr.__dict__, {"__compiled__": object()}):
            self.assertTrue(sr.release_mode())

    def test_uncompiled_release_entry_rejected(self):
        with self.assertRaises(sr.RulePackError):
            sr.initialise_release()

    def test_adapters_propagate_rule_pack_errors(self):
        import library_rules
        import cleaner_rules
        import deep_cache
        import cleaner_core
        with patch.object(library_rules, "_load_lib", side_effect=sr.RulePackError("tampered")):
            for getter in (library_rules.get_library_apps, cleaner_rules.get_extra_apps,
                           cleaner_core.get_supported_apps):
                with self.subTest(getter=getter.__name__), self.assertRaises(sr.RulePackError):
                    getter()
        with patch("trace_rules_360._load_json", side_effect=sr.RulePackError("tampered")), \
                self.assertRaises(sr.RulePackError):
            deep_cache.to_apps()

    def test_distribution_audit_blocks_source_and_private_files(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "rules.scpack").write_bytes(self.packed)
            (base / "SafeCleanerPro.exe").write_bytes(b"stub")
            builder.audit_distribution(base)
            for name in ("cleaner_core.py", "x.pyc", "x.pem", "x.dpapi", "rules_library.json"):
                path = base / name
                path.write_text("must not ship")
                with self.subTest(name=name), self.assertRaises(RuntimeError):
                    builder.audit_distribution(base)
                path.unlink()

    @unittest.skipUnless(os.name == "nt", "Windows DPAPI")
    def test_dpapi_roundtrip(self):
        secret = os.urandom(32)
        protected = builder.dpapi(secret)
        self.assertNotIn(secret, protected)
        self.assertEqual(builder.dpapi(protected, decrypt=True), secret)

    def test_build_command_compiles_all_core_modules(self):
        command = builder.compiler_command(ROOT / "build", ROOT / "build/native")
        for module in ("cleaner_core", "cleaner_rules", "secure_rules", "_release_config", "migrate_core"):
            self.assertIn("--include-module=" + module, command)
        self.assertIn("--mode=standalone", command)
        self.assertFalse(any("rules_library.json" in arg or "trace_rules.json" in arg for arg in command))

    def test_compilation_audit_rejects_bytecode_modules(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Path(temp, "report.xml")
            modules = (*builder.MODULES[:-1], "_release_config")
            content = "".join(f'<module name="{name}" kind="CompiledPythonModule"/>' for name in modules)
            report.write_text("<report>" + content + "</report>")
            builder.audit_compilation(report)
            report.write_text("<report>" + content.replace('name="cleaner_core" kind="CompiledPythonModule"',
                                                            'name="cleaner_core" kind="UncompiledPythonModule"') + "</report>")
            with self.assertRaises(RuntimeError):
                builder.audit_compilation(report)

    def test_new_local_module_requires_release_integration(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            (base / "entry.py").write_text("import new_rules\n")
            (base / "new_rules.py").write_text("RULES = []\n")
            with self.assertRaisesRegex(RuntimeError, "new_rules"):
                builder.verify_source_inventory(base, ("entry",))
            builder.verify_source_inventory(base, ("entry", "new_rules"))


if __name__ == "__main__":
    unittest.main()
