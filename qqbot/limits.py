"""用户可编辑文本的长度上限。

界面上标注的上限、保存时的截断、拼进提示词时的截断必须用同一组数字，
否则用户写满界面允许的字数后，超出部分会被悄悄丢掉。
"""

from __future__ import annotations

#: 机器人名字
BOT_NAME = 40
#: 角色设定
PERSONA = 2000
#: 禁止事项（负面提示词）
NEGATIVE_PROMPT = 1000
#: 回复风格
STYLE_PROMPT = 800
#: 人设锚点
PERSONA_ANCHOR = 1000

__all__ = [
    "BOT_NAME",
    "PERSONA",
    "NEGATIVE_PROMPT",
    "STYLE_PROMPT",
    "PERSONA_ANCHOR",
]
