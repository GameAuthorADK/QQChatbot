# P0-03 状态机与关键流程

> 每个状态机都给出：状态集合、迁移表、迁移动作、异常分支。
> 实现时**状态必须显式建模**，不允许用布尔标志位拼凑。

---

## 1. 网关连接状态机

### 1.1 状态

```
IDLE → CONNECTING → IDENTIFYING → READY
                        ↑            │
                        │            ├─(断线)─→ RECONNECTING ─→ RESUMING ─┐
                        │            │                                  │
                        └────────────┴──────────────────────────────────┘
                                      │
                                 FATAL（配置错误，停止重试）
```

| 状态 | 含义 |
|---|---|
| `IDLE` | 未启动或已停止 |
| `CONNECTING` | 正在建立 wss |
| `IDENTIFYING` | 已连接，发送 op 2 等待 READY |
| `READY` | 正常收发 |
| `RECONNECTING` | 断线，退避中 |
| `RESUMING` | 已连接，发送 op 6 |
| `FATAL` | 不可恢复（无效 appId / intents 无权限），停止重试 |

### 1.2 迁移表

| 当前 | 事件 | 下一状态 | 动作 |
|---|---|---|---|
| IDLE | `start()` | CONNECTING | 取 token → 取 gateway → 建连 |
| CONNECTING | 连接成功 | IDENTIFYING | 发 `op 2` |
| CONNECTING | 连接失败 | RECONNECTING | 退避（1s→2s→…→60s，带抖动） |
| IDENTIFYING | `op 0 READY` | READY | 存 `session_id`，启动心跳 |
| IDENTIFYING | `op 9` | FATAL | 记录原因，停止重试，界面标红 |
| READY | `op 0 EVENT` | READY | 记录 `s`，事件入队 |
| READY | `op 7` | RECONNECTING | 立即重连 |
| READY | 心跳 ACK 超时 ×2 | RECONNECTING | 主动断开 |
| RECONNECTING | 连接成功 | RESUMING | 发 `op 6` |
| RESUMING | `RESUMED` | READY | 恢复心跳 |
| RESUMING | `op 9` | IDENTIFYING | 清 session，重新鉴权 |
| RECONNECTING | 重试次数 > 20 | FATAL | 停止并告警 |
| 任意 | `stop()` | IDLE | 优雅关闭 |

### 1.3 不变式

- `READY` 状态下必须有心跳定时器在跑
- 任何状态迁移都必须写一条状态日志（含原因）
- 重连期间**入站队列不丢**：已入队的消息继续处理

---

## 2. Token 状态机

```
EMPTY ──fetch──► VALID ──(剩余 < 5min)──► REFRESHING ──► VALID
                    │                          │
                    └──(expired)──► STALE      └─(失败 N 次)─► BROKEN
```

| 状态 | 行为 |
|---|---|
| `EMPTY` | 首次获取 |
| `VALID` | 直接使用 |
| `REFRESHING` | 并发请求**等待同一个 Future**（singleflight） |
| `STALE` | 同步阻塞刷新，失败则抛 `E1201` |
| `BROKEN` | 连续 5 次失败，停止自动刷新，界面告警，需人工介入 |

**不变式**：token 明文只存在于内存，任何日志/异常/接口响应都不得包含。

---

## 3. 消息处理流水线

### 3.1 状态

```
RECEIVED → DEDUPED → ROUTED → EXECUTING → REPLYING → DONE
    │         │         │          │          │
    └─────────┴─────────┴──────────┴──────────┴──► DROPPED / FAILED
```

| 状态 | 判定 |
|---|---|
| `RECEIVED` | 已从队列取出 |
| `DEDUPED` | 通过幂等检查；重复则 `DROPPED` |
| `ROUTED` | 已确定 mode / module / plugin |
| `EXECUTING` | 模块或模型处理中 |
| `REPLYING` | 已产生回复，正在发送 |
| `DONE` | 全部回复发出且确认 |
| `DROPPED` | 静默丢弃（重复、限流、拉黑、非授权群） |
| `FAILED` | 处理异常且无法降级 |

### 3.2 丢弃原因（必须记录，便于排查）

| 原因码 | 场景 |
|---|---|
| `DROP_DUP` | 重复消息 |
| `DROP_C2C` | 单聊事件（硬丢弃） |
| `DROP_GROUP` | 群未授权 / 已禁用 |
| `DROP_MUTED` | 用户处于 muted |
| `DROP_RATE` | 触发限流 |
| `DROP_BUDGET` | 超出额度 |
| `DROP_EMPTY` | 内容为空且无附件 |

### 3.3 关闭顺序

`DROPPED` 必须发生在 `ROUTED` **之前**，避免无谓的路由与模型调用。

---

## 4. 滥用防护状态机

```
         窗口内次数 > W1
NORMAL ─────────────────► WARNED
   ▲                        │
   │ owner 解封              │ 警告后窗口内再 > W2
   │ 或 expire_at 到期       ▼
   └──────────────────── MUTED（完全静默）
```

| 状态 | 行为 |
|---|---|
| `NORMAL` | 正常响应 |
| `WARNED` | 响应一次警告，之后仍响应但计数 |
| `MUTED` | **完全静默**，不回复、不计数、只记审计 |

### 4.1 迁移表

| 当前 | 事件 | 下一状态 | 动作 |
|---|---|---|---|
| NORMAL | count > W1 | WARNED | 发警告（**不计入计数**），进入冷却 |
| WARNED | 冷却期后再超 W2 | MUTED | 写 `abuse_state`，审计 |
| WARNED | 窗口内恢复正常 | NORMAL | 计数衰减 |
| MUTED | owner `/unban @user` | NORMAL | 审计 |
| MUTED | `expire_at` 到期 | NORMAL | 审计 |
| MUTED | 用户 @ bot | MUTED | **静默，不回任何内容** |

### 4.2 豁免

不计数、不进状态机：

- owner 本人
- 白名单用户
- 模块声明的高频交互（`expected_frequency` 覆盖）
- 帮助提示消息本身

---

## 5. 模式生命周期

```
        /mode trpg <plugin>
CHAT ──────────────────────► TRPG
  ▲                             │
  │      /mode off              │
  └─────────────────────────────┘
  ▲                             │
  │      /mode minigame <plugin>│
  └──────────► MINIGAME ◄───────┘
```

| 状态 | 处理 |
|---|---|
| `CHAT` | 指令路由 + chat 模块（调 LLM） |
| `TRPG` | 只走指令路由，**不调 LLM** |
| `MINIGAME` | 只走指令路由，**不调 LLM** |

### 5.1 进入前置条件

| 条件 | 失败处理 |
|---|---|
| 调用者是 owner / 群主 / 群管理员 | 静默或提示无权限 |
| 插件存在且已启用 | 回复"插件未启用" |
| 当前无其他模式 | 提示先 `/mode off` |

### 5.2 不变式

- 每次切换写 `audit_log`
- 切换只影响本群
- `TRPG` / `MINIGAME` 下未识别指令**静默**，但每 5 分钟最多给一次帮助提示
- 不自动超时

---

## 6. 群授权生命周期

```
           owner 拉群
PENDING ──────────────► ACTIVE ──(禁用)──► DISABLED
   │                      │                  │
   │ 非 owner 拉群         │ 被移出            │ 重新启用
   ▼                      ▼                  ▼
REMOVED ◄──────────────── REMOVED           ACTIVE
```

| 状态 | 行为 |
|---|---|
| `PENDING` | 记录，不响应 |
| `ACTIVE` | 正常服务 |
| `DISABLED` | 记录，不响应 |
| `REMOVED` | 保留历史，不响应 |

**首次信任**：`owner` 表为空时，第一个 `GROUP_ADD_ROBOT` 进 `PENDING`，由人在界面点确认后才写入 owner 并把该群置为 `ACTIVE`。

---

## 7. 插件生命周期

```
IMPORTED → VALIDATED → PREVIEWED → ENABLED → (DISABLED)
   │           │           │
   └───────────┴───────────┴──► REJECTED
```

| 状态 | 动作 |
|---|---|
| `IMPORTED` | 解压、体积/路径校验、计算哈希 |
| `VALIDATED` | manifest、schema、表达式 AST、依赖图无环 |
| `PREVIEWED` | 用 selftest 跑一遍（有则跑，无则标记"未验证"） |
| `ENABLED` | 可被模式引用 |
| `DISABLED` | 数据保留，不可引用 |
| `REJECTED` | 记录原因，不入库 |

---

## 8. 关键时序

### 8.1 首次配置

```
用户          UI            引擎            平台
 │  双击exe     │              │               │
 ├─────────────►│              │               │
 │              ├─doctor──────►│               │
 │              │◄────结果─────┤               │
 │  填 appId    │              │               │
 ├─────────────►│──保存(DPAPI)►│               │
 │              │              ├─getToken─────►│
 │              │              │◄──token───────┤
 │              │              ├─gateway──────►│
 │              │              │◄──wss url─────┤
 │              │              ├──connect─────►│
 │              │              │◄──READY───────┤
 │  "把bot拉进群"│              │               │
 │              │◄─GROUP_ADD───┤◄──────────────┤
 │  点确认owner  │              │               │
 ├─────────────►│──写owner────►│               │
 │              │              ├─更新群=ACTIVE─┤
 │              │◄──完成────────┤               │
```

### 8.2 消息处理（chat 模式）

```
网关    队列    去重    路由    模块    Provider   出站
 │       │       │       │       │        │        │
 ├─事件─►│       │       │       │        │        │
 │       ├──────►│       │       │        │        │
 │       │       ├─重复──►DROP   │        │        │
 │       │       ├──────►│       │        │        │
 │       │       │       ├──────►│        │        │
 │       │       │       │       ├─拼上下文►│        │
 │       │       │       │       │        ├─25s───►│
 │       │       │       │       │◄──文本──┤        │
 │       │       │       │       ├────────┼───────►│
 │       │       │       │       │        │        ├─msg_seq+1─►平台
 │       │       │       │       │        │        │◄──ok───────┤
```

关键点：
- 队列与处理互不阻塞
- 模型调用期间心跳由**独立任务**维持
- 出站前取 `msg_seq`，成功后 `mark_sent`

### 8.3 断线恢复

```
READY ──断线──► RECONNECTING ──连上──► RESUMING ──RESUMED──► READY
   │                                        │
   │                                        └─op9─► IDENTIFYING
   │
   └─ 期间入队的消息不丢，恢复后按序处理
```

**补发事件可能重复** → 幂等层必须兜住（这正是 §3 `DROP_DUP` 的价值）。

### 8.4 刷屏封禁

```
用户A 疯狂@（10次/60s）
   │
   ├─ 第7次 → WARNED：群内回一条"请降低频率"
   │           （该条不计入计数，进入冷却）
   ├─ 冷却后仍超 W2 → MUTED
   │           写入 abuse_state，界面出现"已静默 N 人"
   └─ 继续 @ → 完全静默（不回"你被拉黑了"）

owner: /unban @A → NORMAL，写审计
```

### 8.5 插件导入

```
用户  →  选 zip
      →  解压到 runtime/tmp/plugin-x
      →  路径校验（禁止 ../、绝对路径、符号链接）
      →  体积校验（解压后 ≤ 20MB，文件数 ≤ 200）
      →  计算 SHA-256，展示前 8 位
      →  解析 manifest（safe_load + alias 上限）
      →  schema / expr AST / 依赖图检查
      →  selftest（有则跑）
      →  ✓ 写入 plugins 表，状态 ENABLED
      →  ✗ 状态 REJECTED，展示具体错误行号
```
