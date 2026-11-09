"""模型 Provider 抽象。

设计约束：
  - 只暴露"给定消息列表，返回一段文本"
  - 不做流式（群聊无流式接口）
  - 不信任静态能力声明，用 probe() 实测
  - 密钥由引擎注入，Provider 不读配置
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass
class ChatMessage:
    role: Role
    content: str | list

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class Completion:
    text: str
    model: str = ""
    usage: dict = field(default_factory=dict)
    finish_reason: str = ""


@dataclass
class ProbeResult:
    ok: bool
    detail: str = ""
    latency_ms: int = 0


class Provider(Protocol):
    id: str

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        timeout: float,
        max_tokens: int,
    ) -> Completion: ...

    async def probe(self) -> ProbeResult: ...

    async def aclose(self) -> None: ...


def build_messages(system: str, history: list[dict], user: "str | list") -> list[ChatMessage]:
    """系统提示 + 历史 + 本轮输入。"""
    out: list[ChatMessage] = []
    if system:
        out.append(ChatMessage("system", system))
    for m in history:
        role = m.get("role")
        content = (m.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            out.append(ChatMessage(role, content))
    out.append(ChatMessage("user", user))
    return out
