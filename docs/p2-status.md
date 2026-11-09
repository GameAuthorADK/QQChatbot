# P2 状态说明

> 完成时间：2026-10-29
> 目标：把固定回复换成模型回复，并具备上下文与降级能力。

---

## 1. 已实现

| 模块 | 文件 | 说明 |
|---|---|---|
| Provider 抽象 | `qqbot/providers/base.py` | `ChatMessage` / `Completion` / `ProbeResult` |
| 假模型 | `qqbot/providers/mock.py` | 无需 Key，回复里带上下文轮数，便于验证 |
| OpenAI 兼容 | `qqbot/providers/openai_compat.py` | 一套覆盖 GLM / DeepSeek / Gemini |
| 会话上下文 | `store.threads` | 按 `(群, 人)` 隔离，滑动窗口 |
| 超时降级 | `app._generate` | 25s 硬超时 → 兜底话术 |
| 文本分段 | `qqbot/textutil.py` | 按自然边界切分，最多 3 条 |
| 出站清洗 | `qqbot/textutil.sanitize` | 去控制字符、屏蔽 `@全体成员` |
| 配置接口 | `POST /api/provider` | 保存并热重建 Provider |
| 连通测试 | `POST /api/provider/test` | 真实发一次探测请求 |
| **本地试聊** | `POST /api/chat/preview` | 不经过 QQ，直接验证整条链路 |

---

## 2. 已验证

| 项 | 结果 |
|---|---|
| 单元测试 | **30 项通过** |
| 默认假模型 | ✅ 启动即就绪，无需 Key |
| 保存配置并重建 | ✅ |
| 连通探测 | ✅ 返回延迟 |
| 配置错误提示 | ✅ `[E2001] 请先填写模型地址与模型名` |
| 上下文累积 | ✅ 1 → 2 → 3 轮 |
| 上下文清空 | ✅ 清空后从 1 轮重新开始 |
| 分段预告 | ✅ 返回 `chunks`，界面提示会分几条发 |
| 打包 | 37.2 MB，路径预算 183 |

---

## 3. 设计取舍

| 决策 | 理由 |
|---|---|
| **只做 OpenAI 兼容协议** | GLM / DeepSeek / Gemini 都提供兼容端点，一套实现足够；避免三套 SDK |
| **不做流式** | 群聊没有流式接口（见 `architecture.md` §7.5） |
| **超时 25s** | 群被动回复窗口 5 分钟，但体验上 30s 就等同于失败 |
| **上下文按人隔离** | bot 只收 @ 消息，不掌握群内氛围，按人隔离是唯一自洽的选择 |
| **滑动窗口，暂不做摘要** | 摘要需要额外一次模型调用，P2 先保简单，见 §4 |
| **本地试聊** | 不依赖 QQ 群即可验证模型与上下文，排障成本低 |

---

## 4. 未做（有意延后）

| 项 | 原因 | 计划 |
|---|---|---|
| 上下文摘要压缩 | 需要额外模型调用与预算控制 | P2.5 |
| 能力探测（图像/音频） | 当前只处理文本，多模态随需要在 P3 补 | P3 |
| 日 token 预算 | 属于滥用防护 | P4 |
| 出站内容审核 | 需要外部审核服务或规则库 | P4 |
| 会话查看/清空界面 | 目前只有试聊清空 | P3 |

---

## 5. 怎么用

1. 启动程序
2. 「模型」区先保持 **假模型**，点「测试连通」应显示 `✓ 假模型就绪`
3. 在「本地试聊」输入一句话，确认能收到回复且轮数递增
4. 拿到真实 Key 后：
   - 类型选 `OpenAI 兼容`
   - 填 Base URL / 模型名 / API Key
   - 点「保存模型」→「测试连通」
   - 通过后，群里 @ 机器人就会用真模型回复

### 常用 Base URL

| 服务 | Base URL | 示例模型 |
|---|---|---|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4.6` |
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | `gemini-2.5-flash` |

> 模型名请以各家当前文档为准；填错会返回 `[E2006] 模型返回错误`。
