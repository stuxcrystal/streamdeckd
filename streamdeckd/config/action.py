import asyncio
from typing import Type, ClassVar, List, Callable, Awaitable

from streamdeckd.state import State
from streamdeckd.application import Streamdeckd

from streamdeckd.config.base import Context
from streamdeckd.config.validators import validated


class ActionableContext(Context):

    async def apply_actions(self, app: Streamdeckd, target: State):
        raise NotImplemented

    @classmethod
    def simple(cls, func: Callable[[Streamdeckd, State], Awaitable[None]]) -> 'ActionableContext':
        return type(f"{func.__name__}ActionableContext", (cls,), {"apply_actions": lambda _, app, state: func(app, state)})()


class ActionContext(ActionableContext):
    SUPPORTED: ClassVar[List[Type[ActionableContext]]] = []

    @classmethod
    def register(cls, atc: Type[ActionableContext]):
        cls.SUPPORTED.append(atc)
        return atc

    def __init__(self):
        self.actions: List[ActionableContext] = []

    def unknown_directive(self, name, args, block):
        for ctx_cls in self.SUPPORTED:
            if hasattr(ctx_cls, f"on_{name}"):
                break
        else:
            return super().unknown_directive(name, args, block)
        
        ctx = ctx_cls()
        ctx.apply_directive(name, args, block)
        self.actions.append(ctx)

    async def apply_actions(self, app: Streamdeckd, target: State):
        if len(self.actions) > 1:
            raise ValueError("Raw Action Context has more than one action.")
        elif not self.actions:
            return

        await self.actions[0].apply_actions(app, target)


class SilentActionContext(ActionContext):

    async def apply_actions(self, app: Streamdeckd, target: State):
        try:
            await super().apply_actions(app, target)
        except Exception as e:
            pass


class ShieldedActionContext(ActionContext):

    async def apply_actions(self, app: Streamdeckd, target: State):
        try:
            await super().apply_actions(app, target)
        except Exception as e:
            app.logger.warn("Shielded operation threw an error", e)


class DetachActionContext(ActionContext):

    async def _run(self, app: Streamdeckd, target: State):
        try:
            await super().apply_actions(app, target)
        except Exception as e:
            app.logger.warn("Detached operation threw an error", e)

    async def apply_actions(self, app: Streamdeckd, target: State):
        asyncio.get_running_loop().create_task(self._run(app, target))


class SequentialActionContext(ActionContext):

    async def apply_actions(self, app: Streamdeckd, target: State):
        for action in self.actions:
            await action.apply_actions(app, target)


class ParallelActionContext(ActionContext):

    async def apply_actions(self, app: Streamdeckd, target: State):
        await asyncio.gather(*(action.apply_actions(app, target) for action in self.actions))


@ActionContext.register
class ExecutionActionContext(ActionContext):

    @validated(min_args=0, max_args=0, with_block=True)
    def on_sequential(self, args, block):
        ctx = SequentialActionContext()
        ctx.apply_block(block)
        self.actions.append(ctx)

    @validated(min_args=0, max_args=0, with_block=True)
    def on_parallel(self, args, block):
        ctx = ParallelActionContext()
        ctx.apply_block(block)
        self.actions.append(ctx)

    def on_detach(self, args, block):
        ctx = DetachActionContext()
        ctx.apply_directive(args[0], args[1:], block)
        self.actions.append(ctx)

    def on_shield(self, args, block):
        ctx = ShieldedActionContext()
        ctx.apply_directive(args[0], args[1:], block)
        self.actions.append(ctx)

    def on_silent(self, args, block):
        ctx = SilentActionContext()
        ctx.apply_directive(args[0], args[1:], block)
        self.actions.append(ctx)