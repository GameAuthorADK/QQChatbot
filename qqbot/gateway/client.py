"""WebSocket 网关客户端。

职责边界：只管连接、鉴权、心跳、resume。**不做任何业务判断**。
事件通过回调派发，回调必须立即返回。
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from enum import Enum
from typing import Awaitable, Callable

import httpx

from .. import errors
from ..events import (
    EVENT_GROUP_ADD,
    EVENT_GROUP_DEL,
    GroupMessage,
    SystemEvent,
    parse_group_message,
)
from . import protocol
from .protocol import ProtocolError
from .token import TokenManager

try:  # websockets >= 13
    from websockets.asyncio.client import connect as ws_connect
except Exception:  # pragma: no cover
    from websockets import connect as ws_connect  # type: ignore

log = logging.getLogger(__name__)

GATEWAY_URL = "https://api.bot.qq.com/gateway"

EventHandler = Callable[[GroupMessage | SystemEvent], Awaitable[None]]
StateHandler = Callable[["GatewayState"], None]


class GatewayState(str, Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    IDENTIFYING = "identifying"
    READY = "ready"
    RECONNECTING = "reconnecting"
    RESUMING = "resuming"
    FATAL = "fatal"
    STOPPED = "stopped"


class Gateway:
    def __init__(
        self,
        tokens: TokenManager,
        *,
        on_event: EventHandler,
        on_state: StateHandler | None = None,
        intents: int = protocol.DEFAULT_INTENTS,
        shard: tuple[int, int] = (0, 1),
        max_retries: int = 20,
    ):
        self.tokens = tokens
        self.on_event = on_event
        self.on_state = on_state
        self.intents = intents
        self.shard = shard
        self.max_retries = max_retries

        self.state = GatewayState.IDLE
        self.session_id: str | None = None
        self.user_id: str = ""
        self.username: str = ""

        self._seq: int = 0
        self._ack = asyncio.Event()
        self._stopped = False
        self._task: asyncio.Task | None = None
        self._http: httpx.AsyncClient | None = None
        self._last_error: str = ""

    # ── 生命周期 ─────────────────────────────────────────
    def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopped = False
        self._task = asyncio.create_task(self._run(), name="gateway")

    async def stop(self) -> None:
        self._stopped = True
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        if self._http:
            await self._http.aclose()
            self._http = None
        self._set_state(GatewayState.STOPPED)

    @property
    def last_error(self) -> str:
        return self._last_error

    def _set_state(self, s: GatewayState) -> None:
        if s == self.state:
            return
        self.state = s
        log.info("网关状态 → %s", s.value)
        if self.on_state:
            try:
                self.on_state(s)
            except Exception:
                log.exception("on_state 回调异常")

    # ── 主循环 ───────────────────────────────────────────
    async def _run(self) -> None:
        retries = 0
        backoff = 1.0
        while not self._stopped:
            try:
                if retries == 0:
                    self._set_state(
                        GatewayState.RESUMING if self.session_id else GatewayState.CONNECTING
                    )
                await self._session()
                retries = 0
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except errors.BotError as exc:
                self._last_error = str(exc)
                if exc.code in (errors.TOKEN_EMPTY, errors.TOKEN_INVALID, errors.WS_IDENTIFY_REJECTED):
                    log.error("网关致命错误: %s", exc)
                    self._set_state(GatewayState.FATAL)
                    return
                log.warning("网关错误: %s", exc)
            except Exception as exc:
                self._last_error = repr(exc)
                log.warning("网关异常: %s", exc)

            if self._stopped:
                return

            retries += 1
            if retries > self.max_retries:
                log.error("重连次数超过上限（%d），停止", self.max_retries)
                self._set_state(GatewayState.FATAL)
                return

            self._set_state(GatewayState.RECONNECTING)
            delay = min(backoff, 60.0) * (0.8 + random.random() * 0.4)
            log.info("将在 %.1fs 后重连（第 %d 次）", delay, retries)
            await asyncio.sleep(delay)
            backoff = min(backoff * 2, 60.0)

    async def _gateway_url(self) -> str:
        token = await self.tokens.get()
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        try:
            resp = await self._http.get(
                GATEWAY_URL, headers={"Authorization": f"QQBot {token}"}
            )
        except httpx.HTTPError as exc:
            raise errors.BotError(
                errors.GATEWAY_URL_FAILED, "获取网关地址失败", retryable=True
            ) from exc
        if resp.status_code >= 400:
            raise errors.BotError(
                errors.GATEWAY_URL_FAILED, f"获取网关地址失败（HTTP {resp.status_code}）"
            )
        url = (resp.json() or {}).get("url")
        if not url:
            raise errors.BotError(errors.GATEWAY_URL_FAILED, "网关地址为空")
        return url

    async def _session(self) -> None:
        url = await self._gateway_url()
        token = await self.tokens.get()

        resuming = bool(self.session_id)
        self._set_state(GatewayState.RESUMING if resuming else GatewayState.CONNECTING)

        try:
            ws = await ws_connect(
                url, ping_interval=None, max_size=None, open_timeout=15, close_timeout=5
            )
        except Exception as exc:
            raise errors.BotError(errors.WS_CONNECT_FAILED, "无法建立 wss 连接") from exc

        async with ws:
            # 1) Hello
            raw = await asyncio.wait_for(ws.recv(), timeout=20)
            hello = protocol.decode(raw)
            if hello.get("op") != protocol.OP_HELLO:
                raise errors.BotError(errors.WS_CONNECT_FAILED, "未收到 Hello")
            interval_ms = int((hello.get("d") or {}).get("heartbeat_interval", 45000))
            interval = max(5.0, interval_ms / 1000.0)
            log.info("已连接网关，心跳间隔 %.1fs", interval)

            # 2) Identify / Resume
            if resuming:
                self._set_state(GatewayState.RESUMING)
                await ws.send(protocol.resume(token, self.session_id or "", self._seq))
            else:
                self._set_state(GatewayState.IDENTIFYING)
                await ws.send(protocol.identify(token, self.intents, self.shard))

            hb = asyncio.create_task(self._heartbeat(ws, interval), name="heartbeat")
            try:
                await self._read_loop(ws)
            finally:
                hb.cancel()
                try:
                    await hb
                except (asyncio.CancelledError, Exception):
                    pass

    async def _heartbeat(self, ws, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            try:
                self._ack.clear()
                await ws.send(protocol.heartbeat(self._seq or None))
            except Exception:
                return
            try:
                await asyncio.wait_for(self._ack.wait(), timeout=interval * 2)
            except asyncio.TimeoutError:
                log.warning("心跳超时，主动断开")
                try:
                    await ws.close()
                except Exception:
                    pass
                return

    async def _read_loop(self, ws) -> None:
        async for raw in ws:
            try:
                msg = protocol.decode(raw)
            except ProtocolError as exc:
                log.warning("协议错误: %s", exc)
                continue

            op = msg.get("op")

            if op == protocol.OP_HEARTBEAT_ACK:
                self._ack.set()
                continue

            if op == protocol.OP_RECONNECT:
                log.info("服务端要求重连")
                return

            if op == protocol.OP_INVALID_SESSION:
                log.warning("会话失效，清空后重新鉴权")
                self.session_id = None
                self._seq = 0
                raise errors.BotError(errors.WS_RESUME_FAILED, "会话失效")

            if op != protocol.OP_DISPATCH:
                continue

            seq = int(msg.get("s") or 0)
            if seq:
                self._seq = seq

            evt = msg.get("t")
            data = msg.get("d") or {}

            if evt == protocol.EVENT_READY:
                self.session_id = data.get("session_id")
                user = data.get("user") or {}
                self.user_id = str(user.get("id", ""))
                self.username = user.get("username", "")
                self._set_state(GatewayState.READY)
                await self._emit(SystemEvent("ready", {"session_id": self.session_id}))
                continue

            if evt == protocol.EVENT_RESUMED:
                self._set_state(GatewayState.READY)
                await self._emit(SystemEvent("resumed", {}))
                continue

            if evt in ("GROUP_AT_MESSAGE_CREATE", "GROUP_MESSAGE_CREATE"):
                author = data.get("author") or {}
                if author.get("bot"):
                    continue
                await self._emit(
                    parse_group_message(
                        data, seq, raw_type=evt, bot_id=self.user_id or ""
                    )
                )
                continue

            if evt == EVENT_GROUP_ADD:
                await self._emit(SystemEvent("group_add", data))
                continue

            if evt == EVENT_GROUP_DEL:
                await self._emit(SystemEvent("group_del", data))
                continue

            # C2C_MESSAGE_CREATE 及其它一律丢弃：本 bot 只服务群聊

    async def _emit(self, event) -> None:
        try:
            await self.on_event(event)
        except Exception:
            log.exception("事件回调异常")
