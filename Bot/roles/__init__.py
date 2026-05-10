"""Role exports used by persona_engine.

Private Murasame role cards are optional. When they are not present in a public
checkout, use a small built-in fallback so message handling never crashes.
"""


def _fallback_role(user_qq: int, bot_qq: int, mode: str) -> str:
    relation = "master" if mode == "master" else "guardian"
    return (
        f"You are QQ bot {bot_qq}. "
        f"Talk naturally with user {user_qq} in {relation} mode. "
        "Reply in Chinese unless the user asks otherwise. "
        "Be helpful, concise, and avoid pretending to have unavailable private persona files."
    )

try:
    from .Murasame_goshujin import get_Murasame_goshujin_role
except ImportError:
    try:
        from .murasame_card import build_murasame_role

        def get_Murasame_goshujin_role(user_qq: int, bot_qq: int) -> str:
            return build_murasame_role(user_qq, bot_qq, master_id=user_qq, mode="master")
    except ImportError:
        def get_Murasame_goshujin_role(user_qq: int, bot_qq: int) -> str:
            return _fallback_role(user_qq, bot_qq, "master")

try:
    from .Murasame_customers import get_Murasame_customs_role
except ImportError:
    try:
        from .murasame_card import build_murasame_role

        def get_Murasame_customs_role(user_qq: int, bot_qq: int) -> str:
            return build_murasame_role(user_qq, bot_qq, master_id=0, mode="guardian")
    except ImportError:
        def get_Murasame_customs_role(user_qq: int, bot_qq: int) -> str:
            return _fallback_role(user_qq, bot_qq, "guardian")


__all__ = [
    "get_Murasame_goshujin_role",
    "get_Murasame_customs_role",
]
