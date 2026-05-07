from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MessageEvent:
    """A normalized OneBot message event.

    The current project receives raw OneBot dictionaries directly. This class
    gives the rest of the bot a stable shape, similar to framework event models
    in NoneBot2, while preserving access to the original payload.
    """

    raw: Dict[str, Any]
    post_type: str
    message_type: str
    user_id: int
    self_id: Optional[int] = None
    group_id: Optional[int] = None
    message_id: Optional[int] = None
    raw_message: str = ""
    message_segments: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_onebot(cls, payload: Dict[str, Any]) -> Optional["MessageEvent"]:
        if payload.get("post_type") != "message":
            return None

        return cls(
            raw=payload,
            post_type=payload.get("post_type", ""),
            message_type=payload.get("message_type", ""),
            user_id=int(payload.get("user_id", 0)),
            self_id=payload.get("self_id"),
            group_id=payload.get("group_id"),
            message_id=payload.get("message_id"),
            raw_message=payload.get("raw_message", ""),
            message_segments=payload.get("message", []),
        )

    @property
    def is_group(self) -> bool:
        return self.message_type == "group"

    @property
    def is_private(self) -> bool:
        return self.message_type == "private"

    def iter_segments(self, segment_type: str):
        for segment in self.message_segments:
            if segment.get("type") == segment_type:
                yield segment

    def is_at(self, qq: Any) -> bool:
        qq = str(qq)
        for segment in self.iter_segments("at"):
            if str(segment.get("data", {}).get("qq")) == qq:
                return True
        return False

    def reply_id(self) -> Optional[str]:
        for segment in self.iter_segments("reply"):
            reply_id = segment.get("data", {}).get("id")
            if reply_id is not None:
                return str(reply_id)
        return None
