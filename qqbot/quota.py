"""每日额度：消息数与 token 数，按日自动归零。"""

from __future__ import annotations

import time

from .store import Store


def today() -> str:
    return time.strftime("%Y-%m-%d")


class Quota:
    def __init__(self, store: Store, cfg):
        self.store = store
        self.cfg = cfg

    def snapshot(self) -> dict:
        d = today()
        g = self.store.quota_detail("global", "all", d)
        return {
            "date": d,
            "msgs": g["msgs"],
            "msg_limit": self.cfg.daily_msg_budget,
            "tokens": g["tokens"],
            "token_limit": self.cfg.daily_token_budget,
            "prompt_tokens": g["prompt"],
            "completion_tokens": g["completion"],
            "cached_tokens": g["cached"],
        }

    def allow_message(self, group: str) -> bool:
        d = today()
        g_msgs, g_tokens = self.store.quota_get("global", "all", d)
        # 0 表示不限制
        if self.cfg.daily_msg_budget > 0 and g_msgs >= self.cfg.daily_msg_budget:
            return False
        if self.cfg.daily_token_budget > 0 and g_tokens >= self.cfg.daily_token_budget:
            return False
        return True

    def record_message(self, group: str) -> None:
        d = today()
        self.store.quota_add("global", "all", d, msgs=1)
        self.store.quota_add("group", group, d, msgs=1)

    def record_tokens(self, n: int) -> None:
        if n <= 0:
            return
        self.store.quota_add("global", "all", today(), tokens=n)

    def record_usage(self, usage: dict | None, provider_id: str = "") -> None:
        """只记真实 provider 返回的 usage；mock 的估算不计。"""
        if provider_id == "mock":
            return
        usage = usage or {}
        try:
            prompt = int(usage.get("prompt_tokens") or 0)
            completion = int(usage.get("completion_tokens") or 0)
            total = int(usage.get("total_tokens") or (prompt + completion))
            details = usage.get("prompt_tokens_details") or {}
            cached = (
                int(details.get("cached_tokens") or 0)
                if isinstance(details, dict)
                else 0
            )
        except (TypeError, ValueError):
            return
        if total <= 0:
            return
        self.store.quota_add(
            "global",
            "all",
            today(),
            tokens=total,
            prompt=prompt,
            completion=completion,
            cached=cached,
        )
