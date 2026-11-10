# 第三方依赖与许可证说明

本项目（QQChatbot）自身代码以 MIT 许可证发布，详见 [LICENSE](LICENSE)。

发布的可执行文件里包含以下第三方组件。各组件的版权归其作者所有，使用时请遵守对应许可证。

| 组件 | 许可证 | 项目地址 |
|---|---|---|
| pywebview | BSD-3-Clause | https://github.com/r0x0r/pywebview |
| FastAPI | MIT | https://github.com/fastapi/fastapi |
| Uvicorn | BSD-3-Clause | https://github.com/encode/uvicorn |
| HTTPX | BSD-3-Clause | https://github.com/encode/httpx |
| websockets | BSD-3-Clause | https://github.com/python-websockets/websockets |
| ruamel.yaml | MIT | https://sourceforge.net/projects/ruamel-yaml/ |
| Pillow | HPND | https://github.com/python-pillow/Pillow |
| pystray | **LGPL-3.0** | https://github.com/moses-palmer/pystray |
| six | MIT | https://github.com/benjaminp/six |
| pythonnet | MIT | https://github.com/pythonnet/pythonnet |
| PyInstaller | GPL-2.0-or-later（含 bootloader 例外） | https://github.com/pyinstaller/pyinstaller |
| Microsoft Edge WebView2 Runtime | Microsoft 软件许可条款 | https://developer.microsoft.com/microsoft-edge/webview2/ |

## 关于 pystray（LGPL-3.0）

托盘功能使用 pystray，许可证为 LGPL-3.0。分发打包后的程序时：

- 本文件和 pystray 的许可证应随程序一起提供
- pystray 的源码可从上面的项目地址获取
- 本项目同时提供完整源码和构建脚本，可按需重新构建或替换该组件

## 关于 PyInstaller

PyInstaller 的 bootloader 采用 GPL-2.0-or-later，并带有允许分发打包应用的例外条款。  
打包后的应用不需要以 GPL 开源，但应保留 PyInstaller 的许可证说明。

## 关于 WebView2

程序使用系统已安装的 Microsoft Edge WebView2 Runtime，不随压缩包分发该 Runtime。

## 游戏规则与商标

跑团规则包是对游戏规则的原创实现，只包含机制、字段、数值和简短说明，不包含规则书原文、表格或美术。  
游戏名称、商标和规则书版权归各自权利人所有，本项目与各游戏发行商无关。
