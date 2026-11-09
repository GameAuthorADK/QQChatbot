"""YAML 读写封装。

之所以不直接用 PyYAML：它在 Python 3.15 上没有可用 wheel，需要 C 编译器。
ruamel.yaml 是纯 Python 实现，打包后体积与兼容性都更好。
"""

from __future__ import annotations

import io

from ruamel.yaml import YAML

_safe = YAML(typ="safe")
_safe.allow_duplicate_keys = False

_dumper = YAML()
_dumper.default_flow_style = False
_dumper.allow_unicode = True
_dumper.width = 4096


def load(text: str):
    return _safe.load(text) or {}


def load_file(path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return _safe.load(f) or {}


def dump(data) -> str:
    buf = io.StringIO()
    _dumper.dump(data, buf)
    return buf.getvalue()
