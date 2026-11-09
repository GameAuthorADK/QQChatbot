"""人设稳定插件的私有状态：自检报告。"""

from __future__ import annotations

import json
import re
import threading
import time

from .store import Store

PLUGIN_ID = "persona"
_REPORT_KEY = "reports"
_ISSUE_KEY = "issues"
_MAX_REPORTS = 10
_MAX_ISSUES = 10


class PersonaMemory:
    def __init__(self, store: Store):
        self.store = store
        self._lock = threading.RLock()

    def _load(self, key: str) -> list:
        raw = self.store.plugin_get(PLUGIN_ID, "global", key)
        try:
            data = json.loads(raw) if raw else []
        except Exception:
            data = []
        return data if isinstance(data, list) else []

    def _save(self, key: str, data: list) -> None:
        self.store.plugin_set(
            PLUGIN_ID,
            "global",
            key,
            json.dumps(data, ensure_ascii=False),
        )

    def record(
        self,
        group: str,
        member: str,
        mode: str,
        status: str,
        note: str = "",
    ) -> None:
        with self._lock:
            items = self._load(_REPORT_KEY)
            items = [
                item
                for item in items
                if not (
                    isinstance(item, dict)
                    and item.get("group") == group
                    and item.get("member") == member
                    and item.get("mode") == mode
                )
            ]
            items.append(
                {
                    "ts": time.time(),
                    "group": group,
                    "member": member,
                    "mode": mode,
                    "status": "drift" if status == "drift" else "ok",
                    "note": (note or "")[:200],
                }
            )
            self._save(_REPORT_KEY, items[-_MAX_REPORTS:])

            note = (note or "").strip()
            if status != "drift" or not note:
                return
            key = re.sub(r"\s+", "", note)[:60]
            issues = self._load(_ISSUE_KEY)
            found = None
            for item in issues:
                if not isinstance(item, dict):
                    continue
                if item.get("key") == key:
                    found = item
                    break
            if found is None:
                found = {
                    "key": key,
                    "text": note[:200],
                    "weight": 1,
                    "count": 1,
                    "last_at": time.time(),
                }
                issues.append(found)
            else:
                found["weight"] = min(20, int(found.get("weight") or 0) + 1)
                found["count"] = int(found.get("count") or 0) + 1
                found["last_at"] = time.time()
                found["text"] = note[:200]
            issues = sorted(
                [i for i in issues if isinstance(i, dict)],
                key=lambda i: (
                    -int(i.get("weight") or 0),
                    -float(i.get("last_at") or 0),
                ),
            )[:_MAX_ISSUES]
            self._save(_ISSUE_KEY, issues)

    def reports(self, limit: int = 20) -> list[dict]:
        with self._lock:
            items = self._load(_REPORT_KEY)
            return list(reversed(items[-max(1, min(30, int(limit))):]))

    def top_issues(self, limit: int = 5) -> list[dict]:
        with self._lock:
            issues = [
                i for i in self._load(_ISSUE_KEY) if isinstance(i, dict)
            ]
            issues.sort(
                key=lambda i: (
                    -int(i.get("weight") or 0),
                    -float(i.get("last_at") or 0),
                )
            )
            return issues[: max(1, min(20, int(limit)))]

    def restore(self, reports: list, issues: list) -> None:
        with self._lock:
            clean_reports = [
                {
                    "ts": float(r.get("ts") or time.time()),
                    "group": str(r.get("group") or ""),
                    "member": str(r.get("member") or ""),
                    "mode": str(r.get("mode") or "chat"),
                    "status": "drift" if r.get("status") == "drift" else "ok",
                    "note": str(r.get("note") or "")[:200],
                }
                for r in reports
                if isinstance(r, dict)
            ][-_MAX_REPORTS:]
            clean_issues = []
            for item in issues:
                if not isinstance(item, dict):
                    continue
                text = str(item.get("text") or "").strip()
                if not text:
                    continue
                clean_issues.append(
                    {
                        "key": str(item.get("key") or text)[:60],
                        "text": text[:200],
                        "weight": max(
                            1, min(20, int(item.get("weight") or 1))
                        ),
                        "count": max(0, int(item.get("count") or 0)),
                        "last_at": float(item.get("last_at") or time.time()),
                    }
                )
            clean_issues.sort(
                key=lambda i: (
                    -int(i.get("weight") or 0),
                    -float(i.get("last_at") or 0),
                )
            )
            self._save(_REPORT_KEY, clean_reports)
            self._save(_ISSUE_KEY, clean_issues[:_MAX_ISSUES])
