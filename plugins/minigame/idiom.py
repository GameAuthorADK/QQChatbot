"""猜成语 —— 单人、按局。"""

import random

NAME = "猜成语"
VERSION = "1.0.0"
DESCRIPTION = "六次机会猜一个四字成语。"
SCOPE = "solo"
MODE = "round"
COMMANDS = {
    "猜": "猜一个四字成语",
    "成语": "查看当前进度",
    "放弃成语": "公布答案",
    "再来成语": "开新的一局",
}

_RAW = """
一心一意 一马当先 一鸣惊人 一箭双雕 一举两得 一诺千金 一败涂地 一视同仁
一帆风顺 一叶知秋 一目了然 一意孤行 一鼓作气 一清二白 一刀两断 一石二鸟
一落千丈 一往无前 一表人才 一丝不苟 画蛇添足 画龙点睛 画饼充饥 杯弓蛇影
守株待兔 亡羊补牢 掩耳盗铃 刻舟求剑 井底之蛙 塞翁失马 叶公好龙 东施效颦
邯郸学步 滥竽充数 自相矛盾 买椟还珠 南辕北辙 拔苗助长 狐假虎威 对牛弹琴
卧薪尝胆 破釜沉舟 背水一战 完璧归赵 负荆请罪 三顾茅庐 草木皆兵 四面楚歌
指鹿为马 望梅止渴 闻鸡起舞 凿壁偷光 悬梁刺股 程门立雪 孟母三迁 乐不思蜀
江郎才尽 东山再起 卷土重来 胸有成竹 熟能生巧 水滴石穿 铁杵成针 愚公移山
精卫填海 夸父逐日 牛郎织女 八仙过海 点石成金 火眼金睛 神通广大 腾云驾雾
呼风唤雨 天马行空 龙飞凤舞 龙争虎斗 藏龙卧虎 生龙活虎 如虎添翼 虎头蛇尾
马到成功 万马奔腾 老马识途 走马观花 蛛丝马迹 鸡飞狗跳 鹤立鸡群 狼吞虎咽
调虎离山 引狼入室 狡兔三窟 兔死狐悲 狗急跳墙 鱼跃龙门 浑水摸鱼 缘木求鱼
如鱼得水 鱼目混珠 春暖花开 鸟语花香 花好月圆 月明星稀 风和日丽 山清水秀
湖光山色 风景如画 生机勃勃 万紫千红 绿树成荫 硕果累累 五谷丰登 白雪皑皑
秋高气爽 烈日炎炎 狂风暴雨 电闪雷鸣 雨过天晴 云开雾散 学而不厌 温故知新
不耻下问 精益求精 持之以恒 锲而不舍 全神贯注 专心致志 废寝忘食 夜以继日
争分夺秒 名列前茅 出类拔萃 才华横溢 博学多才 见多识广 融会贯通 举一反三
循序渐进 脚踏实地 助人为乐 拾金不昧 见义勇为 大公无私 舍己为人 尊老爱幼
和睦相处 同心协力 众志成城 齐心协力 团结一致 风雨同舟 同甘共苦 患难与共
肝胆相照 推心置腹 亲密无间 形影不离 情同手足 若无其事 从容不迫 泰然自若
镇定自若 心平气和 平心静气 心安理得 问心无愧 光明磊落 实事求是 兢兢业业
任劳任怨 埋头苦干 默默无闻 无私奉献 目瞪口呆 大惊小怪 惊弓之鸟 惊慌失措
魂飞魄散 提心吊胆 胆战心惊 毛骨悚然 不寒而栗 心有余悸 兴高采烈 欢天喜地
喜出望外 眉开眼笑 笑逐颜开 手舞足蹈 喜气洋洋 心花怒放 乐不可支 愁眉苦脸
忧心忡忡 闷闷不乐 垂头丧气 无精打采 唉声叹气 泪流满面 痛哭流涕 悲痛欲绝
心如刀割 三心二意 见异思迁 半途而废 有始无终 朝三暮四 朝令夕改 出尔反尔
言而无信 自食其果
"""

_WORDS = list(
    dict.fromkeys(
        word for word in _RAW.split() if len(word) == 4
    )
)


def _feedback(guess, answer):
    marks = ["⬛"] * 4
    used = [False] * 4

    for i in range(4):
        if guess[i] == answer[i]:
            marks[i] = "🟩"
            used[i] = True

    for i in range(4):
        if marks[i] == "🟩":
            continue
        for j in range(4):
            if not used[j] and guess[i] == answer[j]:
                marks[i] = "🟨"
                used[j] = True
                break
    return "".join(marks)


def _new_round(store):
    store["active"] = {
        "answer": random.choice(_WORDS),
        "guesses": [],
        "left": 6,
        "done": False,
        "win": False,
    }
    return store["active"]


def _board(active):
    lines = [f"剩余 {active['left']} 次"]
    for guess, marks in active["guesses"]:
        lines.append(f"{guess}　{marks}")
    return "\n".join(lines)


def handle(ctx):
    store = dict(ctx.get("store") or {})
    command = ctx.get("command") or ""
    active = store.get("active")

    if command == "再来成语":
        if active and not active.get("done"):
            return {"reply": "这一局还没结束，继续 /猜 或 /放弃成语。", "store": store}
        _new_round(store)
        return {"reply": "新的一局，开始猜吧。\n/猜 四字成语", "store": store}

    if command == "成语":
        if not active:
            return {"reply": "还没有开始。\n/猜 四字成语", "store": store}
        text = _board(active)
        if active.get("done"):
            text += f"\n本局结束。答案：{active['answer']}\n/再来成语 开新局"
        return {"reply": text, "store": store}

    if command == "放弃成语":
        if not active or active.get("done"):
            return {"reply": "没有进行中的一局，/猜 四字成语 开始。", "store": store}
        active["done"] = True
        active["win"] = False
        stats = dict(store.get("stats") or {})
        stats["losses"] = int(stats.get("losses", 0)) + 1
        stats["streak"] = 0
        store["stats"] = stats
        return {
            "reply": f"本局放弃。答案：{active['answer']}\n/再来成语 开新局",
            "store": store,
        }

    if command == "猜":
        args = ctx.get("args") or []
        guess = (args[0] if args else "").strip()

        if not active:
            active = _new_round(store)

        if active.get("done"):
            return {
                "reply": f"本局已经结束，答案：{active['answer']}\n/再来成语 开新局",
                "store": store,
            }

        if len(guess) != 4:
            return {"reply": "请输入一个四字成语，例如 /猜 画蛇添足。", "store": store}
        if guess not in _WORDS:
            return {"reply": "词库里没有这个成语，不扣次数。", "store": store}
        if any(item[0] == guess for item in active["guesses"]):
            return {"reply": "这个成语已经猜过了，不扣次数。", "store": store}

        marks = _feedback(guess, active["answer"])
        active["guesses"].append([guess, marks])
        active["left"] = int(active["left"]) - 1

        if guess == active["answer"]:
            active["done"] = True
            active["win"] = True
            stats = dict(store.get("stats") or {})
            stats["wins"] = int(stats.get("wins", 0)) + 1
            stats["streak"] = int(stats.get("streak", 0)) + 1
            stats["best"] = max(int(stats.get("best", 0)), stats["streak"])
            store["stats"] = stats
            store["active"] = active
            return {
                "reply": f"{_board(active)}\n🎉 猜中了！答案：{active['answer']}\n"
                         f"连胜 {stats['streak']}　/再来成语 开新局",
                "store": store,
            }

        if active["left"] <= 0:
            active["done"] = True
            stats = dict(store.get("stats") or {})
            stats["losses"] = int(stats.get("losses", 0)) + 1
            stats["streak"] = 0
            store["stats"] = stats
            store["active"] = active
            return {
                "reply": f"{_board(active)}\n次数用完了。答案：{active['answer']}\n"
                         "/再来成语 开新局",
                "store": store,
            }

        store["active"] = active
        return {
            "reply": f"{_board(active)}\n继续 /猜 四字成语",
            "store": store,
        }

    return {"reply": "可用指令：/猜 成语　/成语　/放弃成语　/再来成语", "store": store}
