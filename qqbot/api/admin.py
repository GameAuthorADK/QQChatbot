"""本地管理 API（仅 127.0.0.1）。"""

from __future__ import annotations

import io
import json
import logging
import platform
import re
import secrets as pysecrets
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path, PurePosixPath

import asyncio

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

from ..app import Runtime
from .. import errors as _errors
from ..paths import (
    BASE,
    DATA_DIR,
    LOG_DIR,
    MINIGAMES_DIR,
    MODES_DIR,
    PLUGINS_DIR,
    PROFILES_DIR,
    RUNTIME_DIR,
    TRPG_DIR,
    instance_id,
)
from ..providers import presets
from ..games import GAME_TEMPLATE, parse_source as parse_game_source
from ..modes import MODE_TEMPLATE, parse_source as parse_mode_source
from ..rulepacks import RULE_TEMPLATE, PackError, load_py_source
from ..ui.page import INDEX_HTML

log = logging.getLogger(__name__)

#: 启动时生成，随窗口 URL 下发
SESSION_TOKEN = pysecrets.token_urlsafe(24)


def _host_ok(request: Request) -> bool:
    host = (request.headers.get("host") or "").lower()
    return host.startswith("127.0.0.1:") or host.startswith("localhost:")


def _bad_filename(name: str) -> bool:
    """上传文件名里不允许出现路径分隔符或 .."""
    text = str(name or "")
    return "/" in text or "\\" in text or ".." in text


def create_app(rt: Runtime) -> FastAPI:
    app = FastAPI(title="QQChatbot", docs_url=None, redoc_url=None, openapi_url=None)

    def guard(request: Request) -> None:
        if not _host_ok(request):
            raise HTTPException(status_code=403, detail="host rejected")
        token = request.headers.get("x-token") or request.query_params.get("t")
        if token != SESSION_TOKEN:
            raise HTTPException(status_code=403, detail="bad token")

    def bot_file_name() -> str:
        name = (rt.cfg.bot_name or "bot").strip()
        name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
        name = name.strip(" .")[:30]
        return name or "bot"

    @app.get("/", response_class=HTMLResponse)
    async def index() -> str:
        return INDEX_HTML

    @app.post("/api/window/show")
    async def window_show(request: Request):
        guard(request)
        from ..ui import window as window_api

        return {"ok": window_api.show_existing()}

    @app.get("/api/state")
    async def state(request: Request):
        guard(request)
        return rt.snapshot()

    @app.get("/api/help")
    async def help_docs(request: Request):
        guard(request)
        sources = [
            ("readme", "用户手册", BASE / "README.txt"),
            ("commands", "指令手册", BASE / "docs" / "commands.md"),
            ("operations", "部署与运维", BASE / "docs" / "operations.md"),
            ("troubleshooting", "常见问题", BASE / "docs" / "troubleshooting.md"),
            ("plugins", "插件编写", BASE / "docs" / "plugin-authoring.md"),
            ("changelog", "版本历史", BASE / "docs" / "changelog.md"),
        ]
        docs = []
        for doc_id, title, path in sources:
            try:
                text = path.read_text("utf-8-sig")
            except Exception:
                text = f"找不到文档：{path.name}"
            docs.append({"id": doc_id, "title": title, "text": text})
        return {
            "version": __import__("qqbot").__version__,
            "docs": docs,
        }

    @app.post("/api/config")
    async def set_config(request: Request):
        guard(request)
        body = await request.json()
        app_id = str(body.get("app_id", "")).strip()
        app_secret = str(body.get("app_secret", "")).strip()
        if not app_id:
            raise HTTPException(status_code=400, detail="app_id 不能为空")
        if not app_secret and not rt.app_secret:
            raise HTTPException(status_code=400, detail="首次配置必须填写 app_secret")
        await rt.disconnect()
        rt.apply_credentials(app_id, app_secret)
        await rt.connect()
        return {"ok": True}

    @app.post("/api/connect")
    async def connect(request: Request):
        guard(request)
        await rt.connect()
        return {"ok": True}

    @app.post("/api/disconnect")
    async def disconnect(request: Request):
        guard(request)
        await rt.disconnect()
        return {"ok": True}

    @app.post("/api/pause")
    async def pause(request: Request):
        guard(request)
        body = await request.json()
        rt.paused = bool(body.get("paused"))
        rt.store.audit("runtime.pause", actor="admin", paused=rt.paused)
        return {"ok": True, "paused": rt.paused}

    @app.post("/api/groups/{group_openid}/mode")
    async def set_group_mode(group_openid: str, request: Request):
        guard(request)
        body = await request.json()
        mode = str(body.get("mode") or "chat")
        if mode not in rt.modes:
            raise HTTPException(status_code=400, detail="非法的模式")
        try:
            return await rt.apply_group_mode(group_openid, mode)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/groups/{group_openid}/status")
    async def set_group_status(group_openid: str, request: Request):
        guard(request)
        body = await request.json()
        status = str(body.get("status", ""))
        if status not in {"active", "pending", "disabled", "removed"}:
            raise HTTPException(status_code=400, detail="非法的群状态")
        rt.store.set_group_status(group_openid, status)
        rt.store.audit("group.status", target=group_openid, actor="admin", status=status)
        return {"ok": True, "status": status}

    @app.post("/api/groups/{group_openid}/listen")
    async def set_group_listen(group_openid: str, request: Request):
        guard(request)
        body = await request.json()
        enabled = bool(body.get("enabled"))
        rt.store.set_group_listen(group_openid, enabled)
        rt.store.audit(
            "group.listen", target=group_openid, actor="admin", enabled=enabled
        )
        return {"ok": True, "listen_enabled": enabled}

    @app.post("/api/groups/{group_openid}/members")
    async def set_group_members(group_openid: str, request: Request):
        guard(request)
        body = await request.json()
        try:
            count = int(body.get("count") or 0)
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="人数必须是数字") from None
        rt.store.set_group_member_count(group_openid, count)
        rt.store.audit(
            "group.members", target=group_openid, actor="admin", count=count
        )
        return {"ok": True, "member_count": rt.store.group_member_count(group_openid)}

    @app.get("/api/groups/{group_openid}/reply")
    async def get_group_reply(group_openid: str, request: Request):
        guard(request)
        return {
            "group": group_openid,
            "overrides": rt.store.get_group_reply(group_openid),
            "effective": vars(rt.reply_settings(group_openid)),
            "listen_enabled": rt.store.group_listen(group_openid),
        }

    @app.post("/api/groups/{group_openid}/reply")
    async def set_group_reply(group_openid: str, request: Request):
        guard(request)
        body = await request.json()
        data = rt.apply_group_reply(group_openid, body)
        rt.store.audit(
            "group.reply",
            target=group_openid,
            actor="admin",
            keys=sorted(body.keys()),
        )
        return {"ok": True, **data}

    @app.delete("/api/groups/{group_openid}/reply")
    async def reset_group_reply(group_openid: str, request: Request):
        guard(request)
        rt.store.clear_group_reply(group_openid)
        rt.store.audit("group.reply.reset", target=group_openid, actor="admin")
        return {
            "ok": True,
            "effective": vars(rt.reply_settings(group_openid)),
        }

    @app.get("/api/groups/{group_openid}/reply/export")
    async def export_group_reply(group_openid: str, request: Request):
        guard(request)
        doc = {
            "format": "qqchatbot-group-reply",
            "version": 1,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "group": group_openid,
            "overrides": rt.store.get_group_reply(group_openid),
            "effective": vars(rt.reply_settings(group_openid)),
            "listen_enabled": rt.store.group_listen(group_openid),
        }
        out_dir = RUNTIME_DIR / "reply"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe = group_openid[-8:] or "group"
        out = out_dir / f"reply-{safe}-{time.strftime('%Y%m%d-%H%M%S')}.json"
        out.write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        rt.store.audit("group.reply.export", target=out.name, actor="admin")
        return {"ok": True, "path": str(out), "data": doc}

    @app.post("/api/groups/{group_openid}/reply/import")
    async def import_group_reply(group_openid: str, request: Request):
        guard(request)
        body = await request.json()
        payload = body.get("data") if isinstance(body.get("data"), dict) else body
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="文件内容不是对象")
        overrides = payload.get("overrides")
        if not isinstance(overrides, dict):
            overrides = payload.get("effective")
        if not isinstance(overrides, dict):
            overrides = payload
        if "listen_enabled" in payload:
            overrides = dict(overrides)
            overrides["listen_enabled"] = payload["listen_enabled"]
        data = rt.apply_group_reply(group_openid, overrides)
        rt.store.audit("group.reply.import", target=group_openid, actor="admin")
        return {"ok": True, **data}

    @app.get("/api/provider/presets")
    async def provider_presets(request: Request):
        guard(request)
        return {"presets": presets.as_list()}

    @app.post("/api/provider")
    async def set_provider(request: Request):
        guard(request)
        body = await request.json()
        await rt.apply_provider(body)
        return {"ok": True, "ready": rt.provider is not None}

    @app.post("/api/provider/test")
    async def test_provider(request: Request):
        guard(request)
        if rt.provider is None:
            raise HTTPException(status_code=400, detail="模型未就绪，请先保存配置")
        try:
            result = await asyncio.wait_for(rt.provider.probe(), timeout=30)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="探测超时")
        return {"ok": result.ok, "detail": result.detail, "latency_ms": result.latency_ms}

    @app.post("/api/chat/preview")
    async def chat_preview(request: Request):
        guard(request)
        body = await request.json()
        text = str(body.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="内容不能为空")
        return await rt.chat_preview(text, str(body.get("group") or "__preview__"))

    @app.post("/api/chat/preview/reset")
    async def chat_preview_reset(request: Request):
        guard(request)
        rt.reset_preview()
        return {"ok": True}

    @app.post("/api/provider/models")
    async def provider_models(request: Request):
        guard(request)
        body = await request.json()
        from ..providers.openai_compat import fetch_models

        preset = presets.get(rt.cfg.provider)
        base = (
            str(body.get("base_url") or "").strip()
            or rt.cfg.base_url
            or (preset.base_url if preset else "")
        )
        if not base:
            raise HTTPException(status_code=400, detail="请先选择服务或填写 Base URL")
        key = str(body.get("api_key") or "").strip() or rt._key_for(rt.cfg.provider)
        if not key:
            raise HTTPException(status_code=400, detail="请先填写 API Key")

        try:
            models = await asyncio.wait_for(fetch_models(base, key), timeout=25)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="拉取超时")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        return {"ok": True, "models": models, "count": len(models)}

    @app.post("/api/provider/test_vision")
    async def test_vision(request: Request):
        guard(request)
        if rt.provider is None:
            raise HTTPException(status_code=400, detail="模型还没配置")
        if getattr(rt.provider, "id", "") == "mock":
            return {"ok": False, "detail": "当前是假模型，无法测试图片理解"}

        from ..images import TEST_PNG_B64
        from ..providers import ChatMessage

        messages = [
            ChatMessage(
                "user",
                [
                    {"type": "text", "text": "这张图片主要是什么颜色？只回答一个词。"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64," + TEST_PNG_B64
                        },
                    },
                ],
            )
        ]
        started = time.time()
        try:
            comp = await rt.provider.complete(messages, timeout=45, max_tokens=64)
        except Exception as exc:
            latency = int((time.time() - started) * 1000)
            logging.getLogger(__name__).info(
                "看图测试失败 %s: %s", type(exc).__name__, exc
            )
            return {
                "ok": False,
                "detail": f"{type(exc).__name__}: {str(exc)[:180]}",
                "latency_ms": latency,
            }
        latency = int((time.time() - started) * 1000)
        text = (comp.text or "").strip()[:100]
        return {
            "ok": True,
            "detail": text or "(模型没有返回内容)",
            "latency_ms": latency,
        }

    @app.get("/api/settings/defaults")
    async def settings_defaults(request: Request):
        guard(request)
        from ..config import DEFAULTS

        return {"defaults": DEFAULTS}

    @app.get("/api/persona/export")
    async def export_persona(request: Request):
        guard(request)
        import json as _json

        doc = {
            "format": "qqchatbot-persona",
            "version": 1,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "bot_name": rt.cfg.bot_name,
            "persona": rt.cfg.persona,
            "negative_prompt": rt.cfg.negative_prompt,
            "style_prompt": rt.cfg.style_prompt,
            "persona_anchor": rt.cfg.persona_anchor,
        }
        out_dir = RUNTIME_DIR / "prompts"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"persona-{bot_file_name()}.json"
        doc["file"] = out.name
        out.write_text(_json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        rt.store.audit("persona.export", target=out.name, actor="admin")
        return {"ok": True, "path": str(out), "data": doc}

    @app.get("/api/memory")
    async def get_memory(request: Request):
        guard(request)
        from ..prompts import compose
        from ..textutil import estimate_tokens

        fixed = estimate_tokens(compose(rt.cfg))
        total = int(rt.cfg.summary_trigger_tokens)
        from ..prompts import SAFETY_PROMPT, STYLE_RULES

        return {
            "auto_summary": rt.cfg.auto_summary,
            "trigger_tokens": total,
            "builtin_tokens": estimate_tokens(SAFETY_PROMPT + STYLE_RULES),
            "fixed_tokens": fixed,
            "content_budget": max(500, total - fixed),
            "items": rt.store.list_summaries(),
        }

    @app.get("/api/memory/page")
    async def get_memory_page(request: Request, page: int = 1, size: int = 10):
        guard(request)
        items, total = rt.store.list_summaries_page(page, size)
        pages = max(1, (total + max(1, min(50, size)) - 1) // max(1, min(50, size)))
        return {
            "items": items,
            "total": total,
            "page": min(max(1, page), pages),
            "pages": pages,
        }

    @app.post("/api/memory/item")
    async def set_memory_item(request: Request):
        guard(request)
        body = await request.json()
        group = str(body.get("group") or "")
        member = str(body.get("member") or "")
        mode = str(body.get("mode") or "chat")[:24]
        summary = str(body.get("summary") or "").strip()
        if not group or not member:
            raise HTTPException(status_code=400, detail="缺少群或成员标识")
        if not summary:
            raise HTTPException(status_code=400, detail="内容不能为空")
        rt.store.save_memory_state(group, member, summary[:1500], [], mode=mode)
        rt.store.audit(
            "memory.item.update",
            target=f"{group[-6:]}/{member[-6:]}/{mode}",
            actor="admin",
        )
        return {"ok": True}

    @app.post("/api/memory/item/delete")
    async def delete_memory_item(request: Request):
        guard(request)
        body = await request.json()
        group = str(body.get("group") or "")
        member = str(body.get("member") or "")
        mode = str(body.get("mode") or "chat")[:24]
        if not group or not member:
            raise HTTPException(status_code=400, detail="缺少群或成员标识")
        rt.store.save_memory_state(group, member, "", [], mode=mode)
        rt.store.audit(
            "memory.item.delete",
            target=f"{group[-6:]}/{member[-6:]}/{mode}",
            actor="admin",
        )
        return {"ok": True}

    PROMPT_FIELDS = {
        "repeat": ("repeat_prompt", 2000),
        "proactive": ("proactive_prompt", 1000),
        "persona_anchor": ("persona_anchor", 1000),
    }

    @app.get("/api/prompts/{key}/export")
    async def export_prompt(key: str, request: Request):
        guard(request)
        import json as _json

        field = PROMPT_FIELDS.get(key)
        if field is None:
            raise HTTPException(status_code=404, detail="未知提示词")
        field, limit = field
        out_dir = RUNTIME_DIR / "prompts"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{key}-{bot_file_name()}.json"
        doc = {
            "format": "qqchatbot-prompt",
            "version": 1,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "key": field,
            "text": getattr(rt.cfg, field, ""),
            "file": out.name,
        }
        out.write_text(_json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        rt.store.audit("prompt.export", target=out.name, actor="admin")
        return {"ok": True, "path": str(out), "data": doc}

    @app.post("/api/prompts/{key}/import")
    async def import_prompt(key: str, request: Request):
        guard(request)
        field = PROMPT_FIELDS.get(key)
        if field is None:
            raise HTTPException(status_code=404, detail="未知提示词")
        field, limit = field
        body = await request.json()
        payload = body.get("data") if isinstance(body.get("data"), dict) else body
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="文件内容不是对象")
        if payload.get("key") and payload.get("key") != field:
            raise HTTPException(status_code=400, detail="提示词类型不匹配")
        text = str(payload.get("text") or payload.get("value") or "").strip()[:limit]
        setattr(rt.cfg, field, text)
        from .. import config as _config
        _config.save(rt.cfg)
        rt.store.audit("prompt.import", target=key, actor="admin", length=len(text))
        return {"ok": True, "key": field, "text": text}

    @app.get("/api/groups/{group_openid}/prompts/proactive/export")
    async def export_group_proactive_prompt(group_openid: str, request: Request):
        guard(request)
        import json as _json

        rs = rt.reply_settings(group_openid)
        overrides = rt.store.get_group_reply(group_openid)
        doc = {
            "format": "qqchatbot-prompt",
            "version": 1,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "key": "proactive_prompt",
            "group": group_openid,
            "text": str(getattr(rs, "proactive_prompt", "") or ""),
            "overridden": "proactive_prompt" in overrides,
        }
        out_dir = RUNTIME_DIR / "prompts"
        out_dir.mkdir(parents=True, exist_ok=True)
        safe = group_openid[-8:] or "group"
        out = out_dir / f"proactive-{bot_file_name()}-{safe}.json"
        doc["file"] = out.name
        out.write_text(_json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        rt.store.audit(
            "group.prompt.export",
            target=out.name,
            actor="admin",
            group=group_openid[-8:],
        )
        return {"ok": True, "path": str(out), "data": doc}

    @app.post("/api/groups/{group_openid}/prompts/proactive/import")
    async def import_group_proactive_prompt(group_openid: str, request: Request):
        guard(request)
        body = await request.json()
        payload = body.get("data") if isinstance(body.get("data"), dict) else body
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="文件内容不是对象")
        if payload.get("key") and payload.get("key") != "proactive_prompt":
            raise HTTPException(status_code=400, detail="提示词类型不匹配")
        text = str(payload.get("text") or payload.get("value") or "").strip()[:1000]
        if not text or text == str(rt.cfg.proactive_prompt or ""):
            rt.apply_group_reply(group_openid, {"clear": ["proactive_prompt"]})
        else:
            rt.apply_group_reply(group_openid, {"proactive_prompt": text})
        rt.store.audit(
            "group.prompt.import",
            target="proactive_prompt",
            actor="admin",
            group=group_openid[-8:],
            length=len(text),
        )
        return {
            "ok": True,
            "key": "proactive_prompt",
            "text": text,
            "effective": vars(rt.reply_settings(group_openid)),
        }

    @app.get("/api/persona/reports/page")
    async def get_persona_reports_page(
        request: Request, page: int = 1, size: int = 10
    ):
        guard(request)
        items, total = rt.persona_mem().reports_page(page, size)
        size = max(1, min(50, size))
        pages = max(1, (total + size - 1) // size)
        return {
            "items": items,
            "total": total,
            "page": min(max(1, page), pages),
            "pages": pages,
        }

    @app.get("/api/persona/reports/export")
    async def export_persona_reports(request: Request):
        guard(request)
        import json as _json

        doc = {
            "format": "qqchatbot-persona-reports",
            "version": 1,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "reports": rt.persona_mem().reports(200),
        }
        out_dir = RUNTIME_DIR / "memory"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"persona-reports-{time.strftime('%Y%m%d-%H%M%S')}.json"
        out.write_text(_json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        rt.store.audit("persona.reports.export", target=out.name, actor="admin")
        return {"ok": True, "path": str(out), "data": doc}

    @app.post("/api/persona/reports/import")
    async def import_persona_reports(request: Request):
        guard(request)
        body = await request.json()
        payload = body.get("data") if isinstance(body.get("data"), dict) else body
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="文件内容不是对象")
        if payload.get("format") not in (None, "qqchatbot-persona-reports"):
            raise HTTPException(status_code=400, detail="这不是自检报告文件")
        mode = str(body.get("mode") or "merge").lower()
        replace = mode == "replace"
        added = rt.persona_mem().restore(
            payload.get("reports") or [], replace=replace
        )
        rt.store.audit(
            "persona.reports.import",
            actor="admin",
            mode="replace" if replace else "merge",
            added=added,
        )
        return {
            "ok": True,
            "mode": "replace" if replace else "merge",
            "added": added,
            "reports": len(rt.persona_mem().reports(200)),
        }

    @app.post("/api/persona/check")
    async def run_persona_check(request: Request):
        guard(request)
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        result = await rt.persona_check_now(
            str(body.get("group") or "").strip(),
            str(body.get("member") or "").strip(),
            str(body.get("mode") or "").strip(),
        )
        rt.store.audit(
            "persona.check",
            actor="admin",
            status=result.get("status") or "error",
            group=str(result.get("group") or "")[-8:],
        )
        return result

    @app.post("/api/persona/reports/item")
    async def update_persona_report(request: Request):
        guard(request)
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="内容不是对象")
        report_id = str(body.get("id") or "").strip()
        if not report_id:
            raise HTTPException(status_code=400, detail="缺少报告标识")
        report = rt.persona_mem().update_report(
            report_id,
            str(body.get("note") or ""),
        )
        if report is None:
            raise HTTPException(status_code=404, detail="没有找到这条自检报告")
        rt.store.audit(
            "persona.report.update",
            actor="admin",
            group=str(report.get("group") or "")[-8:],
            weight=report.get("weight"),
        )
        return {
            "ok": True,
            "report": report,
            "reports": rt.persona_mem().reports(200),
        }

    @app.post("/api/persona/reports/item/delete")
    async def delete_persona_report(request: Request):
        guard(request)
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="内容不是对象")
        report_id = str(body.get("id") or "").strip()
        if not report_id:
            raise HTTPException(status_code=400, detail="缺少报告标识")
        removed = rt.persona_mem().delete_report(report_id)
        if not removed:
            raise HTTPException(status_code=404, detail="没有找到这条自检报告")
        rt.store.audit(
            "persona.report.delete",
            actor="admin",
            report=report_id[:12],
        )
        return {
            "ok": True,
            "reports": rt.persona_mem().reports(200),
        }

    @app.post("/api/persona/reports/clear")
    async def clear_persona_reports(request: Request):
        guard(request)
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="内容不是对象")
        group = str(body.get("group") or "").strip()
        if not group:
            raise HTTPException(status_code=400, detail="缺少群标识")
        removed = rt.persona_mem().clear_group(group)
        rt.store.audit(
            "persona.report.clear",
            actor="admin",
            group=group[-8:],
            removed=removed,
        )
        return {
            "ok": True,
            "removed": removed,
            "reports": rt.persona_mem().reports(200),
        }

    @app.get("/api/reply/export")
    async def export_default_reply(request: Request):
        guard(request)
        import json as _json

        doc = {
            "format": "qqchatbot-reply-default",
            "version": 1,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "effective": vars(rt.reply_settings("__default__")),
            "listen_enabled": rt.cfg.listen_enabled,
        }
        out_dir = RUNTIME_DIR / "reply"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"reply-default-{time.strftime('%Y%m%d-%H%M%S')}.json"
        out.write_text(_json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        rt.store.audit("reply.default.export", target=out.name, actor="admin")
        return {"ok": True, "path": str(out), "data": doc}

    @app.post("/api/reply/import")
    async def import_default_reply(request: Request):
        guard(request)
        body = await request.json()
        payload = body.get("data") if isinstance(body.get("data"), dict) else body
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="文件内容不是对象")
        effective = payload.get("effective")
        if not isinstance(effective, dict):
            effective = payload
        if "listen_enabled" in payload:
            effective = dict(effective)
            effective["listen_enabled"] = payload["listen_enabled"]
        await rt.apply_reply(effective)
        await rt.apply_settings(effective)
        rt.store.audit("reply.default.import", actor="admin")
        return {
            "ok": True,
            "effective": vars(rt.reply_settings("__default__")),
        }

    @app.get("/api/keywords/export")
    async def export_keywords(request: Request):
        guard(request)
        import json as _json

        doc = {
            "format": "qqchatbot-keywords",
            "version": 1,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "rules": rt.cfg.keyword_rules,
        }
        out_dir = RUNTIME_DIR / "keywords"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"keywords-{time.strftime('%Y%m%d-%H%M%S')}.json"
        out.write_text(_json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        rt.store.audit("keywords.export", target=out.name, actor="admin")
        return {"ok": True, "path": str(out), "data": doc}

    @app.post("/api/keywords/import")
    async def import_keywords(request: Request):
        guard(request)
        body = await request.json()
        payload = body.get("data") if isinstance(body.get("data"), dict) else body
        if isinstance(payload, list):
            rules = payload
        elif isinstance(payload, dict):
            if payload.get("format") not in (None, "qqchatbot-keywords"):
                raise HTTPException(status_code=400, detail="这不是关键词文件")
            rules = payload.get("rules") or []
        else:
            raise HTTPException(status_code=400, detail="文件内容不是对象")
        if not isinstance(rules, list):
            raise HTTPException(status_code=400, detail="关键词列表格式不正确")
        result = await rt.apply_rules({"rules": rules})
        rt.store.audit("keywords.import", actor="admin", count=len(result.get("rules", [])))
        return {"ok": True, **result}

    @app.get("/api/memory/export")
    async def export_memory(request: Request):
        guard(request)
        import json as _json

        doc = {
            "format": "qqchatbot-memory",
            "version": 1,
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "auto_summary": rt.cfg.auto_summary,
            "trigger_tokens": rt.cfg.summary_trigger_tokens,
            "items": rt.store.list_summaries(),
        }
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        out_dir = RUNTIME_DIR / "memory"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"memory-{time.strftime('%Y%m%d-%H%M%S')}.json"
        out.write_text(_json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        rt.store.audit("memory.export", target=out.name, actor="admin")
        return {"ok": True, "path": str(out), "data": doc}

    @app.post("/api/memory")
    async def set_memory(request: Request):
        guard(request)
        body = await request.json()
        return await rt.apply_memory(body)

    @app.post("/api/memory/summarize")
    async def summarize_memory(request: Request):
        guard(request)
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        try:
            limit = int(body.get("limit") or 3)
        except (TypeError, ValueError):
            limit = 3
        limit = max(1, min(10, limit))
        if rt.provider is None:
            raise HTTPException(status_code=400, detail="模型未就绪")
        result = await rt.summarize_pending(limit)
        return {"ok": True, **result}

    @app.post("/api/memory/import")
    async def import_memory(request: Request):
        guard(request)
        body = await request.json()
        payload = body.get("data") if isinstance(body.get("data"), dict) else body
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="文件内容不是对象")
        if payload.get("format") not in (None, "qqchatbot-memory"):
            raise HTTPException(status_code=400, detail="这不是记忆文件")
        if "persona" in payload or "bot_name" in payload:
            raise HTTPException(status_code=400, detail="记忆文件不应包含人设字段")

        await rt.apply_memory(
            {
                "auto_summary": payload.get("auto_summary", rt.cfg.auto_summary),
                "trigger_tokens": payload.get("trigger_tokens", rt.cfg.summary_trigger_tokens),
            }
        )
        restored = 0
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            g, m, s = item.get("group"), item.get("member"), item.get("summary")
            mode = str(item.get("mode") or "chat")[:24]
            if g and m and s:
                rt.store.save_memory_state(g, m, str(s), [], mode=mode)
                restored += 1
        rt.store.audit("memory.import", actor="admin", restored=restored)
        return {"ok": True, "restored": restored}

    @app.post("/api/persona/import")
    async def import_persona(request: Request):
        guard(request)
        body = await request.json()
        payload = body.get("data") if isinstance(body.get("data"), dict) else body
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="文件内容不是对象")
        if "safety" in payload:
            raise HTTPException(status_code=400, detail="人设文件不应包含安全规则")
        allowed = {
            "bot_name",
            "persona",
            "negative_prompt",
            "style_prompt",
            "persona_anchor",
        }
        data = {k: payload.get(k) for k in allowed if k in payload}
        if not data:
            raise HTTPException(status_code=400, detail="没有可导入的字段")
        return await rt.apply_persona(data)

    @app.post("/api/packs/reload")
    async def reload_packs(request: Request):
        guard(request)
        rt.load_packs()
        rt.store.audit("packs.reload", actor="admin", count=len(rt.packs))
        return {
            "ok": True,
            "packs": [
                {
                    "id": p.id,
                    "name": p.name,
                    "fields": len(p.fields),
                    "checks": len(p.checks),
                    "version": p.version,
                }
                for p in rt.packs
            ],
            "pack_errors": rt.pack_errors,
        }

    @app.post("/api/rulepacks/{pack_id}/enable")
    async def toggle_rulepack(pack_id: str, request: Request):
        guard(request)
        body = await request.json()
        enabled = bool(body.get("enabled"))

        pack = next((p for p in rt.all_packs if p.id == pack_id), None)
        if pack is None:
            raise HTTPException(status_code=404, detail="没有这个规则")
        if (
            not enabled
            and any(p.id == pack_id for p in rt.packs)
            and len(rt.packs) <= 1
        ):
            raise HTTPException(
                status_code=400, detail="至少要保留一个启用的跑团规则"
            )

        rt.store.set_rulepack_enabled(pack_id, enabled)
        rt.load_packs()
        rt.store.audit(
            "rulepack.enable", target=pack_id, actor="admin", enabled=enabled
        )
        return {
            "ok": True,
            "id": pack_id,
            "enabled": enabled,
            "pack_errors": rt.pack_errors,
        }

    @app.post("/api/rulepacks/{pack_id}/hooks")
    async def toggle_rule_hooks(pack_id: str, request: Request):
        guard(request)
        body = await request.json()
        enabled = bool(body.get("enabled"))

        pack = next((p for p in rt.packs if p.id == pack_id), None)
        if pack is None:
            raise HTTPException(status_code=404, detail="没有这个规则")
        if enabled and not pack.hooks:
            raise HTTPException(status_code=400, detail="这个规则没有声明 hook")

        rt.store.set_rule_hook_enabled(pack_id, enabled, pack.file_hash)
        rt.load_packs()
        rt.store.audit(
            "rulepack.hooks", target=pack_id, actor="admin", enabled=enabled
        )
        return {
            "ok": True,
            "id": pack_id,
            "hooks_active": pack_id in rt.active_rule_hooks,
            "pack_errors": rt.pack_errors,
        }

    @app.get("/api/modes")
    async def list_modes(request: Request):
        guard(request)
        return {"modes": rt.modes_snapshot(), "errors": rt.mode_errors}

    @app.post("/api/modes/scan")
    async def scan_modes(request: Request):
        guard(request)
        rt.reload_modes()
        rt.store.audit("mode.scan", actor="admin", count=len(rt.modes))
        return {
            "ok": True,
            "modes": rt.modes_snapshot(),
            "errors": rt.mode_errors,
        }

    @app.get("/api/modes/template")
    async def mode_template(request: Request):
        guard(request)
        return Response(
            content=MODE_TEMPLATE,
            media_type="text/x-python; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="mode_template.py"'
            },
        )

    @app.get("/api/modes/{mode_id}/export")
    async def mode_export(mode_id: str, request: Request):
        guard(request)
        spec = rt.modes.get(mode_id)
        if spec is None or spec.source != "plugin" or not spec.path:
            raise HTTPException(status_code=404, detail="没有这个自定义模式文件")
        if not spec.path.exists():
            raise HTTPException(status_code=404, detail="模式文件不存在")
        return Response(
            content=spec.path.read_text("utf-8"),
            media_type="text/x-python; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{spec.id}.py"'
            },
        )

    @app.post("/api/modes/import")
    async def mode_import(request: Request):
        guard(request)
        body = await request.json()
        source = str(body.get("source") or "")
        filename = str(body.get("filename") or "mymode.py")
        if _bad_filename(filename):
            raise HTTPException(status_code=400, detail="文件名不能包含路径")
        overwrite = bool(body.get("overwrite"))

        if len(source.encode("utf-8")) > 256 * 1024:
            raise HTTPException(status_code=400, detail="文件过大（上限 256 KB）")

        stem = Path(filename).stem
        mode_id = "".join(
            c for c in stem if c.isascii() and (c.isalnum() or c in "_-")
        )[:24].lower()
        if not mode_id:
            raise HTTPException(
                status_code=400,
                detail="文件名只能包含字母、数字、下划线和短横线，例如 translate.py",
            )

        target = MODES_DIR / f"{mode_id}.py"
        if target.exists() and not overwrite:
            raise HTTPException(
                status_code=409, detail=f"模式 {mode_id} 已存在，请确认后再覆盖"
            )

        spec = parse_mode_source(source, mode_id)
        if spec.error:
            raise HTTPException(status_code=400, detail=spec.error)

        MODES_DIR.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        rt.reload_modes()
        rt.store.audit("mode.import", target=mode_id, actor="admin")
        return {
            "ok": True,
            "id": mode_id,
            "label": spec.label,
            "call_llm": spec.call_llm,
            "allow_keyword": spec.allow_keyword,
            "modes": rt.modes_snapshot(),
            "errors": rt.mode_errors,
        }

    @app.get("/api/minigames")
    async def list_minigames(request: Request):
        guard(request)
        return {"games": rt.games_snapshot(), "errors": rt.game_errors}

    @app.post("/api/minigames/scan")
    async def scan_minigames(request: Request):
        guard(request)
        rt.reload_games()
        rt.store.audit("game.scan", actor="admin", count=len(rt.games))
        return {"ok": True, "games": rt.games_snapshot(), "errors": rt.game_errors}

    @app.post("/api/minigames/{game_id}/enable")
    async def toggle_minigame(game_id: str, request: Request):
        guard(request)
        body = await request.json()
        enabled = bool(body.get("enabled"))

        info = rt.games.get(game_id)
        if info is None:
            rt.reload_games()
            info = rt.games.get(game_id)
        if info is None:
            raise HTTPException(status_code=404, detail="没有这个游戏")
        if enabled and info.error:
            raise HTTPException(
                status_code=400, detail=f"游戏有问题，无法启用：{info.error}"
            )

        rt.store.set_game_enabled(game_id, enabled, info.file_hash)
        rt.reload_games()
        rt.store.audit("game.toggle", target=game_id, actor="admin", enabled=enabled)
        return {"ok": True, "games": rt.games_snapshot(), "errors": rt.game_errors}

    @app.get("/api/minigames/template")
    async def minigame_template(request: Request):
        guard(request)
        return Response(
            content=GAME_TEMPLATE,
            media_type="text/x-python; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="game_template.py"'
            },
        )

    @app.get("/api/minigames/{game_id}/export")
    async def minigame_export(game_id: str, request: Request):
        guard(request)
        info = rt.games.get(game_id)
        if info is None or not info.path or not info.path.exists():
            raise HTTPException(status_code=404, detail="没有这个游戏文件")
        return Response(
            content=info.path.read_text("utf-8"),
            media_type="text/x-python; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{info.id}.py"'
            },
        )

    @app.post("/api/minigames/import")
    async def minigame_import(request: Request):
        guard(request)
        body = await request.json()
        source = str(body.get("source") or "")
        filename = str(body.get("filename") or "mygame.py")
        if _bad_filename(filename):
            raise HTTPException(status_code=400, detail="文件名不能包含路径")
        overwrite = bool(body.get("overwrite"))

        if len(source.encode("utf-8")) > 512 * 1024:
            raise HTTPException(status_code=400, detail="文件过大（上限 512 KB）")

        stem = Path(filename).stem
        game_id = "".join(
            c for c in stem if c.isascii() and (c.isalnum() or c in "_-")
        )[:40]
        if not game_id:
            raise HTTPException(
                status_code=400,
                detail="文件名只能包含字母、数字、下划线和短横线，例如 mygame.py",
            )

        target = MINIGAMES_DIR / f"{game_id}.py"
        if target.exists() and not overwrite:
            raise HTTPException(
                status_code=409, detail=f"游戏 {game_id} 已存在，请确认后再覆盖"
            )

        info = parse_game_source(source, game_id)
        if info.error:
            raise HTTPException(status_code=400, detail=info.error)

        MINIGAMES_DIR.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        rt.reload_games()
        rt.store.audit("game.import", target=game_id, actor="admin")
        return {
            "ok": True,
            "id": game_id,
            "name": info.name,
            "commands": sorted(info.commands),
            "games": rt.games_snapshot(),
            "errors": rt.game_errors,
        }

    @app.get("/api/rulepacks/template")
    async def rulepack_template(request: Request):
        guard(request)
        return Response(
            content=RULE_TEMPLATE,
            media_type="text/x-python; charset=utf-8",
            headers={
                "Content-Disposition": 'attachment; filename="rule_template.py"'
            },
        )

    @app.get("/api/rulepacks/{pack_id}/export")
    async def rulepack_export(pack_id: str, request: Request):
        guard(request)
        pack = next((p for p in rt.packs if p.id == pack_id), None)
        if pack is None:
            raise HTTPException(status_code=404, detail="没有这个规则包")
        if pack.source != "py" or not pack.path or not pack.path.exists():
            raise HTTPException(
                status_code=400,
                detail="只有单文件 .py 规则可以导出；旧的 YAML 包请直接编辑文件夹",
            )
        return Response(
            content=pack.path.read_text("utf-8"),
            media_type="text/x-python; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{pack.id}.py"'
            },
        )

    @app.post("/api/rulepacks/import")
    async def rulepack_import(request: Request):
        guard(request)
        body = await request.json()
        source = str(body.get("source") or "")
        filename = str(body.get("filename") or "myrule.py")
        if _bad_filename(filename):
            raise HTTPException(status_code=400, detail="文件名不能包含路径")
        overwrite = bool(body.get("overwrite"))

        if len(source.encode("utf-8")) > 512 * 1024:
            raise HTTPException(status_code=400, detail="文件过大（上限 512 KB）")

        stem = Path(filename).stem
        pack_id = "".join(
            c for c in stem if c.isascii() and (c.isalnum() or c in "_-")
        )[:40]
        if not pack_id:
            raise HTTPException(
                status_code=400,
                detail="文件名只能包含字母、数字、下划线和短横线，例如 myrule.py",
            )

        target = TRPG_DIR / f"{pack_id}.py"
        if target.exists() and not overwrite:
            raise HTTPException(
                status_code=409, detail=f"规则 {pack_id} 已存在，请确认后再覆盖"
            )

        try:
            pack = load_py_source(source, pack_id)
        except PackError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        TRPG_DIR.mkdir(parents=True, exist_ok=True)
        target.write_text(source, encoding="utf-8")
        rt.load_packs()
        rt.store.audit("rulepack.import", target=pack_id, actor="admin")

        return {
            "ok": True,
            "id": pack_id,
            "name": pack.name,
            "fields": len(pack.fields),
            "checks": len(pack.checks),
            "packs": [
                {"id": p.id, "name": p.name, "fields": len(p.fields)} for p in rt.packs
            ],
            "pack_errors": rt.pack_errors,
        }

    @app.get("/api/code-plugins")
    async def list_code_plugins(request: Request):
        guard(request)
        return {
            "plugins": rt.code_plugins_snapshot(),
            "errors": rt.code_plugin_errors,
        }

    @app.post("/api/code-plugins/scan")
    async def scan_code_plugins(request: Request):
        guard(request)
        rt.reload_code_plugins()
        rt.store.audit("plugin.scan", actor="admin", count=len(rt.code_plugins))
        return {
            "ok": True,
            "plugins": rt.code_plugins_snapshot(),
            "errors": rt.code_plugin_errors,
        }

    @app.post("/api/code-plugins/{plugin_id}/enable")
    async def toggle_code_plugin(plugin_id: str, request: Request):
        guard(request)
        body = await request.json()
        enabled = bool(body.get("enabled"))

        info = rt.code_plugins.get(plugin_id)
        if info is None:
            rt.reload_code_plugins()
            info = rt.code_plugins.get(plugin_id)
        if info is None:
            raise HTTPException(status_code=404, detail="没有这个插件")
        if enabled and info.error:
            raise HTTPException(status_code=400, detail=f"插件有问题，无法启用：{info.error}")

        rt.store.set_plugin_enabled(plugin_id, enabled, info.file_hash)
        rt.reload_code_plugins()
        rt.store.audit("plugin.toggle", target=plugin_id, actor="admin", enabled=enabled)
        return {
            "ok": True,
            "plugins": rt.code_plugins_snapshot(),
            "errors": rt.code_plugin_errors,
        }

    @app.post("/api/rules")
    async def set_rules(request: Request):
        guard(request)
        body = await request.json()
        return await rt.apply_rules(body)

    @app.post("/api/groups/{group_openid}/rule")
    async def set_group_rule(group_openid: str, request: Request):
        guard(request)
        body = await request.json()
        rule = str(body.get("house_rule") or "default")
        if rule not in ("default", "hr2", "hr3", "hr4"):
            raise HTTPException(status_code=400, detail="非法的房规")
        rt.store.set_group_house_rule(group_openid, rule)
        rt.store.audit("config.house_rule", target=group_openid, actor="admin", rule=rule)
        return {"ok": True, "house_rule": rule}

    @app.post("/api/groups/{group_openid}/rulepack")
    async def set_group_rulepack(group_openid: str, request: Request):
        guard(request)
        body = await request.json()
        pack_id = str(body.get("rulepack") or "").strip()
        if pack_id and pack_id not in {p.id for p in rt.packs}:
            raise HTTPException(status_code=400, detail="没有这个规则包")
        rt.store.set_group_rulepack(group_openid, pack_id)
        rt.store.audit(
            "config.rulepack", target=group_openid, actor="admin", pack=pack_id
        )
        return {"ok": True, "rulepack": pack_id}

    @app.post("/api/house-rule")
    async def set_house_rule(request: Request):
        guard(request)
        body = await request.json()
        rule = str(body.get("house_rule") or "default")
        if rule not in ("default", "hr2", "hr3", "hr4"):
            raise HTTPException(status_code=400, detail="非法的房规")
        rt.cfg.house_rule = rule
        from .. import config as _config

        _config.save(rt.cfg)
        rt.store.audit("config.house_rule", actor="admin", rule=rule)
        return {"ok": True, "house_rule": rule}

    @app.post("/api/persona")
    async def set_persona(request: Request):
        guard(request)
        body = await request.json()
        return await rt.apply_persona(body)

    @app.post("/api/reply")
    async def set_reply(request: Request):
        guard(request)
        body = await request.json()
        return await rt.apply_reply(body)

    @app.post("/api/settings")
    async def set_settings(request: Request):
        guard(request)
        body = await request.json()
        changed = await rt.apply_settings(body)
        return {"ok": True, "changed": changed}

    @app.post("/api/abuse/unmute")
    async def abuse_unmute(request: Request):
        guard(request)
        body = await request.json()
        group = str(body.get("group") or "").strip()
        member = str(body.get("member") or "").strip()
        if not group or not member:
            raise HTTPException(status_code=400, detail="参数不完整")
        return {"ok": rt.abuse.unmute(group, member, by="admin")}

    @app.get("/api/logs")
    async def logs(request: Request, lines: int = 80):
        guard(request)
        f = LOG_DIR / "qqbot.log"
        if not f.exists():
            return {"lines": []}
        try:
            content = f.read_text("utf-8", errors="replace").splitlines()
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))
        return {"lines": content[-max(1, min(lines, 500)):]}

    @app.post("/api/builtins/{builtin_id}/enable")
    async def toggle_builtin(builtin_id: str, request: Request):
        guard(request)
        from .. import builtins as builtin_plugins
        from .. import config as config_mod

        item = builtin_plugins.get(builtin_id)
        if item is None:
            raise HTTPException(status_code=404, detail="没有这个内置插件")
        body = await request.json()
        enabled = bool(body.get("enabled"))
        builtin_plugins.set_enabled(rt.cfg, builtin_id, enabled)
        config_mod.save(rt.cfg)
        rt.store.audit(
            "builtin.enable", target=builtin_id, actor="admin", enabled=enabled
        )
        return {
            "ok": True,
            "id": builtin_id,
            "enabled": enabled,
            "builtins": builtin_plugins.snapshot(rt.cfg),
        }

    @app.get("/api/builtins")
    async def list_builtins(request: Request):
        guard(request)
        from .. import builtins as builtin_plugins

        return {"builtins": builtin_plugins.snapshot(rt.cfg)}

    @app.post("/api/logs/clear")
    async def clear_logs(request: Request):
        guard(request)
        from .. import logging_setup

        result = logging_setup.clear_logs()
        rt.store.audit("logs.clear", actor="admin", **result)
        return {"ok": True, **result}

    @app.post("/api/backup/restore")
    async def restore_backup(request: Request):
        guard(request)
        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="备份文件为空")
        if len(body) > 100 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="备份文件过大（上限 100 MB）")

        try:
            zf = zipfile.ZipFile(io.BytesIO(body))
        except zipfile.BadZipFile as exc:
            raise HTTPException(status_code=400, detail="不是合法的 zip 备份") from exc

        names = zf.namelist()
        for name in names:
            path = PurePosixPath(name.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts:
                raise HTTPException(status_code=400, detail=f"非法路径：{name}")
            if path.parts and path.parts[0] not in ("data", "profiles", "plugins", "manifest.json"):
                raise HTTPException(status_code=400, detail=f"备份里包含未知目录：{name}")
            if name.endswith("secrets.dat"):
                raise HTTPException(status_code=400, detail="备份里不应包含密钥文件")

        tmp = Path(tempfile.mkdtemp(dir=str(RUNTIME_DIR), prefix="restore_"))
        try:
            zf.extractall(tmp)
            db_file = tmp / "data" / "bot.db"
            if not db_file.exists():
                raise HTTPException(status_code=400, detail="备份里没有 data/bot.db")
            rt.store.restore_from(db_file)

            for sub, target in (("profiles", PROFILES_DIR), ("plugins", PLUGINS_DIR)):
                src = tmp / sub
                if src.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(src, target, dirs_exist_ok=True)

            rt.load_packs()
            rt.reload_games()
            rt.reload_code_plugins()
            rt.reload_modes()
            rt.store.audit("data.restore", actor="admin")
            return {"ok": True, "restart_recommended": True}
        finally:
            zf.close()
            shutil.rmtree(tmp, ignore_errors=True)

    @app.post("/api/data/reset")
    async def reset_data(request: Request):
        guard(request)
        body = await request.json()
        if str(body.get("confirm") or "") != "RESET":
            raise HTTPException(status_code=400, detail="请输入 RESET 确认")
        rt.store.reset_all()
        rt.abuse.reset()
        rt._last_msg.clear()
        rt.reset_preview()
        rt.load_packs()
        rt.reload_games()
        rt.reload_code_plugins()
        rt.reload_modes()
        # 内置插件开关存在配置里，也要回到默认状态
        from .. import builtins as builtin_plugins
        from .. import config as config_mod

        for item in builtin_plugins.BUILTINS:
            builtin_plugins.set_enabled(rt.cfg, item.id, item.default_enabled)
        config_mod.save(rt.cfg)
        rt.store.audit("data.reset", actor="admin")
        from .. import logging_setup

        logging_setup.clear_logs()
        return {"ok": True}

    @app.get("/api/backup")
    async def backup_data(request: Request):
        guard(request)
        rt.store.checkpoint()
        db_file = DATA_DIR / "bot.db"
        if not db_file.exists():
            raise HTTPException(status_code=404, detail="还没有数据库可备份")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(db_file, "data/bot.db")
            for sub, root in (("profiles", PROFILES_DIR), ("plugins", PLUGINS_DIR)):
                if not root.exists():
                    continue
                for path in root.rglob("*"):
                    if not path.is_file():
                        continue
                    if "__pycache__" in path.parts or path.suffix == ".pyc":
                        continue
                    zf.write(path, f"{sub}/{path.relative_to(root).as_posix()}")
            zf.writestr(
                "manifest.json",
                json.dumps(
                    {
                        "format": "qqchatbot-backup",
                        "version": 1,
                        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        "instance_id": instance_id(),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

        filename = f"qqchatbot-backup-{time.strftime('%Y%m%d-%H%M%S')}.zip"
        return Response(
            content=buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/api/audit/prune")
    async def prune_audit(request: Request):
        guard(request)
        body = await request.json()
        try:
            days = int(body.get("keep_days", 30))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="keep_days 必须是数字") from None
        if days < 0:
            raise HTTPException(status_code=400, detail="keep_days 不能为负数")
        deleted = rt.store.prune_audit(days, 5000, purge_all=(days == 0))
        rt.store.audit(
            "audit.prune", actor="admin", keep_days=days, deleted=deleted
        )
        return {
            "ok": True,
            "deleted": deleted,
            "remaining": rt.store.audit_count(),
        }

    @app.post("/api/diagnostics")
    async def diagnostics(request: Request):
        guard(request)
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        out = RUNTIME_DIR / f"diagnostics-{time.strftime('%Y%m%d-%H%M%S')}.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            info = {
                "instance_id": instance_id(),
                "base": str(BASE),
                "base_len": len(str(BASE)),
                "python": sys.version.split()[0],
                "platform": platform.platform(),
                "arch": platform.machine(),
                "locale": platform.locale() if hasattr(platform, "locale") else "",
                "state": rt.snapshot(),
            }
            z.writestr("instance.json", json.dumps(info, ensure_ascii=False, indent=2))
            if LOG_DIR.exists():
                for f in sorted(LOG_DIR.glob("*.log*"))[-5:]:
                    z.write(f, f"logs/{f.name}")
            # 配置里不含密钥
            cfg_file = BASE / "config" / "instance.yaml"
            if cfg_file.exists():
                z.write(cfg_file, "config/instance.yaml")
        out.write_bytes(buf.getvalue())
        rt.store.audit("diagnostics.export", target=out.name, actor="admin")
        return {"ok": True, "path": str(out), "size": out.stat().st_size}

    @app.exception_handler(HTTPException)
    async def http_exc(_: Request, exc: HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"error": exc.detail})

    @app.exception_handler(_errors.BotError)
    async def bot_exc(_: Request, exc: "_errors.BotError"):
        return JSONResponse(
            status_code=400, content={"error": str(exc), "code": exc.code}
        )

    @app.get("/healthz")
    async def healthz():
        return Response("ok")

    return app
