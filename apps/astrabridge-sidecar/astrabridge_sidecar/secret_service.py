from __future__ import annotations

import base64
import ctypes
import ctypes.wintypes
import hashlib
import os
from dataclasses import dataclass


KEYCHAIN_PREFIX = "AstraBridge:"


@dataclass
class SecretMetadata:
    loaded: bool
    source: str
    fingerprint: str | None
    secret_ref: str | None


class SecretService:
    def store(self, name: str, secret: str) -> str:
        if not secret or len(secret.strip()) < 8:
            raise ValueError("Secret is too short.")
        value = secret.strip()
        if os.name == "nt":
            self._windows_store(name, value)
            return f"wincred:{name}"
        raise RuntimeError("OS keychain is only implemented for Windows in this build.")

    def load(self, secret_ref: str) -> str | None:
        if not secret_ref:
            return None
        if secret_ref.startswith("wincred:"):
            if os.name != "nt":
                return None
            return self._windows_load(secret_ref.split(":", 1)[1])
        return None

    def delete(self, secret_ref: str) -> bool:
        if not secret_ref:
            return False
        if secret_ref.startswith("wincred:"):
            if os.name != "nt":
                return False
            return self._windows_delete(secret_ref.split(":", 1)[1])
        return False

    def fingerprint(self, secret: str | None) -> str | None:
        if not secret:
            return None
        digest = hashlib.sha256(secret.encode("utf-8")).hexdigest()
        return digest[:12]

    def metadata(self, *, env_key: str, auth_mode: str, secret_ref: str | None) -> SecretMetadata:
        env_value = os.environ.get(env_key)
        if env_value:
            return SecretMetadata(True, "environment", self.fingerprint(env_value), secret_ref)
        if auth_mode == "os_keychain" and secret_ref:
            loaded = self.load(secret_ref)
            return SecretMetadata(bool(loaded), "os_keychain", self.fingerprint(loaded), secret_ref)
        return SecretMetadata(False, "missing", None, secret_ref)

    def _windows_store(self, name: str, secret: str) -> None:
        target = KEYCHAIN_PREFIX + name
        data = secret.encode("utf-16-le")
        blob = ctypes.create_string_buffer(data)
        credential = CREDENTIALW()
        credential.Type = CRED_TYPE_GENERIC
        credential.TargetName = target
        credential.CredentialBlobSize = len(data)
        credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
        credential.Persist = CRED_PERSIST_LOCAL_MACHINE
        credential.UserName = "AstraBridge"
        if not advapi32.CredWriteW(ctypes.byref(credential), 0):
            raise ctypes.WinError()

    def _windows_load(self, name: str) -> str | None:
        target = KEYCHAIN_PREFIX + name
        pointer = ctypes.POINTER(CREDENTIALW)()
        if not advapi32.CredReadW(target, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
            error = ctypes.GetLastError()
            if error == 1168:
                return None
            raise ctypes.WinError(error)
        try:
            credential = pointer.contents
            if not credential.CredentialBlob or credential.CredentialBlobSize <= 0:
                return None
            raw = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            return raw.decode("utf-16-le")
        finally:
            advapi32.CredFree(pointer)

    def _windows_delete(self, name: str) -> bool:
        target = KEYCHAIN_PREFIX + name
        if advapi32.CredDeleteW(target, CRED_TYPE_GENERIC, 0):
            return True
        error = ctypes.GetLastError()
        if error == 1168:
            return False
        raise ctypes.WinError(error)


if os.name == "nt":
    advapi32 = ctypes.WinDLL("Advapi32.dll")

    CRED_TYPE_GENERIC = 1
    CRED_PERSIST_LOCAL_MACHINE = 2

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", ctypes.wintypes.DWORD), ("dwHighDateTime", ctypes.wintypes.DWORD)]

    class CREDENTIAL_ATTRIBUTEW(ctypes.Structure):
        _fields_ = [
            ("Keyword", ctypes.wintypes.LPWSTR),
            ("Flags", ctypes.wintypes.DWORD),
            ("ValueSize", ctypes.wintypes.DWORD),
            ("Value", ctypes.POINTER(ctypes.c_ubyte)),
        ]

    class CREDENTIALW(ctypes.Structure):
        _fields_ = [
            ("Flags", ctypes.wintypes.DWORD),
            ("Type", ctypes.wintypes.DWORD),
            ("TargetName", ctypes.wintypes.LPWSTR),
            ("Comment", ctypes.wintypes.LPWSTR),
            ("LastWritten", FILETIME),
            ("CredentialBlobSize", ctypes.wintypes.DWORD),
            ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
            ("Persist", ctypes.wintypes.DWORD),
            ("AttributeCount", ctypes.wintypes.DWORD),
            ("Attributes", ctypes.POINTER(CREDENTIAL_ATTRIBUTEW)),
            ("TargetAlias", ctypes.wintypes.LPWSTR),
            ("UserName", ctypes.wintypes.LPWSTR),
        ]

    advapi32.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIALW), ctypes.wintypes.DWORD]
    advapi32.CredWriteW.restype = ctypes.wintypes.BOOL
    advapi32.CredReadW.argtypes = [
        ctypes.wintypes.LPCWSTR,
        ctypes.wintypes.DWORD,
        ctypes.wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(CREDENTIALW)),
    ]
    advapi32.CredReadW.restype = ctypes.wintypes.BOOL
    advapi32.CredDeleteW.argtypes = [ctypes.wintypes.LPCWSTR, ctypes.wintypes.DWORD, ctypes.wintypes.DWORD]
    advapi32.CredDeleteW.restype = ctypes.wintypes.BOOL
    advapi32.CredFree.argtypes = [ctypes.c_void_p]
    advapi32.CredFree.restype = None

