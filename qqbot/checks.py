"""检定求值：按规则包声明的 outcomes 依次匹配。"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

from . import cards, expr
from .dice import roll as roll_dice, roll_d100
from .rulepacks import Rulepack


@dataclass
class CheckResult:
    ok: bool
    label: str = ""
    roll: int = 0
    target: int = 0
    rank: int = 0
    direction: str = "lte"
    dc: int = 0
    rolls: list[int] = field(default_factory=list)
    bonus_dice: int = 0
    detail: str = ""
    error: str = ""


@dataclass
class AttackResult:
    ok: bool
    roll: int = 0
    rolls: list[int] = field(default_factory=list)
    bonus: int = 0
    total: int = 0
    ac: int = 0
    label: str = ""
    advantage: int = 0
    error: str = ""


@dataclass
class OpposedResult:
    ok: bool
    name: str = ""
    own_roll: int = 0
    own_rolls: list[int] = field(default_factory=list)
    bonus: int = 0
    own_total: int = 0
    opp_roll: int = 0
    opp_bonus: int = 0
    opp_total: int = 0
    outcome: str = ""
    advantage: int = 0
    error: str = ""


@dataclass
class SanResult:
    ok: bool
    roll: int = 0
    target: int = 0
    success: bool = False
    fumble: bool = False
    loss: int = 0
    before: int = 0
    after: int = 0
    detail: str = ""
    loss_expr: str = ""
    error: str = ""


_DICE_TERM = re.compile(r"(\d*)d(\d+)", re.I)


def _numeric_env(data: dict) -> dict:
    env = {}
    for k, v in data.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            env[k] = v
    return env


def skill_value(pack: Rulepack, data: dict, name: str) -> int | None:
    return cards.skill_value(pack, data, name)


def _field_value(pack: Rulepack, data: dict, name: str) -> int | None:
    """按 key 或 label 找一个数值字段（DND 的技能/豁免加值）。"""
    field = pack.by_key().get(name)
    if field is None:
        for item in pack.fields:
            if item.label == name:
                field = item
                break
    if field is None:
        return None
    value = data.get(field.key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    return None


def run_check(
    pack: Rulepack,
    data: dict,
    check_id: str,
    arg: str,
    dc: int | None = None,
    advantage: int = 0,
    bonus_dice: int = 0,
) -> CheckResult:
    spec = pack.checks.get(check_id)
    if spec is None:
        return CheckResult(False, error="该规则包没有定义检定规则")

    if spec.target == "skill":
        if not arg:
            hint = "运动 15" if spec.direction == "gte" else "侦查"
            return CheckResult(False, error=f"请指定技能，例如 /check {hint}")
        target = skill_value(pack, data, arg)
        if target is None:
            target = _field_value(pack, data, arg)
        if target is None:
            return CheckResult(False, error=f"没有这个技能或字段：{arg}")
    elif arg.isdigit():
        target = int(arg)
    else:
        target = _field_value(pack, data, spec.target)
        if target is None:
            value = data.get(spec.target)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                target = int(value)
        if target is None:
            return CheckResult(False, error=f"没有这个属性：{spec.target}")

    dice_expr = spec.dice
    if advantage and dice_expr.replace(" ", "").lower() == "1d20":
        dice_expr = "2d20kh1" if advantage > 0 else "2d20kl1"
    if bonus_dice and dice_expr.replace(" ", "").lower() == "1d100":
        rolled = roll_d100(bonus_dice)
    else:
        rolled = roll_dice(dice_expr)
    if not rolled.ok:
        return CheckResult(False, error=rolled.error)
    value = rolled.total

    env = _numeric_env(data)
    env.update({"roll": value, "target": target, "dc": int(dc or spec.dc)})

    for item in spec.outcomes:
        if item["else"]:
            chosen = item
            break
        try:
            if expr.evaluate_bool(item["when"], env):
                chosen = item
                break
        except expr.ExprError:
            continue
    else:
        chosen = {"label": "失败", "rank": 0}

    return CheckResult(
        True,
        label=chosen["label"],
        roll=value,
        target=target,
        rank=int(chosen.get("rank") or 0),
        direction=spec.direction,
        dc=int(dc or spec.dc),
        rolls=rolled.rolls,
        bonus_dice=bonus_dice,
        detail=rolled.detail,
    )


def _d20(advantage: int = 0, seed: int | None = None):
    if advantage > 0:
        return roll_dice("2d20kh1", seed=seed)
    if advantage < 0:
        return roll_dice("2d20kl1", seed=seed)
    return roll_dice("1d20", seed=seed)


def run_attack(
    pack: Rulepack,
    data: dict,
    ac: int,
    advantage: int = 0,
    seed: int | None = None,
) -> AttackResult:
    bonus = _field_value(pack, data, "attack_bonus")
    if bonus is None:
        bonus = _field_value(pack, data, "攻击加值")
    if bonus is None:
        return AttackResult(False, error="当前规则没有攻击加值字段")

    rolled = _d20(advantage, seed)
    if not rolled.ok:
        return AttackResult(False, error=rolled.error)

    total = rolled.total + bonus
    if rolled.total == 20:
        label = "重击"
    elif rolled.total == 1:
        label = "必失"
    elif total >= ac:
        label = "命中"
    else:
        label = "未命中"

    return AttackResult(
        True,
        roll=rolled.total,
        rolls=rolled.rolls,
        bonus=bonus,
        total=total,
        ac=ac,
        label=label,
        advantage=advantage,
    )


def run_opposed(
    pack: Rulepack,
    data: dict,
    name: str,
    opp_bonus: int,
    advantage: int = 0,
    seed: int | None = None,
) -> OpposedResult:
    spec = next(
        (item for item in pack.checks.values() if item.direction == "gte"), None
    )
    if spec is None:
        return OpposedResult(False, error="当前规则不支持对抗检定")

    bonus = skill_value(pack, data, name)
    if bonus is None:
        bonus = _field_value(pack, data, name)
    if bonus is None:
        return OpposedResult(False, error=f"没有这个技能或字段：{name}")

    own = _d20(advantage, seed)
    if not own.ok:
        return OpposedResult(False, error=own.error)
    opp = _d20(0, seed + 1 if seed is not None else None)
    if not opp.ok:
        return OpposedResult(False, error=opp.error)

    own_total = own.total + bonus
    opp_total = opp.total + opp_bonus
    if own_total > opp_total:
        outcome = "你胜"
    elif own_total < opp_total:
        outcome = "对方胜"
    else:
        outcome = "平手，局面不变"

    return OpposedResult(
        True,
        name=name,
        own_roll=own.total,
        own_rolls=own.rolls,
        bonus=bonus,
        own_total=own_total,
        opp_roll=opp.total,
        opp_bonus=opp_bonus,
        opp_total=opp_total,
        outcome=outcome,
        advantage=advantage,
    )


def _amount(expr_text: str, rng: random.Random | None = None) -> int:
    text = (expr_text or "0").strip()
    if not text:
        return 0
    if text.isdigit():
        return int(text)
    r = roll_dice(text)
    return r.total if r.ok else 0


def _max_amount(expr_text: str) -> int:
    """大失败时取最大值。"""
    text = (expr_text or "0").strip()
    if text.isdigit():
        return int(text)
    total = 0
    for m in _DICE_TERM.finditer(text):
        count = int(m.group(1) or 1)
        faces = int(m.group(2))
        total += count * faces
    return total or 1


def parse_san_expr(text: str) -> tuple[str, str]:
    """支持 0/1d6、1/1d10 这种写法。"""
    raw = (text or "").strip()
    if "/" in raw:
        a, b = raw.split("/", 1)
        return a.strip() or "0", b.strip() or "0"
    if raw:
        return "0", raw
    return "0", "1d6"


def _amount_ok(text: str) -> bool:
    t = (text or "").strip()
    return bool(t) and roll_dice(t).ok


def run_san(pack: Rulepack, data: dict, text: str) -> SanResult:
    san = data.get("san")
    if not isinstance(san, (int, float)):
        return SanResult(False, error="角色卡上没有理智值")
    san = int(san)

    ok_expr, fail_expr = parse_san_expr(text)
    for expr in (ok_expr, fail_expr):
        if not _amount_ok(expr):
            return SanResult(
                False, error=f"损失写法看不懂：{expr}（示例：/sancheck 0/1d6）"
            )
    rolled = roll_dice("1d100")
    if not rolled.ok:
        return SanResult(False, error=rolled.error)
    roll = rolled.total

    success = roll <= san
    # 大失败：目标 ≥50 时 100；否则 96–100
    fumble = (roll == 100) if san >= 50 else (roll >= 96)

    if fumble:
        loss = _max_amount(fail_expr)
        detail = "大失败，损失取最大值"
    else:
        loss = _amount(fail_expr if not success else ok_expr)
        detail = "失败" if not success else "成功"

    before = san
    after = max(0, san - loss)
    return SanResult(
        True,
        roll=roll,
        target=san,
        success=success and not fumble,
        fumble=fumble,
        loss=loss,
        before=before,
        after=after,
        detail=detail,
        loss_expr=fail_expr if (fumble or not success) else ok_expr,
    )
