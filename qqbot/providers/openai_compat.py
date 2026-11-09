"""OpenAI 兼容 Provider。

一套实现覆盖 GLM / DeepSeek / Gemini(OpenAI 兼容端点) 以及绝大多数国内 API：
只要提供 base_url + model + api_key 即可。
"""

from __future__ import annotations

import time

import httpx

from .. import errors
from .base import ChatMessage, Completion, ProbeResult


def _content_text(content) -> str:
    """兼容 content 为字符串、分段数组或对象三种返回格式。"""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, dict):
        return str(content.get("text") or "").strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
        return "".join(parts).strip()
    return ""


class OpenAICompatProvider:
    id = "openai"

    def __init__(self, base_url: str, model: str, api_key: str, *, temperature: float = 0.7):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self._http = httpx.AsyncClient(timeout=httpx.Timeout(60.0))

    def _url(self) -> str:
        if self.base_url.endswith("/chat/completions"):
            return self.base_url
        return f"{self.base_url}/chat/completions"

    def _models_url(self) -> str:
        return self._url()[: -len("/chat/completions")] + "/models"

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        timeout: float,
        max_tokens: int,
    ) -> Completion:
        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "max_tokens": max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            resp = await self._http.post(
                self._url(), json=payload, headers=headers, timeout=timeout
            )
        except httpx.TimeoutException as exc:
            raise errors.BotError(errors.LLM_TIMEOUT, "模型响应超时", retryable=True) from exc
        except httpx.HTTPError as exc:
            raise errors.BotError(errors.LLM_BAD_RESPONSE, "模型请求失败", retryable=True) from exc

        if resp.status_code == 401 or resp.status_code == 403:
            raise errors.BotError(errors.LLM_AUTH, "模型密钥无效或无权限")
        if resp.status_code == 429:
            raise errors.BotError(errors.LLM_RATE_LIMIT, "模型上游限流", retryable=True)
        if resp.status_code >= 400:
            raise errors.BotError(
                errors.LLM_BAD_RESPONSE,
                f"模型返回错误（HTTP {resp.status_code}）",
                detail={"body": resp.text[:200]},
            )

        try:
            data = resp.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
        except Exception as exc:
            raise errors.BotError(errors.LLM_BAD_RESPONSE, "模型返回格式异常") from exc

        return Completion(
            text=_content_text(content),
            model=data.get("model", self.model),
            usage=data.get("usage", {}),
            finish_reason=str(choice.get("finish_reason") or ""),
        )

    async def probe(self) -> ProbeResult:
        started = time.perf_counter()
        try:
            await self.complete(
                [ChatMessage("user", "回复 ok 两个字")], timeout=15, max_tokens=8
            )
            return ProbeResult(
                ok=True,
                detail=f"{self.model} 可用",
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
        except Exception as exc:
            return ProbeResult(ok=False, detail=str(exc))

    async def aclose(self) -> None:
        await self._http.aclose()

    async def list_models(self) -> list[str]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = await self._http.get(self._models_url(), headers=headers, timeout=20)
        except httpx.HTTPError as exc:
            raise errors.BotError(errors.LLM_BAD_RESPONSE, "拉取模型列表失败（网络）") from exc
        if resp.status_code in (401, 403):
            raise errors.BotError(errors.LLM_AUTH, "密钥无效，无法读取模型列表")
        if resp.status_code >= 400:
            raise errors.BotError(
                errors.LLM_BAD_RESPONSE,
                f"该服务不支持模型列表（HTTP {resp.status_code}），请手动填写",
            )
        try:
            data = resp.json()
        except Exception as exc:
            raise errors.BotError(errors.LLM_BAD_RESPONSE, "模型列表格式异常") from exc

        items = data.get("data") if isinstance(data, dict) else data
        out: list[str] = []
        for it in items or []:
            if isinstance(it, dict):
                mid = it.get("id") or it.get("name")
            else:
                mid = str(it)
            if mid:
                out.append(mid)
        return sorted(out)


async def fetch_models(base_url: str, api_key: str, *, timeout: float = 20) -> list[str]:
    """不依赖已保存的 Provider，直接拉一次模型列表。"""
    provider = OpenAICompatProvider(base_url, "-", api_key)
    try:
        return await provider.list_models()
    finally:
        await provider.aclose()
