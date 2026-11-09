"""代码插件执行器（子进程）。

用法（由主进程调用，不面向用户）：

    QQChatbot.exe --plugin-worker <插件.py> <输入.json> <输出.json>

安全边界：
  - 独立子进程，崩溃 / 死循环不影响主程序
  - 安装审计钩子后才执行插件代码，拦截网络、写文件、子进程、ctypes
  - 输出文件句柄在安装钩子之前打开，插件无法借它写别的东西
  - 超时由主进程控制并强制结束

注意：审计钩子是进程内的，挡得住误用和普通恶意代码，但不是内核级沙箱。
代码插件应被视为「自己写的受信任扩展」，不用于运行来路不明的文件。
"""

from __future__ import annotations

import json
import os
import sys
import traceback
import types

#: 直接拒绝的审计事件
_BLOCKED = {
    "socket.connect",
    "socket.bind",
    "socket.getaddrinfo",
    "socket.gethostbyname",
    "socket.sethostname",
    "subprocess.Popen",
    "os.system",
    "os.exec",
    "os.spawn",
    "os.posix_spawn",
    "os.remove",
    "os.rename",
    "os.replace",
    "os.mkdir",
    "os.rmdir",
    "os.chmod",
    "os.chown",
    "os.link",
    "os.symlink",
    "os.utime",
    "shutil.copyfile",
    "shutil.copymode",
    "shutil.copystat",
    "shutil.move",
    "shutil.rmtree",
    "ctypes.dlopen",
    "ctypes.dlsym",
    "ctypes.dlsym/handle",
    "ctypes.call_function",
}

_WRITE_FLAGS = (
    os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND | os.O_TRUNC
)


def _install_guard() -> None:
    def hook(event: str, args) -> None:
        if event in _BLOCKED:
            raise PermissionError(f"插件禁止的操作：{event}")

        if event == "open":
            mode = args[1] if len(args) > 1 else None
            if isinstance(mode, str):
                if any(c in mode for c in "wax+"):
                    raise PermissionError("插件不允许写文件")
                return
            flags = args[2] if len(args) > 2 else 0
            if isinstance(flags, int) and flags & _WRITE_FLAGS:
                raise PermissionError("插件不允许写文件")

    sys.addaudithook(hook)


def _fail(handle, code: str, message: str) -> int:
    handle.write(json.dumps({"ok": False, "code": code, "error": message}, ensure_ascii=False))
    handle.flush()
    return 0


def run(plugin_path: str, in_path: str, out_path: str, func: str = "handle") -> int:
    # 输出句柄必须先打开：钩子装上之后就再也拿不到写权限了
    out = open(out_path, "w", encoding="utf-8")
    try:
        try:
            with open(in_path, "r", encoding="utf-8") as fh:
                payload = json.load(fh)
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}

        sys.dont_write_bytecode = True
        _install_guard()

        try:
            with open(plugin_path, "r", encoding="utf-8", errors="replace") as fh:
                source = fh.read()
            code = compile(source, plugin_path, "exec")
            module = types.ModuleType("qqbot_plugin")
            module.__file__ = plugin_path
            module.__name__ = "qqbot_plugin"
            exec(code, module.__dict__)

            handler = getattr(module, func, None)
            if not callable(handler):
                raise RuntimeError(f"插件缺少 {func}(ctx)")

            result = handler(payload)
        except PermissionError as exc:
            return _fail(out, "E3110", str(exc) or "插件尝试了被禁止的操作")
        except BaseException as exc:  # 含 SystemExit：插件不能自己结束进程
            return _fail(out, "E3101", f"{type(exc).__name__}: {exc}")

        reply = ""
        extra = None
        card = None
        if isinstance(result, dict):
            reply = str(result.get("reply") or "")
            extra = result.get("store")
            card = result.get("card")
        elif result is not None:
            reply = str(result)

        data = {"ok": True, "reply": reply[:8000]}
        if isinstance(extra, dict):
            data["store"] = extra
        if isinstance(card, dict):
            data["card"] = card
        out.write(json.dumps(data, ensure_ascii=False))
        out.flush()
        return 0
    except BaseException:
        try:
            out.write(json.dumps({"ok": False, "code": "E3101", "error": "插件执行失败"}))
            out.flush()
        except Exception:
            pass
        return 0
    finally:
        try:
            out.close()
        except Exception:
            pass


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) < 3:
        return 2
    func = argv[3] if len(argv) > 3 else "handle"
    return run(argv[0], argv[1], argv[2], func)


if __name__ == "__main__":
    raise SystemExit(main())
