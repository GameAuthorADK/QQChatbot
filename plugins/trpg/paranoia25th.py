"""妄想症25th —— 单文件规则插件（裸骰模式）。

/check 只掷 1d20 并报骰值，成败由 KP 判定。
只收录角色卡正面：身份、六项技能、能量武器专精。
背面 SECRET SIDE（Power / Access、变异、结社、秘密技能、装备等）一律不录。
"""

NAME = "妄想症25th"
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
    {"key": "sector", "label": "区域", "type": "str", "max": 3, "hide_if_default": True},
    {"key": "clone", "label": "克隆体编号", "type": "int", "min": 1, "max": 6, "default": 1},
    {"key": "gender", "label": "性别", "type": "enum", "options": ["M", "F", "Other"], "default": "Other"},
    {"key": "player", "label": "玩家", "type": "str", "max": 40, "hide_if_default": True},
    {
        "key": "service_group",
        "label": "服务部门",
        "type": "enum",
        "options": ["IntSec", "Tech", "HPDMC", "Army", "PLC", "Power", "RND", "CPU"],
    },
    {
        "key": "duty",
        "label": "强制职责",
        "type": "enum",
        "options": [
            "team_leader",
            "loyalty_officer",
            "hygiene_officer",
            "comm_recording",
            "equipment_guy",
            "happiness_officer",
            "other",
        ],
    },
    {"key": "tics", "label": "习惯动作", "type": "str", "max": 100, "hide_if_default": True},
    {"key": "management", "label": "处世", "type": "int", "min": 0, "max": 20, "default": 0},
    {"key": "stealth", "label": "隐秘", "type": "int", "min": 0, "max": 20, "default": 0},
    {"key": "violence", "label": "武力", "type": "int", "min": 0, "max": 20, "default": 0},
    {"key": "hardware", "label": "硬件", "type": "int", "min": 0, "max": 20, "default": 0},
    {"key": "software", "label": "软件", "type": "int", "min": 0, "max": 20, "default": 0},
    {"key": "wetware", "label": "湿件", "type": "int", "min": 0, "max": 20, "default": 0},
    {"key": "energy_weapons", "label": "能量武器", "type": "expr", "expr": "violence + 4"},
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
