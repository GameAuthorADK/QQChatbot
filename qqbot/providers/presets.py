"""模型服务预设。

只负责"填 URL 和默认模型名"，不保证模型名长期有效。
模型名一律可在界面里手改。
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Preset:
    id: str
    label: str
    base_url: str
    models: tuple[str, ...] = ()
    needs_key: bool = True
    note: str = ""


PRESETS: tuple[Preset, ...] = (
    Preset(
        id="mock",
        label="假模型（无需 Key）",
        base_url="",
        models=("mock",),
        needs_key=False,
        note="用于联调，回复里会带上文轮数",
    ),
    Preset(
        id="deepseek",
        label="DeepSeek",
        base_url="https://api.deepseek.com/v1",
        models=("deepseek-chat", "deepseek-reasoner"),
        note="reasoner 会返回 reasoning_content，content 可能较晚才填满",
    ),
    Preset(
        id="glm",
        label="智谱 GLM",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        models=("glm-4.6", "glm-4.5", "glm-4-flash"),
        note="模型名以智谱控制台为准",
    ),
    Preset(
        id="gemini",
        label="Google Gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        models=("gemini-2.5-flash", "gemini-2.5-pro"),
        note="走 OpenAI 兼容层，部分参数支持有限",
    ),
    Preset(
        id="openai",
        label="OpenAI",
        base_url="https://api.openai.com/v1",
        models=("gpt-4o-mini", "gpt-4.1-mini"),
        note="o 系列推理模型可能需要 max_completion_tokens",
    ),
    Preset(
        id="custom",
        label="自定义（OpenAI 兼容）",
        base_url="",
        models=(),
        note="自行填写 Base URL 与模型名",
    ),
)

BY_ID: dict[str, Preset] = {p.id: p for p in PRESETS}


def get(preset_id: str) -> Preset | None:
    return BY_ID.get((preset_id or "").strip().lower())


def as_list() -> list[dict]:
    return [
        {
            "id": p.id,
            "label": p.label,
            "base_url": p.base_url,
            "models": list(p.models),
            "needs_key": p.needs_key,
            "note": p.note,
        }
        for p in PRESETS
    ]
