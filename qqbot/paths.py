"""路径解析与实例身份。

硬规则：
  1. 一切路径基于可执行文件位置，绝不用 cwd。
  2. 不写入 BASE 之外的任何位置。
  3. 路径预算动态计算，不写死。
"""

from __future__ import annotations

import hashlib
import json
import socket
import sys
from pathlib import Path

FROZEN = bool(getattr(sys, "frozen", False))

#: MAX_PATH 在 Windows 上的上限；LongPathsEnabled=0 时生效
WIN_MAX_PATH = 260
#: 为临时文件与后缀预留的余量
PATH_MARGIN = 10
#: 读不到 path-budget.json 时的保守假设
DEFAULT_MAX_REL = 100


def resolve_base() -> Path:
    if FROZEN:
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


BASE = resolve_base()

CONFIG_DIR = BASE / "config"
DATA_DIR = BASE / "data"
LOG_DIR = BASE / "logs"
RUNTIME_DIR = BASE / "runtime"
PROFILES_DIR = BASE / "profiles"
PLUGINS_DIR = BASE / "plugins"
TRPG_DIR = PLUGINS_DIR / "trpg"
MINIGAMES_DIR = PLUGINS_DIR / "minigame"
MODES_DIR = PLUGINS_DIR / "modes"

INSTANCE_YAML = CONFIG_DIR / "instance.yaml"
SECRETS_DAT = CONFIG_DIR / "secrets.dat"
DB_PATH = DATA_DIR / "bot.db"
LOCK_PATH = DATA_DIR / ".instance.lock"


def ensure_dirs() -> None:
    for d in (
        CONFIG_DIR,
        DATA_DIR,
        LOG_DIR,
        RUNTIME_DIR,
        PROFILES_DIR,
        PLUGINS_DIR,
        TRPG_DIR,
        MINIGAMES_DIR,
        MODES_DIR,
    ):
        d.mkdir(parents=True, exist_ok=True)


def max_rel_len() -> int:
    """产物内最长相对路径长度，由构建脚本写入。"""
    manifest = BASE / "app" / "path-budget.json"
    try:
        return int(json.loads(manifest.read_text("utf-8"))["max_rel_len"])
    except Exception:
        return DEFAULT_MAX_REL


def path_budget() -> int:
    """BASE 允许的最大长度。"""
    return WIN_MAX_PATH - max_rel_len() - PATH_MARGIN


def check_base_path() -> tuple[bool, str]:
    """返回 (是否可用, 人话说明)。"""
    n = len(str(BASE))
    budget = path_budget()
    if n > budget:
        return False, (
            f"程序所在路径过长（{n} 字符，上限 {budget}）。"
            "请把整个文件夹移动到更短的目录，例如 D:\\QQBot。"
        )
    return True, f"{n}/{budget}"


def instance_id() -> str:
    """实例身份由路径 + 主机名推导，不持久化。

    拷到任何新路径都会自动获得新身份，避免两个文件夹共用状态。
    """
    seed = f"{BASE}|{socket.gethostname()}".lower().encode("utf-8")
    return hashlib.sha256(seed).hexdigest()[:12]


def is_network_path(p: Path = BASE) -> bool:
    s = str(p)
    return s.startswith("\\\\")
