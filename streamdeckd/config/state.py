import asyncio
from typing import Optional

from streamdeckd.application import Streamdeckd
from streamdeckd.state import State

from streamdeckd.config.base import Context
from streamdeckd.config.validators import validated
from streamdeckd.config.action import ActionableContext, ActionContext


class StateContext(ActionableContext):

    def __init__(self, *args, **kwargs):
        self.state = {}
        super().__init__(*args, **kwargs)

    async def apply_actions(self, app: Streamdeckd, target: State):
        target.apply(self.state)


@ActionContext.register
class ButtonContext(StateContext):

    @validated(min_args=1, max_args=1, with_block=False)
    def on_text(self, args, block):
        self.state["text"] = args[0]

    @validated(min_args=1, max_args=1, with_block=False)
    def on_image(self, args, block):
        self.state["image"] = args[0]

    @validated(min_args=1, max_args=1, with_block=False)
    def on_font(self, args, block):
        self.state["font"] = args[0]

    @validated(min_args=1, max_args=1, with_block=False)
    def on_size(self, args, block):
        self.state["size"] = args[0]

    @validated(min_args=1, max_args=1, with_block=False)
    def on_bg(self, args, block):
        self.state["bg"] = args[0]

    @validated(min_args=1, max_args=1, with_block=False)
    def on_fg(self, args, block):
        self.state["fg"] = args[0]

    @validated(min_args=1, max_args=1, with_block=False)
    def on_state(self, args, block):
        self.state["state"] = args[0]

    async def apply_actions(self, app: Streamdeckd, target: State):
        await super().apply_actions(app, target)

        from streamdeckd.display import Display
        st: Optional[State] = target
        while isinstance(st, State):
            if isinstance(st, Display):
                st.render()
                break
            st = st.parent


@ActionContext.register
class DeckContext(StateContext):

    @validated(min_args=1, max_args=1, with_block=False)
    def on_fps(self, args, block):
        self.state["fps"] = args[0]

    @validated(min_args=1, max_args=1, with_block=False)
    def on_brightness(self, args, block):
        self.state["brightness"] = args[0]

    @validated(min_args=1, max_args=1, with_block=False)
    def on_menu(self, args, block):
        self.state["menu"] = args[0]
