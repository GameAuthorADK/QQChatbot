"""桌面窗口（pywebview），失败时降级为系统浏览器。"""

from __future__ import annotations

import ctypes
import logging
import os
import time
import webbrowser

log = logging.getLogger(__name__)
_ACTIVE_API = None

_SW_HIDE = 0
_SW_RESTORE = 9

_WNDENUMPROC = (
    ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    if hasattr(ctypes, "WINFUNCTYPE")
    else None
)


def _find_hwnd(title: str) -> int:
    """查找本进程里标题匹配的顶层窗口。

    不能用 FindWindowW(None, title)：用户机器上可能恰好有同名窗口（例如
    打开着名为 QQChatbot 的资源管理器窗口），会误隐藏或误恢复别的程序。
    """
    if os.name != "nt":
        return 0
    user32 = ctypes.windll.user32
    user32.EnumWindows.argtypes = [_WNDENUMPROC, ctypes.c_void_p]
    user32.GetWindowThreadProcessId.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_ulong),
    ]
    user32.GetWindowTextLengthW.argtypes = [ctypes.c_void_p]
    user32.GetWindowTextW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]
    user32.GetClassNameW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]

    pid = os.getpid()
    matches: list[tuple[int, bool]] = []

    @_WNDENUMPROC
    def _callback(hwnd, _lparam):
        owner = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                text = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, text, length + 1)
                if text.value == title:
                    cls = ctypes.create_unicode_buffer(256)
                    user32.GetClassNameW(hwnd, cls, 256)
                    matches.append((int(hwnd), "WindowsForms" in cls.value))
        return True

    user32.EnumWindows(_callback, 0)
    if not matches:
        return 0
    # 优先真正的 WebView2 主窗口
    matches.sort(key=lambda item: not item[1])
    return matches[0][0]


def _show_hwnd(title: str) -> bool:
    hwnd = _find_hwnd(title)
    if not hwnd:
        return False
    try:
        user32 = ctypes.windll.user32
        user32.ShowWindow(hwnd, _SW_RESTORE)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception:
        return False


def _hide_hwnd(title: str) -> bool:
    hwnd = _find_hwnd(title)
    if not hwnd:
        return False
    try:
        ctypes.windll.user32.ShowWindow(hwnd, _SW_HIDE)
        return True
    except Exception:
        return False


def _close_action() -> str:
    """读取「点 X」的行为：tray=缩到托盘，exit=退出程序。"""
    try:
        from ..config import load

        action = str(getattr(load(), "close_action", "tray") or "tray").lower()
        return action if action in ("tray", "exit") else "tray"
    except Exception:
        return "tray"


def show_existing() -> bool:
    """从第二个实例唤起已运行窗口。"""
    api = _ACTIVE_API
    if api is None:
        return False
    try:
        api.show()
        return True
    except Exception:
        return False


def _tray_image():
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((4, 4, 60, 60), radius=16, fill=(45, 108, 223, 255))
    draw.text((21, 18), "Q", fill=(255, 255, 255, 255))
    return img


class _WindowApi:
    def __init__(self) -> None:
        self.window = None
        self.icon = None
        self.title = "QQChatbot"
        self._allow_close = False

    def _restore(self, icon, item) -> None:
        # 不在图标自己的消息线程里 stop（容易死锁），show() 里会把图标隐藏，
        # 退出时再统一停止。
        self.show()

    def show(self) -> None:
        # 托盘图标只在窗口隐藏时显示
        if self.icon is not None:
            try:
                self.icon.visible = False
            except Exception:
                pass
        # 用 Win32 操作窗口，避免从托盘/HTTP 线程直接碰 WebView2 造成未响应
        if _show_hwnd(self.title):
            return
        if self.window is not None:
            try:
                self.window.show()
                self.window.restore()
            except Exception:
                pass

    def _quit(self, icon, item) -> None:
        self._allow_close = True
        try:
            icon.stop()
        except Exception:
            pass
        self.icon = None
        # 托盘回调线程里 destroy WebView2 可能卡住，直接结束进程；
        # 数据库是 WAL，OS 会释放实例锁。
        try:
            logging.shutdown()
        except Exception:
            pass
        os._exit(0)

    def _hide_to_tray(self) -> bool:
        """隐藏窗口并显示托盘图标；失败返回 False。"""
        if self.window is None:
            return False
        try:
            import pystray

            if self.icon is None:
                menu = pystray.Menu(
                    pystray.MenuItem(
                        "打开管理界面", self._restore, default=True
                    ),
                    pystray.MenuItem("退出", self._quit),
                )
                self.icon = pystray.Icon(
                    "QQChatbot", _tray_image(), "QQChatbot", menu
                )
                self.icon.run_detached()
            else:
                try:
                    self.icon.visible = True
                except Exception:
                    pass
            if not _hide_hwnd(self.title):
                self.window.hide()
            log.info("窗口已隐藏到托盘")
            return True
        except Exception as exc:
            log.warning("托盘最小化失败：%s", exc)
            return False

    def _on_closing(self) -> bool:
        """点窗口 X：按设置缩到托盘，或直接退出程序。"""
        if self._allow_close:
            return True
        if _close_action() == "exit":
            self._allow_close = True
            return True
        if self._hide_to_tray():
            return False
        return True


def open_window(url: str, title: str = "QQChatbot", devtools: bool = False) -> None:
    """阻塞直到窗口关闭。"""
    global _ACTIVE_API
    try:
        import webview  # type: ignore

        # 允许下载（备份、导出插件、诊断包），否则 WebView2 会直接取消
        webview.settings["ALLOW_DOWNLOADS"] = True
        api = _WindowApi()
        api.title = title
        _ACTIVE_API = api
        # 不要给 create_window 传带 window/icon 引用的对象作为 js_api：pywebview
        # 会递归遍历它的属性，最终递归进 WebView2 控件，导致界面未响应。
        api.window = webview.create_window(
            title,
            url,
            width=1000,
            height=760,
            min_size=(820, 620),
        )
        api.window.events.closing += api._on_closing
        webview.start(debug=devtools)
        if api.icon is not None:
            try:
                api.icon.stop()
            except Exception:
                pass
        return
    except Exception as exc:
        log.error("无法创建原生窗口（%s），降级到浏览器", exc)

    try:
        webbrowser.open(url)
    except Exception:
        log.exception("打开浏览器也失败了")

    # 无窗口时保持主线程存活，避免服务被回收
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return
