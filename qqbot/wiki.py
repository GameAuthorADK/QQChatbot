"""外部 wiki 查询：MediaWiki 搜索 + 摘要。

只访问配置里明确列出的站点（https），不跟随跨站跳转，
解析出的 IP 属于内网/回环/保留段时直接拒绝，避免 SSRF。
外部文本只做清洗和截断，不交给模型解释。
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import quote, urlparse

from .netguard import host_is_public

import httpx

log = logging.getLogger(__name__)

#: 站点声明为「浏览器」UA 是为了兼容部分站点的访问策略；
#: 请求频率由调用方的频率限制和缓存控制。
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

TIMEOUT = 6.0
MAX_SITES = 10
MAX_SUMMARY = 320
MAX_BODY = 400_000
CACHE_TTL = 12 * 3600

#: 名称|地址，按顺序尝试
DEFAULT_SITES = [
    "灰机wiki|https://www.huijiwiki.com",
    "萌娘百科|https://zh.moegirl.org.cn",
]


class WikiError(Exception):
    """可以直接展示给用户的错误。"""


_CJK_RE = re.compile(r"[\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff]")


def has_cjk(text: str) -> bool:
    return bool(_CJK_RE.search(text or ""))


def hit_aligned(query: str, hit: "WikiHit | None") -> bool:
    """中文关键词却返回了纯英文标题，说明多半没匹配上。"""
    if hit is None:
        return False
    if not has_cjk(query):
        return True
    return has_cjk(hit.title)


@dataclass(frozen=True)
class WikiSite:
    name: str
    base: str


@dataclass
class WikiHit:
    site: str
    title: str
    url: str
    summary: str = ""


@dataclass
class WikiResult:
    ok: bool
    hit: WikiHit | None = None
    others: list[WikiHit] = field(default_factory=list)
    error: str = ""
    notes: list[str] = field(default_factory=list)


# ── 配置 ──────────────────────────────────────────────
def parse_sites(raw) -> list[WikiSite]:
    """接受「名称|https://host」列表或多行文本，非法项直接忽略。"""
    if isinstance(raw, str):
        lines = raw.replace("\r", "\n").split("\n")
    elif isinstance(raw, (list, tuple)):
        lines = [str(x) for x in raw]
    else:
        lines = list(DEFAULT_SITES)

    sites: list[WikiSite] = []
    seen: set[str] = set()
    for line in lines:
        text = str(line).strip()
        if not text or text.startswith("#"):
            continue
        if "|" in text:
            name, url = text.split("|", 1)
        else:
            name, url = "", text
        name = name.strip()[:24]
        url = url.strip().rstrip("/")
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname:
            continue
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            continue
        if parsed.path not in ("", "/"):
            continue
        base = f"https://{parsed.hostname.lower()}"
        if parsed.port:
            base += f":{parsed.port}"
        if base in seen:
            continue
        seen.add(base)
        sites.append(WikiSite(name or parsed.hostname, base))
        if len(sites) >= MAX_SITES:
            break
    return sites


# ── 网页清洗 ──────────────────────────────────────────
_TAG_RE = re.compile(r"(?s)<[^>]+>")
_SCRIPT_RE = re.compile(r"(?is)<(script|style|noscript|sup)[^>]*>.*?</\1>")
_BREAK_RE = re.compile(r"(?i)<br\s*/?>|</p>|</div>|</li>|</h[1-6]>")
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CITE_RE = re.compile(r"\[\d+(?::\d+)?\]")


def strip_html(raw: str) -> str:
    text = _SCRIPT_RE.sub(" ", raw)
    text = _BREAK_RE.sub("\n", text)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = _CTRL_RE.sub("", text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t\u00a0]+", " ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def clean_summary(text: str, limit: int = MAX_SUMMARY) -> str:
    text = strip_html(text)
    text = _CITE_RE.sub("", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    if len(text) > limit:
        cut = text[:limit]
        end = max(cut.rfind("。"), cut.rfind("！"), cut.rfind("？"))
        if end >= limit // 2:
            cut = cut[: end + 1]
        else:
            cut = cut.rstrip("，、；：,;:") + "…"
        text = cut
    return text


# ── 网络 ──────────────────────────────────────────────
def _friendly(exc: Exception) -> str:
    if isinstance(exc, WikiError):
        return str(exc)
    if isinstance(exc, httpx.TimeoutException):
        return "超时"
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        if code in (401, 403):
            return "拒绝自动访问（站点开了防爬）"
        if code == 404:
            return "接口不存在"
        if code == 429:
            return "访问太频繁"
        return f"HTTP {code}"
    if isinstance(exc, httpx.HTTPError):
        return "连不上"
    return "出错"


async def _api(client: httpx.AsyncClient, site: WikiSite, params: dict) -> dict:
    params = {**params, "format": "json", "formatversion": 2}
    resp = await client.get(site.base + "/api.php", params=params)
    if resp.status_code != 200:
        raise WikiError(_friendly(
            httpx.HTTPStatusError("bad status", request=resp.request, response=resp)
        ))
    ctype = resp.headers.get("content-type", "")
    if "json" not in ctype and not resp.text.lstrip().startswith(("{", "[")):
        raise WikiError("接口返回了网页，可能被防爬拦截")
    if len(resp.content) > MAX_BODY:
        raise WikiError("返回内容过大")
    try:
        data = resp.json()
    except ValueError as exc:
        raise WikiError("返回格式异常") from exc
    if isinstance(data, dict) and data.get("error"):
        raise WikiError("站点不允许查询")
    return data


async def _search(
    client: httpx.AsyncClient, site: WikiSite, query: str
) -> list[tuple[str, str]]:
    data = await _api(
        client,
        site,
        {"action": "opensearch", "search": query, "limit": 3, "namespace": 0},
    )
    if not isinstance(data, list) or len(data) < 2:
        return []
    titles = [str(t) for t in (data[1] or []) if str(t).strip()]
    urls = data[3] if len(data) > 3 and isinstance(data[3], list) else []
    out: list[tuple[str, str]] = []
    for i, title in enumerate(titles):
        url = str(urls[i]) if i < len(urls) else ""
        if url and not url.startswith(site.base + "/"):
            url = ""
        out.append((title, url))
    return out


async def _extract(client: httpx.AsyncClient, site: WikiSite, title: str) -> str:
    try:
        data = await _api(
            client,
            site,
            {
                "action": "query",
                "prop": "extracts",
                "exintro": 1,
                "explaintext": 1,
                "redirects": 1,
                "titles": title,
            },
        )
        pages = (data.get("query") or {}).get("pages") or []
        if isinstance(pages, dict):  # 老格式
            pages = list(pages.values())
        for page in pages:
            text = str(page.get("extract") or "").strip()
            if text:
                return clean_summary(text)
    except WikiError:
        pass

    try:
        data = await _api(
            client,
            site,
            {"action": "parse", "page": title, "prop": "text", "section": 0},
        )
        raw = ((data.get("parse") or {}).get("text") or "")
        if isinstance(raw, dict):
            raw = raw.get("*") or ""
        return clean_summary(str(raw))
    except WikiError:
        return ""


async def _lookup_site(
    client: httpx.AsyncClient, site: WikiSite, query: str, cache
) -> WikiHit | None:
    host = urlparse(site.base).hostname or ""
    if not await asyncio.to_thread(host_is_public, host):
        raise WikiError("地址不可用（内网或无法解析）")

    found = await _search(client, site, query)
    if not found:
        return None
    title, url = found[0]
    url = url or f"{site.base}/wiki/{quote(title.replace(' ', '_'))}"

    key = f"{site.base}|{title}"
    text = _cache_get(cache, key)
    if text is None:
        text = await _extract(client, site, title)
        if text:
            _cache_put(cache, key, url, text)
    return WikiHit(site=site.name, title=title, url=url, summary=text or "")


def _cache_get(cache, key: str) -> str | None:
    if cache is None:
        return None
    try:
        return cache.wiki_cache_get(key)
    except Exception:  # 缓存坏了不影响查询
        return None


def _cache_put(cache, key: str, url: str, text: str) -> None:
    if cache is None:
        return
    try:
        cache.wiki_cache_put(key, url, text, CACHE_TTL)
    except Exception:
        pass


def cache_key(url: str) -> str:
    return hashlib.sha1(url.encode("utf-8")).hexdigest()


async def lookup(
    query: str, sites: list[WikiSite], cache=None, *, timeout: float = TIMEOUT
) -> WikiResult:
    query = re.sub(r"\s+", " ", (query or "")).strip()[:80]
    if not query:
        return WikiResult(False, error="用法：/wiki 关键词")
    if not sites:
        return WikiResult(False, error="还没有配置 wiki 站点")

    headers = {
        "User-Agent": UA,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }
    limits = httpx.Limits(max_connections=8, max_keepalive_connections=4)
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(timeout, connect=4.0),
        headers=headers,
        follow_redirects=False,
        limits=limits,
    ) as client:
        tasks = [_lookup_site(client, site, query, cache) for site in sites]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    hits: list[WikiHit] = []
    notes: list[str] = []
    for site, result in zip(sites, results):
        if isinstance(result, WikiHit):
            hits.append(result)
        elif isinstance(result, Exception):
            reason = _friendly(result)
            log.info("wiki 查询失败 site=%s reason=%s", site.base, reason)
            notes.append(f"{site.name}：{reason}")
        else:
            notes.append(f"{site.name}：没有对应条目")
    if not hits:
        detail = "；".join(notes[:3])
        return WikiResult(False, error=detail or "没找到相关条目", notes=notes)

    hits.sort(key=lambda h: 0 if h.summary else 1)
    return WikiResult(True, hit=hits[0], others=hits[1:], notes=notes)


def format_result(result: WikiResult) -> str:
    if not result.ok or result.hit is None:
        return f"没查到。{result.error}" if result.error else "没查到相关条目。"

    hit = result.hit
    lines = [f"📖 {hit.title} —— {hit.site}"]
    if hit.summary:
        lines.append(hit.summary)
    else:
        lines.append("（这个站点没给出摘要，点链接看原文）")
    lines.append(f"🔗 {hit.url}")
    others = [f"{h.site}「{h.title}」" for h in result.others[:2] if h.title]
    if others:
        lines.append("另见：" + "、".join(others))
    return "\n".join(lines)
