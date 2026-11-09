"""每日 Boss —— 全群共享，每天一次。"""

import hashlib
import random

NAME = "每日 Boss"
VERSION = "1.1.0"
DESCRIPTION = "全群一起打 Boss，每人每天一次攻击。"
SCOPE = "group"
MODE = "daily"
COMMANDS = {"boss": "查看今日 Boss", "挑战": "挑战今日 Boss（每天一次）"}

_NAMES = [
    # COC7th：宇宙恐怖
    "星之眷族",
    "深潜者大祭司",
    "米·戈实验体",
    "廷达罗斯猎犬",
    "夜魇",
    "修格斯",
    "黄衣之王的化身",
    "奈亚拉托提普的阴影",
    # DND5e：西幻
    "深渊魔龙",
    "血月狼王",
    "堕落圣骑士",
    "亡灵巫妖",
    "石像鬼之王",
    "熔岩巨人",
    "冰霜巨龙",
    "混沌恶魔",
    # 妄想症2e：复古科技
    "失控的机房核心",
    "变异清洁机器人",
    "反叛的中央电脑",
    "快乐部主管",
    "失控的自动售货机",
    "巨型实验仓鼠",
    "错误代码聚合体",
    "服务器房的热浪",
    # 妄想症25th：荒诞科技
    "反物质咖啡机",
    "量产型战斗拖把",
    "全息广告巨像",
    "自检中的战斗机器人",
    "快乐部无人机群",
    "克隆体回收车",
    "记忆修正服务器",
    "自动点赞机",
]


def _daily(store, ctx):
    daily = dict(store.get("daily") or {})
    if "name" not in daily or "hp" not in daily:
        raw = f"{ctx.get('date', '')}|{ctx.get('group', '')}|boss".encode("utf-8")
        seed = hashlib.sha256(raw).digest()
        name = _NAMES[seed[0] % len(_NAMES)]
        hp = 50 + seed[1] % 101  # 50–150
        daily = {
            "name": name,
            "hp": hp,
            "max_hp": hp,
            "players": {},
            "killed": False,
        }
    return daily


def _top(daily):
    players = daily.get("players") or {}
    if not players:
        return "还没有人攻击。"
    rows = sorted(players.items(), key=lambda item: -int(item[1]))[:5]
    return "　".join(f"…{user[-4:]} {dmg}" for user, dmg in rows)


def handle(ctx):
    store = dict(ctx.get("store") or {})
    daily = _daily(store, ctx)
    command = ctx.get("command") or ""
    user = str(ctx.get("user") or "")

    if command == "boss":
        mine = daily["players"].get(user)
        lines = [
            f"👹 今日 Boss：{daily['name']}",
            f"生命 {daily['hp']}/{daily['max_hp']}",
            f"你的伤害：{mine if mine is not None else '未攻击'}",
            f"伤害榜：{_top(daily)}",
        ]
        if daily.get("killed"):
            lines.append("今天的 Boss 已被击败，明天再来。")
        else:
            lines.append("/挑战 每人每天一次")
        store["daily"] = daily
        return {"reply": "\n".join(lines), "store": store}

    if command == "挑战":
        if daily.get("killed"):
            return {"reply": "今天的 Boss 已经被打倒了，明天再来。", "store": store}
        if user in daily["players"]:
            return {
                "reply": f"你今天已经攻击过了，造成 {daily['players'][user]} 点伤害。",
                "store": store,
            }

        damage = random.randint(12, 28)
        daily["players"][user] = damage
        daily["hp"] = max(0, int(daily["hp"]) - damage)

        killed = daily["hp"] <= 0
        if killed:
            daily["killed"] = True
            stats = dict(store.get("stats") or {})
            stats["kills"] = int(stats.get("kills", 0)) + 1
            store["stats"] = stats

        store["daily"] = daily
        if killed:
            return {
                "reply": f"💥 你造成 {damage} 点伤害，{daily['name']} 倒下了！\n"
                         f"全群累计击杀 {store['stats']['kills']} 次。",
                "store": store,
            }
        return {
            "reply": f"⚔ 你造成 {damage} 点伤害。\n"
                     f"{daily['name']} 剩余 {daily['hp']}/{daily['max_hp']}。",
            "store": store,
        }

    return {"reply": "可用指令：/boss　/挑战", "store": store}
