"""21 点 —— 单人、按局。"""

import random

NAME = "21点"
VERSION = "1.0.0"
DESCRIPTION = "和庄家比点数，一局一局来。"
SCOPE = "solo"
MODE = "round"
COMMANDS = {
    "开21": "开一局 21 点",
    "要牌": "再要一张牌",
    "停牌": "停牌并结算",
    "再来21": "上一局结束后再来一局",
}

_RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
_SUITS = ["♠", "♥", "♣", "♦"]


def _new_deck():
    deck = [rank + suit for suit in _SUITS for rank in _RANKS]
    random.shuffle(deck)
    return deck


def _value(card):
    rank = card[:-1]
    if rank == "A":
        return 11
    if rank in ("J", "Q", "K", "10"):
        return 10
    return int(rank)


def _total(cards):
    total = sum(_value(c) for c in cards)
    aces = sum(1 for c in cards if c[:-1] == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def _show(cards):
    return " ".join(cards)


def _new_round(store):
    deck = _new_deck()
    active = {
        "deck": deck,
        "player": [deck.pop(), deck.pop()],
        "dealer": [deck.pop(), deck.pop()],
        "done": False,
    }
    store["active"] = active
    return active


def _settle(store, active, reason=""):
    player = _total(active["player"])
    dealer = _total(active["dealer"])
    stats = dict(store.get("stats") or {})

    if player > 21:
        result = "爆牌，你输了"
        stats["losses"] = int(stats.get("losses", 0)) + 1
        stats["streak"] = 0
    else:
        while dealer < 17:
            active["dealer"].append(active["deck"].pop())
            dealer = _total(active["dealer"])
        if dealer > 21:
            result = "庄家爆牌，你赢了"
            stats["wins"] = int(stats.get("wins", 0)) + 1
            stats["streak"] = int(stats.get("streak", 0)) + 1
        elif player > dealer:
            result = "你赢了"
            stats["wins"] = int(stats.get("wins", 0)) + 1
            stats["streak"] = int(stats.get("streak", 0)) + 1
        elif player < dealer:
            result = "你输了"
            stats["losses"] = int(stats.get("losses", 0)) + 1
            stats["streak"] = 0
        else:
            result = "平手"
            stats["pushes"] = int(stats.get("pushes", 0)) + 1

    stats["best"] = max(int(stats.get("best", 0)), int(stats.get("streak", 0)))
    active["done"] = True
    active["result"] = result
    store["active"] = active
    store["stats"] = stats

    lines = [
        f"你：{_show(active['player'])}（{player}）",
        f"庄家：{_show(active['dealer'])}（{dealer}）",
        f"→ {result}",
    ]
    if reason:
        lines.append(reason)
    lines.append(f"战绩 {stats.get('wins', 0)} 胜 / {stats.get('losses', 0)} 负　"
                 f"连胜 {stats.get('streak', 0)}　/再来21 可开新局")
    return "\n".join(lines)


def handle(ctx):
    store = dict(ctx.get("store") or {})
    command = ctx.get("command") or ""
    active = store.get("active")

    if command == "再来21":
        if active and not active.get("done"):
            return {"reply": "这一局还没结束，先 /停牌 或继续 /要牌。", "store": store}
        active = _new_round(store)
        return {
            "reply": (
                f"🃏 新的一局\n你：{_show(active['player'])}（{_total(active['player'])}）\n"
                f"庄家明牌：{active['dealer'][0]}\n/要牌 或 /停牌"
            ),
            "store": store,
        }

    if command == "开21":
        if active and not active.get("done"):
            return {
                "reply": (
                    f"进行中：你 {_show(active['player'])}（{_total(active['player'])}）\n"
                    f"庄家明牌：{active['dealer'][0]}\n/要牌 或 /停牌"
                ),
                "store": store,
            }
        if active and active.get("done"):
            return {
                "reply": f"上一局：{active.get('result', '')}\n/再来21 开新局。",
                "store": store,
            }
        active = _new_round(store)
        if _total(active["player"]) == 21:
            return {
                "reply": _settle(store, active, "起手 21 点！"),
                "store": store,
            }
        return {
            "reply": (
                f"🃏 你：{_show(active['player'])}（{_total(active['player'])}）\n"
                f"庄家明牌：{active['dealer'][0]}\n/要牌 或 /停牌"
            ),
            "store": store,
        }

    if command == "要牌":
        if not active or active.get("done"):
            return {"reply": "没有进行中的牌局，先 /开21。", "store": store}
        active["player"].append(active["deck"].pop())
        total = _total(active["player"])
        if total > 21:
            return {"reply": _settle(store, active), "store": store}
        return {
            "reply": (
                f"🃏 你：{_show(active['player'])}（{total}）\n"
                f"庄家明牌：{active['dealer'][0]}\n/要牌 或 /停牌"
            ),
            "store": store,
        }

    if command == "停牌":
        if not active or active.get("done"):
            return {"reply": "没有进行中的牌局，先 /开21。", "store": store}
        return {"reply": _settle(store, active), "store": store}

    return {"reply": "可用指令：/开21　/要牌　/停牌　/再来21", "store": store}
