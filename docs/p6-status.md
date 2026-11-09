# P6 状态说明（核心部分）

> 完成时间：2026-10-29
> 内容：受限表达式、规则包加载、角色卡、`/pc` 指令。

---

## 1. 受限表达式

`qqbot/expr.py`

| 允许 | 禁止 |
|---|---|
| 数字字面量 | 字符串 / 列表 / 字典 |
| 字段名 | 属性访问 `a.b` |
| `+ - * / // % **` | 函数定义 / lambda |
| `floor ceil min max abs round` | 下标 / 推导式 |
| 括号 | `import` / 任意函数调用 |

实现方式：用 `ast.parse` 解析后**自行递归求值**，不调用 `eval`。
未在白名单里的节点直接抛 `ExprError`。

限制：表达式 ≤ 500 字符，嵌套 ≤ 32 层，指数 ≤ 32。

已验证能拦住：

```
__import__('os').system('calc')
open('x')
().__class__
[x for x in range(3)]
lambda: 1
```

---

## 2. 规则包

`qqbot/rulepacks/loader.py`

```
plugins/<id>/
  manifest.yaml     # id / name / version / engine_version / type / reveal / permissions
  schema.yaml       # 字段定义
```

校验项：

| 检查 | 失败处理 |
|---|---|
| 目录名 = manifest.id | 拒绝加载 |
| `permissions` 非空 | 拒绝加载 |
| `engine_version` 不满足 | 拒绝加载 |
| `reveal` 非法 | 拒绝加载 |
| 字段类型未知 | 拒绝加载 |
| `expr` 语法/安全 | 拒绝加载 |
| 派生字段依赖成环 | 拒绝加载（附环路路径） |

**单个包失败不影响其它包**，错误写进日志并在界面显示。

### 字段类型

| type | 说明 |
|---|---|
| `int` | 整数，可设 `min` / `max` / `default` |
| `str` | 文本，`max` 为长度上限 |
| `bool` | 布尔 |
| `enum` | 枚举，需 `options` |
| `expr` | 公式派生 |
| `lookup` | 区间表，需 `source` + `table` |

---

## 3. 角色卡

`qqbot/cards.py` + `characters` 表。

- 每人每规则一张，主键 `(member_openid, pack_id, slot)`
- 建卡时按 schema 填默认值，再计算派生
- 派生值**不可直接修改**，改源字段后自动重算
- 渲染按 3 列排版，属性与派生值用分隔线隔开

### 内置样例：COC7th

13 个字段：9 项属性 + 移动 + 3 个派生（生命 / 魔法 / 理智）。

```yaml
- { key: hp,  type: expr, expr: "floor((con + siz) / 10)" }
- { key: mp,  type: expr, expr: "floor(pow / 5)" }
- { key: san, type: expr, expr: "pow" }
```

技能列表**尚未实现**，留到 P6.5。

---

## 4. `/pc` 指令

| 指令 | 行为 |
|---|---|
| `/pc new` | 建卡并展示 |
| `/pc show` | 查看自己的卡 |
| `/pc set <字段> <值>` | 支持中文名（力量）与英文字段名（str） |
| `/pc del` | 删除 |

不支持跨用户读取（与架构 D19 一致）。

---

## 5. 已验证

| 项 | 结果 |
|---|---|
| 单元测试 | **69 项通过** |
| 表达式安全 | ✅ 6 类恶意输入全部拦截 |
| 依赖成环检测 | ✅ 报出环路 |
| 非法 expr 拒绝 | ✅ |
| 打包带上规则包 | ✅ `bundled plugin: coc7th` |
| 规则包加载 | ✅ 13 字段，无错误 |
| `/pc new` | ✅ 生命 10 / 魔法 10 / 理智 50 |
| `/pc set 体质 80` | ✅ 生命自动变 13 |
| `/pc set 生命 5` | ✅ 拒绝（派生字段） |
| `/pc del` | ✅ |

---

## 6. P6.5 补充（技能 / 检定 / 理智）

| 能力 | 说明 |
|---|---|
| 技能表 | COC7th 内置 84 项技能与基础值，`type: skills` |
| 属性依赖基础值 | `base_expr`，如闪避 `floor(dex/2)`、母语 `edu` |
| 当前值 / 上限分离 | `hp/hp_max`、`mp/mp_max`、`san/san_max` |
| 手动值优先 | `/pc set 生命 4` 后不会被派生重算覆盖 |
| 技能检定 | `/check 侦查`，d100 + 规则包分级 |
| 理智检定 | `/sancheck 0/1d6`，独立指令，自动扣减并回写 |
| 表达式 | 新增比较（`< > <= >= == !=`）与布尔（`and or not`） |

`check.yaml` 结构：

```yaml
checks:
  skill:
    label: 技能检定
    dice: "1d100"
    target: skill
    outcomes:
      - { when: "roll == 1", label: 大成功, rank: 4 }
      - { when: "roll == 100 or (roll >= 96 and target < 50)", label: 大失败, rank: -1 }
      - { when: "roll <= floor(target / 5)", label: 极难成功, rank: 3 }
      - { when: "roll <= floor(target / 2)", label: 困难成功, rank: 2 }
      - { when: "roll <= target", label: 成功, rank: 1 }
      - { else: true, label: 失败, rank: 0 }
```

---

## 7. 房规（每群独立）

`groups.house_rule` 存 `default` / `hr2` / `hr3` / `hr4`。
`check.yaml` 里对应四套 outcomes id：`skill`、`skill_hr2`、`skill_hr3`、`skill_hr4`，
引擎按群的设置选 id，规则没有硬编码在 Python 里。

| 房规 | 大成功 | 大失败 |
|---|---|---|
| default | 01 | 目标 < 50：96–100；目标 ≥ 50：仅 100 |
| hr2 | 目标 ≥ 50 时 1–5，否则仅 01 | 同 default |
| hr3 | 不论目标 1–5 | 不论目标 96–100 |
| hr4 | 不论目标仅 01 | 不论目标仅 100 |

- `/rule` 查看本群房规，`/rule 1~4` 切换（群主 / 管理员）
- 切换成功会回复新的大成功 / 大失败判定说明
- 群列表里每个群也有下拉框，两种方式写同一份数据

### 每群独立规则包

`groups.rulepack` 存本群使用的规则包 id，空值表示用默认（第一个加载的）。

- `/rulepack` 列出所有规则包并标出本群当前使用的那套
- `/rulepack 2`、`/rulepack coc7th` 切换（群主 / 管理员）
- 角色卡按 `(member, pack_id)` 分开保存，切规则不会丢卡
- 规则包被删除或改名时自动回退到默认包

---

## 8. 代码插件（单文件 .py）

```
plugins/
  lucky.py      # NAME / DESCRIPTION / COMMANDS / def handle(ctx)
```

- 发现阶段用 `ast` 读元信息，**不执行**插件代码
- 执行阶段另起子进程，`sys.addaudithook` 拦截网络 / 写文件 / 子进程 / ctypes
- 主进程 3 秒超时强杀，错误码：`E3101` 崩溃、`E3102` 超时、`E3110` 越界操作
- 默认全部关闭，`code_plugins` 表保存启用状态 + 文件哈希
- 文件哈希变化 → 自动停用并提示重新启用
- `ctx`：`text / args / user / group / role / mode / date / card / store`
- 返回字符串，或 `{"reply": ..., "store": {...}}`（store 由主进程持久化）

主进程与子进程之间用 `runtime/` 下的临时 JSON 文件通信，
避免 PyInstaller `--noconsole` 下 stdout 为 `None` 的问题。

定位：**自己写的受信任扩展**。审计钩子不是内核级沙箱。

---

## 9. 单文件规则插件

```
plugins/trpg/coc7th.py
```

```python
NAME = "COC7th"
FIELDS = [...]
CHECKS = {...}
HOUSE_RULES = {...}
```

- 加载时用 `ast.literal_eval` 读取四个字面量，**不执行文件**
- 文件名 = 规则 id，限制 `[A-Za-z0-9_-]{1,40}`
- `load_py_source()` 先解析校验，通过后才写盘，坏文件不会落进 plugins
- 导入 / 导出 / 模板下载走管理 API，只处理文本
- `plugins/<id>/` 的 YAML 老格式仍兼容，同名时 `.py` 优先
- 规则插件可以声明 `HOUSE_RULES`，每群用 `/rule` 在声明范围内切换；
  没声明的规则，`/rule` 直接回复「没有定义房规」
- 界面可以启用 / 关闭规则；默认启用，至少保留一个，关闭后该规则不再出现在 `/rulepack` 列表
- `REVEAL = "roll-only"` 时 `/check` 只掷骰报值，不取目标、不判成败；
  `CHECKS.outcomes` 允许为空
- `CHECKS` 可声明 `direction: "gte"`（掷高）与 `dc: 15`，用于 DND5e
- DND 检定支持优势 / 劣势：`/check 运动 15 优势`、`/check 运动 15 劣势`
  （2d20 取高/低，不会叠加，优势与劣势同时存在时抵消）
- 字段可声明 `hide_if_default: True`，默认值不显示（熟练标记、备注常用）

内置规则插件：

| 文件 | 判定 | 说明 |
|---|---|---|
| `trpg/coc7th.py` | `full` | COC7th，84 项技能，四套房规 |
| `trpg/dnd5e.py` | `full` | DND5e，属性调整 + 熟练加值，d20 对抗 DC |
| `trpg/paranoia2e.py` | `roll-only` | 妄想症2e，8 项属性 + 派生，不录技能与隐藏信息 |
| `trpg/paranoia25th.py` | `roll-only` | 妄想症25th，六项技能 + 能量武器，不录 SECRET SIDE |

DND5e 已实现：技能 / 豁免 `d20 + 属性调整 + 熟练` 对抗 DC、优势 / 劣势、
攻击检定（自然 1 必失 / 20 重击）、对抗检定（双方比总值）、被动察觉数值。
未实现：专长 / 装备带来的额外加值、被动检定的 `/check` 指令。
规则依据：D&D Beyond Basic Rules (2014) / SRD 5.1 的能力检定、熟练、优势与被动检定章节。

### 规则 hook

规则文件可以声明以下函数，全部在代码插件子进程里执行（同样的审计钩子与 3 秒超时）：

| hook | 时机 | 返回 |
|---|---|---|
| `handle(ctx)` + `COMMANDS` | 群内发对应指令 | 字符串或 `{"reply", "card", "store"}` |
| `on_new(ctx)` | `/pc new` 掷完属性后 | `{"card": {...}, "reply": "..."}` |
| `on_check(ctx)` | `/check` 出结果后 | `{"reply": "...", "card": {...}}` |

- `ctx["card"]` 是当前卡；`ctx["store"]` 按「规则 + 群」隔离，存 `rule_store` 表
- `ctx["check"]` 含 `roll / target / label / rank / skill / check_id`
- 返回的 `card` 只接受规则里已声明的字段，派生字段会被忽略并重算
- hook 报错时：`on_new` 直接失败不建卡；`on_check` 保留默认结果并附错误码；
  指令返回错误码
- 指令名不能与引擎保留指令冲突，冲突的会在加载时被忽略并显示在错误列表

**含 hook 的规则默认关闭。** 界面列表里点「启用 hook」才执行，启用时记录文件哈希；
文件改动后自动关闭。纯声明规则不需要这一步，因为加载时本来就不会执行代码。

加载阶段仍然只做 AST 字面量解析，hook 函数体不会在加载时执行。

---

## 10. 小游戏插件

```
plugins/minigame/<id>.py
```

```python
NAME = "我的游戏"
VERSION = "0.1.0"
DESCRIPTION = "..."
SCOPE = "solo"   # solo 单人 | group 全群共享
MODE = "round"   # round 按局 | daily 每天一次
COMMANDS = {"demo": "示例指令"}

def handle(ctx): ...     # 必须
```

- 加载时只 AST 读 `NAME/VERSION/DESCRIPTION/COMMANDS/SCOPE/MODE`，不执行
- 默认关闭，界面逐个启用并记录文件哈希；文件改动自动停用
- **同一个群可以同时启用多款游戏**，指令直接响应，不需要 `/game start`
- `SCOPE="solo"`：状态存 `solo_store`，按「游戏 + 群 + 玩家」隔离
- `SCOPE="group"`：状态存 `game_store`，按「游戏 + 群」共享
- `MODE="daily"`：框架维护 `__date`，跨天自动清空 `store["daily"]`，保留 `store["stats"]`
- `MODE="round"`：状态由游戏自己管理，通常用 `store["active"]`
- 断线跨天不需要定时器：下次指令发现日期变了就会重置
- 指令名不能与引擎保留指令冲突，冲突的在加载时忽略
- 多款游戏指令重名时，先加载的占用，后加载的报错

内置游戏：

| 文件 | SCOPE | MODE | 说明 |
|---|---|---|---|
| `minigame/fortune.py` | solo | daily | 每日运势，兼容 `/lucky` |
| `minigame/fishing.py` | solo | daily | 每天一竿，31 种鱼/杂物，图鉴显示每种钓到次数 |
| `minigame/boss.py` | group | daily | 全群共享 Boss，名字与血量每天随机，每人每天一次攻击 |
| `minigame/blackjack.py` | solo | round | 21 点，一局一局 |
| `minigame/idiom.py` | solo | round | 猜成语，6 次机会 |
| `minigame/dungeon.py` | solo | round | 10 层线性文字地牢，西幻 / 克苏鲁 / 科幻三种主题，纯 roguelike |

所有游戏函数都走代码插件子进程：审计钩子、3 秒超时、错误码 `E3101 / E3102 / E3110`。
返回值支持 `{"reply": ..., "store": {...}}`；store 由主进程保存并在下次调用传回。

---

## 11. 模式插件

```
plugins/modes/<id>.py
```

```python
LABEL = "翻译模式"
DESCRIPTION = "把每句话翻译成英文"
CALL_LLM = True
ALLOW_KEYWORD = False
EXTRA_PROMPT = "只输出英文译文。"
HELP = "翻译模式：直接发要翻译的内容。"
```

模式是**管线声明**，不是代码：

| 字段 | 作用 |
|---|---|
| `CALL_LLM` | 非指令消息是否交给模型 |
| `ALLOW_KEYWORD` | 关键词规则是否生效 |
| `EXTRA_PROMPT` | 追加到系统提示词 |
| `HELP` | `/help` 内容 |

- 加载时只 AST 读取字面量，不执行文件
- 内置 `chat / trpg / minigame` 不能被覆盖
- 管线不再判断 `mode != "chat"`，而是读 `spec.call_llm` / `spec.allow_keyword`
- `/mode <id 或名称>` 切换；群列表里也可以直接选
- 界面支持导入、导出、下载模板、重新扫描
- 纯声明，所以不需要启用开关；导入后不会影响任何群，直到被选中

### 上下文隔离

对话历史与长期记忆的主键从 `(群, 人)` 改成 `(群, 人, 模式)`：

- 每个模式有独立的 thread、摘要和 pending 队列
- 切换模式不会把翻译、改写内容混进日常聊天
- 升级时旧数据自动迁移到 `chat` 模式，不丢记录
- 记忆列表会显示每条记忆属于哪个模式；编辑、删除都按模式操作
- 代价：每个会调用模型的模式都会各自消耗额度、各自占用记忆条目

---

## 12. 数据备份与恢复

界面「基础设置 → 数据备份」：

- **下载备份**：zip 内含 `data/bot.db`、`profiles/`、`plugins/` 和 `manifest.json`
- **恢复备份**：校验 zip 路径，SQLite 在线备份回写，恢复人设与插件，建议重启
- **清空业务数据**：清空群、角色卡、记忆、审计、游戏/插件启用状态和日志，
  保留账号配置、密钥和插件文件
- 备份不包含 `secrets.dat` / AppSecret / 模型 Key

恢复时拒绝绝对路径、`..`、`secrets.dat` 和未知顶层目录。

## 13. 检定补充

- COC：`/check 侦查 奖励1`、`/check 侦查 惩罚2`，最多各 2 颗，自动抵消
- DND：`/attack 15` 命中后按 `伤害骰 + 伤害加值` 结算，重击掷两次伤害骰
- DND：`/先攻` 掷 d20 + 先攻加值
