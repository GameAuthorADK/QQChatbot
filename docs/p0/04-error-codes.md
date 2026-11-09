# P0-04 错误码表

> 错误码是**给排查用的**，不是给用户看的。
> 用户看到的永远是一句人话；错误码只出现在日志、诊断包、界面折叠详情里。

---

## 1. 编码规则

```
E <分类 1位> <序号 3位>
E1 001
```

| 分类 | 范围 | 领域 |
|---|---|---|
| 1 | E1001–E1999 | 平台 / 网关 / 鉴权 |
| 2 | E2001–E2999 | 模型 Provider |
| 3 | E3001–E3999 | 插件 / 规则包 |
| 4 | E4001–E4999 | 限流 / 额度 / 滥用 |
| 5 | E5001–E5999 | 存储 |
| 6 | E6001–E6999 | 运行时 / 环境 |
| 7 | E7001–E7999 | 管理面 / 界面 |

---

## 2. 平台 / 网关（E1xxx）

| 码 | 名称 | 含义 | 重试 | 界面文案 |
|---|---|---|---|---|
| E1001 | `TOKEN_EMPTY` | 未配置 appId / secret | 否 | 请先在设置中填写机器人凭据 |
| E1002 | `TOKEN_INVALID` | appId 或 secret 错误 | 否 | 凭据无效，请检查 appId 与密钥 |
| E1003 | `TOKEN_FETCH_FAILED` | 取 token 网络失败 | 是 | 网络异常，正在重试 |
| E1004 | `TOKEN_BROKEN` | 连续刷新失败 5 次 | 否 | 无法获取访问凭证，请检查网络或凭据 |
| E1101 | `GATEWAY_URL_FAILED` | 取 wss 地址失败 | 是 | 连接超时，正在重试 |
| E1102 | `WS_CONNECT_FAILED` | wss 握手失败 | 是 | 无法连接服务器 |
| E1103 | `WS_IDENTIFY_REJECTED` | op 9，鉴权参数有误 | 否 | 机器人配置异常（intents 无权限？） |
| E1104 | `WS_HEARTBEAT_TIMEOUT` | 心跳无 ACK | 是 | 连接不稳定，正在重连 |
| E1105 | `WS_RESUME_FAILED` | resume 失败，转全新连接 | 是 | 正在重新连接 |
| E1106 | `WS_FATAL` | 多次重连失败 | 否 | 已停止重连，请检查网络后手动重试 |
| E1201 | `INTENTS_FORBIDDEN` | 订阅了无权限的 intents | 否 | 缺少事件权限，请到开放平台申请 |
| E1301 | `SEND_FAILED` | 发送消息失败 | 部分 | 消息发送失败 |
| E1302 | `SEND_MSG_SEQ_CONFLICT` | `msg_id + msg_seq` 重复 | 否 | （不展示） |
| E1303 | `SEND_WINDOW_EXPIRED` | 超过 5 分钟被动窗口 | 否 | （不展示，静默） |
| E1304 | `SEND_RATE_LIMITED` | 平台频控 | 是 | 发送过于频繁 |
| E1305 | `MEDIA_UPLOAD_FAILED` | 富媒体上传失败 | 是 | 附件发送失败 |

> 平台侧具体错误码按官方文档补充映射，内部统一收敛到以上一组。

---

## 3. 模型（E2xxx）

| 码 | 名称 | 含义 | 重试 | 界面文案 |
|---|---|---|---|---|
| E2001 | `LLM_NO_PROVIDER` | 未配置模型 | 否 | 请先配置模型 API |
| E2002 | `LLM_AUTH` | Key 无效 / 无权限 | 否 | 模型密钥无效 |
| E2003 | `LLM_TIMEOUT` | 超过 25s 硬超时 | 是（1 次） | 思考超时，请稍后再试 |
| E2004 | `LLM_RATE_LIMIT` | 上游限流 | 是 | 模型繁忙，请稍后再试 |
| E2005 | `LLM_CONTEXT_OVERFLOW` | 上下文超限 | 否 | 对话太长了 |
| E2006 | `LLM_BAD_RESPONSE` | 返回格式不合预期 | 是（1 次） | 模型返回异常 |
| E2007 | `LLM_UNSUPPORTED_MODALITY` | 不支持该种输入 | 否 | 我暂时看不了这类内容 |
| E2008 | `LLM_BUDGET_EXCEEDED` | 超出日预算 | 否 | 今日额度已用完 |

降级链：`LLM_TIMEOUT` → 兜底话术；`LLM_UNSUPPORTED_MODALITY` → 取 ASR / 提示。

---

## 4. 插件 / 规则包（E3xxx）

| 码 | 名称 | 含义 | 重试 | 界面文案 |
|---|---|---|---|---|
| E3001 | `PLUGIN_BAD_ZIP` | 非法压缩包 | 否 | 文件不是有效的插件包 |
| E3002 | `PLUGIN_PATH_TRAVERSAL` | 含 `../` 或绝对路径 | 否 | 插件包包含非法路径 |
| E3003 | `PLUGIN_TOO_LARGE` | 超体积/文件数上限 | 否 | 插件包过大 |
| E3004 | `PLUGIN_BAD_YAML` | YAML 解析失败 | 否 | 插件配置格式错误（第 N 行） |
| E3005 | `PLUGIN_YAML_BOMB` | 别名炸弹 | 否 | 插件配置异常 |
| E3006 | `PLUGIN_BAD_MANIFEST` | 缺字段 / 类型不符 | 否 | 插件清单不完整 |
| E3007 | `PLUGIN_ENGINE_MISMATCH` | `engine_version` 不满足 | 否 | 插件版本与当前程序不兼容 |
| E3008 | `PLUGIN_PERMISSION_DENIED` | `permissions` 非空 | 否 | 插件申请了不允许的权限 |
| E3009 | `PLUGIN_DUP_ID` | id 与已装/内置冲突 | 否 | 插件 ID 已存在 |
| E3010 | `PLUGIN_EXPR_BAD` | 表达式 AST 校验失败 | 否 | 插件公式非法（第 N 个字段） |
| E3011 | `PLUGIN_DEP_CYCLE` | 字段依赖成环 | 否 | 插件字段存在循环依赖 |
| E3012 | `PLUGIN_SELFTEST_FAILED` | 预演未通过 | 否 | 插件自检失败 |
| E3101 | `PLUGIN_RUNTIME_ERROR` | 解释执行异常 | 否 | （不展示）插件执行出错 |
| E3102 | `PLUGIN_TIMEOUT` | 求值超时 | 否 | （不展示） |
| E3201 | `PLUGIN_ORPHAN_DATA` | 该规则下仍有角色卡 | 否 | 请先备份或确认删除 |

---

## 5. 限流 / 额度 / 滥用（E4xxx）

| 码 | 名称 | 含义 | 重试 | 界面文案 |
|---|---|---|---|---|
| E4001 | `RATE_USER` | 单用户频控 | 是 | 慢一点 |
| E4002 | `RATE_GROUP` | 单群频控 | 是 | 本群消息太频繁 |
| E4003 | `RATE_GLOBAL` | 全局 60qpm | 是 | 服务繁忙 |
| E4101 | `REPLY_BUDGET` | 被动回复次数用尽 | 否 | （静默） |
| E4102 | `REPLY_DEADLINE` | 超出 5 分钟窗口 | 否 | （静默） |
| E4201 | `ABUSE_WARNED` | 进入警告状态 | — | 请降低 @ 频率 |
| E4202 | `ABUSE_MUTED` | 已静默 | — | （静默） |
| E4301 | `BUDGET_DAILY_TOKENS` | 日 token 预算耗尽 | 否 | （静默 + 管理端告警） |
| E4302 | `BUDGET_DAILY_MSGS` | 日消息数耗尽 | 否 | （静默 + 管理端告警） |

**注意**：E4101/E4102/E4202 对用户必须**静默**，不回任何内容。

---

## 6. 存储（E5xxx）

| 码 | 名称 | 含义 | 重试 | 界面文案 |
|---|---|---|---|---|
| E5001 | `DB_OPEN_FAILED` | 无法打开数据库 | 否 | 数据库无法打开，请检查目录权限 |
| E5002 | `DB_LOCKED` | 被其他进程占用 | 是 | 数据库被占用（是否重复启动？） |
| E5003 | `DB_MIGRATION_FAILED` | 迁移失败 | 否 | 数据升级失败，已回滚 |
| E5004 | `DB_DISK_FULL` | 磁盘满 | 否 | 磁盘空间不足 |
| E5005 | `DB_CORRUPT` | 完整性检查失败 | 否 | 数据库损坏，请从备份恢复 |
| E5101 | `CHAR_SCHEMA_MISMATCH` | 角色卡不符合 schema | 否 | 角色卡数据与规则包不匹配 |

---

## 7. 运行时 / 环境（E6xxx）

| 码 | 名称 | 含义 | 重试 | 界面文案 |
|---|---|---|---|---|
| E6001 | `PATH_TOO_LONG` | BASE > 120 字符 | 否 | 路径太长，请把程序移到更短的目录 |
| E6002 | `PATH_NOT_WRITABLE` | 目录不可写 | 否 | 程序目录没有写入权限 |
| E6003 | `PATH_NETWORK` | 位于网络驱动器 | 否 | 请不要把程序放在网络盘上运行 |
| E6004 | `DISK_LOW` | 剩余空间 < 500MB | 否 | 磁盘空间不足 |
| E6005 | `UNICODE_PATH_FAILED` | 中文/空格路径写入失败 | 否 | 路径编码异常 |
| E6101 | `WEBVIEW2_MISSING` | 无 WebView2 | — | 已改用浏览器打开 |
| E6102 | `PORT_BIND_FAILED` | 无法绑定本地端口 | 是 | 端口绑定失败 |
| E6103 | `INSTANCE_LOCKED` | 已有实例在运行 | — | 已切到正在运行的窗口 |
| E6201 | `APPID_CONFLICT` | 同机同 appId 另开 | 否 | 该机器人已在另一个实例运行 |
| E6202 | `ARCH_UNSUPPORTED` | 非 x64 | 否 | 当前仅支持 64 位 Windows |
| E6203 | `CLOCK_SKEW` | 系统时间偏差 > 5min | — | 系统时间不准确 |
| E6301 | `OFFLINE` | 网络不可达 | 是 | 当前处于离线状态 |

---

## 8. 管理面（E7xxx）

| 码 | 名称 | 含义 |
|---|---|---|
| E7001 | `CSRF_FAILED` | CSRF 校验失败 |
| E7002 | `ORIGIN_REJECTED` | Origin / Host 不匹配 |
| E7003 | `TOKEN_EXPIRED` | 一次性令牌已用 |
| E7004 | `NOT_FOUND` | 资源不存在 |
| E7005 | `PATH_ESCAPE` | 文件访问越界 |

---

## 9. 日志格式

每条错误日志固定结构：

```json
{
  "ts": "2026-10-29T12:00:00.123+08:00",
  "level": "error",
  "code": "E2003",
  "trace": "5f3a...",
  "group": "…尾号",
  "msg_id": "…尾号",
  "detail": { "provider": "glm", "elapsed_ms": 25012 },
  "retry": 0
}
```

### 9.1 脱敏规则（强制）

以下内容**永不进日志**：

- `access_token` / `Authorization` 头
- `appSecret` / 模型 API Key
- `auth_token=` / `rkey=` 参数
- 完整 openid（只留末 4 位）
- 消息正文全文（只留长度与哈希）

---

## 10. 错误传播原则

| 层 | 职责 |
|---|---|
| Gateway | 转成 `SystemEvent`，不抛业务异常 |
| Router | 只抛 `DROP_*` 或 `E4xxx` |
| Module | 抛 `E4xxx` / `E3xxx`，由引擎兜底 |
| Provider | 抛 `E2xxx`，不重试超过 2 次 |
| Outbound | 抛 `E13xx`，不重试同 `msg_seq` |
| Admin API | 统一包成 `{ code, message, detail }` |

**用户可见文案三原则**：

1. 说人话，不出现错误码
2. 给一个可执行动作（重试 / 检查网络 / 重新配置）
3. 静默类错误（E4101/E4102/E4202）**一个字都不说**
