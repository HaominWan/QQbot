import inspect
from dataclasses import dataclass
from typing import Awaitable, Callable, List, Optional

from .context import BotContext


Rule = Callable[[BotContext], bool]
Handler = Callable[[BotContext], Awaitable[None]]


@dataclass
class Matcher:
    name: str
    rule: Rule
    handler: Handler
    priority: int = 100
    block: bool = True


class EventRouter:
    """A tiny matcher router inspired by NoneBot2's rule/matcher model."""

    def __init__(self):
        self._matchers: List[Matcher] = []

    def message(
        self,
        rule: Rule,
        name: Optional[str] = None,
        priority: int = 100,
        block: bool = True,
    ):
        def decorator(handler: Handler):
            matcher = Matcher(
                name=name or handler.__name__,
                rule=rule,
                handler=handler,
                priority=priority,
                block=block,
            )
            self.register(matcher)
            return handler

        return decorator

    def register(self, matcher: Matcher) -> None:
        self._matchers.append(matcher)
        self._matchers.sort(key=lambda item: item.priority)

    async def dispatch(self, ctx: BotContext) -> bool:
        handled = False
        for matcher in self._matchers:
            if not await self._call_rule(matcher.rule, ctx):
                continue

            handled = True
            await matcher.handler(ctx)
            if matcher.block:
                break

        return handled

    async def _call_rule(self, rule: Rule, ctx: BotContext) -> bool:
        result = rule(ctx)
        if inspect.isawaitable(result):
            result = await result
        return bool(result)
