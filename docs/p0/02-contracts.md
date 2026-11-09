# P0-02 模块接口契约

> 定义引擎、规则包、模块、Provider、存储之间的边界。
> 原则：**契约由引擎定义，插件只能遵守，不能扩展。**

---

## 1. 分层与依赖方向

```
        ┌──────────────┐
        │  Admin UI    │  (仅调用 Admin API)
        └──────┬───────┘
               ▼
        ┌──────────────┐
        │  Admin API   │
        └──────┬───────┘
               ▼
   ┌────────────────────────┐
   │         Engine         │
   │  Gateway / Router /    │
   │  Session / Outbound    │
   └───┬────────┬───────┬───┘
       ▼        ▼       ▼
  ┌────────┐ ┌──────┐ ┌────────┐
  │Rulepack│ │Module│ │Provider│
  └────────┘ └──────┘ └────────┘
       │        │          │
       └────────┴──────────┘
                ▼
           ┌────────┐
           │ Store  │
           └────────┘
```

**依赖只能向下。** 规则包与模块**不得**直接访问 Store、网络、文件系统——一切通过引擎提供的受控能力。

---

## 2. 核心数据结构

### 2.1 InternalMessage（入站归一化）

```python
@dataclass(frozen=True)
class InternalMessage:
    # 来源
    scene: Literal["group"]              # 首版仅群聊
    group_openid: str
    member_openid: str
    member_role: Literal["member", "admin", "owner"]

    # 消息
    msg_id: str
    content: str                          # 已去除 @ 前缀
    attachments: list[Attachment]
    mentions: list[Mention]
    ref_msg_idx: str | None               # 引用消息索引
    created_at: datetime

    # 元信息
    intent: str                           # GROUP_AT_MESSAGE_CREATE 等
    seq: int                              # 网关下行序号，用于 resume
```

### 2.2 Attachment

```python
@dataclass(frozen=True)
class Attachment:
    kind: Literal["image", "voice", "video", "file"]
    url: str
    mime: str
    size: int
    asr_text: str | None                  # 平台已给语音转写
    # 注意：auth_token / rkey 不进此结构，只在下行时临时取用
```

### 2.3 CallContext（贯穿一次处理）

```python
@dataclass
class CallContext:
    message: InternalMessage
    mode: Literal["chat", "trpg", "minigame"]
    room_id: str | None
    plugin_id: str | None
    remaining_replies: int                # 被动回复剩余次数（初值 5）
    deadline: datetime                    # 5 分钟窗口截止
    trace_id: str
```

### 2.4 InternalReply（出站原语）

```python
@dataclass
class InternalReply:
    ctx: CallContext
    text: str
    msg_type: Literal[0, 2, 7] = 0        # 文本 / markdown / 富媒体
    media: MediaRef | None = None
    final: bool = True                    # 是否本轮最后一条
```

---

## 3. Gateway 契约

### 3.1 职责

维护 WS 连接、鉴权、心跳、resume、token 刷新。**不做任何业务判断。**

### 3.2 对外事件

```python
class Gateway:
    async def start(self) -> None: ...
    async def stop(self) -> None: ...

    # 事件通过回调派发，保证：单线程顺序、不阻塞心跳
    on_event: Callable[[InternalMessage | SystemEvent], Awaitable[None]]
    on_state: Callable[[GatewayState], None]
```

### 3.3 硬性约束

| # | 约束 |
|---|---|
| G1 | 事件回调必须**立即返回**，业务处理入队异步执行 |
| G2 | 队列满时**丢弃最旧**并计数，不阻塞接收 |
| G3 | 收到事件先落 `s` 序号，再交给业务 |
| G4 | resume 失败降级为全新 identify，并清空 session |
| G5 | token 刷新用 singleflight，同一时刻只有一个刷新在飞 |

---

## 4. Rulepack 契约

### 4.1 声明（manifest.yaml）

```yaml
id: coc7th
name: 克苏鲁的呼唤 第7版
type: rulepack
version: 1.0.0
engine_version: ">=1.0 <2.0"
reveal: full                 # full | roll-only
permissions: []              # 必须为空
```

### 4.2 能力面

规则包**只能声明数据**，不能提供可执行代码。引擎解释执行。

| 能力 | 形式 |
|---|---|
| 角色卡 schema | YAML |
| 派生值 | `expr` / `lookup` |
| 检定 | `check` 块（见 rulepack-check-spec） |
| 指令 | 声明式匹配 + 动作列表 |
| 迁移 | `migrations` 声明 |

### 4.3 引擎暴露给规则包的只读上下文

```python
@dataclass(frozen=True)
class RulepackContext:
    group_openid: str
    member_role: str
    character: dict | None      # 已按 schema 校验
    room_state: dict            # 只读快照
    rng: RandomSource           # 引擎提供的随机源，带审计
```

**规则包拿不到**：Store、HTTP 客户端、文件句柄、其他群的数据。

### 4.4 指令契约

```yaml
commands:
  - name: roll
    aliases: ["r"]
    match: "^roll\\s+(?P<expr>.+)$"
    action: { kind: dice, expr: "{expr}" }
  - name: check
    aliases: ["c"]
    match: "^check\\s+(?P<skill>\\S+)(?:\\s+(?P<target>\\d+))?$"
    action: { kind: check, check_id: skill_check, target: "{target}" }
```

约束：

| # | 约束 |
|---|---|
| C1 | 引擎指令（`/mode` `/help` `/pc`）不可覆盖 |
| C2 | 插件指令必须含命名空间，或由引擎转发裸别名 |
| C3 | 正则必须是**有限状态可判定**，引擎限制回溯深度与长度 |
| C4 | 动作只能是引擎预定义的 `kind`，不能是自由代码 |

---

## 5. Module 契约

### 5.1 接口

```python
class Module(Protocol):
    id: str
    mode: Literal["chat", "trpg", "minigame"]

    def match(self, msg: InternalMessage) -> bool: ...
    async def handle(self, ctx: CallContext) -> list[InternalReply]: ...
    def prompt_fragment(self, ctx: CallContext) -> str | None: ...
    def expected_frequency(self) -> tuple[int, int]: ...
        # (次数, 窗口秒) —— 用于覆盖滥用阈值
```

### 5.2 约束

| # | 约束 |
|---|---|
| M1 | `handle` 必须尊重 `ctx.remaining_replies`，超预算抛 `E4101` |
| M2 | `handle` 必须有总超时（默认 25s），超时由引擎取消 |
| M3 | 不得直接发送消息，只返回 `InternalReply` |
| M4 | 不得跨群读写状态 |
| M5 | 输出文本必须经过引擎的出站过滤器 |

---

## 6. Provider 契约（模型）

```python
class Provider(Protocol):
    id: str
    capabilities: set[Literal["text", "image", "audio", "video"]]

    async def complete(
        self,
        messages: list[Message],
        *,
        timeout: float,
        max_tokens: int,
        model: str | None = None,
    ) -> Completion: ...

    async def probe(self) -> ProbeResult: ...
```

| # | 约束 |
|---|---|
| P1 | `complete` 必须有硬超时，默认 25s |
| P2 | 流式暂不支持（群聊无流式接口） |
| P3 | 失败重试 ≤ 2 次，仅对网络类错误 |
| P4 | 密钥只从引擎注入，Provider 不得读配置 |
| P5 | 能力必须经 `probe` 实测，不信任静态声明 |

---

## 7. Store 契约

```python
class Store(Protocol):
    # 幂等
    async def seen(self, key: tuple[str, str]) -> bool: ...
    async def mark_seen(self, key: tuple[str, str]) -> None: ...

    # 回复守卫
    async def next_msg_seq(self, msg_id: str) -> int: ...
    async def mark_sent(self, msg_id: str, msg_seq: int) -> None: ...

    # 会话
    async def get_thread(self, room_id: str, member: str) -> dict | None: ...
    async def put_thread(self, ...) -> None: ...

    # 额度
    async def consume(self, scope: str, key: str, n: int) -> bool: ...

    # 审计
    async def audit(self, actor: str, action: str, target: str,
                    detail: dict) -> None: ...
```

| # | 约束 |
|---|---|
| S1 | `next_msg_seq` 必须原子递增并持久化，重启不重置 |
| S2 | `consume` 是**先扣后判**，返回是否仍有余量 |
| S3 | 所有写操作在单连接上串行（SQLite WAL） |
| S4 | 表结构变更必须走 `sheet_version` / 迁移脚本 |

---

## 8. Outbound 契约

```python
class Outbound(Protocol):
    async def send(self, reply: InternalReply) -> SendResult: ...
```

| # | 约束 |
|---|---|
| O1 | 发送前校验 `remaining_replies > 0`，否则拒绝 |
| O2 | 每条消息 `msg_seq` 单调递增，来自 Store |
| O3 | 文本长度超限自动分段，段间不重复计算次数 |
| O4 | 出站前过内容过滤（禁 `@` 语法、长度上限、控制字符） |
| O5 | 限流桶：全局 60qpm、单群 20qpm |
| O6 | 失败不自动重试 `msg_seq` 相同的请求 |

---

## 9. Admin API 契约

仅监听 `127.0.0.1`，路径前缀含随机令牌。

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/state` | 连接、模式、额度、版本 |
| GET | `/api/doctor` | 自检结果 |
| GET | `/api/groups` | 群列表与状态 |
| POST | `/api/groups/{id}/approve` | 审批加群 |
| POST | `/api/groups/{id}/mode` | 切换模式 |
| GET | `/api/plugins` | 插件列表 |
| POST | `/api/plugins/import` | 导入 zip |
| POST | `/api/plugins/{id}/enable` | 启用 |
| GET | `/api/sessions/{group}/{member}` | 查看上下文 |
| DELETE | `/api/sessions/{group}/{member}` | 清空 |
| GET | `/api/logs` | 脱敏日志流（SSE） |
| GET | `/api/diagnostics` | 导出诊断包 |
| POST | `/api/emergency/pause` | 暂停接收 |

| # | 约束 |
|---|---|
| A1 | 所有写操作校验 `Origin` + CSRF token |
| A2 | `Host` 头必须匹配 `127.0.0.1` / `localhost` |
| A3 | 响应中密钥一律掩码 |
| A4 | 日志接口只读 `logs/` 下文件，路径穿越校验 |

---

## 10. 超时与预算总表

| 环节 | 默认 | 可配 |
|---|---|---|
| WS 心跳 | 平台下发（约 45s） | 否 |
| 心跳超时判定 | 2 个周期无 ACK | 否 |
| 事件入队 | 立即 | 否 |
| 消息总处理 | 25s | 是 |
| 模型调用 | 25s | 是 |
| 出站发送 | 10s | 是 |
| 插件解析 | 5s | 否 |
| 单次被动回复次数 | 5 | 否 |
| 被动回复窗口 | 5 分钟 | 否 |
| 全局 qpm | 60 | 是 |
| 单群 qpm | 20 | 是 |

---

## 11. 版本与兼容

| 项 | 规则 |
|---|---|
| 引擎版本 | `1.x` |
| 插件 `engine_version` | 不满足即拒绝启用 |
| 角色卡 `sheet_version` | 升级走声明式迁移 |
| manifest 未知字段 | **忽略并警告**，不报错 |
| 未知 `action.kind` | 拒绝加载该指令，其余可用 |
