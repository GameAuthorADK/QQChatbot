"""实例配置（不含密钥）。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import yamlutil
from .paths import INSTANCE_YAML

DEFAULT_REPLY = "收到，我是测试用机器人。"

#: 可在界面上调整的参数及其默认值（不要在这里放密钥/身份）
DEFAULTS = {
    "abuse_warn_threshold": 6,
    "abuse_mute_threshold": 3,
    "abuse_window_s": 60,
    "abuse_warn_cooldown_s": 300,
    "group_qpm": 20,
    "global_qpm": 60,
    "daily_msg_budget": 1000,
    "daily_token_budget": 300000,
    "history_limit": 12,
    "max_tokens": 800,
    "audit_keep_days": 30,
}


@dataclass
class InstanceConfig:
    # 身份
    app_id: str = ""
    # 模型
    provider: str = "mock"          # mock | openai
    base_url: str = ""
    model: str = ""
    max_tokens: int = 800
    timeout_s: float = 25.0
    temperature: float = 0.7
    history_limit: int = 12
    # 人设（安全底线在 prompts.py 里硬编码，不在此处）
    bot_name: str = "小助手"
    persona: str = "你是一个友善、简洁的群聊助手，回答直接，不说教。"
    negative_prompt: str = "不要输出代码块；不要长篇大论；不要替用户做决定。"
    #: 额外的回复风格要求，会拼在禁止事项之后
    style_prompt: str = ""
    # 长期记忆（用户可编辑，会拼进提示词）
    memory: str = ""
    auto_summary: bool = True
    summary_trigger_tokens: int = 8000
    #: 待整理对话攒够多少条也触发一次（短消息很难达到 token 阈值）
    summary_trigger_messages: int = 60
    # 房规：default | hr2 | hr3 | hr4
    house_rule: str = "default"    # 回复
    fallback_reply: str = "我想太久了，换个说法再问我一次？"
    chunk_limit: int = 1200
    max_chunks: int = 3
    # 关键词规则：[{pattern, reply, enabled}]
    keyword_rules: list = field(default_factory=list)
    # 群聊监听（需要 QQ 群开启全量消息）
    listen_enabled: bool = False
    listen_probability: int = 15
    listen_cooldown_s: int = 120
    listen_daily_limit: int = 30
    listen_min_chars: int = 4
    listen_min_members: int = 0
    listen_keywords: list = field(default_factory=list)
    # 多段回复
    multi_message: bool = False
    multi_message_max: int = 3
    multi_message_delay_ms: int = 700
    # 回复时不 @ 用户（改用主动消息）
    reply_without_at: bool = False
    # 内置插件：复读 / 接梗
    repeat_enabled: bool = False
    repeat_probability: int = 10
    repeat_cooldown_s: int = 60
    repeat_daily_limit: int = 20
    repeat_max_chars: int = 40
    repeat_mode: str = "both"  # repeat | banter | both
    #: 接梗提示词：一行一个，格式为「[梗名]：对梗的解释，应该怎么接」
    repeat_prompt: str = ""
    # 内置插件：主动发起话题
    proactive_enabled: bool = False
    proactive_probability: int = 10
    proactive_interval_s: int = 600
    proactive_idle_s: int = 300
    proactive_daily_limit: int = 5
    proactive_prompt: str = (
        "根据最近的群聊，主动开一个轻松、适合群聊的话题。"
    )
    # 内置插件：人设稳定
    persona_guard_enabled: bool = False
    persona_anchor: str = ""
    #: 按群累计多少条对话消息后自动更新一次自检报告
    persona_check_interval: int = 20
    #: 人设自检单独使用模型；启用后可以填不同的服务商 / 地址 / Key
    persona_check_use_separate: bool = False
    persona_check_provider: str = ""
    persona_check_base_url: str = ""
    persona_check_model: str = ""
    # 行为
    reply_text: str = DEFAULT_REPLY
    # 日志
    log_level: str = "INFO"
    #: 审计记录自动保留天数（0 表示不按时间清理，最多保留 5000 条）
    audit_keep_days: int = 30
    # 网关
    shard_index: int = 0
    shard_total: int = 1
    # 群授权：陌生人拉群一律进待审批，不再自动放行
    auto_approve_groups: bool = False
    # 滥用防护
    abuse_enabled: bool = True
    abuse_window_s: int = 60
    abuse_warn_threshold: int = 6
    abuse_mute_threshold: int = 3
    abuse_warn_cooldown_s: int = 300
    abuse_warn_text: str = "你 @ 得太频繁了，先缓一缓。"
    # 频率与额度
    group_qpm: int = 20
    global_qpm: int = 60
    daily_msg_budget: int = 1000
    daily_token_budget: int = 300000
    # 界面
    open_devtools: bool = False
    #: 点窗口 X 的行为：tray=最小化到托盘，exit=退出程序
    close_action: str = "tray"
    #: 是否把图片附件交给模型（需要模型支持图片输入）
    vision_enabled: bool = False
    # 外部 wiki 查询
    wiki_enabled: bool = True
    #: 中文关键词没匹配上时，是否自动翻成英文再查一次（会调用模型）
    wiki_translate: bool = True
    wiki_sites: list = field(
        default_factory=lambda: [
            "灰机wiki|https://www.huijiwiki.com",
            "萌娘百科|https://zh.moegirl.org.cn",
        ]
    )

    # 运行时开关（不落盘）
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("extra", None)
        return d


def load(path: Path = INSTANCE_YAML) -> InstanceConfig:
    if not path.exists():
        return InstanceConfig()
    raw = yamlutil.load_file(path)
    known = {k: v for k, v in raw.items() if k in InstanceConfig.__dataclass_fields__}
    known.pop("extra", None)
    return InstanceConfig(**known)


def save(cfg: InstanceConfig, path: Path = INSTANCE_YAML) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(yamlutil.dump(cfg.to_dict()), encoding="utf-8")
    tmp.replace(path)
