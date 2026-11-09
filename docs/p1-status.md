# P1 状态说明

> 完成时间：2026-10-29
> 目标：连接 QQ 网关 → 收到群 @ → 回一条固定文本。

---

## 1. 已实现

| 模块 | 文件 | 说明 |
|---|---|---|
| 路径与实例身份 | `qqbot/paths.py` | 基于 exe 推导、动态路径预算、实例 ID |
| 配置 | `qqbot/config.py` | YAML（ruamel），不含密钥 |
| 凭据 | `qqbot/secrets.py` | DPAPI 加密，机器绑定 |
| 日志 | `qqbot/logging_setup.py` | 轮转 + 强制脱敏 |
| 存储 | `qqbot/store.py` | SQLite WAL：幂等、msg_seq、群、审计 |
| 协议 | `qqbot/gateway/protocol.py` | opcode 编解码 |
| Token | `qqbot/gateway/token.py` | 缓存 + 提前刷新 + singleflight |
| 网关 | `qqbot/gateway/client.py` | 连接 / 心跳 / resume / 重连退避 |
| 出站 | `qqbot/api/sender.py` | 群消息被动回复 |
| 编排 | `qqbot/app.py` | 队列 + worker + 去重 + 回复 |
| 管理面 | `qqbot/api/admin.py` | 仅 127.0.0.1 + Token + Host 校验 |
| 界面 | `qqbot/ui/` | pywebview 窗口，失败降级浏览器 |
| 打包 | `build.ps1` | onedir + 路径预算 |

---

## 2. 已验证

| 项 | 结果 |
|---|---|
| 单元测试 | 18 项通过 |
| 打包体积 | 37.2 MB |
| 冷启动 | 1–2 秒 |
| 迁移到中文+空格路径 | ✅ |
| 单实例锁 | ✅ 第二个进程退出 |
| 实例 ID 随路径变化 | ✅ |
| 无 token 访问 API | ✅ 403 |
| 日志脱敏 | ✅ 未出现明文凭据 |
| 假凭据错误路径 | ✅ 状态转 fatal，提示人话 |

---

## 3. 真机验证结果

已使用真实 AppID / AppSecret 跑通：

| 项 | 结果 |
|---|---|
| token 获取 | ✅ |
| WS 连接与 identify | ✅ |
| 群 @ 消息接收 | ✅ |
| 被动回复发送 | ✅ |
| 界面状态流转 | ✅ `connecting → identifying → ready` |

**P1 目标达成：能连、能收、能回。**

### 仍未覆盖

- 断线后 resume 补发（需长时间运行才能遇到）
- 平台错误码的真实映射（目前按类别收敛）
- 沙箱环境（`sandbox.api.sgroup.qq.com`），当前只连正式环境

---

## 4. P1 之后的已知限制

| # | 限制 | 计划 |
|---|---|---|
| 1 | 群默认自动放行（`auto_approve_groups=true`） | P3 改为 owner 绑定 + 审批 |
| 2 | 回复内容为固定文本 | P2 接模型 |
| 3 | 无滥用防护 | P4 |
| 4 | 无指令路由 / 规则包 | P5–P6 |
| 5 | 窗口关闭即退出（无托盘） | P6 |
| 6 | 重复启动只会打开浏览器，不聚焦已有窗口 | P6 |
| 7 | 被动回复 5 分钟窗口未做超时保护 | P2 |

---

## 5. 开发命令

```powershell
# 首次
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-dev.txt

# 跑测试
.\.venv\Scripts\python.exe -m unittest discover -s tests -v

# 开发模式
.\run-dev.ps1

# 无窗口（调试）
$env:QQBOT_NO_WINDOW=1; .\run-dev.ps1

# 打包
.\build.ps1
```

产物：`dist\QQChatbot\`（整个文件夹即成品）
