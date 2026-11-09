"""主动发起话题插件的私有状态。

核心只提供 plugin_kv；这里记录每个群的冷却、每日次数。
"""

from __future__ import annotations

import json
import threading
import time

from .store import Store

PLUGIN_ID = "proactive"


class ProactiveMemory:
    def __init__(self, store: Store):
        self.store = store
        self._lock = threading.RLock()

    def state(self, group: str) -> tuple[str, int, float]:
        with self._lock:
            raw = self.store.plugin_get(PLUGIN_ID, group, "state")
            if not raw:
                return ("", 0, 0.0)
            try:
                data = json.loads(raw)
            except Exception:
                return ("", 0, 0.0)
            if not isinstance(data, dict):
                return ("", 0, 0.0)
            return (
                str(data.get("date") or ""),
                int(data.get("count") or 0),
                float(data.get("last_at") or 0.0),
            )

    def bump(self, group: str, date: str) -> None:
        with self._lock:
            saved, count, _ = self.state(group)
            if saved != date:
                count = 0
            self.store.plugin_set(
                PLUGIN_ID,
                group,
                "state",
                json.dumps(
                    {
                        "date": date,
                        "count": count + 1,
                        "last_at": time.time(),
                    },
                    ensure_ascii=False,
                ),
            )
