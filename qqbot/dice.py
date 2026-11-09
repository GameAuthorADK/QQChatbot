"""骰子表达式。

支持：1d20 / 3d6+2 / 2d20kh1 / d100 / 1d8+1d6
每次投骰都带种子，可复现、可审计。
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field

MAX_TERMS = 8
MAX_DICE = 100
MAX_FACES = 1000

_TERM_RE = re.compile(r"[+-]?[^+-]+")
_DICE_RE = re.compile(r"^(\d*)d(\d+)(?:k([hl])(\d+))?$")


@dataclass
class RollResult:
    ok: bool
    total: int = 0
    seed: int = 0
    detail: str = ""
    error: str = ""
    rolls: list[int] = field(default_factory=list)


def roll(expr: str, *, seed: int | None = None) -> RollResult:
    raw = (expr or "").strip().replace(" ", "").replace("D", "d")
    if not raw:
        return RollResult(False, error="请给出骰子表达式，例如 1d20")

    seed = seed if seed is not None else random.SystemRandom().randrange(1, 2**31)
    rng = random.Random(seed)

    terms = _TERM_RE.findall(raw)
    if not terms or "".join(terms) != raw:
        return RollResult(False, error=f"表达式看不懂：{expr}")
    if len(terms) > MAX_TERMS:
        return RollResult(False, error="项数太多了")

    total = 0
    parts: list[str] = []
    all_rolls: list[int] = []

    for term in terms:
        sign = -1 if term.startswith("-") else 1
        body = term.lstrip("+-")

        if "d" in body:
            m = _DICE_RE.match(body)
            if not m:
                return RollResult(False, error=f"骰子写法不对：{body}")
            count = int(m.group(1) or 1)
            faces = int(m.group(2))
            keep_mode = m.group(3)
            keep_n = int(m.group(4) or 1)

            if not (1 <= count <= MAX_DICE) or not (2 <= faces <= MAX_FACES):
                return RollResult(False, error="骰子数量或面数超出范围")

            rolls = [rng.randint(1, faces) for _ in range(count)]
            all_rolls.extend(rolls)

            if keep_mode:
                if not (1 <= keep_n <= count):
                    return RollResult(False, error="取高/取低的数量不合法")
                kept = sorted(rolls, reverse=(keep_mode == "h"))[:keep_n]
                value = sum(kept)
                parts.append(f"{body} {rolls} 取 {kept} = {value}")
            else:
                value = sum(rolls)
                parts.append(f"{body} {rolls} = {value}")
            total += sign * value
        else:
            if not body.isdigit():
                return RollResult(False, error=f"无法识别的部分：{body}")
            value = int(body)
            total += sign * value
            parts.append(f"{sign * value:+d}")

    return RollResult(True, total=total, seed=seed, detail="；".join(parts), rolls=all_rolls)


def roll_d100(bonus: int = 0, *, seed: int | None = None) -> RollResult:
    """COC 奖励骰 / 惩罚骰。

    bonus > 0 为奖励骰，< 0 为惩罚骰，绝对值最多 2 颗。
    个位骰不变，额外十位骰取最低（奖励）或最高（惩罚）。
    """
    bonus = max(-2, min(2, int(bonus)))
    if bonus == 0:
        return roll("1d100", seed=seed)

    seed = seed if seed is not None else random.SystemRandom().randrange(1, 2**31)
    rng = random.Random(seed)
    units = rng.randint(0, 9)
    tens = [rng.randrange(0, 10) for _ in range(1 + abs(bonus))]
    chosen = min(tens) if bonus > 0 else max(tens)
    value = chosen * 10 + units
    if value == 0:
        value = 100
    shown = [100 if t * 10 + units == 0 else t * 10 + units for t in tens]
    detail = (
        f"{'奖励' if bonus > 0 else '惩罚'}{abs(bonus)}："
        f"十位 {tens} 个位 {units} 取"
        f"{'低' if bonus > 0 else '高'} → {value}"
    )
    return RollResult(True, total=value, seed=seed, detail=detail, rolls=shown)


def roll_scaled(expr_text: str) -> RollResult:
    """支持 3d6*5 与 (2d6+6)*5 这种带倍数的写法。"""
    text = (expr_text or "").strip()
    mul = 1
    inner = text
    m = re.fullmatch(r"\((.+?)\)\s*\*\s*(\d+)", text) or re.fullmatch(
        r"(.+?)\s*\*\s*(\d+)", text
    )
    if m:
        inner, mul = m.group(1), int(m.group(2))
    result = roll(inner)
    if not result.ok:
        return result
    result.total *= mul
    if mul != 1:
        result.detail = f"({result.detail})×{mul}"
    return result


def format_roll(expr: str, result: RollResult, *, show_seed: bool = False) -> str:
    if not result.ok:
        return f"⚠ {result.error}"
    head = f"🎲 {expr} → {result.total}"
    tail = f"　（{result.detail}）" if result.detail else ""
    if show_seed:
        tail += f"\n种子 {result.seed}"
    return head + tail
