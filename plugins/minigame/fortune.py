"""每日运势 —— 单人、每天一次。"""

import hashlib

NAME = "每日运势"
VERSION = "1.0.0"
DESCRIPTION = "投 1D100，看看今天的运势。"
SCOPE = "solo"
MODE = "daily"
COMMANDS = {"运势": "看看今天的运势", "lucky": "看看今天的运势"}

_TIERS = (
    (1, "大凶"),
    (10, "凶"),
    (25, "末吉"),
    (45, "小吉"),
    (65, "中吉"),
    (85, "吉"),
    (100, "大吉"),
)


def _label(roll):
    for upper, name in _TIERS:
        if roll <= upper:
            return name
    return _TIERS[-1][1]


def handle(ctx):
    store = dict(ctx.get("store") or {})
    daily = dict(store.get("daily") or {})

    if daily.get("roll"):
        return {
            "reply": (
                f"今天已经抽过了：🎲 1D100 → {daily['roll']}　【{daily['label']}】\n"
                "明天再来。"
            ),
            "store": store,
        }

    raw = f"{ctx.get('user')}|{ctx.get('date')}".encode("utf-8")
    seed = int.from_bytes(hashlib.sha256(raw).digest()[:8], "big")
    roll = seed % 100 + 1
    label = _label(roll)

    daily["roll"] = roll
    daily["label"] = label
    store["daily"] = daily
    store["stats"] = {"total": int(store.get("stats", {}).get("total", 0)) + 1}

    return {
        "reply": f"你今日的运势是 🎲 1D100 → {roll}　【{label}】",
        "store": store,
    }
