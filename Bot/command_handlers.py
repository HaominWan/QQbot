import asyncio
import os
import re
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Optional

from plugins import P5_card, YGO_find_card, drawing, jm2pdf, markdown, pixiv, typst_renderer
from plugin_state import GroupBotBanStore, GroupPluginBanStore, UserBanStore
from tool_router import Tool, ToolRouter, ToolScope

_BOT_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _BOT_DIR.parent
_WINDOWS_RESTART_SCRIPT = _ROOT_DIR / "run.bat"
_USER_BAN_RE = re.compile(r"^(?:user|qq)\s*[:：]?\s*(?:\[CQ:at,qq=)?(\d+)", re.I)


class CommandType(Enum):
    HELP = "help"
    RESET = "reset"
    STOP = "stop"
    CLEAN = "clean"
    DRAW = "draw"
    TYPST = "typst"
    MARKDOWN = "markdown"
    YGO = "YGO"
    P5 = "P5"
    JM = "jm"
    PIXIV = "pixiv"
    BAN = "ban"
    UNBAN = "unban"


class MessageType(Enum):
    GROUP = "group"
    PRIVATE = "private"


class CommandHandler:
    """Command facade backed by ToolRouter."""

    def __init__(self, bot_interfaces, user_sessions, session_manager=None):
        self.bot_interfaces = bot_interfaces
        self.user_sessions = user_sessions
        self.session_manager = session_manager
        self.tool_router = ToolRouter()
        self.group_bot_bans = GroupBotBanStore(_BOT_DIR / "data" / "group_bot_bans.json")
        self.group_plugin_bans = GroupPluginBanStore(_BOT_DIR / "data" / "group_plugin_bans.json")
        self.user_bans = UserBanStore(_BOT_DIR / "data" / "banned_users.json")
        self.help_message = """========================
.help              查看此帮助
.help <插件名>     查看插件语法
.reset             重启 Bot            ★
.stop              强制停止 Bot        ★
.clean             清空当前群记忆      ★
.ban / .unban      禁用管理            ★
.draw              AI 绘图
.typ / .typst      Typst 渲染
.md / .markdown    Markdown 渲染
.YGO               查询游戏王卡片
.P5                生成 P5 预告信
.jm                下载 JM 并生成 PDF
.jm recommend      今日 JM 推荐
.pixiv             Pixiv 搜图
========================
★ 超级用户专属指令"""
        self.plugin_help_messages = {
            "pixiv": """Pixiv 插件语法

.pixiv <关键词> [-n 数量]
按角色/tag/标题搜索，默认返回 1 张，数量上限由 pixiv_settings.max_count 控制。
示例：.pixiv 斯卡蒂
示例：.pixiv character:斯卡蒂 -n 2

.pixiv drawer:<画师名> [-n 数量]
按画师搜索作品。
示例：.pixiv drawer:toi8

.pixiv <PID>
按作品 PID 直接获取。
示例：.pixiv 12345678

.pixiv recommend [-n 数量]
从 Pixiv 日榜里随机推荐高质量图。
示例：.pixiv recommend -n 2""",
            "jm": """JM 插件语法

.jm <编号>
下载指定 JM 本子并生成 PDF。
示例：.jm 123456

.jm recommend [数量]
获取今日 JM 推荐栏编号，默认 10 个、最多 20 个。
示例：.jm recommend 5

.jm recommend debug
导出 JM 推荐栏解析调试日志。
示例：.jm debug""",
            "ban": """Ban 管理语法

.ban this
禁用 Bot 在当前群聊的所有回复。

.unban this
恢复 Bot 在当前群聊的回复。

.ban <插件名>
在当前群禁用可管理插件，例如 .ban jm。

.unban <插件名>
在当前群重新启用插件，例如 .unban jm。

.ban user:<QQ号>
禁止 Bot 回复指定用户，群聊和私聊均生效。

.unban user:<QQ号>
解除指定用户的回复封禁。""",
        }
        self._register_tools()

    def _register_tools(self):
        self.tool_router.register_many(
            [
                Tool(
                    name="help",
                    command_type=CommandType.HELP,
                    prefixes=[".help"],
                    group_handler=self._handle_help_group,
                    private_handler=self._handle_help_private,
                    description="显示插件信息",
                ),
                Tool(
                    name="reset",
                    command_type=CommandType.RESET,
                    prefixes=[".reset"],
                    group_handler=self._handle_reset_group,
                    private_handler=self._handle_reset_private,
                    description="重启 Bot",
                    super_only=True,
                ),
                Tool(
                    name="stop",
                    command_type=CommandType.STOP,
                    prefixes=[".stop"],
                    group_handler=self._handle_stop_group,
                    private_handler=self._handle_stop_private,
                    description="强制停止 Bot",
                    super_only=True,
                ),
                Tool(
                    name="clean",
                    command_type=CommandType.CLEAN,
                    prefixes=[".clean"],
                    group_handler=self._handle_clean_group,
                    private_handler=self._handle_clean_private,
                    description="清空当前群向量记忆",
                    super_only=True,
                ),
                Tool(
                    name="ban",
                    command_type=CommandType.BAN,
                    prefixes=[".ban"],
                    group_handler=self._handle_ban_group,
                    private_handler=self._handle_ban_private,
                    description="禁用本群插件",
                    super_only=True,
                ),
                Tool(
                    name="unban",
                    command_type=CommandType.UNBAN,
                    prefixes=[".unban"],
                    group_handler=self._handle_unban_group,
                    private_handler=self._handle_unban_private,
                    description="启用本群插件",
                    super_only=True,
                ),
                Tool(
                    name="draw",
                    command_type=CommandType.DRAW,
                    prefixes=[".draw"],
                    group_handler=self._handle_draw_group,
                    private_handler=self._handle_draw_private,
                    description="AI 绘图",
                    controllable=True,
                ),
                Tool(
                    name="typst",
                    command_type=CommandType.TYPST,
                    prefixes=[".typst", ".typ"],
                    group_handler=self._handle_typst_group,
                    private_handler=self._handle_typst_private,
                    description="Typst 渲染",
                    controllable=True,
                ),
                Tool(
                    name="markdown",
                    command_type=CommandType.MARKDOWN,
                    prefixes=[".markdown", ".md"],
                    group_handler=self._handle_markdown_group,
                    private_handler=self._handle_markdown_private,
                    description="Markdown 渲染",
                    controllable=True,
                ),
                Tool(
                    name="ygo",
                    command_type=CommandType.YGO,
                    prefixes=[".YGO"],
                    group_handler=self._handle_ygo_group,
                    private_handler=self._handle_ygo_private,
                    description="查询游戏王卡片",
                    controllable=True,
                ),
                Tool(
                    name="p5",
                    command_type=CommandType.P5,
                    prefixes=[".P5", ".p5"],
                    group_handler=self._handle_p5_group,
                    private_handler=self._handle_p5_private,
                    description="生成 P5 预告信",
                    controllable=True,
                ),
                Tool(
                    name="jm",
                    command_type=CommandType.JM,
                    prefixes=[".jm", ".JM"],
                    group_handler=self._handle_jm_group,
                    private_handler=self._handle_jm_private,
                    description="下载 JM 并生成 PDF",
                    controllable=True,
                ),
                Tool(
                    name="pixiv",
                    command_type=CommandType.PIXIV,
                    prefixes=[".pixiv", ".pid"],
                    group_handler=self._handle_pixiv_group,
                    private_handler=self._handle_pixiv_private,
                    description="Pixiv 搜图",
                    controllable=True,
                ),
            ]
        )

    def get_command_type(self, message_content: str) -> Optional[CommandType]:
        return self.tool_router.match_command_type(message_content)

    def extract_command_content(self, message_content: str, command_type: CommandType) -> str:
        return self.tool_router.extract_content(message_content, command_type)

    def is_user_banned(self, user_id: int | str) -> bool:
        return self.user_bans.is_banned(user_id)

    def is_group_bot_banned(self, group_id: int | str) -> bool:
        return self.group_bot_bans.is_banned(group_id)

    def is_group_unban_this_command(self, message_content: str) -> bool:
        command_type = self.get_command_type(message_content)
        if command_type != CommandType.UNBAN:
            return False
        return self.extract_command_content(message_content, CommandType.UNBAN).strip().lower() == "this"

    async def handle_command(
        self,
        ws,
        message_type: MessageType,
        command_type: CommandType,
        message_content: str,
        **kwargs,
    ) -> bool:
        try:
            scope = ToolScope(message_type.value)
            if await self._block_banned_group_tool(scope, command_type, ws, **kwargs):
                return True
            return await self.tool_router.handle(
                scope,
                command_type,
                ws,
                message_content,
                **kwargs,
            )
        except Exception as exc:
            print(f"[Command] Failed to handle {command_type}: {exc}")
            return False

    async def _block_banned_group_tool(self, scope: ToolScope, command_type: CommandType, ws, **kwargs) -> bool:
        if scope != ToolScope.GROUP:
            return False

        tool = self.tool_router.get_tool(command_type)
        group_id = kwargs.get("group_id")
        if tool is None or not tool.controllable or group_id is None:
            return False

        if not self.group_plugin_bans.is_banned(group_id, tool.name):
            return False

        await self._send_group_text(
            ws,
            group_id,
            f"{tool.name} 插件已在本群禁用，请联系超级用户使用 .unban {tool.name} 启用",
        )
        return True

    async def _send_group_text(self, ws, group_id: int, text: str):
        await self.bot_interfaces["send_group_message"](
            ws,
            group_id,
            await self.bot_interfaces["decode_CQ_to_message"](text),
        )

    async def _send_private_text(self, ws, user_id: int, text: str):
        await self.bot_interfaces["send_private_message"](
            ws,
            user_id,
            await self.bot_interfaces["decode_CQ_to_message"](text),
        )

    def _get_help_message(self, message_content: str) -> str:
        topic = self.extract_command_content(message_content, CommandType.HELP).strip()
        if not topic:
            return self.help_message

        topic_key = topic.lstrip(".").lower()
        help_message = self.plugin_help_messages.get(topic_key)
        if help_message:
            return help_message

        tool = self.tool_router.find_tool(topic_key)
        if tool:
            aliases = " / ".join(tool.prefixes)
            return f"{tool.name} 插件\n指令：{aliases}\n说明：{tool.description}\n暂无更详细语法。"

        available = "、".join(sorted(self.plugin_help_messages))
        return f"未找到 {topic} 的帮助。可用专题：{available}"

    async def _handle_help_group(self, ws, message_content: str, group_id: int, **kwargs):
        await self._send_group_text(ws, group_id, self._get_help_message(message_content))

    async def _handle_help_private(self, ws, message_content: str, user_id: int, **kwargs):
        await self._send_private_text(ws, user_id, self._get_help_message(message_content))

    async def _handle_reset_group(
        self,
        ws,
        message_content: str,
        group_id: int,
        user_id: int,
        **kwargs,
    ):
        if not self.bot_interfaces["test_if_super_user"](user_id):
            await self._send_group_text(ws, group_id, "权限不足，仅超级用户可重启 Bot")
            return
        await self._send_group_text(ws, group_id, "Bot 重启中，稍后见~")
        await self._trigger_restart()

    async def _handle_reset_private(self, ws, message_content: str, user_id: int, **kwargs):
        if not self.bot_interfaces["test_if_super_user"](user_id):
            await self._send_private_text(ws, user_id, "权限不足，仅超级用户可重启 Bot")
            return
        await self._send_private_text(ws, user_id, "Bot 重启中，稍后见~")
        await self._trigger_restart()

    async def _trigger_restart(self):
        await asyncio.sleep(0.8)
        if os.name == "nt":
            subprocess.Popen(
                ["cmd.exe", "/c", str(_WINDOWS_RESTART_SCRIPT)],
                creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            return

        restart_code = (
            "import os, sys, time; "
            "time.sleep(1); "
            f"os.chdir({str(_BOT_DIR)!r}); "
            f"os.execv({sys.executable!r}, [{sys.executable!r}, 'bot.py'])"
        )
        log_path = _ROOT_DIR / "startup.log"
        log = open(log_path, "ab")
        subprocess.Popen(
            [sys.executable, "-c", restart_code],
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
        os._exit(0)

    async def _handle_stop_group(
        self,
        ws,
        message_content: str,
        group_id: int,
        user_id: int,
        **kwargs,
    ):
        if not self.bot_interfaces["test_if_super_user"](user_id):
            await self._send_group_text(ws, group_id, "权限不足，仅超级用户可停止 Bot")
            return
        await self._send_group_text(ws, group_id, "Bot 已停止，再见~")
        await self._do_stop()

    async def _handle_stop_private(self, ws, message_content: str, user_id: int, **kwargs):
        if not self.bot_interfaces["test_if_super_user"](user_id):
            await self._send_private_text(ws, user_id, "权限不足，仅超级用户可停止 Bot")
            return
        await self._send_private_text(ws, user_id, "Bot 已停止，再见~")
        await self._do_stop()

    async def _do_stop(self):
        await asyncio.sleep(0.8)
        if os.name == "nt":
            # Only kill the NapCat-injected QQ process (identified by --enable-logging).
            # Plain personal QQ does not carry this flag and must not be touched.
            subprocess.run(
                [
                    "wmic", "process",
                    "where", "name='QQ.exe' and commandline like '%--enable-logging%'",
                    "call", "terminate",
                ],
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        os._exit(0)

    async def _handle_clean_group(
        self,
        ws,
        message_content: str,
        group_id: int,
        user_id: int,
        **kwargs,
    ):
        if not self.bot_interfaces["test_if_super_user"](user_id):
            await self._send_group_text(ws, group_id, "权限不足，仅超级用户可清空记忆")
            return
        memory = getattr(self.session_manager, "memory", None) if self.session_manager else None
        if not memory:
            await self._send_group_text(ws, group_id, "向量记忆未启用")
            return
        if memory.clear(group_id):
            if self.session_manager:
                self.session_manager.reset_group_session(group_id)
            await self._send_group_text(ws, group_id, "已清空本群的向量记忆和当前对话上下文")
        else:
            await self._send_group_text(ws, group_id, "清空失败，记忆模块尚未就绪")

    async def _handle_clean_private(self, ws, message_content: str, user_id: int, **kwargs):
        await self._send_private_text(ws, user_id, "私聊暂无向量记忆可清理")

    def _manageable_tool_names(self) -> str:
        return "、".join(tool.name for tool in self.tool_router.controllable_tools())

    def _resolve_manageable_tool(self, raw_name: str):
        tool = self.tool_router.find_tool(raw_name)
        if tool is None or not tool.controllable:
            return None
        return tool

    @staticmethod
    def _parse_user_ban_target(raw_content: str) -> Optional[int]:
        match = _USER_BAN_RE.match(raw_content.strip())
        if not match:
            return None
        return int(match.group(1))

    async def _handle_ban_group(
        self,
        ws,
        message_content: str,
        group_id: int,
        user_id: int,
        **kwargs,
    ):
        if not self.bot_interfaces["test_if_super_user"](user_id):
            await self._send_group_text(ws, group_id, "权限不足，仅超级用户可禁用插件")
            return

        raw_name = self.extract_command_content(message_content, CommandType.BAN)
        if raw_name.strip().lower() == "this":
            changed = self.group_bot_bans.ban(group_id)
            if changed:
                await self._send_group_text(ws, group_id, "已禁用 Bot 在本群的回复，使用 .unban this 恢复")
            else:
                await self._send_group_text(ws, group_id, "Bot 已经在本群禁用回复")
            return

        banned_user_id = self._parse_user_ban_target(raw_name)
        if banned_user_id is not None:
            if self.bot_interfaces["test_if_super_user"](banned_user_id):
                await self._send_group_text(ws, group_id, "不能封禁超级用户，避免管理入口被锁住")
                return

            changed = self.user_bans.ban(banned_user_id)
            if changed:
                await self._send_group_text(ws, group_id, f"已禁止 Bot 回复用户 {banned_user_id}")
            else:
                await self._send_group_text(ws, group_id, f"用户 {banned_user_id} 已在回复封禁列表中")
            return

        tool = self._resolve_manageable_tool(raw_name)
        if tool is None:
            await self._send_group_text(ws, group_id, f"请输入可管理插件名：{self._manageable_tool_names()}，或使用 .ban user:<QQ号>")
            return

        changed = self.group_plugin_bans.ban(group_id, tool.name)
        if changed:
            await self._send_group_text(ws, group_id, f"已在本群禁用 {tool.name} 插件")
        else:
            await self._send_group_text(ws, group_id, f"{tool.name} 插件已经在本群禁用")

    async def _handle_unban_group(
        self,
        ws,
        message_content: str,
        group_id: int,
        user_id: int,
        **kwargs,
    ):
        if not self.bot_interfaces["test_if_super_user"](user_id):
            await self._send_group_text(ws, group_id, "权限不足，仅超级用户可启用插件")
            return

        raw_name = self.extract_command_content(message_content, CommandType.UNBAN)
        if raw_name.strip().lower() == "this":
            changed = self.group_bot_bans.unban(group_id)
            if changed:
                await self._send_group_text(ws, group_id, "已恢复 Bot 在本群的回复")
            else:
                await self._send_group_text(ws, group_id, "Bot 在本群本来就是可回复状态")
            return

        banned_user_id = self._parse_user_ban_target(raw_name)
        if banned_user_id is not None:
            changed = self.user_bans.unban(banned_user_id)
            if changed:
                await self._send_group_text(ws, group_id, f"已允许 Bot 回复用户 {banned_user_id}")
            else:
                await self._send_group_text(ws, group_id, f"用户 {banned_user_id} 本来就不在回复封禁列表中")
            return

        tool = self._resolve_manageable_tool(raw_name)
        if tool is None:
            await self._send_group_text(ws, group_id, f"请输入可管理插件名：{self._manageable_tool_names()}，或使用 .unban user:<QQ号>")
            return

        changed = self.group_plugin_bans.unban(group_id, tool.name)
        if changed:
            await self._send_group_text(ws, group_id, f"已在本群启用 {tool.name} 插件")
        else:
            await self._send_group_text(ws, group_id, f"{tool.name} 插件本来就是启用状态")

    async def _handle_ban_private(self, ws, message_content: str, user_id: int, **kwargs):
        if not self.bot_interfaces["test_if_super_user"](user_id):
            await self._send_private_text(ws, user_id, "权限不足，仅超级用户可禁用插件")
            return

        raw_name = self.extract_command_content(message_content, CommandType.BAN)
        banned_user_id = self._parse_user_ban_target(raw_name)
        if banned_user_id is None:
            await self._send_private_text(ws, user_id, "插件禁用只对当前群聊生效；私聊可使用 .ban user:<QQ号> 封禁用户回复")
            return

        if self.bot_interfaces["test_if_super_user"](banned_user_id):
            await self._send_private_text(ws, user_id, "不能封禁超级用户，避免管理入口被锁住")
            return

        changed = self.user_bans.ban(banned_user_id)
        if changed:
            await self._send_private_text(ws, user_id, f"已禁止 Bot 回复用户 {banned_user_id}")
        else:
            await self._send_private_text(ws, user_id, f"用户 {banned_user_id} 已在回复封禁列表中")

    async def _handle_unban_private(self, ws, message_content: str, user_id: int, **kwargs):
        if not self.bot_interfaces["test_if_super_user"](user_id):
            await self._send_private_text(ws, user_id, "权限不足，仅超级用户可启用插件")
            return

        raw_name = self.extract_command_content(message_content, CommandType.UNBAN)
        banned_user_id = self._parse_user_ban_target(raw_name)
        if banned_user_id is None:
            await self._send_private_text(ws, user_id, "插件启用只对当前群聊生效；私聊可使用 .unban user:<QQ号> 解除用户回复封禁")
            return

        changed = self.user_bans.unban(banned_user_id)
        if changed:
            await self._send_private_text(ws, user_id, f"已允许 Bot 回复用户 {banned_user_id}")
        else:
            await self._send_private_text(ws, user_id, f"用户 {banned_user_id} 本来就不在回复封禁列表中")

    async def _handle_draw_group(self, ws, message_content: str, group_id: int, **kwargs):
        prompt = self.extract_command_content(message_content, CommandType.DRAW)
        image_cq = await drawing.handle_drawing_message(prompt)
        await self._send_group_text(ws, group_id, image_cq)

    async def _handle_draw_private(self, ws, message_content: str, user_id: int, **kwargs):
        prompt = self.extract_command_content(message_content, CommandType.DRAW)
        image_cq = await drawing.handle_drawing_message(prompt)
        await self._send_private_text(ws, user_id, image_cq)

    async def _handle_typst_group(self, ws, message_content: str, group_id: int, **kwargs):
        image_cq_code = await typst_renderer.handle_typst_message(message_content)
        await self._send_group_text(ws, group_id, image_cq_code)

    async def _handle_typst_private(self, ws, message_content: str, user_id: int, **kwargs):
        image_cq_code = await typst_renderer.handle_typst_message(message_content)
        await self._send_private_text(ws, user_id, image_cq_code)

    async def _handle_markdown_group(self, ws, message_content: str, group_id: int, **kwargs):
        image_cq_code = await markdown.handle_markdown_message(message_content)
        await self._send_group_text(ws, group_id, image_cq_code)

    async def _handle_markdown_private(self, ws, message_content: str, user_id: int, **kwargs):
        image_cq_code = await markdown.handle_markdown_message(message_content)
        await self._send_private_text(ws, user_id, image_cq_code)

    async def _handle_ygo_group(self, ws, message_content: str, group_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.YGO)
        card_info = await YGO_find_card.get_card_info(command_content)
        await self.bot_interfaces["send_group_message"](
            ws,
            group_id,
            card_info or "抱歉，未找到相关卡片信息。",
        )

    async def _handle_ygo_private(self, ws, message_content: str, user_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.YGO)
        card_info = await YGO_find_card.get_card_info(command_content)
        await self.bot_interfaces["send_private_message"](
            ws,
            user_id,
            card_info or "抱歉，未找到相关卡片信息。",
        )

    async def _handle_p5_group(self, ws, message_content: str, group_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.P5)
        card_image = await P5_card.get_card(command_content)
        await self.bot_interfaces["send_group_message"](
            ws,
            group_id,
            card_image or "预告信生成失败",
        )

    async def _handle_p5_private(self, ws, message_content: str, user_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.P5)
        card_image = await P5_card.get_card(command_content)
        await self.bot_interfaces["send_private_message"](
            ws,
            user_id,
            card_image or "预告信生成失败",
        )

    async def _handle_jm_group(self, ws, message_content: str, group_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.JM)
        if self._is_jm_debug_command(command_content):
            await self._send_jm_debug_group(ws, group_id, command_content)
            return

        if self._is_jm_recommend_command(command_content):
            await self._send_jm_recommend_group(ws, group_id, command_content)
            return

        await self._send_group_text(ws, group_id, f"好好好，{command_content} 嘛，这就去给你搬过来~")
        jm_pdf = await jm2pdf.get_pdf(command_content)
        if jm_pdf == 0:
            await self._send_group_text(ws, group_id, f"翻了个遍没找到 {command_content}，编号没搞错吧？还是被和谐了？")
            return

        try:
            await self.bot_interfaces["upload_group_file"](
                ws,
                group_id,
                os.path.abspath(jm_pdf),
                f"{command_content}.pdf",
                "/",
            )
            await self._send_group_text(ws, group_id, "Get Da★Ze☆~ 少🦌一点哦，已发至群文件，好好欣赏哦")
        finally:
            self._cleanup_jm_tmp(jm_pdf, command_content)

    async def _handle_jm_private(self, ws, message_content: str, user_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.JM)
        if self._is_jm_debug_command(command_content):
            await self._send_jm_debug_private(ws, user_id, command_content)
            return

        if self._is_jm_recommend_command(command_content):
            await self._send_jm_recommend_private(ws, user_id, command_content)
            return

        await self._send_private_text(ws, user_id, f"好好好，{command_content} 嘛，这就去给你搬过来~")
        jm_pdf = await jm2pdf.get_pdf(command_content)
        if jm_pdf == 0:
            await self._send_private_text(ws, user_id, f"翻了个遍没找到 {command_content}，编号没搞错吧？还是被和谐了？")
            return

        try:
            await self.bot_interfaces["upload_private_file"](
                ws,
                user_id,
                os.path.abspath(jm_pdf),
                f"{command_content}.pdf",
            )
            await self._send_private_text(ws, user_id, "Get Da★Ze☆~ 少🦌一点哦，发过去了，好好欣赏哦")
        finally:
            self._cleanup_jm_tmp(jm_pdf, command_content)

    @staticmethod
    def _is_jm_recommend_command(command_content: str) -> bool:
        parts = command_content.strip().split(maxsplit=1)
        return bool(parts and parts[0].lower() in {"recommend", "rec", "daily", "today"})

    @staticmethod
    def _is_jm_debug_command(command_content: str) -> bool:
        parts = command_content.strip().lower().split()
        if not parts:
            return False
        if parts[0] in {"debug", "dbg", "log"}:
            return True
        return parts[0] in {"recommend", "rec", "daily", "today"} and any(
            part in {"debug", "dbg", "log"} for part in parts[1:]
        )

    @staticmethod
    def _parse_jm_recommend_limit(command_content: str) -> int:
        parts = command_content.strip().split()
        for part in parts[1:]:
            if part.isdigit():
                return max(1, min(int(part), 20))
        return 10

    @staticmethod
    def _format_jm_recommendations(recommendations: list[dict]) -> str:
        if not recommendations:
            return "没有解析到 Cxxx&推薦本本 栏目的 JM 编号"

        lines = ["Cxxx&推薦本本："]
        for index, item in enumerate(recommendations, start=1):
            title = item.get("title") or "未命名"
            album_id = item.get("id") or "未知"
            lines.append(f"{index}. JM{album_id} - {title}")
            tags = item.get("tags") or []
            if isinstance(tags, str):
                tags_text = tags
            else:
                tags_text = " / ".join(str(tag) for tag in tags[:8])
            if tags_text:
                lines.append(f"   Tags：{tags_text}")
        lines.append("发送 .jm <编号> 可下载对应 PDF")
        return "\n".join(lines)

    async def _send_jm_recommend_group(self, ws, group_id: int, command_content: str):
        limit = self._parse_jm_recommend_limit(command_content)
        await self._send_group_text(ws, group_id, "正在获取今日 JM 推荐栏...")
        recommendations = await jm2pdf.get_daily_recommendations(limit)
        await self._send_group_text(ws, group_id, self._format_jm_recommendations(recommendations))

    async def _send_jm_recommend_private(self, ws, user_id: int, command_content: str):
        limit = self._parse_jm_recommend_limit(command_content)
        await self._send_private_text(ws, user_id, "正在获取今日 JM 推荐栏...")
        recommendations = await jm2pdf.get_daily_recommendations(limit)
        await self._send_private_text(ws, user_id, self._format_jm_recommendations(recommendations))

    async def _send_jm_debug_group(self, ws, group_id: int, command_content: str):
        limit = self._parse_jm_recommend_limit(command_content)
        await self._send_group_text(ws, group_id, "正在导出 JM 推荐栏调试日志...")
        debug_log = await jm2pdf.export_recommend_debug_log(limit)
        try:
            await self.bot_interfaces["upload_group_file"](
                ws,
                group_id,
                os.path.abspath(debug_log),
                os.path.basename(debug_log),
                "/",
            )
            await self._send_group_text(ws, group_id, "已导出 JM 调试日志，发我这个 txt 就能继续定位。")
        except Exception as exc:
            await self._send_group_text(ws, group_id, f"调试日志已生成，但上传失败：{exc}\n本地路径：{debug_log}")

    async def _send_jm_debug_private(self, ws, user_id: int, command_content: str):
        limit = self._parse_jm_recommend_limit(command_content)
        await self._send_private_text(ws, user_id, "正在导出 JM 推荐栏调试日志...")
        debug_log = await jm2pdf.export_recommend_debug_log(limit)
        try:
            await self.bot_interfaces["upload_private_file"](
                ws,
                user_id,
                os.path.abspath(debug_log),
                os.path.basename(debug_log),
            )
            await self._send_private_text(ws, user_id, "已导出 JM 调试日志，发我这个 txt 就能继续定位。")
        except Exception as exc:
            await self._send_private_text(ws, user_id, f"调试日志已生成，但上传失败：{exc}\n本地路径：{debug_log}")

    async def _handle_pixiv_group(self, ws, message_content: str, group_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.PIXIV)
        pixiv_result = await pixiv.handle_pixiv_message(command_content)
        await self.bot_interfaces["send_group_message"](ws, group_id, pixiv_result)

    async def _handle_pixiv_private(self, ws, message_content: str, user_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.PIXIV)
        pixiv_result = await pixiv.handle_pixiv_message(command_content)
        await self.bot_interfaces["send_private_message"](ws, user_id, pixiv_result)

    def _cleanup_jm_tmp(self, jm_pdf: str, command_content: str):
        if jm_pdf and os.path.exists(jm_pdf):
            os.remove(jm_pdf)

        tmp_dir = _BOT_DIR / "tmp" / command_content
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
