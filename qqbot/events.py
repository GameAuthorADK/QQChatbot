"""领域事件：把网关的原始 JSON 收敛成内部结构。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Attachment:
    kind: str  # image | voice | video | file
    url: str
    mime: str = ""
    size: int = 0
    asr_text: str | None = None
    filename: str = ""


@dataclass(frozen=True)
class GroupMessage:
    group_openid: str
    member_openid: str
    member_role: str  # member | admin | owner
    msg_id: str
    content: str
    timestamp: str
    seq: int
    attachments: tuple[Attachment, ...] = ()
    mentions: tuple[str, ...] = ()
    raw_type: str = "GROUP_AT_MESSAGE_CREATE"
    mentioned: bool = True
    union_openid: str = ""


@dataclass(frozen=True)
class SystemEvent:
    kind: str  # group_add | group_del | ready | resumed
    data: dict = field(default_factory=dict)


@dataclass(frozen=True)
class BotInfo:
    user_id: str
    username: str
    session_id: str
    shard: tuple[int, int]


EVENT_GROUP_AT = "GROUP_AT_MESSAGE_CREATE"
EVENT_GROUP_ALL = "GROUP_MESSAGE_CREATE"
EVENT_C2C = "C2C_MESSAGE_CREATE"
EVENT_GROUP_ADD = "GROUP_ADD_ROBOT"
EVENT_GROUP_DEL = "GROUP_DEL_ROBOT"


def parse_timestamp(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return datetime.now()


def parse_attachments(items: list[dict] | None) -> tuple[Attachment, ...]:
    out: list[Attachment] = []
    for it in items or []:
        ctype = str(it.get("content_type", ""))
        if ctype.startswith("image/"):
            kind = "image"
        elif ctype == "voice":
            kind = "voice"
        elif ctype.startswith("video/"):
            kind = "video"
        else:
            kind = "file"
        out.append(
            Attachment(
                kind=kind,
                url=it.get("url", ""),
                mime=ctype,
                size=int(it.get("size") or 0),
                asr_text=it.get("asr_refer_text"),
                filename=it.get("filename", ""),
            )
        )
    return tuple(out)


def parse_group_message(
    payload: dict,
    seq: int,
    *,
    raw_type: str = EVENT_GROUP_AT,
    bot_id: str = "",
) -> GroupMessage:
    author = payload.get("author") or {}
    raw_content = (payload.get("content") or "").strip()
    mention_items = payload.get("mentions") or []
    mentions = tuple(u.get("id", "") for u in mention_items)
    if raw_type == EVENT_GROUP_AT:
        content = raw_content
        mentioned = True
    else:
        # 全量消息里 @ 会以 <@openid> 的形式留在正文里
        content = re.sub(r"<@[^>]{1,80}>", " ", raw_content)
        content = re.sub(r"\s{2,}", " ", content).strip()
        mentioned = bool(
            any(bool(u.get("bot")) for u in mention_items)
            or (bot_id and (bot_id in mentions or f"<@{bot_id}>" in raw_content))
        )
    return GroupMessage(
        group_openid=payload.get("group_openid", ""),
        member_openid=author.get("member_openid") or author.get("id", ""),
        member_role=author.get("member_role", "member"),
        msg_id=payload.get("id", ""),
        content=content,
        timestamp=payload.get("timestamp", ""),
        seq=seq,
        attachments=parse_attachments(payload.get("attachments")),
        mentions=mentions,
        raw_type=raw_type,
        mentioned=mentioned,
        union_openid=author.get("union_openid") or "",
    )
