"""SQLite 存储：幂等、回复守卫、群状态、审计。

P1 只落地最小集合；后续按需加表。
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from . import errors
from .paths import DB_PATH

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS meta (
    k TEXT PRIMARY KEY,
    v TEXT NOT NULL
);

-- 入站幂等：同一条消息只处理一次
CREATE TABLE IF NOT EXISTS seen (
    msg_id TEXT NOT NULL,
    kind   TEXT NOT NULL,
    ts     REAL NOT NULL,
    PRIMARY KEY (msg_id, kind)
);

-- 出站守卫：每个 msg_id 的下一个可用 msg_seq
CREATE TABLE IF NOT EXISTS sent (
    msg_id   TEXT PRIMARY KEY,
    last_seq INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS groups (
    group_openid TEXT PRIMARY KEY,
    status       TEXT NOT NULL DEFAULT 'pending',
    added_by     TEXT,
    added_at     REAL,
    mode         TEXT NOT NULL DEFAULT 'chat',
    house_rule   TEXT NOT NULL DEFAULT 'default',
    rulepack     TEXT NOT NULL DEFAULT '',
    minigame_id  TEXT NOT NULL DEFAULT '',
    listen_enabled INTEGER NOT NULL DEFAULT 0,
    member_count INTEGER NOT NULL DEFAULT 0,
    note         TEXT
);

CREATE TABLE IF NOT EXISTS audit (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    ts     REAL NOT NULL,
    actor  TEXT,
    action TEXT NOT NULL,
    target TEXT,
    detail TEXT
);

-- 会话上下文：按 (群, 人, 模式) 隔离
CREATE TABLE IF NOT EXISTS threads (
    group_openid  TEXT NOT NULL,
    member_openid TEXT NOT NULL,
    mode          TEXT NOT NULL DEFAULT 'chat',
    messages      TEXT NOT NULL DEFAULT '[]',
    summary       TEXT NOT NULL DEFAULT '',
    pending       TEXT NOT NULL DEFAULT '[]',
    updated_at    REAL NOT NULL,
    PRIMARY KEY (group_openid, member_openid, mode)
);

-- 每个群的回复设置覆盖；空表示沿用全局默认
CREATE TABLE IF NOT EXISTS group_reply (
    group_openid TEXT PRIMARY KEY,
    data         TEXT NOT NULL DEFAULT '{}',
    updated_at   REAL NOT NULL
);

-- 滥用状态（仅持久化静默，警告态在内存）
CREATE TABLE IF NOT EXISTS abuse_state (
    group_openid  TEXT NOT NULL,
    member_openid TEXT NOT NULL,
    level         TEXT NOT NULL DEFAULT 'muted',
    muted_at      REAL,
    muted_by      TEXT,
    reason        TEXT,
    PRIMARY KEY (group_openid, member_openid)
);

-- 每日额度
CREATE TABLE IF NOT EXISTS quota_daily (
    scope     TEXT NOT NULL,
    scope_key TEXT NOT NULL,
    date      TEXT NOT NULL,
    msgs      INTEGER NOT NULL DEFAULT 0,
    tokens    INTEGER NOT NULL DEFAULT 0,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    cached_tokens     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (scope, scope_key, date)
);

-- 角色卡：每人每规则一张
CREATE TABLE IF NOT EXISTS characters (
    member_openid TEXT NOT NULL,
    pack_id       TEXT NOT NULL,
    slot          TEXT NOT NULL DEFAULT 'default',
    data          TEXT NOT NULL DEFAULT '{}',
    updated_at    REAL NOT NULL,
    PRIMARY KEY (member_openid, pack_id, slot)
);

-- 模式切换通知（界面切换时可能没有可用的被动回复上下文）
CREATE TABLE IF NOT EXISTS mode_notices (
    group_openid TEXT PRIMARY KEY,
    text         TEXT NOT NULL,
    created_at   REAL NOT NULL
);

-- 代码插件的启用状态与私有数据
CREATE TABLE IF NOT EXISTS code_plugins (
    id         TEXT PRIMARY KEY,
    enabled    INTEGER NOT NULL DEFAULT 0,
    file_hash  TEXT NOT NULL DEFAULT '',
    store      TEXT NOT NULL DEFAULT '{}',
    updated_at REAL NOT NULL
);

-- 规则 hook 的每群状态
CREATE TABLE IF NOT EXISTS rule_store (
    pack_id      TEXT NOT NULL,
    group_openid TEXT NOT NULL,
    data         TEXT NOT NULL DEFAULT '{}',
    updated_at   REAL NOT NULL,
    PRIMARY KEY (pack_id, group_openid)
);

-- 规则 hook 的启用状态（默认关闭）
CREATE TABLE IF NOT EXISTS rule_plugins (
    id           TEXT PRIMARY KEY,
    hooks_enabled INTEGER NOT NULL DEFAULT 0,
    file_hash    TEXT NOT NULL DEFAULT '',
    updated_at   REAL NOT NULL
);

-- 规则插件的启用状态（默认启用）
CREATE TABLE IF NOT EXISTS rulepacks (
    id         TEXT PRIMARY KEY,
    enabled    INTEGER NOT NULL DEFAULT 1,
    updated_at REAL NOT NULL
);

-- 小游戏插件：启用状态与每群状态
CREATE TABLE IF NOT EXISTS minigames (
    id         TEXT PRIMARY KEY,
    enabled    INTEGER NOT NULL DEFAULT 0,
    file_hash  TEXT NOT NULL DEFAULT '',
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS game_store (
    game_id      TEXT NOT NULL,
    group_openid TEXT NOT NULL,
    data         TEXT NOT NULL DEFAULT '{}',
    updated_at   REAL NOT NULL,
    PRIMARY KEY (game_id, group_openid)
);

CREATE TABLE IF NOT EXISTS solo_store (
    game_id       TEXT NOT NULL,
    group_openid  TEXT NOT NULL,
    member_openid TEXT NOT NULL,
    data          TEXT NOT NULL DEFAULT '{}',
    updated_at    REAL NOT NULL,
    PRIMARY KEY (game_id, group_openid, member_openid)
);

-- 群聊监听：主动回复的冷却和每日次数
CREATE TABLE IF NOT EXISTS proactive_state (
    group_openid TEXT PRIMARY KEY,
    date         TEXT NOT NULL DEFAULT '',
    count        INTEGER NOT NULL DEFAULT 0,
    last_at      REAL NOT NULL DEFAULT 0
);

-- 插件私有状态：插件自己决定 scope / key / value 的格式
CREATE TABLE IF NOT EXISTS plugin_kv (
    plugin_id  TEXT NOT NULL,
    scope      TEXT NOT NULL,
    k          TEXT NOT NULL,
    v          TEXT NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY (plugin_id, scope, k)
);

-- 外部 wiki 摘要缓存
CREATE TABLE IF NOT EXISTS wiki_cache (
    key        TEXT PRIMARY KEY,
    url        TEXT NOT NULL DEFAULT '',
    content    TEXT NOT NULL DEFAULT '',
    fetched_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
"""


class Store:
    def __init__(self, path: Path = DB_PATH):
        self.path = path
        self._lock = threading.RLock()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(path, check_same_thread=False, timeout=5)
        except sqlite3.Error as exc:
            raise errors.BotError(errors.DB_OPEN_FAILED, f"无法打开数据库: {exc}") from exc

        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()
            self._migrate()

    def _migrate(self) -> None:
        """老库补列 / 重建主键，失败不影响启动。"""
        try:
            cols = {r[1] for r in self.conn.execute("PRAGMA table_info(threads)")}
            if cols:
                if "summary" not in cols:
                    self.conn.execute(
                        "ALTER TABLE threads ADD COLUMN summary TEXT NOT NULL DEFAULT ''"
                    )
                if "pending" not in cols:
                    self.conn.execute(
                        "ALTER TABLE threads ADD COLUMN pending TEXT NOT NULL DEFAULT '[]'"
                    )

                if "mode" not in cols:
                    # 旧表主键是 (群, 人)，SQLite 不能直接改主键，只能重建。
                    # 已有数据全部归到 chat 模式，升级后聊天记录不会丢。
                    self.conn.execute("ALTER TABLE threads RENAME TO threads_old")
                    self.conn.execute(
                        """
                        CREATE TABLE threads (
                            group_openid  TEXT NOT NULL,
                            member_openid TEXT NOT NULL,
                            mode          TEXT NOT NULL DEFAULT 'chat',
                            messages      TEXT NOT NULL DEFAULT '[]',
                            summary       TEXT NOT NULL DEFAULT '',
                            pending       TEXT NOT NULL DEFAULT '[]',
                            updated_at    REAL NOT NULL,
                            PRIMARY KEY (group_openid, member_openid, mode)
                        )
                        """
                    )
                    self.conn.execute(
                        """
                        INSERT INTO threads(
                            group_openid, member_openid, mode,
                            messages, summary, pending, updated_at
                        )
                        SELECT group_openid, member_openid, 'chat',
                               messages, summary, pending, updated_at
                        FROM threads_old
                        """
                    )
                    self.conn.execute("DROP TABLE threads_old")
                self.conn.commit()
        except sqlite3.Error:
            try:
                self.conn.rollback()
            except sqlite3.Error:
                pass

        try:
            gcols = {
                r[1] for r in self.conn.execute("PRAGMA table_info(groups)")
            }
            if gcols and "mode" not in gcols:
                # 极早期库可能没有模式列；不补会让群列表查询直接报错。
                self.conn.execute(
                    "ALTER TABLE groups ADD COLUMN mode TEXT NOT NULL DEFAULT 'chat'"
                )
                self.conn.commit()
            if gcols and "house_rule" not in gcols:
                self.conn.execute(
                    "ALTER TABLE groups ADD COLUMN house_rule TEXT NOT NULL DEFAULT 'default'"
                )
                self.conn.commit()
            if gcols and "rulepack" not in gcols:
                self.conn.execute(
                    "ALTER TABLE groups ADD COLUMN rulepack TEXT NOT NULL DEFAULT ''"
                )
                self.conn.commit()
            if gcols and "minigame_id" not in gcols:
                self.conn.execute(
                    "ALTER TABLE groups ADD COLUMN minigame_id TEXT NOT NULL DEFAULT ''"
                )
                self.conn.commit()
            if gcols and "listen_enabled" not in gcols:
                self.conn.execute(
                    "ALTER TABLE groups ADD COLUMN listen_enabled INTEGER NOT NULL DEFAULT 0"
                )
                self.conn.commit()
            if gcols and "member_count" not in gcols:
                self.conn.execute(
                    "ALTER TABLE groups ADD COLUMN member_count INTEGER NOT NULL DEFAULT 0"
                )
                self.conn.commit()
            if gcols:
                # 规则 id 改名：保留用户已经选好的群设置
                self.conn.execute(
                    "UPDATE groups SET rulepack='paranoia25th' "
                    "WHERE rulepack='paranoia25'"
                )
                self.conn.execute(
                    "UPDATE groups SET rulepack='coc7th' WHERE rulepack='coc7e'"
                )
                self.conn.commit()
        except sqlite3.Error:
            pass

        try:
            qcols = {
                r[1]
                for r in self.conn.execute("PRAGMA table_info(quota_daily)")
            }
            for name in ("prompt_tokens", "completion_tokens", "cached_tokens"):
                if qcols and name not in qcols:
                    self.conn.execute(
                        f"ALTER TABLE quota_daily ADD COLUMN {name} "
                        "INTEGER NOT NULL DEFAULT 0"
                    )
            if qcols:
                self.conn.commit()
        except sqlite3.Error:
            pass

    def get_memory_state(
        self, group_openid: str, member_openid: str, mode: str = "chat"
    ) -> tuple[str, list]:
        """返回 (已有摘要, 待总结的消息)。按 群 + 人 + 模式 隔离。"""
        with self._lock:
            row = self.conn.execute(
                "SELECT summary, pending FROM threads "
                "WHERE group_openid=? AND member_openid=? AND mode=?",
                (group_openid, member_openid, mode),
            ).fetchone()
        if not row:
            return "", []
        try:
            pending = json.loads(row[1] or "[]")
            if not isinstance(pending, list):
                pending = []
        except Exception:
            pending = []
        return (row[0] or "", pending)

    def save_memory_state(
        self,
        group_openid: str,
        member_openid: str,
        summary: str,
        pending: list,
        *,
        mode: str = "chat",
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO threads"
                "(group_openid,member_openid,mode,messages,summary,pending,updated_at) "
                "VALUES(?,?,?, '[]', ?, ?, ?) "
                "ON CONFLICT(group_openid,member_openid,mode) DO UPDATE SET "
                "summary=excluded.summary, pending=excluded.pending",
                (
                    group_openid,
                    member_openid,
                    mode,
                    (summary or "")[:1500],
                    json.dumps(pending[-200:], ensure_ascii=False),
                    time.time(),
                ),
            )
            self.conn.commit()

    def list_summaries(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT group_openid, member_openid, mode, summary, updated_at "
                "FROM threads WHERE summary != '' ORDER BY updated_at DESC LIMIT 200"
            ).fetchall()
        return [
            {
                "group": r[0],
                "member": r[1],
                "mode": r[2] or "chat",
                "summary": r[3],
                "updated_at": r[4],
            }
            for r in rows
        ]

    def pending_summary(self) -> dict:
        """待整理的记忆：去重人数、对话数和消息条数。"""
        with self._lock:
            rows = self.conn.execute(
                "SELECT member_openid, pending FROM threads "
                "WHERE pending NOT IN ('', '[]')"
            ).fetchall()
        people: set[str] = set()
        threads = 0
        messages = 0
        for member, raw in rows:
            try:
                items = json.loads(raw or "[]")
            except (TypeError, ValueError):
                continue
            if not isinstance(items, list) or not items:
                continue
            threads += 1
            messages += len(items)
            people.add(member)
        return {
            "people": len(people),
            "threads": threads,
            "messages": messages,
        }

    def pending_threads(self) -> list[dict]:
        """返回仍有待整理消息的对话，旧的排前面。"""
        with self._lock:
            rows = self.conn.execute(
                "SELECT group_openid, member_openid, mode, summary, pending "
                "FROM threads WHERE pending NOT IN ('', '[]') "
                "ORDER BY updated_at ASC"
            ).fetchall()
        out: list[dict] = []
        for group, member, mode, summary, raw in rows:
            try:
                items = json.loads(raw or "[]")
            except (TypeError, ValueError):
                continue
            if not isinstance(items, list) or not items:
                continue
            out.append(
                {
                    "group": group,
                    "member": member,
                    "mode": mode or "chat",
                    "summary": summary or "",
                    "pending": items,
                }
            )
        return out

    def member_summaries(
        self,
        member_openid: str,
        mode: str = "chat",
        *,
        exclude_group: str | None = None,
        limit: int = 3,
    ) -> list[dict]:
        """同一用户在其他群已生成的摘要。"""
        sql = (
            "SELECT group_openid, summary, updated_at FROM threads "
            "WHERE member_openid=? AND mode=? AND summary != ''"
        )
        args: list = [member_openid, mode]
        if exclude_group:
            sql += " AND group_openid != ?"
            args.append(exclude_group)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        args.append(max(1, min(10, int(limit))))
        with self._lock:
            rows = self.conn.execute(sql, args).fetchall()
        return [
            {"group": r[0], "summary": r[1], "updated_at": r[2]}
            for r in rows
        ]

    def get_summary(
        self, group_openid: str, member_openid: str, mode: str = "chat"
    ) -> str:
        return self.get_memory_state(group_openid, member_openid, mode)[0]

    def set_summary(
        self,
        group_openid: str,
        member_openid: str,
        summary: str,
        mode: str = "chat",
    ) -> None:
        _, pending = self.get_memory_state(group_openid, member_openid, mode)
        self.save_memory_state(group_openid, member_openid, summary, pending, mode=mode)

    def close(self) -> None:
        with self._lock:
            self.conn.close()

    # ── meta ──────────────────────────────────────────────
    def get_meta(self, key: str, default: str | None = None) -> str | None:
        with self._lock:
            row = self.conn.execute("SELECT v FROM meta WHERE k=?", (key,)).fetchone()
        return row[0] if row else default

    def set_meta(self, key: str, value: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO meta(k,v) VALUES(?,?) "
                "ON CONFLICT(k) DO UPDATE SET v=excluded.v",
                (key, value),
            )
            self.conn.commit()

    # ── 幂等 ──────────────────────────────────────────────
    def claim_message(self, msg_id: str, kind: str = "group") -> bool:
        """首次见到返回 True；重复返回 False。原子操作。"""
        with self._lock:
            try:
                self.conn.execute(
                    "INSERT INTO seen(msg_id, kind, ts) VALUES(?,?,?)",
                    (msg_id, kind, time.time()),
                )
                self.conn.commit()
                return True
            except sqlite3.IntegrityError:
                return False

    # ── 回复守卫 ──────────────────────────────────────────
    def next_msg_seq(self, msg_id: str) -> int:
        """返回并预占下一个 msg_seq，持久化，重启不重置。"""
        with self._lock:
            row = self.conn.execute(
                "SELECT last_seq FROM sent WHERE msg_id=?", (msg_id,)
            ).fetchone()
            nxt = (row[0] if row else 0) + 1
            self.conn.execute(
                "INSERT INTO sent(msg_id, last_seq) VALUES(?,?) "
                "ON CONFLICT(msg_id) DO UPDATE SET last_seq=excluded.last_seq",
                (msg_id, nxt),
            )
            self.conn.commit()
            return nxt

    def peek_msg_seq(self, msg_id: str) -> int:
        with self._lock:
            row = self.conn.execute(
                "SELECT last_seq FROM sent WHERE msg_id=?", (msg_id,)
            ).fetchone()
        return row[0] if row else 0

    # ── 群 ────────────────────────────────────────────────
    def upsert_group(self, group_openid: str, status: str, added_by: str | None) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO groups(group_openid,status,added_by,added_at) "
                "VALUES(?,?,?,?) "
                "ON CONFLICT(group_openid) DO UPDATE SET status=excluded.status",
                (group_openid, status, added_by, time.time()),
            )
            self.conn.commit()

    def group_status(self, group_openid: str) -> str | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT status FROM groups WHERE group_openid=?", (group_openid,)
            ).fetchone()
        return row[0] if row else None

    def set_group_status(self, group_openid: str, status: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO groups(group_openid,status,added_at) VALUES(?,?,?) "
                "ON CONFLICT(group_openid) DO UPDATE SET status=excluded.status",
                (group_openid, status, time.time()),
            )
            self.conn.commit()

    def group_mode(self, group_openid: str) -> str:
        with self._lock:
            row = self.conn.execute(
                "SELECT mode FROM groups WHERE group_openid=?", (group_openid,)
            ).fetchone()
        return row[0] if row and row[0] else "chat"

    def group_house_rule(self, group_openid: str) -> str:
        with self._lock:
            row = self.conn.execute(
                "SELECT house_rule FROM groups WHERE group_openid=?", (group_openid,)
            ).fetchone()
        return row[0] if row and row[0] else "default"

    def set_group_house_rule(self, group_openid: str, rule: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO groups(group_openid,status,added_at,house_rule) "
                "VALUES(?,'active',?,?) "
                "ON CONFLICT(group_openid) DO UPDATE SET house_rule=excluded.house_rule",
                (group_openid, time.time(), rule),
            )
            self.conn.commit()

    def group_rulepack(self, group_openid: str) -> str:
        with self._lock:
            row = self.conn.execute(
                "SELECT rulepack FROM groups WHERE group_openid=?", (group_openid,)
            ).fetchone()
        return row[0] if row and row[0] else ""

    def set_group_rulepack(self, group_openid: str, pack_id: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO groups(group_openid,status,added_at,rulepack) "
                "VALUES(?,'active',?,?) "
                "ON CONFLICT(group_openid) DO UPDATE SET rulepack=excluded.rulepack",
                (group_openid, time.time(), pack_id),
            )
            self.conn.commit()

    def group_listen(self, group_openid: str) -> bool:
        with self._lock:
            row = self.conn.execute(
                "SELECT listen_enabled FROM groups WHERE group_openid=?",
                (group_openid,),
            ).fetchone()
        return bool(row[0]) if row else False

    def set_group_listen(self, group_openid: str, enabled: bool) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE groups SET listen_enabled=? WHERE group_openid=?",
                (1 if enabled else 0, group_openid),
            )
            self.conn.commit()

    def group_member_count(self, group_openid: str) -> int:
        with self._lock:
            row = self.conn.execute(
                "SELECT member_count FROM groups WHERE group_openid=?",
                (group_openid,),
            ).fetchone()
        return int(row[0] or 0) if row else 0

    def set_group_member_count(self, group_openid: str, count: int) -> None:
        with self._lock:
            self.conn.execute(
                "UPDATE groups SET member_count=? WHERE group_openid=?",
                (max(0, min(100000, int(count))), group_openid),
            )
            self.conn.commit()

    def proactive_state(self, group_openid: str) -> tuple[str, int, float]:
        with self._lock:
            row = self.conn.execute(
                "SELECT date,count,last_at FROM proactive_state WHERE group_openid=?",
                (group_openid,),
            ).fetchone()
        return (row[0], int(row[1]), float(row[2])) if row else ("", 0, 0.0)

    def bump_proactive(self, group_openid: str, date: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO proactive_state(group_openid,date,count,last_at) "
                "VALUES(?,?,1,?) ON CONFLICT(group_openid) DO UPDATE SET "
                "count=CASE WHEN proactive_state.date=excluded.date "
                "THEN proactive_state.count+1 ELSE 1 END, "
                "date=excluded.date, last_at=excluded.last_at",
                (group_openid, date, time.time()),
            )
            self.conn.commit()

    def plugin_get(
        self,
        plugin_id: str,
        scope: str,
        key: str,
        default: str | None = None,
    ) -> str | None:
        """通用插件私有存储。"""
        with self._lock:
            row = self.conn.execute(
                "SELECT v FROM plugin_kv "
                "WHERE plugin_id=? AND scope=? AND k=?",
                (plugin_id, scope, key),
            ).fetchone()
        return row[0] if row else default

    def plugin_set(
        self, plugin_id: str, scope: str, key: str, value: str
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO plugin_kv(plugin_id,scope,k,v,updated_at) "
                "VALUES(?,?,?,?,?) "
                "ON CONFLICT(plugin_id,scope,k) DO UPDATE SET "
                "v=excluded.v, updated_at=excluded.updated_at",
                (plugin_id, scope, key, value, time.time()),
            )
            self.conn.commit()

    def plugin_items(self, plugin_id: str, scope: str) -> dict[str, str]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT k,v FROM plugin_kv WHERE plugin_id=? AND scope=?",
                (plugin_id, scope),
            ).fetchall()
        return {r[0]: r[1] for r in rows}

    def plugin_delete(self, plugin_id: str, scope: str, key: str) -> None:
        with self._lock:
            self.conn.execute(
                "DELETE FROM plugin_kv "
                "WHERE plugin_id=? AND scope=? AND k=?",
                (plugin_id, scope, key),
            )
            self.conn.commit()

    def set_group_mode(self, group_openid: str, mode: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO groups(group_openid,status,added_at,mode) VALUES(?,'active',?,?) "
                "ON CONFLICT(group_openid) DO UPDATE SET mode=excluded.mode",
                (group_openid, time.time(), mode),
            )
            self.conn.commit()

    def groups(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT group_openid,status,mode,house_rule,rulepack,minigame_id,"
                "added_at,added_by,listen_enabled,member_count FROM groups"
            ).fetchall()
        return [
            {
                "group": r[0],
                "status": r[1],
                "mode": r[2] or "chat",
                "house_rule": r[3] or "default",
                "rulepack": r[4] or "",
                "minigame_id": r[5] or "",
                "added_at": r[6],
                "added_by": r[7],
                "listen_enabled": bool(r[8]),
                "member_count": int(r[9] or 0),
            }
            for r in rows
        ]

    def get_group_reply(self, group_openid: str) -> dict:
        with self._lock:
            row = self.conn.execute(
                "SELECT data FROM group_reply WHERE group_openid=?",
                (group_openid,),
            ).fetchone()
        if not row:
            return {}
        try:
            data = json.loads(row[0])
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def set_group_reply(self, group_openid: str, data: dict) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO group_reply(group_openid,data,updated_at) "
                "VALUES(?,?,?) ON CONFLICT(group_openid) DO UPDATE SET "
                "data=excluded.data, updated_at=excluded.updated_at",
                (
                    group_openid,
                    json.dumps(data, ensure_ascii=False),
                    time.time(),
                ),
            )
            self.conn.commit()

    def clear_group_reply(self, group_openid: str) -> None:
        with self._lock:
            self.conn.execute(
                "DELETE FROM group_reply WHERE group_openid=?",
                (group_openid,),
            )
            self.conn.commit()

    # ── 会话上下文 ────────────────────────────────────────
    def get_thread(
        self, group_openid: str, member_openid: str, mode: str = "chat"
    ) -> list[dict]:
        with self._lock:
            row = self.conn.execute(
                "SELECT messages FROM threads "
                "WHERE group_openid=? AND member_openid=? AND mode=?",
                (group_openid, member_openid, mode),
            ).fetchone()
        if not row or not row[0]:
            return []
        try:
            data = json.loads(row[0])
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def append_thread(
        self,
        group_openid: str,
        member_openid: str,
        role: str,
        content: str,
        *,
        mode: str = "chat",
        limit: int = 12,
    ) -> None:
        msgs = self.get_thread(group_openid, member_openid, mode)
        msgs.append({"role": role, "content": content})
        msgs = msgs[-max(2, limit):]
        with self._lock:
            self.conn.execute(
                "INSERT INTO threads"
                "(group_openid,member_openid,mode,messages,updated_at) "
                "VALUES(?,?,?,?,?) "
                "ON CONFLICT(group_openid,member_openid,mode) DO UPDATE SET "
                "messages=excluded.messages, updated_at=excluded.updated_at",
                (
                    group_openid,
                    member_openid,
                    mode,
                    json.dumps(msgs, ensure_ascii=False),
                    time.time(),
                ),
            )
            self.conn.commit()

    def append_turn(
        self,
        group_openid: str,
        member_openid: str,
        user_text: str,
        assistant_text: str,
        *,
        mode: str = "chat",
        limit: int = 12,
    ) -> list[dict]:
        """一次性写入一轮问答，返回被挤出的旧消息。"""
        msgs = self.get_thread(group_openid, member_openid, mode)
        if user_text:
            msgs.append({"role": "user", "content": user_text})
        if assistant_text:
            msgs.append({"role": "assistant", "content": assistant_text})
        dropped = msgs[:-limit] if len(msgs) > limit else []
        msgs = msgs[-max(2, limit):]
        with self._lock:
            self.conn.execute(
                "INSERT INTO threads"
                "(group_openid,member_openid,mode,messages,updated_at) "
                "VALUES(?,?,?,?,?) "
                "ON CONFLICT(group_openid,member_openid,mode) DO UPDATE SET "
                "messages=excluded.messages, updated_at=excluded.updated_at",
                (
                    group_openid,
                    member_openid,
                    mode,
                    json.dumps(msgs, ensure_ascii=False),
                    time.time(),
                ),
            )
            self.conn.commit()
        return dropped

    def clear_thread(
        self, group_openid: str, member_openid: str, mode: str = "chat"
    ) -> None:
        with self._lock:
            self.conn.execute(
                "DELETE FROM threads "
                "WHERE group_openid=? AND member_openid=? AND mode=?",
                (group_openid, member_openid, mode),
            )
            self.conn.commit()

    # ── 滥用 ──────────────────────────────────────────────
    def is_muted(self, group_openid: str, member_openid: str) -> bool:
        with self._lock:
            row = self.conn.execute(
                "SELECT level FROM abuse_state WHERE group_openid=? AND member_openid=?",
                (group_openid, member_openid),
            ).fetchone()
        return bool(row and row[0] == "muted")

    def mute(self, group_openid: str, member_openid: str, *, by: str, reason: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO abuse_state(group_openid,member_openid,level,muted_at,muted_by,reason) "
                "VALUES(?,?,'muted',?,?,?) "
                "ON CONFLICT(group_openid,member_openid) DO UPDATE SET "
                "level='muted', muted_at=excluded.muted_at, "
                "muted_by=excluded.muted_by, reason=excluded.reason",
                (group_openid, member_openid, time.time(), by, reason),
            )
            self.conn.commit()
        self.audit("abuse.mute", target=f"{group_openid[-6:]}/{member_openid[-6:]}",
                   actor=by, reason=reason)

    def unmute(self, group_openid: str, member_openid: str, *, by: str = "admin") -> bool:
        with self._lock:
            cur = self.conn.execute(
                "DELETE FROM abuse_state WHERE group_openid=? AND member_openid=?",
                (group_openid, member_openid),
            )
            self.conn.commit()
            return cur.rowcount > 0

    def muted_list(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT group_openid, member_openid, muted_at, muted_by, reason "
                "FROM abuse_state ORDER BY muted_at DESC"
            ).fetchall()
        return [
            {
                "group": r[0],
                "member": r[1],
                "muted_at": r[2],
                "muted_by": r[3],
                "reason": r[4],
            }
            for r in rows
        ]

    # ── 额度 ──────────────────────────────────────────────
    def quota_get(self, scope: str, key: str, date: str) -> tuple[int, int]:
        with self._lock:
            row = self.conn.execute(
                "SELECT msgs, tokens FROM quota_daily WHERE scope=? AND scope_key=? AND date=?",
                (scope, key, date),
            ).fetchone()
        return (row[0], row[1]) if row else (0, 0)

    def quota_add(
        self,
        scope: str,
        key: str,
        date: str,
        *,
        msgs: int = 0,
        tokens: int = 0,
        prompt: int = 0,
        completion: int = 0,
        cached: int = 0,
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO quota_daily"
                "(scope,scope_key,date,msgs,tokens,prompt_tokens,completion_tokens,cached_tokens) "
                "VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(scope,scope_key,date) DO UPDATE SET "
                "msgs=msgs+excluded.msgs, tokens=tokens+excluded.tokens, "
                "prompt_tokens=prompt_tokens+excluded.prompt_tokens, "
                "completion_tokens=completion_tokens+excluded.completion_tokens, "
                "cached_tokens=cached_tokens+excluded.cached_tokens",
                (scope, key, date, msgs, tokens, prompt, completion, cached),
            )
            self.conn.commit()

    def quota_detail(self, scope: str, key: str, date: str) -> dict:
        with self._lock:
            row = self.conn.execute(
                "SELECT msgs,tokens,prompt_tokens,completion_tokens,cached_tokens "
                "FROM quota_daily WHERE scope=? AND scope_key=? AND date=?",
                (scope, key, date),
            ).fetchone()
        if not row:
            return {
                "msgs": 0,
                "tokens": 0,
                "prompt": 0,
                "completion": 0,
                "cached": 0,
            }
        return {
            "msgs": int(row[0]),
            "tokens": int(row[1]),
            "prompt": int(row[2]),
            "completion": int(row[3]),
            "cached": int(row[4]),
        }

    # ── 角色卡 ────────────────────────────────────────────
    def get_card(self, member_openid: str, pack_id: str, slot: str = "default") -> dict | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT data FROM characters WHERE member_openid=? AND pack_id=? AND slot=?",
                (member_openid, pack_id, slot),
            ).fetchone()
        if not row:
            return None
        try:
            data = json.loads(row[0])
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    def put_card(
        self, member_openid: str, pack_id: str, data: dict, slot: str = "default"
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO characters(member_openid,pack_id,slot,data,updated_at) "
                "VALUES(?,?,?,?,?) "
                "ON CONFLICT(member_openid,pack_id,slot) DO UPDATE SET "
                "data=excluded.data, updated_at=excluded.updated_at",
                (member_openid, pack_id, slot, json.dumps(data, ensure_ascii=False), time.time()),
            )
            self.conn.commit()

    def delete_card(self, member_openid: str, pack_id: str, slot: str = "default") -> bool:
        with self._lock:
            cur = self.conn.execute(
                "DELETE FROM characters WHERE member_openid=? AND pack_id=? AND slot=?",
                (member_openid, pack_id, slot),
            )
            self.conn.commit()
            return cur.rowcount > 0

    def count_cards(self, pack_id: str) -> int:
        with self._lock:
            row = self.conn.execute(
                "SELECT COUNT(*) FROM characters WHERE pack_id=?", (pack_id,)
            ).fetchone()
        return int(row[0]) if row else 0

    def delete_all_cards(self, member_openid: str) -> int:
        with self._lock:
            cur = self.conn.execute(
                "DELETE FROM characters WHERE member_openid=?", (member_openid,)
            )
            self.conn.commit()
            return int(cur.rowcount or 0)

    # ── 代码插件 ──────────────────────────────────────────
    def plugin_state(self, plugin_id: str) -> tuple[bool, str, dict]:
        with self._lock:
            row = self.conn.execute(
                "SELECT enabled, file_hash, store FROM code_plugins WHERE id=?",
                (plugin_id,),
            ).fetchone()
        if not row:
            return False, "", {}
        try:
            data = json.loads(row[2] or "{}")
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        return bool(row[0]), row[1] or "", data

    def set_plugin_enabled(self, plugin_id: str, enabled: bool, file_hash: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO code_plugins(id,enabled,file_hash,updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled, "
                "file_hash=excluded.file_hash, updated_at=excluded.updated_at",
                (plugin_id, 1 if enabled else 0, file_hash, time.time()),
            )
            self.conn.commit()

    def set_plugin_store(self, plugin_id: str, data: dict) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO code_plugins(id,enabled,file_hash,store,updated_at) "
                "VALUES(?,0,'',?,?) "
                "ON CONFLICT(id) DO UPDATE SET store=excluded.store, updated_at=excluded.updated_at",
                (plugin_id, json.dumps(data, ensure_ascii=False)[:100000], time.time()),
            )
            self.conn.commit()

    def all_plugin_states(self) -> dict[str, dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, enabled, file_hash, store FROM code_plugins"
            ).fetchall()
        out = {}
        for r in rows:
            try:
                data = json.loads(r[3] or "{}")
            except Exception:
                data = {}
            out[r[0]] = {"enabled": bool(r[1]), "file_hash": r[2] or "", "store": data}
        return out

    # ── 规则 hook 状态（按 规则 + 群） ────────────────────
    def get_rule_store(self, pack_id: str, group_openid: str) -> dict:
        with self._lock:
            row = self.conn.execute(
                "SELECT data FROM rule_store WHERE pack_id=? AND group_openid=?",
                (pack_id, group_openid),
            ).fetchone()
        if not row:
            return {}
        try:
            data = json.loads(row[0] or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def set_rule_store(self, pack_id: str, group_openid: str, data: dict) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO rule_store(pack_id,group_openid,data,updated_at) "
                "VALUES(?,?,?,?) "
                "ON CONFLICT(pack_id,group_openid) DO UPDATE SET "
                "data=excluded.data, updated_at=excluded.updated_at",
                (
                    pack_id,
                    group_openid,
                    json.dumps(data, ensure_ascii=False)[:100000],
                    time.time(),
                ),
            )
            self.conn.commit()

    # ── 规则 hook 启用状态 ────────────────────────────────
    def rule_hook_state(self, pack_id: str) -> tuple[bool, str]:
        with self._lock:
            row = self.conn.execute(
                "SELECT hooks_enabled, file_hash FROM rule_plugins WHERE id=?",
                (pack_id,),
            ).fetchone()
        if not row:
            return False, ""
        return bool(row[0]), row[1] or ""

    def all_rule_hook_states(self) -> dict[str, dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, hooks_enabled, file_hash FROM rule_plugins"
            ).fetchall()
        return {
            r[0]: {"enabled": bool(r[1]), "file_hash": r[2] or ""} for r in rows
        }

    def set_rule_hook_enabled(
        self, pack_id: str, enabled: bool, file_hash: str
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO rule_plugins(id,hooks_enabled,file_hash,updated_at) "
                "VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "hooks_enabled=excluded.hooks_enabled, "
                "file_hash=excluded.file_hash, updated_at=excluded.updated_at",
                (pack_id, 1 if enabled else 0, file_hash, time.time()),
            )
            self.conn.commit()

    # ── 模式通知 ──────────────────────────────────────────
    def set_mode_notice(self, group_openid: str, text: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO mode_notices(group_openid,text,created_at) "
                "VALUES(?,?,?) ON CONFLICT(group_openid) DO UPDATE SET "
                "text=excluded.text, created_at=excluded.created_at",
                (group_openid, text[:1000], time.time()),
            )
            self.conn.commit()

    def pop_mode_notice(self, group_openid: str) -> str:
        with self._lock:
            row = self.conn.execute(
                "SELECT text FROM mode_notices WHERE group_openid=?",
                (group_openid,),
            ).fetchone()
            if not row:
                return ""
            self.conn.execute(
                "DELETE FROM mode_notices WHERE group_openid=?", (group_openid,)
            )
            self.conn.commit()
        return row[0] or ""

    def clear_mode_notice(self, group_openid: str) -> None:
        with self._lock:
            self.conn.execute(
                "DELETE FROM mode_notices WHERE group_openid=?", (group_openid,)
            )
            self.conn.commit()

    # ── 规则插件启用状态 ──────────────────────────────────
    def rulepack_enabled(self, pack_id: str) -> bool:
        with self._lock:
            row = self.conn.execute(
                "SELECT enabled FROM rulepacks WHERE id=?", (pack_id,)
            ).fetchone()
        return True if not row else bool(row[0])

    def set_rulepack_enabled(self, pack_id: str, enabled: bool) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO rulepacks(id,enabled,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled, "
                "updated_at=excluded.updated_at",
                (pack_id, 1 if enabled else 0, time.time()),
            )
            self.conn.commit()

    def normalize_group_rulepacks(self, valid: set[str], fallback: str) -> int:
        """把指向已停用/已删除规则的群，改回可用的规则。"""
        with self._lock:
            rows = self.conn.execute(
                "SELECT group_openid, rulepack FROM groups WHERE rulepack != ''"
            ).fetchall()
            changed = 0
            for group_openid, pack_id in rows:
                if pack_id in valid:
                    continue
                self.conn.execute(
                    "UPDATE groups SET rulepack=? WHERE group_openid=?",
                    (fallback, group_openid),
                )
                changed += 1
            if changed:
                self.conn.commit()
            return changed

    # ── wiki 缓存 ─────────────────────────────────────────
    def wiki_cache_get(self, key: str) -> str | None:
        with self._lock:
            row = self.conn.execute(
                "SELECT content, expires_at FROM wiki_cache WHERE key=?", (key,)
            ).fetchone()
        if not row or float(row[1]) < time.time():
            return None
        return str(row[0])

    def wiki_cache_put(
        self, key: str, url: str, content: str, ttl: float
    ) -> None:
        now = time.time()
        with self._lock:
            self.conn.execute(
                "INSERT INTO wiki_cache(key,url,content,fetched_at,expires_at) "
                "VALUES(?,?,?,?,?) "
                "ON CONFLICT(key) DO UPDATE SET url=excluded.url, "
                "content=excluded.content, fetched_at=excluded.fetched_at, "
                "expires_at=excluded.expires_at",
                (key, url, content, now, now + ttl),
            )
            self.conn.execute(
                "DELETE FROM wiki_cache WHERE expires_at < ?", (now - 7 * 86400,)
            )
            self.conn.commit()

    # ── 小游戏 ────────────────────────────────────────────
    def group_game(self, group_openid: str) -> str:
        with self._lock:
            row = self.conn.execute(
                "SELECT minigame_id FROM groups WHERE group_openid=?",
                (group_openid,),
            ).fetchone()
        return row[0] if row and row[0] else ""

    def set_group_game(self, group_openid: str, game_id: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO groups(group_openid,status,added_at,minigame_id) "
                "VALUES(?,'active',?,?) "
                "ON CONFLICT(group_openid) DO UPDATE SET "
                "minigame_id=excluded.minigame_id",
                (group_openid, time.time(), game_id),
            )
            self.conn.commit()

    def game_state(self, game_id: str) -> tuple[bool, str]:
        with self._lock:
            row = self.conn.execute(
                "SELECT enabled, file_hash FROM minigames WHERE id=?", (game_id,)
            ).fetchone()
        if not row:
            return False, ""
        return bool(row[0]), row[1] or ""

    def all_game_states(self) -> dict[str, dict]:
        with self._lock:
            rows = self.conn.execute(
                "SELECT id, enabled, file_hash FROM minigames"
            ).fetchall()
        return {
            r[0]: {"enabled": bool(r[1]), "file_hash": r[2] or ""} for r in rows
        }

    def set_game_enabled(self, game_id: str, enabled: bool, file_hash: str) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO minigames(id,enabled,file_hash,updated_at) "
                "VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET "
                "enabled=excluded.enabled, file_hash=excluded.file_hash, "
                "updated_at=excluded.updated_at",
                (game_id, 1 if enabled else 0, file_hash, time.time()),
            )
            self.conn.commit()

    def get_game_store(self, game_id: str, group_openid: str) -> dict:
        with self._lock:
            row = self.conn.execute(
                "SELECT data FROM game_store WHERE game_id=? AND group_openid=?",
                (game_id, group_openid),
            ).fetchone()
        if not row:
            return {}
        try:
            data = json.loads(row[0] or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def set_game_store(self, game_id: str, group_openid: str, data: dict) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO game_store(game_id,group_openid,data,updated_at) "
                "VALUES(?,?,?,?) ON CONFLICT(game_id,group_openid) DO UPDATE SET "
                "data=excluded.data, updated_at=excluded.updated_at",
                (
                    game_id,
                    group_openid,
                    json.dumps(data, ensure_ascii=False)[:100000],
                    time.time(),
                ),
            )
            self.conn.commit()

    def clear_game_store(self, game_id: str, group_openid: str) -> None:
        with self._lock:
            self.conn.execute(
                "DELETE FROM game_store WHERE game_id=? AND group_openid=?",
                (game_id, group_openid),
            )
            self.conn.commit()

    def get_solo_store(
        self, game_id: str, group_openid: str, member_openid: str
    ) -> dict:
        with self._lock:
            row = self.conn.execute(
                "SELECT data FROM solo_store "
                "WHERE game_id=? AND group_openid=? AND member_openid=?",
                (game_id, group_openid, member_openid),
            ).fetchone()
        if not row:
            return {}
        try:
            data = json.loads(row[0] or "{}")
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def set_solo_store(
        self, game_id: str, group_openid: str, member_openid: str, data: dict
    ) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO solo_store"
                "(game_id,group_openid,member_openid,data,updated_at) "
                "VALUES(?,?,?,?,?) "
                "ON CONFLICT(game_id,group_openid,member_openid) DO UPDATE SET "
                "data=excluded.data, updated_at=excluded.updated_at",
                (
                    game_id,
                    group_openid,
                    member_openid,
                    json.dumps(data, ensure_ascii=False)[:100000],
                    time.time(),
                ),
            )
            self.conn.commit()

    def clear_solo_store(
        self, game_id: str, group_openid: str, member_openid: str
    ) -> None:
        with self._lock:
            self.conn.execute(
                "DELETE FROM solo_store "
                "WHERE game_id=? AND group_openid=? AND member_openid=?",
                (game_id, group_openid, member_openid),
            )
            self.conn.commit()

    # ── 数据维护 ──────────────────────────────────────────
    def checkpoint(self) -> None:
        with self._lock:
            try:
                self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
                self.conn.commit()
            except sqlite3.Error:
                pass

    def restore_from(self, path: Path) -> None:
        src = sqlite3.connect(path)
        try:
            with self._lock:
                src.backup(self.conn)
                self.conn.commit()
        finally:
            src.close()
        with self._lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()
        self._migrate()

    def reset_all(self) -> None:
        tables = [
            "meta",
            "seen",
            "sent",
            "groups",
            "audit",
            "threads",
            "group_reply",
            "abuse_state",
            "quota_daily",
            "characters",
            "code_plugins",
            "rule_store",
            "rule_plugins",
            "rulepacks",
            "minigames",
            "game_store",
            "solo_store",
            "mode_notices",
            "wiki_cache",
            "proactive_state",
            "plugin_kv",
        ]
        with self._lock:
            for table in tables:
                try:
                    self.conn.execute(f"DELETE FROM {table}")
                except sqlite3.Error:
                    pass
            self.conn.commit()

    # ── 审计 ──────────────────────────────────────────────
    def audit(self, action: str, target: str = "", actor: str = "system", **detail) -> None:
        with self._lock:
            self.conn.execute(
                "INSERT INTO audit(ts,actor,action,target,detail) VALUES(?,?,?,?,?)",
                (time.time(), actor, action, target, json.dumps(detail, ensure_ascii=False)),
            )
            self.conn.commit()

    def audit_count(self) -> int:
        with self._lock:
            row = self.conn.execute("SELECT COUNT(*) FROM audit").fetchone()
        return int(row[0]) if row else 0

    def prune_audit(
        self, keep_days: int = 30, keep_rows: int = 5000, purge_all: bool = False
    ) -> int:
        """裁剪审计表。

        keep_days=0 表示不按时间删除；purge_all=True 时全部清空。
        """
        now = time.time()
        deleted = 0
        with self._lock:
            if purge_all:
                cur = self.conn.execute("DELETE FROM audit")
                self.conn.commit()
                return max(0, cur.rowcount)
            if keep_days > 0:
                cur = self.conn.execute(
                    "DELETE FROM audit WHERE ts < ?", (now - keep_days * 86400,)
                )
                deleted += max(0, cur.rowcount)
            if keep_rows > 0:
                cur = self.conn.execute(
                    "DELETE FROM audit WHERE id NOT IN "
                    "(SELECT id FROM audit ORDER BY ts DESC LIMIT ?)",
                    (keep_rows,),
                )
                deleted += max(0, cur.rowcount)
            self.conn.commit()
        return deleted
