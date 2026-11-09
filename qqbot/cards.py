"""角色卡：建卡、校验、派生计算、渲染。"""

from __future__ import annotations

import re

from . import expr
from .dice import roll_scaled
from .rulepacks import Field, Rulepack

DERIVED = ("expr", "lookup")


def defaults(pack: Rulepack) -> dict:
    out: dict = {}
    deferred: list[Field] = []

    for f in pack.fields:
        if f.type in DERIVED or f.type == "skills":
            continue
        if f.default_expr:
            deferred.append(f)
            continue
        out[f.key] = _default_for(f)

    # 技能依赖属性，放在属性之后
    for f in pack.fields:
        if f.type == "skills":
            out[f.key] = _skill_defaults(f, out)

    # 派生值（含 *_max）先算出来，才能给 hp/san 这类当前值取初值
    out = compute(pack, out)

    for f in deferred:
        try:
            out[f.key] = int(expr.evaluate(f.default_expr or "0", out))
        except expr.ExprError:
            out[f.key] = _default_for(f)

    return out


def _skill_defaults(f: Field, env: dict) -> dict:
    values: dict[str, int] = {}
    for item in f.catalog:
        values[item["name"]] = _skill_base(item, env)
    return values


def skill_field(pack: Rulepack) -> Field | None:
    for f in pack.fields:
        if f.type == "skills":
            return f
    return None


def skill_names(pack: Rulepack) -> list[str]:
    f = skill_field(pack)
    return [i["name"] for i in f.catalog] if f else []


def find_skill(pack: Rulepack, name: str) -> str | None:
    f = skill_field(pack)
    if not f:
        return None
    name = (name or "").strip()
    for item in f.catalog:
        if item["name"] == name:
            return name
    # 允许前缀匹配，例如「格斗」匹配「格斗（斗殴）」
    for item in f.catalog:
        if item["name"].startswith(name):
            return item["name"]
    return None


def skill_value(pack: Rulepack, data: dict, name: str) -> int | None:
    """返回技能值；卡上没有这项时回退到规则里的初始值。"""
    f = skill_field(pack)
    if not f:
        return None
    real = find_skill(pack, name)
    if not real:
        return None
    table = data.get(f.key) or {}
    if real in table:
        try:
            return int(table[real])
        except (TypeError, ValueError):
            pass
    for item in f.catalog:
        if item["name"] == real:
            return _skill_base(item, data)
    return 0


def set_skill(pack: Rulepack, data: dict, name: str, raw) -> tuple[bool, str]:
    f = skill_field(pack)
    if not f:
        return False, "该规则包没有技能列表"
    real = find_skill(pack, name)
    if not real:
        return False, f"没有这个技能：{name}"
    try:
        val = int(float(str(raw).strip()))
    except (TypeError, ValueError):
        return False, "技能值需要是数字"
    if not (0 <= val <= 99):
        return False, "技能值必须在 0–99 之间"
    table = dict(data.get(f.key) or {})
    table[real] = val
    data[f.key] = table
    return True, ""


def _default_for(f: Field):
    if f.default is not None:
        return f.default
    if f.type == "int":
        return int(f.min if f.min is not None else 0)
    if f.type == "bool":
        return False
    if f.type == "enum":
        return (f.options or [""])[0]
    return ""


def coerce(pack: Rulepack, key: str, raw: str):
    """把用户输入转成字段类型，返回 (value, error)。"""
    fields = pack.by_key()
    f = fields.get(key)
    if f is None:
        return None, f"没有这个字段：{key}"
    if f.type in DERIVED:
        return None, f"{f.label} 是自动计算的，不能直接改"
    if f.type == "skills":
        return None, "技能请按技能名设置，例如 /pc set 侦查 60"

    text = str(raw).strip()
    if f.type == "int":
        try:
            val = int(float(text))
        except (TypeError, ValueError):
            return None, f"{f.label} 需要是数字"
        if f.min is not None and val < float(f.min):
            return None, f"{f.label} 不能小于 {int(float(f.min))}"
        if f.max is not None and val > float(f.max):
            return None, f"{f.label} 不能大于 {int(float(f.max))}"
        return val, ""

    if f.type == "bool":
        return text.lower() in ("1", "true", "yes", "是", "on"), ""

    if f.type == "enum":
        if text not in (f.options or []):
            return None, f"{f.label} 只能是：{'、'.join(f.options or [])}"
        return text, ""

    return text[: f.max_length], ""


def compute(pack: Rulepack, data: dict) -> dict:
    """按依赖顺序计算派生字段。"""
    out = dict(data)
    fields = pack.by_key()
    pending = [f for f in pack.fields if f.type in DERIVED]

    for _ in range(len(pending) + 1):
        if not pending:
            break
        progressed = False
        for f in list(pending):
            if f.type == "expr":
                refs = {k for k in fields if re.search(rf"\b{re.escape(k)}\b", f.expr or "")}
                if any(r not in out for r in refs):
                    continue
                try:
                    val = expr.evaluate(f.expr or "0", out)
                    out[f.key] = int(val)
                except expr.ExprError:
                    out[f.key] = None
            else:
                src = out.get(f.source or "")
                if src is None:
                    continue
                out[f.key] = expr.lookup(f.table or [], float(src))
            pending.remove(f)
            progressed = True
        if not progressed:
            break
    return out


def apply_updates(pack: Rulepack, data: dict, updates: dict) -> tuple[dict, list[str]]:
    """应用 hook 返回的字段更新。

    只接受规则包已声明的字段；派生字段忽略（由 compute 重算）。
    返回 (新的卡, 实际写入的字段列表)。
    """
    out = dict(data)
    fields = pack.by_key()
    applied: list[str] = []

    for raw_key, value in (updates or {}).items():
        key = str(raw_key)
        f = fields.get(key)
        if f is None or f.type in DERIVED:
            continue

        if f.type == "skills":
            if not isinstance(value, dict):
                continue
            table = dict(out.get(f.key) or {})
            for name, raw in value.items():
                real = find_skill(pack, str(name))
                if not real:
                    continue
                try:
                    num = int(float(raw))
                except (TypeError, ValueError):
                    continue
                if 0 <= num <= 99:
                    table[real] = num
            out[f.key] = table
            applied.append(f.key)
            continue

        coerced, err = coerce(pack, key, value)
        if err:
            continue
        out[key] = coerced
        applied.append(key)

    if applied:
        out = compute(pack, out)
    return out, applied


def _hidden(f: Field, data: dict) -> bool:
    if not f.hide_if_default:
        return False
    current = data.get(f.key)
    default = f.default
    if default is None:
        if f.type == "int":
            default = int(f.min if f.min is not None else 0)
        elif f.type == "bool":
            default = False
        else:
            default = ""
    return current == default


def render(pack: Rulepack, data: dict, *, title: str = "") -> str:
    lines: list[str] = []
    head = f"【{pack.name}】"
    if title:
        head += f" {title}"
    lines.append(head)

    basic = [
        f
        for f in pack.fields
        if f.type not in DERIVED and f.type != "skills" and not _hidden(f, data)
    ]
    keys = pack.by_key()
    derived = [
        f
        for f in pack.fields
        if f.type in DERIVED
        and not (f.key.endswith("_max") and f.key[: -len("_max")] in keys)
    ]
    skills = [f for f in pack.fields if f.type == "skills"]

    for row in _wrap(basic, 3):
        lines.append("　".join(_cell(f, data) for f in row))

    if derived:
        lines.append("――――――")
        for row in _wrap(derived, 3):
            lines.append("　".join(_cell(f, data) for f in row))

    for f in skills:
        lines.append("――――――")
        lines.append(_skills_block(f, data.get(f.key) or {}, data))

    return "\n".join(lines)


def roll_new(pack: Rulepack) -> dict:
    """建卡时按规则包声明的 roll 掷属性，其余照默认值。"""
    data = defaults(pack)

    rolled_any = False
    for f in pack.fields:
        if not f.roll_expr:
            continue
        result = roll_scaled(f.roll_expr)
        if not result.ok:
            continue
        value = int(result.total)
        if f.min is not None:
            value = max(int(float(f.min)), value)
        if f.max is not None:
            value = min(int(float(f.max)), value)
        data[f.key] = value
        rolled_any = True

    if not rolled_any:
        return data

    # 属性变了，技能基础值与派生值都要重算
    for f in pack.fields:
        if f.type == "skills":
            data[f.key] = _skill_defaults(f, data)
    data = compute(pack, data)
    for f in pack.fields:
        if f.default_expr:
            try:
                data[f.key] = int(expr.evaluate(f.default_expr, data))
            except expr.ExprError:
                pass
    return data


def _skill_base(item: dict, env: dict) -> int:
    base = item.get("base", 0)
    expr_text = item.get("base_expr")
    if expr_text:
        try:
            base = int(expr.evaluate(expr_text, env))
        except expr.ExprError:
            base = 0
    return max(0, min(99, int(base)))


def _skills_block(f: Field, values: dict, env: dict) -> str:
    cat = {i["name"]: _skill_base(i, env) for i in f.catalog}
    changed = [
        (name, int(val))
        for name, val in values.items()
        if name in cat and int(val) != int(cat[name])
    ]
    if not changed:
        return f"【{f.label}】全部为基础值"
    changed.sort(key=lambda x: -x[1])
    rows = []
    for i in range(0, len(changed), 3):
        rows.append("　".join(f"{n} {v}" for n, v in changed[i : i + 3]))
    return f"【{f.label}】\n" + "\n".join(rows)


def _cell(f: Field, data: dict) -> str:
    val = data.get(f.key)
    if f.type == "int":
        mx = data.get(f"{f.key}_max")
        if isinstance(mx, (int, float)):
            return f"{f.label} {_fmt(val)}/{int(mx)}"
    return f"{f.label} {_fmt(val)}"


def _wrap(items: list, per: int):
    for i in range(0, len(items), per):
        yield items[i : i + per]


def _fmt(value) -> str:
    if value is None:
        return "-"
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value)
