from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
from ctypes import wintypes
from pathlib import Path
from typing import Any

from Cryptodome.Cipher import AES
from Cryptodome.Random import get_random_bytes


class SecureStore:
    """Encrypt local credential documents with OS- or secret-backed keys."""

    def __init__(
        self,
        filepath: str | Path,
        *,
        backend: str | None = None,
        secret: str | None = None,
    ) -> None:
        self.path = Path(filepath)
        self.backend_name = backend or ("dpapi" if os.name == "nt" else "aesgcm")
        self.secret = secret if secret is not None else os.getenv(
            "BILIBILI_CREDENTIAL_SECRET",
            "",
        )
        if self.backend_name not in {"dpapi", "aesgcm"}:
            raise ValueError(f"Unsupported credential backend: {self.backend_name}")

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            envelope = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        if not isinstance(envelope, dict) or envelope.get("version") != 1:
            return {}

        backend = envelope.get("backend")
        ciphertext = envelope.get("ciphertext")
        if not isinstance(backend, str) or not isinstance(ciphertext, str):
            return {}

        if backend == "dpapi":
            payload = self._dpapi_unprotect(base64.b64decode(ciphertext))
        elif backend == "aesgcm":
            nonce = envelope.get("nonce")
            tag = envelope.get("tag")
            if not isinstance(nonce, str) or not isinstance(tag, str):
                return {}
            payload = self._aes_decrypt(
                base64.b64decode(ciphertext),
                base64.b64decode(nonce),
                base64.b64decode(tag),
            )
        else:
            return {}

        decoded = json.loads(payload.decode("utf-8"))
        return decoded if isinstance(decoded, dict) else {}

    def write(self, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        if self.backend_name == "dpapi":
            envelope: dict[str, Any] = {
                "version": 1,
                "backend": "dpapi",
                "ciphertext": base64.b64encode(
                    self._dpapi_protect(payload)
                ).decode("ascii"),
            }
        else:
            ciphertext, nonce, tag = self._aes_encrypt(payload)
            envelope = {
                "version": 1,
                "backend": "aesgcm",
                "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
                "nonce": base64.b64encode(nonce).decode("ascii"),
                "tag": base64.b64encode(tag).decode("ascii"),
            }
        self._atomic_write(envelope)

    def delete(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def _key(self) -> bytes:
        if not self.secret:
            raise ValueError(
                "BILIBILI_CREDENTIAL_SECRET is required for aesgcm credential storage"
            )
        return hashlib.sha256(self.secret.encode("utf-8")).digest()

    def _aes_encrypt(self, payload: bytes) -> tuple[bytes, bytes, bytes]:
        nonce = get_random_bytes(12)
        cipher = AES.new(self._key(), AES.MODE_GCM, nonce=nonce)
        ciphertext, tag = cipher.encrypt_and_digest(payload)
        return ciphertext, nonce, tag

    def _aes_decrypt(self, ciphertext: bytes, nonce: bytes, tag: bytes) -> bytes:
        cipher = AES.new(self._key(), AES.MODE_GCM, nonce=nonce)
        return cipher.decrypt_and_verify(ciphertext, tag)

    def _dpapi_protect(self, payload: bytes) -> bytes:
        if os.name != "nt":
            raise ValueError("dpapi credential storage is only available on Windows")
        return self._dpapi_call(payload, protect=True)

    def _dpapi_unprotect(self, payload: bytes) -> bytes:
        if os.name != "nt":
            raise ValueError("dpapi credential storage is only available on Windows")
        return self._dpapi_call(payload, protect=False)

    @staticmethod
    def _dpapi_call(payload: bytes, *, protect: bool) -> bytes:
        class DataBlob(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
            ]

        def make_blob(data: bytes):
            buffer = ctypes.create_string_buffer(data)
            return DataBlob(
                len(data),
                ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
            ), buffer

        source, source_buffer = make_blob(payload)
        entropy, entropy_buffer = make_blob(b"BiliBrief")
        destination = DataBlob()
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        function = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
        result = function(
            ctypes.byref(source),
            None,
            ctypes.byref(entropy),
            None,
            None,
            0x1,
            ctypes.byref(destination),
        )
        _ = source_buffer, entropy_buffer
        if not result:
            raise OSError(ctypes.get_last_error(), "DPAPI operation failed")
        try:
            return ctypes.string_at(destination.pbData, destination.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(destination.pbData)

    def _atomic_write(self, envelope: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f"{self.path.name}.tmp")
        temporary.write_text(
            json.dumps(envelope, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
