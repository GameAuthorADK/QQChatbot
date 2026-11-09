# 规则包角色卡规格（Card Spec）

> 本文定义角色卡的收录边界与 schema 约定。
> 参考物：`Paranoia2E半自动角色卡.xlsx`（5 页签）。

---

## 1. 收录原则

> **录正面，不录背面；录得起，就录。**

角色卡在 bot 里的定位是**公开信息的记录本**——不是判定工具，也不是保密容器。

判断一个字段该不该录，看三条，优先级从高到低：

| 判据 | 说明 |
|---|---|
| ① **是否属于隐藏信息** | **硬性排除**。卡面上标 `SECRET` / `CLASSIFIED` 的一律不录 |
| ② **录入成本是否可承受** | 字段数量、建卡时是否需要逐项输入 |
| ③ **是否高频变动** | 高频变动且价值低的，交给玩家自己记 |

**注意：「是否参与判定」不是判据。** 裸骰模式下所有字段都不参与判定，但公开数据依然值得记录——`/pc show`、复盘、争议取证都用得上。

这条原则在两个妄想症规则包上会得出不同结果，差异来自判据 ②：

| 规则包 | 技能 | 专精 | 结论 |
|---|---|---|---|
| 妄想症 2E | 60+ 项 + 30 点分配 + 部门训练上限 | 混在技能里 | 成本过高，都不录 |
| 妄想症 25 周年 | 6 项固定数字 | 自由文本 + 动态列表 + 频繁变动 | 技能录，专精不录 |

**专精是"正面可见但成本不划算"的第一个例外**——判据 ② 在这里起了实际作用，不是口号。

---

## 2. 妄想症 2E

### 2.1 为什么不录技能

| 原因 | 说明 |
|---|---|
| **录入成本过高（主因）** | 原表 60+ 个技能字段，还要处理 30 点分配、部门训练上限 13/14 的校验 |
| 维护成本更高 | 技能点变动、部门训练差异、中文翻译不一致 |
| 判定价值为零 | 裸骰模式下 `/check` 不读取技能值，录了也不参与任何计算 |

对比：25 周年只有 6 项技能，成本可承受，因此录入（见 §3）。**差异来自成本，不是来自隐藏性。**

**连带后果**：`部门特殊训练表` 与 `技能说明表` 整个不需要——它们只决定技能上限 13/14 和解释用途，bot 都不管。

### 2.2 为什么不录隐秘部分

原角色卡自带声明：

> 「关于部门、秘密结社和异能力的投骰结果具体信息请私聊 GM。隐秘事项在任何时刻都不可以公开，公开隐秘事项的行为是反叛行为。」

涉及字段：异能力、是否注册、秘密结社、结社等级、反叛性技能、是否安全局特工、旧历时代文化 / 电脑安保 / 电脑编程 / 赤色宣传。

**这些不录，等于用技术手段落实了游戏内的保密规则。** 录进 bot 后，它会在以下位置留下副本：

- SQLite 数据库
- 日志（即使脱敏，字段名也可能出现）
- 备份包
- 诊断导出包
- 管理界面截图

任何一处泄漏，在游戏内都是可处决级别的证据。

### 2.3 最小 schema

```yaml
id: paranoia2e
name: 妄想症 第2版
type: rulepack
reveal: roll-only          # 裸骰：只掷 1d20，不判成败

identity:
  - { key: name,      label: 名字,     type: str, required: true }
  - { key: clearance, label: 保密等级, type: enum,
      options: [R, O, Y, G, B, I, V, U], default: R }
  - { key: sector,    label: 地区代码, type: str, max: 3 }
  - { key: clone,     label: 克隆体编号, type: int, min: 1, default: 1 }
  - { key: player,    label: 玩家,     type: str, optional: true }
  - { key: dept,      label: 服务部门, type: enum,
      options: [IntSec, Tech, HPDMC, Army, PLC, Power, RND, CPU] }

attributes:                 # 各 1–20，创建时 1d20，可重投两次
  - { key: str, label: 力量 }
  - { key: agi, label: 敏捷 }
  - { key: dex, label: 灵巧 }
  - { key: con, label: 耐久 }
  - { key: mox, label: 精力 }
  - { key: chz, label: 厚颜 }
  - { key: mek, label: 机械天赋 }
  - { key: pow, label: 能量 }

derived:
  - key: carry
    label: 载重量
    type: expr
    expr: "25 + max(0, str - 12) * 5"

  - key: dmg_bonus
    label: 伤害加值
    type: lookup
    source: str
    table: [{ max: 13, value: "0" }, { max: 18, value: "1" }, { max: 20, value: "2" }]

  - key: soak
    label: 英雄气概
    type: lookup
    source: con
    table: [{ max: 13, value: "0" }, { max: 18, value: "1" }, { max: 20, value: "2" }]

misc:
  - { key: credits, label: 信用点, type: int, optional: true }
  - { key: notes,   label: 备注,   type: str, optional: true, max: 200 }
```

**字段数：13（必填 9，可选 4）**，约为原表的 20%。

### 2.4 与原始表格的对照

| 原表区块 | 处理 | 原因 |
|---|---|---|
| 名字 / 保密等级 / 地区 / 克隆体 / 玩家 / 部门 | ✅ 保留 | 身份，且公开可见 |
| 8 项属性 | ✅ 保留 | 机械数值，玩家自己就能读 |
| 载重量 / 伤害加值 / 英雄气概 | ✅ 保留（自动算） | 战斗时需要，纯派生 |
| 5 项技能基值 | ❌ 剔除 | 依附于技能，无技能则无意义 |
| 60+ 技能与技能点 | ❌ 剔除 | 判定模糊，裸骰不需要 |
| 部门特殊训练表 | ❌ 剔除 | 只用于技能上限校验 |
| 技能说明表 | ❌ 剔除 | 纯文本参考 |
| 异能 / 结社 / 反叛技能 / 安全局特工 | ❌ 剔除 | **隐藏信息，不得入库** |
| 装备列表 / 护甲等级 | ❌ 首版剔除 | 高频变动，且不参与任何自动化 |
| 信用点 | ⚠️ 可选 | 简单数值，但变动频繁 |
| 角色背景 / 备注 | ⚠️ 可选 | 自由文本，需长度上限 |

### 2.5 指令对应

| 指令 | 行为 |
|---|---|
| `/pc init` | 逐项录入，或 `/pc roll` 一键 8 项 d20 |
| `/pc show` | 展示精简卡（身份 + 属性 + 派生） |
| `/pc set <字段> <值>` | 修改单项（重投属性、改克隆体编号等） |
| `/pc share` | 把精简卡贴到群里（供 KP 参考） |
| `/check <标签>` | 掷 `1d20`，标签仅记录不校验 |

`/check` 的标签不做白名单校验——因为不录技能，无法也不知道有哪些合法技能。这正好符合"判定权归 KP"。

### 2.6 值得保留的两个小功能

| 功能 | 理由 |
|---|---|
| 克隆体编号 +1 | 死亡换克隆体是妄想症的核心循环，一个计数器成本极低 |
| 属性重投记录 | 原表允许重投两次，记录哪两项重投过，避免争议 |

---

## 3. 妄想症 25 周年

> 参考：`Paranoia Troubleshooters with bookmarks.pdf` 第 199–200 页（角色卡正反面）

### 3.1 角色卡的双面结构

官方角色卡明确分成两面，这本身就是最好的收录指南：

| 面 | 内容 | 是否公开 |
|---|---|---|
| **正面** | 名字 / 保密等级 / 区域 / 克隆体编号 / 性别 / 玩家 / 服务部门 / 习惯(Tics) / 强制 bonus duty / 六项技能与专精 | 公开 |
| **背面（SECRET SIDE）** | 变异能力 / 秘密结社 / 结社等级 / 结社任务 / **属性** / 秘密技能 / 装备 / 信用点 / 搞事点数 / 反叛点数与证据 | 保密 |

背面标题直接印着 `SECRETS ARE TREASON`。

### 3.2 两组不同的数据：六项技能 vs 两项属性

这里最容易混淆，必须先分清——**它们是两组完全不同的东西**：

| | 六项技能 | 两项属性 |
|---|---|---|
| 名称 | Management / Stealth / Violence / Hardware / Software / Wetware | Power / Access |
| 位置 | **正面** | 背面 |
| 可见性 | **玩家可见**，自己掷、自己写 | 预印 `CLASSIFIED` |
| 数量 | 6 | 2 |
| 是否录入 | ✅ | ❌ |

背面的 `CLASSIFIED` 只作用于这一行：

```
Attribute ratings:   Power  CLASSIFIED      Access  CLASSIFIED
```

规则书（p.56）：

> Track each PC's attribute ratings secretly during play. Remember, players can never show knowledge of their own or anyone's attribute ratings.

**它约束的只是 Power 和 Access，与六项技能无关。**

| | 2E | 25 周年 |
|---|---|---|
| 属性 | 8 项，正面，玩家自己掷 | 2 项，背面，玩家不可知 |
| 属性是否录入 | ✅ | ❌ |
| 技能 | 60+ 项 | 6 项 |
| 技能是否录入 | ❌（成本） | ✅ |

属性不录的理由：录入就必须长期隐藏，而"隐藏状态"正是本设计刻意避免的东西。
技能录入的理由：**它们就印在正面，玩家本来就能看到**，没有隐藏性，成本也可承受。

### 3.3 最小 schema

```yaml
id: paranoia25th
name: 妄想症 25 周年
type: rulepack
reveal: roll-only          # 裸骰，同 2E

identity:
  - { key: name,  label: 名字,     type: str, required: true }
  - { key: clearance, label: 保密等级, type: enum,
      options: [R, O, Y, G, B, I, V, U], default: R }
  - { key: sector, label: 区域,   type: str, max: 3 }
  - { key: clone,  label: 克隆体编号, type: int, min: 1, max: 6, default: 1 }
  - { key: gender, label: 性别,   type: enum,
      options: [M, F, Other], default: Other }
  - { key: player, label: 玩家,   type: str, optional: true }
  - { key: service_group, label: 服务部门, type: enum,
      options: [IntSec, Tech, HPDMC, Army, PLC, Power, RND, CPU] }
  - { key: duty,   label: 强制职责, type: enum, optional: true,
      options: [team_leader, loyalty_officer, hygiene_officer,
                comm_recording, equipment_guy, happiness_officer, other] }
  - { key: tics,   label: 习惯动作, type: str, optional: true, max: 100 }

skills:                      # 六项，正面可见，0–20
  - { key: management, label: 处世, type: int, min: 0, max: 20 }
  - { key: stealth,    label: 隐秘, type: int, min: 0, max: 20 }
  - { key: violence,   label: 武力, type: int, min: 0, max: 20 }
  - { key: hardware,   label: 硬件, type: int, min: 0, max: 20 }
  - { key: software,   label: 软件, type: int, min: 0, max: 20 }
  - { key: wetware,    label: 湿件, type: int, min: 0, max: 20 }

derived:
  - key: energy_weapons
    label: 能量武器
    type: expr
    expr: "violence + 4"     # 所有肃反队员必备专精，自动派生

misc:
  - { key: credits, label: 信用点, type: int, optional: true }
  - { key: notes,   label: 备注,   type: str, optional: true, max: 200 }
```

**固定字段：18（必填 12，可选 5，派生 1），无动态列表。**

### 不录专精

| 维度 | 情况 |
|---|---|
| 数量 | 卡面印 50 个条目 + 空白行，玩家实际只有 5–8 个 |
| 形态 | 自由文本，无法校验 |
| 稳定性 | 每次任务后可增可改（升技能、加专精、服务部门专精加成） |
| 结构 | 需要动态列表 UI，录入时要选所属技能并填等级 |
| 收益 | 仅 `/pc show` 多显示几行 |

**成本是"动态列表 + 自由文本 + 频繁变动"，收益只是"多几行展示"** —— 判据 ② 不通过。

需要某项专精数值时，玩家看纸质卡即可，那本来就是权威版本。

**保留的派生**：能量武器仍是 `武力 + 4` 自动计算——它是规则强制的必备专精，不是名单里可选的一项，零成本。

### 3.4 收录决策表

| 卡面区块 | 处理 | 原因 |
|---|---|---|
| 名字 / 保密等级 / 区域 / 克隆体 | ✅ | 身份 |
| 性别 / 玩家 | ✅ | 身份，公开 |
| 服务部门 | ✅ | 公开；虽不再录专精，但仍决定角色可用的专精范围（纸质参考） |
| 习惯(Tics) | ✅ | 公开的角色扮演特征，且他人可据此花费搞事点数 |
| 强制职责 | ✅ | 公开，任务内的角色分工 |
| 六项技能 | ✅ | 印在正面，玩家可见；6 项固定数字，成本可承受 |
| 专精列表 | ❌ | 自由文本 + 动态列表 + 频繁变动，收益仅"多显示几行" |
| **属性（Power / Access）** | ❌ | 背面标 `CLASSIFIED`，玩家不能知道 |
| 变异能力 / 注册状态 | ❌ | SECRET SIDE |
| 秘密结社 / 等级 / 任务 | ❌ | SECRET SIDE |
| 秘密技能（Uncommon / Unlikely / Unhealthy） | ❌ | SECRET SIDE |
| 装备（个人 / 配发 / 违禁） | ❌ | 高频变动，且"违禁"本身是敏感信息 |
| 搞事点数 | ❌ | 玩家级资源，非角色属性 |
| 反叛点数与证据 | ❌ | 敏感，且属于指控材料 |
| 信用点 | ⚠️ 可选 | 简单数值 |
| 备注 | ⚠️ 可选 | 自由文本，需限长 |

### 3.5 与 2E 的差异汇总

| 项 | 2E | 25 周年 |
|---|---|---|
| 固定字段 | 13 | 18 |
| 属性 | 8 项，✅ 录入 | 2 项，❌ 不录（CLASSIFIED） |
| 技能 | 60+，❌ 不录（成本） | 6 项，✅ 录入 |
| 专精 | 混在技能里，不录 | 自由文本，❌ 不录（成本） |
| 派生值 | 载重量 / 伤害加值 / 英雄气概 | 能量武器 = 武力 + 4 |
| 特色字段 | 保密等级 / 克隆体 | 性别 / 习惯 / 强制职责 |
| 检定 | `1d20` 裸骰 | `1d20` 裸骰 |
| 判定权 | KP | KP |

**两个规则包共用同一个裸骰实现，差异 100% 在 schema。**

### 3.6 指令对应

| 指令 | 行为 |
|---|---|
| `/pc init` | 逐项录入 |
| `/pc show` | 展示身份块（不含任何 SECRET SIDE 内容） |
| `/pc clone` | 克隆体编号 +1（上限 6） |
| `/pc share` | 贴到群里 —— **只贴正面字段** |
| `/check <标签>` | 掷 `1d20`，标签仅记录 |

`/pc share` 需要特别保证：**任何情况下都不输出 Power / Access、秘密技能、结社、变异**。这是硬约束，不是"默认值"。六项技能属于正面数据，可以正常展示。

---

## 4. COC / DND 的录入要求

两套都是 `full` 模式——引擎要读角色卡算目标值与加值，所以**技能必须录**，不能像妄想症那样省略。

### 4.1 总览

| 规则包 | 判定模式 | 技能 | 理由 |
|---|---|---|---|
| COC 7e | `full` | 必录 | 引擎要取技能值作目标 |
| DND 5e | `full` | 必录 | 引擎要用属性调整 + 熟练加值 |
| 妄想症 2E | `roll-only` | 不录 | 60+ 项，录入成本过高 |
| 妄想症 25 周年 | `roll-only` | 录 | 仅 6 项，且印在正面 |

注意 2E 与 25 周年同为裸骰模式，技能处理却相反——**决定因素是成本，不是判定模式**。

### 4.2 COC 7e 最小字段

| 分组 | 字段 |
|---|---|
| 身份 | 姓名 / 年龄 / 职业 / 居住地 |
| 属性 | STR / CON / SIZ / DEX / APP / INT / POW / EDU（+ LUCK） |
| 派生 | HP / MP / SAN / MOV / 伤害加值 / 体格 |
| 技能 | 名称（自由文本）+ 值（0–99） |
| 状态 | 当前 HP / MP / SAN / 幸运 |

**派生全部可算**：`HP = (CON+SIZ)/10`、`MP = POW/5`、`SAN = POW`、`MOV` 与 `伤害加值` 查表（`lookup`）。这部分交给引擎，不重复录入。

### 4.3 DND 5e 最小字段

| 分组 | 字段 |
|---|---|
| 身份 | 姓名 / 种族 / 职业 / 等级 |
| 属性 | STR / DEX / CON / INT / WIS / CHA（3–20） |
| 派生 | 6 项属性调整值 / 熟练加值 / 被动察觉 |
| 熟练 | 6 项豁免标记（布尔）+ 18 项技能标记（布尔） |
| 状态 | 当前 HP / AC / 临时 HP |

**关键差异**：5e 存的是**熟练标记（布尔）**，不是技能数值。每次检定的加值在运行时算：

```
加值 = 属性调整值 + (熟练 ? 熟练加值 : 0)
```

这与 COC「存一个技能数字」的模型完全不同，schema 需要区分「值型」与「标记型」两种字段。

### 4.4 共同约定

| 约定 | 说明 |
|---|---|
| 技能名 | 自由文本（中译本术语不统一） |
| 结构字段 | 枚举（6 项属性、6 项豁免固定不变） |
| 派生值 | 一律由引擎计算，不录入 |
| 不录 | 装备、物品、背景故事、角色外貌 |

通用原则：

> **录正面，不录背面；录得起，就录。**

---

## 5. 数据落点

角色卡统一存 `characters` 表：

```sql
characters (member_openid, rulepack_id, slot, name,
            data_json, sheet_version, updated_at,
            PK(member_openid, rulepack_id, slot))
```

`data_json` 内按 schema 组织，由引擎做类型与范围校验后写入。插件本身不接触 SQL。

由于字段极简，2E 的角色卡 JSON 大约 300 字节，可读性也很好——这对排查问题很有帮助。
