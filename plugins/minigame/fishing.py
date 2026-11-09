"""钓鱼 —— 单人、每天一次。"""

import random

NAME = "钓鱼"
VERSION = "1.1.0"
DESCRIPTION = "每天一竿，收集鱼种。"
SCOPE = "solo"
MODE = "daily"
COMMANDS = {"钓鱼": "今天钓一竿", "鱼图鉴": "查看收集进度"}

# 名称, 稀有度, 权重, 最小尺寸, 最大尺寸
_FISH = [
    ("鲫鱼", "普通", 30, 8, 30),
    ("鲤鱼", "普通", 25, 15, 60),
    ("草鱼", "普通", 20, 20, 80),
    ("鲈鱼", "普通", 15, 20, 70),
    ("黄颡鱼", "普通", 12, 10, 35),
    ("鳊鱼", "普通", 12, 20, 55),
    ("白条", "普通", 14, 8, 25),
    ("泥鳅", "普通", 10, 8, 20),
    ("罗非鱼", "普通", 10, 15, 40),
    ("鲢鱼", "普通", 8, 30, 90),
    ("鳙鱼", "普通", 7, 30, 100),
    ("青鱼", "普通", 5, 40, 120),
    ("旧靴子", "普通", 8, 20, 30),
    ("水草", "普通", 8, 10, 40),
    ("易拉罐", "普通", 6, 8, 12),
    ("黑鱼", "稀有", 6, 30, 90),
    ("鲶鱼", "稀有", 5, 30, 100),
    ("鳜鱼", "稀有", 4, 20, 60),
    ("翘嘴", "稀有", 4, 30, 80),
    ("鳟鱼", "稀有", 3, 20, 60),
    ("鳗鱼", "稀有", 3, 40, 120),
    ("河豚", "稀有", 2, 15, 45),
    ("生锈的怀表", "稀有", 2, 3, 8),
    ("破旧渔网", "稀有", 2, 20, 50),
    ("锦鲤", "史诗", 2, 30, 80),
    ("中华鲟", "史诗", 1, 80, 200),
    ("娃娃鱼", "史诗", 1, 40, 100),
    ("江豚", "史诗", 1, 100, 200),
    ("金色鳞片", "传说", 1, 1, 5),
    ("龙王令牌", "传说", 1, 10, 20),
    ("月光贝", "传说", 1, 5, 15),
]

_ORDER = ("普通", "稀有", "史诗", "传说")
_TOTAL = sum(item[2] for item in _FISH)


def _catch():
    point = random.randint(1, _TOTAL)
    for name, rarity, weight, low, high in _FISH:
        point -= weight
        if point <= 0:
            return name, rarity, random.randint(low, high)
    name, rarity, _, low, high = _FISH[-1]
    return name, rarity, random.randint(low, high)


def _book(caught, total):
    unique = sum(1 for name, *_ in _FISH if caught.get(name, 0) > 0)
    lines = [f"🎣 钓鱼图鉴　累计 {total} 竿　收集 {unique}/{len(_FISH)}"]
    for rarity in _ORDER:
        items = [item for item in _FISH if item[1] == rarity]
        if not items:
            continue
        lines.append(f"【{rarity}】")
        for name, *_ in items:
            lines.append(f"{name} ×{caught.get(name, 0)}")
    return "\n".join(lines)


def handle(ctx):
    store = dict(ctx.get("store") or {})
    daily = dict(store.get("daily") or {})
    stats = dict(store.get("stats") or {})
    caught = dict(stats.get("caught") or {})
    command = ctx.get("command") or ""

    if command == "鱼图鉴":
        return {"reply": _book(caught, int(stats.get("total", 0))), "store": store}

    if daily.get("fish"):
        return {
            "reply": (
                f"今天已经钓过了：{daily['fish']}（{daily['rarity']}，"
                f"{daily['size']} cm）\n明天再来。"
            ),
            "store": store,
        }

    fish, rarity, size = _catch()
    count = int(caught.get(fish, 0)) + 1
    daily.update({"fish": fish, "rarity": rarity, "size": size})
    stats["total"] = int(stats.get("total", 0)) + 1
    caught[fish] = count
    stats["caught"] = caught
    store["daily"] = daily
    store["stats"] = stats

    unique = sum(1 for name, *_ in _FISH if caught.get(name, 0) > 0)
    return {
        "reply": (
            f"🎣 钓到了：{fish}（{rarity}）\n"
            f"尺寸 {size} cm　第 {count} 次　图鉴 {unique}/{len(_FISH)}"
        ),
        "store": store,
    }
