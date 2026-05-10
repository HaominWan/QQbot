"""Role exports used by persona_engine.

Private Murasame role cards are optional. Public checkouts may not include them,
so this module must always export the role factory functions used elsewhere.
"""

from importlib import import_module
from typing import Callable

RoleFactory = Callable[[int, int], str]


def _fallback_role(user_qq: int, bot_qq: int, mode: str) -> str:
    relation = "master" if mode == "master" else "guardian"
    return (
        f"You are QQ bot {bot_qq}. "
        f"Talk naturally with user {user_qq} in {relation} mode. "
        "Reply in Chinese unless the user asks otherwise. "
        "Be helpful, concise, and avoid pretending to have unavailable private persona files."
    )


def _fallback_factory(mode: str) -> RoleFactory:
    def factory(user_qq: int, bot_qq: int) -> str:
        return _fallback_role(user_qq, bot_qq, mode)

    return factory


def _load_named_factory(module_names: tuple[str, ...], factory_name: str) -> RoleFactory | None:
    for module_name in module_names:
        try:
            module = import_module(f"{__name__}.{module_name}")
            factory = getattr(module, factory_name)
        except Exception as exc:
            print(f"[Roles] Optional role module {module_name}.{factory_name} unavailable: {exc}")
            continue
        if callable(factory):
            return factory
    return None


def _load_card_factory(mode: str) -> RoleFactory | None:
    try:
        module = import_module(f"{__name__}.murasame_card")
        build_murasame_role = getattr(module, "build_murasame_role")
    except Exception as exc:
        print(f"[Roles] Optional murasame_card unavailable: {exc}")
        return None

    if not callable(build_murasame_role):
        return None

    def factory(user_qq: int, bot_qq: int) -> str:
        master_id = user_qq if mode == "master" else 0
        role_mode = "master" if mode == "master" else "guardian"
        return build_murasame_role(user_qq, bot_qq, master_id=master_id, mode=role_mode)

    return factory


get_Murasame_goshujin_role = (
    _load_named_factory(("Murasame_goshujin",), "get_Murasame_goshujin_role")
    or _load_card_factory("master")
    or _fallback_factory("master")
)

get_Murasame_customs_role = (
    _load_named_factory(
        ("Murasame_customs", "Murasame_customers"),
        "get_Murasame_customs_role",
    )
    or _load_card_factory("guardian")
    or _fallback_factory("guardian")
)


__all__ = [
    "get_Murasame_goshujin_role",
    "get_Murasame_customs_role",
]
