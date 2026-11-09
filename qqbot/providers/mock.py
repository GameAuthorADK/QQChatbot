"""假 Provider：不需要任何 key，用于跑通链路。

行为刻意做得"可观测"：回复里会带上收到内容与历史轮数，
这样从群里就能确认上下文是否生效。
"""

from __future__ import annotations

import asyncio
import time

from .. import errors
from .base import ChatMessage, Completion, ProbeResult


class MockProvider:
    id = "mock"

    def __init__(self, prefix: str = "收到"):
        self.prefix = prefix

    @staticmethod
    def _text(content) -> str:
        if isinstance(content, str):
            return content
        parts = []
        for item in content or []:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text") or ""))
        return " ".join(p for p in parts if p)

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        timeout: float,
        max_tokens: int,
    ) -> Completion:
        started = time.perf_counter()
        # 模拟一点延迟，让"输入中"的体验接近真实
        await asyncio.sleep(0.35)

        system = self._text(next((m.content for m in messages if m.role == "system"), ""))
        turns = sum(1 for m in messages if m.role == "user")
        last_user = self._text(
            next((m.content for m in reversed(messages) if m.role == "user"), "")
        )

        text = (
            f"{self.prefix}：{last_user[:80]}\n"
            f"——（假模型：上下文 {turns} 轮，系统提示 {len(system)} 字）"
        )
        if len(text) > max_tokens * 4:
            text = text[: max_tokens * 4]

        elapsed = int((time.perf_counter() - started) * 1000)
        approx_tokens = max(
            1, (sum(len(self._text(m.content)) for m in messages) + len(text)) // 3
        )
        return Completion(
            text=text,
            model="mock",
            usage={"latency_ms": elapsed, "total_tokens": approx_tokens},
        )

    async def probe(self) -> ProbeResult:
        started = time.perf_counter()
        await asyncio.sleep(0.05)
        return ProbeResult(
            ok=True,
            detail="假模型就绪（无需密钥）",
            latency_ms=int((time.perf_counter() - started) * 1000),
        )

    async def aclose(self) -> None:
        return None


class FailingProvider:
    """用于测试超时与失败降级。"""

    id = "failing"

    async def complete(self, messages, *, timeout, max_tokens):
        raise errors.BotError(errors.LLM_TIMEOUT, "模拟超时")

    async def probe(self) -> ProbeResult:
        return ProbeResult(ok=False, detail="故意失败")

    async def aclose(self) -> None:
        return None
