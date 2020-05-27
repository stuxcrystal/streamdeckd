from typing import List, Optional, Tuple, Dict, cast
from StreamDeck.Devices.StreamDeck import StreamDeck

from streamdeckd.application import Streamdeckd
from streamdeckd.devices import DeviceSource

from streamdeckd.config.base import Context
from streamdeckd.config.validators import validated
from streamdeckd.config.state import DeckContext, ButtonContext
from streamdeckd.config.action import SequentialActionContext


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


class StateDefinition(BaseButtonDefinition):
    
    def __init__(self, name: str, default: bool):
        super().__init__()
        self.name = name
        self.default = default


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

        return StateDefinition('<none>', True)


class MenuContext(DeckContext, ButtonContext):

    def __init__(self, identifier: str, default: bool=False):
        super().__init__()
        self.identifier = identifier
        self.default = default

        self.buttons: Dict[Tuple[int, int], ButtonContext] = {}

    @validated(min_args=2, max_args=2, with_block=True)
    def on_button(self, args, block):
        x = int(args[0])
        y = int(args[1])

        ctx = ButtonDefinition(x, y)
        ctx.apply_block(block)

        self.buttons[(x, y)] = ctx


class StreamdeckContext(DeckContext, ButtonContext):

    def __init__(self, app: Streamdeckd, identifier: str, default:bool=False):
        super().__init__()
        self.app = app
        self.identifier = identifier

        self.default = default
        self.menus: List[MenuContext] = []

    def get_menu(self, name: Optional[str]) -> MenuContext:
        if name is not None:
            for ctx in self.menus:
                if ctx.identifier == name:
                    return ctx
        for ctx in self.menus:
            if ctx.default:
                return ctx

        return MenuContext('<none>', True)

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

    def matches(self, deck: StreamDeck) -> bool:
        return cast(DeviceSource, self.app.scanner).matches(self.identifier, deck)

    def apply_devices(self, source: DeviceSource):
        source.request(self.identifier)