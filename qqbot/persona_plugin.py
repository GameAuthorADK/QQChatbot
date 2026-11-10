"""人设稳定插件的私有状态：按群保存的自检报告历史。"""

from __future__ import annotations

import json
import re
import threading
import time
from uuid import uuid4

from .store import Store

PLUGIN_ID = "persona"
_REPORT_KEY = "reports"
DEFAULT_REPORT_LIMIT = 10
MAX_TOTAL_REPORTS = 200
MAX_NOTE_CHARS = 500
MAX_PROBLEM_LINES = 10


def _norm_weight(value, default: float = 0.0) -> float:
    """把自检权重收拢到 0.0-1.0，并兼容旧版 0-20 的整数权重。"""
    try:
        weight = float(value)
    except (TypeError, ValueError):
        weight = float(default)
    if weight > 1.0:
        weight = weight / 20.0
    return round(max(0.0, min(1.0, weight)), 1)


_WEIGHT_SUFFIX_RE = re.compile(
    r"^(.*?)[（(]\s*([0-9]+(?:\.[0-9]+)?)\s*[）)]\s*$"
)


def parse_report_lines(text) -> list[tuple[str, float, bool]]:
    """解析「- 内容（0.7）」；括号缺失或数值不合法时只保留内容。"""
    result: list[tuple[str, float, bool]] = []
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        line = re.sub(r"^[-*•]\s*", "", line).strip()
        if not line:
            continue
        match = _WEIGHT_SUFFIX_RE.match(line)
        if match:
            content = match.group(1).strip()
            try:
                weight = float(match.group(2))
            except (TypeError, ValueError):
                weight = -1.0
            if content and 0.0 <= weight <= 1.0:
                result.append((content, round(weight, 1), True))
                continue
        result.append((line, 0.0, False))
    return result


class PersonaMemory:
    def __init__(
        self, store: Store, report_limit: int = DEFAULT_REPORT_LIMIT
    ):
        self.store = store
        self._lock = threading.RLock()
        self.report_limit = self._clean_limit(report_limit)

    @staticmethod
    def _clean_limit(limit) -> int:
        try:
            value = int(limit)
        except (TypeError, ValueError):
            value = DEFAULT_REPORT_LIMIT
        return max(1, min(100, value))

    @staticmethod
    def _clean_mode(mode) -> str:
        return str(mode or "chat")[:24] or "chat"

    @staticmethod
    def _trim_groups(items: list, limit: int) -> list:
        """每群最多保留 limit 条有权重报告；0.0 不占名额，最新一条始终保留。"""
        grouped: dict[str, list[dict]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            grouped.setdefault(str(item.get("group") or ""), []).append(item)
        kept: list[dict] = []
        for rows in grouped.values():
            rows.sort(key=lambda item: float(item.get("ts") or 0))
            latest = rows[-1] if rows else None
            weighted = [
                item
                for item in rows
                if _norm_weight(item.get("weight"), 0.0) > 0.0
            ]
            weighted.sort(
                key=lambda item: (
                    -_norm_weight(item.get("weight"), 0.0),
                    -float(item.get("ts") or 0),
                )
            )
            chosen = weighted[:limit]
            if latest is not None:
                latest_weight = _norm_weight(latest.get("weight"), 0.0)
                if latest_weight > 0.0:
                    if latest not in chosen:
                        chosen = weighted[: max(0, limit - 1)] + [latest]
                elif latest not in chosen:
                    chosen.append(latest)
            kept.extend(chosen)
        kept.sort(key=lambda item: float(item.get("ts") or 0))
        return kept

    @staticmethod
    def _trim_problem_lines(
        items: list, limit: int = MAX_PROBLEM_LINES
    ) -> list:
        """每群最多保留 limit 条带权重的问题内容；最新零权重报告保留。"""
        grouped: dict[str, list[dict]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            grouped.setdefault(str(item.get("group") or ""), []).append(item)
        result: list[dict] = []
        for rows in grouped.values():
            rows.sort(key=lambda item: float(item.get("ts") or 0))
            latest = rows[-1] if rows else None
            parsed_by_id: dict[int, tuple[list, list]] = {}
            candidates: list[tuple] = []
            for order, item in enumerate(rows):
                parsed = parse_report_lines(item.get("note"))
                has_suffix = any(has for _, _, has in parsed)
                positives = [
                    (content, weight)
                    for content, weight, has in parsed
                    if has and weight > 0.0
                ]
                if not has_suffix:
                    legacy_weight = _norm_weight(item.get("weight"), 0.0)
                    legacy_note = re.sub(
                        r"^[-*•]\s*", "", str(item.get("note") or "")
                    ).strip()
                    if legacy_weight > 0.0 and legacy_note:
                        positives = [(legacy_note, legacy_weight)]
                parsed_by_id[id(item)] = (parsed, positives, has_suffix)
                ts = float(item.get("ts") or 0)
                for line_idx, (content, weight) in enumerate(positives):
                    candidates.append(
                        (weight, ts, order, line_idx, content, item)
                    )
            candidates.sort(
                key=lambda row: (-row[0], -row[1], row[2], row[3])
            )
            selected = candidates[:limit]
            keep: dict[int, list[tuple]] = {}
            for weight, _ts, _order, line_idx, content, item in selected:
                keep.setdefault(id(item), []).append(
                    (line_idx, content, weight)
                )
            for item in rows:
                lines = keep.get(id(item))
                if lines:
                    lines.sort(key=lambda row: row[0])
                    parsed, _positives, has_suffix = parsed_by_id[id(item)]
                    note_lines = [
                        f"- {content}（{weight:.1f}）"
                        for _idx, content, weight in lines
                    ]
                    if has_suffix:
                        for content, weight, has in parsed:
                            if has and weight <= 0.0:
                                note_lines.append(f"- {content}（0.0）")
                            elif not has:
                                note_lines.append(f"- {content}")
                    item["note"] = "\n".join(note_lines)
                    item["weight"] = max(row[2] for row in lines)
                    item["status"] = "drift"
                    result.append(item)
                elif item is latest:
                    parsed, positives, has_suffix = parsed_by_id[id(item)]
                    if positives:
                        note_lines = []
                        if has_suffix:
                            for content, weight, has in parsed:
                                if has and weight <= 0.0:
                                    note_lines.append(f"- {content}（0.0）")
                                elif not has:
                                    note_lines.append(f"- {content}")
                        item["note"] = "\n".join(note_lines)
                        item["weight"] = 0.0
                        item["status"] = "ok"
                    result.append(item)
        result.sort(key=lambda item: float(item.get("ts") or 0))
        return result

    @staticmethod
    def _trim_total(items: list) -> list:
        """所有群合计最多保留 200 条；超出时先删低权重、再删较旧的。"""
        if len(items) <= MAX_TOTAL_REPORTS:
            return items
        ordered = sorted(
            items,
            key=lambda item: (
                -_norm_weight(item.get("weight"), 0.0),
                -float(item.get("ts") or 0),
            ),
        )[:MAX_TOTAL_REPORTS]
        ordered.sort(key=lambda item: float(item.get("ts") or 0))
        return ordered

    def _apply_limits(self, items: list) -> list:
        return self._trim_total(
            self._trim_problem_lines(
                self._trim_groups(items, self.report_limit)
            )
        )

    def rebalance(self) -> None:
        """按新规则重新评估已有报告：每群限量、总量 200，低权重先删。"""
        with self._lock:
            items = self._load_reports()
            kept = self._apply_limits(items)
            if kept != items:
                self._save(_REPORT_KEY, kept)

    def set_report_limit(self, limit) -> None:
        self.report_limit = self._clean_limit(limit)
        self.rebalance()

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

    def _load_reports(self) -> list:
        """补上旧报告缺少的 id；只保留聊天模式。"""
        items = [
            item for item in self._load(_REPORT_KEY) if isinstance(item, dict)
        ]
        changed = False
        kept: list[dict] = []
        for item in items:
            if self._clean_mode(item.get("mode")) != "chat":
                changed = True
                continue
            if not item.get("id"):
                item["id"] = uuid4().hex
                changed = True
            if item.get("member"):
                item["member"] = ""
                changed = True
            item["mode"] = "chat"
            kept.append(item)
        if changed:
            self._save(_REPORT_KEY, kept)
        return kept

    def record(
        self,
        group: str,
        mode: str,
        status: str,
        note: str = "",
        source: str = "auto",
        weight: float | None = None,
    ) -> dict:
        """追加一条按群的自检报告；同一群可以保留多条历史。"""
        status = status if status in ("drift", "error") else "ok"
        note = (note or "").strip()[:MAX_NOTE_CHARS]
        parsed = parse_report_lines(note)
        has_suffix = any(has for _, _, has in parsed)
        if has_suffix:
            valid = [
                (content, weight)
                for content, weight, has in parsed
                if has and weight > 0.0
            ]
            if valid:
                weight = max(item[1] for item in valid)
                note = "\n".join(
                    f"- {content}（{weight:.1f}）"
                    for content, weight, has in parsed
                    if has and weight > 0.0
                )
                status = "drift"
            else:
                weight = 0.0
                note = ""
                if status != "error":
                    status = "ok"
        else:
            if weight is None:
                weight = 0.5 if status == "drift" else 0.0
            weight = _norm_weight(weight, 0.5 if status == "drift" else 0.0)
            if weight <= 0.0 and status != "error":
                status = "ok"
                note = ""
        if not note:
            weight = 0.0
        report = {
            "id": uuid4().hex,
            "ts": time.time(),
            "group": group,
            "member": "",
            "mode": "chat",
            "status": status,
            "note": note,
            "weight": weight,
            "source": (source or "auto")[:10],
        }
        with self._lock:
            items = self._load_reports()
            items.append(report)
            items = self._apply_limits(items)
            self._save(_REPORT_KEY, items)
        return dict(report)

    def update_report(
        self,
        report_id: str,
        note: str,
    ) -> dict | None:
        """手动编辑报告文字；权重只从行末括号读取。"""
        note = (note or "").strip()[:MAX_NOTE_CHARS]
        parsed = parse_report_lines(note)
        valid = [
            (content, weight)
            for content, weight, has in parsed
            if has and weight > 0.0
        ]
        weight = max((item[1] for item in valid), default=0.0)
        status = "drift" if weight > 0.0 else "ok"
        if not note:
            weight = 0.0
        with self._lock:
            items = self._load_reports()
            target = None
            for item in items:
                if item.get("id") == report_id:
                    target = item
                    break
            if target is None:
                return None
            target["member"] = ""
            target["note"] = note
            target["weight"] = weight
            target["status"] = status
            target["ts"] = time.time()
            target["edited_at"] = target["ts"]
            try:
                items.remove(target)
            except ValueError:
                pass
            items.append(target)
            items = self._apply_limits(items)
            self._save(_REPORT_KEY, items)
            return dict(target)

    def delete_report(self, report_id: str) -> bool:
        with self._lock:
            items = self._load_reports()
            kept = [item for item in items if item.get("id") != report_id]
            if len(kept) == len(items):
                return False
            self._save(_REPORT_KEY, kept)
            return True

    def reports(self, limit: int = MAX_TOTAL_REPORTS) -> list[dict]:
        with self._lock:
            items = self._load_reports()
            take = max(1, int(limit))
            return list(reversed(items[-take:]))

    def count_reports(self) -> int:
        with self._lock:
            return len(self._load_reports())

    def reports_page(
        self, page: int = 1, size: int = 10
    ) -> tuple[list[dict], int]:
        size = max(1, min(50, int(size)))
        page = max(1, int(page))
        with self._lock:
            ordered = list(reversed(self._load_reports()))
        total = len(ordered)
        pages = max(1, (total + size - 1) // size)
        page = min(page, pages)
        start = (page - 1) * size
        return ordered[start:start + size], total

    def clear_group(self, group: str) -> int:
        with self._lock:
            items = self._load_reports()
            kept = [
                item for item in items if item.get("group") != group
            ]
            removed = len(items) - len(kept)
            if removed:
                self._save(_REPORT_KEY, kept)
            return removed

    def active_reports(
        self, group: str, mode: str = "", limit: int = 20
    ) -> list[dict]:
        """该群所有行末带合法权重的报告内容都会影响回复。"""
        with self._lock:
            items = self._load_reports()
        chosen: dict[str, dict] = {}

        def add(content: str, weight: float, item: dict) -> None:
            content = str(content or "").strip()
            weight = _norm_weight(weight, 0.0)
            if not content or weight <= 0.0:
                return
            key = "".join(content.split())
            current = chosen.get(key)
            ts = float(item.get("ts") or 0)
            if current is None or (weight, ts) >= (
                _norm_weight(current.get("weight"), 0.0),
                float(current.get("ts") or 0),
            ):
                chosen[key] = {
                    "id": item.get("id"),
                    "group": item.get("group"),
                    "note": content,
                    "weight": weight,
                    "ts": ts,
                }

        for item in items:
            if item.get("group") != group:
                continue
            note = str(item.get("note") or "").strip()
            parsed = parse_report_lines(note)
            valid = [
                (content, weight)
                for content, weight, has in parsed
                if has and weight > 0.0
            ]
            if valid:
                for content, weight in valid:
                    add(content, weight, item)
                continue
            has_suffix = any(has for _, _, has in parsed)
            legacy_weight = _norm_weight(item.get("weight"), 0.0)
            if not has_suffix and legacy_weight > 0.0 and note:
                content = re.sub(r"^[-*•]\s*", "", note).strip()
                add(content, legacy_weight, item)

        active = list(chosen.values())
        active.sort(
            key=lambda item: (
                -_norm_weight(item.get("weight"), 0.0),
                -float(item.get("ts") or 0),
            )
        )
        return active[: max(1, min(MAX_PROBLEM_LINES, int(limit)))]

    def restore(self, reports: list, replace: bool = True) -> int:
        """导入聊天模式报告；可以选择覆盖或合并，返回实际新增条数。"""
        existing = [] if replace else self._load_reports()
        items: list[dict] = list(existing)
        seen_ids = {str(item.get("id") or "") for item in existing}
        seen_rows = {
            (
                str(item.get("group") or ""),
                "chat",
                round(float(item.get("ts") or 0), 3),
                str(item.get("note") or ""),
            )
            for item in existing
        }
        added = 0
        for r in reports:
            if not isinstance(r, dict):
                continue
            group = str(r.get("group") or "")
            if not group:
                continue
            if self._clean_mode(r.get("mode")) != "chat":
                continue
            report_id = str(r.get("id") or uuid4().hex)
            if report_id in seen_ids:
                continue
            ts = float(r.get("ts") or time.time())
            note = str(r.get("note") or "")[:MAX_NOTE_CHARS]
            signature = (group, "chat", round(ts, 3), note)
            if signature in seen_rows:
                continue
            seen_ids.add(report_id)
            seen_rows.add(signature)
            status = (
                r.get("status")
                if r.get("status") in ("drift", "error")
                else "ok"
            )
            parsed = parse_report_lines(note)
            valid = [
                (content, weight)
                for content, weight, has in parsed
                if has and weight > 0.0
            ]
            has_suffix = any(has for _, _, has in parsed)
            if valid:
                weight = max(item[1] for item in valid)
                status = "drift"
            elif has_suffix:
                weight = 0.0
                if status != "error":
                    status = "ok"
            else:
                weight = _norm_weight(r.get("weight"), 0.0)
                if weight <= 0.0 and status != "error":
                    status = "ok"
            if not note:
                weight = 0.0
            items.append(
                {
                    "id": report_id,
                    "ts": ts,
                    "group": group,
                    "member": "",
                    "mode": "chat",
                    "status": status,
                    "note": note,
                    "weight": weight,
                    "source": str(r.get("source") or "auto")[:10],
                }
            )
            added += 1
        items.sort(key=lambda item: float(item.get("ts") or 0))
        items = self._apply_limits(items)
        self._save(_REPORT_KEY, items)
        return added
