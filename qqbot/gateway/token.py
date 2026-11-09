"""AccessToken 管理：缓存 + 提前刷新 + singleflight。"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

from .. import errors

log = logging.getLogger(__name__)

TOKEN_URL = "https://api.bot.qq.com/app/getAppAccessToken"
#: 提前这么多秒刷新
REFRESH_AHEAD = 300


class TokenManager:
    def __init__(self, app_id: str, app_secret: str, *, http: httpx.AsyncClient | None = None):
        self.app_id = app_id
        self.app_secret = app_secret
        self._http = http
        self._owns_http = http is None
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = asyncio.Lock()
        self._failures = 0

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            self._http = httpx.AsyncClient(timeout=httpx.Timeout(15.0))
        return self._http

    async def aclose(self) -> None:
        if self._owns_http and self._http is not None:
            await self._http.aclose()
            self._http = None

    # ── 公开接口 ─────────────────────────────────────────
    async def get(self) -> str:
        if self._token and time.time() < self._expires_at:
            return self._token
        return await self._refresh()

    async def force_refresh(self) -> str:
        self._token = None
        self._expires_at = 0.0
        return await self._refresh()

    @property
    def failures(self) -> int:
        return self._failures

    # ── 内部 ────────────────────────────────────────────
    async def _refresh(self) -> str:
        """singleflight：同一时刻只有一个请求在飞，其余等待结果。"""
        async with self._lock:
            # 可能在等锁期间已被别人刷新
            if self._token and time.time() < self._expires_at:
                return self._token

            if not self.app_id or not self.app_secret:
                raise errors.BotError(errors.TOKEN_EMPTY, "尚未配置 appId / appSecret")

            client = await self._client()
            try:
                resp = await client.post(
                    TOKEN_URL,
                    json={"appId": self.app_id, "clientSecret": self.app_secret},
                )
            except httpx.HTTPError as exc:
                self._failures += 1
                raise errors.BotError(
                    errors.TOKEN_FETCH_FAILED, "获取访问凭证失败（网络）", retryable=True
                ) from exc

            if resp.status_code >= 400:
                self._failures += 1
                raise errors.BotError(
                    errors.TOKEN_INVALID,
                    f"获取访问凭证失败（HTTP {resp.status_code}）",
                )

            try:
                data = resp.json()
            except Exception as exc:
                raise errors.BotError(errors.TOKEN_FETCH_FAILED, "凭证响应格式异常") from exc

            token = data.get("access_token")
            if not token:
                self._failures += 1
                code = data.get("code") or data.get("err_code")
                msg = data.get("message") or data.get("msg") or ""
                detail = f"code={code} {msg}".strip() if code else "响应缺少 access_token"
                raise errors.BotError(errors.TOKEN_INVALID, f"获取访问凭证失败：{detail}")

            # 文档中 expires_in 是字符串
            try:
                ttl = int(data.get("expires_in", 7200))
            except (TypeError, ValueError):
                ttl = 7200

            self._token = token
            self._expires_at = time.time() + max(60, ttl - REFRESH_AHEAD)
            self._failures = 0
            log.info("access_token 已刷新，有效期约 %ss", ttl)
            return token
