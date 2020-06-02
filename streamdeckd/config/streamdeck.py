from typing import List, Optional, Tuple, Dict, cast
from StreamDeck.Devices.StreamDeck import StreamDeck

from streamdeckd.application import Streamdeckd
from streamdeckd.devices import DeviceSource
from streamdeckd.signals import create as create_signal

from streamdeckd.config.base import Context
from streamdeckd.config.validators import validated
from streamdeckd.config.state import DeckContext, ButtonContext, State
from streamdeckd.config.action import SequentialActionContext, ActionContext, ActionableContext


class BaseButtonDefinition(DeckContext, ButtonContext):

    @validated(min_args=0, max_args=0, with_block=True)
    def on_pressed(self, args, block):
        ctx = SequentialActionContext()
        ctx.apply_block(block)
        self.state["pressed"] = ctx
        

    @validated(min_args=0, max_args=0, with_block=True)
    def on_released(self, args, block):
        ctx = SequentialActionContext()
        ctx.apply_block(block)
        self.state["released"] = ctx

    def on_state(self, args, block):
        raise ValueError("state: Directive is not acceptable here.")


@ActionContext.register
class ButtonActionContext(ActionContext):

    @validated(min_args=2, max_args=2, with_block=True)
    def on_button(self, args, block):
        from streamdeckd.display import Display

        x = int(args[0])
        y = int(args[1])

        ctx = SequentialActionContext()
        ctx.apply_block(block)

        @self.actions.append
        @ActionableContext.simple
        async def _op(app, target):
            while isinstance(target, State):
                if isinstance(target, Display):
                    break

                target = target.parent
            
            if not isinstance(target, Display):
                return

            target = target.buttons[(x, y)]
            await ctx.apply_actions(app, target)

    @validated(min_args=0, max_args=0, with_block=False)
    def on_press(self, args, block):
        @self.actions.append
        @ActionableContext.simple
        async def _op(app, target):
            await target.when_key_pressed()

    @validated(min_args=0, max_args=0, with_block=False)
    def on_release(self, args, block):
        @self.actions.append
        @ActionableContext.simple
        async def _op(app, target):
            await target.when_key_released(force=True)


class SignalContext:

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.signals = []

    @validated(min_args=1, with_block=True)
    def on_signal(self, args, block):
        name = args[0]
        rest = args[1:]
        signal = create_signal(name, rest, None)

        ctx = SequentialActionContext()
        ctx.apply_block(block)

        self.signals.append((signal, ctx, [None]))


class StateDefinition(SignalContext, BaseButtonDefinition):
    
    def __init__(self, name: str, default: bool):
        super().__init__()
        self.name = name
        self.default = default
        self.entered = None
        self.leaving = None

    @validated(min_args=0, max_args=0, with_block=True)
    def on_entered(self, args, block):
        self.entered = SequentialActionContext()
        self.entered.apply_block(block)

    @validated(min_args=0, max_args=0, with_block=True)
    def on_leaving(self, args, block):
        self.leaving = SequentialActionContext()
        self.leaving.apply_block(block)

    async def when_entered(self, app, target):
        if self.entered is not None:
            await self.entered.apply_actions(app, target)

        for signal, sig_ctx, cb_holder in self.signals:
            cb = (lambda ctx: (lambda: ctx.apply_actions(app, target)))(sig_ctx)
            cb_holder[0] = cb
            signal.register(cb)

    async def when_leaving(self, app, target):
        if self.leaving is not None:
            await self.leaving.apply_actions(app, target)

        for signal, sig_ctx, cb_holder in self.signals:
            signal.unregister(cb_holder[0])
            cb_holder[0] = None


class ButtonDefinition(BaseButtonDefinition):
    def __init__(self, x: int, y: int):
        super().__init__()
        self.x = x
        self.y = y

        self.states: List[StateDefinition] = []

    @validated(min_args=1, max_args=2, with_block=True)
    def on_state(self, args, block):
        default = False
        if len(args) == 2:
            if args[1] != "default":
                raise ValueError("state: Argument 2 must be 'default'")
            default = True

        sctx = StateDefinition(args[0], default)
        sctx.apply_block(block)
        self.states.append(sctx)

    def get_state(self, name: Optional[bool]) -> StateDefinition:
        if name is not None:
            for ctx in self.states:
                if ctx.name == name:
                    return ctx
        for ctx in self.states:
            if ctx.default:
                return ctx

        return StateDefinition('', True)


class MenuContext(DeckContext, ButtonContext):

    def __init__(self, identifier: str, default: bool=False):
        super().__init__()
        self.identifier = identifier
        self.default = default

        self.buttons: Dict[Tuple[int, int], ButtonContext] = {}
        self.opened = None
        self.closed = None

    @validated(min_args=2, max_args=2, with_block=True)
    def on_button(self, args, block):
        x = int(args[0])
        y = int(args[1])

        ctx = ButtonDefinition(x, y)
        ctx.apply_block(block)

        self.buttons[(x, y)] = ctx

    @validated(min_args=0, max_args=0, with_block=True)
    def on_opened(self, args, block):
        ctx = SequentialActionContext()
        ctx.apply_block(block)
        self.opened = ctx

    @validated(min_args=0, max_args=0, with_block=True)
    def on_closed(self, args, block):
        ctx = SequentialActionContext()
        ctx.apply_block(block)
        self.closed = ctx



class StreamdeckContext(SignalContext, DeckContext, ButtonContext):

    def __init__(self, app: Streamdeckd, identifier: str, default:bool=False):
        super().__init__()
        self.app = app
        self.identifier = identifier

        self.default = default
        self.menus: List[MenuContext] = []

        self.connected = None

    def get_menu(self, name: Optional[str]) -> MenuContext:
        if name is not None:
            for ctx in self.menus:
                if ctx.identifier == name:
                    return ctx
        for ctx in self.menus:
            if ctx.default:
                return ctx

        return MenuContext('', True)

    @validated(min_args=1, max_args=2, with_block=True)
    def on_menu(self, args, block):
        default = False
        if len(args) == 2:
            if args[1] != "default":
                raise ValueError("menu: Argument 2 must be 'default'")
            default = True

        ctx = MenuContext(args[0], default=default)
        ctx.apply_block(block)
        self.menus.append(ctx)

    @validated(min_args=0, max_args=0, with_block=True)
    def on_connected(self, args, block):
        ctx = SequentialActionContext()
        ctx.apply_block(block)
        self.connected = ctx

    def matches(self, deck: StreamDeck) -> bool:
        return cast(DeviceSource, self.app.scanner).matches(self.identifier, deck)

    def apply_devices(self, source: DeviceSource):
        source.request(self.identifier)