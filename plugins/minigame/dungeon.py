"""文字地牢 —— 单人、按局、线性楼层。"""

import random

NAME = "文字地牢"
VERSION = "1.0.0"
DESCRIPTION = "十层线性地牢，三种主题，纯文字 roguelike。"
SCOPE = "solo"
MODE = "round"
COMMANDS = {
    "地牢": "开始或继续一局",
    "走": "前往下一个房间",
    "攻击": "攻击敌人",
    "防御": "防御本回合",
    "喝药": "喝一瓶药",
    "逃跑": "尝试脱离战斗",
    "背包": "查看背包",
    "状态": "查看当前状态",
    "撤退": "结束本局",
    "再来地牢": "开新的一局",
}

_MAX_FLOOR = 10
_PLAYER_HP = 50
_POTION_HEAL = 10

_THEMES = {
    "西幻": {
        "intro": "你推开沉重的石门，潮湿的风从地下吹来。",
        "rooms": [
            "一条被火把照亮的走廊",
            "堆满骸骨的房间",
            "长满苔藓的石阶",
            "废弃的武器库",
            "刻着古老符文的墙壁",
        ],
        "monsters": ["地穴鼠", "骷髅兵", "石像鬼", "食人魔", "暗影狼", "亡灵法师"],
        "bosses": ["深渊魔龙", "亡灵巫妖王", "熔岩领主"],
    },
    "克苏鲁": {
        "intro": "你走进一座多年无人居住的宅邸，空气里有海腥味。",
        "rooms": [
            "墙纸剥落的走廊",
            "摆满旧书的书房",
            "通向地下室的窄梯",
            "窗户被钉死的大厅",
            "传来低语的储藏室",
        ],
        "monsters": ["深潜者", "米·戈", "夜魇", "修格斯", "星之眷族幼体", "疯狂信徒"],
        "bosses": ["黄衣之王的化身", "星之眷族母体", "修格斯之主"],
    },
    "科幻": {
        "intro": "你醒在一座废弃设施里，应急灯一闪一闪。",
        "rooms": [
            "布满线缆的通道",
            "停机的实验舱",
            "被拆开的服务器间",
            "冷气泄漏的仓储区",
            "还在播放广告的走廊",
        ],
        "monsters": ["清洁机器人", "保安无人机", "变异实验体", "失控机械臂", "记忆清除者", "主机节点"],
        "bosses": ["失控主机", "母体重型机器人", "反叛的中央 AI"],
    },
}

_THEME_ALIASES = {
    "西幻": "西幻",
    "dnd": "西幻",
    "fantasy": "西幻",
    "克苏鲁": "克苏鲁",
    "coc": "克苏鲁",
    "cthulhu": "克苏鲁",
    "科幻": "科幻",
    "scifi": "科幻",
    "sci-fi": "科幻",
}


def _new_run(theme):
    return {
        "theme": theme,
        "floor": 1,
        "pos": 0,
        "plan": [],
        "hp": _PLAYER_HP,
        "max_hp": _PLAYER_HP,
        "atk": 6,
        "def": 0,
        "gold": 0,
        "potions": 3,
        "phase": "explore",
        "enemy": None,
    }


def _new_floor(run):
    if run["floor"] >= _MAX_FLOOR:
        run["plan"] = ["boss"]
    else:
        kinds = ["combat", "combat", "treasure", "trap", "rest", "event"]
        run["plan"] = [random.choice(kinds) for _ in range(2)] + ["stairs"]
    run["pos"] = 0


def _enemy(theme, floor, boss=False):
    if boss:
        return {
            "name": random.choice(_THEMES[theme]["bosses"]),
            "hp": 60 + random.randint(0, 10),
            "max_hp": 0,
            "atk": 6 + random.randint(0, 1),
            "gold": 50,
            "boss": True,
        }
    hp = 4 + floor * 2 + random.randint(0, 4)
    return {
        "name": random.choice(_THEMES[theme]["monsters"]),
        "hp": hp,
        "max_hp": hp,
        "atk": 1 + floor // 4 + random.randint(0, 1),
        "gold": 4 + floor * 2 + random.randint(0, 5),
        "boss": False,
    }


def _status(run):
    lines = [
        f"【文字地牢 · {run['theme']}】",
        f"第 {run['floor']}/{_MAX_FLOOR} 层　生命 {run['hp']}/{run['max_hp']}　"
        f"攻击 {run['atk']}　防御 {run['def']}",
        f"金币 {run['gold']}　药水 {run['potions']}",
    ]
    enemy = run.get("enemy")
    if run.get("phase") == "combat" and enemy:
        lines.append(f"敌人：{enemy['name']}　生命 {enemy['hp']}/{enemy['max_hp']}")
    return "\n".join(lines)


def _dead(store, run, text):
    run["phase"] = "dead"
    run["enemy"] = None
    stats = dict(store.get("stats") or {})
    stats["best_floor"] = max(int(stats.get("best_floor", 0)), int(run["floor"]))
    store["stats"] = stats
    store["run"] = run
    return {
        "reply": f"{text}\n💀 你倒在了第 {run['floor']} 层。\n"
                 f"最深 {stats['best_floor']} 层　/再来地牢 开新局",
        "store": store,
    }


def _win_battle(store, run):
    enemy = run["enemy"] or {}
    gold = int(enemy.get("gold", 0))
    run["gold"] += gold
    run["enemy"] = None
    run["phase"] = "explore"

    stats = dict(store.get("stats") or {})
    stats["kills"] = int(stats.get("kills", 0)) + 1

    extra = []
    if random.random() < 0.25 and run["potions"] < 5:
        run["potions"] += 1
        extra.append("药水 +1")
    if random.random() < 0.10:
        run["def"] += 1
        extra.append("护甲 +1")
    if random.random() < 0.15:
        run["atk"] += 1
        extra.append("武器 +1")

    if enemy.get("boss"):
        run["phase"] = "won"
        stats["wins"] = int(stats.get("wins", 0)) + 1
        stats["best_floor"] = _MAX_FLOOR
        store["stats"] = stats
        store["run"] = run
        return {
            "reply": f"🏆 {enemy.get('name', 'Boss')} 倒下了。\n"
                     f"你通关了十层地牢！金币 {run['gold']}　"
                     f"/再来地牢 开新局",
            "store": store,
        }

    run["pos"] = int(run["pos"]) + 1
    store["stats"] = stats
    store["run"] = run
    line = f"⚔ {enemy.get('name', '敌人')} 倒下了。金币 +{gold}"
    if extra:
        line += "　" + "　".join(extra)
    line += "\n/走 继续前进　/状态 查看状态"
    return {"reply": line, "store": store}


def _enemy_hit(store, run, mult=1.0):
    enemy = run["enemy"]
    damage = max(1, int((random.randint(1, 4) + enemy["atk"] - run["def"]) * mult))
    run["hp"] = max(0, int(run["hp"]) - damage)
    if run["hp"] <= 0:
        return _dead(store, run, f"{enemy['name']} 造成 {damage} 点伤害。")
    return None


def _enter_room(store, run):
    if run["pos"] >= len(run["plan"]):
        return _descend(store, run)

    kind = run["plan"][run["pos"]]
    theme = _THEMES[run["theme"]]

    if kind == "combat":
        enemy = _enemy(run["theme"], run["floor"])
        run["enemy"] = enemy
        run["phase"] = "combat"
        store["run"] = run
        flavor = random.choice(theme["rooms"])
        return {
            "reply": f"{flavor}。\n{enemy['name']} 挡住了去路！\n"
                     f"生命 {enemy['hp']}/{enemy['max_hp']}\n/攻击　/防御　/喝药　/逃跑",
            "store": store,
        }

    if kind == "boss":
        enemy = _enemy(run["theme"], run["floor"], boss=True)
        enemy["max_hp"] = enemy["hp"]
        run["enemy"] = enemy
        run["phase"] = "combat"
        store["run"] = run
        return {
            "reply": f"地牢最深处，{enemy['name']} 睁开了眼睛。\n"
                     f"生命 {enemy['hp']}/{enemy['max_hp']}\n"
                     "/攻击　/防御　/喝药　/逃跑",
            "store": store,
        }

    if kind == "stairs":
        return _descend(store, run)

    run["pos"] = int(run["pos"]) + 1

    if kind == "treasure":
        gold = random.randint(5, 15)
        run["gold"] += gold
        extra = []
        if random.random() < 0.35 and run["potions"] < 5:
            run["potions"] += 1
            extra.append("药水 +1")
        if random.random() < 0.20:
            run["atk"] += 1
            extra.append("武器 +1")
        if random.random() < 0.10:
            run["def"] += 1
            extra.append("护甲 +1")
        store["run"] = run
        text = f"你打开一个旧箱子，金币 +{gold}"
        if extra:
            text += "　" + "　".join(extra)
        return {"reply": text + "\n/走 继续前进", "store": store}

    if kind == "trap":
        damage = random.randint(3, 8)
        run["hp"] = max(0, int(run["hp"]) - damage)
        if run["hp"] <= 0:
            return _dead(store, run, f"你触发了陷阱，受到 {damage} 点伤害。")
        store["run"] = run
        return {"reply": f"你触发了陷阱，受到 {damage} 点伤害。\n/走 继续前进", "store": store}

    if kind == "rest":
        heal = min(10, run["max_hp"] - run["hp"])
        run["hp"] += heal
        run["potions"] = min(5, run["potions"] + (1 if random.random() < 0.2 else 0))
        store["run"] = run
        if heal:
            text = f"你休息了一会儿，回复 {heal} 点生命。"
        else:
            text = "你休息了一会儿，状态很好。"
        return {"reply": text + "\n/走 继续前进", "store": store}

    # event
    roll = random.random()
    if roll < 0.35:
        heal = min(6, run["max_hp"] - run["hp"])
        run["hp"] += heal
        text = f"你找到一处干净的泉水，回复 {heal} 点生命。"
    elif roll < 0.65:
        gold = random.randint(4, 10)
        run["gold"] += gold
        text = f"你捡到一些散落的钱币，金币 +{gold}。"
    elif roll < 0.85:
        damage = random.randint(2, 5)
        run["hp"] = max(0, int(run["hp"]) - damage)
        if run["hp"] <= 0:
            return _dead(store, run, f"墙上掉落的碎石砸中了你，受到 {damage} 点伤害。")
        text = f"墙上掉落的碎石砸中了你，受到 {damage} 点伤害。"
    else:
        run["atk"] += 1
        text = "你在墙角发现一块磨刀石，攻击 +1。"
    store["run"] = run
    return {"reply": text + "\n/走 继续前进", "store": store}


def _descend(store, run):
    if run["floor"] >= _MAX_FLOOR:
        run["phase"] = "won"
        store["run"] = run
        return {"reply": "你已经走到了地牢尽头。\n/再来地牢 开新局", "store": store}

    run["floor"] = int(run["floor"]) + 1
    stats = dict(store.get("stats") or {})
    stats["best_floor"] = max(int(stats.get("best_floor", 0)), int(run["floor"]))
    store["stats"] = stats
    _new_floor(run)
    store["run"] = run
    text = f"你走下石阶，来到第 {run['floor']} 层。"
    room = _enter_room(store, run)
    return {"reply": text + "\n" + room["reply"], "store": room["store"]}


def _attack(store, run):
    enemy = run["enemy"]
    damage = random.randint(2, 5) + int(run["atk"])
    enemy["hp"] = max(0, int(enemy["hp"]) - damage)
    lines = [
        f"你造成 {damage} 点伤害。{enemy['name']} 剩余 "
        f"{enemy['hp']}/{enemy['max_hp']}。"
    ]
    if enemy["hp"] <= 0:
        return _win_battle(store, run)

    counter = _enemy_hit(store, run)
    if counter:
        return counter
    lines.append(f"{enemy['name']} 反击，你剩余 {run['hp']} 点生命。")
    store["run"] = run
    return {"reply": "\n".join(lines) + "\n/攻击　/防御　/喝药　/逃跑", "store": store}


def _defend(store, run):
    enemy = run["enemy"]
    counter = _enemy_hit(store, run, mult=0.5)
    if counter:
        return counter
    store["run"] = run
    return {
        "reply": f"你举盾防御，只受到少量伤害。\n"
                 f"生命 {run['hp']}/{run['max_hp']}　"
                 f"{enemy['name']} 剩余 {enemy['hp']}/{enemy['max_hp']}\n"
                 "/攻击　/防御　/喝药　/逃跑",
        "store": store,
    }


def _potion(store, run):
    enemy = run["enemy"]
    if run["potions"] <= 0:
        return {"reply": "你没有药水了。", "store": store}
    run["potions"] = int(run["potions"]) - 1
    heal = min(_POTION_HEAL, run["max_hp"] - run["hp"])
    run["hp"] += heal
    counter = _enemy_hit(store, run)
    if counter:
        return counter
    store["run"] = run
    return {
        "reply": f"你喝下药水，回复 {heal} 点生命。\n"
                 f"生命 {run['hp']}/{run['max_hp']}　"
                 f"{enemy['name']} 剩余 {enemy['hp']}/{enemy['max_hp']}\n"
                 "/攻击　/防御　/喝药　/逃跑",
        "store": store,
    }


def _flee(store, run):
    enemy = run["enemy"]
    if random.random() < 0.5:
        run["enemy"] = None
        run["phase"] = "explore"
        run["pos"] = int(run["pos"]) + 1
        store["run"] = run
        return {"reply": "你成功脱离了战斗。\n/走 继续前进", "store": store}
    counter = _enemy_hit(store, run)
    if counter:
        return counter
    store["run"] = run
    return {
        "reply": f"逃跑失败，你被追着打了一下。\n"
                 f"生命 {run['hp']}/{run['max_hp']}　"
                 f"{enemy['name']} 剩余 {enemy['hp']}/{enemy['max_hp']}\n"
                 "/攻击　/防御　/喝药　/逃跑",
        "store": store,
    }


def _start(store, ctx):
    raw = (ctx.get("args") or [""])[0].strip().lower()
    theme = _THEME_ALIASES.get(raw)
    if theme is None:
        theme = random.choice(list(_THEMES))

    stats = dict(store.get("stats") or {})
    stats["runs"] = int(stats.get("runs", 0)) + 1
    store["stats"] = stats

    run = _new_run(theme)
    _new_floor(run)
    store["run"] = run
    room = _enter_room(store, run)
    return {
        "reply": f"{_THEMES[theme]['intro']}\n{room['reply']}",
        "store": room["store"],
    }


def handle(ctx):
    store = dict(ctx.get("store") or {})
    run = store.get("run")
    command = ctx.get("command") or ""

    if command in ("地牢", "再来地牢"):
        if run and run.get("phase") not in ("dead", "won", "retired"):
            return {
                "reply": _status(run) + "\n/状态　/背包　/撤退",
                "store": store,
            }
        if command == "再来地牢" or not run:
            return _start(store, ctx)
        return {
            "reply": _status(run) + "\n本局已结束，/再来地牢 开新局。",
            "store": store,
        }

    if not run:
        return {"reply": "还没有开始，发 /地牢 进入地牢。", "store": store}

    if run.get("phase") in ("dead", "won", "retired"):
        return {
            "reply": f"本局已经结束，最深 {run['floor']} 层。\n/再来地牢 开新局",
            "store": store,
        }

    if command == "状态":
        return {"reply": _status(run), "store": store}

    if command == "背包":
        return {
            "reply": f"药水 ×{run['potions']}　金币 {run['gold']}　"
                     f"攻击 {run['atk']}　防御 {run['def']}",
            "store": store,
        }

    if command == "撤退":
        run["retired"] = True
        run["phase"] = "retired"
        stats = dict(store.get("stats") or {})
        stats["best_floor"] = max(int(stats.get("best_floor", 0)), int(run["floor"]))
        store["stats"] = stats
        store["run"] = run
        return {
            "reply": f"你撤出了地牢，停在第 {run['floor']} 层。\n/再来地牢 开新局",
            "store": store,
        }

    if run.get("phase") == "combat":
        if command == "攻击":
            return _attack(store, run)
        if command == "防御":
            return _defend(store, run)
        if command == "喝药":
            return _potion(store, run)
        if command == "逃跑":
            return _flee(store, run)
        return {"reply": "战斗中：/攻击　/防御　/喝药　/逃跑", "store": store}

    if command == "走":
        return _enter_room(store, run)

    return {
        "reply": "可用指令：/走　/攻击　/防御　/喝药　/逃跑　/状态　/背包　/撤退",
        "store": store,
    }
