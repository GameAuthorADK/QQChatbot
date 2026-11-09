"""复读 / 接梗插件自己的私有记忆。

核心 Store 只提供通用的 plugin_kv 读写；这里负责：
- 冷却和每日次数
- 复读 / 接梗的类型与频率
- 用户常用梗、群内常复读内容
"""

from __future__ import annotations

import json
import re
import threading
import time

from .store import Store

PLUGIN_ID = "repeat"


class RepeatMemory:
    def __init__(self, store: Store):
        self.store = store
        self._lock = threading.RLock()

    # ── 私有 JSON 读写 ──────────────────────────────────
    def _get(self, group: str, key: str) -> dict:
        raw = self.store.plugin_get(PLUGIN_ID, group, key)
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _set(self, group: str, key: str, data: dict) -> None:
        self.store.plugin_set(
            PLUGIN_ID, group, key, json.dumps(data, ensure_ascii=False)
        )

    # ── 冷却 / 每日次数 ─────────────────────────────────
    def state(self, group: str) -> tuple[str, int, float]:
        with self._lock:
            data = self._get(group, "state")
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
            self._set(
                group,
                "state",
                {"date": date, "count": count + 1, "last_at": time.time()},
            )

    # ── 类型 / 频率 ─────────────────────────────────────
    def bump_type(self, group: str, date: str, kind: str) -> None:
        kind = "banter" if kind == "banter" else "repeat"
        key = f"stats:{date}"
        with self._lock:
            data = self._get(group, key)
            entry = data.get(kind) if isinstance(data.get(kind), dict) else {}
            data[kind] = {
                "count": int(entry.get("count") or 0) + 1,
                "last_at": time.time(),
            }
            self._set(group, key, data)

    def stats(self, group: str, date: str | None = None) -> dict:
        date = date or time.strftime("%Y-%m-%d")
        with self._lock:
            data = self._get(group, f"stats:{date}")
            return {
                kind: {
                    "count": int(entry.get("count") or 0),
                    "last_at": float(entry.get("last_at") or 0.0),
                }
                for kind, entry in data.items()
                if isinstance(entry, dict)
            }

    # ── 用户常用梗 / 群内常复读 ─────────────────────────
    def bump_meme(
        self, group: str, member: str, kind: str, text: str
    ) -> None:
        kind = "banter" if kind == "banter" else "repeat"
        text = re.sub(r"\s+", " ", (text or "")).strip()[:80]
        if not text:
            return
        key = f"meme:{kind}:{member}"
        with self._lock:
            data = self._get(group, key)
            entry = data.get(text) if isinstance(data.get(text), dict) else {}
            data[text] = {
                "count": int(entry.get("count") or 0) + 1,
                "last_at": time.time(),
            }
            self._set(group, key, data)

    def top_memes(
        self,
        group: str,
        *,
        kind: str | None = None,
        member_openid: str | None = None,
        limit: int = 10,
    ) -> list[dict]:
        with self._lock:
            result: dict[str, dict] = {}
            for key, raw in self.store.plugin_items(PLUGIN_ID, group).items():
                if not key.startswith("meme:"):
                    continue
                parts = key.split(":", 2)
                if len(parts) != 3:
                    continue
                _, item_kind, item_member = parts
                if kind and item_kind != kind:
                    continue
                if member_openid and item_member != member_openid:
                    continue
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(data, dict):
                    continue
                for text, entry in data.items():
                    if not isinstance(entry, dict):
                        continue
                    agg = result.setdefault(
                        text, {"text": text, "count": 0, "last_at": 0.0}
                    )
                    agg["count"] += int(entry.get("count") or 0)
                    agg["last_at"] = max(
                        agg["last_at"], float(entry.get("last_at") or 0.0)
                    )
            items = sorted(
                result.values(),
                key=lambda item: (-item["count"], -item["last_at"]),
            )
            return items[: max(1, min(50, int(limit)))]
