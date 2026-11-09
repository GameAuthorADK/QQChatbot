"""小游戏插件：发现与元信息。

一个 .py 文件就是一个游戏，放在程序目录的 plugins/minigame/ 下。

    NAME = "我的游戏"
    VERSION = "0.1.0"
    DESCRIPTION = "一句话说明"
    SCOPE = "solo"   # solo 单人 | group 全群共享
    MODE = "round"   # round 按局 | daily 每天一次
    COMMANDS = {"demo": "示例指令"}

    def handle(ctx):      # 指令处理（必须）
        ...

加载阶段只用 ast 读字面量，不执行代码。
"""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from .paths import MINIGAMES_DIR

MAX_FILE_BYTES = 512 * 1024


@dataclass
class GamePlugin:
    id: str
    path: Path | None
    name: str
    version: str = "0.0.0"
    description: str = ""
    commands: dict = field(default_factory=dict)
    hooks: set = field(default_factory=set)
    scope: str = "solo"   # solo | group
    mode: str = "round"   # daily | round
    file_hash: str = ""
    error: str = ""


def parse_source(
    source: str, game_id: str, path: Path | None = None
) -> GamePlugin:
    info = GamePlugin(id=game_id, path=path, name=game_id)
    info.file_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()

    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", game_id):
        info.error = "文件名只能包含字母、数字、下划线和短横线"
        return info

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        info.error = f"语法错误：第 {exc.lineno} 行 {exc.msg}"
        return info

    hooks: set[str] = set()
    found: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {
            "handle",
        }:
            hooks.add(node.name)

        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id in {
                "NAME",
                "VERSION",
                "DESCRIPTION",
                "COMMANDS",
                "SCOPE",
                "MODE",
            }:
                try:
                    found[target.id] = ast.literal_eval(node.value)
                except Exception:
                    info.error = f"{target.id} 必须是字面量"
                    return info

    info.name = str(found.get("NAME") or game_id)[:60]
    info.version = str(found.get("VERSION") or "0.0.0")[:20]
    info.description = str(found.get("DESCRIPTION") or "")[:300]
    info.hooks = hooks

    scope = str(found.get("SCOPE") or "solo").lower()
    if scope not in ("solo", "group"):
        info.error = "SCOPE 只能是 solo 或 group"
        return info
    info.scope = scope

    mode = str(found.get("MODE") or "round").lower()
    if mode not in ("daily", "round"):
        info.error = "MODE 只能是 daily 或 round"
        return info
    info.mode = mode

    raw_commands = found.get("COMMANDS")
    if not isinstance(raw_commands, dict) or not raw_commands:
        info.error = "COMMANDS 必须是非空字典"
        return info

    commands: dict[str, str] = {}
    for name, desc in raw_commands.items():
        cmd = str(name).strip().lower()
        if not re.fullmatch(r"[\w]{1,24}", cmd, re.UNICODE):
            info.error = f"指令名 {name} 非法（不能包含空格或标点）"
            return info
        commands[cmd] = str(desc)[:80]
    if len(commands) > 20:
        info.error = "指令最多 20 个"
        return info

    info.commands = commands
    if "handle" not in hooks:
        info.error = "缺少 handle(ctx)"
    return info


def read_meta(path: Path) -> GamePlugin:
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_FILE_BYTES:
            info = GamePlugin(
                id=path.stem, path=path, name=path.stem, error="文件过大（上限 512 KB）"
            )
            return info
        source = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        return GamePlugin(
            id=path.stem, path=path, name=path.stem, error=f"读取失败：{exc}"
        )

    info = parse_source(source, path.stem, path)
    info.file_hash = hashlib.sha256(raw).hexdigest()
    return info


def discover(base: Path | None = None) -> list[GamePlugin]:
    base = base or MINIGAMES_DIR
    out: list[GamePlugin] = []
    if not base.exists():
        return out
    for path in sorted(base.glob("*.py")):
        if path.name.startswith("_"):
            continue
        out.append(read_meta(path))
    return out


GAME_TEMPLATE = '''"""我的游戏 —— 单文件小游戏插件模板。

放在 plugins/minigame/ 下，文件名就是游戏 id，例如 mygame.py。
加载时只读取模块顶部的字面量，不执行文件里的代码。

游戏节奏：
  SCOPE = "solo"    单人，状态按 游戏 + 群 + 玩家 隔离
  SCOPE = "group"   全群共享一份状态
  MODE = "round"    按局，结束一局再开下一局
  MODE = "daily"    每天一次；跨天时框架自动清空 store["daily"]，保留 store["stats"]

ctx 里包含：
  event / command / text / args / user / group / role / mode / date
  card    当前群使用的跑团角色卡（可能为 None）
  store   游戏私有状态（JSON）

返回值：
  字符串，或 {"reply": "...", "store": {...}}
  store 由主进程保存，下一次调用会原样传回来。
"""

NAME = "我的游戏"
VERSION = "0.1.0"
DESCRIPTION = "一句话说明这个游戏怎么玩"
SCOPE = "solo"
MODE = "round"
COMMANDS = {"demo": "示例指令"}


def handle(ctx):
    """处理 COMMANDS 里声明的指令。"""
    store = dict(ctx.get("store") or {})
    active = dict(store.get("active") or {})
    active["n"] = int(active.get("n", 0)) + 1
    store["active"] = active
    return {"reply": f"第 {active['n']} 次（示例逻辑，请替换）", "store": store}
'''
