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


if __name__ == "__main__":
    unittest.main()
