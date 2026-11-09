"""Provider 工厂。"""

from __future__ import annotations

from .. import errors
from . import presets
from .base import ChatMessage, Completion, ProbeResult, Provider, build_messages
from .mock import FailingProvider, MockProvider
from .openai_compat import OpenAICompatProvider, fetch_models

__all__ = [
    "ChatMessage",
    "Completion",
    "ProbeResult",
    "Provider",
    "build_messages",
    "build_provider",
    "presets",
    "MockProvider",
]


def build_provider(cfg, api_key: str) -> Provider:
    kind = (cfg.provider or "mock").strip().lower()

    if kind in ("mock", ""):
        return MockProvider()

    if kind == "failing":
        return FailingProvider()

    preset = presets.get(kind)
    if preset is None:
        raise errors.BotError(errors.LLM_NO_PROVIDER, f"未知的模型服务：{kind}")

    # 预设负责填默认值，界面上的手填优先
    base_url = (cfg.base_url or preset.base_url).strip()
    model = (cfg.model or (preset.models[0] if preset.models else "")).strip()

    if not base_url:
        raise errors.BotError(errors.LLM_NO_PROVIDER, "请先填写模型地址（Base URL）")
    if not model:
        raise errors.BotError(errors.LLM_NO_PROVIDER, "请先填写模型名")
    if preset.needs_key and not api_key:
        raise errors.BotError(errors.LLM_AUTH, "请先填写模型 API Key")

    return OpenAICompatProvider(base_url, model, api_key or "-")
