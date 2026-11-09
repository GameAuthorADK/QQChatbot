"""滥用防护：normal → warned → muted 状态机。

要点：
  - 警告消息本身不计入计数
  - muted 完全静默，不回任何内容
  - 状态持久化到数据库，重启后仍然有效
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Literal

from .ratelimit import SlidingWindow
from .store import Store

log = logging.getLogger(__name__)

Action = Literal["ok", "warn", "mute", "muted"]


@dataclass
class Decision:
    action: Action
    count: int = 0
    message: str = ""


class AbuseGuard:
    def __init__(self, store: Store, cfg):
        self.store = store
        self.cfg = cfg
        self.window = SlidingWindow(1000, cfg.abuse_window_s)
        self._warned_at: dict[tuple[str, str], float] = {}

    # ── 判定 ──────────────────────────────────────────────
    def reset(self) -> None:
        self.window = SlidingWindow(1000, self.cfg.abuse_window_s)
        self._warned_at.clear()

    def check(self, group: str, member: str) -> Decision:
        key = (group, member)

        # 已静默：直接丢，且不再计数
        if self.store.is_muted(group, member):
            return Decision("muted")

        count = self.window.hit(f"{group}|{member}")
        state = self._state(key)

        if state == "normal":
            if count > self.cfg.abuse_warn_threshold:
                self._warned_at[key] = time.time()
                log.info("滥用警告 group=%s member=%s count=%d", group[-4:], member[-4:], count)
                self.store.audit(
                    "abuse.warn", target=f"{group[-6:]}/{member[-6:]}",
                    actor=member, count=count,
                )
                return Decision("warn", count=count, message=self.cfg.abuse_warn_text)
            return Decision("ok", count=count)

        # warned
        elapsed = time.time() - self._warned_at.get(key, 0.0)
        if elapsed >= self.cfg.abuse_warn_cooldown_s and count > self.cfg.abuse_mute_threshold:
            self.store.mute(group, member, by="auto", reason=f"{count}@{self.cfg.abuse_window_s}s")
            self._warned_at.pop(key, None)
            log.warning("滥用静默 group=%s member=%s count=%d", group[-4:], member[-4:], count)
            return Decision("mute", count=count)
        return Decision("ok", count=count)

    def _state(self, key: tuple[str, str]) -> str:
        return "warned" if key in self._warned_at else "normal"

    # ── 管理 ──────────────────────────────────────────────
    def unmute(self, group: str, member: str, by: str = "admin") -> bool:
        changed = self.store.unmute(group, member, by=by)
        if changed:
            self._warned_at.pop((group, member), None)
            self.window.reset(f"{group}|{member}")
            self.store.audit("abuse.unmute", target=f"{group[-6:]}/{member[-6:]}", actor=by)
        return changed

    def list_muted(self) -> list[dict]:
        return self.store.muted_list()
