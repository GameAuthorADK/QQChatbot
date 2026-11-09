"""QQ 图片下载：白名单域名 + 大小限制，转成 data URL 供模型使用。"""

from __future__ import annotations

import asyncio
import base64
import io
import logging
from urllib.parse import urlparse

import httpx

from .netguard import host_is_public

try:  # 缩图是可选能力，没有 Pillow 也能跑
    from PIL import Image
except Exception:  # pragma: no cover - 打包时一定会有
    Image = None

log = logging.getLogger(__name__)

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

#: QQ 群消息里的图片地址只会出现在这些域名下
ALLOWED_HOSTS = {"multimedia.nt.qq.com.cn"}
ALLOWED_SUFFIXES = (".qpic.cn",)
#: 只接受常见位图；SVG 之类可能带脚本，直接拒绝
ALLOWED_MIME = {
    "image/png",
    "image/jpeg",
    "image/jpg",
    "image/webp",
    "image/gif",
}

MAX_BYTES = 4 * 1024 * 1024
#: 缩放后的最长边，避免把几 MB 的原图直接塞给模型
MAX_EDGE = 1280
JPEG_QUALITY = 85
TIMEOUT = 12.0

#: 32x32 纯红 PNG，用于「测试看图」，不依赖 Pillow
TEST_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAKklEQVR42mO4o6FBU8QwasGo"
    "BaMWjFowasGoBaMWjFowasGoBaMWDBULAIahsD0l4r5QAAAAAElFTkSuQmCC"
)


def allowed_url(url: str) -> bool:
    parsed = urlparse(url or "")
    if parsed.scheme != "https":
        return False
    if parsed.username or parsed.password:
        return False
    host = (parsed.hostname or "").lower()
    if not host:
        return False
    if parsed.port not in (None, 443):
        return False
    if host in ALLOWED_HOSTS:
        return True
    return any(host.endswith(suffix) for suffix in ALLOWED_SUFFIXES)


def normalize_image(data: bytes, ctype: str) -> tuple[bytes, str]:
    """把图片缩到最长边 1280 并转成 JPEG，减少体积和格式兼容问题。"""
    if Image is None or not data:
        return data, ctype
    try:
        with Image.open(io.BytesIO(data)) as im:
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            else:
                im = im.convert("RGB")
            im.thumbnail((MAX_EDGE, MAX_EDGE))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=JPEG_QUALITY, optimize=True)
            out = buf.getvalue()
            if out and len(out) < len(data):
                return out, "image/jpeg"
    except Exception as exc:
        log.info("图片缩放失败，按原图发送：%s", type(exc).__name__)
    return data, ctype


async def fetch_data_url(url: str) -> str | None:
    """下载图片并转成 data URL；不合规、太大或失败都返回 None。"""
    if not allowed_url(url):
        log.info("图片地址不在白名单，忽略")
        return None

    host = urlparse(url).hostname or ""
    if not await asyncio.to_thread(host_is_public, host):
        log.info("图片域名解析到内网，忽略")
        return None

    headers = {"User-Agent": UA, "Accept": "image/*"}
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(TIMEOUT, connect=6.0),
            headers=headers,
            follow_redirects=False,
        ) as client:
            async with client.stream("GET", url) as resp:
                if resp.status_code != 200:
                    log.info("图片下载失败：HTTP %s", resp.status_code)
                    return None
                ctype = (resp.headers.get("content-type") or "").split(";")[0].strip().lower()
                if ctype not in ALLOWED_MIME:
                    log.info("图片类型不支持：%s", ctype or "(空)")
                    return None
                buf = bytearray()
                async for chunk in resp.aiter_bytes():
                    buf.extend(chunk)
                    if len(buf) > MAX_BYTES:
                        log.info("图片超过 %d 字节，忽略", MAX_BYTES)
                        return None
    except httpx.HTTPError as exc:
        log.info("图片下载出错：%s", exc)
        return None

    if not buf:
        return None
    data = bytes(buf)
    data, ctype = normalize_image(data, ctype)
    log.info("图片已准备：%s %d 字节", ctype, len(data))
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{ctype};base64,{encoded}"
