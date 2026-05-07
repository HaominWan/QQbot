from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional


class ToolScope(Enum):
    GROUP = "group"
    PRIVATE = "private"
    BOTH = "both"


ToolHandler = Callable[..., Awaitable[None]]


@dataclass
class Tool:
    name: str
    command_type: Any
    prefixes: List[str]
    group_handler: Optional[ToolHandler] = None
    private_handler: Optional[ToolHandler] = None
    description: str = ""

    def supports(self, scope: ToolScope) -> bool:
        if scope == ToolScope.GROUP:
            return self.group_handler is not None
        if scope == ToolScope.PRIVATE:
            return self.private_handler is not None
        return self.group_handler is not None or self.private_handler is not None


@dataclass
class ToolMatch:
    tool: Tool
    prefix: str
    content: str


class ToolRouter:
    """Prefix based tool registry used by command and future agent routing."""

    def __init__(self):
        self._tools: Dict[Any, Tool] = {}
        self._prefixes: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if tool.command_type in self._tools:
            raise ValueError(f"Tool command already registered: {tool.command_type}")

        self._tools[tool.command_type] = tool
        for prefix in tool.prefixes:
            if prefix in self._prefixes:
                raise ValueError(f"Tool prefix already registered: {prefix}")
            self._prefixes[prefix] = tool

    def register_many(self, tools: Iterable[Tool]) -> None:
        for tool in tools:
            self.register(tool)

    def match(self, message_content: str) -> Optional[ToolMatch]:
        # Prefer the longest prefix so aliases such as .typ and .typst behave
        # predictably even when one prefix contains another.
        for prefix in sorted(self._prefixes.keys(), key=len, reverse=True):
            if message_content.startswith(prefix):
                return ToolMatch(
                    tool=self._prefixes[prefix],
                    prefix=prefix,
                    content=message_content[len(prefix):].strip(),
                )
        return None

    def match_command_type(self, message_content: str) -> Optional[Any]:
        match = self.match(message_content)
        if match is None:
            return None
        return match.tool.command_type

    def extract_content(self, message_content: str, command_type: Any) -> str:
        match = self.match(message_content)
        if match is None or match.tool.command_type != command_type:
            return ""
        return match.content

    async def handle(
        self,
        scope: ToolScope,
        command_type: Any,
        ws,
        message_content: str,
        **kwargs,
    ) -> bool:
        tool = self._tools.get(command_type)
        if tool is None:
            return False

        if scope == ToolScope.GROUP:
            handler = tool.group_handler
        elif scope == ToolScope.PRIVATE:
            handler = tool.private_handler
        else:
            handler = tool.private_handler or tool.group_handler

        if handler is None:
            return False

        await handler(ws, message_content, **kwargs)
        return True
