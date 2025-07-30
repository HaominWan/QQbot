"""
命令处理器模块 - 使用枚举和字典映射重构命令处理逻辑
"""
import os
from enum import Enum
from typing import Callable, Dict, Optional, Tuple, Any
from models import Group, User
from plugins import *


class CommandType(Enum):
    """命令类型枚举"""
    HELP = "help"
    RESET = "reset"
    DRAW = "draw"
    TYPST = "typst"
    MARKDOWN = "markdown"
    YGO = "YGO"
    P5 = "P5"
    JM = "jm"


class MessageType(Enum):
    """消息类型枚举"""
    GROUP = "group"
    PRIVATE = "private"


class CommandHandler:
    """命令处理器类"""
    
    def __init__(self, bot_interfaces):
        self.bot_interfaces = bot_interfaces
        self.help_message = '''========================
.help           插件信息
.reset          重置对话
.draw           AI绘图
.typ/.typst     Typst渲染
.md/.markdown   Markdown渲染
.YGO            查询卡片信息
.P5             预告信
========================'''
        
        # 命令前缀映射到命令类型
        self.command_prefixes = {
            ".help": CommandType.HELP,
            ".reset": CommandType.RESET,
            ".draw": CommandType.DRAW,
            ".typ": CommandType.TYPST,
            ".typst": CommandType.TYPST,
            ".md": CommandType.MARKDOWN,
            ".markdown": CommandType.MARKDOWN,
            ".YGO": CommandType.YGO,
            ".P5": CommandType.P5,
            ".p5": CommandType.P5,
            ".jm": CommandType.JM,
            ".JM": CommandType.JM,
        }
        
        # 群组命令处理器映射
        self.group_handlers: Dict[CommandType, Callable] = {
            CommandType.HELP: self._handle_help_group,
            CommandType.RESET: self._handle_reset_group,
            CommandType.DRAW: self._handle_draw_group,
            CommandType.TYPST: self._handle_typst_group,
            CommandType.MARKDOWN: self._handle_markdown_group,
            CommandType.YGO: self._handle_ygo_group,
            CommandType.P5: self._handle_p5_group,
            CommandType.JM: self._handle_jm_group,
        }
        
        # 私聊命令处理器映射
        self.private_handlers: Dict[CommandType, Callable] = {
            CommandType.HELP: self._handle_help_private,
            CommandType.RESET: self._handle_reset_private,
            CommandType.DRAW: self._handle_draw_private,
            CommandType.TYPST: self._handle_typst_private,
            CommandType.MARKDOWN: self._handle_markdown_private,
            CommandType.YGO: self._handle_ygo_private,
            CommandType.P5: self._handle_p5_private,
            CommandType.JM: self._handle_jm_private,
        }

    def get_command_type(self, message_content: str) -> Optional[CommandType]:
        """根据消息内容获取命令类型"""
        for prefix, command_type in self.command_prefixes.items():
            if message_content.startswith(prefix):
                return command_type
        return None

    def extract_command_content(self, message_content: str, command_type: CommandType) -> str:
        """提取命令参数内容"""
        for prefix, cmd_type in self.command_prefixes.items():
            if cmd_type == command_type and message_content.startswith(prefix):
                return message_content[len(prefix):].strip()
        return ""

    async def handle_command(self, ws, message_type: MessageType, command_type: CommandType, 
                           message_content: str, **kwargs) -> bool:
        """处理命令"""
        try:
            if message_type == MessageType.GROUP:
                handler = self.group_handlers.get(command_type)
                if handler:
                    await handler(ws, message_content, **kwargs)
                    return True
            elif message_type == MessageType.PRIVATE:
                handler = self.private_handlers.get(command_type)
                if handler:
                    await handler(ws, message_content, **kwargs)
                    return True
        except Exception as e:
            print(f"命令处理错误: {e}")
            return False
        return False

    # 群组命令处理器
    async def _handle_help_group(self, ws, message_content: str, group_id: int, **kwargs):
        await self.bot_interfaces["send_group_message"](
            ws, group_id, 
            await self.bot_interfaces["decode_CQ_to_message"](self.help_message)
        )

    async def _handle_reset_group(self, ws, message_content: str, group_id: int, user_id: int, **kwargs):
        group = Group(group_id, self.bot_interfaces["bot_qq"])
        if self.bot_interfaces["test_if_super_user"](user_id):
            try:
                group.chat_history = []
                reset_message = "重置成功"
                await self.bot_interfaces["send_group_message"](
                    ws, group_id, 
                    await self.bot_interfaces["decode_CQ_to_message"](reset_message)
                )
            except:
                reset_message = "重置失败"
                await self.bot_interfaces["send_group_message"](
                    ws, group_id, 
                    await self.bot_interfaces["decode_CQ_to_message"](reset_message)
                )
        else:
            reset_message = "抱歉，您没有权限重置对话"
            await self.bot_interfaces["send_group_message"](
                ws, group_id, 
                await self.bot_interfaces["decode_CQ_to_message"](reset_message)
            )

    async def _handle_draw_group(self, ws, message_content: str, group_id: int, **kwargs):
        image_cq_code = await drawing.handle_drawing_message(message_content)
        if image_cq_code is None:
            image_cq_code = "抱歉，目前无法为您提供绘图服务，请尝试使用其他指令。"
        try:
            await self.bot_interfaces["send_group_message"](
                ws, group_id, 
                await self.bot_interfaces["decode_CQ_to_message"](image_cq_code)
            )
        except:
            await self.bot_interfaces["send_group_message"](
                ws, group_id, 
                await self.bot_interfaces["decode_CQ_to_message"](
                    "抱歉，目前无法为您提供绘图服务，请尝试使用其他指令。"
                )
            )

    async def _handle_typst_group(self, ws, message_content: str, group_id: int, **kwargs):
        image_cq_code = await typst_renderer.handle_typst_message(message_content)
        try:
            await self.bot_interfaces["send_group_message"](
                ws, group_id, 
                await self.bot_interfaces["decode_CQ_to_message"](image_cq_code)
            )
        except:
            await self.bot_interfaces["send_group_message"](
                ws, group_id, 
                await self.bot_interfaces["decode_CQ_to_message"](
                    "抱歉，目前无法为您提供Typst渲染服务，请尝试使用其他指令。"
                )
            )

    async def _handle_markdown_group(self, ws, message_content: str, group_id: int, **kwargs):
        image_cq_code = await markdown.handle_markdown_message(message_content)
        try:
            await self.bot_interfaces["send_group_message"](
                ws, group_id, 
                await self.bot_interfaces["decode_CQ_to_message"](image_cq_code)
            )
        except:
            await self.bot_interfaces["send_group_message"](
                ws, group_id, 
                await self.bot_interfaces["decode_CQ_to_message"](
                    "抱歉，目前无法为您提供Markdown渲染服务，请尝试使用其他指令。"
                )
            )

    async def _handle_ygo_group(self, ws, message_content: str, group_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.YGO)
        card_info = await YGO_find_card.get_card_info(command_content)
        try:
            await self.bot_interfaces["send_group_message"](ws, group_id, card_info)
        except:
            await self.bot_interfaces["send_group_message"](ws, group_id, "抱歉，未找到相关卡片信息。")

    async def _handle_p5_group(self, ws, message_content: str, group_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.P5)
        card_image = await P5_card.get_card(command_content)
        try:
            await self.bot_interfaces["send_group_message"](ws, group_id, card_image)
        except:
            await self.bot_interfaces["send_group_message"](ws, group_id, "怪盗团有点繁忙")

    async def _handle_jm_group(self, ws, message_content: str, group_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.JM)
        jm_pdf = await jm2pdf.get_pdf(command_content)
        if jm_pdf == 0:
            await self.bot_interfaces["send_group_message"](ws, group_id, "抱歉，未找到相关本子信息。")
        else:
            try:
                await self.bot_interfaces["upload_group_file"](
                    group_id, jm_pdf, {command_content + ".pdf"}, "jm"
                )
                await self.bot_interfaces["send_group_message"](ws, group_id, "少🦌点哟。")
            except:
                await self.bot_interfaces["send_group_message"](
                    ws, group_id, "抱歉，查询功能暂时无法提供服务，请尝试使用其他指令。"
                )
            finally:
                os.remove(jm_pdf)
                os.rmdir(f"Bot/tmp/{command_content}")

    # 私聊命令处理器
    async def _handle_help_private(self, ws, message_content: str, user_id: int, **kwargs):
        await self.bot_interfaces["send_private_message"](
            ws, user_id, 
            await self.bot_interfaces["decode_CQ_to_message"](self.help_message)
        )

    async def _handle_reset_private(self, ws, message_content: str, user_id: int, **kwargs):
        user = User(user_id, self.bot_interfaces["test_if_super_user"](user_id), self.bot_interfaces["bot_qq"])
        try:
            user.chat_history = []
            reset_message = "重置成功"
            await self.bot_interfaces["send_private_message"](
                ws, user_id, 
                await self.bot_interfaces["decode_CQ_to_message"](reset_message)
            )
        except:
            reset_message = "重置失败"
            await self.bot_interfaces["send_private_message"](
                ws, user_id, 
                await self.bot_interfaces["decode_CQ_to_message"](reset_message)
            )

    async def _handle_draw_private(self, ws, message_content: str, user_id: int, **kwargs):
        image_cq_code = await drawing.handle_drawing_message(message_content)
        try:
            await self.bot_interfaces["send_private_message"](
                ws, user_id, 
                await self.bot_interfaces["decode_CQ_to_message"](image_cq_code)
            )
        except:
            await self.bot_interfaces["send_private_message"](
                ws, user_id, 
                await self.bot_interfaces["decode_CQ_to_message"](
                    "抱歉，目前无法为您提供绘图服务，请尝试使用其他指令。"
                )
            )

    async def _handle_typst_private(self, ws, message_content: str, user_id: int, **kwargs):
        image_cq_code = await typst_renderer.handle_typst_message(message_content)
        try:
            await self.bot_interfaces["send_private_message"](
                ws, user_id, 
                await self.bot_interfaces["decode_CQ_to_message"](image_cq_code)
            )
        except:
            await self.bot_interfaces["send_private_message"](
                ws, user_id, 
                await self.bot_interfaces["decode_CQ_to_message"](
                    "抱歉，目前无法为您提供Typst渲染服务，请尝试使用其他指令。"
                )
            )

    async def _handle_markdown_private(self, ws, message_content: str, user_id: int, **kwargs):
        image_cq_code = await markdown.handle_markdown_message(message_content)
        try:
            await self.bot_interfaces["send_private_message"](
                ws, user_id, 
                await self.bot_interfaces["decode_CQ_to_message"](image_cq_code)
            )
        except:
            await self.bot_interfaces["send_private_message"](
                ws, user_id, 
                await self.bot_interfaces["decode_CQ_to_message"](
                    "抱歉，目前无法为您提供Markdown渲染服务，请尝试使用其他指令。"
                )
            )

    async def _handle_ygo_private(self, ws, message_content: str, user_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.YGO)
        card_info = await YGO_find_card.get_card_info(command_content)
        try:
            await self.bot_interfaces["send_private_message"](ws, user_id, card_info)
        except:
            await self.bot_interfaces["send_private_message"](ws, user_id, "抱歉，未找到相关卡片信息。")

    async def _handle_p5_private(self, ws, message_content: str, user_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.P5)
        card_image = await P5_card.get_card(command_content)
        try:
            await self.bot_interfaces["send_private_message"](ws, user_id, card_image)
        except:
            await self.bot_interfaces["send_private_message"](ws, user_id, "怪盗团有点繁忙")

    async def _handle_jm_private(self, ws, message_content: str, user_id: int, **kwargs):
        command_content = self.extract_command_content(message_content, CommandType.JM)
        jm_pdf = await jm2pdf.get_pdf(command_content)
        if jm_pdf == 0:
            await self.bot_interfaces["send_private_message"](ws, user_id, "抱歉，未找到相关本子信息。")
        else:
            try:
                await self.bot_interfaces["upload_private_file"](
                    user_id, jm_pdf, {command_content + ".pdf"}
                )
                await self.bot_interfaces["send_private_message"](ws, user_id, "少🦌点哟。")
            except:
                await self.bot_interfaces["send_private_message"](
                    ws, user_id, "抱歉，查询功能暂时无法提供服务，请尝试使用其他指令。"
                )
            finally:
                os.remove(jm_pdf)
                os.rmdir(f"Bot/tmp/{command_content}")
