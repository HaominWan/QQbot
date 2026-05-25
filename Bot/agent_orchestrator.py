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
_JM_CODE_RE = re.compile(
    r"(?:JM\s*|禁漫\s*|jmcomic\s*|本子\s*)(?P<code>\d{5,8})"
    r"|(?P<code_before>\d{5,8}).{0,8}(?:本子|jm|JM|禁漫)"
)
_ORDINAL = r"\d{1,2}|[一二三四五六七八九十两]+"
_JM_RECOMMEND_INDEX_RE = re.compile(
    rf"(?:推荐栏|推荐列表|推荐).{{0,12}}第\s*(?P<index>{_ORDINAL})\s*(?:个|本|项)?"
    rf"|第\s*(?P<index_before>{_ORDINAL})\s*(?:个|本|项).{{0,12}}(?:推荐栏|推荐列表|推荐|本子|jm|JM)"
)
# 自主模式：识别JM推荐相关的高置信度意图
# 自主回复模式启用时，匹配此模式的消息会自动触发推荐查询命令，无需@或使用.jm命令
# 匹配例：「今天推荐本子」「来点jm」「jm推荐」「想看本子」等
_JM_AUTONOMOUS_RE = re.compile(
    r"(?:今天|今日|最近|还没|没看|想看|推荐|来点|有没有).{0,16}(?:jm|JM|本子)"
    r"|(?:jm|JM|本子).{0,16}(?:推荐|来点|看看|没看|想看)"
)
_PIXIV_PID_RE = re.compile(r"(?:pixiv|p站|P站|pid|PID)[^\d]{0,8}(?P<pid>\d{5,12})")
_PIXIV_RECOMMEND_RE = re.compile(r"(?:pixiv|p站|P站).{0,12}(?:推荐|来点|日榜|排行榜|每日)")
_PIXIV_DRAWER_RE = re.compile(r"(?:pixiv|p站|P站).{0,8}(?:画师|作者|artist|drawer)\s*[:：]?\s*(?P<name>\S.{0,40})")
_PIXIV_SEARCH_RE = re.compile(r"(?:搜|搜索|查|找|来点|来张).{0,8}(?:pixiv|p站|P站)\s*(?P<query>\S.{0,50})")
_YGO_RE = re.compile(
    r"(?:游戏王|ygo|YGO).{0,8}(?:查卡|查一下|查询|卡片|效果)\s*(?P<query>\S.{0,50})"
    r"|(?:查|查询)\s*(?:游戏王|ygo|YGO)?\s*(?:卡|卡片)\s*(?P<query_alt>\S.{0,50})"
)
_DRAW_RE = re.compile(r"(?:画一张|画个|帮我画|生成图片|生成一张图|AI绘图|ai绘图)\s*[:：]?\s*(?P<prompt>\S.{0,160})")
_P5_RE = re.compile(r"(?:生成|做|来张|制作)?\s*(?:P5|p5)\s*(?:预告信|卡片|风格图)?\s*[:：]?\s*(?P<content>\S.{0,120})")
_MARKDOWN_RE = re.compile(r"(?:渲染|生成|转成图片).{0,8}(?:markdown|Markdown|md|MD)\s*[:：]\s*(?P<content>[\s\S]{2,})")
_TYPST_RE = re.compile(r"(?:渲染|生成|转成图片).{0,8}(?:typst|Typst|typ)\s*[:：]\s*(?P<content>[\s\S]{2,})")
_CHINESE_NUMERAL = {
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}
_ROUTE_TRAILING_NOISE_RE = re.compile(r"(?:吧|吗|呢|一下|看看|谢谢|谢了|可以吗|能不能|行吗|好吗|了)+$")
# 自主模式：识别公开求助问题的高置信度意图
# 自主回复模式启用时，匹配此模式的消息会被视为求助问题，触发ChatGPT直接回复
# 匹配例：「有人知道怎么...」「谁知道是什么...」「求问为什么...」等
_HELP_QUESTION_RE = re.compile(
    r"(?:有人知道|有没有人知道|谁知道|求问|请问|想问一下).{0,80}"
    r"(?:是什么|什么是|怎么|如何|为什么|为啥|能不能|可以吗|吗|\?)"
)


MultimodalProcessor = Callable[[list, str], Awaitable[str]]


def _parse_positive_index(raw_index: str | None) -> Optional[int]:
    if raw_index is None:
        return None

    raw_index = raw_index.strip()
    if raw_index.isdigit():
        value = int(raw_index)
        return value if value > 0 else None

    if raw_index in _CHINESE_NUMERAL:
        return _CHINESE_NUMERAL[raw_index]

    if "十" in raw_index:
        before, _, after = raw_index.partition("十")
        tens = _CHINESE_NUMERAL.get(before, 1) if before else 1
        ones = _CHINESE_NUMERAL.get(after, 0) if after else 0
        value = tens * 10 + ones
        return value if value > 0 else None

    return None


def _clean_route_content(text: str | None) -> str:
    text = (text or "").strip(" ：:，,。！？!?\"'“”‘’[]【】（）()")
    text = _ROUTE_TRAILING_NOISE_RE.sub("", text).strip(" ：:，,。！？!?\"'“”‘’[]【】（）()")
    return text


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

        chat_content = decision.message_content or message_content
        chat_content = await self._with_reply_context(ws, segments, chat_content)
        message_content = await self.multimodal_processor(segments, chat_content)

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
        # 第一优先级：检查是否是明确的命令（如 .jm, .draw 等）
        command_type = self.command_handler.get_command_type(message_content)
        if command_type:
            return AgentDecision(AgentAction.TOOL, "matched explicit command", command_type)

        # 第二优先级：检查是否 @了 Bot
        if self._is_at_me(segments):
            return AgentDecision(AgentAction.CHAT, "bot was mentioned")

        # 第三优先级：检查该群是否启用了自主回复模式
        # 如果未启用，则忽略此消息（除非是命令或被@）
        if not self.command_handler.is_group_agent_enabled(group_id):
            return AgentDecision(AgentAction.IGNORE, "group agent mode is disabled")

        # 第四优先级：尝试自动识别高置信度意图（JM推荐、求助问题、其他工具需求等）
        # 这是自主回复模式的核心逻辑，允许Bot在无@的情况下对特定意图自动回复
        autonomous_decision = self._decide_autonomous_group(message_content)
        if autonomous_decision:
            return autonomous_decision

        # 默认：忽略该消息
        return AgentDecision(AgentAction.IGNORE, "group message did not mention bot")

    def _decide_autonomous_group(self, group_id: int, message_content: str) -> Optional[AgentDecision]:
        # 移除CQ码（如图片、@、链接等），只保留纯文本用于意图识别
        text = _CQ_RE.sub("", message_content or "").strip()
        if not text:
            return None

        # 自主模式的决策树，按优先级从高到低检查意图类型
        # 优先级1：JM书籍编号请求（如 "JM123456" 或 "禁漫123456"）
        jm_code = self._extract_jm_code(text)
        if jm_code:
            return AgentDecision(
                AgentAction.TOOL,
                "autonomous jm code request",
                CommandType.JM,
                f".jm {jm_code}",
            )

        # 优先级2：JM推荐栏索引请求（如 "推荐栏第3个" 或 "第3个本子"）
        # 这需要检查历史推荐记录，可能需要ChatGPT解释或给出建议
        jm_index = self._extract_jm_recommendation_index(text)
        if jm_index is not None:
            album_id, total = self.command_handler.recent_jm_recommendation_at(group_id, jm_index)
            if album_id:
                return AgentDecision(
                    AgentAction.TOOL,
                    "autonomous jm recommendation index",
                    CommandType.JM,
                    f".jm {album_id}",
                )

            if total <= 0:
                # 无推荐历史，用ChatGPT解释并引导用户
                return AgentDecision(
                    AgentAction.CHAT,
                    "autonomous jm recommendation index without history",
                    message_content=(
                        f"用户想看推荐栏第 {jm_index} 个，但当前群还没有可用的推荐栏记录。"
                        "请简短告诉用户先获取推荐栏，或直接提供 JM 编号。"
                    ),
                )

            # 推荐索引超出范围，用ChatGPT解释
            return AgentDecision(
                AgentAction.CHAT,
                "autonomous jm recommendation index out of range",
                message_content=(
                    f"用户想看推荐栏第 {jm_index} 个，但当前只记录了 {total} 个推荐项。"
                    f"请简短说明超出范围，并建议换一个 1-{total} 的序号或重新获取更多推荐。"
                ),
            )

        # 优先级3：JM推荐意向识别（如 "今天推荐本子" "来点jm" "想看本子" 等）
        # 触发自动推荐查询，使用.jm recommend命令
        if _JM_AUTONOMOUS_RE.search(text):
            return AgentDecision(
                AgentAction.TOOL,
                "autonomous jm recommendation cue",
                CommandType.JM,
                ".jm recommend",
            )

        # 优先级4：其他工具路由检查（pixiv, ygo, draw, p5, markdown等）
        # 这些工具也支持自主识别，例如 "P站推荐" "画一张猫" 等
        module_decision = self._decide_module_route(text)
        if module_decision:
            return module_decision

        # 优先级5：公开求助问题识别（如 "谁知道怎么..." "有人知道是什么..." 等）
        # 这些问题没有对应的工具，由ChatGPT直接回复
        if _HELP_QUESTION_RE.search(text):
            return AgentDecision(AgentAction.CHAT, "autonomous public help question")

        # 无匹配的意图，继续忽略此消息
        return None

    @staticmethod
    def _extract_jm_code(text: str) -> Optional[str]:
        match = _JM_CODE_RE.search(text)
        if not match:
            return None
        return match.group("code") or match.group("code_before")

    @staticmethod
    def _extract_jm_recommendation_index(text: str) -> Optional[int]:
        match = _JM_RECOMMEND_INDEX_RE.search(text)
        if not match:
            return None
        raw_index = match.group("index") or match.group("index_before")
        return _parse_positive_index(raw_index)

    def _decide_module_route(self, text: str) -> Optional[AgentDecision]:
        if pixiv_decision := self._route_pixiv(text):
            return pixiv_decision
        if ygo_decision := self._route_ygo(text):
            return ygo_decision
        if draw_decision := self._route_draw(text):
            return draw_decision
        if p5_decision := self._route_p5(text):
            return p5_decision
        if markdown_decision := self._route_markdown(text):
            return markdown_decision
        if typst_decision := self._route_typst(text):
            return typst_decision
        return None

    @staticmethod
    def _route_pixiv(text: str) -> Optional[AgentDecision]:
        if match := _PIXIV_PID_RE.search(text):
            return AgentDecision(
                AgentAction.TOOL,
                "autonomous pixiv pid request",
                CommandType.PIXIV,
                f".pixiv {match.group('pid')}",
            )

        if _PIXIV_RECOMMEND_RE.search(text):
            return AgentDecision(
                AgentAction.TOOL,
                "autonomous pixiv recommendation cue",
                CommandType.PIXIV,
                ".pixiv recommend",
            )

        if match := _PIXIV_DRAWER_RE.search(text):
            name = _clean_route_content(match.group("name"))
            if name:
                return AgentDecision(
                    AgentAction.TOOL,
                    "autonomous pixiv drawer search",
                    CommandType.PIXIV,
                    f".pixiv drawer:{name}",
                )

        if match := _PIXIV_SEARCH_RE.search(text):
            query = _clean_route_content(match.group("query"))
            if query:
                return AgentDecision(
                    AgentAction.TOOL,
                    "autonomous pixiv search",
                    CommandType.PIXIV,
                    f".pixiv {query}",
                )

        return None

    @staticmethod
    def _route_ygo(text: str) -> Optional[AgentDecision]:
        match = _YGO_RE.search(text)
        if not match:
            return None
        query = _clean_route_content(match.group("query") or match.group("query_alt"))
        if not query:
            return None
        return AgentDecision(
            AgentAction.TOOL,
            "autonomous ygo card lookup",
            CommandType.YGO,
            f".YGO {query}",
        )

    @staticmethod
    def _route_draw(text: str) -> Optional[AgentDecision]:
        if "画师" in text:
            return None
        match = _DRAW_RE.search(text)
        if not match:
            return None
        prompt = _clean_route_content(match.group("prompt"))
        if not prompt:
            return None
        return AgentDecision(
            AgentAction.TOOL,
            "autonomous drawing request",
            CommandType.DRAW,
            f".draw {prompt}",
        )

    @staticmethod
    def _route_p5(text: str) -> Optional[AgentDecision]:
        match = _P5_RE.search(text)
        if not match:
            return None
        content = _clean_route_content(match.group("content"))
        if not content or content.lower() in {"p5", "预告信", "卡片"}:
            return None
        return AgentDecision(
            AgentAction.TOOL,
            "autonomous p5 card request",
            CommandType.P5,
            f".P5 {content}",
        )

    @staticmethod
    def _route_markdown(text: str) -> Optional[AgentDecision]:
        match = _MARKDOWN_RE.search(text)
        if not match:
            return None
        content = match.group("content").strip()
        if not content:
            return None
        return AgentDecision(
            AgentAction.TOOL,
            "autonomous markdown render request",
            CommandType.MARKDOWN,
            f".md {content}",
        )

    @staticmethod
    def _route_typst(text: str) -> Optional[AgentDecision]:
        match = _TYPST_RE.search(text)
        if not match:
            return None
        content = match.group("content").strip()
        if not content:
            return None
        return AgentDecision(
            AgentAction.TOOL,
            "autonomous typst render request",
            CommandType.TYPST,
            f".typ {content}",
        )

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
