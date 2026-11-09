"""规则包加载与校验。

插件目录结构：
  plugins/<id>/
    manifest.yaml
    schema.yaml
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import expr, yamlutil
from ..paths import PLUGINS_DIR

log = logging.getLogger(__name__)

ENGINE_VERSION = (1, 0)
VALID_TYPES = {"int", "str", "bool", "enum", "expr", "lookup", "skills"}
VALID_REVEAL = {"full", "roll-only", "hidden"}


class PackError(Exception):
    pass


@dataclass
class Field:
    key: str
    label: str
    type: str
    min: float | None = None
    max: float | None = None
    default: object = None
    default_expr: str | None = None
    expr: str | None = None
    source: str | None = None
    table: list[dict] | None = None
    options: list[str] | None = None
    optional: bool = False
    max_length: int = 200
    catalog: list[dict] = field(default_factory=list)
    roll_expr: str | None = None
    hide_if_default: bool = False


@dataclass
class CheckSpec:
    id: str
    label: str
    dice: str = "1d100"
    target: str = "skill"
    direction: str = "lte"
    dc: int = 15
    outcomes: list[dict] = field(default_factory=list)


@dataclass
class Rulepack:
    id: str
    name: str
    version: str
    type: str
    reveal: str
    description: str = ""
    fields: list[Field] = field(default_factory=list)
    checks: dict[str, CheckSpec] = field(default_factory=dict)
    house_rules: dict[str, dict] = field(default_factory=dict)
    commands: dict[str, str] = field(default_factory=dict)
    hooks: set[str] = field(default_factory=set)
    file_hash: str = ""
    source: str = "yaml"
    path: Path | None = None

    def by_key(self) -> dict[str, Field]:
        return {f.key: f for f in self.fields}


def _check_engine(spec: str) -> bool:
    """极简版本约束：支持 >=x、<y、<=x、>y 的组合。"""
    if not spec:
        return True
    major, minor = ENGINE_VERSION
    current = major + minor / 100.0
    for part in str(spec).replace(",", " ").split():
        m = re.fullmatch(r"(>=|<=|>|<)?\s*(\d+)(?:\.(\d+))?", part.strip())
        if not m:
            continue
        op = m.group(1) or "=="
        ver = int(m.group(2)) + int(m.group(3) or 0) / 100.0
        if op == ">=" and not (current >= ver):
            return False
        if op == ">" and not (current > ver):
            return False
        if op == "<=" and not (current <= ver):
            return False
        if op == "<" and not (current < ver):
            return False
        if op == "==" and current != ver:
            return False
    return True


def _parse_field(raw: dict) -> Field:
    key = str(raw.get("key") or "").strip()
    if not key:
        raise PackError("字段缺少 key")
    ftype = str(raw.get("type") or "int").strip()
    if ftype not in VALID_TYPES:
        raise PackError(f"字段 {key} 的类型不支持：{ftype}")

    f = Field(
        key=key,
        label=str(raw.get("label") or key),
        type=ftype,
        min=raw.get("min"),
        max=raw.get("max"),
        default=raw.get("default"),
        optional=bool(raw.get("optional", False)),
        max_length=int(raw.get("max") or 200),
        hide_if_default=bool(raw.get("hide_if_default", False)),
    )

    if ftype == "expr":
        if not raw.get("expr"):
            raise PackError(f"字段 {key} 缺少 expr")
        try:
            expr.validate(str(raw["expr"]))
        except expr.ExprError as exc:
            raise PackError(f"字段 {key} 的表达式非法：{exc}") from exc
        f.expr = str(raw["expr"])

    if raw.get("default_expr"):
        try:
            expr.validate(str(raw["default_expr"]))
        except expr.ExprError as exc:
            raise PackError(f"字段 {key} 的 default_expr 非法：{exc}") from exc
        f.default_expr = str(raw["default_expr"])

    if raw.get("roll"):
        text = str(raw["roll"]).strip()
        dice_part = text
        mul = 1
        m = re.fullmatch(r"\((.+?)\)\s*\*\s*(\d+)", text) or re.fullmatch(
            r"(.+?)\s*\*\s*(\d+)", text
        )
        if m:
            dice_part, mul = m.group(1), int(m.group(2))
        from ..dice import roll as _roll

        probe = _roll(dice_part, seed=1)
        if not probe.ok:
            raise PackError(f"字段 {key} 的 roll 非法：{probe.error}")
        f.roll_expr = text if mul == 1 else f"({dice_part})*{mul}"

    if ftype == "lookup":
        if not raw.get("source") or not raw.get("table"):
            raise PackError(f"字段 {key} 的 lookup 需要 source 与 table")
        if not isinstance(raw["table"], list) or len(raw["table"]) > 200:
            raise PackError(f"字段 {key} 的 table 非法")
        f.source = str(raw["source"])
        f.table = raw["table"]

    if ftype == "enum":
        opts = raw.get("options")
        if not isinstance(opts, list) or not opts:
            raise PackError(f"字段 {key} 的 enum 需要 options")
        f.options = [str(o) for o in opts]

    if ftype == "skills":
        catalog = raw.get("catalog")
        if not isinstance(catalog, list) or not catalog:
            raise PackError(f"字段 {key} 的 skills 需要 catalog")
        if len(catalog) > 300:
            raise PackError(f"字段 {key} 的技能条目过多")
        cleaned = []
        for item in catalog:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            base = item.get("base", 0)
            base_expr = item.get("base_expr")
            if base_expr:
                expr.validate(str(base_expr))
            try:
                base_val = int(float(base))
            except (TypeError, ValueError):
                base_val = 0
            cleaned.append(
                {
                    "name": name,
                    "base": max(0, min(99, base_val)),
                    "base_expr": str(base_expr) if base_expr else None,
                }
            )
        if not cleaned:
            raise PackError(f"字段 {key} 的 catalog 为空")
        f.catalog = cleaned

    return f


def _parse_check(raw_id: str, raw: dict, allow_empty: bool = False) -> CheckSpec:
    label = str(raw.get("label") or raw_id)
    dice = str(raw.get("dice") or "1d100")
    target = str(raw.get("target") or "skill")
    direction = str(raw.get("direction") or "lte").lower()
    if direction not in ("lte", "gte"):
        raise PackError(f"检定 {raw_id} 的 direction 只能是 lte 或 gte")
    try:
        dc = int(raw.get("dc") or 15)
    except (TypeError, ValueError) as exc:
        raise PackError(f"检定 {raw_id} 的 dc 必须是数字") from exc
    if not (1 <= dc <= 100):
        raise PackError(f"检定 {raw_id} 的 dc 必须在 1–100")

    outcomes = raw.get("outcomes")
    if isinstance(outcomes, list) and not outcomes and allow_empty:
        return CheckSpec(
            id=raw_id,
            label=label,
            dice=dice,
            target=target,
            direction=direction,
            dc=dc,
            outcomes=[],
        )
    if not isinstance(outcomes, list) or not outcomes:
        raise PackError(f"检定 {raw_id} 缺少 outcomes")

    cleaned = []
    has_else = False
    for item in outcomes:
        if not isinstance(item, dict):
            continue
        text = str(item.get("label") or "").strip()
        if not text:
            continue
        when = item.get("when")
        if when:
            try:
                expr.validate(str(when))
            except expr.ExprError as exc:
                raise PackError(f"检定 {raw_id} 的条件非法：{exc}") from exc
        elif item.get("else"):
            has_else = True
        else:
            raise PackError(f"检定 {raw_id} 的条目需要 when 或 else")
        cleaned.append(
            {
                "when": str(when) if when else None,
                "else": bool(item.get("else")),
                "label": text,
                "rank": int(item.get("rank", 0)),
            }
        )

    if not cleaned or not has_else:
        raise PackError(f"检定 {raw_id} 必须有一条 else 兜底")

    return CheckSpec(id=raw_id, label=label, dice=dice, target=target,
                     direction=direction, dc=dc, outcomes=cleaned)


def _parse_house_rules(raw: object) -> dict[str, dict]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise PackError("HOUSE_RULES 必须是字典")
    out: dict[str, dict] = {}
    for key, item in raw.items():
        if not isinstance(item, dict):
            raise PackError(f"房规 {key} 必须是字典")
        hid = str(key)[:24]
        out[hid] = {
            "name": str(item.get("name") or hid)[:40],
            "check": str(item.get("check") or "skill")[:32],
            "crit": str(item.get("crit") or "")[:120],
            "fumble": str(item.get("fumble") or "")[:120],
        }
    return out


def _parse_fields(raw_list: list, pack_id: str) -> list[Field]:
    fields: list[Field] = []
    for raw in raw_list:
        if not isinstance(raw, dict):
            raise PackError(f"{pack_id}: 字段必须是字典")
        fields.append(_parse_field(raw))

    keys = {f.key for f in fields}
    deps: dict[str, set[str]] = {}
    for f in fields:
        refs: set[str] = set()
        if f.type == "expr" and f.expr:
            refs = {k for k in keys if re.search(rf"\b{re.escape(k)}\b", f.expr)}
        elif f.type == "lookup" and f.source:
            refs = {f.source} & keys
        deps[f.key] = refs
    _assert_acyclic(deps)
    return fields


def load_pack(pack_dir: Path) -> Rulepack:
    manifest_path = pack_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise PackError(f"{pack_dir.name}: 缺少 manifest.yaml")

    man = yamlutil.load_file(manifest_path)
    pack_id = str(man.get("id") or pack_dir.name).strip()

    if pack_id != pack_dir.name:
        raise PackError(f"目录名 {pack_dir.name} 与 id {pack_id} 不一致")

    if not _check_engine(str(man.get("engine_version") or "")):
        raise PackError(f"{pack_id}: engine_version 不满足（当前 1.0）")

    perms = man.get("permissions") or []
    if perms:
        raise PackError(f"{pack_id}: 不允许申请权限 {perms}")

    reveal = str(man.get("reveal") or "full")
    if reveal not in VALID_REVEAL:
        raise PackError(f"{pack_id}: reveal 非法")

    fields: list[Field] = []
    schema_path = pack_dir / "schema.yaml"
    if schema_path.exists():
        doc = yamlutil.load_file(schema_path)
        fields = _parse_fields(doc.get("fields") or [], pack_id)

    checks: dict[str, CheckSpec] = {}
    house_rules: dict[str, dict] = {}
    checks_path = pack_dir / "check.yaml"
    if checks_path.exists():
        doc = yamlutil.load_file(checks_path)
        for cid, craw in (doc.get("checks") or {}).items():
            if isinstance(craw, dict):
                checks[str(cid)] = _parse_check(
                    str(cid), craw, allow_empty=(reveal == "roll-only")
                )
        house_rules = _parse_house_rules(doc.get("house_rules"))

    return Rulepack(
        id=pack_id,
        name=str(man.get("name") or pack_id),
        version=str(man.get("version") or "0.0.0"),
        type=str(man.get("type") or "rulepack"),
        reveal=reveal,
        description=str(man.get("description") or ""),
        fields=fields,
        checks=checks,
        house_rules=house_rules,
        source="yaml",
        path=pack_dir,
    )


def _assert_acyclic(deps: dict[str, set[str]]) -> None:
    state: dict[str, int] = {}

    def visit(node: str, stack: list[str]) -> None:
        if state.get(node) == 2:
            return
        if state.get(node) == 1:
            raise PackError(f"字段依赖成环：{' → '.join(stack + [node])}")
        state[node] = 1
        for nxt in deps.get(node, ()):
            visit(nxt, stack + [node])
        state[node] = 2

    for k in deps:
        visit(k, [])


def load_py_pack(path: Path) -> Rulepack:
    try:
        if path.stat().st_size > 512 * 1024:
            raise PackError(f"{path.name}: 文件过大（上限 512 KB）")
        source = path.read_text("utf-8", errors="replace")
    except PackError:
        raise
    except Exception as exc:
        raise PackError(f"{path.name}: 读取失败：{exc}") from exc

    pack = load_py_source(source, path.stem, path=path)
    pack.source = "py"
    return pack


def load_py_source(
    source: str, pack_id: str, path: Path | None = None
) -> Rulepack:
    """从单文件规则插件读取声明。只解析字面量，绝不执行文件。"""
    import ast

    pack_id = str(pack_id).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,40}", pack_id):
        raise PackError("规则 id 只能包含字母、数字、下划线和短横线（1–40 字符）")

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise PackError(
            f"{pack_id}: 第 {exc.lineno} 行语法错误：{exc.msg}"
        ) from exc

    wanted = {
        "NAME",
        "VERSION",
        "DESCRIPTION",
        "FIELDS",
        "CHECKS",
        "HOUSE_RULES",
        "COMMANDS",
        "REVEAL",
    }
    found: dict[str, object] = {}
    hooks: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name in {
            "handle",
            "on_new",
            "on_check",
        }:
            hooks.add(node.name)
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in wanted:
                try:
                    found[target.id] = ast.literal_eval(node.value)
                except Exception as exc:
                    raise PackError(
                        f"{pack_id}: {target.id} 必须是字面量"
                        "（不能调用函数、引用变量或写运算）"
                    ) from exc

    raw_fields = found.get("FIELDS")
    if not isinstance(raw_fields, list) or not raw_fields:
        raise PackError(f"{pack_id}: FIELDS 必须是非空列表")
    fields = _parse_fields(raw_fields, pack_id)

    reveal = str(found.get("REVEAL") or "full")
    if reveal not in VALID_REVEAL:
        raise PackError(f"{pack_id}: REVEAL 只能是 full / roll-only / hidden")

    checks: dict[str, CheckSpec] = {}
    raw_checks = found.get("CHECKS") or {}
    if not isinstance(raw_checks, dict):
        raise PackError(f"{pack_id}: CHECKS 必须是字典")
    for cid, craw in raw_checks.items():
        if not isinstance(craw, dict):
            raise PackError(f"{pack_id}: 检定 {cid} 必须是字典")
        checks[str(cid)] = _parse_check(
            str(cid), craw, allow_empty=(reveal == "roll-only")
        )

    house_rules = _parse_house_rules(found.get("HOUSE_RULES"))
    for key, rule in house_rules.items():
        if rule["check"] not in checks:
            raise PackError(
                f"{pack_id}: 房规 {key} 指向不存在的检定 {rule['check']}"
            )

    raw_commands = found.get("COMMANDS") or {}
    if not isinstance(raw_commands, dict):
        raise PackError(f"{pack_id}: COMMANDS 必须是字典")
    commands: dict[str, str] = {}
    for name, desc in raw_commands.items():
        cmd = str(name).strip().lower()
        if not re.fullmatch(r"[a-z0-9_]{1,24}", cmd):
            raise PackError(
                f"{pack_id}: 指令名 {name} 非法（只能小写字母、数字、下划线）"
            )
        commands[cmd] = str(desc)[:80]
    if len(commands) > 20:
        raise PackError(f"{pack_id}: 指令最多 20 个")
    if commands and "handle" not in hooks:
        raise PackError(f"{pack_id}: 声明了 COMMANDS 但没有 handle(ctx)")
    if "handle" in hooks and not commands:
        raise PackError(f"{pack_id}: 声明了 handle 但没有 COMMANDS")

    return Rulepack(
        id=pack_id,
        name=str(found.get("NAME") or pack_id)[:60],
        version=str(found.get("VERSION") or "0.0.0")[:20],
        type="rulepack",
        reveal=reveal,
        description=str(found.get("DESCRIPTION") or "")[:300],
        fields=fields,
        checks=checks,
        house_rules=house_rules,
        commands=commands,
        hooks=hooks,
        file_hash=hashlib.sha256(source.encode("utf-8")).hexdigest(),
        source="py",
        path=path,
    )


def load_all(base: Path | None = None) -> tuple[list[Rulepack], list[str]]:
    """返回 (成功加载的规则包, 错误列表)。错误不影响其它包。

    目录布局：
      plugins/trpg/*.py     单文件规则插件（优先）
      plugins/<id>/         旧的 YAML 规则包（兼容）
    """
    base = base or PLUGINS_DIR
    packs: list[Rulepack] = []
    errors: list[str] = []
    if not base.exists():
        return packs, errors

    retired = {"coc7e": "coc7th", "paranoia25": "paranoia25th"}
    py_ids: set[str] = set()
    trpg_dir = base / "trpg"
    if trpg_dir.is_dir():
        for path in sorted(trpg_dir.glob("*.py")):
            if path.name.startswith("_"):
                continue
            if path.stem in retired and (trpg_dir / f"{retired[path.stem]}.py").exists():
                log.info("规则 %s 已改名为 %s，忽略旧文件 %s", path.stem, retired[path.stem], path.name)
                continue
            try:
                pack = load_py_pack(path)
            except Exception as exc:
                errors.append(str(exc))
                log.warning("规则插件加载失败 %s: %s", path.name, exc)
                continue
            if pack.id in py_ids:
                errors.append(f"{pack.id}: 存在重复的规则插件，已跳过 {path.name}")
                continue
            py_ids.add(pack.id)
            packs.append(pack)

    for d in sorted(base.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in ("trpg", "minigame", "modes"):
            continue
        if d.name in retired and retired[d.name] in py_ids:
            log.info("规则 %s 已改名为 %s，忽略旧 YAML 目录", d.name, retired[d.name])
            continue
        try:
            pack = load_pack(d)
        except Exception as exc:
            errors.append(str(exc))
            log.warning("规则包加载失败 %s: %s", d.name, exc)
            continue
        if pack.id in py_ids:
            log.info("规则 %s 已由 plugins/trpg 下的 .py 提供，忽略同名 YAML 包", pack.id)
            continue
        packs.append(pack)
    return packs, errors


RULE_TEMPLATE = '''"""我的规则 —— 单文件规则插件模板。

放在 plugins/trpg/ 下，文件名就是规则 id，例如 myrule.py。
加载时只读取下面的字面量，不会执行文件里的代码。

可用字段类型：
  int(str/bool/enum)  普通值，可设 min / max / default
  expr                公式派生，例：{"key": "power", "type": "expr", "expr": "hp + atk"}
  skills              技能表，catalog 里每项 {"name": "侦查", "base": 25}
  lookup              区间表（较少用）

roll 写法：3d6*5、(2d6+6)*5、1d10

CHECKS 里每一步按顺序匹配，必须有一条 {"else": True, ...} 兜底。
表达式只能用字段名、数字、+ - * / // % **、比较、and/or/not、
floor/ceil/min/max/abs/round，不能写函数、属性或 import。

可选 hook（都在子进程沙箱里执行，禁止联网 / 写文件 / 启动程序）：
  COMMANDS + handle(ctx)   自定义指令，ctx 里有 card / args / store
  on_new(ctx)              /pc new 之后，返回 {"card": {...}, "reply": "..."}
  on_check(ctx)            /check 之后，返回 {"reply": "...", "card": {...}}
不写 hook 时，这个文件只被当作数据读取，不会执行任何代码。
"""

NAME = "我的规则"
VERSION = "0.1.0"
DESCRIPTION = "一句话说明这套规则用来做什么"

FIELDS = [
    {"key": "hp", "label": "生命", "type": "int", "min": 0, "max": 20, "default": 10},
    {"key": "atk", "label": "攻击", "type": "int", "min": 0, "max": 20, "default": 5},
    {"key": "power", "label": "战力", "type": "expr", "expr": "hp + atk"},
]

CHECKS = {
    "skill": {
        "label": "检定",
        "dice": "1d10",
        "target": "atk",
        "outcomes": [
            {"when": "roll == 1", "label": "大成功", "rank": 4},
            {"when": "roll <= target", "label": "成功", "rank": 1},
            {"else": True, "label": "失败", "rank": 0},
        ],
    },
}

# 可选：自定义指令。声明 COMMANDS 就必须写 handle(ctx)。
# COMMANDS = {"fate": "抽一张命运卡"}
#
# def handle(ctx):
#     return "命运说：今天适合早睡"
#
# 可选：建卡后调整。只能改已声明字段，派生值会自动重算。
# def on_new(ctx):
#     return {"card": {"hp": 12}, "reply": "额外说明"}
#
# 可选：检定后追加内容。
# def on_check(ctx):
#     return {"reply": f"（{ctx['check']['label']}）"}
#
# hook 在独立子进程里运行，禁止联网 / 写文件 / 启动其它程序，3 秒超时。

# 可选：房规。check 指向上面 CHECKS 里的某个 id。
# HOUSE_RULES = {
#     "default": {
#         "name": "默认",
#         "check": "skill",
#         "crit": "01 才算大成功",
#         "fumble": "100 才算大失败",
#     },
# }
'''

