from typing import Any, Dict

from .event import MessageEvent


class BotContext:
    """Runtime context passed to router handlers.

    This is intentionally small: it carries the normalized event, the websocket,
    and the legacy interface table so existing handlers can be migrated gradually.
    """

    def __init__(self, ws: Any, interfaces: Dict[str, Any], event: MessageEvent):
        self.ws = ws
        self.interfaces = interfaces
        self.event = event

    async def send(self, message: Any, auto_escape: bool = False):
        if self.event.is_group:
            return await self.interfaces["send_group_message"](
                self.ws, self.event.group_id, message, auto_escape=auto_escape
            )

        if self.event.is_private:
            return await self.interfaces["send_private_message"](
                self.ws, self.event.user_id, message, auto_escape=auto_escape
            )

        return None
