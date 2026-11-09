"""代码插件的发现与执行（主进程侧）。

插件约定：一个 .py 文件就是一个插件，放在程序目录的 plugins/ 下。

    NAME = "每日运势"
    DESCRIPTION = "每人每天一签"
    COMMANDS = {"lucky": "看看今天的运势"}

    def handle(ctx):
        return "……"

发现阶段只用 ast 读字面量，不执行插件代码。
执行阶段另起子进程（见 plugin_worker.py），3 秒超时强杀。
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from .errors import PLUGIN_LOAD_FAILED, PLUGIN_TIMEOUT
from .paths import FROZEN, PLUGINS_DIR, RUNTIME_DIR

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 3.0
MAX_FILE_BYTES = 512 * 1024
MAX_STORE_BYTES = 100_000


class PluginError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class CodePlugin:
    id: str
    path: Path
    name: str
    description: str = ""
    commands: dict = field(default_factory=dict)
    file_hash: str = ""
    error: str = ""


def _hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def read_meta(path: Path) -> CodePlugin:
    """只解析不执行：从 AST 里读取 NAME / DESCRIPTION / COMMANDS。"""
    plugin_id = path.stem
    info = CodePlugin(id=plugin_id, path=path, name=plugin_id, file_hash=_hash(path))

    try:
        if path.stat().st_size > MAX_FILE_BYTES:
            info.error = "文件过大（上限 512 KB）"
            return info
        source = path.read_text("utf-8", errors="replace")
        tree = ast.parse(source)
    except SyntaxError as exc:
        info.error = f"语法错误：第 {exc.lineno} 行 {exc.msg}"
        return info
    except Exception as exc:
        info.error = f"读取失败：{exc}"
        return info

    has_handle = False
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "handle":
            has_handle = True
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "NAME":
                try:
                    info.name = str(ast.literal_eval(node.value))[:40]
                except Exception:
                    pass
            elif target.id == "DESCRIPTION":
                try:
                    info.description = str(ast.literal_eval(node.value))[:200]
                except Exception:
                    pass
            elif target.id == "COMMANDS":
                try:
                    value = ast.literal_eval(node.value)
                    if isinstance(value, dict):
                        info.commands = {
                            str(k)[:24]: str(v)[:80] for k, v in value.items()
                        }
                except Exception:
                    info.error = "COMMANDS 必须是字面量字典"

    if not has_handle:
        info.error = info.error or "缺少 handle(ctx)"
    if not info.commands:
        info.error = info.error or "COMMANDS 为空"
    return info


def discover(base: Path | None = None) -> list[CodePlugin]:
    base = base or PLUGINS_DIR
    out: list[CodePlugin] = []
    if not base.exists():
        return out
    for path in sorted(base.glob("*.py")):
        if path.name.startswith("_"):
            continue
        out.append(read_meta(path))
    return out


def _worker_cmd(plugin_path: Path, in_path: str, out_path: str, func: str = "handle") -> list[str]:
    args = ["--plugin-worker", str(plugin_path), in_path, out_path, func]
    if FROZEN:
        return [sys.executable, *args]
    return [sys.executable, "-m", "qqbot", *args]


def _cleanup(*paths: str) -> None:
    for p in paths:
        try:
            Path(p).unlink(missing_ok=True)
        except Exception:
            pass


def _worker_env() -> dict:
    env = os.environ.copy()
    if not FROZEN:
        root = str(Path(__file__).resolve().parent.parent)
        old = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = root + (os.pathsep + old if old else "")
    return env


def run_plugin(
    plugin: CodePlugin,
    payload: dict,
    timeout: float = DEFAULT_TIMEOUT,
    func: str = "handle",
) -> dict:
    """执行一次插件调用，返回 {reply, store}；失败抛 PluginError。"""
    if plugin.error:
        raise PluginError(PLUGIN_LOAD_FAILED, plugin.error)

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    in_path = out_path = ""

    try:
        fd, in_path = tempfile.mkstemp(dir=str(RUNTIME_DIR), prefix="plug_in_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False)

        fd2, out_path = tempfile.mkstemp(dir=str(RUNTIME_DIR), prefix="plug_out_", suffix=".json")
        os.close(fd2)

        try:
            proc = subprocess.run(
                _worker_cmd(plugin.path, in_path, out_path, func),
                capture_output=True,
                timeout=timeout,
                cwd=str(plugin.path.parent),
                env=_worker_env(),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except subprocess.TimeoutExpired:
            raise PluginError(PLUGIN_TIMEOUT, f"插件执行超过 {timeout:.0f} 秒，已中止")

        raw = ""
        try:
            raw = Path(out_path).read_text("utf-8")
        except Exception:
            pass

        if not raw.strip():
            stderr = (proc.stderr or b"").decode("utf-8", "replace").strip()
            detail = stderr.splitlines()[-1] if stderr else f"退出码 {proc.returncode}"
            raise PluginError(PLUGIN_LOAD_FAILED, f"插件没有返回结果（{detail[:160]}）")

        try:
            data = json.loads(raw)
        except Exception:
            raise PluginError(PLUGIN_LOAD_FAILED, "插件返回的不是合法 JSON")

        if not isinstance(data, dict) or not data.get("ok"):
            code = str((data or {}).get("code") or PLUGIN_LOAD_FAILED)
            message = str((data or {}).get("error") or "插件执行失败")
            raise PluginError(code, message[:300])

        store = data.get("store")
        if isinstance(store, dict):
            if len(json.dumps(store, ensure_ascii=False).encode("utf-8")) > MAX_STORE_BYTES:
                data.pop("store", None)
        return data
    finally:
        _cleanup(in_path, out_path)
