import asyncio
import os
import shutil
import subprocess
from enum import Enum
from typing import Optional

from plugins import P5_card, YGO_find_card, drawing, jm2pdf, markdown, typst_renderer
from tool_router import Tool, ToolRouter, ToolScope

_RESTART_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "run.bat",
)


class CommandType(Enum):
    HELP = "help"
    RESET = "reset"
    CLEAN = "clean"
    DRAW = "draw"
    TYPST = "typst"
    MARKDOWN = "markdown"
    YGO = "YGO"
    P5 = "P5"
    JM = "jm"


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
        self.help_message = """========================
.help              查看此帮助
.reset             重启 Bot            ★
.clean             清空当前群记忆      ★
.draw              AI 绘图
.typ / .typst      Typst 渲染
.md / .markdown    Markdown 渲染
.YGO               查询游戏王卡片
.P5                生成 P5 预告信
.jm                下载 JM 并生成 PDF
========================
★ 超级用户专属指令"""
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
                ),
                Tool(
                    name="clean",
                    command_type=CommandType.CLEAN,
                    prefixes=[".clean"],
                    group_handler=self._handle_clean_group,
                    private_handler=self._handle_clean_private,
                    description="清空当前群向量记忆",
                ),
                Tool(
                    name="draw",
                    command_type=CommandType.DRAW,
                    prefixes=[".draw"],
                    group_handler=self._handle_draw_group,
                    private_handler=self._handle_draw_private,
                    description="AI 绘图",
                ),
                Tool(
                    name="typst",
                    command_type=CommandType.TYPST,
                    prefixes=[".typst", ".typ"],
                    group_handler=self._handle_typst_group,
                    private_handler=self._handle_typst_private,
                    description="Typst 渲染",
                ),
                Tool(
                    name="markdown",
                    command_type=CommandType.MARKDOWN,
                    prefixes=[".markdown", ".md"],
                    group_handler=self._handle_markdown_group,
                    private_handler=self._handle_markdown_private,
                    description="Markdown 渲染",
                ),
                Tool(
                    name="ygo",
                    command_type=CommandType.YGO,
                    prefixes=[".YGO"],
                    group_handler=self._handle_ygo_group,
                    private_handler=self._handle_ygo_private,
                    description="查询游戏王卡片",
                ),
                Tool(
                    name="p5",
                    command_type=CommandType.P5,
                    prefixes=[".P5", ".p5"],
                    group_handler=self._handle_p5_group,
                    private_handler=self._handle_p5_private,
                    description="生成 P5 预告信",
                ),
                Tool(
                    name="jm",
                    command_type=CommandType.JM,
                    prefixes=[".jm", ".JM"],
                    group_handler=self._handle_jm_group,
                    private_handler=self._handle_jm_private,
                    description="下载 JM 并生成 PDF",
                ),
            ]
        )

    def get_command_type(self, message_content: str) -> Optional[CommandType]:
        return self.tool_router.match_command_type(message_content)

    def extract_command_content(self, message_content: str, command_type: CommandType) -> str:
        return self.tool_router.extract_content(message_content, command_type)

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

    async def _handle_help_group(self, ws, message_content: str, group_id: int, **kwargs):
        await self._send_group_text(ws, group_id, self.help_message)

    async def _handle_help_private(self, ws, message_content: str, user_id: int, **kwargs):
        await self._send_private_text(ws, user_id, self.help_message)

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
        subprocess.Popen(
            ["cmd.exe", "/c", _RESTART_SCRIPT],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
        )

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
            await self._send_group_text(ws, group_id, "已清空本群的向量记忆")
        else:
            await self._send_group_text(ws, group_id, "清空失败，记忆模块尚未就绪")

    async def _handle_clean_private(self, ws, message_content: str, user_id: int, **kwargs):
        await self._send_private_text(ws, user_id, "私聊暂无向量记忆可清理")

    async def _handle_draw_group(self, ws, message_content: str, group_id: int, **kwargs):
        image_cq_code = await drawing.handle_drawing_message(message_content)
        await self._send_group_text(ws, group_id, image_cq_code or "绘图服务暂时不可用")

    async def _handle_draw_private(self, ws, message_content: str, user_id: int, **kwargs):
        image_cq_code = await drawing.handle_drawing_message(message_content)
        await self._send_private_text(ws, user_id, image_cq_code or "绘图服务暂时不可用")

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
        jm_pdf = await jm2pdf.get_pdf(command_content)
        if jm_pdf == 0:
            await self._send_group_text(ws, group_id, "抱歉，未找到相关本子信息。")
            return

        try:
            await self.bot_interfaces["upload_group_file"](
                ws,
                group_id,
                jm_pdf,
                f"{command_content}.pdf",
                "jm",
            )
            await self._send_group_text(ws, group_id, "发送完成")
        finally:
            self._cleanup_jm_tmp(jm_pdf, command_content)

    async def _handle_jm_private(self, ws, message_content: str, user_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.JM)
        jm_pdf = await jm2pdf.get_pdf(command_content)
        if jm_pdf == 0:
            await self._send_private_text(ws, user_id, "抱歉，未找到相关本子信息。")
            return

        try:
            await self.bot_interfaces["upload_private_file"](
                ws,
                user_id,
                jm_pdf,
                f"{command_content}.pdf",
            )
            await self._send_private_text(ws, user_id, "发送完成")
        finally:
            self._cleanup_jm_tmp(jm_pdf, command_content)

    def _cleanup_jm_tmp(self, jm_pdf: str, command_content: str):
        if jm_pdf and os.path.exists(jm_pdf):
            os.remove(jm_pdf)

        tmp_dir = os.path.join("Bot", "tmp", command_content)
        if os.path.isdir(tmp_dir):
            shutil.rmtree(tmp_dir, ignore_errors=True)
