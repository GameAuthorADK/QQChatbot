"""模式插件：让用户自定义「大模式」的管线行为。

一个 .py 文件就是一个模式，放在 plugins/modes/ 下：

    LABEL = "翻译模式"
    DESCRIPTION = "把每句话翻译成英文"
    CALL_LLM = True
    ALLOW_KEYWORD = False
    EXTRA_PROMPT = "只输出英文译文。"
    HELP = "翻译模式：直接发要翻译的内容。"

模式只描述管线行为，不执行代码：
  CALL_LLM        是否调用模型
  ALLOW_KEYWORD   关键词规则是否生效
  EXTRA_PROMPT    追加到系统提示词后面的说明
  HELP            /help 的内容

内置 chat / trpg / minigame 不能被覆盖。
"""

from __future__ import annotations

import ast
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .paths import MODES_DIR

MAX_FILE_BYTES = 256 * 1024
MAX_PROMPT = 2000
MAX_HELP = 1000
MAX_LABEL = 40
MAX_DESC = 200

_CHAT_HELP = (
    "聊天模式：闲聊交给模型，指令只响应通用和小游戏。\n"
    "/mode　　　查看当前模式\n"
    "/mode trpg　进入跑团模式\n"
    "/mode minigame　进入小游戏模式\n"
    "/wiki 原神　查游戏 wiki\n"
    "/game　　　查看已启用的小游戏\n"
    "/help　查看帮助"
)

_TRPG_HELP = (
    "跑团模式：只响应跑团指令，不回闲聊，不调用模型。\n"
    "/roll 1d100　掷骰\n"
    "/check 侦察　技能检定\n"
    "/check 侦察 惩罚1　COC 奖励骰 / 惩罚骰\n"
    "/check 运动 15　DND：d20 + 加值 对抗 DC\n"
    "/attack 15　攻击检定\n"
    "/先攻　DND 先攻检定\n"
    "/opposed 运动 5　对抗检定\n"
    "/sancheck 0/1d6　理智检定\n"
    "/pc new　　建角色卡\n"
    "/rule　　　查看房规\n"
    "/rulepack　查看本群规则\n"
    "/wiki 原神　查游戏 wiki\n"
    "/mode　　　查看当前模式\n"
    "/mode off　退出模式"
)

_GAME_HELP = (
    "小游戏模式：只响应小游戏指令，不回闲聊，不调用模型。\n"
    "/mode　　　查看当前模式\n"
    "/wiki 原神　查游戏 wiki\n"
    "/game　　　查看已启用的小游戏\n"
    "/mode off　退出模式"
)


def _builtin(
    mode_id: str,
    label: str,
    description: str,
    call_llm: bool,
    allow_keyword: bool,
    help_text: str,
) -> "ModeSpec":
    return ModeSpec(
        id=mode_id,
        label=label,
        description=description,
        call_llm=call_llm,
        allow_keyword=allow_keyword,
        help_text=help_text,
        source="builtin",
    )


@dataclass
class ModeSpec:
    id: str
    label: str
    description: str = ""
    call_llm: bool = False
    allow_keyword: bool = False
    extra_prompt: str = ""
    help_text: str = ""
    source: str = "plugin"
    path: Path | None = None
    file_hash: str = ""
    error: str = ""


BUILTIN_MODES: dict[str, ModeSpec] = {
    "chat": _builtin(
        "chat",
        "聊天",
        "正常聊天，消息交给模型处理。",
        True,
        True,
        _CHAT_HELP,
    ),
    "trpg": _builtin(
        "trpg",
        "跑团",
        "只响应跑团指令，不回闲聊，不调用模型。",
        False,
        False,
        _TRPG_HELP,
    ),
    "minigame": _builtin(
        "minigame",
        "小游戏",
        "只响应小游戏指令，不回闲聊，不调用模型。",
        False,
        False,
        _GAME_HELP,
    ),
}


def parse_source(source: str, mode_id: str, path: Path | None = None) -> ModeSpec:
    info = ModeSpec(id=mode_id, label=mode_id, path=path)
    info.file_hash = hashlib.sha256(source.encode("utf-8")).hexdigest()

    if mode_id in BUILTIN_MODES:
        info.error = f"{mode_id} 是内置模式，不能被覆盖"
        return info
    if not re.fullmatch(r"[a-z0-9_-]{1,24}", mode_id):
        info.error = "模式 id 只能包含小写字母、数字、下划线和短横线（1–24 字符）"
        return info

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        info.error = f"语法错误：第 {exc.lineno} 行 {exc.msg}"
        return info

    wanted = {
        "LABEL",
        "DESCRIPTION",
        "CALL_LLM",
        "ALLOW_KEYWORD",
        "EXTRA_PROMPT",
        "HELP",
    }
    found: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in wanted:
                try:
                    found[target.id] = ast.literal_eval(node.value)
                except Exception:
                    info.error = f"{target.id} 必须是字面量"
                    return info

    info.label = str(found.get("LABEL") or mode_id)[:MAX_LABEL]
    info.description = str(found.get("DESCRIPTION") or "")[:MAX_DESC]
    info.extra_prompt = str(found.get("EXTRA_PROMPT") or "")[:MAX_PROMPT]

    call_llm = found.get("CALL_LLM", False)
    if not isinstance(call_llm, bool):
        info.error = "CALL_LLM 必须是 True 或 False"
        return info
    info.call_llm = call_llm

    allow_keyword = found.get("ALLOW_KEYWORD", False)
    if not isinstance(allow_keyword, bool):
        info.error = "ALLOW_KEYWORD 必须是 True 或 False"
        return info
    info.allow_keyword = allow_keyword

    info.help_text = str(found.get("HELP") or "")[:MAX_HELP]
    if not info.help_text:
        info.help_text = (
            f"{info.label}："
            + ("正常调用模型。" if info.call_llm else "只响应指令，不调用模型。")
        )
    info.source = "plugin"
    return info


def read_meta(path: Path) -> ModeSpec:
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_FILE_BYTES:
            return ModeSpec(
                id=path.stem,
                label=path.stem,
                path=path,
                error="文件过大（上限 256 KB）",
            )
        source = raw.decode("utf-8", errors="replace")
    except Exception as exc:
        return ModeSpec(
            id=path.stem, label=path.stem, path=path, error=f"读取失败：{exc}"
        )

    info = parse_source(source, path.stem, path)
    info.file_hash = hashlib.sha256(raw).hexdigest()
    return info


def discover(base: Path | None = None) -> list[ModeSpec]:
    base = base or MODES_DIR
    out: list[ModeSpec] = []
    if not base.exists():
        return out
    for path in sorted(base.glob("*.py")):
        if path.name.startswith("_"):
            continue
        out.append(read_meta(path))
    return out


MODE_TEMPLATE = '''"""自定义模式模板。

放在 plugins/modes/ 下，文件名就是模式 id，例如 translate.py。
加载时只读取下面的字面量，不执行文件里的代码。

模式只影响消息管线，不提供指令：
  CALL_LLM        True = 闲聊也交给模型；False = 只响应指令
  ALLOW_KEYWORD   True = 关键词规则也生效
  EXTRA_PROMPT    追加到系统提示词，用来规定这个模式的说话方式
  HELP            /help 显示的内容

需要自定义指令时，用代码插件、规则插件或小游戏插件。
"""

LABEL = "翻译模式"
DESCRIPTION = "把每句话翻译成英文"
CALL_LLM = True
ALLOW_KEYWORD = False

EXTRA_PROMPT = """当前处于翻译模式。
把用户发来的内容翻译成英文，只输出译文，不要解释。"""

HELP = """翻译模式：直接发要翻译的内容。
/help　查看帮助
/mode off　退出模式"""
'''
