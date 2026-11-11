"""P1 核心逻辑测试（不依赖网络与凭据）。

运行：python -m unittest discover -s tests -v
"""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qqbot import paths  # noqa: E402
from qqbot.events import parse_attachments, parse_group_message  # noqa: E402
from qqbot.gateway import protocol  # noqa: E402
from qqbot.store import Store  # noqa: E402


class TestPaths(unittest.TestCase):
    def test_budget_formula(self):
        self.assertEqual(paths.path_budget(), 260 - paths.max_rel_len() - 10)

    def test_budget_positive(self):
        self.assertGreater(paths.path_budget(), 0)

    def test_instance_id_stable(self):
        self.assertEqual(paths.instance_id(), paths.instance_id())
        self.assertEqual(len(paths.instance_id()), 12)

    def test_check_base(self):
        ok, detail = paths.check_base_path()
        self.assertIn(ok, (True, False))
        self.assertIsInstance(detail, str)


class TestProtocol(unittest.TestCase):
    def test_decode_ok(self):
        d = protocol.decode('{"op":0,"s":1,"t":"READY","d":{}}')
        self.assertEqual(d["op"], 0)

    def test_decode_bad(self):
        with self.assertRaises(protocol.ProtocolError):
            protocol.decode("not json")

    def test_identify_token_prefix(self):
        s = protocol.identify("abc", protocol.DEFAULT_INTENTS, (0, 1))
        self.assertIn('"token":"QQBot abc"', s)
        self.assertIn(str(1 << 25), s)

    def test_heartbeat_null(self):
        self.assertIn('"op":1', protocol.heartbeat(None))

    def test_resume(self):
        s = protocol.resume("abc", "sess", 42)
        self.assertIn('"session_id":"sess"', s)
        self.assertIn('"seq":42', s)


class TestEvents(unittest.TestCase):
    def test_parse_group_message(self):
        payload = {
            "id": "MSG1",
            "author": {
                "member_openid": "M1",
                "member_role": "admin",
                "username": "x",
                "union_openid": "U1",
            },
            "content": " hello ",
            "group_openid": "G1",
            "timestamp": "2026-10-29T10:00:00+08:00",
        }
        m = parse_group_message(payload, seq=7)
        self.assertEqual(m.content, "hello")
        self.assertEqual(m.member_role, "admin")
        self.assertEqual(m.seq, 7)
        self.assertEqual(m.union_openid, "U1")

    def test_parse_attachments(self):
        items = [
            {"content_type": "image/png", "url": "u1", "size": 10},
            {"content_type": "voice", "url": "u2", "asr_refer_text": "你好"},
        ]
        atts = parse_attachments(items)
        self.assertEqual(atts[0].kind, "image")
        self.assertEqual(atts[1].kind, "voice")
        self.assertEqual(atts[1].asr_text, "你好")


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"
        self.store = Store(self.db)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_dedupe(self):
        self.assertTrue(self.store.claim_message("m1"))
        self.assertFalse(self.store.claim_message("m1"))
        self.assertTrue(self.store.claim_message("m2"))

    def test_msg_seq_monotonic(self):
        self.assertEqual(self.store.next_msg_seq("m1"), 1)
        self.assertEqual(self.store.next_msg_seq("m1"), 2)
        self.assertEqual(self.store.next_msg_seq("m1"), 3)
        self.assertEqual(self.store.peek_msg_seq("m1"), 3)

    def test_msg_seq_survives_reopen(self):
        self.store.next_msg_seq("m9")
        self.store.next_msg_seq("m9")
        self.store.close()
        self.store = Store(self.db)
        self.assertEqual(self.store.next_msg_seq("m9"), 3)

    def test_group_status(self):
        self.assertIsNone(self.store.group_status("g1"))
        self.store.upsert_group("g1", "active", "u1")
        self.assertEqual(self.store.group_status("g1"), "active")

    def test_set_group_status(self):
        self.store.upsert_group("g2", "pending", "u1")
        self.store.set_group_status("g2", "active")
        self.assertEqual(self.store.group_status("g2"), "active")
        self.store.set_group_status("g2", "disabled")
        self.assertEqual(self.store.group_status("g2"), "disabled")

    def test_audit(self):
        self.store.audit("test.action", target="x", foo=1)
        rows = self.store.conn.execute("SELECT action FROM audit").fetchall()
        self.assertEqual(rows[0][0], "test.action")


class TestSecrets(unittest.TestCase):
    def test_roundtrip(self):
        from qqbot import secrets

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.dat"
            secrets.save({"app_secret": "abc123"}, p)
            self.assertEqual(secrets.load(p)["app_secret"], "abc123")

    def test_multiple_keys_roundtrip(self):
        from qqbot import secrets

        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.dat"
            keys = {"llm_keys": {"deepseek": "sk-a", "glm": "sk-b"}}
            secrets.save(keys, p)
            got = secrets.load(p)
            self.assertEqual(got["llm_keys"]["deepseek"], "sk-a")
            self.assertEqual(got["llm_keys"]["glm"], "sk-b")

    def test_mask(self):
        from qqbot import secrets

        self.assertEqual(secrets.mask("abcdefgh"), "****efgh")
        self.assertNotIn("abcd", secrets.mask("abcdefgh"))


class TestTextUtil(unittest.TestCase):
    def test_short_passthrough(self):
        from qqbot.textutil import split_text

        self.assertEqual(split_text("你好"), ["你好"])

    def test_empty(self):
        from qqbot.textutil import split_text

        self.assertEqual(split_text("   "), [])

    def test_long_split_within_max_chunks(self):
        from qqbot.textutil import split_text

        text = "这是一句话。" * 400
        chunks = split_text(text)
        self.assertTrue(1 <= len(chunks) <= 3)
        self.assertTrue(all(len(c) <= 1200 for c in chunks))

    def test_sanitize_blocks_at_all(self):
        from qqbot.textutil import sanitize

        out = sanitize("@全体成员 集合")
        self.assertNotIn("@全体成员", out)

    def test_control_chars_removed(self):
        from qqbot.textutil import sanitize

        self.assertEqual(sanitize("a\x00b\x07c"), "abc")


class TestThreads(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_append_turn(self):
        self.store.append_turn("g", "m", "你好", "你好呀")
        msgs = self.store.get_thread("g", "m")
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["role"], "user")
        self.assertEqual(msgs[1]["role"], "assistant")

    def test_limit(self):
        for i in range(10):
            self.store.append_turn("g", "m", f"u{i}", f"a{i}", limit=4)
        msgs = self.store.get_thread("g", "m")
        self.assertEqual(len(msgs), 4)
        self.assertEqual(msgs[-1]["content"], "a9")

    def test_isolation_by_member(self):
        self.store.append_turn("g", "m1", "a", "b")
        self.store.append_turn("g", "m2", "c", "d")
        self.assertEqual(len(self.store.get_thread("g", "m1")), 2)
        self.assertEqual(self.store.get_thread("g", "m1")[0]["content"], "a")

    def test_clear(self):
        self.store.append_turn("g", "m", "a", "b")
        self.store.clear_thread("g", "m")
        self.assertEqual(self.store.get_thread("g", "m"), [])

    def test_repeat_stats_only_counts_type(self):
        from qqbot.repeat_plugin import RepeatMemory

        mem = RepeatMemory(self.store)
        mem.bump_type("g", "2026-11-09", "repeat")
        mem.bump_type("g", "2026-11-09", "repeat")
        mem.bump_type("g", "2026-11-09", "banter")
        mem.bump_type("g", "2026-11-10", "banter")

        day1 = mem.stats("g", "2026-11-09")
        self.assertEqual(day1["repeat"]["count"], 2)
        self.assertEqual(day1["banter"]["count"], 1)
        day2 = mem.stats("g", "2026-11-10")
        self.assertEqual(day2["repeat"]["count"] if "repeat" in day2 else 0, 0)
        self.assertEqual(day2["banter"]["count"], 1)
        self.assertEqual(self.store.get_thread("g", "m"), [])

    def test_meme_stats_by_member_and_group(self):
        from qqbot.repeat_plugin import RepeatMemory

        mem = RepeatMemory(self.store)
        mem.bump_meme("g", "m1", "repeat", "急了")
        mem.bump_meme("g", "m1", "repeat", "急了")
        mem.bump_meme("g", "m2", "repeat", "抽象")
        mem.bump_meme("g", "m1", "banter", "润了")

        group_top = mem.top_memes("g", kind="repeat")
        self.assertEqual(group_top[0]["text"], "急了")
        self.assertEqual(group_top[0]["count"], 2)
        member_top = mem.top_memes("g", member_openid="m1")
        texts = [m["text"] for m in member_top]
        self.assertIn("急了", texts)
        self.assertIn("润了", texts)
        self.assertNotIn("抽象", texts)

    def test_group_reply_overrides(self):
        self.assertEqual(self.store.get_group_reply("g"), {})
        self.store.set_group_reply(
            "g", {"fallback_reply": "群专用", "chunk_limit": 500}
        )
        data = self.store.get_group_reply("g")
        self.assertEqual(data["fallback_reply"], "群专用")
        self.assertEqual(data["chunk_limit"], 500)
        self.store.clear_group_reply("g")
        self.assertEqual(self.store.get_group_reply("g"), {})

    def test_member_summaries_across_groups(self):
        self.store.save_memory_state("g1", "u1", "群1记忆", [], mode="chat")
        self.store.save_memory_state("g2", "u1", "群2记忆", [], mode="chat")
        self.store.save_memory_state("g3", "u2", "别人的记忆", [], mode="chat")
        rows = self.store.member_summaries("u1", "chat", exclude_group="g1")
        self.assertEqual([r["group"] for r in rows], ["g2"])
        self.assertEqual(rows[0]["summary"], "群2记忆")


class TestMockProvider(unittest.IsolatedAsyncioTestCase):
    async def test_complete_uses_last_user(self):
        from qqbot.providers import MockProvider, build_messages

        msgs = build_messages("sys", [{"role": "user", "content": "早"}], "今天天气如何")
        comp = await MockProvider().complete(msgs, timeout=5, max_tokens=200)
        self.assertIn("今天天气如何", comp.text)
        self.assertIn("2 轮", comp.text)

    async def test_probe(self):
        from qqbot.providers import MockProvider

        r = await MockProvider().probe()
        self.assertTrue(r.ok)


class _Cfg:
    abuse_window_s = 60
    abuse_warn_threshold = 3
    abuse_mute_threshold = 1
    abuse_warn_cooldown_s = 0
    abuse_warn_text = "慢点"
    daily_msg_budget = 5
    daily_token_budget = 1000


class TestRateLimit(unittest.TestCase):
    def test_hit_and_count(self):
        from qqbot.ratelimit import SlidingWindow

        w = SlidingWindow(3, 60)
        self.assertEqual(w.hit("a"), 1)
        self.assertEqual(w.hit("a"), 2)
        self.assertEqual(w.count("a"), 2)
        self.assertFalse(w.over("a"))
        w.hit("a")
        self.assertTrue(w.over("a"))
        w.reset("a")
        self.assertEqual(w.count("a"), 0)

    def test_keys_isolated(self):
        from qqbot.ratelimit import SlidingWindow

        w = SlidingWindow(2, 60)
        w.hit("a")
        self.assertEqual(w.count("b"), 0)


class TestAbuse(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "a.db"
        self.store = Store(self.db)
        from qqbot.abuse import AbuseGuard

        self.guard = AbuseGuard(self.store, _Cfg())

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_normal_then_warn(self):
        acts = [self.guard.check("g", "m").action for _ in range(4)]
        self.assertEqual(acts[:3], ["ok", "ok", "ok"])
        self.assertEqual(acts[3], "warn")

    def test_warn_then_mute_then_silent(self):
        for _ in range(4):
            self.guard.check("g", "m")
        self.assertEqual(self.guard.check("g", "m").action, "mute")
        self.assertEqual(self.guard.check("g", "m").action, "muted")

    def test_unmute(self):
        for _ in range(5):
            self.guard.check("g", "m")
        self.assertTrue(self.guard.unmute("g", "m"))
        self.assertEqual(self.guard.check("g", "m").action, "ok")

    def test_mute_persists_after_reopen(self):
        for _ in range(5):
            self.guard.check("g", "m")
        self.store.close()
        self.store = Store(self.db)
        self.assertTrue(self.store.is_muted("g", "m"))


class TestQuota(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "q.db")
        from qqbot.quota import Quota

        self.quota = Quota(self.store, _Cfg())

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_message_budget(self):
        for _ in range(5):
            self.assertTrue(self.quota.allow_message("g"))
            self.quota.record_message("g")
        self.assertFalse(self.quota.allow_message("g"))

    def test_tokens(self):
        self.quota.record_tokens(400)
        self.assertEqual(self.quota.snapshot()["tokens"], 400)

    def test_zero_means_unlimited(self):
        self.quota.cfg.daily_msg_budget = 0
        self.quota.cfg.daily_token_budget = 0
        for _ in range(20):
            self.quota.record_message("g")
            self.quota.record_tokens(10_000)
        self.assertTrue(self.quota.allow_message("g"))


class TestDice(unittest.TestCase):
    def test_fixed_seed_reproducible(self):
        from qqbot.dice import roll

        a = roll("3d6+2", seed=12345)
        b = roll("3d6+2", seed=12345)
        self.assertEqual(a.total, b.total)
        self.assertEqual(a.rolls, b.rolls)
        self.assertEqual(a.total, sum(a.rolls) + 2)

    def test_keep_high(self):
        from qqbot.dice import roll

        r = roll("2d20kh1", seed=7)
        self.assertTrue(r.ok)
        self.assertEqual(r.total, max(r.rolls))

    def test_keep_low(self):
        from qqbot.dice import roll

        r = roll("2d20kl1", seed=7)
        self.assertEqual(r.total, min(r.rolls))

    def test_d100_default_count(self):
        from qqbot.dice import roll

        r = roll("d100", seed=1)
        self.assertTrue(r.ok)
        self.assertEqual(len(r.rolls), 1)
        self.assertTrue(1 <= r.total <= 100)

    def test_rejects_garbage(self):
        from qqbot.dice import roll

        self.assertFalse(roll("abc").ok)
        self.assertFalse(roll("").ok)
        self.assertFalse(roll("1d").ok)

    def test_rejects_huge(self):
        from qqbot.dice import roll

        self.assertFalse(roll("9999d6").ok)

    def test_multi_term(self):
        from qqbot.dice import roll

        r = roll("1d8+1d6+3", seed=3)
        self.assertTrue(r.ok)
        self.assertEqual(len(r.rolls), 2)
        self.assertEqual(r.total, sum(r.rolls) + 3)


class TestCommands(unittest.TestCase):
    def test_parse_basic(self):
        from qqbot.commands import parse

        c = parse("/roll 1d20")
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "roll")
        self.assertEqual(c.args, ["1d20"])

    def test_not_command(self):
        from qqbot.commands import parse

        self.assertIsNone(parse("你好"))
        self.assertIsNone(parse(""))
        self.assertIsNone(parse("/"))

    def test_fullwidth_prefix(self):
        from qqbot.commands import parse

        c = parse("／help")
        self.assertIsNotNone(c)
        self.assertEqual(c.name, "help")

    def test_alias(self):
        from qqbot.commands import parse

        self.assertEqual(parse("/r 1d6").name, "roll")
        self.assertEqual(parse("/帮助").name, "help")

    def test_case_insensitive(self):
        from qqbot.commands import parse

        self.assertEqual(parse("/ROLL 1d6").name, "roll")


class TestGroupMode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "m.db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_default_chat(self):
        self.assertEqual(self.store.group_mode("g"), "chat")

    def test_set_and_read(self):
        self.store.upsert_group("g", "active", "u")
        self.store.set_group_mode("g", "trpg")
        self.assertEqual(self.store.group_mode("g"), "trpg")
        self.assertEqual(self.store.groups()[0]["mode"], "trpg")

    def test_set_mode_keeps_status(self):
        self.store.upsert_group("g", "active", "u")
        self.store.set_group_mode("g", "minigame")
        self.assertEqual(self.store.group_status("g"), "active")


class TestExpr(unittest.TestCase):
    def test_arithmetic(self):
        from qqbot.expr import evaluate

        self.assertEqual(evaluate("floor((con + siz) / 10)", {"con": 55, "siz": 50}), 10)
        self.assertEqual(evaluate("pow", {"pow": 60}), 60)

    def test_functions(self):
        from qqbot.expr import evaluate

        self.assertEqual(evaluate("max(0, str - 12) * 5 + 25", {"str": 15}), 40)
        self.assertEqual(evaluate("min(3, 9)", {}), 3)

    def test_rejects_code(self):
        from qqbot.expr import ExprError, evaluate

        for bad in [
            "__import__('os').system('calc')",
            "open('x')",
            "().__class__",
            "[x for x in range(3)]",
            "lambda: 1",
            "a.b",
        ]:
            with self.assertRaises(ExprError):
                evaluate(bad, {"a": 1})

    def test_rejects_unknown_name(self):
        from qqbot.expr import ExprError, evaluate

        with self.assertRaises(ExprError):
            evaluate("nope + 1", {"a": 1})

    def test_rejects_div_zero(self):
        from qqbot.expr import ExprError, evaluate

        with self.assertRaises(ExprError):
            evaluate("1 / 0", {})

    def test_lookup(self):
        from qqbot.expr import lookup

        table = [{"max": 13, "value": "0"}, {"max": 18, "value": "1"}, {"max": 20, "value": "2"}]
        self.assertEqual(lookup(table, 10), "0")
        self.assertEqual(lookup(table, 17), "1")
        self.assertEqual(lookup(table, 20), "2")


class TestRulepack(unittest.TestCase):
    def test_load_bundled_coc(self):
        from qqbot.paths import PLUGINS_DIR
        from qqbot.rulepacks import load_py_pack

        pack = load_py_pack(PLUGINS_DIR / "trpg" / "coc7th.py")
        self.assertEqual(pack.id, "coc7th")
        self.assertTrue(any(f.key == "hp_max" and f.type == "expr" for f in pack.fields))
        self.assertGreater(len(pack.fields), 8)

    def test_rejects_permissions(self):
        import tempfile as tf
        from pathlib import Path as P

        from qqbot.rulepacks import PackError, load_pack

        with tf.TemporaryDirectory() as d:
            p = P(d) / "bad"
            p.mkdir()
            (p / "manifest.yaml").write_text(
                "id: bad\npermissions: [net]\n", encoding="utf-8"
            )
            with self.assertRaises(PackError):
                load_pack(p)

    def test_rejects_cycle(self):
        import tempfile as tf
        from pathlib import Path as P

        from qqbot.rulepacks import PackError, load_pack

        with tf.TemporaryDirectory() as d:
            p = P(d) / "cyc"
            p.mkdir()
            (p / "manifest.yaml").write_text("id: cyc\n", encoding="utf-8")
            (p / "schema.yaml").write_text(
                "fields:\n"
                "  - { key: a, type: expr, expr: 'b + 1' }\n"
                "  - { key: b, type: expr, expr: 'a + 1' }\n",
                encoding="utf-8",
            )
            with self.assertRaises(PackError):
                load_pack(p)

    def test_rejects_bad_expr(self):
        import tempfile as tf
        from pathlib import Path as P

        from qqbot.rulepacks import PackError, load_pack

        with tf.TemporaryDirectory() as d:
            p = P(d) / "evl"
            p.mkdir()
            (p / "manifest.yaml").write_text("id: evl\n", encoding="utf-8")
            (p / "schema.yaml").write_text(
                "fields:\n  - { key: a, type: expr, expr: \"__import__('os')\" }\n",
                encoding="utf-8",
            )
            with self.assertRaises(PackError):
                load_pack(p)


class TestCards(unittest.TestCase):
    def setUp(self):
        from qqbot.paths import PLUGINS_DIR
        from qqbot.rulepacks import load_py_pack

        self.pack = load_py_pack(PLUGINS_DIR / "trpg" / "coc7th.py")

    def test_manual_values_are_not_overwritten(self):
        from qqbot import cards

        data = cards.defaults(self.pack)
        data["hp"] = 4
        data["skills"]["侦查"] = 60
        data["con"] = 80

        data = cards.compute(self.pack, data)
        self.assertEqual(data["hp"], 4)
        self.assertEqual(data["hp_max"], (80 + data["siz"]) // 10)
        self.assertEqual(data["skills"]["侦查"], 60)

    def test_skills_cannot_be_set_as_whole_field(self):
        from qqbot import cards

        value, err = cards.coerce(self.pack, "skills", "侦查 60")
        self.assertIsNone(value)
        self.assertIn("pc set 侦查", err)

    def test_defaults_compute(self):
        from qqbot import cards

        d = cards.defaults(self.pack)
        self.assertEqual(d["hp"], 10)     # (50+50)/10
        self.assertEqual(d["mp"], 10)     # 50/5
        self.assertEqual(d["san"], 50)

    def test_set_updates_derived(self):
        from qqbot import cards

        d = cards.defaults(self.pack)
        d["con"] = 80
        d["siz"] = 80
        d = cards.compute(self.pack, d)
        self.assertEqual(d["hp_max"], 16)
        # 当前生命不会因为上限变化而自动回满
        self.assertEqual(d["hp"], 10)

    def test_coerce_range(self):
        from qqbot import cards

        val, err = cards.coerce(self.pack, "str", "120")
        self.assertIsNotNone(err)
        val, err = cards.coerce(self.pack, "str", "60")
        self.assertEqual((val, err), (60, ""))

    def test_coerce_rejects_derived(self):
        from qqbot import cards

        val, err = cards.coerce(self.pack, "hp", "12")
        self.assertIsNotNone(err)

    def test_render_contains_label(self):
        from qqbot import cards

        text = cards.render(self.pack, cards.defaults(self.pack))
        self.assertIn("力量", text)
        self.assertIn("生命", text)

    def test_skill_catalog(self):
        from qqbot import cards

        names = cards.skill_names(self.pack)
        self.assertGreater(len(names), 60)
        self.assertIn("侦查", names)
        self.assertIn("图书馆使用", names)

    def test_skill_base_expr(self):
        from qqbot import cards

        d = cards.defaults(self.pack)
        self.assertEqual(d["skills"]["闪避"], 25)      # dex 50 / 2
        self.assertEqual(d["skills"]["语言（母语）"], 50)  # edu 50
        self.assertEqual(d["skills"]["侦查"], 25)      # 固定 25

    def test_set_skill(self):
        from qqbot import cards

        d = cards.defaults(self.pack)
        ok, err = cards.set_skill(self.pack, d, "侦查", "60")
        self.assertTrue(ok, err)
        self.assertEqual(d["skills"]["侦查"], 60)

    def test_set_skill_rejects(self):
        from qqbot import cards

        d = cards.defaults(self.pack)
        ok, _ = cards.set_skill(self.pack, d, "不存在的技能", "60")
        self.assertFalse(ok)
        ok, _ = cards.set_skill(self.pack, d, "侦查", "999")
        self.assertFalse(ok)

    def test_render_only_changed_skills(self):
        from qqbot import cards

        d = cards.defaults(self.pack)
        self.assertIn("全部为基础值", cards.render(self.pack, d))
        cards.set_skill(self.pack, d, "侦查", "60")
        text = cards.render(self.pack, d)
        self.assertIn("侦查 60", text)
        self.assertNotIn("闪避 25", text)

    def test_hp_default_follows_max(self):
        from qqbot import cards

        d = cards.defaults(self.pack)
        self.assertEqual(d["hp"], d["hp_max"])
        self.assertEqual(d["san"], 50)
        self.assertEqual(d["san_max"], 99)

    def test_render_shows_current_over_max(self):
        from qqbot import cards

        d = cards.defaults(self.pack)
        d["hp"] = 4
        self.assertIn("生命 4/10", cards.render(self.pack, d))

    def test_can_edit_current_hp(self):
        from qqbot import cards

        val, err = cards.coerce(self.pack, "hp", "4")
        self.assertEqual((val, err), (4, ""))
        # 上限仍然是派生，不可改
        val, err = cards.coerce(self.pack, "hp_max", "99")
        self.assertIsNotNone(err)


class TestChecks(unittest.TestCase):
    def setUp(self):
        from qqbot.paths import PLUGINS_DIR
        from qqbot.rulepacks import load_py_pack

        self.pack = load_py_pack(PLUGINS_DIR / "trpg" / "coc7th.py")

    def test_missing_skill_falls_back_to_base(self):
        from qqbot import cards, checks

        data = cards.defaults(self.pack)
        base = data["skills"]["侦查"]
        del data["skills"]["侦查"]
        self.assertEqual(checks.skill_value(self.pack, data, "侦查"), base)

    def _grade(self, roll, target):
        from qqbot import expr

        env = {"roll": roll, "target": target}
        for item in self.pack.checks["skill"].outcomes:
            if item["else"] or expr.evaluate_bool(item["when"], env):
                return item["label"]
        return "失败"

    def test_grades(self):
        self.assertEqual(self._grade(1, 60), "大成功")
        self.assertEqual(self._grade(12, 60), "极难成功")
        self.assertEqual(self._grade(30, 60), "困难成功")
        self.assertEqual(self._grade(60, 60), "成功")
        self.assertEqual(self._grade(61, 60), "失败")
        self.assertEqual(self._grade(100, 60), "大失败")

    def test_fumble_threshold(self):
        # 目标 < 50 时 96-100 都是大失败
        self.assertEqual(self._grade(96, 40), "大失败")
        # 目标 >= 50 时只有 100
        self.assertEqual(self._grade(96, 60), "失败")

    def test_san_parse(self):
        from qqbot.checks import parse_san_expr

        self.assertEqual(parse_san_expr("0/1d6"), ("0", "1d6"))
        self.assertEqual(parse_san_expr("1/1d10"), ("1", "1d10"))
        self.assertEqual(parse_san_expr(""), ("0", "1d6"))

    def test_san_max_amount(self):
        from qqbot.checks import _max_amount

        self.assertEqual(_max_amount("1d6"), 6)
        self.assertEqual(_max_amount("2d10"), 20)
        self.assertEqual(_max_amount("3"), 3)


class TestKeywordRules(unittest.TestCase):
    def _rt(self, rules):
        import types

        from qqbot.app import Runtime

        fake = types.SimpleNamespace(cfg=types.SimpleNamespace(keyword_rules=rules))
        return fake, Runtime.match_rule

    def test_match(self):
        rules = [{"pattern": "开团|跑团", "reply": "想跑团请私聊团长", "enabled": True}]
        fake, fn = self._rt(rules)
        self.assertEqual(fn(fake, "什么时候开团"), "想跑团请私聊团长")

    def test_disabled_skipped(self):
        rules = [{"pattern": "开团", "reply": "x", "enabled": False}]
        fake, fn = self._rt(rules)
        self.assertIsNone(fn(fake, "开团吗"))

    def test_first_match_wins(self):
        rules = [
            {"pattern": "帮助", "reply": "A", "enabled": True},
            {"pattern": "帮助", "reply": "B", "enabled": True},
        ]
        fake, fn = self._rt(rules)
        self.assertEqual(fn(fake, "帮助"), "A")

    def test_no_match(self):
        fake, fn = self._rt([{"pattern": "^ping$", "reply": "pong", "enabled": True}])
        self.assertIsNone(fn(fake, "ping 一下"))

    def test_bad_regex_ignored(self):
        fake, fn = self._rt([{"pattern": "([", "reply": "x", "enabled": True}])
        self.assertIsNone(fn(fake, "任意"))


class TestMemory(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name) / "mem.db")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_append_turn_returns_dropped(self):
        dropped = []
        for i in range(3):
            dropped = self.store.append_turn("g", "m", f"u{i}", f"a{i}", limit=4)
        self.assertEqual([d["content"] for d in dropped], ["u0", "a0"])

    def test_memory_state_roundtrip(self):
        self.store.save_memory_state("g", "m", "- 用户叫小周", [{"role": "user", "content": "hi"}])
        summary, pending = self.store.get_memory_state("g", "m")
        self.assertEqual(summary, "- 用户叫小周")
        self.assertEqual(len(pending), 1)

    def test_memory_isolated_per_member(self):
        self.store.save_memory_state("g", "m1", "A", [])
        self.store.save_memory_state("g", "m2", "B", [])
        self.assertEqual(self.store.get_memory_state("g", "m1")[0], "A")
        self.assertEqual(self.store.get_memory_state("g", "m2")[0], "B")

    def test_memory_updated_at_refreshes_on_save(self):
        import time

        self.store.save_memory_state("g", "m", "A", [])
        first = self.store.list_summaries()[0]["updated_at"]
        time.sleep(0.02)
        self.store.save_memory_state("g", "m", "B", [])
        second = self.store.list_summaries()[0]["updated_at"]
        self.assertGreater(second, first)

    def test_memory_total_limit(self):
        import time

        self.store.save_memory_state(
            "g", "m0", "S0", [{"role": "user", "content": "old"}]
        )
        for i in range(1, 205):
            self.store.save_memory_state("g", f"m{i}", f"S{i}", [])
            time.sleep(0.001)
        rows = self.store.list_summaries()
        self.assertEqual(len(rows), 200)
        self.assertEqual(self.store.get_summary("g", "m0"), "")
        self.assertEqual(self.store.get_memory_state("g", "m0")[1], [])
        self.assertEqual(self.store.get_summary("g", "m204"), "S204")

    def test_memory_page(self):
        for i in range(25):
            self.store.save_memory_state("g", f"m{i}", f"S{i}", [])
        items, total = self.store.list_summaries_page(page=2, size=10)
        self.assertEqual(total, 25)
        self.assertEqual(len(items), 10)

    def test_memory_limit_after_restore_backup(self):
        import time

        src_path = Path(self.tmp.name) / "backup.db"
        src = Store(src_path)
        try:
            for i in range(205):
                src.save_memory_state("g", f"m{i}", f"S{i}", [])
                time.sleep(0.001)
        finally:
            src.close()
        self.store.restore_from(src_path)
        rows = self.store.list_summaries()
        self.assertEqual(len(rows), 200)
        self.assertEqual(self.store.get_summary("g", "m0"), "")
        self.assertEqual(self.store.get_summary("g", "m204"), "S204")

    def test_pending_summary(self):
        self.store.save_memory_state(
            "g1", "m1", "S1",
            [
                {"role": "user", "content": "a"},
                {"role": "assistant", "content": "b"},
            ],
        )
        self.store.save_memory_state(
            "g1", "m2", "", [{"role": "user", "content": "c"}]
        )
        self.store.save_memory_state(
            "g2", "m1", "", [{"role": "user", "content": "d"}]
        )
        self.store.save_memory_state("g2", "m3", "S3", [])
        self.assertEqual(
            self.store.pending_summary(),
            {"people": 2, "threads": 3, "messages": 4},
        )


class TestSummaryPrompt(unittest.TestCase):
    def test_prompt_exists(self):
        from qqbot import prompts

        self.assertIn("记忆整理任务", prompts.SUMMARY_PROMPT)
        self.assertIn("最多 10 条", prompts.SUMMARY_PROMPT)
        self.assertIn("最多 6 条", prompts.SUMMARY_PROMPT)
        self.assertIn("最多 4 条", prompts.SUMMARY_PROMPT)
        self.assertIn("以新内容为准", prompts.SUMMARY_PROMPT)
        self.assertIn("物品", prompts.SUMMARY_PROMPT)
        self.assertIn("用户用「助手」称呼机器人", prompts.SUMMARY_PROMPT)
        self.assertIn("不要按固定词表判断", prompts.SUMMARY_PROMPT)

    def test_no_manual_memory_section(self):
        from qqbot import prompts
        from qqbot.config import InstanceConfig

        text = prompts.compose(InstanceConfig())
        self.assertNotIn("【长期记忆】", text)
        self.assertIn("【安全底线", text)


class TestHouseRules(unittest.TestCase):
    def setUp(self):
        from qqbot.paths import PLUGINS_DIR
        from qqbot.rulepacks import load_py_pack

        self.pack = load_py_pack(PLUGINS_DIR / "trpg" / "coc7th.py")

    def _grade(self, check_id, roll, target):
        from qqbot import expr

        env = {"roll": roll, "target": target}
        for item in self.pack.checks[check_id].outcomes:
            if item["else"] or expr.evaluate_bool(item["when"], env):
                return item["label"]
        return "失败"

    def test_variants_present(self):
        for cid in ("skill", "skill_hr2", "skill_hr3", "skill_hr4"):
            self.assertIn(cid, self.pack.checks)

    def test_hr2(self):
        self.assertEqual(self._grade("skill_hr2", 5, 60), "大成功")
        # 目标 < 50 时不享受 1–5 大成功，按普通分级落到极难
        self.assertEqual(self._grade("skill_hr2", 5, 40), "极难成功")
        self.assertEqual(self._grade("skill_hr2", 96, 40), "大失败")

    def test_hr3(self):
        self.assertEqual(self._grade("skill_hr3", 5, 40), "大成功")
        self.assertEqual(self._grade("skill_hr3", 96, 99), "大失败")

    def test_hr4(self):
        self.assertEqual(self._grade("skill_hr4", 2, 60), "极难成功")
        self.assertEqual(self._grade("skill_hr4", 100, 99), "大失败")


class TestRollNew(unittest.TestCase):
    def setUp(self):
        from qqbot.paths import PLUGINS_DIR
        from qqbot.rulepacks import load_py_pack

        self.pack = load_py_pack(PLUGINS_DIR / "trpg" / "coc7th.py")

    def test_attributes_in_range(self):
        from qqbot import cards

        for _ in range(20):
            d = cards.roll_new(self.pack)
            self.assertTrue(15 <= d["str"] <= 90, d["str"])
            self.assertTrue(40 <= d["int"] <= 90, d["int"])
            self.assertTrue(40 <= d["edu"] <= 90, d["edu"])
            self.assertTrue(15 <= d["luck"] <= 90, d["luck"])

    def test_hp_matches_rolled(self):
        from qqbot import cards

        d = cards.roll_new(self.pack)
        self.assertEqual(d["hp"], d["hp_max"])
        self.assertEqual(d["hp_max"], (d["con"] + d["siz"]) // 10)
        self.assertEqual(d["san"], d["pow"])


class TestRollScaled(unittest.TestCase):
    def test_multiplier(self):
        from qqbot.dice import roll_scaled

        r = roll_scaled("3d6*5")
        self.assertTrue(r.ok)
        self.assertEqual(r.total % 5, 0)
        self.assertTrue(15 <= r.total <= 90)

    def test_paren(self):
        from qqbot.dice import roll_scaled

        r = roll_scaled("(2d6+6)*5")
        self.assertTrue(r.ok)
        self.assertTrue(40 <= r.total <= 90)


class TestHouseRuleAliases(unittest.TestCase):
    def test_aliases(self):
        from qqbot.app import HOUSE_ALIASES

        for text in ("1", "默认", "规则书", "default"):
            self.assertEqual(HOUSE_ALIASES[text], "default")
        for text in ("2", "房规2", "房规二", "hr2"):
            self.assertEqual(HOUSE_ALIASES[text], "hr2")
        for text in ("3", "房规三", "hr3"):
            self.assertEqual(HOUSE_ALIASES[text], "hr3")
        for text in ("4", "房规四", "hr4"):
            self.assertEqual(HOUSE_ALIASES[text], "hr4")

    def test_descriptions_cover_all(self):
        from qqbot.app import HOUSE_RULES

        for key in ("default", "hr2", "hr3", "hr4"):
            self.assertIn(key, HOUSE_RULES)
            self.assertTrue(HOUSE_RULES[key]["crit"])
            self.assertTrue(HOUSE_RULES[key]["fumble"])


class TestCodePlugins(unittest.TestCase):
    def setUp(self):
        import tempfile
        import pathlib

        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _make(self, name, source):
        from qqbot.plugins_code import read_meta

        path = self.dir / f"{name}.py"
        path.write_text(source, encoding="utf-8")
        return read_meta(path)

    def test_meta_from_ast(self):
        info = self._make(
            "demo",
            'NAME = "示例"\n'
            'DESCRIPTION = "测试用"\n'
            'COMMANDS = {"hi": "打个招呼"}\n'
            "def handle(ctx):\n"
            '    return "hello"\n',
        )
        self.assertEqual(info.name, "示例")
        self.assertEqual(info.description, "测试用")
        self.assertIn("hi", info.commands)
        self.assertFalse(info.error)
        self.assertTrue(info.file_hash)

    def test_meta_rejects_broken(self):
        info = self._make("bad", "def handle(ctx)\n    return 1\n")
        self.assertTrue(info.error)

    def test_run_plugin(self):
        import qqbot.plugins_code as pc

        info = self._make(
            "echo",
            'COMMANDS = {"echo": "重复"}\n'
            "def handle(ctx):\n"
            '    return "参数=" + ",".join(ctx.get("args") or [])\n',
        )
        out = pc.run_plugin(info, {"args": ["a", "b"]})
        self.assertEqual(out["reply"], "参数=a,b")

    def test_plugin_can_return_store(self):
        import qqbot.plugins_code as pc

        info = self._make(
            "counter",
            'COMMANDS = {"count": "计数"}\n'
            "def handle(ctx):\n"
            '    n = int(ctx.get("store", {}).get("n", 0)) + 1\n'
            '    return {"reply": str(n), "store": {"n": n}}\n',
        )
        out = pc.run_plugin(info, {"store": {"n": 4}})
        self.assertEqual(out["reply"], "5")
        self.assertEqual(out["store"], {"n": 5})

    def test_crash_returns_code(self):
        import qqbot.plugins_code as pc

        info = self._make(
            "boom",
            'COMMANDS = {"boom": "爆炸"}\n'
            "def handle(ctx):\n"
            '    raise ValueError("坏了")\n',
        )
        with self.assertRaises(pc.PluginError) as ctx:
            pc.run_plugin(info, {})
        self.assertEqual(ctx.exception.code, "E3101")

    def test_timeout_returns_code(self):
        import qqbot.plugins_code as pc

        info = self._make(
            "slow",
            'COMMANDS = {"slow": "慢"}\n'
            "def handle(ctx):\n"
            "    import time\n"
            "    time.sleep(5)\n"
            '    return "done"\n',
        )
        with self.assertRaises(pc.PluginError) as ctx:
            pc.run_plugin(info, {}, timeout=0.6)
        self.assertEqual(ctx.exception.code, "E3102")

    def test_write_blocked(self):
        import qqbot.plugins_code as pc

        target = self.dir / "hacked.txt"
        info = self._make(
            "writer",
            'COMMANDS = {"w": "写"}\n'
            "def handle(ctx):\n"
            f"    open({str(target)!r}, 'w').write('x')\n"
            '    return "ok"\n',
        )
        with self.assertRaises(pc.PluginError) as ctx:
            pc.run_plugin(info, {})
        self.assertEqual(ctx.exception.code, "E3110")
        self.assertFalse(target.exists())

    def test_fortune_game(self):
        import qqbot.plugins_code as pc
        from qqbot.paths import PLUGINS_DIR

        path = PLUGINS_DIR / "minigame" / "fortune.py"
        plugin = pc.CodePlugin(id="fortune", path=path, name="fortune")

        payload = {"user": "u1", "date": "2026-01-01", "command": "运势", "store": {}}
        first = pc.run_plugin(plugin, payload)
        self.assertRegex(first["reply"], r"^你今日的运势是 🎲 1D100 → \d{1,3}　【.+】$")

        payload["store"] = first["store"]
        second = pc.run_plugin(plugin, payload)
        self.assertIn("今天已经抽过了", second["reply"])


class TestCustomRulepack(unittest.TestCase):
    def _write(self, base, name, files):
        d = base / name
        d.mkdir()
        for fname, text in files.items():
            (d / fname).write_text(text, encoding="utf-8")
        return d

    def _manifest(self, pack_id="d10"):
        return (
            f'id: {pack_id}\n'
            "name: 测试规则\n"
            'version: "0.1"\n'
            'engine_version: ">=1.0 <2.0"\n'
            "type: rulepack\n"
            "permissions: []\n"
        )

    def test_minimal_pack(self):
        import tempfile
        import pathlib
        from qqbot import cards
        from qqbot.rulepacks import load_pack

        schema = (
            "fields:\n"
            "  - { key: hp, label: 生命, type: int, min: 1, max: 20, default: 10 }\n"
            "  - { key: atk, label: 攻击, type: int, min: 0, max: 20, default: 5 }\n"
            '  - { key: power, label: 战力, type: expr, expr: "hp + atk" }\n'
        )
        check = (
            "checks:\n"
            "  skill:\n"
            "    label: 检定\n"
            '    dice: "1d10"\n'
            "    target: atk\n"
            "    outcomes:\n"
            '      - { when: "roll == 1", label: 大成功, rank: 4 }\n'
            "      - { else: true, label: 失败, rank: 0 }\n"
        )
        with tempfile.TemporaryDirectory() as tmp:
            d = self._write(
                pathlib.Path(tmp),
                "d10",
                {
                    "manifest.yaml": self._manifest(),
                    "schema.yaml": schema,
                    "check.yaml": check,
                },
            )
            pack = load_pack(d)
            self.assertEqual(pack.id, "d10")
            self.assertIn("skill", pack.checks)
            data = cards.defaults(pack)
            self.assertEqual(data["power"], 15)

    def test_cycle_rejected(self):
        import tempfile
        import pathlib
        from qqbot.rulepacks import PackError, load_pack

        schema = (
            "fields:\n"
            '  - { key: a, label: A, type: expr, expr: "b + 1" }\n'
            '  - { key: b, label: B, type: expr, expr: "a + 1" }\n'
        )
        with tempfile.TemporaryDirectory() as tmp:
            d = self._write(
                pathlib.Path(tmp),
                "d10",
                {"manifest.yaml": self._manifest(), "schema.yaml": schema},
            )
            with self.assertRaises(PackError):
                load_pack(d)

    def test_permissions_rejected(self):
        import tempfile
        import pathlib
        from qqbot.rulepacks import PackError, load_pack

        man = self._manifest().replace("permissions: []", "permissions: [network]")
        with tempfile.TemporaryDirectory() as tmp:
            d = self._write(
                pathlib.Path(tmp), "d10", {"manifest.yaml": man}
            )
            with self.assertRaises(PackError):
                load_pack(d)


class TestRulepackSelection(unittest.TestCase):
    def test_aliases(self):
        from qqbot.commands import ALIASES, RESERVED

        self.assertEqual(ALIASES["规则包"], "rulepack")
        self.assertEqual(ALIASES["rp"], "rulepack")
        self.assertEqual(RESERVED["rulepack"], "跑团规则")

    def test_store_default_and_set(self):
        import tempfile
        import pathlib
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "g.db")
            self.assertEqual(st.group_rulepack("g1"), "")

            st.set_group_rulepack("g1", "coc7th")
            self.assertEqual(st.group_rulepack("g1"), "coc7th")

            rows = {r["group"]: r for r in st.groups()}
            self.assertEqual(rows["g1"]["rulepack"], "coc7th")
            self.assertEqual(rows["g1"]["status"], "active")

            st.set_group_rulepack("g1", "")
            self.assertEqual(st.group_rulepack("g1"), "")
            st.close()

    def test_normalize_group_rulepacks(self):
        import tempfile
        import pathlib
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "g.db")
            st.set_group_rulepack("g1", "coc7th")
            st.set_group_rulepack("g2", "dnd5e")
            st.set_group_rulepack("g3", "")

            changed = st.normalize_group_rulepacks({"dnd5e"}, "dnd5e")
            self.assertEqual(changed, 1)
            self.assertEqual(st.group_rulepack("g1"), "dnd5e")
            self.assertEqual(st.group_rulepack("g2"), "dnd5e")
            self.assertEqual(st.group_rulepack("g3"), "")
            st.close()

    def test_san_rejects_bad_amount(self):
        from qqbot import cards, checks
        from qqbot.paths import PLUGINS_DIR
        from qqbot.rulepacks import load_py_pack

        pack = load_py_pack(PLUGINS_DIR / "trpg" / "coc7th.py")
        data = cards.defaults(pack)
        data["san"] = 60

        bad = checks.run_san(pack, data, "乱写")
        self.assertFalse(bad.ok)
        self.assertIn("看不懂", bad.error)

        bad2 = checks.run_san(pack, data, "0/xyz")
        self.assertFalse(bad2.ok)

        good = checks.run_san(pack, data, "0/1d6")
        self.assertTrue(good.ok)
        self.assertIn(good.loss_expr, ("0", "1d6"))

    def test_rulepack_enabled_defaults_true(self):
        import tempfile
        import pathlib
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "p.db")
            self.assertTrue(st.rulepack_enabled("coc7th"))
            st.set_rulepack_enabled("coc7th", False)
            self.assertFalse(st.rulepack_enabled("coc7th"))
            st.set_rulepack_enabled("coc7th", True)
            self.assertTrue(st.rulepack_enabled("coc7th"))
            st.close()

    def test_rule_hook_state(self):
        import tempfile
        import pathlib
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "h.db")
            self.assertEqual(st.rule_hook_state("r"), (False, ""))
            st.set_rule_hook_enabled("r", True, "abc123")
            self.assertEqual(st.rule_hook_state("r"), (True, "abc123"))
            self.assertTrue(st.all_rule_hook_states()["r"]["enabled"])
            st.set_rule_hook_enabled("r", False, "abc123")
            self.assertFalse(st.rule_hook_state("r")[0])
            st.close()

    def test_mode_notice_store(self):
        import tempfile
        import pathlib
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "n.db")
            st.set_mode_notice("g", "当前模式：跑团")
            self.assertEqual(st.pop_mode_notice("g"), "当前模式：跑团")
            self.assertEqual(st.pop_mode_notice("g"), "")
            st.set_mode_notice("g", "x")
            st.clear_mode_notice("g")
            self.assertEqual(st.pop_mode_notice("g"), "")
            st.close()

    def test_old_rulepack_ids_are_migrated(self):
        import tempfile
        import pathlib
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "r.db"
            st = Store(path)
            st.set_group_rulepack("g1", "coc7e")
            st.set_group_rulepack("g2", "paranoia25")
            st.close()

            st = Store(path)
            self.assertEqual(st.group_rulepack("g1"), "coc7th")
            self.assertEqual(st.group_rulepack("g2"), "paranoia25th")
            st.close()

    def test_delete_all_cards(self):
        import tempfile
        import pathlib
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "c.db")
            st.put_card("m1", "coc7th", {"hp": 10})
            st.put_card("m1", "dnd5e", {"hp": 8})
            st.put_card("m2", "coc7th", {"hp": 9})

            self.assertEqual(st.delete_all_cards("m1"), 2)
            self.assertIsNone(st.get_card("m1", "coc7th"))
            self.assertIsNone(st.get_card("m1", "dnd5e"))
            self.assertIsNotNone(st.get_card("m2", "coc7th"))
            st.close()


class TestSingleFileRulepack(unittest.TestCase):
    def test_coc7th_pack(self):
        from qqbot.paths import PLUGINS_DIR
        from qqbot.rulepacks import load_py_pack

        pack = load_py_pack(PLUGINS_DIR / "trpg" / "coc7th.py")

        self.assertEqual(pack.id, "coc7th")
        self.assertEqual(len(pack.fields), 17)
        self.assertEqual(set(pack.checks), {"skill", "skill_hr2", "skill_hr3", "skill_hr4"})
        self.assertEqual(set(pack.house_rules), {"default", "hr2", "hr3", "hr4"})

        skills = [f for f in pack.fields if f.type == "skills"][0]
        self.assertEqual(len(skills.catalog), 84)

    def test_template_is_valid(self):
        from qqbot.rulepacks import RULE_TEMPLATE, load_py_source

        pack = load_py_source(RULE_TEMPLATE, "template")
        self.assertEqual(pack.id, "template")
        self.assertTrue(pack.fields)
        self.assertIn("skill", pack.checks)

    def test_py_rejects_non_literal(self):
        from qqbot.rulepacks import PackError, load_py_source

        source = (
            "def make():\n"
            "    return []\n"
            "FIELDS = make()\n"
        )
        with self.assertRaises(PackError):
            load_py_source(source, "bad")

    def test_py_rejects_missing_house_check(self):
        from qqbot.rulepacks import PackError, load_py_source

        source = (
            'FIELDS = [{"key": "hp", "label": "生命", "type": "int", "default": 10}]\n'
            'HOUSE_RULES = {"hr9": {"name": "九", "check": "nothere"}}\n'
        )
        with self.assertRaises(PackError):
            load_py_source(source, "bad")

    def test_py_preferred_over_yaml(self):
        import tempfile
        import pathlib
        from qqbot.rulepacks import load_all

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            (base / "trpg").mkdir()
            (base / "trpg" / "dup.py").write_text(
                'NAME = "PY 版"\n'
                'FIELDS = [{"key": "hp", "label": "生命", "type": "int", "default": 1}]\n',
                encoding="utf-8",
            )
            d = base / "dup"
            d.mkdir()
            (base / "minigame").mkdir()
            (base / "minigame" / "demo.py").write_text(
                'COMMANDS = {"demo": "x"}\n', encoding="utf-8"
            )
            (base / "modes").mkdir()
            (base / "modes" / "story.py").write_text(
                'LABEL = "故事"\nCALL_LLM = False\n', encoding="utf-8"
            )
            (d / "manifest.yaml").write_text(
                'id: dup\nname: YAML 版\nengine_version: ">=1.0 <2.0"\n'
                "permissions: []\n",
                encoding="utf-8",
            )
            (d / "schema.yaml").write_text(
                'fields:\n  - { key: hp, label: 生命, type: int, default: 2 }\n',
                encoding="utf-8",
            )
            packs, errors = load_all(base)
            self.assertEqual(len(packs), 1)
            self.assertEqual(packs[0].source, "py")
            self.assertEqual(packs[0].name, "PY 版")
            self.assertEqual(errors, [])


class TestRuleHooks(unittest.TestCase):
    def setUp(self):
        import tempfile
        import pathlib

        self._tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _source(self, extra=""):
        return (
            'NAME = "H"\n'
            'FIELDS = [{"key": "hp", "label": "生命", "type": "int", "min": 0, "max": 20, "default": 10},\n'
            '          {"key": "atk", "label": "攻击", "type": "int", "min": 0, "max": 20, "default": 5},\n'
            '          {"key": "power", "label": "战力", "type": "expr", "expr": "hp + atk"}]\n'
            + extra
        )

    def test_hooks_and_commands_parsed(self):
        from qqbot.rulepacks import load_py_source

        pack = load_py_source(
            self._source(
                'COMMANDS = {"fate": "抽一张命运卡"}\n'
                "def handle(ctx):\n"
                '    return "ok"\n'
                "def on_new(ctx):\n"
                '    return {}\n'
                "def on_check(ctx):\n"
                '    return {}\n'
            ),
            "hooked",
        )
        self.assertEqual(pack.hooks, {"handle", "on_new", "on_check"})
        self.assertEqual(pack.commands, {"fate": "抽一张命运卡"})

    def test_commands_require_handle(self):
        from qqbot.rulepacks import PackError, load_py_source

        with self.assertRaises(PackError):
            load_py_source(self._source('COMMANDS = {"fate": "x"}\n'), "bad")

    def test_handle_requires_commands(self):
        from qqbot.rulepacks import PackError, load_py_source

        with self.assertRaises(PackError):
            load_py_source(
                self._source("def handle(ctx):\n    return 'x'\n"), "bad"
            )

    def test_load_does_not_execute(self):
        from qqbot.rulepacks import load_py_source

        marker = self.dir / "ran.txt"
        source = self._source(f'open({str(marker)!r}, "w").write("x")\n')
        pack = load_py_source(source, "lazy")
        self.assertEqual(pack.id, "lazy")
        self.assertFalse(marker.exists())

    def test_run_named_hook(self):
        import qqbot.plugins_code as pc

        path = self.dir / "hook.py"
        path.write_text(
            self._source(
                "def on_new(ctx):\n"
                '    return {"reply": "NEW", "card": {"hp": 3}}\n'
            ),
            encoding="utf-8",
        )
        info = pc.CodePlugin(id="hook", path=path, name="hook")
        out = pc.run_plugin(info, {}, func="on_new")
        self.assertEqual(out["reply"], "NEW")
        self.assertEqual(out["card"], {"hp": 3})

    def test_apply_updates(self):
        from qqbot import cards
        from qqbot.rulepacks import load_py_source

        pack = load_py_source(self._source(), "upd")
        data = cards.defaults(pack)
        self.assertEqual(data["power"], 15)

        new, applied = cards.apply_updates(
            pack,
            data,
            {"hp": 4, "power": 99, "nope": 1, "atk": 7},
        )
        self.assertEqual(new["hp"], 4)
        self.assertEqual(new["atk"], 7)
        self.assertEqual(new["power"], 11)  # 派生值重算，不接受直接写入
        self.assertNotIn("nope", new)
        self.assertEqual(sorted(applied), ["atk", "hp"])


class TestMinigames(unittest.TestCase):
    def test_game_scopes_and_modes(self):
        from qqbot.games import discover

        games = {g.id: g for g in discover()}
        self.assertEqual((games["fishing"].scope, games["fishing"].mode), ("solo", "daily"))
        self.assertEqual((games["fortune"].scope, games["fortune"].mode), ("solo", "daily"))
        self.assertEqual((games["boss"].scope, games["boss"].mode), ("group", "daily"))
        self.assertEqual((games["blackjack"].scope, games["blackjack"].mode), ("solo", "round"))
        self.assertEqual((games["idiom"].scope, games["idiom"].mode), ("solo", "round"))

    def test_dungeon_start_status_and_stairs(self):
        import qqbot.plugins_code as pc
        from qqbot.paths import PLUGINS_DIR

        path = PLUGINS_DIR / "minigame" / "dungeon.py"
        plugin = pc.CodePlugin(id="dungeon", path=path, name="dungeon")

        start = pc.run_plugin(
            plugin,
            {
                "command": "地牢",
                "args": ["西幻"],
                "user": "u1",
                "group": "g",
                "store": {},
            },
        )
        self.assertIn("store", start)
        self.assertEqual(start["store"]["run"]["theme"], "西幻")
        self.assertEqual(start["store"]["run"]["floor"], 1)

        status = pc.run_plugin(
            plugin,
            {
                "command": "状态",
                "user": "u1",
                "group": "g",
                "store": start["store"],
            },
        )
        self.assertIn("第 1/10 层", status["reply"])

        store = {
            "run": {
                "theme": "西幻",
                "floor": 1,
                "pos": 0,
                "plan": ["stairs"],
                "hp": 30,
                "max_hp": 30,
                "atk": 3,
                "def": 0,
                "gold": 0,
                "potions": 1,
                "phase": "explore",
                "enemy": None,
            },
            "stats": {},
        }
        down = pc.run_plugin(
            plugin,
            {"command": "走", "user": "u1", "group": "g", "store": store},
        )
        self.assertEqual(down["store"]["run"]["floor"], 2)
        self.assertIn("第 2 层", down["reply"])

    def test_boss_group_state_is_shared(self):
        import qqbot.plugins_code as pc
        from qqbot.paths import PLUGINS_DIR

        path = PLUGINS_DIR / "minigame" / "boss.py"
        plugin = pc.CodePlugin(id="boss", path=path, name="boss")

        first = pc.run_plugin(
            plugin,
            {"command": "挑战", "user": "u1", "store": {}, "date": "2026-01-01"},
        )
        store = first["store"]
        self.assertIn("u1", store["daily"]["players"])
        self.assertIn("name", store["daily"])
        self.assertTrue(50 <= store["daily"]["max_hp"] <= 150)
        self.assertLess(store["daily"]["hp"], store["daily"]["max_hp"])

        second = pc.run_plugin(
            plugin,
            {"command": "挑战", "user": "u2", "store": store, "date": "2026-01-01"},
        )
        self.assertIn("u2", second["store"]["daily"]["players"])
        self.assertLess(second["store"]["daily"]["hp"], store["daily"]["hp"])

        again = pc.run_plugin(
            plugin,
            {"command": "挑战", "user": "u1", "store": second["store"], "date": "2026-01-01"},
        )
        self.assertIn("已经攻击过", again["reply"])

    def test_solo_store_is_per_player(self):
        import tempfile
        import pathlib
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "s.db")
            st.set_solo_store("fishing", "g", "a", {"daily": {"fish": "鲤鱼"}})
            st.set_solo_store("fishing", "g", "b", {"daily": {"fish": "鲫鱼"}})
            self.assertEqual(st.get_solo_store("fishing", "g", "a")["daily"]["fish"], "鲤鱼")
            self.assertEqual(st.get_solo_store("fishing", "g", "b")["daily"]["fish"], "鲫鱼")
            self.assertEqual(st.get_solo_store("fishing", "other", "a"), {})
            st.clear_solo_store("fishing", "g", "a")
            self.assertEqual(st.get_solo_store("fishing", "g", "a"), {})
            st.close()

    def test_template_parses(self):
        from qqbot.games import GAME_TEMPLATE, parse_source

        game = parse_source(GAME_TEMPLATE, "template")
        self.assertFalse(game.error, game.error)
        self.assertEqual(game.hooks, {"handle"})
        self.assertEqual(game.scope, "solo")
        self.assertEqual(game.mode, "round")
        self.assertIn("demo", game.commands)

    def test_requires_handle(self):
        from qqbot.games import parse_source

        game = parse_source('COMMANDS = {"x": "x"}\n', "bad")
        self.assertIn("handle", game.error)

    def test_requires_commands(self):
        from qqbot.games import parse_source

        game = parse_source("def handle(ctx):\n    return 'x'\n", "bad")
        self.assertIn("COMMANDS", game.error)

    def test_run_game_hooks(self):
        import tempfile
        import pathlib
        import qqbot.plugins_code as pc

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "g.py"
            path.write_text(
                'COMMANDS = {"step": "走一步"}\n'
                "def on_start(ctx):\n"
                '    return {"reply": "start", "store": {"n": 0}}\n'
                "def handle(ctx):\n"
                '    n = int(ctx["store"].get("n", 0)) + 1\n'
                '    return {"reply": str(n), "store": {"n": n}}\n',
                encoding="utf-8",
            )
            info = pc.CodePlugin(id="g", path=path, name="g")

            start = pc.run_plugin(info, {"store": {}}, func="on_start")
            self.assertEqual(start["reply"], "start")
            self.assertEqual(start["store"], {"n": 0})

            step = pc.run_plugin(info, {"store": start["store"]}, func="handle")
            self.assertEqual(step["reply"], "1")
            self.assertEqual(step["store"], {"n": 1})

    def test_store_is_per_group(self):
        import tempfile
        import pathlib
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "g.db")
            self.assertEqual(st.get_game_store("g", "a"), {})
            st.set_game_store("g", "a", {"n": 1})
            st.set_game_store("g", "b", {"n": 2})
            self.assertEqual(st.get_game_store("g", "a"), {"n": 1})
            self.assertEqual(st.get_game_store("g", "b"), {"n": 2})
            st.clear_game_store("g", "a")
            self.assertEqual(st.get_game_store("g", "a"), {})
            st.close()

    def test_game_state_default_off(self):
        import tempfile
        import pathlib
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "g.db")
            self.assertEqual(st.game_state("g"), (False, ""))
            st.set_game_enabled("g", True, "hash")
            self.assertEqual(st.game_state("g"), (True, "hash"))
            st.close()


class TestModePlugins(unittest.TestCase):
    def test_builtins(self):
        from qqbot.modes import BUILTIN_MODES

        self.assertEqual(set(BUILTIN_MODES), {"chat", "trpg", "minigame"})
        self.assertTrue(BUILTIN_MODES["chat"].call_llm)
        self.assertFalse(BUILTIN_MODES["trpg"].call_llm)
        self.assertFalse(BUILTIN_MODES["minigame"].call_llm)

    def test_template(self):
        from qqbot.modes import MODE_TEMPLATE, parse_source

        spec = parse_source(MODE_TEMPLATE, "translate")
        self.assertFalse(spec.error, spec.error)
        self.assertEqual(spec.label, "翻译模式")
        self.assertTrue(spec.call_llm)
        self.assertFalse(spec.allow_keyword)
        self.assertIn("翻译", spec.extra_prompt)

    def test_cannot_override_builtin(self):
        from qqbot.modes import parse_source

        spec = parse_source('LABEL = "假的聊天"\n', "chat")
        self.assertIn("内置", spec.error)

    def test_call_llm_must_be_bool(self):
        from qqbot.modes import parse_source

        spec = parse_source('LABEL = "x"\nCALL_LLM = "yes"\n', "bad")
        self.assertIn("CALL_LLM", spec.error)

    def test_no_llm_mode(self):
        from qqbot.modes import parse_source

        spec = parse_source(
            'LABEL = "故事"\nCALL_LLM = False\nALLOW_KEYWORD = True\n',
            "story",
        )
        self.assertFalse(spec.error)
        self.assertFalse(spec.call_llm)
        self.assertTrue(spec.allow_keyword)
        self.assertTrue(spec.help_text)


class TestModeIsolation(unittest.TestCase):
    def test_thread_and_memory_are_per_mode(self):
        import tempfile
        import pathlib
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "m.db")

            st.append_turn("g", "m", "hi", "hello", mode="chat")
            st.append_turn("g", "m", "hola", "hi", mode="translate")
            self.assertEqual(st.get_thread("g", "m")[0]["content"], "hi")
            self.assertEqual(st.get_thread("g", "m", "translate")[0]["content"], "hola")

            st.save_memory_state("g", "m", "C", [], mode="chat")
            st.save_memory_state("g", "m", "T", [], mode="translate")
            self.assertEqual(st.get_memory_state("g", "m")[0], "C")
            self.assertEqual(st.get_memory_state("g", "m", "translate")[0], "T")

            modes = {item["mode"] for item in st.list_summaries()}
            self.assertEqual(modes, {"chat", "translate"})

            st.clear_thread("g", "m")
            self.assertEqual(st.get_thread("g", "m"), [])
            self.assertTrue(st.get_thread("g", "m", "translate"))
            st.close()

    def test_old_thread_table_is_migrated(self):
        import sqlite3
        import tempfile
        import pathlib
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "old.db"
            conn = sqlite3.connect(path)
            conn.executescript(
                """
                CREATE TABLE threads (
                    group_openid TEXT NOT NULL,
                    member_openid TEXT NOT NULL,
                    messages TEXT NOT NULL DEFAULT '[]',
                    updated_at REAL NOT NULL,
                    PRIMARY KEY (group_openid, member_openid)
                );
                INSERT INTO threads VALUES
                    ('g', 'm', '[{"role":"user","content":"old"}]', 1.0);
                """
            )
            conn.commit()
            conn.close()

            st = Store(path)
            self.assertEqual(st.get_thread("g", "m")[0]["content"], "old")
            self.assertEqual(st.get_thread("g", "m", "translate"), [])
            cols = {r[1] for r in st.conn.execute("PRAGMA table_info(threads)")}
            self.assertIn("mode", cols)
            st.close()


    def test_old_groups_table_gets_mode(self):
        import sqlite3
        import tempfile
        import pathlib
        from qqbot.store import Store

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = pathlib.Path(tmp.name) / "old_groups.db"
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE groups (
                group_openid TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'pending',
                added_by TEXT,
                added_at REAL,
                note TEXT
            );
            INSERT INTO groups VALUES('g', 'active', 'u', 1.0, 'old');
            """
        )
        conn.commit()
        conn.close()

        st = Store(path)
        self.addCleanup(st.close)
        g = st.groups()[0]
        self.assertEqual(g["mode"], "chat")
        self.assertEqual(g["status"], "active")
        self.assertEqual(g["member_count"], 0)
        self.assertFalse(g["listen_enabled"])

    def test_old_quota_table_gets_token_columns(self):
        import sqlite3
        import tempfile
        import pathlib
        from qqbot.store import Store

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = pathlib.Path(tmp.name) / "old_quota.db"
        conn = sqlite3.connect(path)
        conn.executescript(
            """
            CREATE TABLE quota_daily (
                scope TEXT NOT NULL,
                scope_key TEXT NOT NULL,
                date TEXT NOT NULL,
                msgs INTEGER NOT NULL DEFAULT 0,
                tokens INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (scope, scope_key, date)
            );
            INSERT INTO quota_daily VALUES('group', 'g', '2026-11-01', 3, 99);
            """
        )
        conn.commit()
        conn.close()

        st = Store(path)
        self.addCleanup(st.close)
        cols = {r[1] for r in st.conn.execute("PRAGMA table_info(quota_daily)")}
        for name in ("prompt_tokens", "completion_tokens", "cached_tokens"):
            self.assertIn(name, cols)
        row = st.conn.execute(
            "SELECT msgs, tokens FROM quota_daily WHERE scope_key='g'"
        ).fetchone()
        self.assertEqual(tuple(row), (3, 99))


class TestParanoiaPacks(unittest.TestCase):
    def test_packs_load_as_roll_only(self):
        from qqbot.paths import PLUGINS_DIR
        from qqbot.rulepacks import load_py_pack

        p2 = load_py_pack(PLUGINS_DIR / "trpg" / "paranoia2e.py")
        p25 = load_py_pack(PLUGINS_DIR / "trpg" / "paranoia25th.py")

        for pack in (p2, p25):
            self.assertEqual(pack.reveal, "roll-only")
            self.assertEqual(pack.checks["skill"].outcomes, [])
            self.assertEqual(pack.checks["skill"].dice, "1d20")

        labels2 = [f.label for f in p2.fields]
        labels25 = [f.label for f in p25.fields]
        self.assertIn("克隆体编号", labels2)
        self.assertIn("英雄气概", labels2)
        self.assertNotIn("处世", labels2)
        self.assertIn("处世", labels25)
        self.assertIn("能量武器", labels25)
        self.assertNotIn("力量", labels25)  # 属性在 SECRET SIDE，不录

    def test_empty_outcomes_only_for_roll_only(self):
        from qqbot.rulepacks import PackError, load_py_source

        base = (
            'FIELDS = [{"key": "hp", "label": "生命", "type": "int", "default": 1}]\n'
            'CHECKS = {"skill": {"dice": "1d20", "outcomes": []}}\n'
        )
        with self.assertRaises(PackError):
            load_py_source(base, "fullpack")

        pack = load_py_source('REVEAL = "roll-only"\n' + base, "barepack")
        self.assertEqual(pack.reveal, "roll-only")
        self.assertEqual(pack.checks["skill"].outcomes, [])

    def test_paranoia_card_math(self):
        from qqbot import cards
        from qqbot.paths import PLUGINS_DIR
        from qqbot.rulepacks import load_py_pack

        p2 = load_py_pack(PLUGINS_DIR / "trpg" / "paranoia2e.py")
        data = cards.roll_new(p2)
        self.assertTrue(1 <= data["str"] <= 20)
        self.assertEqual(data["carry"], 25 + max(0, data["str"] - 12) * 5)
        self.assertIn(data["dmg_bonus"], (0, 1, 2))
        self.assertIn(data["soak"], (0, 1, 2))

        p25 = load_py_pack(PLUGINS_DIR / "trpg" / "paranoia25th.py")
        data25 = cards.defaults(p25)
        self.assertEqual(data25["energy_weapons"], 4)


class TestDndPack(unittest.TestCase):
    def setUp(self):
        from qqbot.paths import PLUGINS_DIR
        from qqbot.rulepacks import load_py_pack

        self.pack = load_py_pack(PLUGINS_DIR / "trpg" / "dnd5e.py")

    def test_pack_shape(self):
        self.assertEqual(self.pack.reveal, "full")
        self.assertGreaterEqual(len(self.pack.fields), 60)
        spec = self.pack.checks["skill"]
        self.assertEqual(spec.direction, "gte")
        self.assertEqual(spec.dc, 15)

    def test_derived_math(self):
        from qqbot import cards

        data = cards.defaults(self.pack)
        self.assertEqual(data["mod_str"], 0)
        self.assertEqual(data["prof_bonus"], 2)
        self.assertEqual(data["skill_athletics"], 0)
        self.assertEqual(data["passive_perception"], 10)

        data["str"] = 16
        data["level"] = 5
        data["prof_athletics"] = 1
        data = cards.compute(self.pack, data)
        self.assertEqual(data["mod_str"], 3)
        self.assertEqual(data["prof_bonus"], 3)
        self.assertEqual(data["skill_athletics"], 6)
        self.assertEqual(data["save_str"], 3)

    def test_check_uses_bonus_and_dc(self):
        from qqbot import cards, checks

        data = cards.defaults(self.pack)
        data["str"] = 16
        data["prof_athletics"] = 1
        data = cards.compute(self.pack, data)

        result = checks.run_check(self.pack, data, "skill", "运动", dc=10)
        self.assertTrue(result.ok)
        self.assertEqual(result.target, 5)
        self.assertEqual(result.dc, 10)
        self.assertEqual(result.direction, "gte")
        self.assertIn(result.label, ("成功", "失败"))

        save = checks.run_check(self.pack, data, "skill", "力量豁免", dc=10)
        self.assertTrue(save.ok)
        self.assertEqual(save.target, 3)

    def test_advantage_keeps_higher(self):
        from qqbot import cards, checks

        data = cards.defaults(self.pack)
        adv = checks.run_check(self.pack, data, "skill", "运动", dc=10, advantage=1)
        self.assertEqual(len(adv.rolls), 2)
        self.assertEqual(adv.roll, max(adv.rolls))

        dis = checks.run_check(self.pack, data, "skill", "运动", dc=10, advantage=-1)
        self.assertEqual(dis.roll, min(dis.rolls))

    def test_attack_natural_one_and_twenty(self):
        from qqbot import cards, checks

        data = cards.defaults(self.pack)
        data["attack_bonus"] = 5

        crit = checks.run_attack(self.pack, data, 25, seed=5)
        self.assertEqual(crit.roll, 20)
        self.assertEqual(crit.label, "重击")

        miss = checks.run_attack(self.pack, data, 5, seed=31)
        self.assertEqual(miss.roll, 1)
        self.assertEqual(miss.label, "必失")

        normal = checks.run_attack(self.pack, data, 15, seed=1)
        self.assertEqual(normal.roll, 5)
        self.assertEqual(normal.total, 10)
        self.assertEqual(normal.label, "未命中")

    def test_opposed_compares_totals(self):
        from qqbot import cards, checks

        data = cards.defaults(self.pack)
        data["str"] = 16
        data["prof_athletics"] = 1
        data = cards.compute(self.pack, data)

        result = checks.run_opposed(self.pack, data, "运动", 3, seed=7)
        self.assertTrue(result.ok)
        self.assertEqual(result.bonus, 5)
        self.assertEqual(result.own_total, result.own_roll + 5)
        self.assertEqual(result.opp_total, result.opp_roll + 3)
        self.assertIn(result.outcome, ("你胜", "对方胜", "平手，局面不变"))


class TestRetiredRulepackIds(unittest.TestCase):
    def test_old_coc7e_yaml_is_ignored(self):
        import tempfile
        import pathlib
        from qqbot.rulepacks import load_all

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            (base / "trpg").mkdir()
            (base / "trpg" / "coc7th.py").write_text(
                'NAME = "新 COC"\n'
                'FIELDS = [{"key": "hp", "label": "生命", "type": "int", "default": 1}]\n',
                encoding="utf-8",
            )
            old = base / "coc7e"
            old.mkdir()
            (old / "manifest.yaml").write_text(
                'id: coc7e\nname: 旧 COC\nengine_version: ">=1.0 <2.0"\n'
                "permissions: []\n",
                encoding="utf-8",
            )
            (old / "schema.yaml").write_text(
                "fields:\n  - { key: hp, label: 生命, type: int, default: 2 }\n",
                encoding="utf-8",
            )

            packs, errors = load_all(base)
            self.assertEqual([p.id for p in packs], ["coc7th"])
            self.assertEqual(errors, [])


class TestCocBonusDice(unittest.TestCase):
    def test_bonus_and_penalty(self):
        from qqbot.dice import roll_d100

        bonus = roll_d100(1, seed=7)
        self.assertTrue(bonus.ok)
        self.assertTrue(1 <= bonus.total <= 100)
        self.assertIn("奖励1", bonus.detail)

        penalty = roll_d100(-2, seed=7)
        self.assertTrue(penalty.ok)
        self.assertTrue(1 <= penalty.total <= 100)
        self.assertIn("惩罚2", penalty.detail)

    def test_check_accepts_bonus(self):
        from qqbot import cards, checks
        from qqbot.paths import PLUGINS_DIR
        from qqbot.rulepacks import load_py_pack

        pack = load_py_pack(PLUGINS_DIR / "trpg" / "coc7th.py")
        data = cards.defaults(pack)
        result = checks.run_check(pack, data, "skill", "侦查", bonus_dice=1)
        self.assertTrue(result.ok)
        self.assertEqual(result.bonus_dice, 1)
        self.assertTrue(result.detail)


    def test_old_py_ids_are_ignored(self):
        import tempfile
        import pathlib
        from qqbot.rulepacks import load_all

        with tempfile.TemporaryDirectory() as tmp:
            base = pathlib.Path(tmp)
            trpg = base / "trpg"
            trpg.mkdir()
            source = (
                'NAME = "新"\n'
                'FIELDS = [{"key": "hp", "label": "生命", "type": "int", "default": 1}]\n'
            )
            (trpg / "coc7th.py").write_text(source, encoding="utf-8")
            (trpg / "coc7e.py").write_text(source, encoding="utf-8")
            (trpg / "paranoia25th.py").write_text(source, encoding="utf-8")
            (trpg / "paranoia25.py").write_text(source, encoding="utf-8")

            packs, errors = load_all(base)
            self.assertEqual(sorted(p.id for p in packs), ["coc7th", "paranoia25th"])
            self.assertEqual(errors, [])


class TestWiki(unittest.TestCase):
    def test_parse_sites(self):
        from qqbot import wiki

        sites = wiki.parse_sites(
            [
                "灰机wiki|https://www.huijiwiki.com",
                "萌娘百科|https://zh.moegirl.org.cn/",
                "坏站|http://insecure.example.com",
                "带路径|https://example.com/wiki",
                "重复|https://www.huijiwiki.com",
            ]
        )
        self.assertEqual([s.name for s in sites], ["灰机wiki", "萌娘百科"])
        self.assertEqual(sites[1].base, "https://zh.moegirl.org.cn")

        text = "灰机wiki|https://www.huijiwiki.com\n\n萌娘百科|https://zh.moegirl.org.cn\n"
        self.assertEqual(len(wiki.parse_sites(text)), 2)
        self.assertEqual(wiki.parse_sites([]), [])

    def test_host_is_public_blocks_local(self):
        from qqbot import wiki

        self.assertFalse(wiki.host_is_public("localhost"))
        self.assertFalse(wiki.host_is_public("127.0.0.1"))
        self.assertFalse(wiki.host_is_public("10.0.0.1"))
        self.assertFalse(wiki.host_is_public(""))

    def test_strip_html_and_summary(self):
        from qqbot import wiki

        raw = (
            "<div><script>alert(1)</script><p>《原神》是一款<b>开放世界</b>游戏[1]。</p>"
            "<style>.x{}</style><p>第二段<br>换行</p></div>"
        )
        text = wiki.strip_html(raw)
        self.assertIn("《原神》是一款开放世界游戏[1]。", text)
        self.assertIn("第二段", text)
        self.assertNotIn("alert", text)
        self.assertNotIn("style", text)

        summary = wiki.clean_summary(raw)
        self.assertNotIn("[1]", summary)
        self.assertIn("开放世界", summary)

        long_text = "这是一个很长的段落。" * 100
        cut = wiki.clean_summary(long_text, limit=50)
        self.assertLessEqual(len(cut), 51)
        self.assertTrue(cut.endswith("。") or cut.endswith("…"))

    def test_cache_roundtrip(self):
        import pathlib
        import tempfile
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "w.db")
            self.assertIsNone(st.wiki_cache_get("k1"))
            st.wiki_cache_put("k1", "https://example.com/a", "内容", 3600)
            self.assertEqual(st.wiki_cache_get("k1"), "内容")
            st.wiki_cache_put("k2", "https://example.com/b", "过期", -1)
            self.assertIsNone(st.wiki_cache_get("k2"))
            st.close()

    def test_wiki_defaults_for_old_config(self):
        import pathlib
        import tempfile
        from qqbot import config

        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "instance.yaml"
            path.write_text("app_id: '123'\nbot_name: old\n", encoding="utf-8")
            cfg = config.load(path)
            self.assertTrue(cfg.wiki_enabled)
            self.assertEqual(len(cfg.wiki_sites), 2)

    def test_format_result(self):
        from qqbot import wiki

        hit = wiki.WikiHit("灰机wiki", "原神", "https://example.com/原神", "摘要文字")
        other = wiki.WikiHit("萌娘百科", "原神", "https://example.org/原神", "")
        text = wiki.format_result(wiki.WikiResult(True, hit=hit, others=[other]))
        self.assertIn("📖 原神", text)
        self.assertIn("摘要文字", text)
        self.assertIn("https://example.com", text)
        self.assertIn("另见", text)

        empty = wiki.format_result(wiki.WikiResult(False, error="站点超时"))
        self.assertIn("没查到", empty)


class TestWikiTranslate(unittest.TestCase):
    def _runtime(self, provider=None, translate=True):
        from types import SimpleNamespace
        from qqbot.app import Runtime

        audits = []

        class Store:
            def audit(self, action, **kw):
                audits.append((action, kw))

            def wiki_cache_get(self, key):
                return None

            def wiki_cache_put(self, *a, **k):
                pass

            def append_turn(self, *a, **k):
                raise AssertionError("wiki 查询不应该写对话历史")

            def save_memory_state(self, *a, **k):
                raise AssertionError("wiki 查询不应该写长期记忆")

        rt = Runtime.__new__(Runtime)
        rt.cfg = SimpleNamespace(
            wiki_enabled=True,
            wiki_translate=translate,
            wiki_sites=["测试站|https://example.com"],
        )
        rt.store = Store()
        rt.provider = provider
        rt._wiki_query_cache = {}
        rt._audits = audits

        tokens = []

        class Quota:
            def record_tokens(self, n):
                tokens.append(n)

            def record_usage(self, usage, provider_id=""):
                tokens.append(int((usage or {}).get("total_tokens") or 0))

        rt.quota = Quota()
        rt._tokens = tokens
        return rt

    def test_has_cjk_and_alignment(self):
        from qqbot import wiki

        self.assertTrue(wiki.has_cjk("天顶剑"))
        self.assertFalse(wiki.has_cjk("Zenith"))
        self.assertFalse(wiki.has_cjk("123 abc"))

        zh_hit = wiki.WikiHit("站", "天顶剑", "u")
        en_hit = wiki.WikiHit("站", "Zenith", "u")
        self.assertTrue(wiki.hit_aligned("天顶剑", zh_hit))
        self.assertFalse(wiki.hit_aligned("天顶剑", en_hit))
        self.assertTrue(wiki.hit_aligned("Zenith", en_hit))

    def test_translate_query_uses_provider(self):
        import asyncio
        from types import SimpleNamespace

        class Fake:
            id = "openai"

            async def complete(self, messages, *, timeout, max_tokens):
                return SimpleNamespace(text="Zenith\n")

        rt = self._runtime(Fake())
        self.assertEqual(asyncio.run(rt._translate_query("天顶剑")), "Zenith")
        # 第二次走内存缓存
        self.assertEqual(asyncio.run(rt._translate_query("天顶剑")), "Zenith")

    def test_translate_query_rejects_chinese_output(self):
        import asyncio
        from types import SimpleNamespace

        class Fake:
            id = "openai"

            async def complete(self, messages, *, timeout, max_tokens):
                return SimpleNamespace(text="天顶剑")

        rt = self._runtime(Fake())
        self.assertEqual(asyncio.run(rt._translate_query("天顶剑")), "")

    def test_mock_provider_skips_translation(self):
        import asyncio
        from qqbot.providers import MockProvider

        rt = self._runtime(MockProvider())
        self.assertEqual(asyncio.run(rt._translate_query("天顶剑")), "")

    def test_cmd_wiki_retries_with_english(self):
        import asyncio
        from types import SimpleNamespace
        from unittest import mock as umock
        from qqbot import wiki
        from qqbot.commands import Command
        from qqbot.events import GroupMessage

        class Fake:
            id = "openai"

            async def complete(self, messages, *, timeout, max_tokens):
                return SimpleNamespace(text="Zenith")

        async def fake_lookup(query, sites, cache=None, **kw):
            if query == "Zenith":
                return wiki.WikiResult(
                    True, hit=wiki.WikiHit("测试站", "Zenith", "https://e/x", "英文摘要")
                )
            return wiki.WikiResult(
                True, hit=wiki.WikiHit("测试站", "Melee weapons/yue", "https://e/y")
            )

        rt = self._runtime(Fake())
        msg = GroupMessage("g", "m", "member", "id", "/wiki 天顶剑", "", 0)

        with umock.patch.object(wiki, "lookup", fake_lookup):
            reply = asyncio.run(rt._cmd_wiki(msg, Command("wiki", ["天顶剑"])))

        self.assertIn("Zenith", reply)
        self.assertIn("已按「Zenith」检索", reply)
        # 成功的查询不写审计，只有翻译那条会记 token
        self.assertFalse(any(a[0] == "wiki.lookup" for a in rt._audits))

    def test_cmd_wiki_failure_is_audited(self):
        import asyncio
        from unittest import mock as umock
        from qqbot import wiki
        from qqbot.commands import Command
        from qqbot.events import GroupMessage

        async def fake_lookup(query, sites, cache=None, **kw):
            return wiki.WikiResult(False, error="测试站：超时")

        rt = self._runtime(None)
        msg = GroupMessage("g", "m", "member", "id", "/wiki 原神", "", 0)
        with umock.patch.object(wiki, "lookup", fake_lookup):
            reply = asyncio.run(rt._cmd_wiki(msg, Command("wiki", ["原神"])))

        self.assertIn("没查到", reply)
        rows = [a for a in rt._audits if a[0] == "wiki.lookup"]
        self.assertEqual(len(rows), 1)
        self.assertIn("超时", rows[0][1].get("reason", ""))


    def test_translate_records_tokens(self):
        import asyncio
        from types import SimpleNamespace

        class Fake:
            id = "openai"

            async def complete(self, messages, *, timeout, max_tokens):
                return SimpleNamespace(
                    text="Zenith", usage={"total_tokens": 17}
                )

        rt = self._runtime(Fake())
        asyncio.run(rt._translate_query("天顶剑"))
        self.assertEqual(rt._tokens, [17])

    def test_cmd_wiki_never_writes_history_or_memory(self):
        import asyncio
        from unittest import mock as umock
        from qqbot import wiki
        from qqbot.commands import Command
        from qqbot.events import GroupMessage

        async def fake_lookup(query, sites, cache=None, **kw):
            return wiki.WikiResult(
                True, hit=wiki.WikiHit("测试站", "原神", "https://e/x", "摘要")
            )

        rt = self._runtime(None)
        msg = GroupMessage("g", "m", "member", "id", "/wiki 原神", "", 0)
        with umock.patch.object(wiki, "lookup", fake_lookup):
            reply = asyncio.run(rt._cmd_wiki(msg, Command("wiki", ["原神"])))

        self.assertIn("原神", reply)

    def test_cmd_wiki_untranslated_shows_closest(self):
        import asyncio
        from unittest import mock as umock
        from qqbot import wiki
        from qqbot.commands import Command
        from qqbot.events import GroupMessage

        async def fake_lookup(query, sites, cache=None, **kw):
            return wiki.WikiResult(
                True, hit=wiki.WikiHit("测试站", "Melee weapons/yue", "https://e/y")
            )

        rt = self._runtime(None)  # 没有 provider，不会翻译
        msg = GroupMessage("g", "m", "member", "id", "/wiki 天顶剑", "", 0)

        with umock.patch.object(wiki, "lookup", fake_lookup):
            reply = asyncio.run(rt._cmd_wiki(msg, Command("wiki", ["天顶剑"])))

        self.assertIn("没找到「天顶剑」", reply)
        self.assertIn("最接近的是", reply)
        self.assertIn("英文关键词", reply)
        rows = [a for a in rt._audits if a[0] == "wiki.lookup"]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1].get("reason"), "no-match")

    def test_audit_prune(self):
        import pathlib
        import tempfile
        import time
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "a.db")
            st.audit("old.event", target="x")
            st.conn.execute(
                "UPDATE audit SET ts = ? WHERE action = 'old.event'",
                (time.time() - 40 * 86400,),
            )
            st.conn.commit()
            st.audit("new.event", target="y")
            self.assertEqual(st.audit_count(), 2)

            deleted = st.prune_audit(30, 5000)
            self.assertEqual(deleted, 1)
            self.assertEqual(st.audit_count(), 1)

            st.audit("another.event")
            cleared = st.prune_audit(0, 5000, purge_all=True)
            self.assertEqual(cleared, 2)
            self.assertEqual(st.audit_count(), 0)
            st.close()


class TestBuiltins(unittest.TestCase):
    def test_snapshot_and_toggle(self):
        from types import SimpleNamespace
        from qqbot import builtins as bp

        cfg = SimpleNamespace(
            wiki_enabled=True,
            repeat_enabled=False,
        )
        snap = bp.snapshot(cfg)
        self.assertEqual([b["id"] for b in snap], ["wiki", "repeat"])
        self.assertTrue(snap[0]["enabled"])
        self.assertFalse(snap[1]["enabled"])
        self.assertEqual(snap[0]["commands"], ["/wiki", "/百科"])
        self.assertEqual(snap[1]["commands"], [])

        self.assertTrue(bp.is_enabled(cfg, "wiki"))
        self.assertTrue(bp.set_enabled(cfg, "wiki", False))
        self.assertFalse(cfg.wiki_enabled)
        self.assertFalse(bp.is_enabled(cfg, "wiki"))
        self.assertTrue(bp.set_enabled(cfg, "repeat", True))
        self.assertTrue(cfg.repeat_enabled)

        self.assertFalse(bp.set_enabled(cfg, "nope", True))
        self.assertIsNone(bp.get("nope"))
        self.assertFalse(bp.is_enabled(cfg, "nope"))


class TestMemorySummary(unittest.TestCase):
    def _rt(self, provider=None):
        import pathlib
        import tempfile
        from types import SimpleNamespace
        from qqbot.app import Runtime
        from qqbot.config import InstanceConfig
        from qqbot.store import Store

        tmp = tempfile.TemporaryDirectory()
        rt = Runtime.__new__(Runtime)
        rt.cfg = InstanceConfig()
        rt.cfg.auto_summary = True
        rt.cfg.summary_trigger_tokens = 8000
        rt.store = Store(pathlib.Path(tmp.name) / "m.db")
        self.addCleanup(rt.store.close)
        rt.provider = provider

        class Quota:
            def record_tokens(self, n):
                pass

        rt.quota = Quota()
        rt._summary_busy = set()
        rt._tmp = tmp
        return rt

    def test_summarize_keeps_unprocessed(self):
        import asyncio
        from types import SimpleNamespace

        class P:
            id = "openai"

            async def complete(self, msgs, *, timeout, max_tokens):
                return SimpleNamespace(text="新的记忆", usage={"total_tokens": 9})

        rt = self._rt(P())
        pending = [{"role": "user", "content": f"消息{i}"} for i in range(35)]
        asyncio.run(rt._summarize("g", "m", "", pending, "chat"))

        summary, rest = rt.store.get_memory_state("g", "m", "chat")
        self.assertEqual(summary, "新的记忆")
        self.assertEqual(len(rest), 35 - 30)

    def test_summarize_failure_keeps_pending(self):
        import asyncio

        class Bad:
            id = "openai"

            async def complete(self, msgs, *, timeout, max_tokens):
                raise RuntimeError("boom")

        rt = self._rt(Bad())
        pending = [{"role": "user", "content": "x"} for _ in range(10)]
        asyncio.run(rt._summarize("g", "m", "", pending, "chat"))

        summary, rest = rt.store.get_memory_state("g", "m", "chat")
        self.assertEqual(summary, "")
        self.assertEqual(len(rest), 10)

    def test_queue_triggers_on_message_count(self):
        import asyncio
        from types import SimpleNamespace

        class P:
            id = "openai"

            async def complete(self, msgs, *, timeout, max_tokens):
                return SimpleNamespace(text="摘要", usage={"total_tokens": 5})

        rt = self._rt(P())
        rt.cfg.summary_trigger_messages = 20
        pending = [{"role": "user", "content": "短"} for _ in range(19)]
        rt.store.save_memory_state("g", "m", "", pending, mode="chat")

        async def flow():
            rt._queue_summary(
                "g", "m",
                [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}],
                "chat",
            )
            for _ in range(50):
                await asyncio.sleep(0.02)
                summary, _ = rt.store.get_memory_state("g", "m", "chat")
                if summary:
                    return summary
            return ""

        self.assertEqual(asyncio.run(flow()), "摘要")


class TestImages(unittest.TestCase):
    def test_allowed_url(self):
        from qqbot import images

        ok_urls = [
            "https://multimedia.nt.qq.com.cn/download?appid=1&fileid=abc",
            "https://gchat.qpic.cn/gchatpic_new/1/2-3-ABC/0?term=2",
            "https://a.b.qpic.cn/x.jpg",
        ]
        for u in ok_urls:
            self.assertTrue(images.allowed_url(u), u)

        bad = [
            "http://multimedia.nt.qq.com.cn/download",
            "https://evil.com/x.jpg",
            "https://qpic.cn.evil.com/x.jpg",
            "https://127.0.0.1/x.jpg",
            "https://user:pw@multimedia.nt.qq.com.cn/x",
            "https://multimedia.nt.qq.com.cn:8443/x",
            "",
        ]
        for u in bad:
            self.assertFalse(images.allowed_url(u), u)

    def test_image_parts(self):
        import asyncio
        from unittest import mock as umock
        from qqbot.app import Runtime
        from qqbot.config import InstanceConfig
        from qqbot.events import Attachment

        rt = Runtime.__new__(Runtime)
        rt.cfg = InstanceConfig()

        async def fake_fetch(url):
            return "data:image/png;base64,AAAA"

        with umock.patch("qqbot.images.fetch_data_url", fake_fetch):
            parts = asyncio.run(
                rt._image_parts(
                    [Attachment("image", "https://gchat.qpic.cn/x")], "这是什么"
                )
            )
        self.assertIsNotNone(parts)
        self.assertEqual(parts[0]["type"], "text")
        self.assertIn("这是什么", parts[0]["text"])
        self.assertIn("不是指令", parts[0]["text"])
        self.assertEqual(parts[1]["type"], "image_url")
        self.assertTrue(parts[1]["image_url"]["url"].startswith("data:image/png"))

    def test_image_parts_all_failed(self):
        import asyncio
        from unittest import mock as umock
        from qqbot.app import Runtime
        from qqbot.config import InstanceConfig
        from qqbot.events import Attachment

        rt = Runtime.__new__(Runtime)
        rt.cfg = InstanceConfig()

        async def fake_fetch(url):
            return None

        with umock.patch("qqbot.images.fetch_data_url", fake_fetch):
            parts = asyncio.run(
                rt._image_parts([Attachment("image", "https://gchat.qpic.cn/x")], "")
            )
        self.assertIsNone(parts)

    def test_multimodal_message_and_mock(self):
        import asyncio
        from qqbot.providers import MockProvider, build_messages
        from qqbot.providers.base import ChatMessage

        msgs = build_messages("sys", [], [
            {"type": "text", "text": "看图"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AA"}},
        ])
        self.assertEqual(msgs[-1].content[0]["text"], "看图")
        self.assertIsInstance(msgs[-1].content, list)

        comp = asyncio.run(MockProvider().complete(msgs, timeout=5, max_tokens=100))
        self.assertIn("看图", comp.text)
        self.assertEqual(ChatMessage("user", "x").to_dict()["content"], "x")


    def test_generate_with_image_vision_off(self):
        import asyncio
        from types import SimpleNamespace
        from qqbot.app import Runtime
        from qqbot.config import InstanceConfig
        from qqbot.events import Attachment, GroupMessage

        class P:
            id = "openai"

            def __init__(self):
                self.called = False

            async def complete(self, messages, *, timeout, max_tokens):
                self.called = True
                return SimpleNamespace(text="看到了", usage={"total_tokens": 3})

        class Store:
            def get_thread(self, *a, **k):
                return []

            def get_summary(self, *a, **k):
                return ""

            def append_turn(self, *a, **k):
                return []

        class Quota:
            def record_tokens(self, n):
                pass

        rt = Runtime.__new__(Runtime)
        rt.cfg = InstanceConfig()
        rt.cfg.vision_enabled = False
        rt.provider = P()
        rt.store = Store()
        rt.quota = Quota()
        rt.error = ""

        msg = GroupMessage(
            "g", "m", "member", "id", "", "", 0,
            attachments=(Attachment("image", "https://gchat.qpic.cn/x"),),
        )
        reply = asyncio.run(rt._generate(msg))
        self.assertIn("看不了图片", reply)
        self.assertFalse(rt.provider.called)

    def test_generate_with_image_vision_on(self):
        import asyncio
        from types import SimpleNamespace
        from unittest import mock as umock
        from qqbot.app import Runtime
        from qqbot.config import InstanceConfig
        from qqbot.events import Attachment, GroupMessage

        class P:
            id = "openai"

            def __init__(self):
                self.messages = None

            async def complete(self, messages, *, timeout, max_tokens):
                self.messages = messages
                return SimpleNamespace(text="看到了", usage={"total_tokens": 3})

        class Store:
            def get_thread(self, *a, **k):
                return []

            def get_summary(self, *a, **k):
                return ""

            def append_turn(self, *a, **k):
                return []

        class Quota:
            def record_tokens(self, n):
                pass

        rt = Runtime.__new__(Runtime)
        rt.cfg = InstanceConfig()
        rt.cfg.vision_enabled = True
        rt.provider = P()
        rt.store = Store()
        rt.quota = Quota()
        rt.error = ""

        async def fake_fetch(url):
            return "data:image/png;base64,AAAA"

        msg = GroupMessage(
            "g", "m", "member", "id", "", "", 0,
            attachments=(Attachment("image", "https://gchat.qpic.cn/x"),),
        )
        with umock.patch("qqbot.images.fetch_data_url", fake_fetch):
            reply = asyncio.run(rt._generate(msg))

        self.assertEqual(reply, "看到了")
        content = rt.provider.messages[-1].content
        self.assertIsInstance(content, list)
        self.assertEqual(content[1]["type"], "image_url")


    def test_allowed_mime(self):
        from qqbot.images import ALLOWED_MIME

        for mime in ("image/png", "image/jpeg", "image/webp", "image/gif"):
            self.assertIn(mime, ALLOWED_MIME)
        for mime in ("image/svg+xml", "text/html", "application/octet-stream"):
            self.assertNotIn(mime, ALLOWED_MIME)

    def test_image_parts_order(self):
        import asyncio
        from unittest import mock as umock
        from qqbot.app import Runtime
        from qqbot.config import InstanceConfig
        from qqbot.events import Attachment

        rt = Runtime.__new__(Runtime)
        rt.cfg = InstanceConfig()

        async def fake_fetch(url):
            await asyncio.sleep(0.01)
            return "data:image/png;base64," + url[-1]

        atts = [
            Attachment("image", "https://gchat.qpic.cn/1"),
            Attachment("image", "https://gchat.qpic.cn/2"),
        ]
        with umock.patch("qqbot.images.fetch_data_url", fake_fetch):
            parts = asyncio.run(rt._image_parts(atts, ""))
        self.assertEqual(len(parts), 3)
        self.assertTrue(parts[1]["image_url"]["url"].endswith("1"))
        self.assertTrue(parts[2]["image_url"]["url"].endswith("2"))

    def test_generate_image_provider_error(self):
        import asyncio
        from qqbot.app import Runtime
        from qqbot.config import InstanceConfig
        from qqbot.events import Attachment, GroupMessage

        class Bad:
            id = "openai"

            async def complete(self, messages, *, timeout, max_tokens):
                raise RuntimeError("HTTP 400 image not supported")

        class Store:
            def get_thread(self, *a, **k):
                return []

            def get_summary(self, *a, **k):
                return ""

            def append_turn(self, *a, **k):
                return []

        class Quota:
            def record_tokens(self, n):
                pass

        rt = Runtime.__new__(Runtime)
        rt.cfg = InstanceConfig()
        rt.cfg.vision_enabled = True
        rt.provider = Bad()
        rt.store = Store()
        rt.quota = Quota()
        rt.error = ""

        async def fake_fetch(url):
            return "data:image/png;base64,AAAA"

        msg = GroupMessage(
            "g", "m", "member", "id", "", "", 0,
            attachments=(Attachment("image", "https://gchat.qpic.cn/x"),),
        )
        from unittest import mock as umock

        with umock.patch("qqbot.images.fetch_data_url", fake_fetch):
            reply = asyncio.run(rt._generate(msg))
        self.assertIn("图片没能交给模型", reply)
        self.assertIn("HTTP 400", reply)

    def test_normalize_image(self):
        try:
            from PIL import Image
        except Exception:
            self.skipTest("没有 Pillow")
        import io
        from qqbot.images import normalize_image

        buf = io.BytesIO()
        Image.new("RGB", (2000, 1200), (200, 30, 30)).save(buf, "PNG")
        raw = buf.getvalue()
        out, ctype = normalize_image(raw, "image/png")
        self.assertEqual(ctype, "image/jpeg")
        self.assertLess(len(out), len(raw))
        with Image.open(io.BytesIO(out)) as im:
            self.assertLessEqual(max(im.size), 1280)

    def test_normalize_png_with_alpha(self):
        try:
            from PIL import Image
        except Exception:
            self.skipTest("没有 Pillow")
        import io
        from qqbot.images import normalize_image

        buf = io.BytesIO()
        Image.new("RGBA", (64, 64), (0, 0, 0, 0)).save(buf, "PNG")
        out, ctype = normalize_image(buf.getvalue(), "image/png")
        self.assertTrue(out)
        self.assertIn(ctype, ("image/jpeg", "image/png"))

    def test_generate_image_content_filter(self):
        import asyncio
        from qqbot import errors
        from qqbot.app import Runtime
        from qqbot.config import InstanceConfig
        from qqbot.events import Attachment, GroupMessage

        class Bad:
            id = "openai"

            async def complete(self, messages, *, timeout, max_tokens):
                raise errors.BotError(
                    errors.LLM_BAD_RESPONSE,
                    "模型返回错误（HTTP 400）",
                    detail={"body": '{"error":"safety filter: content_filter"}'},
                )

        class Store:
            def get_thread(self, *a, **k):
                return []

            def get_summary(self, *a, **k):
                return ""

            def append_turn(self, *a, **k):
                return []

        class Quota:
            def record_tokens(self, n):
                pass

        rt = Runtime.__new__(Runtime)
        rt.cfg = InstanceConfig()
        rt.cfg.vision_enabled = True
        rt.provider = Bad()
        rt.store = Store()
        rt.quota = Quota()
        rt.error = ""

        async def fake_fetch(url):
            return "data:image/jpeg;base64,AAAA"

        msg = GroupMessage(
            "g", "m", "member", "id", "", "", 0,
            attachments=(Attachment("image", "https://gchat.qpic.cn/x"),),
        )
        from unittest import mock as umock

        with umock.patch("qqbot.images.fetch_data_url", fake_fetch):
            reply = asyncio.run(rt._generate(msg))
        self.assertIn("安全过滤", reply)
        self.assertIn("换一张图", reply)

    def test_test_png(self):
        import base64
        from qqbot.images import TEST_PNG_B64

        raw = base64.b64decode(TEST_PNG_B64)
        self.assertTrue(raw.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(int.from_bytes(raw[16:20], "big"), 32)
        self.assertEqual(int.from_bytes(raw[20:24], "big"), 32)


class TestContentNormalize(unittest.TestCase):
    def test_content_shapes(self):
        from qqbot.providers.openai_compat import _content_text

        self.assertEqual(_content_text(" 红色 "), "红色")
        self.assertEqual(
            _content_text([{"type": "text", "text": "红"}, {"text": "色"}]), "红色"
        )
        self.assertEqual(_content_text({"text": "纯红"}), "纯红")
        self.assertEqual(_content_text(None), "")
        self.assertEqual(_content_text([{"type": "image_url"}]), "")


class TestModeGating(unittest.TestCase):
    def _rt(self, mode="chat"):
        from qqbot import modes as mode_plugins
        from qqbot.app import Runtime

        class Store:
            def __init__(self):
                self.mode = mode

            def group_mode(self, g):
                return self.mode

            def set_group_mode(self, g, m):
                self.mode = m

            def clear_mode_notice(self, g):
                pass

            def audit(self, *a, **k):
                pass

        rt = Runtime.__new__(Runtime)
        rt.modes = dict(mode_plugins.BUILTIN_MODES)
        rt.store = Store()
        rt.game_commands = {"运势": "fortune"}
        rt.code_commands = {"hello": "p"}
        rt.cfg = type("C", (), {"wiki_enabled": True})()
        rt.games = {}
        rt.active_rule_hooks = set()
        rt.pack_for = lambda g: None
        return rt

    def test_mode_command_shows_current(self):
        from qqbot.commands import Command
        from qqbot.events import GroupMessage

        msg = GroupMessage("g", "m", "member", "id", "/mode", "", 0)
        rt = self._rt("trpg")
        reply = rt._cmd_mode(msg, Command("mode", []))
        self.assertIn("当前模式", reply)
        self.assertIn("跑团", reply)
        self.assertEqual(rt.store.mode, "trpg")

    def test_mode_switch_requires_role(self):
        from qqbot.commands import Command
        from qqbot.events import GroupMessage

        msg = GroupMessage("g", "m", "member", "id", "/mode trpg", "", 0)
        rt = self._rt("chat")
        reply = rt._cmd_mode(msg, Command("mode", ["trpg"]))
        self.assertIn("群主", reply)
        self.assertEqual(rt.store.mode, "chat")

    def test_trpg_commands_blocked_outside_trpg(self):
        import asyncio
        from qqbot.commands import Command
        from qqbot.events import GroupMessage

        rt = self._rt("chat")
        msg = GroupMessage("g", "m", "member", "id", "/check 侦查", "", 0)
        for mode in ("chat", "minigame"):
            out = asyncio.run(rt._run_command(msg, Command("check", ["侦查"]), mode))
            self.assertIsNone(out)

    def test_game_commands_blocked_in_trpg(self):
        import asyncio
        from qqbot.commands import Command
        from qqbot.events import GroupMessage

        rt = self._rt("trpg")
        msg = GroupMessage("g", "m", "member", "id", "/运势", "", 0)
        self.assertIsNone(
            asyncio.run(rt._run_command(msg, Command("运势", []), "trpg"))
        )


class TestNewReplyFeatures(unittest.TestCase):
    def test_split_human(self):
        from qqbot.textutil import split_human

        self.assertEqual(
            split_human("第一句话。第二句话！第三句话？"),
            ["第一句话", "第二句话！", "第三句话？"],
        )
        self.assertEqual(split_human("短句", 3), ["短句"])
        self.assertEqual(len(split_human("甲。乙。丙。丁。戊。", 3)), 3)
        self.assertEqual(len(split_human("甲。乙。丙。", 1)), 1)

    def test_style_prompt(self):
        from qqbot import prompts
        from qqbot.config import InstanceConfig

        cfg = InstanceConfig(style_prompt="像朋友聊天，句子短一点。")
        text = prompts.compose(cfg)
        self.assertIn("【回复风格】", text)
        self.assertIn("像朋友聊天，句子短一点。", text)
        self.assertLess(text.index("【禁止事项】"), text.index("【回复风格】"))

    def test_store_listen_and_proactive(self):
        import pathlib
        import tempfile
        from qqbot.store import Store

        with tempfile.TemporaryDirectory() as tmp:
            st = Store(pathlib.Path(tmp) / "l.db")
            st.set_group_rulepack("g", "coc7th")
            self.assertFalse(st.group_listen("g"))
            st.set_group_listen("g", True)
            self.assertTrue(st.group_listen("g"))
            self.assertEqual(st.proactive_state("g"), ("", 0, 0.0))
            st.bump_proactive("g", "2026-11-09")
            st.bump_proactive("g", "2026-11-09")
            d, c, last = st.proactive_state("g")
            self.assertEqual((d, c), ("2026-11-09", 2))
            self.assertGreater(last, 0)
            st.bump_proactive("g", "2026-11-10")
            d, c, _ = st.proactive_state("g")
            self.assertEqual((d, c), ("2026-11-10", 1))
            st.close()

    def _listen_rt(self, **cfg_kw):
        from qqbot.app import Runtime
        from qqbot.config import InstanceConfig

        class Store:
            def __init__(self):
                self.state = ("", 0, 0.0)
                self.bumped = 0
                self.listen = True

            def group_listen(self, g):
                return self.listen

            def group_mode(self, g):
                return "chat"

            def proactive_state(self, g):
                return self.state

            def bump_proactive(self, g, date):
                self.bumped += 1
                self.state = (date, self.state[1] + 1, 1e18)

        rt = Runtime.__new__(Runtime)
        rt.cfg = InstanceConfig(**cfg_kw)
        rt.store = Store()
        return rt

    def test_listen_decision(self):
        from qqbot.events import GroupMessage

        msg = GroupMessage("g", "m", "member", "id", "今天好热啊", "", 0, mentioned=False)
        rt = self._listen_rt(listen_enabled=True, listen_probability=100)
        self.assertTrue(rt._listen_ok(msg))
        rt = self._listen_rt(listen_enabled=False, listen_probability=100)
        self.assertFalse(rt._listen_ok(msg))
        rt = self._listen_rt(listen_enabled=True, listen_probability=0)
        self.assertFalse(rt._listen_ok(msg))
        rt = self._listen_rt(
            listen_enabled=True, listen_probability=0, listen_keywords=["好热"]
        )
        self.assertTrue(rt._listen_ok(msg))
        rt = self._listen_rt(listen_enabled=True, listen_probability=100)
        rt.store.state = (__import__("time").strftime("%Y-%m-%d"), 5, 1e18)
        rt.cfg.listen_daily_limit = 5
        self.assertFalse(rt._listen_ok(msg))
        rt = self._listen_rt(listen_enabled=True, listen_probability=100)
        rt.store.state = (
            __import__("time").strftime("%Y-%m-%d"),
            1,
            __import__("time").time(),
        )
        rt.cfg.listen_cooldown_s = 999
        self.assertFalse(rt._listen_ok(msg))

    def test_listen_master_off_warns_once(self):
        from qqbot.events import GroupMessage

        msg = GroupMessage("g", "m", "member", "id", "今天好热啊", "", 0, mentioned=False)
        rt = self._listen_rt(listen_enabled=False, listen_probability=100)
        with self.assertLogs("qqbot.app", level="INFO") as logs:
            self.assertFalse(rt._listen_ok(msg))
            self.assertFalse(rt._listen_ok(msg))
        text = "\n".join(logs.output)
        self.assertEqual(text.count("监听总开关未开启"), 1)

    def test_send_without_at(self):
        import asyncio
        from qqbot.app import Runtime
        from qqbot.config import InstanceConfig
        from qqbot.events import GroupMessage

        class Sender:
            def __init__(self, fail=False):
                self.calls = []
                self.fail = fail

            async def send_group_text(self, group, text, **kw):
                self.calls.append(("active", text))
                if self.fail:
                    raise RuntimeError("no permission")
                return "id"

            async def reply(self, msg, text, seq):
                self.calls.append(("passive", text))
                return "id"

        class Store:
            def next_msg_seq(self, mid):
                return 1

        msg = GroupMessage("g", "m", "member", "id", "hi", "", 0)
        rt = Runtime.__new__(Runtime)
        rt.cfg = InstanceConfig(reply_without_at=True)
        rt.store = Store()
        rt.sender = Sender()
        rt.reply_count = 0
        rt.error = ""
        asyncio.run(rt._send_text(msg, "你好"))
        self.assertEqual(rt.sender.calls, [("active", "你好")])

        rt.sender = Sender(fail=True)
        asyncio.run(rt._send_text(msg, "你好"))
        self.assertEqual([c[0] for c in rt.sender.calls], ["active", "passive"])


class TestListenFlow(unittest.TestCase):
    def _rt(self, **cfg_kw):
        import pathlib
        import tempfile
        from qqbot import modes as mode_plugins
        from qqbot.app import Runtime
        from qqbot.config import InstanceConfig
        from qqbot.store import Store
        from qqbot.providers.base import Completion

        class Sender:
            def __init__(self):
                self.calls = []

            async def send_group_text(self, group, text, **kw):
                self.calls.append(("active", text))
                return "id"

            async def reply(self, msg, text, seq):
                self.calls.append(("passive", text))
                return "id"

        class Quota:
            def allow_message(self, g):
                return True

            def record_message(self, g):
                pass

            def record_tokens(self, n):
                pass

        class Win:
            def hit(self, key):
                return 0

        class Provider:
            id = "openai"

            async def complete(self, messages, *, timeout, max_tokens):
                return Completion(text="第一句。第二句。第三句。", usage={"total_tokens": 3})

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        st = Store(pathlib.Path(tmp.name) / "listen.db")
        self.addCleanup(st.close)
        st.set_group_rulepack("g", "coc7th")
        st.set_group_status("g", "active")
        st.set_group_listen("g", True)
        st.set_group_mode("g", "chat")

        rt = Runtime.__new__(Runtime)
        rt.cfg = InstanceConfig(**cfg_kw)
        rt.cfg.abuse_enabled = False
        rt.cfg.auto_summary = False
        rt.store = st
        rt.modes = dict(mode_plugins.BUILTIN_MODES)
        rt.provider = Provider()
        rt.sender = Sender()
        rt.quota = Quota()
        rt.global_window = Win()
        rt.group_window = Win()
        rt.games = {}
        rt.game_commands = {}
        rt.code_commands = {}
        rt.code_plugins = {}
        rt.active_rule_hooks = set()
        rt.msg_count = 0
        rt.reply_count = 0
        rt.drop_count = 0
        rt._last_msg = {}
        rt._last_prune = 1e18
        rt._summary_busy = set()
        rt._wiki_query_cache = {}
        rt.error = ""
        rt.pack_for = lambda g: None
        return rt

    def test_proactive_reply_and_multi(self):
        import asyncio
        from qqbot.events import GroupMessage

        rt = self._rt(
            listen_enabled=True,
            listen_probability=100,
            listen_min_chars=1,
            listen_cooldown_s=0,
            listen_daily_limit=0,
            multi_message=True,
            multi_message_max=3,
            multi_message_delay_ms=0,
        )
        msg = GroupMessage("g", "m", "member", "id", "今天好热", "", 0, mentioned=False)
        asyncio.run(rt._handle_group_message(msg))
        self.assertEqual(len(rt.sender.calls), 3)
        self.assertTrue(all(c[0] == "passive" for c in rt.sender.calls))
        thread = rt.store.get_thread("g", "m", "chat")
        self.assertEqual([m["role"] for m in thread], ["user", "assistant"])
        self.assertEqual(thread[0]["content"], "今天好热")
        self.assertEqual(thread[1]["content"], "第一句。第二句。第三句。")

    def test_proactive_memory_has_recent_context(self):
        import asyncio
        from qqbot.events import GroupMessage

        rt = self._rt(
            listen_enabled=True,
            listen_probability=0,
            listen_min_chars=1,
            listen_cooldown_s=0,
            listen_daily_limit=0,
        )
        m1 = GroupMessage("g", "m1", "member", "c1", "前面那句话", "", 1, mentioned=False)
        m2 = GroupMessage("g", "m2", "member", "c2", "另一句", "", 2, mentioned=False)
        asyncio.run(rt._handle_group_message(m1))
        asyncio.run(rt._handle_group_message(m2))

        rt.cfg.listen_probability = 100
        m3 = GroupMessage("g", "m", "member", "c3", "现在这句", "", 3, mentioned=False)
        asyncio.run(rt._handle_group_message(m3))

        thread = rt.store.get_thread("g", "m", "chat")
        self.assertEqual(len(thread), 2)
        self.assertIn("【最近的群聊】", thread[0]["content"])
        self.assertIn("前面那句话", thread[0]["content"])
        self.assertIn("另一句", thread[0]["content"])
        self.assertIn("现在这句", thread[0]["content"])

    def test_proactive_ignores_commands(self):
        import asyncio
        from qqbot.events import GroupMessage

        rt = self._rt(
            listen_enabled=True,
            listen_probability=100,
            listen_min_chars=1,
            listen_cooldown_s=0,
            listen_daily_limit=0,
        )
        msg = GroupMessage("g", "m", "member", "id", "/pc new", "", 0, mentioned=False)
        asyncio.run(rt._handle_group_message(msg))
        self.assertEqual(rt.sender.calls, [])

    def test_proactive_without_at_uses_active(self):
        import asyncio
        from qqbot.events import GroupMessage

        rt = self._rt(
            listen_enabled=True,
            listen_probability=100,
            listen_min_chars=1,
            listen_cooldown_s=0,
            listen_daily_limit=0,
            reply_without_at=True,
        )
        msg = GroupMessage("g", "m", "member", "id", "今天好热", "", 0, mentioned=False)
        asyncio.run(rt._handle_group_message(msg))
        self.assertEqual([c[0] for c in rt.sender.calls], ["active"])


class TestBatchFeatures(unittest.TestCase):
    def test_split_human_strips_period(self):
        from qqbot.textutil import split_human

        self.assertEqual(
            split_human("第一句话。第二句话！第三句话？", 3),
            ["第一句话", "第二句话！", "第三句话？"],
        )
        self.assertEqual(split_human("真的吗？？？", 3), ["真的吗？？？"])

    def test_quota_usage_breakdown(self):
        import pathlib
        import tempfile
        from qqbot.config import InstanceConfig
        from qqbot.quota import Quota
        from qqbot.store import Store

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        st = Store(pathlib.Path(tmp.name) / "q.db")
        self.addCleanup(st.close)
        q = Quota(st, InstanceConfig())
        q.record_usage(
            {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
                "prompt_tokens_details": {"cached_tokens": 3},
            },
            "openai",
        )
        snap = q.snapshot()
        self.assertEqual(snap["tokens"], 15)
        self.assertEqual(snap["prompt_tokens"], 10)
        self.assertEqual(snap["completion_tokens"], 5)
        self.assertEqual(snap["cached_tokens"], 3)

        q.record_usage({"total_tokens": 99}, "mock")
        self.assertEqual(q.snapshot()["tokens"], 15)

        q.record_usage({"prompt_tokens": 2, "completion_tokens": 3}, "openai")
        self.assertEqual(q.snapshot()["tokens"], 20)

    def test_group_member_count(self):
        import pathlib
        import tempfile
        from qqbot.store import Store

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        st = Store(pathlib.Path(tmp.name) / "m.db")
        self.addCleanup(st.close)
        st.set_group_rulepack("g", "coc7th")
        self.assertEqual(st.group_member_count("g"), 0)
        st.set_group_member_count("g", 42)
        self.assertEqual(st.group_member_count("g"), 42)
        row = [g for g in st.groups() if g["group"] == "g"][0]
        self.assertEqual(row["member_count"], 42)

    def test_group_reply_overrides_effective(self):
        rt = self._rt()
        rt.store.set_group_reply(
            "g",
            {
                "fallback_reply": "群专用兜底",
                "chunk_limit": 500,
                "multi_message": True,
            },
        )
        rs = rt.reply_settings("g")
        self.assertEqual(rs.fallback_reply, "群专用兜底")
        self.assertEqual(rs.chunk_limit, 500)
        self.assertTrue(rs.multi_message)
        self.assertEqual(rs.max_chunks, rt.cfg.max_chunks)
        self.assertEqual(rs.fallback_reply, "群专用兜底")

        rt.apply_group_reply(
            "g",
            {
                "chunk_limit": 9999,
                "multi_message_max": 99,
                "listen_keywords": ["热", " 热 ", ""],
                "listen_enabled": True,
            },
        )
        rs = rt.reply_settings("g")
        self.assertEqual(rs.chunk_limit, 4000)
        self.assertEqual(rs.multi_message_max, 5)
        self.assertEqual(rs.listen_keywords, ["热", "热"])
        self.assertTrue(rt.store.group_listen("g"))

        rt.apply_group_reply(
            "g",
            {"clear": ["chunk_limit", "multi_message", "listen_keywords", "bogus"]},
        )
        rs = rt.reply_settings("g")
        self.assertEqual(rs.chunk_limit, rt.cfg.chunk_limit)
        self.assertEqual(rs.multi_message, rt.cfg.multi_message)
        self.assertEqual(rs.listen_keywords, list(rt.cfg.listen_keywords))
        self.assertEqual(rt.store.get_group_reply("g").get("fallback_reply"), "群专用兜底")

    def test_cross_group_memory_is_injected(self):
        import asyncio
        from types import SimpleNamespace
        from qqbot.events import GroupMessage

        seen = []

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                seen.append(messages)
                return SimpleNamespace(text="好", usage={"total_tokens": 2})

        rt = self._rt()
        rt.provider = Provider()
        rt.store.save_memory_state("g1", "U1", "群1记忆", [], mode="chat")
        rt.store.save_memory_state("g2", "U1", "群2记忆", [], mode="chat")
        msg = GroupMessage(
            "g2", "m2", "member", "id", "在吗", "", 0,
            mentioned=True, union_openid="U1",
        )
        asyncio.run(rt._generate(msg))
        system = seen[0][0].content
        self.assertIn("【历史对话摘要】", system)
        self.assertIn("群2记忆", system)
        self.assertIn("【该用户在其他群的记忆】", system)
        self.assertIn("群1记忆", system)

    def test_memory_injection_is_not_truncated(self):
        import asyncio
        from types import SimpleNamespace
        from qqbot.events import GroupMessage

        seen = []

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                seen.append(messages)
                return SimpleNamespace(text="好", usage={})

        rt = self._rt()
        rt.provider = Provider()
        current = "当前群记忆开头" + "甲" * 1800 + "当前群记忆结尾"
        cross = "其他群记忆开头" + "乙" * 1800 + "其他群记忆结尾"
        rt.store.save_memory_state("g1", "U1", cross, [], mode="chat")
        rt.store.save_memory_state("g2", "U1", current, [], mode="chat")
        msg = GroupMessage(
            "g2", "m2", "member", "id", "在吗", "", 0,
            mentioned=True, union_openid="U1",
        )
        asyncio.run(rt._generate(msg))
        system = seen[0][0].content
        self.assertIn(current, system)
        self.assertIn(cross, system)
        self.assertEqual(
            rt.store.get_summary("g2", "U1", "chat"), current
        )

    def _rt(self, **cfg_kw):
        import pathlib
        import tempfile
        from qqbot import modes as mode_plugins
        from qqbot.app import Runtime
        from qqbot.config import InstanceConfig
        from qqbot.store import Store

        class Sender:
            def __init__(self):
                self.calls = []

            async def send_group_text(self, group, text, **kw):
                self.calls.append(text)
                return "id"

            async def reply(self, msg, text, seq):
                self.calls.append(text)
                return "id"

        class Quota:
            def record_tokens(self, n):
                pass

            def record_usage(self, usage, provider_id=""):
                pass

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        st = Store(pathlib.Path(tmp.name) / "b.db")
        self.addCleanup(st.close)
        st.set_group_rulepack("g", "coc7th")
        st.set_group_mode("g", "chat")
        st.set_group_listen("g", True)

        rt = Runtime.__new__(Runtime)
        rt.cfg = InstanceConfig(**cfg_kw)
        rt.store = st
        rt.modes = dict(mode_plugins.BUILTIN_MODES)
        rt.sender = Sender()
        rt.quota = Quota()
        rt.provider = None
        rt.secrets = {"llm_keys": {}}
        rt.reply_count = 0
        rt.error = ""
        return rt

    def test_repeat_decision_and_echo(self):
        import asyncio
        from qqbot.events import GroupMessage

        msg = GroupMessage("g", "m", "member", "id", "今天好热。", "", 0, mentioned=False)
        rt = self._rt(repeat_enabled=True, repeat_probability=100, repeat_max_chars=40)
        self.assertTrue(rt._repeat_ok(msg))
        asyncio.run(rt._do_repeat(msg))
        self.assertEqual(rt.sender.calls, ["今天好热"])
        self.assertEqual(rt.store.get_thread("g", "m", "chat"), [])
        self.assertEqual(rt.repeat_mem().stats("g")["repeat"]["count"], 1)

        rt = self._rt(repeat_enabled=True, repeat_probability=0)
        self.assertFalse(rt._repeat_ok(msg))
        rt = self._rt(repeat_enabled=True, repeat_probability=100, repeat_max_chars=2)
        self.assertFalse(rt._repeat_ok(msg))
        cmd = GroupMessage("g", "m", "member", "id", "/pc new", "", 0, mentioned=False)
        rt = self._rt(repeat_enabled=True, repeat_probability=100)
        self.assertFalse(rt._repeat_ok(cmd))

    def test_repeat_mode_semantics(self):
        import asyncio
        from types import SimpleNamespace
        from qqbot.events import GroupMessage

        msg = GroupMessage("g", "m", "member", "id", "今天好热", "", 0, mentioned=False)

        class Boom:
            id = "openai"

            async def complete(self, *a, **k):
                raise AssertionError("只允许复读时不应调用模型")

        rt = self._rt(repeat_mode="repeat", repeat_enabled=True)
        rt.provider = Boom()
        asyncio.run(rt._do_repeat(msg))
        self.assertEqual(rt.sender.calls, ["今天好热"])

        rt = self._rt(repeat_mode="banter", repeat_enabled=True)
        rt.provider = None
        asyncio.run(rt._do_repeat(msg))
        self.assertEqual(rt.sender.calls, [])

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                return SimpleNamespace(
                    text="这就热上了", usage={"total_tokens": 3}
                )

        rt = self._rt(repeat_mode="banter", repeat_enabled=True)
        rt.provider = Provider()
        asyncio.run(rt._do_repeat(msg))
        self.assertEqual(rt.sender.calls, ["这就热上了"])

    def test_repeat_and_banter_write_stats_only(self):
        import asyncio
        from types import SimpleNamespace
        from qqbot.events import GroupMessage

        msg = GroupMessage("g", "m", "member", "id", "今天好热。", "", 0, mentioned=False)

        rt = self._rt(repeat_mode="repeat", repeat_enabled=True)
        asyncio.run(rt._do_repeat(msg))
        self.assertEqual(rt.store.get_thread("g", "m", "chat"), [])
        self.assertEqual(rt.repeat_mem().stats("g")["repeat"]["count"], 1)
        memes = rt.repeat_mem().top_memes("g", kind="repeat")
        self.assertEqual(memes[0]["text"], "今天好热。")
        self.assertEqual(memes[0]["count"], 1)

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                return SimpleNamespace(text="好活", usage={"total_tokens": 3})

        rt = self._rt(repeat_mode="banter", repeat_enabled=True)
        rt.provider = Provider()
        asyncio.run(rt._do_repeat(msg))
        self.assertEqual(rt.store.get_thread("g", "m", "chat"), [])
        self.assertEqual(rt.repeat_mem().stats("g")["banter"]["count"], 1)
        memes = rt.repeat_mem().top_memes("g", kind="banter")
        self.assertEqual(memes[0]["text"], "今天好热。")
        self.assertEqual(memes[0]["count"], 1)

    def test_repeat_disabled_not_counted(self):
        import asyncio
        from qqbot.events import GroupMessage

        msg = GroupMessage("g", "m", "member", "id", "今天好热", "", 0, mentioned=False)
        rt = self._rt(repeat_enabled=False, repeat_mode="repeat")
        asyncio.run(rt._do_repeat(msg))
        self.assertEqual(rt.sender.calls, [])
        self.assertEqual(rt.repeat_mem().stats("g"), {})
        self.assertEqual(rt.repeat_mem().top_memes("g"), [])
        self.assertEqual(rt.store.get_thread("g", "m", "chat"), [])

    def test_proactive_decision_and_send(self):
        import asyncio
        import time as _time
        from types import SimpleNamespace

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                return SimpleNamespace(
                    text="来聊点别的。", usage={"total_tokens": 3}
                )

        rt = self._rt(
            proactive_enabled=True,
            proactive_probability=100,
            proactive_interval_s=0,
            proactive_idle_s=0,
            proactive_daily_limit=0,
        )
        rt.provider = Provider()
        self.assertTrue(rt._proactive_group_ok("g", 0))
        self.assertTrue(asyncio.run(rt._do_proactive("g")))
        self.assertEqual(rt.sender.calls, ["来聊点别的"])
        self.assertEqual(rt.proactive_mem().state("g")[1], 1)

        rt = self._rt(
            proactive_enabled=True,
            proactive_probability=100,
            proactive_interval_s=0,
            proactive_idle_s=0,
            proactive_daily_limit=0,
        )
        rt.provider = Provider()
        rt._last_msg = {}
        asyncio.run(rt._proactive_tick())
        self.assertEqual(rt.sender.calls, ["来聊点别的"])

        rt = self._rt(proactive_enabled=False)
        self.assertFalse(rt._proactive_group_ok("g", 0))
        rt = self._rt(proactive_enabled=True, proactive_probability=0)
        self.assertFalse(rt._proactive_group_ok("g", 0))
        rt = self._rt(
            proactive_enabled=True,
            proactive_probability=100,
            proactive_idle_s=300,
        )
        self.assertFalse(rt._proactive_group_ok("g", _time.time()))
        self.assertTrue(rt._proactive_group_ok("g", 0))

        rt = self._rt(
            proactive_enabled=False,
            proactive_probability=100,
            proactive_interval_s=0,
            proactive_idle_s=0,
            proactive_daily_limit=0,
        )
        rt.store.set_group_reply("g", {"proactive_enabled": True})
        self.assertFalse(rt._proactive_group_ok("g", 0))
        rt.cfg.proactive_enabled = True
        self.assertTrue(rt._proactive_group_ok("g", 0))

    def test_manual_summarize_pending(self):
        import asyncio
        from types import SimpleNamespace

        class Provider:
            id = "mock"

            async def complete(self, messages, **kw):
                return SimpleNamespace(text="- 手动整理后的记忆", usage={})

        rt = self._rt(auto_summary=False)
        rt.provider = Provider()
        rt._summary_busy = set()
        rt.store.save_memory_state(
            "g", "m1", "", [{"role": "user", "content": "a"}]
        )
        rt.store.save_memory_state(
            "g", "m2", "", [{"role": "assistant", "content": "b"}]
        )
        res = asyncio.run(rt.summarize_pending(limit=5))
        self.assertEqual(res["summarized"], 2)
        self.assertEqual(res["failed"], 0)
        self.assertEqual(res["pending"]["messages"], 0)
        self.assertEqual(len(rt.store.list_summaries()), 2)

    def test_summary_retries_when_length_empty(self):
        import asyncio
        from qqbot.providers.base import Completion

        class Provider:
            id = "mock"

            def __init__(self):
                self.calls = []

            async def complete(self, messages, **kw):
                self.calls.append(kw.get("max_tokens"))
                if len(self.calls) == 1:
                    return Completion("", finish_reason="length")
                return Completion("- 重试后的记忆", finish_reason="stop")

        rt = self._rt(auto_summary=False)
        rt.provider = Provider()
        rt._summary_busy = set()
        rt.store.save_memory_state(
            "g", "m1", "", [{"role": "user", "content": "a"}]
        )
        ok = asyncio.run(
            rt._summarize(
                "g", "m1", "", [{"role": "user", "content": "a"}], "chat"
            )
        )
        self.assertTrue(ok)
        self.assertEqual(rt.provider.calls, [8000, 12000])
        self.assertTrue(rt.store.list_summaries())

    def test_persona_anchor_and_check(self):
        import asyncio
        from types import SimpleNamespace
        from qqbot import prompts
        from qqbot.events import GroupMessage

        enabled = self._rt(
            persona_guard_enabled=True,
            persona_anchor="你是群里的老油条，说话短，不客服腔。",
            persona_check_interval=2,
        )
        text = prompts.compose(enabled.cfg)
        self.assertIn("【人设锚点】", text)
        self.assertIn("老油条", text)
        self.assertIn("违反第N条", prompts.PERSONA_CHECK_PROMPT)
        self.assertIn("严重程度", prompts.PERSONA_CHECK_PROMPT)
        self.assertNotIn("状态：", prompts.PERSONA_CHECK_PROMPT)
        status, note, weight = enabled._parse_persona_report(
            "报告：太像客服了，下一句短一点。\n权重：0.8"
        )
        self.assertEqual((status, weight), ("drift", 0.8))
        self.assertIn("客服", note)
        status, note, weight = enabled._parse_persona_report(
            "报告：语气正常，继续保持。\n权重：0.0"
        )
        self.assertEqual((status, weight), ("ok", 0.0))
        self.assertEqual(note, "")

        disabled = self._rt(persona_guard_enabled=False)
        self.assertNotIn("【人设锚点】", prompts.compose(disabled.cfg))

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                system = messages[0].content or ""
                if "人设检查器" in system:
                    return SimpleNamespace(
                        text="别用客服腔，短一点。（0.5）",
                        usage={"total_tokens": 4},
                    )
                return SimpleNamespace(text="行", usage={"total_tokens": 1})

        msg = GroupMessage("g", "m", "member", "id", "在吗", "", 0, mentioned=True)
        enabled.provider = Provider()
        mem = enabled.persona_mem()
        self.assertEqual(mem.bump_turn("g", "chat"), 1)
        self.assertEqual(mem.bump_turn("g", "chat"), 2)
        mem.reset_turn("g", "chat")
        self.assertEqual(mem.get_turn("g", "chat"), 0)
        history = [{"role": "assistant", "content": "您好，请问有什么可以帮您？"}]
        note = asyncio.run(enabled._persona_check(msg, "chat", history))
        self.assertIn("客服腔", note)
        reports = enabled.persona_mem().reports()
        self.assertEqual(reports[0]["status"], "drift")
        self.assertEqual(reports[0]["member"], "")
        self.assertIn("客服腔", reports[0]["note"])
        active = enabled.persona_mem().active_reports("g", "chat")
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["weight"], 0.5)

        enabled.persona_mem().record(
            "g", "chat", "drift", "别用客服腔，短一点。", weight=0.5
        )
        self.assertEqual(
            len(enabled.persona_mem().active_reports("g", "chat")), 1
        )

        seen = []

        class PromptProvider:
            id = "openai"

            async def complete(self, messages, **kw):
                seen.append(messages)
                return SimpleNamespace(text="行", usage={"total_tokens": 1})

        enabled.provider = PromptProvider()
        enabled.cfg.persona_check_interval = 0
        asyncio.run(enabled._generate(msg))
        self.assertIn("【人设自检提醒】", seen[0][0].content)
        self.assertIn("客服腔", seen[0][0].content)

        class OkProvider:
            id = "openai"

            async def complete(self, messages, **kw):
                return SimpleNamespace(text="OK", usage={"total_tokens": 1})

        ok_rt = self._rt(persona_guard_enabled=True)
        ok_rt.provider = OkProvider()
        self.assertEqual(asyncio.run(ok_rt._persona_check(msg, "chat", history)), "")
        ok_report = ok_rt.persona_mem().reports()[0]
        self.assertEqual(ok_report["status"], "ok")
        self.assertEqual(ok_report["note"], "")
        self.assertEqual(ok_report["weight"], 0.0)
        self.assertEqual(ok_rt.persona_mem().active_reports("g", "chat"), [])
        seen.clear()
        ok_rt.provider = PromptProvider()
        asyncio.run(ok_rt._generate(msg))
        self.assertNotIn("客服腔", seen[0][0].content)
        self.assertNotIn("【人设自检提醒】", seen[0][0].content)
        ok_rt.persona_mem().record(
            "g0", "chat", "drift", "零权重报告", weight=0.0
        )
        self.assertEqual(ok_rt.persona_mem().active_reports("g0", "chat"), [])
        self.assertEqual(ok_rt.persona_mem().reports()[0]["note"], "")

        from unittest import mock as umock

        class TempProvider:
            id = "temp"

            def __init__(self):
                self.closed = False
                self.used = 0

            async def complete(self, messages, **kw):
                self.used += 1
                return SimpleNamespace(
                    text="用短句，别客服腔（0.5）", usage={"total_tokens": 3}
                )

            async def aclose(self):
                self.closed = True

        temp = TempProvider()
        separate = self._rt(
            persona_guard_enabled=True,
            persona_check_use_separate=True,
            persona_check_provider="custom",
            persona_check_base_url="https://example.com/v1",
            persona_check_model="other-model",
            persona_check_interval=1,
        )
        separate.provider = Provider()
        separate.secrets = {
            "llm_keys": {},
            "persona_check_api_key": "sk-persona",
        }
        with umock.patch("qqbot.app.build_provider", return_value=temp) as bp:
            note = asyncio.run(separate._persona_check(msg, "chat", history))
        bp.assert_called_once()
        pcfg, key = bp.call_args.args
        self.assertEqual(pcfg.provider, "custom")
        self.assertEqual(pcfg.base_url, "https://example.com/v1")
        self.assertEqual(pcfg.model, "other-model")
        self.assertEqual(key, "sk-persona")
        self.assertIn("别客服腔", note)
        self.assertEqual(temp.used, 1)
        self.assertTrue(temp.closed)

    def test_persona_check_counts_per_group_and_manual_runs(self):
        import asyncio
        from types import SimpleNamespace
        from qqbot.events import GroupMessage

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                system = messages[0].content or ""
                if "人设检查器" in system:
                    return SimpleNamespace(
                        text=(
                            "报告：语气和人设一致，继续用短句。\n权重：0.0"
                        ),
                        usage={"total_tokens": 5},
                    )
                return SimpleNamespace(text="行", usage={"total_tokens": 1})

        rt = self._rt(
            persona_guard_enabled=True,
            persona_anchor="说话短，不客服腔。",
            persona_check_interval=2,
        )
        rt.provider = Provider()
        a = GroupMessage("g", "m1", "member", "id1", "在吗", "", 0)
        b = GroupMessage("g", "m2", "member", "id2", "在吗", "", 0)
        mem = rt.persona_mem()
        self.assertEqual(mem.bump_turn("g", "chat"), 1)
        self.assertEqual(mem.bump_turn("g", "chat"), 2)
        mem.reset_turn("g", "chat")
        self.assertEqual(mem.get_turn("g", "chat"), 0)

        rt.cfg.persona_check_interval = 1
        rt._remember_assistant("g", "您好，请问有什么可以帮您？")
        rt.store.append_turn("g", "m1", "在吗", "您好，请问有什么可以帮您？")

        async def run_bg_and_manual():
            rt._maybe_persona_check("g", "chat")
            await asyncio.sleep(0.05)
            return await rt.persona_check_now()

        manual = asyncio.run(run_bg_and_manual())
        self.assertTrue(manual["ok"])
        self.assertEqual(manual["status"], "ok")
        self.assertEqual(manual["note"], "")
        reports = rt.persona_mem().reports()
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["source"], "manual")
        self.assertEqual(reports[0]["member"], "")
        self.assertEqual(rt.persona_mem().active_reports("g", "chat"), [])

    def test_persona_manual_check_uses_proactive_buffer(self):
        import asyncio
        from collections import deque
        from types import SimpleNamespace

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                return SimpleNamespace(
                    text="报告：主动发言也保持了人设。\n权重：0.0",
                    usage={},
                )

        rt = self._rt(persona_guard_enabled=True)
        rt.provider = Provider()
        rt._persona_recent = {"g-proactive": deque(["今晚聊点什么"])}
        result = asyncio.run(rt.persona_check_now())
        self.assertTrue(result["ok"])
        self.assertEqual(result["group"], "g-proactive")
        self.assertEqual(result["note"], "")
        report = rt.persona_mem().reports()[0]
        self.assertEqual(report["source"], "manual")
        self.assertEqual(report["member"], "")

    def test_persona_check_records_error_report(self):
        import asyncio
        from qqbot.events import GroupMessage

        class Broken:
            id = "openai"

            async def complete(self, messages, **kw):
                raise RuntimeError("模型不可用")

        rt = self._rt(persona_guard_enabled=True)
        rt.provider = Broken()
        rt.store.append_turn("g", "m", "在吗", "您好，请问有什么可以帮您？")
        msg = GroupMessage("g", "m", "member", "id", "在吗", "", 0)
        note = asyncio.run(
            rt._persona_check(
                msg,
                "chat",
                [{"role": "assistant", "content": "您好，请问有什么可以帮您？"}],
            )
        )
        self.assertEqual(note, "")
        report = rt.persona_mem().reports()[0]
        self.assertEqual(report["status"], "error")
        self.assertEqual(report["member"], "")
        self.assertIn("自检调用失败", report["note"])
        self.assertEqual(rt.persona_mem().active_reports("g", "chat"), [])

    def test_persona_check_always_uses_builtin_prompt(self):
        import asyncio
        from types import SimpleNamespace
        from qqbot import prompts
        from qqbot.config import InstanceConfig

        seen = []

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                seen.append(messages)
                return SimpleNamespace(
                    text="报告：检查通过。\n权重：0.0", usage={}
                )

        rt = self._rt(persona_guard_enabled=True)
        rt.provider = Provider()
        asyncio.run(
            rt._persona_check_report(
                "g",
                "chat",
                [
                    {"role": "user", "content": "用户说了一句不该检查的话"},
                    {"role": "assistant", "content": "机器人自己的回复"},
                ],
            )
        )
        self.assertEqual(seen[0][0].content, prompts.PERSONA_CHECK_PROMPT)
        self.assertIn("只检查机器人自己", seen[0][0].content)
        self.assertIn("机器人自己的回复", seen[0][1].content)
        self.assertNotIn("用户说了一句不该检查的话", seen[0][1].content)
        self.assertNotIn(
            "persona_check_prompt", InstanceConfig.__dataclass_fields__
        )

    def test_persona_check_sends_full_negative_prompt_and_checklist(self):
        import asyncio
        from types import SimpleNamespace
        from qqbot import prompts

        seen = []

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                seen.append(messages)
                return SimpleNamespace(
                    text="- 未发现问题（0.0）", usage={}
                )

        tail = "结尾标记：不要出现这句话"
        negative = "不要客服腔。不要用表情。" + "不要啰嗦。" * 120 + tail
        self.assertGreater(len(negative), 600)
        rt = self._rt(
            persona_guard_enabled=True,
            persona_anchor="说话短。不要客服腔。",
            negative_prompt=negative,
        )
        rt.provider = Provider()
        asyncio.run(
            rt._persona_check_report(
                "g",
                "chat",
                [{"role": "assistant", "content": "你好，我在。"}],
            )
        )
        user = seen[0][1].content
        self.assertIn(tail, user)
        self.assertIn("【检查清单】", user)
        for index, item in enumerate(prompts.PERSONA_CHECK_ITEMS, 1):
            self.assertIn(f"{index}. {item}", user)
        self.assertIn("【人设锚点】\n说话短。不要客服腔。", user)

    def test_persona_check_checklist_is_generic(self):
        import asyncio
        from types import SimpleNamespace
        from qqbot import prompts

        anchors = [
            "你是一只猫。",
            "Persona: a grumpy mechanic who speaks in short English sentences.",
            "你是个话很少的人，喜欢用比喻，讨厌被追问。",
        ]
        expected = [
            f"{i}. {item}"
            for i, item in enumerate(prompts.PERSONA_CHECK_ITEMS, 1)
        ]

        for anchor in anchors:
            seen = []

            class Provider:
                id = "openai"

                async def complete(self, messages, **kw):
                    seen.append(messages)
                    return SimpleNamespace(
                        text="- 未发现问题（0.0）", usage={}
                    )

            rt = self._rt(persona_guard_enabled=True, persona_anchor=anchor)
            rt.provider = Provider()
            asyncio.run(
                rt._persona_check_report(
                    "g",
                    "chat",
                    [{"role": "assistant", "content": "在。"}],
                )
            )
            user = seen[0][1].content
            for line in expected:
                self.assertIn(line, user)
            self.assertNotIn("1. 你是一只猫", user)

    def test_persona_limits_match_ui_and_prompt(self):
        import re
        from qqbot import limits, prompts
        from qqbot.config import InstanceConfig
        from qqbot.ui.page import INDEX_HTML

        fields = (
            ("psName", limits.BOT_NAME, "input"),
            ("psPersona", limits.PERSONA, "textarea"),
            ("psNegative", limits.NEGATIVE_PROMPT, "textarea"),
            ("psStyle", limits.STYLE_PROMPT, "textarea"),
            ("pgAnchor", limits.PERSONA_ANCHOR, "textarea"),
        )
        for field_id, limit, tag in fields:
            match = re.search(
                rf'<{tag} id="{field_id}"[^>]*>', INDEX_HTML, re.S
            )
            self.assertIsNotNone(match, field_id)
            self.assertIn(f'maxlength="{limit}"', match.group(0))

        samples = {
            "persona": "设" * (limits.PERSONA - 1) + "人",
            "persona_anchor": "锚" * (limits.PERSONA_ANCHOR - 1) + "点",
            "negative_prompt": "禁" * (limits.NEGATIVE_PROMPT - 1) + "止",
            "style_prompt": "风" * (limits.STYLE_PROMPT - 1) + "格",
        }
        cfg = InstanceConfig(persona_guard_enabled=True, **samples)
        text = prompts.compose(cfg)
        for value in samples.values():
            self.assertIn(value, text)

    def test_persona_check_uses_full_persona_without_anchor(self):
        import asyncio
        from types import SimpleNamespace
        from qqbot import limits

        seen = []

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                seen.append(messages)
                return SimpleNamespace(
                    text="- 未发现问题（0.0）", usage={}
                )

        tail = "人设最后一句"
        rt = self._rt(
            persona_guard_enabled=True,
            persona="设" * (limits.PERSONA - len(tail)) + tail,
        )
        rt.provider = Provider()
        asyncio.run(
            rt._persona_check_report(
                "g",
                "chat",
                [{"role": "assistant", "content": "在。"}],
            )
        )
        self.assertIn(tail, seen[0][1].content)

    def test_persona_check_checklist_weight_from_severity(self):
        rt = self._rt()
        status, note, weight = rt._parse_checklist_report(
            "- 违反第1条：回复 63 字，超过 50 字上限｜一般\n"
            "- 违反第2条：出现客服腔，原文「有什么可以帮您」｜严重\n"
            "- 违反第2条：同一问题重复出现｜轻微"
        )
        self.assertEqual(status, "drift")
        self.assertEqual(weight, 0.9)
        self.assertIn("回复 63 字", note)
        self.assertIn("（0.6）", note)
        self.assertIn("（0.9）", note)
        self.assertNotIn("第1条", note)
        self.assertEqual(note.count("客服腔"), 1)
        self.assertIsNone(rt._parse_checklist_report("- 未发现问题（0.0）"))

    def test_persona_check_report_uses_checklist_result(self):
        import asyncio
        from types import SimpleNamespace

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                return SimpleNamespace(
                    text="- 违反第2条：用了客服腔，原文「有什么可以帮您」｜一般",
                    usage={},
                )

        rt = self._rt(
            persona_guard_enabled=True,
            persona_anchor="说话短。不要客服腔。",
        )
        rt.provider = Provider()
        result = asyncio.run(
            rt._persona_check_report(
                "g",
                "chat",
                [
                    {
                        "role": "assistant",
                        "content": "您好，请问有什么可以帮您？",
                    }
                ],
            )
        )
        self.assertEqual(result["status"], "drift")
        self.assertEqual(result["weight"], 0.6)
        self.assertIn("客服腔", result["note"])
        self.assertIn("（0.6）", result["note"])

    def test_persona_report_manual_edit(self):
        rt = self._rt()
        first = rt.persona_mem().record(
            "g", "chat", "drift", "旧问题", weight=0.5
        )
        updated = rt.persona_mem().update_report(
            first["id"], "手动改过的报告（0.9）"
        )
        self.assertIsNotNone(updated)
        self.assertIn("手动改过的报告", updated["note"])
        self.assertEqual(updated["weight"], 0.9)
        self.assertEqual(updated["status"], "drift")
        active = rt.persona_mem().active_reports("g", "chat")
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["note"], "手动改过的报告")
        self.assertEqual(active[0]["weight"], 0.9)

        text_only = rt.persona_mem().update_report(
            first["id"], "只改文字不改权重"
        )
        self.assertEqual(text_only["note"], "只改文字不改权重")
        self.assertEqual(text_only["weight"], 0.0)
        self.assertEqual(text_only["status"], "ok")
        self.assertEqual(rt.persona_mem().active_reports("g", "chat"), [])

        cleared = rt.persona_mem().update_report(first["id"], "")
        self.assertEqual(cleared["note"], "")
        self.assertEqual(cleared["weight"], 0.0)
        self.assertEqual(cleared["status"], "ok")
        self.assertEqual(rt.persona_mem().active_reports("g", "chat"), [])
        self.assertIsNone(
            rt.persona_mem().update_report("missing", "z")
        )

    def test_persona_report_multi_line_and_invalid_weight(self):
        rt = self._rt()
        status, note, weight = rt._parse_persona_report(
            "- 问题一（0.7）\n- 问题二（0.4）"
        )
        self.assertEqual(status, "drift")
        self.assertEqual(weight, 0.7)
        self.assertIn("问题一", note)
        self.assertIn("问题二", note)
        report = rt.persona_mem().record("g", "chat", status, note, weight=weight)
        active = rt.persona_mem().active_reports("g", "chat")
        self.assertEqual(
            [(r["note"], r["weight"]) for r in active],
            [("问题一", 0.7), ("问题二", 0.4)],
        )

        rt.persona_mem().update_report(
            report["id"], "- 问题三（abc）\n- 问题四（0.8）"
        )
        active = rt.persona_mem().active_reports("g", "chat")
        self.assertEqual(
            [(r["note"], r["weight"]) for r in active],
            [("问题四", 0.8)],
        )
        self.assertIn("abc", rt.persona_mem().reports(200)[0]["note"])
        rt.persona_mem().update_report(report["id"], "- 没有括号的问题")
        self.assertEqual(rt.persona_mem().active_reports("g", "chat"), [])

    def test_persona_max_problem_lines_per_group(self):
        rt = self._rt()
        note = "\n".join(f"- 问题{i}（0.5）" for i in range(12))
        rt.persona_mem().record("g", "chat", "drift", note, weight=0.5)
        active = rt.persona_mem().active_reports("g", "chat")
        self.assertEqual(len(active), 10)
        stored = rt.persona_mem().reports(200)[0]["note"]
        self.assertEqual(len([x for x in stored.splitlines() if x.strip()]), 10)

    def test_persona_turn_count_persists_across_restart(self):
        rt = self._rt(
            persona_guard_enabled=True,
            persona_check_interval=5,
        )
        mem = rt.persona_mem()
        self.assertEqual(mem.bump_turn("g", "chat"), 1)
        self.assertEqual(mem.bump_turn("g", "chat"), 2)
        rt._persona_mem_instance = None
        mem2 = rt.persona_mem()
        self.assertEqual(mem2.get_turn("g", "chat"), 2)
        self.assertEqual(mem2.bump_turn("g", "chat"), 3)
        mem2.reset_turn("g", "chat")
        self.assertEqual(mem2.get_turn("g", "chat"), 0)

    def test_persona_reports_page(self):
        rt = self._rt()
        for i in range(25):
            rt.persona_mem().record(
                f"g{i}", "chat", "drift", f"问题{i}", weight=0.5
            )
        items, total = rt.persona_mem().reports_page(page=2, size=10)
        self.assertEqual(total, 25)
        self.assertEqual(len(items), 10)
        self.assertEqual(items[0]["group"], "g14")

    def test_persona_reports_are_group_level_and_capped(self):
        rt = self._rt()
        for i in range(80):
            rt.persona_mem().record(
                "g1", "chat", "drift", f"问题{i}", weight=0.4
            )
        self.assertLessEqual(len(rt.persona_mem().reports(200)), 10)

        rt.persona_mem().set_report_limit(5)
        self.assertLessEqual(len(rt.persona_mem().reports(200)), 5)

        rt.persona_mem().record("gA", "chat", "drift", "聊天问题", weight=0.7)
        rt.persona_mem().record(
            "gA", "translate", "drift", "翻译问题", weight=0.9
        )
        chat = rt.persona_mem().active_reports("gA", "chat")
        self.assertEqual(
            [r["note"] for r in chat], ["翻译问题", "聊天问题"]
        )
        all_modes = rt.persona_mem().active_reports("gA", "")
        self.assertEqual(
            [r["note"] for r in all_modes], ["翻译问题", "聊天问题"]
        )

    def test_persona_report_limit_deletes_low_weight_first(self):
        rt = self._rt()
        rt.persona_mem().record("g", "chat", "drift", "低权重", weight=0.1)
        rt.persona_mem().record("g", "chat", "drift", "高权重", weight=0.9)
        rt.persona_mem().record("g", "chat", "drift", "中权重", weight=0.5)
        rt.persona_mem().record("g", "chat", "drift", "次高权重", weight=0.7)
        rt.persona_mem().set_report_limit(3)
        notes = [
            r["note"].replace("- ", "").split("（")[0]
            for r in rt.persona_mem().reports(200)
        ]
        self.assertEqual(notes, ["次高权重", "中权重", "高权重"])
        self.assertNotIn("低权重", notes)

    def test_persona_report_keeps_newest_even_if_low_weight(self):
        rt = self._rt()
        rt.persona_mem().set_report_limit(3)
        rt.persona_mem().record("g", "chat", "drift", "高1", weight=0.9)
        rt.persona_mem().record("g", "chat", "drift", "高2", weight=0.8)
        rt.persona_mem().record("g", "chat", "drift", "高3", weight=0.7)
        latest = rt.persona_mem().record(
            "g", "chat", "drift", "最新低权重", weight=0.1
        )
        reports = rt.persona_mem().reports(200)
        notes = [r["note"] for r in reports]
        self.assertTrue(any("最新低权重" in note for note in notes))
        self.assertEqual(reports[0]["id"], latest["id"])
        self.assertEqual(len(reports), 3)
        self.assertFalse(any("高3" in note for note in notes))

    def test_persona_edit_old_report_makes_it_current(self):
        rt = self._rt()
        first = rt.persona_mem().record(
            "g", "chat", "drift", "旧报告", weight=0.2
        )
        rt.persona_mem().record("g", "chat", "drift", "新报告", weight=0.5)
        active = rt.persona_mem().active_reports("g", "chat")
        self.assertEqual(
            [r["note"] for r in active], ["新报告", "旧报告"]
        )

        updated = rt.persona_mem().update_report(
            first["id"], "旧报告已更新（0.9）"
        )
        self.assertIsNotNone(updated)
        active = rt.persona_mem().active_reports("g", "chat")
        self.assertEqual(
            [r["note"] for r in active], ["旧报告已更新", "新报告"]
        )
        self.assertEqual(active[0]["id"], first["id"])
        self.assertEqual(rt.persona_mem().reports(200)[0]["id"], first["id"])

    def test_persona_import_dedupes_old_reports_without_id(self):
        rt = self._rt()
        report = {
            "group": "g",
            "mode": "chat",
            "status": "drift",
            "note": "重复报告",
            "weight": 0.5,
            "ts": 1.0,
        }
        rt.persona_mem().restore([report, dict(report)])
        rows = rt.persona_mem().reports(200)
        self.assertEqual(len(rows), 1)
        self.assertIn("重复报告", rows[0]["note"])

    def test_persona_reports_keep_history_per_group(self):
        rt = self._rt()
        first = rt.persona_mem().record(
            "g", "chat", "drift", "旧问题", weight=0.5
        )
        second = rt.persona_mem().record(
            "g", "chat", "drift", "新问题", weight=0.7
        )
        reports = [
            r for r in rt.persona_mem().reports(200) if r["group"] == "g"
        ]
        self.assertEqual(len(reports), 2)
        self.assertEqual(reports[0]["id"], second["id"])
        self.assertEqual(reports[1]["id"], first["id"])
        active = rt.persona_mem().active_reports("g", "chat")
        self.assertEqual(
            [r["note"] for r in active], ["新问题", "旧问题"]
        )

        self.assertTrue(rt.persona_mem().delete_report(second["id"]))
        active = rt.persona_mem().active_reports("g", "chat")
        self.assertEqual([r["note"] for r in active], ["旧问题"])
        self.assertFalse(rt.persona_mem().delete_report(second["id"]))
        third = rt.persona_mem().record(
            "g", "chat", "drift", "删除后新报告", weight=0.6
        )
        active = rt.persona_mem().active_reports("g", "chat")
        self.assertEqual(
            [r["note"] for r in active], ["删除后新报告", "旧问题"]
        )
        self.assertEqual(active[0]["id"], third["id"])

    def test_persona_zero_weight_does_not_use_limit(self):
        rt = self._rt()
        rt.persona_mem().set_report_limit(2)
        rt.persona_mem().record("g", "chat", "drift", "高权重A", weight=0.9)
        rt.persona_mem().record("g", "chat", "drift", "高权重B", weight=0.8)
        rt.persona_mem().record("g", "chat", "ok", "", weight=0.0)
        reports = rt.persona_mem().reports(200)
        self.assertEqual(len(reports), 3)
        self.assertEqual(reports[0]["weight"], 0.0)
        active = rt.persona_mem().active_reports("g", "chat")
        self.assertEqual(
            [r["note"] for r in active], ["高权重A", "高权重B"]
        )

    def test_persona_total_report_limit_is_200(self):
        rt = self._rt()
        for i in range(25):
            for j in range(10):
                rt.persona_mem().record(
                    f"g{i}",
                    "chat",
                    "drift",
                    f"问题{i}-{j}",
                    weight=0.5,
                )
        self.assertEqual(len(rt.persona_mem().reports(300)), 200)

    def test_persona_import_merge_and_replace(self):
        rt = self._rt()
        rt.persona_mem().record("g1", "chat", "drift", "原报告", weight=0.5)
        added = rt.persona_mem().restore(
            [
                {
                    "group": "g2",
                    "mode": "chat",
                    "note": "追加报告",
                    "weight": 0.6,
                    "ts": 10.0,
                }
            ],
            replace=False,
        )
        self.assertEqual(added, 1)
        groups = {r["group"] for r in rt.persona_mem().reports(200)}
        self.assertEqual(groups, {"g1", "g2"})
        rt.persona_mem().restore(
            [
                {
                    "group": "g3",
                    "mode": "chat",
                    "note": "覆盖报告",
                    "weight": 0.7,
                    "ts": 11.0,
                }
            ],
            replace=True,
        )
        groups = {r["group"] for r in rt.persona_mem().reports(200)}
        self.assertEqual(groups, {"g3"})

    def test_persona_clear_group(self):
        rt = self._rt()
        rt.persona_mem().record("g1", "chat", "drift", "A", weight=0.5)
        rt.persona_mem().record("g1", "chat", "drift", "B", weight=0.6)
        rt.persona_mem().record("g2", "chat", "drift", "C", weight=0.7)
        self.assertEqual(rt.persona_mem().clear_group("g1"), 2)
        groups = {r["group"] for r in rt.persona_mem().reports(200)}
        self.assertEqual(groups, {"g2"})

    def test_listen_min_members(self):
        from qqbot.events import GroupMessage

        rt = self._rt(
            listen_enabled=True,
            listen_probability=100,
            listen_min_chars=1,
            listen_min_members=5,
        )
        msg = GroupMessage("g", "m", "member", "id", "今天好热", "", 0, mentioned=False)
        self.assertFalse(rt._listen_ok(msg))
        rt.store.set_group_member_count("g", 3)
        self.assertFalse(rt._listen_ok(msg))
        rt.store.set_group_member_count("g", 10)
        self.assertTrue(rt._listen_ok(msg))

    def test_banter_uses_custom_prompt(self):
        import asyncio
        from types import SimpleNamespace

        seen = []

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                seen.append(messages)
                return SimpleNamespace(
                    text="好活", usage={"total_tokens": 3}
                )

        rt = self._rt(
            repeat_prompt="[急了]：调侃对方破防，应该回“这就急了？”"
        )
        rt.provider = Provider()
        text = asyncio.run(rt._banter("今天又加班"))
        self.assertEqual(text, "好活")
        system = seen[0][0].content
        self.assertIn("[梗名]：对梗的解释，应该怎么接", system)
        self.assertIn("[急了]", system)
        self.assertIn("这就急了", system)
        self.assertIn("不超过 30 字", system)

        rt = self._rt(repeat_prompt="")
        rt.provider = Provider()
        asyncio.run(rt._banter("今天又加班"))
        fallback = seen[-1][0].content
        self.assertIn("按群里常见的方式接一句", fallback)
        self.assertNotIn("[梗名]：对梗的解释，应该怎么接", fallback)

    def test_banter_uses_meme_stats(self):
        import asyncio
        from types import SimpleNamespace

        seen = []

        class Provider:
            id = "openai"

            async def complete(self, messages, **kw):
                seen.append(messages)
                return SimpleNamespace(text="好活", usage={"total_tokens": 3})

        rt = self._rt(repeat_prompt="群里的梗：不会就接一句吐槽。")
        rt.repeat_mem().bump_meme("g", "m", "banter", "急了")
        rt.repeat_mem().bump_meme("g", "m2", "repeat", "抽象")
        rt.repeat_mem().bump_meme("g", "m2", "repeat", "抽象")
        rt.provider = Provider()
        asyncio.run(rt._banter("今天又加班", "g", "m"))

        system = seen[0][0].content
        self.assertIn("这个用户常说的梗", system)
        self.assertIn("急了", system)
        self.assertIn("群里常复读的句子", system)
        self.assertIn("抽象（2次）", system)


if __name__ == "__main__":
    unittest.main()
