"""网关协议常量与报文构造。

协议极简：opcode 0/1/2/6/7/9/10/11。
"""

from __future__ import annotations

import json

OP_DISPATCH = 0
OP_HEARTBEAT = 1
OP_IDENTIFY = 2
OP_RESUME = 6
OP_RECONNECT = 7
OP_INVALID_SESSION = 9
OP_HELLO = 10
OP_HEARTBEAT_ACK = 11

#: 群 + 单聊事件共用这一位，无法只订阅群聊
INTENT_GROUP_AND_C2C = 1 << 25
#: 首版只需群聊相关事件
DEFAULT_INTENTS = INTENT_GROUP_AND_C2C

EVENT_READY = "READY"
EVENT_RESUMED = "RESUMED"


class ProtocolError(Exception):
    pass


def decode(raw: str | bytes) -> dict:
    try:
        data = json.loads(raw)
    except Exception as exc:
        raise ProtocolError(f"非法 JSON: {raw!r}") from exc
    if not isinstance(data, dict) or "op" not in data:
        raise ProtocolError(f"缺少 op 字段: {data!r}")
    return data


def encode(op: int, d=None, s: int | None = None, t: str | None = None) -> str:
    payload: dict = {"op": op}
    if d is not None:
        payload["d"] = d
    if s is not None:
        payload["s"] = s
    if t is not None:
        payload["t"] = t
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def identify(token: str, intents: int, shard: tuple[int, int]) -> str:
    return encode(
        OP_IDENTIFY,
        {
            "token": f"QQBot {token}",
            "intents": intents,
            "shard": [shard[0], shard[1]],
            "properties": {"$os": "windows", "$browser": "qqbot-local", "$device": "qqbot-local"},
        },
    )


def resume(token: str, session_id: str, seq: int) -> str:
    return encode(
        OP_RESUME,
        {"token": f"QQBot {token}", "session_id": session_id, "seq": seq},
    )


def heartbeat(seq: int | None) -> str:
    return encode(OP_HEARTBEAT, seq)
