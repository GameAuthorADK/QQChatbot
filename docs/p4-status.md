# P3/P4 状态说明

> 完成时间：2026-10-29
> 内容：模型预设、群审批闸、滥用防护、频率与额度。

---

## 1. 模型预设

`qqbot/providers/presets.py` 内置六个选项，界面下拉即可：

| id | 显示 | Base URL |
|---|---|---|
| `mock` | 假模型（无需 Key） | — |
| `deepseek` | DeepSeek | `https://api.deepseek.com/v1` |
| `glm` | 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` |
| `gemini` | Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` |
| `openai` | OpenAI | `https://api.openai.com/v1` |
| `custom` | 自定义 | 自填 |

规则：**预设负责填默认值，界面上手填的优先。**

模型名一律可编辑，且标记为"以官方文档为准"——模型 ID 变化很快，写死会过期。

### 关于 "OpenAI 兼容"

它不是标准，是事实约定。已知差异：

| 差异 | 影响 |
|---|---|
| Base URL 形态不一 | 由预设消除 |
| 认证头不同（Azure 用 `api-key`） | 暂不支持，需改代码 |
| `max_tokens` vs `max_completion_tokens` | o 系列可能报错 |
| `temperature` 范围不同 | 通常无碍 |
| 推理模型返回 `reasoning_content` | `content` 可能较晚填充 |
| 错误体格式不统一 | 统一收敛为 `E2006` |

---

## 2. 群审批闸（P3 前置）

`auto_approve_groups` 默认 `False`。

```
陌生人/协作者拉群 → pending（群里 @ 无反应）
    → 管理界面点「批准」→ active
    → 「停用」→ disabled
```

API：`POST /api/groups/{group_openid}/status`

> 背景：个人认证主体下，公开服务开关不可用，只有创建者本人且是群主时才能加群。
> 详见 `architecture.md` §2 与 README 第五节。

---

## 3. 滥用防护

### 3.1 状态机

```
normal ──窗口内 > W1──► warned ──冷却后再 > W2──► muted
   ▲                      │                        │
   └──── 管理界面解封 ─────┴────────────────────────┘
```

### 3.2 默认阈值

| 参数 | 默认 | 说明 |
|---|---|---|
| `abuse_window_s` | 60 | 滑动窗口 |
| `abuse_warn_threshold` | 6 | 超过即警告 |
| `abuse_mute_threshold` | 3 | 警告冷却后再超此值 → 静默 |
| `abuse_warn_cooldown_s` | 300 | 警告后的观察期 |
| `abuse_warn_text` | 「你 @ 得太频繁了，先缓一缓。」 | 警告文案 |

### 3.3 行为约定

| 状态 | 行为 |
|---|---|
| normal | 正常回复 |
| warned | **只发一次警告，本轮不调用模型**（省钱） |
| muted | **完全静默**，不回"你被拉黑了" |

- 警告消息本身不计入计数
- 静默状态持久化到数据库，**重启仍然有效**
- 只有管理界面能解封

---

## 4. 频率与额度

| 项 | 默认 | 行为 |
|---|---|---|
| 全局频率 | 60 qpm | 超出丢弃 |
| 单群频率 | 20 qpm | 超出丢弃 |
| 每日消息数 | 1000 | 超出丢弃 |
| 每日 token | 300000 | 超出丢弃 |

额度按自然日归零。界面显示今日用量。

---

## 5. 处理顺序（重要）

```
幂等 → 群状态 → 空内容 → 滥用 → 全局频率 → 群频率 → 每日额度 → 模型
```

**所有拦截都在模型调用之前**，所以被拦截的消息不花钱。

---

## 6. 已验证

| 项 | 结果 |
|---|---|
| 单元测试 | **38 项通过** |
| 预设列表 | ✅ 6 个 |
| 选 deepseek 不填 Key | ✅ `[E2002] 请先填写模型 API Key` |
| 切回 mock | ✅ 立即就绪 |
| 额度快照 | ✅ 日期 / 消息 / token |
| 解封不存在的人 | ✅ 返回 `false` |
| 打包 | 37.2 MB |

---

## 7. 未做

| 项 | 计划 |
|---|---|
| 群内 `/unban` 指令 | 需要指令路由（P5） |
| owner 多用户解封权限 | 需要 owner 表 |
| 出站内容审核 | 需外部服务或规则库 |
| 摘要压缩 | P2.5 |
