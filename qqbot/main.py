"""进程入口：单实例、自检、启动服务与窗口。"""

from __future__ import annotations

import asyncio
import ctypes
import json
import logging
import os
import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from . import config, logging_setup, paths
from .api.admin import SESSION_TOKEN, create_app
from .app import Runtime
from .paths import LOCK_PATH, RUNTIME_DIR

log = logging.getLogger(__name__)


# ── 小工具 ────────────────────────────────────────────────
def message_box(text: str, title: str = "QQChatbot") -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, text, title, 0x10)
    except Exception:
        print(text, file=sys.stderr)


class InstanceLock:
    """同文件夹单实例锁。进程退出由 OS 释放。"""

    def __init__(self, path=LOCK_PATH):
        self.path = path
        self._fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = open(self.path, "a+b")
        try:
            import msvcrt

            self._fh.seek(0)
            msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
            self._fh.seek(0)
            self._fh.truncate()
            self._fh.write(str(os.getpid()).encode())
            self._fh.flush()
            return True
        except OSError:
            self._fh.close()
            self._fh = None
            return False

    def release(self) -> None:
        if not self._fh:
            return
        try:
            import msvcrt

            self._fh.seek(0)
            msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
        try:
            self._fh.close()
        except Exception:
            pass
        self._fh = None


def _bind_socket() -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    sock.setblocking(False)
    return sock


# ── 主流程 ────────────────────────────────────────────────
def run() -> int:
    argv = sys.argv[1:]
    if argv and argv[0] == "--plugin-worker":
        from .plugin_worker import main as worker_main

        return worker_main(argv[1:])

    paths.ensure_dirs()

    cfg = config.load()
    logging_setup.setup(cfg.log_level)

    ok, detail = paths.check_base_path()
    if not ok:
        log.error("路径检查失败: %s", detail)
        message_box(detail, "无法启动")
        return 2

    if paths.is_network_path():
        log.warning("程序位于网络路径，SQLite 锁可能不可靠")

    if sys.maxsize <= 2**32:
        message_box("当前仅支持 64 位 Windows。", "无法启动")
        return 2

    lock = InstanceLock()
    if not lock.acquire():
        # 优先唤起已运行窗口；它可能正在退出，唤不起来再等锁释放。
        if _focus_existing():
            return 0
        acquired = False
        for _ in range(12):
            time.sleep(0.25)
            if lock.acquire():
                acquired = True
                break
        if not acquired:
            log.info("已有实例在运行，无法唤起界面")
            return 0

    loop = asyncio.new_event_loop()
    loop_thread = threading.Thread(target=loop.run_forever, name="asyncio", daemon=True)
    loop_thread.start()

    rt = Runtime()
    try:
        asyncio.run_coroutine_threadsafe(rt.start(), loop).result(timeout=15)

        sock = _bind_socket()
        port = sock.getsockname()[1]
        app = create_app(rt)
        server = uvicorn.Server(
            uvicorn.Config(app, log_config=None, access_log=False, lifespan="on")
        )
        asyncio.run_coroutine_threadsafe(server.serve(sockets=[sock]), loop)

        # 等服务真正起来
        for _ in range(100):
            if server.started:
                break
            time.sleep(0.05)

        url = f"http://127.0.0.1:{port}/?t={SESSION_TOKEN}"
        (RUNTIME_DIR / "url.txt").write_text(url, encoding="utf-8")
        log.info("管理界面: http://127.0.0.1:%d/", port)

        from .ui import open_window

        if os.environ.get("QQBOT_NO_WINDOW") == "1":
            log.info("headless 模式：不打开窗口（仅用于验证）")
            while True:
                time.sleep(1)
        else:
            try:
                open_window(url, "QQChatbot", devtools=cfg.open_devtools)
            except Exception:
                log.exception("窗口异常退出")

        # 收尾
        server.should_exit = True
        asyncio.run_coroutine_threadsafe(rt.shutdown(), loop).result(timeout=20)
    except Exception as exc:
        log.exception("启动失败")
        message_box(f"启动失败：\n{exc}", "QQChatbot")
        return 1
    finally:
        try:
            loop.call_soon_threadsafe(loop.stop)
        except Exception:
            pass
        lock.release()

    return 0


def _focus_existing() -> bool:
    """尝试唤起已运行实例的窗口或浏览器界面。"""
    if os.environ.get("QQBOT_NO_WINDOW") == "1":
        log.info("已有实例在运行（headless，不唤起界面）")
        return False
    url_file = RUNTIME_DIR / "url.txt"
    if not url_file.exists():
        log.warning("已有实例在运行，但找不到管理界面地址")
        return False
    try:
        url = url_file.read_text("utf-8").strip()
        if "/?t=" in url:
            base, token = url.split("/?t=", 1)
            req = urllib.request.Request(
                base + "/api/window/show",
                method="POST",
                headers={"X-Token": token},
            )
            opener = urllib.request.build_opener(
                urllib.request.ProxyHandler({})
            )
            try:
                with opener.open(req, timeout=3) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode("utf-8") or "{}")
                        if data.get("ok"):
                            return True
            except Exception:
                log.info("唤起已运行窗口失败，尝试打开浏览器")
        webbrowser.open(url)
        return True
    except Exception:
        log.warning("已有实例在运行，但无法唤起界面")
        return False
