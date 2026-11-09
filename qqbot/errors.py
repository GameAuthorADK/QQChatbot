"""错误码。

编码规则 E<分类><序号>，与 docs/p0/04-error-codes.md 保持一致。
用户只看 message，程序只看 code。
"""

from __future__ import annotations


class BotError(Exception):
    """所有可预期错误的基类。"""

    def __init__(self, code: str, message: str, *, retryable: bool = False, detail=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.detail = detail or {}

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


# ── 平台 / 网关 ────────────────────────────────────────────────
TOKEN_EMPTY = "E1001"
TOKEN_INVALID = "E1002"
TOKEN_FETCH_FAILED = "E1003"
TOKEN_BROKEN = "E1004"

GATEWAY_URL_FAILED = "E1101"
WS_CONNECT_FAILED = "E1102"
WS_IDENTIFY_REJECTED = "E1103"
WS_HEARTBEAT_TIMEOUT = "E1104"
WS_RESUME_FAILED = "E1105"
WS_FATAL = "E1106"

SEND_FAILED = "E1301"
SEND_MSG_SEQ_CONFLICT = "E1302"
SEND_WINDOW_EXPIRED = "E1303"
SEND_RATE_LIMITED = "E1304"

# ── 模型 ──────────────────────────────────────────────────────
LLM_NO_PROVIDER = "E2001"
LLM_AUTH = "E2002"
LLM_TIMEOUT = "E2003"
LLM_RATE_LIMIT = "E2004"
LLM_CONTEXT_OVERFLOW = "E2005"
LLM_BAD_RESPONSE = "E2006"
LLM_UNSUPPORTED_MODALITY = "E2007"
LLM_BUDGET_EXCEEDED = "E2008"

# ── 代码插件 ──────────────────────────────────────────────────
PLUGIN_LOAD_FAILED = "E3101"
PLUGIN_TIMEOUT = "E3102"
PLUGIN_FORBIDDEN = "E3110"
PLUGIN_NOT_ENABLED = "E3111"

# ── 存储 ──────────────────────────────────────────────────────
DB_OPEN_FAILED = "E5001"
DB_LOCKED = "E5002"

# ── 运行时 ────────────────────────────────────────────────────
PATH_TOO_LONG = "E6001"
PATH_NOT_WRITABLE = "E6002"
PATH_NETWORK = "E6003"
UNICODE_PATH_FAILED = "E6005"
WEBVIEW2_MISSING = "E6101"
INSTANCE_LOCKED = "E6103"
APPID_CONFLICT = "E6201"
ARCH_UNSUPPORTED = "E6202"
