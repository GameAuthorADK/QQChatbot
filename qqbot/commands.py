"""指令解析与保留字。

规则：
  - 引擎指令不可被插件覆盖
  - 前缀支持半角 / 与全角 ／
  - 只解析第一条空白之前的部分作为指令名
"""

from __future__ import annotations

from dataclasses import dataclass, field

PREFIXES = ("/", "／")

#: 引擎保留指令
RESERVED = {
    "help": "查看帮助",
    "mode": "切换模式",
    "roll": "掷骰",
    "check": "检定",
    "attack": "攻击检定",
    "opposed": "对抗检定",
    "initiative": "先攻",
    "sancheck": "理智检定",
    "san": "理智检定",
    "sc": "理智检定",
    "pc": "角色卡",
    "rule": "房规",
    "rulepack": "跑团规则",
    "game": "小游戏",
    "wiki": "wiki 查询",
}

ALIASES = {
    "帮助": "help",
    "r": "roll",
    "掷骰": "roll",
    "c": "check",
    "检定": "check",
    "攻击检定": "attack",
    "对抗": "opposed",
    "contest": "opposed",
    "先攻": "initiative",
    "角色卡": "pc",
    "模式": "mode",
    "房规": "rule",
    "hr": "rule",
    "规则": "rule",
    "规则包": "rulepack",
    "ruleset": "rulepack",
    "rp": "rulepack",
    "小游戏": "game",
    "游戏": "game",
    "games": "game",
    "理智": "sancheck",
    "理智检定": "sancheck",
    "sc": "sancheck",
    "san": "sancheck",
    "百科": "wiki",
    "维基": "wiki",
    "灰机": "wiki",
}


@dataclass
class Command:
    name: str
    args: list[str] = field(default_factory=list)
    raw: str = ""

    @property
    def text(self) -> str:
        return " ".join(self.args)


def parse(text: str) -> Command | None:
    """不是指令则返回 None。"""
    t = (text or "").strip()
    if not t or t[0] not in PREFIXES:
        return None
    body = t[1:].strip()
    if not body:
        return None
    parts = body.split()
    name = parts[0].lower()
    name = ALIASES.get(name, name)
    return Command(name=name, args=parts[1:], raw=body)
