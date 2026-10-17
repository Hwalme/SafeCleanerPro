"""Authenticated release rule storage. Development sources stay editable.

The AES key is compiled into each release: this raises extraction cost, it does
not make offline rules secret from someone controlling the running process.
Only the publisher holds the separate Ed25519 private signing key.
"""
import hashlib
import json
import os
import struct
import sys
import zlib
from pathlib import Path

MAGIC = b"SCPRULE1"
MAX_PACK = 16 * 1024 * 1024
MAX_PLAIN = 32 * 1024 * 1024
MAX_HEADER = 4096
_BUNDLE = None


class RulePackError(RuntimeError):
    """Release rules are unavailable or do not match the trusted build."""


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def validate_bundle(bundle):
    """Check the adapter contract before packaging or using any rule data."""
    if not isinstance(bundle, dict) or set(bundle) != {"library", "trace"}:
        raise RulePackError("Invalid rule datasets")
    lib = bundle["library"]
    if not isinstance(lib, dict) or not isinstance(lib.get("sources"), dict):
        raise RulePackError("Invalid library metadata")
    for name in ("winapp2", "dismpp"):
        rows = lib.get(name)
        if not isinstance(rows, list):
            raise RulePackError("Invalid library rules")
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str):
                raise RulePackError("Invalid library rule id")
            # Legacy Winapp2 slugs collide; the existing adapter deduplicates.
            if not row["id"]:
                raise RulePackError("Empty library rule id")
            if name == "winapp2":
                for field in ("filekeys", "detect", "exclude"):
                    values = row.get(field, [])
                    if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                        raise RulePackError("Invalid Winapp2 rule fields")
            else:
                paths = row.get("file_paths", [])
                if not isinstance(paths, list) or not all(
                    isinstance(p, dict) and isinstance(p.get("root", ""), str)
                    and isinstance(p.get("query", ""), str) for p in paths
                ):
                    raise RulePackError("Invalid Dism rule fields")
    if not isinstance(bundle["trace"], list):
        raise RulePackError("Invalid trace rules")
    for group in bundle["trace"]:
        if not isinstance(group, dict) or not isinstance(group.get("items"), list):
            raise RulePackError("Invalid trace group")
        for item in group["items"]:
            if not isinstance(item, dict) or not isinstance(item.get("type"), str) or not isinstance(item.get("target"), str):
                raise RulePackError("Invalid trace target")
    return bundle


def seal_bundle(bundle, aes_key, signing_key, build_id):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    plain = canonical_json(validate_bundle(bundle))
    if len(plain) > MAX_PLAIN:
        raise RulePackError("Rules exceed size limit")
    header = canonical_json({"schema": 1, "build_id": build_id,
                             "plain_sha256": hashlib.sha256(plain).hexdigest()})
    if len(header) > MAX_HEADER:
        raise RulePackError("Header exceeds size limit")
    aad = MAGIC + struct.pack(">I", len(header)) + header
    nonce = os.urandom(12)
    signed = aad + nonce + AESGCM(aes_key).encrypt(nonce, zlib.compress(plain, 9), aad)
    packed = signed + signing_key.sign(signed)
    if len(packed) > MAX_PACK:
        raise RulePackError("Pack exceeds size limit")
    return packed


def open_bundle(packed, aes_key, public_key, build_id, expected_sha256):
    """Pin exact build, verify publisher, authenticate, then bounded decode."""
    from cryptography.exceptions import InvalidSignature, InvalidTag
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    try:
        if len(packed) > MAX_PACK or len(packed) < 12 + 12 + 16 + 64:
            raise RulePackError("Invalid rule pack size")
        if hashlib.sha256(packed).hexdigest() != expected_sha256:
            raise RulePackError("Rule pack does not match this release")
        signed, signature = packed[:-64], packed[-64:]
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature, signed)
        if signed[:8] != MAGIC:
            raise RulePackError("Invalid rule pack format")
        size = struct.unpack(">I", signed[8:12])[0]
        if size > MAX_HEADER or size < 2 or 12 + size + 28 > len(signed):
            raise RulePackError("Invalid rule pack header")
        end = 12 + size
        header = json.loads(signed[12:end])
        if header.get("schema") != 1 or header.get("build_id") != build_id:
            raise RulePackError("Wrong rule pack version")
        compressed = AESGCM(aes_key).decrypt(signed[end:end + 12], signed[end + 12:], signed[:end])
        dec = zlib.decompressobj()
        plain = dec.decompress(compressed, MAX_PLAIN + 1)
        if len(plain) > MAX_PLAIN or not dec.eof or dec.unused_data or dec.unconsumed_tail:
            raise RulePackError("Invalid compressed rules")
        if hashlib.sha256(plain).hexdigest() != header.get("plain_sha256"):
            raise RulePackError("Invalid rule content digest")
        return validate_bundle(json.loads(plain))
    except RulePackError:
        raise
    except (InvalidSignature, InvalidTag, ValueError, TypeError, KeyError,
            AttributeError, zlib.error, struct.error) as exc:
        raise RulePackError("Rule pack authentication or decoding failed") from exc


def release_mode():
    # No environment-variable override in a compiled/frozen program.
    return "__compiled__" in globals() or bool(getattr(sys, "frozen", False))


def initialise_release():
    global _BUNDLE
    if _BUNDLE is not None:
        return _BUNDLE
    if not release_mode():
        raise RulePackError("Protected release must be compiled")
    try:
        import _release_config as config
        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        path = base / "rules.scpack"
        with path.open("rb") as stream:
            packed = stream.read(MAX_PACK + 1)
        _BUNDLE = open_bundle(packed, config.AES_KEY, config.PUBLIC_KEY,
                              config.BUILD_ID, config.PACK_SHA256)
        return _BUNDLE
    except (ImportError, OSError, AttributeError) as exc:
        raise RulePackError("Protected release rules are missing") from exc


def load_dataset(name):
    if name not in ("library", "trace"):
        raise RulePackError("Unknown rule dataset")
    if release_mode():
        return initialise_release()[name]
    # Source development uses fixed project paths, never the working directory.
    base = Path(__file__).resolve().parent
    path = base / ("rules_library.json" if name == "library" else "rules/trace_rules.json")
    try:
        with path.open(encoding="utf-8") as stream:
            return json.load(stream)
    except (OSError, ValueError) as exc:
        raise RulePackError("Development rule source is missing or invalid") from exc
