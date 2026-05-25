import asyncio
import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path


BOT_DIR = Path(__file__).resolve().parents[1] / "Bot"
if str(BOT_DIR) not in sys.path:
    sys.path.insert(0, str(BOT_DIR))


def install_plugin_stubs():
    plugins = types.ModuleType("plugins")
    plugins.__path__ = []
    for name in ("P5_card", "YGO_find_card", "drawing", "jm2pdf", "markdown", "pixiv", "typst_renderer"):
        setattr(plugins, name, types.SimpleNamespace())
    sys.modules["plugins"] = plugins
    markdown_module = types.ModuleType("plugins.markdown")
    markdown_module.markdown_to_image = lambda _text: ""
    stickers_module = types.ModuleType("plugins.stickers")
    stickers_module.get_available_stickers = lambda: {}
    stickers_module.sticker_to_segment = lambda _name: None
    sys.modules["plugins.markdown"] = markdown_module
    sys.modules["plugins.stickers"] = stickers_module


install_plugin_stubs()


class BanThisCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_plugin_stubs()
        cls.command_handlers = importlib.import_module("command_handlers")
        cls.plugin_state = importlib.import_module("plugin_state")

    def make_handler(self, data_dir: Path):
        sent_group: list[tuple[int, str]] = []

        async def decode(text):
            return text

        async def send_group(_ws, group_id, message):
            sent_group.append((group_id, message))

        async def send_private(_ws, user_id, message):
            pass

        handler = self.command_handlers.CommandHandler(
            {
                "decode_CQ_to_message": decode,
                "send_group_message": send_group,
                "send_private_message": send_private,
                "test_if_super_user": lambda user_id: int(user_id) == 1,
            },
            {},
        )
        handler.group_bot_bans = self.plugin_state.GroupBotBanStore(data_dir / "group_bot_bans.json")
        handler.group_agent_modes = self.plugin_state.GroupAgentModeStore(data_dir / "group_agent_modes.json")
        handler.group_plugin_bans = self.plugin_state.GroupPluginBanStore(data_dir / "group_plugin_bans.json")
        handler.user_bans = self.plugin_state.UserBanStore(data_dir / "banned_users.json")
        return handler, sent_group

    def test_help_main_defers_ban_details_to_help_ban(self):
        with tempfile.TemporaryDirectory() as tmp:
            handler, _sent = self.make_handler(Path(tmp))

            main_help = handler._get_help_message(".help")
            ban_help = handler._get_help_message(".help ban")

            self.assertIn(".ban / .unban", main_help)
            self.assertNotIn(".ban user:<QQ号>", main_help)
            self.assertIn(".ban this", ban_help)
            self.assertIn(".unban this", ban_help)
            self.assertIn(".ban user:<QQ号>", ban_help)

    def test_ban_and_unban_this_toggle_current_group(self):
        with tempfile.TemporaryDirectory() as tmp:
            handler, sent = self.make_handler(Path(tmp))

            asyncio.run(
                handler.handle_command(
                    None,
                    self.command_handlers.MessageType.GROUP,
                    self.command_handlers.CommandType.BAN,
                    ".ban this",
                    group_id=100,
                    user_id=1,
                )
            )
            self.assertTrue(handler.is_group_bot_banned(100))
            self.assertIn("已禁用 Bot 在本群的回复", sent[-1][1])

            asyncio.run(
                handler.handle_command(
                    None,
                    self.command_handlers.MessageType.GROUP,
                    self.command_handlers.CommandType.UNBAN,
                    ".unban this",
                    group_id=100,
                    user_id=1,
                )
            )
            self.assertFalse(handler.is_group_bot_banned(100))
            self.assertIn("已恢复 Bot 在本群的回复", sent[-1][1])

    def test_command_chain_splits_only_when_every_part_is_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            handler, _sent = self.make_handler(Path(tmp))

            self.assertEqual(
                handler.split_command_chain(".unban jm && .jm recommend && .ban jm"),
                [".unban jm", ".jm recommend", ".ban jm"],
            )
            self.assertEqual(
                handler.split_command_chain(".md a && b"),
                [".md a && b"],
            )
            self.assertEqual(
                handler.split_command_chain(".help &&"),
                [".help &&"],
            )

    def test_command_chain_runs_plugin_unban_recommend_then_ban_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            handler, _sent = self.make_handler(Path(tmp))
            group_id = 100
            handler.group_plugin_bans.ban(group_id, "jm")
            observed: list[tuple[int, str, bool]] = []

            async def fake_jm_recommend(_ws, seen_group_id, command_content):
                observed.append(
                    (
                        seen_group_id,
                        command_content,
                        handler.group_plugin_bans.is_banned(seen_group_id, "jm"),
                    )
                )

            handler._send_jm_recommend_group = fake_jm_recommend

            handled = asyncio.run(
                handler.handle_command(
                    None,
                    self.command_handlers.MessageType.GROUP,
                    self.command_handlers.CommandType.UNBAN,
                    ".unban jm && .jm recommend 3 && .ban jm",
                    group_id=group_id,
                    user_id=1,
                )
            )

            self.assertTrue(handled)
            self.assertEqual(observed, [(group_id, "recommend 3", False)])
            self.assertTrue(handler.group_plugin_bans.is_banned(group_id, "jm"))

    def test_agent_mode_defaults_off_and_super_user_can_toggle_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            handler, sent = self.make_handler(Path(tmp))
            group_id = 100

            self.assertFalse(handler.is_group_agent_enabled(group_id))

            asyncio.run(
                handler.handle_command(
                    None,
                    self.command_handlers.MessageType.GROUP,
                    self.command_handlers.CommandType.AGENT,
                    ".agent on",
                    group_id=group_id,
                    user_id=1,
                )
            )
            self.assertTrue(handler.is_group_agent_enabled(group_id))
            self.assertIn("已启用本群自主回复模式", sent[-1][1])

            asyncio.run(
                handler.handle_command(
                    None,
                    self.command_handlers.MessageType.GROUP,
                    self.command_handlers.CommandType.AGENT,
                    ".agent off",
                    group_id=group_id,
                    user_id=1,
                )
            )
            self.assertFalse(handler.is_group_agent_enabled(group_id))
            self.assertIn("已关闭本群自主回复模式", sent[-1][1])

    def test_agent_mode_rejects_non_super_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            handler, sent = self.make_handler(Path(tmp))

            asyncio.run(
                handler.handle_command(
                    None,
                    self.command_handlers.MessageType.GROUP,
                    self.command_handlers.CommandType.AGENT,
                    ".agent on",
                    group_id=100,
                    user_id=2,
                )
            )

            self.assertFalse(handler.is_group_agent_enabled(100))
            self.assertIn("权限不足", sent[-1][1])


class MutedGroupOrchestratorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_plugin_stubs()
        cls.agent_orchestrator = importlib.import_module("agent_orchestrator")
        cls.command_handlers = importlib.import_module("command_handlers")

    def test_muted_group_ignores_non_unban_messages(self):
        class FakeCommandHandler:
            def is_user_banned(self, _user_id):
                return False

            def is_group_bot_banned(self, _group_id):
                return True

            def get_command_type(self, _message_content):
                return None

            def is_group_unban_this_command(self, _message_content):
                return False

        sent: list[tuple[int, list]] = []
        interfaces = {
            "bot_qq": 42,
            "test_if_super_user": lambda _user_id: False,
            "encode_message_to_CQ": lambda segments: asyncio.sleep(0, result="[CQ:at,qq=42] hi"),
            "send_group_message": lambda _ws, group_id, message: asyncio.sleep(0, result=sent.append((group_id, message))),
        }
        orchestrator = self.agent_orchestrator.AgentOrchestrator(
            interfaces,
            FakeCommandHandler(),
            persona_engine=None,
            session_manager=types.SimpleNamespace(memory=None),
            multimodal_processor=lambda _segments, content: asyncio.sleep(0, result=content),
        )

        result = asyncio.run(
            orchestrator.handle_group_message(
                None,
                {
                    "group_id": 100,
                    "user_id": 2,
                    "message": [{"type": "at", "data": {"qq": "42"}}, {"type": "text", "data": {"text": "hi"}}],
                },
            )
        )

        self.assertFalse(result.handled)
        self.assertEqual(result.reason, "group is muted")
        self.assertEqual(sent, [])

    def test_muted_group_allows_super_unban_this(self):
        class FakeCommandHandler:
            def __init__(self):
                self.handled = False

            def is_user_banned(self, _user_id):
                return False

            def is_group_bot_banned(self, _group_id):
                return True

            def get_command_type(self, _message_content):
                return self_command_type

            def is_group_unban_this_command(self, _message_content):
                return True

            async def handle_command(self, *_args, **_kwargs):
                self.handled = True
                return True

        self_command_type = self.command_handlers.CommandType.UNBAN
        command_handler = FakeCommandHandler()
        interfaces = {
            "bot_qq": 42,
            "test_if_super_user": lambda user_id: int(user_id) == 1,
            "encode_message_to_CQ": lambda _segments: asyncio.sleep(0, result=".unban this"),
        }
        orchestrator = self.agent_orchestrator.AgentOrchestrator(
            interfaces,
            command_handler,
            persona_engine=None,
            session_manager=types.SimpleNamespace(memory=None),
            multimodal_processor=lambda _segments, content: asyncio.sleep(0, result=content),
        )

        result = asyncio.run(
            orchestrator.handle_group_message(
                None,
                {"group_id": 100, "user_id": 1, "message": [{"type": "text", "data": {"text": ".unban this"}}]},
            )
        )

        self.assertTrue(result.handled)
        self.assertTrue(command_handler.handled)


class AutonomousGroupAgentDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_plugin_stubs()
        cls.agent_orchestrator = importlib.import_module("agent_orchestrator")
        cls.command_handlers = importlib.import_module("command_handlers")

    def make_orchestrator(self, enabled: bool, recommendations: list[dict] | None = None):
        class FakeCommandHandler:
            def get_command_type(self, _message_content):
                return None

            def is_group_agent_enabled(self, _group_id):
                return enabled

            def recent_jm_recommendation_at(self, _group_id, index):
                items = recommendations or []
                if index < 1 or index > len(items):
                    return None, len(items)
                return str(items[index - 1]["id"]), len(items)

        interfaces = {
            "bot_qq": 42,
            "test_if_super_user": lambda _user_id: False,
        }
        return self.agent_orchestrator.AgentOrchestrator(
            interfaces,
            FakeCommandHandler(),
            persona_engine=None,
            session_manager=types.SimpleNamespace(memory=None),
            multimodal_processor=lambda _segments, content: asyncio.sleep(0, result=content),
        )

    def test_autonomous_group_agent_is_disabled_by_default(self):
        orchestrator = self.make_orchestrator(enabled=False)

        decision = orchestrator.decide_group(100, "有人知道什么是模型蒸馏吗？", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.IGNORE)
        self.assertEqual(decision.reason, "group agent mode is disabled")

    def test_autonomous_group_agent_answers_public_help_question(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "有人知道什么是模型蒸馏吗？", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.CHAT)
        self.assertEqual(decision.reason, "autonomous public help question")

    def test_autonomous_group_agent_answers_direct_public_question(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "模型蒸馏是什么？", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.CHAT)
        self.assertEqual(decision.reason, "autonomous public help question")

    def test_autonomous_group_agent_answers_whether_question(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "这样会不会减少缓存命中率？", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.CHAT)
        self.assertEqual(decision.reason, "autonomous public help question")

    def test_autonomous_group_agent_routes_jm_recommendation_cue(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "今天还没看jm本子", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.command_type.value, "jm")
        self.assertEqual(decision.message_content, ".jm recommend")

    def test_autonomous_group_agent_maps_jm_recommendation_index_to_code(self):
        orchestrator = self.make_orchestrator(
            enabled=True,
            recommendations=[{"id": "1439001"}, {"id": "1436338"}],
        )

        decision = orchestrator.decide_group(100, "我想看推荐栏的第2个", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.reason, "autonomous jm recommendation index")
        self.assertEqual(decision.message_content, ".jm 1436338")

    def test_autonomous_group_agent_discusses_out_of_range_jm_index(self):
        orchestrator = self.make_orchestrator(enabled=True, recommendations=[{"id": "1439001"}])

        decision = orchestrator.decide_group(100, "我想看推荐栏第六个", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.CHAT)
        self.assertEqual(decision.reason, "autonomous jm recommendation index out of range")
        self.assertIn("当前只记录了 1 个推荐项", decision.message_content)

    def test_autonomous_group_agent_discusses_jm_index_without_history(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "我想看推荐栏第1个", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.CHAT)
        self.assertEqual(decision.reason, "autonomous jm recommendation index without history")
        self.assertIn("还没有可用的推荐栏记录", decision.message_content)

    def test_autonomous_group_agent_prefers_explicit_jm_code_over_recommend(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "那我想看JM1436338了，丛雨能帮我获取一下吗", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.reason, "autonomous jm code request")
        self.assertEqual(decision.command_type.value, "jm")
        self.assertEqual(decision.message_content, ".jm 1436338")

    def test_autonomous_group_agent_extracts_number_before_jm_keyword(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "想看1436338这个本子", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.message_content, ".jm 1436338")

    def test_autonomous_group_agent_routes_pixiv_recommendation(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "来点p站推荐", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.command_type.value, "pixiv")
        self.assertEqual(decision.message_content, ".pixiv recommend")

    def test_autonomous_group_agent_routes_bare_pixiv_recommendation(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "给我来点pixiv", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.command_type.value, "pixiv")
        self.assertEqual(decision.message_content, ".pixiv recommend")

    def test_autonomous_group_agent_routes_pixiv_search_after_cue(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "来点pixiv 斯卡蒂", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.command_type.value, "pixiv")
        self.assertEqual(decision.message_content, ".pixiv 斯卡蒂")

    def test_autonomous_group_agent_routes_pixiv_pid(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "帮我看一下pixiv 12345678", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.message_content, ".pixiv 12345678")

    def test_autonomous_group_agent_routes_ygo_lookup(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "游戏王查卡 青眼白龙", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.command_type.value, "YGO")
        self.assertEqual(decision.message_content, ".YGO 青眼白龙")

    def test_autonomous_group_agent_routes_reversed_ygo_lookup(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "查一下青眼白龙这张游戏王卡", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.command_type.value, "YGO")
        self.assertEqual(decision.message_content, ".YGO 青眼白龙")

    def test_autonomous_group_agent_routes_drawing_request(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "帮我画 一只猫坐在键盘上", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.command_type.value, "draw")
        self.assertEqual(decision.message_content, ".draw 一只猫坐在键盘上")

    def test_autonomous_group_agent_routes_short_drawing_request(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "画张猫猫", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.command_type.value, "draw")
        self.assertEqual(decision.message_content, ".draw 猫猫")

    def test_autonomous_group_agent_routes_generated_image_request(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "生成图片 猫猫", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.command_type.value, "draw")
        self.assertEqual(decision.message_content, ".draw 猫猫")

    def test_autonomous_group_agent_routes_p5_card_request(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "生成P5预告信 群友今晚必早睡", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.command_type.value, "P5")
        self.assertEqual(decision.message_content, ".P5 群友今晚必早睡")

    def test_autonomous_group_agent_routes_markdown_render_request(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "渲染markdown: # 标题", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.command_type.value, "markdown")
        self.assertEqual(decision.message_content, ".md # 标题")

    def test_autonomous_group_agent_routes_typst_render_request(self):
        orchestrator = self.make_orchestrator(enabled=True)

        decision = orchestrator.decide_group(100, "渲染typst: $x^2$", [])

        self.assertEqual(decision.action, self.agent_orchestrator.AgentAction.TOOL)
        self.assertEqual(decision.command_type.value, "typst")
        self.assertEqual(decision.message_content, ".typ $x^2$")

    def test_handle_group_message_routes_autonomous_tool_without_exception(self):
        class FakeCommandHandler:
            def __init__(self):
                self.calls = []

            def is_user_banned(self, _user_id):
                return False

            def is_group_bot_banned(self, _group_id):
                return False

            def get_command_type(self, _message_content):
                return None

            def is_group_agent_enabled(self, _group_id):
                return True

            def recent_jm_recommendation_at(self, _group_id, _index):
                return None, 0

            async def handle_command(self, _ws, message_type, command_type, message_content, **kwargs):
                self.calls.append((message_type, command_type, message_content, kwargs))
                return True

        command_handler = FakeCommandHandler()
        interfaces = {
            "bot_qq": 42,
            "test_if_super_user": lambda _user_id: False,
            "encode_message_to_CQ": lambda _segments: asyncio.sleep(0, result="我想看JM1436338了，丛雨能帮我获取一下吗"),
        }
        orchestrator = self.agent_orchestrator.AgentOrchestrator(
            interfaces,
            command_handler,
            persona_engine=None,
            session_manager=types.SimpleNamespace(memory=None),
            multimodal_processor=lambda _segments, content: asyncio.sleep(0, result=content),
        )

        result = asyncio.run(
            orchestrator.handle_group_message(
                None,
                {"group_id": 100, "user_id": 2, "message": [{"type": "text", "data": {"text": "x"}}]},
            )
        )

        self.assertTrue(result.handled)
        self.assertEqual(command_handler.calls[0][0], self.command_handlers.MessageType.GROUP)
        self.assertEqual(command_handler.calls[0][1].value, "jm")
        self.assertEqual(command_handler.calls[0][2], ".jm 1436338")

    def test_handle_group_message_routes_autonomous_non_jm_tool(self):
        class FakeCommandHandler:
            def __init__(self):
                self.calls = []

            def is_user_banned(self, _user_id):
                return False

            def is_group_bot_banned(self, _group_id):
                return False

            def get_command_type(self, _message_content):
                return None

            def is_group_agent_enabled(self, _group_id):
                return True

            def recent_jm_recommendation_at(self, _group_id, _index):
                return None, 0

            async def handle_command(self, _ws, message_type, command_type, message_content, **kwargs):
                self.calls.append((message_type, command_type, message_content, kwargs))
                return True

        command_handler = FakeCommandHandler()
        interfaces = {
            "bot_qq": 42,
            "test_if_super_user": lambda _user_id: False,
            "encode_message_to_CQ": lambda _segments: asyncio.sleep(0, result="给我来点pixiv"),
        }
        orchestrator = self.agent_orchestrator.AgentOrchestrator(
            interfaces,
            command_handler,
            persona_engine=None,
            session_manager=types.SimpleNamespace(memory=None),
            multimodal_processor=lambda _segments, content: asyncio.sleep(0, result=content),
        )

        result = asyncio.run(
            orchestrator.handle_group_message(
                None,
                {"group_id": 100, "user_id": 2, "message": [{"type": "text", "data": {"text": "x"}}]},
            )
        )

        self.assertTrue(result.handled)
        self.assertEqual(command_handler.calls[0][0], self.command_handlers.MessageType.GROUP)
        self.assertEqual(command_handler.calls[0][1].value, "pixiv")
        self.assertEqual(command_handler.calls[0][2], ".pixiv recommend")

    def test_handle_group_message_answers_autonomous_public_question(self):
        class FakeCommandHandler:
            def is_user_banned(self, _user_id):
                return False

            def is_group_bot_banned(self, _group_id):
                return False

            def get_command_type(self, _message_content):
                return None

            def is_group_agent_enabled(self, _group_id):
                return True

            def recent_jm_recommendation_at(self, _group_id, _index):
                return None, 0

        class FakePersonaEngine:
            def prepare(self, _user_id, message_content):
                return types.SimpleNamespace(
                    message_content=message_content,
                    system_role="",
                    blocked_override=False,
                    blocked_reasons=[],
                    mode="normal",
                )

        class FakeGroupSession:
            async def handle_message(self, _user_id, message_content, _system_role, **_kwargs):
                self.message_content = message_content
                return "模型蒸馏是把大模型能力迁移到小模型的一类训练方法。"

        sent = []
        group_session = FakeGroupSession()
        interfaces = {
            "bot_qq": 42,
            "test_if_super_user": lambda _user_id: False,
            "encode_message_to_CQ": lambda _segments: asyncio.sleep(0, result="模型蒸馏是什么？"),
            "decode_CQ_to_message": lambda text: asyncio.sleep(0, result=text),
            "send_group_message": lambda _ws, group_id, message: asyncio.sleep(0, result=sent.append((group_id, message))),
        }
        orchestrator = self.agent_orchestrator.AgentOrchestrator(
            interfaces,
            FakeCommandHandler(),
            persona_engine=FakePersonaEngine(),
            session_manager=types.SimpleNamespace(
                memory=None,
                get_group_session=lambda _group_id: group_session,
            ),
            multimodal_processor=lambda _segments, content: asyncio.sleep(0, result=content),
        )

        result = asyncio.run(
            orchestrator.handle_group_message(
                None,
                {"group_id": 100, "user_id": 2, "message": [{"type": "text", "data": {"text": "x"}}]},
            )
        )

        self.assertTrue(result.handled)
        self.assertEqual(result.action, self.agent_orchestrator.AgentAction.CHAT)
        self.assertEqual(group_session.message_content, "模型蒸馏是什么？")
        self.assertEqual(sent, [(100, "模型蒸馏是把大模型能力迁移到小模型的一类训练方法。")])


if __name__ == "__main__":
    unittest.main()
