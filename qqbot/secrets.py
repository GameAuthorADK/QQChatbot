"""凭据存储：Windows DPAPI 加密，机器 + 用户绑定。

设计意图：拷贝文件夹到另一台机器后解密必然失败 —— 这正好等价于
"新 bot 需要新凭据"，所以不是缺陷。
"""

from __future__ import annotations

import base64
import ctypes
import json
import sys
from ctypes import wintypes
from pathlib import Path

from . import errors
from .paths import SECRETS_DAT

MAGIC = "QQChatbot"
VERSION = 1
#: 应用级熵，防止其他程序直接解开本程序的密文
ENTROPY = b"QQChatbot/v1/dpapi"


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_char)),
    ]


def _blob(data: bytes):
    buf = ctypes.create_string_buffer(data, len(data))
    return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char))), buf


def _dpapi(data: bytes, *, protect: bool) -> bytes:
    if sys.platform != "win32":
        raise errors.BotError(errors.TOKEN_BROKEN, "当前平台不支持 DPAPI")

    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    in_blob, _keep_in = _blob(data)
    ent_blob, _keep_ent = _blob(ENTROPY)
    out_blob = DATA_BLOB()

    func = crypt32.CryptProtectData if protect else crypt32.CryptUnprotectData
    ok = func(
        ctypes.byref(in_blob),
        None,
        ctypes.byref(ent_blob),
        None,
        None,
        0,
        ctypes.byref(out_blob),
    )
    if not ok:
        err = ctypes.get_last_error()
        raise OSError(err, f"DPAPI {'encrypt' if protect else 'decrypt'} failed")

    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def save(secrets: dict[str, str], path: Path = SECRETS_DAT) -> None:
    payload = json.dumps(secrets, ensure_ascii=False).encode("utf-8")
    cipher = _dpapi(payload, protect=True)
    doc = {
        "magic": MAGIC,
        "version": VERSION,
        "alg": "dpapi",
        "data": base64.b64encode(cipher).decode("ascii"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def load(path: Path = SECRETS_DAT) -> dict[str, str]:
    """读取凭据。文件不存在返回空字典；解密失败抛 BotError。"""
    if not path.exists():
        return {}
    try:
        doc = json.loads(path.read_text("utf-8"))
    except Exception as exc:
        raise errors.BotError(errors.TOKEN_INVALID, "凭据文件损坏") from exc

    if doc.get("magic") != MAGIC:
        raise errors.BotError(errors.TOKEN_INVALID, "凭据文件格式不识别")

    try:
        cipher = base64.b64decode(doc.get("data", ""))
        plain = _dpapi(cipher, protect=False)
        return json.loads(plain.decode("utf-8"))
    except OSError as exc:
        raise errors.BotError(
            errors.TOKEN_INVALID,
            "凭据无法解密（可能来自另一台电脑），请重新填写",
        ) from exc
    except Exception as exc:
        raise errors.BotError(errors.TOKEN_INVALID, "凭据解析失败") from exc


def has_secrets(path: Path = SECRETS_DAT) -> bool:
    return path.exists()


def mask(value: str, keep: int = 4) -> str:
    """日志与界面统一用这个，禁止直接打印原值。"""
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]
