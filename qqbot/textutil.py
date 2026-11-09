"""文本处理：清洗与分段。"""

from __future__ import annotations

import re

#: 单条消息的保守上限（平台真实上限更大，但短消息观感更好）
CHUNK_LIMIT = 1200
#: 一轮最多发几条
MAX_CHUNKS = 3

_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MULTI_NL = re.compile(r"\n{3,}")
#: 出站禁止的 @ 语法（含 @全体成员）
_AT = re.compile(r"@(全体成员|all|everyone)", re.I)


def sanitize(text: str) -> str:
    """清洗模型输出：去控制字符、压缩空行、屏蔽 @ 全体。"""
    if not text:
        return ""
    text = _CONTROL.sub("", text)
    text = _AT.sub("＠\\1", text)
    text = _MULTI_NL.sub("\n\n", text)
    return text.strip()


def estimate_tokens(text: str) -> int:
    """粗略 token 估算：中文约 1.6 字 / token。"""
    return int(len(text or "") / 1.6) + 1


def split_text(text: str, limit: int = CHUNK_LIMIT, max_chunks: int = MAX_CHUNKS) -> list[str]:
    """按自然边界分段，最多 max_chunks 段，超出部分截断并加省略号。"""
    text = sanitize(text)
    if not text:
        return []
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    rest = text
    while rest and len(chunks) < max_chunks:
        if len(rest) <= limit:
            chunks.append(rest)
            rest = ""
            break
        window = rest[:limit]
        cut = max(
            window.rfind("\n\n"),
            window.rfind("\n"),
            window.rfind("。"),
            window.rfind("！"),
            window.rfind("？"),
            window.rfind(". "),
        )
        if cut < limit * 0.5:
            cut = limit
        else:
            cut += 1
        chunks.append(rest[:cut].strip())
        rest = rest[cut:].lstrip()

    if rest:
        chunks[-1] = chunks[-1][: limit - 1] + "…"
    return [c for c in chunks if c]


_SENTENCE = re.compile(r"(?<=[。！？!?…])(?![。！？!?…])\s*")


def split_human(text: str, max_parts: int = 3) -> list[str]:
    """把回复拆成几条更像真人说话的消息，句末句号会被去掉。"""
    text = sanitize(text)
    if not text:
        return []
    max_parts = max(1, min(5, int(max_parts)))

    if max_parts == 1:
        out = [text]
    else:
        blocks = [b.strip() for b in re.split(r"\n{2,}", text) if b.strip()]
        if len(blocks) == 1:
            blocks = [s.strip() for s in _SENTENCE.split(blocks[0]) if s.strip()]
        if len(blocks) <= max_parts:
            out = blocks or [text]
        else:
            total = sum(len(b) for b in blocks)
            target = total / max_parts
            out = []
            cur = ""
            for idx, block in enumerate(blocks):
                cur += block
                left_after = len(blocks) - idx - 1
                parts_left = max_parts - len(out) - 1
                if len(out) < max_parts - 1 and (
                    len(cur) >= target or (parts_left > 0 and left_after <= parts_left)
                ):
                    out.append(cur.strip())
                    cur = ""
            if cur.strip():
                out.append(cur.strip())
            if len(out) > max_parts:
                out = out[: max_parts - 1] + ["".join(out[max_parts - 1:])]

    cleaned: list[str] = []
    for part in out:
        part = part.strip()
        while part.endswith("。"):
            part = part[:-1].rstrip()
        if part:
            cleaned.append(part)
    return cleaned or [text.rstrip("。").strip() or text]
