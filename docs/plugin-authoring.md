# 插件编写指南

本文面向想自己写规则、游戏、模式或代码插件的人。

所有插件都是**单个 `.py` 文件**，放在程序目录的 `plugins/` 下。
加载阶段只读取模块顶层的字面量，**不执行代码**；需要执行的部分统一跑在子进程沙箱里。

```
plugins/
├─ trpg/                 规则插件
│  ├─ coc7th.py
│  ├─ dnd5e.py
│  └─ ...
├─ minigame/             小游戏插件
│  ├─ fishing.py
│  └─ ...
├─ modes/                模式插件
│  └─ translate.py
├─ goodies.py            代码插件（顶层 .py）
```

---

## 一、公共约定

| 项 | 说明 |
|---|---|
| 文件大小 | 规则/游戏/模式 ≤ 256–512 KB |
| 文件名 | 规则、游戏、代码插件：字母数字下划线短横线 |
| 指令名 | 游戏可用中文；不能含空格或标点 |
| 保留指令 | `/help`、`/mode`、`/roll`、`/check`、`/pc`、`/rule`、`/rulepack`、`/game`、`/wiki`、`/attack`、`/opposed`、`/initiative`、`/sancheck` 等不能被插件覆盖 |
| 启用 | 规则默认启用；游戏、模式、代码插件默认关闭，界面逐个启用 |
| 文件改动 | 启用状态记录文件哈希，改动后自动失效，需要重新启用 |
| 内置插件 | 不是文件，不能导入导出；在「模式与插件 → 内置插件」里整体开关（目前是 `/wiki`）。关闭时不显示它的具体设置 |

---

## 二、规则插件

目录：`plugins/trpg/<id>.py`

```python
NAME = "COC7th"
VERSION = "1.0.0"
DESCRIPTION = "..."
REVEAL = "full"          # full | roll-only

FIELDS = [
    {"key": "str", "label": "力量", "type": "int", "min": 1, "max": 99, "default": 50, "roll": "3d6*5"},
    {"key": "hp", "label": "生命", "type": "int", "min": 0, "default": 10, "default_expr": "hp_max"},
    {"key": "hp_max", "label": "生命上限", "type": "expr", "expr": "floor((con + siz) / 10)"},
    {"key": "skills", "label": "技能", "type": "skills",
     "catalog": [{"name": "侦查", "base": 25}, {"name": "闪避", "base_expr": "floor(dex / 2)"}]},
]

CHECKS = {
    "skill": {
        "label": "技能检定",
        "dice": "1d100",
        "target": "skill",
        "outcomes": [
            {"when": "roll == 1", "label": "大成功", "rank": 4},
            {"when": "roll <= target", "label": "成功", "rank": 1},
            {"else": True, "label": "失败", "rank": 0},
        ],
    },
}

HOUSE_RULES = {
    "default": {"name": "默认", "check": "skill", "crit": "...", "fumble": "..."},
}
```

### 字段类型

| type | 用途 |
|---|---|
| `int` / `str` / `bool` / `enum` | 普通可编辑字段 |
| `expr` | 自动计算，不可直接改 |
| `lookup` | 按区间查表 |
| `skills` | 技能表，支持 `base` / `base_expr` |

可选属性：

- `min` / `max`
- `default`
- `default_expr`：建卡时用公式取初值
- `roll`：建卡时投骰，如 `3d6*5`
- `hide_if_default`：默认值不显示
- `optional` / `max`

### `REVEAL`

| 值 | 行为 |
|---|---|
| `full` | 正常取目标、分级、公布成败 |
| `roll-only` | 只掷骰报值，不判成败；`outcomes` 可为空 |

### 表达式限制

只允许数字、字段名、`+ - * / // % **`、比较、`and/or/not`、`floor/ceil/min/max/abs/round`。
禁止属性访问、下标、函数定义、lambda、import。

---

## 三、小游戏插件

目录：`plugins/minigame/<id>.py`

```python
NAME = "钓鱼"
VERSION = "1.0.0"
DESCRIPTION = "每天一竿，收集鱼种。"
SCOPE = "solo"     # solo 单人 | group 全群共享
MODE = "daily"     # daily 每天一次 | round 按局
COMMANDS = {"钓鱼": "今天钓一竿", "鱼图鉴": "查看图鉴"}

def handle(ctx):
    store = dict(ctx.get("store") or {})
    daily = dict(store.get("daily") or {})
    if daily.get("done"):
        return {"reply": "今天已经钓过了。", "store": store}
    daily["done"] = True
    store["daily"] = daily
    return {"reply": "钓到一条鱼。", "store": store}
```

### `SCOPE`

| 值 | 状态存储 | 说明 |
|---|---|---|
| `solo` | `solo_store`，按游戏 + 群 + 玩家 | 同一个群可多人各玩各的 |
| `group` | `game_store`，按游戏 + 群 | 全群共享，如每日 Boss |

### `MODE`

| 值 | 行为 |
|---|---|
| `daily` | 框架维护 `__date`；跨天自动清空 `store["daily"]`，保留 `store["stats"]` |
| `round` | 状态完全由插件管理，通常放 `store["active"]` |

- 每天一次的游戏把当天状态放 `store["daily"]`，长期统计放 `store["stats"]`
- 按局的游戏结束后自己清空 `active`，或提供 `/再来xxx`
- 游戏启用后直接响应指令，不需要 `/game start`
- 同一个群可以同时启用多款游戏
- 启用游戏会记录哈希，文件改动后自动停用

### `ctx`

```
event / command / text / args / user / group / role / mode / date
card   当前群使用的角色卡（可能为 None）
store  游戏状态
```

返回字符串，或 `{"reply": "...", "store": {...}}`。

---

## 四、模式插件

目录：`plugins/modes/<id>.py`

```python
LABEL = "翻译模式"
DESCRIPTION = "把每句话翻译成英文"
CALL_LLM = True
ALLOW_KEYWORD = False
EXTRA_PROMPT = "只输出英文译文。"
HELP = "翻译模式：直接发要翻译的内容。"
```

| 字段 | 作用 |
|---|---|
| `CALL_LLM` | 非指令消息是否交给模型 |
| `ALLOW_KEYWORD` | 关键词规则是否生效 |
| `EXTRA_PROMPT` | 追加到系统提示词 |
| `HELP` | `/help` 内容 |

- 模式是管线声明，不执行代码
- 内置 `chat / trpg / minigame` 不可覆盖
- 每个模式有独立的对话历史和记忆
- `/mode <id 或名称>` 切换

---

## 五、代码插件

目录：`plugins/*.py`（只扫描顶层）

```python
NAME = "示例"
COMMANDS = {"hello": "打个招呼"}

def handle(ctx):
    return "你好"
```

- 默认关闭，必须界面启用
- 跑在独立子进程：禁网、禁写文件、禁子进程、禁 ctypes
- 3 秒超时
- 错误码：`E3101` 崩溃、`E3102` 超时、`E3110` 越界操作
- 文件改动后自动停用

`ctx` 包含 `text / args / user / group / role / mode / date / card / store`。

---

## 六、导入与导出

「模式与插件」页面：

- 规则：导入 `.py`、导出、下载模板、启用/关闭
- 小游戏：导入 `.py`、导出、下载模板、启用/关闭
- 模式：导入、导出、下载模板
- 代码插件：扫描 `plugins/*.py`，逐个启用

导入前会先解析校验，失败不会落盘。

---

## 七、安全边界

- 规则/游戏/模式的声明部分只做 AST 字面量读取，不执行
- 代码插件、规则 hook、游戏 `handle` 在子进程沙箱运行
- 沙箱不是内核级隔离，挡不住精心构造的底层绕过
- 只运行自己写的或可信来源的 `.py`
- 备份不包含密钥；恢复时拒绝 `secrets.dat` 和路径穿越

---

## 八、调试建议

1. 先下载模板，改最小字段
2. 点「重新扫描」，看「加载错误」
3. 用试聊窗口跑指令
4. 规则检查先用 `/pc new`，再 `/check`
5. 游戏 daily 先测第二次是否提示「今天已经…」
6. 改文件后记得重新启用 hook / 游戏 / 代码插件
