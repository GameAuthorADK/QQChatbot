"""日志：结构化 + 强制脱敏。

任何日志在落盘前都会过一遍脱敏过滤器。这是硬约束，不是可选项。
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import sys
from pathlib import Path

from .paths import LOG_DIR

#: 必须匹配并打码的模式
_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(QQBot\s+)\S+"), r"\1***"),
    (re.compile(r"(Bearer\s+)\S+"), r"\1***"),
    (re.compile(r"(sk-)[A-Za-z0-9_\-]{6,}"), r"\1***"),
    (re.compile(r'("?access_token"?\s*[:=]\s*"?)[^"\s,}]+'), r"\1***"),
    (re.compile(r"(auth_token=)[^&\s\"']+"), r"\1***"),
    (re.compile(r"(rkey=)[^&\s\"']+"), r"\1***"),
    (re.compile(r"(appSecret\"?\s*[:=]\s*\"?)[^\"\s,}]+", re.I), r"\1***"),
]


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except Exception:
            return True
        for pattern, repl in _REDACTIONS:
            msg = pattern.sub(repl, msg)
        record.msg = msg
        record.args = ()
        return True


def mask_id(value: str | None, keep: int = 4) -> str:
    if not value:
        return "-"
    if len(value) <= keep:
        return "*" * len(value)
    return f"…{value[-keep:]}"


_configured = False


def setup(level: str = "INFO") -> Path:
    """初始化日志，返回日志文件路径。重复调用无副作用。"""
    global _configured
    log_file = LOG_DIR / "qqbot.log"
    if _configured:
        return log_file

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(level.upper())

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)-22s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    fh = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    fh.setFormatter(fmt)
    fh.addFilter(RedactFilter())

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.addFilter(RedactFilter())

    root.addHandler(fh)
    if sys.stderr is not None:  # --noconsole 打包后 stderr 为 None
        root.addHandler(sh)

    # 第三方库降噪
    for name in ("httpx", "httpcore", "uvicorn.access", "websockets"):
        logging.getLogger(name).setLevel(logging.WARNING)

    _configured = True
    return log_file


def clear_logs() -> dict:
    """清空当前日志文件与轮转文件。

    正在写入的 RotatingFileHandler 不能删除（Windows 会拒绝），
    所以直接截断它的流；轮转出来的旧文件直接删。
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()

    truncated = 0
    locked: set[str] = set()
    for handler in root.handlers:
        stream = getattr(handler, "stream", None)
        path = getattr(handler, "baseFilename", None)
        if stream is None or not path:
            continue
        try:
            handler.acquire()
            stream.flush()
            stream.seek(0)
            stream.truncate(0)
            stream.seek(0, 2)
            truncated += 1
            locked.add(str(Path(path).resolve()))
        except Exception:
            continue
        finally:
            try:
                handler.release()
            except Exception:
                pass

    removed = 0
    for old in LOG_DIR.glob("qqbot.log*"):
        try:
            if str(old.resolve()) in locked:
                continue
            old.unlink()
            removed += 1
        except Exception:
            continue

    return {"truncated": truncated, "removed": removed}

