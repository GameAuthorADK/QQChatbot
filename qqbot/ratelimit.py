"""滑动窗口限流。内存实现，重启清空（可接受）。"""

from __future__ import annotations

import threading
import time
from collections import deque


class SlidingWindow:
    """按 key 统计窗口内事件数。"""

    def __init__(self, limit: int, window_s: float):
        self.limit = max(1, limit)
        self.window_s = max(1.0, window_s)
        self._data: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def configure(self, limit: int, window_s: float) -> None:
        """运行期调整阈值，不清空已有计数。"""
        with self._lock:
            self.limit = max(1, int(limit))
            self.window_s = max(1.0, float(window_s))

    def _prune(self, q: deque[float], now: float) -> None:
        edge = now - self.window_s
        while q and q[0] < edge:
            q.popleft()

    def hit(self, key: str) -> int:
        """记录一次并返回窗口内次数。"""
        now = time.time()
        with self._lock:
            q = self._data.setdefault(key, deque())
            self._prune(q, now)
            q.append(now)
            return len(q)

    def count(self, key: str) -> int:
        now = time.time()
        with self._lock:
            q = self._data.get(key)
            if not q:
                return 0
            self._prune(q, now)
            return len(q)

    def over(self, key: str) -> bool:
        return self.count(key) >= self.limit

    def reset(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)

    def cleanup(self, max_keys: int = 5000) -> None:
        """防止 key 无限增长。"""
        with self._lock:
            if len(self._data) <= max_keys:
                return
            now = time.time()
            dead = [k for k, q in self._data.items() if not q or q[-1] < now - self.window_s * 10]
            for k in dead:
                self._data.pop(k, None)
