# QQChatbot

一个本地运行的简易 QQ 群聊机器人管理端：包括人设、记忆、跑团、小游戏等功能模块。

基于 DeepSeek V4.1 Flash 开发。

> 完整中文使用手册见 [README.txt](README.txt)。  
> 当前版本：0.2.7

## 功能

- QQ 官方机器人网关（WebSocket），支持 @ 消息与群内全部消息
- 人设、禁止事项、回复风格、人设锚点和人设自检
- 全局回复设置与按群覆盖，支持提示词/回复/关键词导入导出
- 自动长期记忆与手动整理，按群、按人、按模式隔离
- 群聊监听、主动发起话题、复读与接梗
- 跑团规则包：COC7th、DND5e、妄想症 2e / 25th
- 小游戏：21 点、每日 Boss、文字地牢、钓鱼、每日运势、猜成语
- 插件模式：规则包、代码插件、自定义模式
- 本地管理界面（FastAPI + pywebview），无外部服务依赖
- 点 X 缩到托盘，可设置点 X 直接退出；最小化保留在任务栏

## 环境

- Windows 10 / 11，64 位
- Python 3.11+（开发和打包使用 3.15）

## 直接使用

下载 Release 里的 `QQChatbot-0.2.7-win64.zip`，解压后双击 `QQChatbot.exe`。  
第一次启动会生成 `config`、`data`、`logs` 等目录，请不要删除。

## 从源码运行

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run-dev.ps1
```

## 打包

```powershell
.\build.ps1
```

产物在 `dist\QQChatbot\`。打包脚本会保留 `config`、`data`、`logs`、`runtime`、`profiles`、`plugins` 里的用户数据。

## 数据与安全

- 所有数据都保存在程序目录，不上传第三方服务器
- AppSecret、模型 Key 使用 Windows DPAPI 加密保存在本机
- 管理界面只监听 `127.0.0.1`，接口需要本地会话 Token
- `config/`、`data/`、`logs/`、`runtime/`、`profiles/` 已加入 `.gitignore`，不会进入仓库

## 测试

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
```

## 许可证

[MIT](LICENSE)
