"""内置插件注册表。

内置插件随程序发布，没有文件，不能导入导出，只能整体启用或关闭。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Builtin:
    id: str
    name: str
    description: str
    commands: tuple[str, ...]
    #: 对应 InstanceConfig 上的开关字段
    config_key: str
    #: 清空业务数据时恢复到的默认状态
    default_enabled: bool = True


BUILTINS: tuple[Builtin, ...] = (
    Builtin(
        id="wiki",
        name="游戏 Wiki 查询",
        description="在群里用 /wiki 关键词 查游戏资料，返回摘要和链接。",
        commands=("/wiki", "/百科"),
        config_key="wiki_enabled",
    ),
    Builtin(
        id="repeat",
        name="复读与接梗",
        description="群友聊天时，偶尔复读一句或接个梗。",
        commands=(),
        config_key="repeat_enabled",
        default_enabled=False,
    ),
)

BY_ID = {b.id: b for b in BUILTINS}


def get(builtin_id: str) -> Builtin | None:
    return BY_ID.get(builtin_id)


def is_enabled(cfg, builtin_id: str) -> bool:
    item = get(builtin_id)
    if item is None:
        return False
    return bool(getattr(cfg, item.config_key, False))


def set_enabled(cfg, builtin_id: str, enabled: bool) -> bool:
    item = get(builtin_id)
    if item is None:
        return False
    setattr(cfg, item.config_key, bool(enabled))
    return True


def snapshot(cfg) -> list[dict]:
    return [
        {
            "id": b.id,
            "name": b.name,
            "description": b.description,
            "commands": list(b.commands),
            "enabled": bool(getattr(cfg, b.config_key, False)),
        }
        for b in BUILTINS
    ]
