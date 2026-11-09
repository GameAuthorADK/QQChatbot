"""妄想症2e —— 单文件规则插件（裸骰模式）。

判定权归 KP：/check 只掷 1d20 并报出骰值，不取目标、不判成败。
角色卡只收录原表正面、公开、且玩家自己能读到的内容；
异能力、秘密结社、反叛技能、安全局特工等隐藏信息一律不录。
"""

NAME = "妄想症2e"
VERSION = "0.1.0"
DESCRIPTION = "裸骰模式：只掷 1d20 报骰值，成败由 KP 判定。"

REVEAL = "roll-only"

FIELDS = [
    {"key": "name", "label": "名字", "type": "str", "max": 40, "hide_if_default": True},
    {
        "key": "clearance",
        "label": "保密等级",
        "type": "enum",
        "options": ["R", "O", "Y", "G", "B", "I", "V", "U"],
        "default": "R",
    },
    {"key": "sector", "label": "地区代码", "type": "str", "max": 3, "hide_if_default": True},
    {"key": "clone", "label": "克隆体编号", "type": "int", "min": 1, "max": 99, "default": 1},
    {"key": "player", "label": "玩家", "type": "str", "max": 40, "hide_if_default": True},
    {
        "key": "dept",
        "label": "服务部门",
        "type": "enum",
        "options": ["IntSec", "Tech", "HPDMC", "Army", "PLC", "Power", "RND", "CPU"],
    },
    {"key": "str", "label": "力量", "type": "int", "min": 1, "max": 20, "default": 10, "roll": "1d20"},
    {"key": "agi", "label": "敏捷", "type": "int", "min": 1, "max": 20, "default": 10, "roll": "1d20"},
    {"key": "dex", "label": "灵巧", "type": "int", "min": 1, "max": 20, "default": 10, "roll": "1d20"},
    {"key": "con", "label": "耐久", "type": "int", "min": 1, "max": 20, "default": 10, "roll": "1d20"},
    {"key": "mox", "label": "精力", "type": "int", "min": 1, "max": 20, "default": 10, "roll": "1d20"},
    {"key": "chz", "label": "厚颜", "type": "int", "min": 1, "max": 20, "default": 10, "roll": "1d20"},
    {"key": "mek", "label": "机械天赋", "type": "int", "min": 1, "max": 20, "default": 10, "roll": "1d20"},
    {"key": "pow", "label": "能量", "type": "int", "min": 1, "max": 20, "default": 10, "roll": "1d20"},
    {"key": "carry", "label": "载重量", "type": "expr", "expr": "25 + max(0, str - 12) * 5"},
    {
        "key": "dmg_bonus",
        "label": "伤害加值",
        "type": "lookup",
        "source": "str",
        "table": [
            {"max": 13, "value": 0},
            {"max": 18, "value": 1},
            {"max": 20, "value": 2},
        ],
    },
    {
        "key": "soak",
        "label": "英雄气概",
        "type": "lookup",
        "source": "con",
        "table": [
            {"max": 13, "value": 0},
            {"max": 18, "value": 1},
            {"max": 20, "value": 2},
        ],
    },
    {"key": "credits", "label": "信用点", "type": "int", "min": 0, "default": 0},
    {"key": "notes", "label": "备注", "type": "str", "max": 200, "hide_if_default": True},
]

CHECKS = {
    "skill": {
        "label": "检定",
        "dice": "1d20",
        "target": "skill",
        "outcomes": [],
    },
}
