import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional

from command_handlers import CommandType, MessageType
from plugins.markdown import markdown_to_image
from plugins.stickers import sticker_to_segment

# Matches both special tag types in one pass
_SPECIAL_RE   = re.compile(r'(<render_md>.*?</render_md>|<sticker:\w+>)', re.DOTALL)
_RENDER_MD_RE = re.compile(r'<render_md>(.*?)</render_md>', re.DOTALL)
_STICKER_RE   = re.compile(r'<sticker:(\w+)>')
_CQ_RE        = re.compile(r'\[CQ:[^\]]*\]')
_JM_AUTONOMOUS_RE = re.compile(
    r"(?:今天|今日|最近|还没|没看|想看|推荐|来点|有没有).{0,16}(?:jm|JM|本子)"
    r"|(?:jm|JM|本子).{0,16}(?:推荐|来点|看看|没看|想看)"
)
_HELP_QUESTION_RE = re.compile(
    r"(?:有人知道|有没有人知道|谁知道|求问|请问|想问一下).{0,80}"
    r"(?:是什么|什么是|怎么|如何|为什么|为啥|能不能|可以吗|吗|\?)"
)


MultimodalProcessor = Callable[[list, str], Awaitable[str]]


class AgentAction(Enum):
    IGNORE = "ignore"
    TOOL = "tool"
    CHAT = "chat"


@dataclass
class AgentDecision:
    action: AgentAction
    reason: str
    command_type: Optional[Any] = None
    message_content: Optional[str] = None


@dataclass
class AgentRunResult:
    handled: bool
    action: AgentAction
    reason: str


class AgentOrchestrator:
    """Coordinates command tools, persona prompts, sessions, and replies.

    This is deliberately small for now. It gives the bot a single agent entry
    point without forcing every plugin to become an LLM tool immediately.
    """

    def __init__(
        self,
        bot_interfaces: Dict[str, Any],
        command_handler,
        persona_engine,
        session_manager,
        multimodal_processor: MultimodalProcessor,
    ):
        self.bot_interfaces = bot_interfaces
        self.command_handler = command_handler
        self.persona_engine = persona_engine
        self.session_manager = session_manager
        self.multimodal_processor = multimodal_processor

    async def handle_group_message(self, ws, payload: Dict[str, Any]) -> AgentRunResult:
        group_id = int(payload["group_id"])
        user_id = int(payload["user_id"])
        message_id = payload.get("message_id")
        segments = payload.get("message", [])
        message_content = await self.bot_interfaces["encode_message_to_CQ"](segments)

        if self._is_blocked_user(user_id):
            print(f"[Agent] ignored banned group user {user_id}")
            return AgentRunResult(False, AgentAction.IGNORE, "user is banned")

        if self.command_handler.is_group_bot_banned(group_id):
            command_type = self.command_handler.get_command_type(message_content)
            if (
                command_type is not None
                and self.command_handler.is_group_unban_this_command(message_content)
                and self.bot_interfaces["test_if_super_user"](user_id)
            ):
                handled = await self.command_handler.handle_command(
                    ws,
                    MessageType.GROUP,
                    command_type,
                    message_content,
                    group_id=group_id,
                    user_id=user_id,
                    message_id=message_id,
                )
                return AgentRunResult(handled, AgentAction.TOOL, "matched group unban command")

            print(f"[Agent] ignored muted group {group_id}")
            return AgentRunResult(False, AgentAction.IGNORE, "group is muted")

        # Store every group message so the bot can recall group history later.
        memory = self.session_manager.memory
        if memory:
            memory.store(group_id, user_id, message_content, "user")

        decision = self.decide_group(group_id, message_content, segments)
        print(f"[Agent] group decision={decision.action.value} reason={decision.reason}")

        if decision.action == AgentAction.IGNORE:
            return AgentRunResult(False, decision.action, decision.reason)

        if decision.action == AgentAction.TOOL:
            tool_message = decision.message_content or message_content
            handled = await self.command_handler.handle_command(
                ws,
                MessageType.GROUP,
                decision.command_type,
                tool_message,
                group_id=group_id,
                user_id=user_id,
                message_id=message_id,
            )
            return AgentRunResult(handled, decision.action, decision.reason)

        message_content = await self._with_reply_context(ws, segments, message_content)
        message_content = await self.multimodal_processor(segments, message_content)

        persona_prompt = self.persona_engine.prepare(user_id, message_content)
        if persona_prompt.blocked_override:
            print(
                f"[Persona] Blocked override from group user {user_id}: "
                f"{', '.join(persona_prompt.blocked_reasons)}"
            )

        group = self.session_manager.get_group_session(group_id)
        response = await group.handle_message(
            user_id,
            persona_prompt.message_content,
            persona_prompt.system_role,
            store_user=False,
            mode=persona_prompt.mode,
        )
        segments = await self._build_message_segments(response)
        await self.bot_interfaces["send_group_message"](ws, group_id, segments)
        return AgentRunResult(True, decision.action, decision.reason)

    async def handle_private_message(self, ws, payload: Dict[str, Any]) -> AgentRunResult:
        user_id = int(payload["user_id"])
        segments = payload.get("message", [])
        message_content = await self.bot_interfaces["encode_message_to_CQ"](segments)

        if self._is_blocked_user(user_id):
            print(f"[Agent] ignored banned private user {user_id}")
            return AgentRunResult(False, AgentAction.IGNORE, "user is banned")

        decision = self.decide_private(message_content)
        print(f"[Agent] private decision={decision.action.value} reason={decision.reason}")

        if decision.action == AgentAction.TOOL:
            handled = await self.command_handler.handle_command(
                ws,
                MessageType.PRIVATE,
                decision.command_type,
                message_content,
                user_id=user_id,
            )
            return AgentRunResult(handled, decision.action, decision.reason)

        message_content = await self.multimodal_processor(segments, message_content)

        persona_prompt = self.persona_engine.prepare(user_id, message_content)
        if persona_prompt.blocked_override:
            print(
                f"[Persona] Blocked override from private user {user_id}: "
                f"{', '.join(persona_prompt.blocked_reasons)}"
            )
        print(f"[Persona] Using {persona_prompt.mode} mode for private user {user_id}")

        user_session = self.session_manager.get_private_session(user_id)
        response = await user_session.handle_message(
            persona_prompt.message_content,
            persona_prompt.system_role,
        )
        segments = await self._build_message_segments(response)
        await self.bot_interfaces["send_private_message"](ws, user_id, segments)
        return AgentRunResult(True, decision.action, decision.reason)

    async def _build_message_segments(self, response: str) -> List[dict]:
        """Split AI response into a mixed text+image OneBot segment list.

        Handles two special tag types inside the AI response:
          <render_md>…</render_md>  – render the enclosed markdown as a PNG image
          <sticker:name>            – insert the named pre-set sticker image

        Surrounding text may still contain CQ codes and is parsed normally.
        All failures degrade gracefully to plain text so nothing is lost silently.
        """
        if not _SPECIAL_RE.search(response):
            return await self.bot_interfaces["decode_CQ_to_message"](response)

        # split() with one capturing group → [text, tag, text, tag, …]
        parts = _SPECIAL_RE.split(response)
        result: List[dict] = []
        for i, part in enumerate(parts):
            if not part:
                continue
            if i % 2 == 0:
                # plain text segment (may contain CQ codes)
                result.extend(await self.bot_interfaces["decode_CQ_to_message"](part))
            elif part.startswith('<render_md>'):
                md_match = _RENDER_MD_RE.match(part)
                md_content = md_match.group(1).strip() if md_match else part
                md_content = _CQ_RE.sub('', md_content)
                try:
                    img_b64 = await markdown_to_image(md_content)
                    result.append({"type": "image", "data": {"file": f"base64://{img_b64}"}})
                except Exception as exc:
                    print(f"[Agent] markdown render failed, sending raw text: {exc}")
                    result.extend(await self.bot_interfaces["decode_CQ_to_message"](md_content))
            elif part.startswith('<sticker:'):
                name = _STICKER_RE.match(part).group(1)
                seg = sticker_to_segment(name)
                if seg:
                    result.append(seg)
                else:
                    print(f"[Agent] sticker not found: {name}")
        return result

    def decide_group(self, group_id: int, message_content: str, segments: list) -> AgentDecision:
        command_type = self.command_handler.get_command_type(message_content)
        if command_type:
            return AgentDecision(AgentAction.TOOL, "matched explicit command", command_type)

        if self._is_at_me(segments):
            return AgentDecision(AgentAction.CHAT, "bot was mentioned")

        if not self.command_handler.is_group_agent_enabled(group_id):
            return AgentDecision(AgentAction.IGNORE, "group agent mode is disabled")

        autonomous_decision = self._decide_autonomous_group(message_content)
        if autonomous_decision:
            return autonomous_decision

        return AgentDecision(AgentAction.IGNORE, "group message did not mention bot")

    def _decide_autonomous_group(self, message_content: str) -> Optional[AgentDecision]:
        text = _CQ_RE.sub("", message_content or "").strip()
        if not text:
            return None

        if _JM_AUTONOMOUS_RE.search(text):
            return AgentDecision(
                AgentAction.TOOL,
                "autonomous jm recommendation cue",
                CommandType.JM,
                ".jm recommend",
            )

        if _HELP_QUESTION_RE.search(text):
            return AgentDecision(AgentAction.CHAT, "autonomous public help question")

        return None

    def decide_private(self, message_content: str) -> AgentDecision:
        command_type = self.command_handler.get_command_type(message_content)
        if command_type:
            return AgentDecision(AgentAction.TOOL, "matched explicit command", command_type)
        return AgentDecision(AgentAction.CHAT, "private message")

    def _is_blocked_user(self, user_id: int) -> bool:
        if self.bot_interfaces["test_if_super_user"](user_id):
            return False
        return self.command_handler.is_user_banned(user_id)

    async def _with_reply_context(self, ws, segments: list, message_content: str) -> str:
        reply_id = self._reply_id(segments)
        if not reply_id:
            return message_content

        try:
            reply_message = await self.bot_interfaces["get_message_by_id"](ws, reply_id)
            if not reply_message or "message" not in reply_message:
                print(f"[Agent] Could not fetch replied message with id {reply_id}")
                return message_content

            reply_content = await self.bot_interfaces["encode_message_to_CQ"](
                reply_message["message"]
            )
            return (
                f"The user is replying to this message: '{reply_content}'. "
                f"Their new message is: {message_content}"
            )
        except Exception as exc:
            print(f"[Agent] Error fetching replied message {reply_id}: {exc}")
            return message_content

    def _is_at_me(self, segments: list) -> bool:
        bot_qq = str(self.bot_interfaces["bot_qq"])
        for part in segments:
            if part.get("type") == "at" and str(part.get("data", {}).get("qq")) == bot_qq:
                return True
        return False

    def _reply_id(self, segments: list) -> Optional[str]:
        for part in segments:
            if part.get("type") == "reply":
                reply_id = part.get("data", {}).get("id")
                if reply_id is not None:
                    return str(reply_id)
        return None
