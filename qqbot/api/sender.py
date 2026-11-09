"""出站：发送群消息。"""

from __future__ import annotations

import logging

import httpx

from .. import errors
from ..events import GroupMessage
from ..gateway.token import TokenManager

log = logging.getLogger(__name__)

API_BASE = "https://api.bot.qq.com"
SEND_GROUP = API_BASE + "/v2/groups/{group_openid}/messages"


class Sender:
    def __init__(self, tokens: TokenManager, *, http: httpx.AsyncClient | None = None):
        self.tokens = tokens
        self._http = http or httpx.AsyncClient(timeout=httpx.Timeout(10.0))

    async def aclose(self) -> None:
        await self._http.aclose()

    async def send_group_text(
        self,
        group_openid: str,
        content: str,
        *,
        msg_id: str = "",
        msg_seq: int = 0,
    ) -> str:
        """发送被动回复；不传 msg_id 时是主动消息。"""
        token = await self.tokens.get()
        body = {
            "content": content,
            "msg_type": 0,
        }
        if msg_id:
            body["msg_id"] = msg_id
            body["msg_seq"] = msg_seq
        url = SEND_GROUP.format(group_openid=group_openid)
        try:
            resp = await self._http.post(
                url, json=body, headers={"Authorization": f"QQBot {token}"}
            )
        except httpx.HTTPError as exc:
            raise errors.BotError(
                errors.SEND_FAILED, "发送失败（网络）", retryable=True
            ) from exc

        if resp.status_code == 429:
            raise errors.BotError(errors.SEND_RATE_LIMITED, "发送过于频繁", retryable=True)
        if resp.status_code >= 400:
            detail = resp.text[:300]
            code = errors.SEND_FAILED
            if "msg_seq" in detail or "seq" in detail.lower():
                code = errors.SEND_MSG_SEQ_CONFLICT
            raise errors.BotError(code, f"发送失败（HTTP {resp.status_code}）", detail={"body": detail})

        try:
            data = resp.json()
        except Exception:
            data = {}
        return str(data.get("id", ""))

    async def reply(self, msg: GroupMessage, content: str, msg_seq: int) -> str:
        return await self.send_group_text(
            msg.group_openid, content, msg_id=msg.msg_id, msg_seq=msg_seq
        )
