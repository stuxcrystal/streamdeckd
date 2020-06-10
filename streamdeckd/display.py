from asyncio import get_running_loop
from typing import Dict, Tuple, Optional

from PIL import Image, ImageDraw, ImageFont

from StreamDeck.ImageHelpers import PILHelper
from StreamDeck.Devices.StreamDeck import StreamDeck

from streamdeckd.state import State, StateVariable
from streamdeckd.utils import parse_color, ColorStateVariable, TimeSpanStateVariable, ImageStateVariable, LiveVariable
from streamdeckd.variables import Variables



_FONTCACHE: Dict[Tuple[str, int], ImageFont.ImageFont] = {}


class Button(State):
    image = ImageStateVariable(None)
    text = StateVariable("{p}")
    font = StateVariable("")
    size = StateVariable.with_parser(int, 10)
    bg = ColorStateVariable("#000")
    fg = ColorStateVariable("#FFF")
    state = StateVariable("")

    pressed = StateVariable(None)
    released = StateVariable(None)

    def __init__(self, x: int, y: int, parent: 'Display'):
        super().__init__(parent)

        self.x = x
        self.y = y
        self.p = self.y*self.parent.deck.key_layout()[0] + self.x

        self.reset()
        self._display_state = {
            "text": None, 
            "bg": None,
            "fg": None,
            "image": None,
            "font": None,
            "size": None
        }

        self.d_vars = {
            "x": self.x,
            "y": self.y,
            "p": self.p,
            "state": LiveVariable(lambda: self.state)
        }
        self.s_vars = self.parent.s_vars.make_child()
        self.s_vars.add_map(self.d_vars)

        self._shown_image: Image.Image = PILHelper.create_image(self.parent.deck)

        self._pressed = False

        self._current_state = None

    def _make_state(self, text):
        return {
            "text": text,
            "bg": self.bg,
            "fg": self.fg,
            "image": self.image,
            "font": self.font,
            "size": self.size
        }

    def _get_font(self):
        if not self.font:
            return ImageFont.load_default()

        key = (self.font, self.size)
        if key in _FONTCACHE:
            return _FONTCACHE[key]
        
        font = ImageFont.truetype(self.font, size=self.size)
        _FONTCACHE[key] = font

        return font

    def draw(self):
        img = self._shown_image
        text = self.s_vars.format(self.text)
        text = text.replace("\\n", "\n")

        new_state = self._make_state(text)
        if new_state == self._display_state:
            return None
        self.parent.app.logger.debug(f"Change detected at: {self.x},{self.y} => Rerendering")
        self._display_state = new_state

        draw = ImageDraw.Draw(img)
        draw.rectangle(((0, 0), (img.width, img.height)), fill=self.bg)

        font = self._get_font()
        tw, th = draw.textsize(text, font=font)

        tx = (img.width - tw) // 2

        if not self.image:
            ty = (img.height - th) // 2
        else:
            iw = img.width - th - 15
            ih = img.height - th - 15

            resized = self.image.resize((iw, ih), Image.BICUBIC)
            if img.mode == "RGBA":
                img.paste(resized, ((img.width - iw)//2, 5), resized)
            else:
                img.paste(resized, ((img.width - iw)//2, 5))

            ty = img.height - 5 - th

        draw.text((tx, ty), text, font=font, fill=self.fg)
        return img

    async def when_key_pressed(self):
        self._pressed = True

        if self.pressed is not None:
            get_running_loop().create_task(self.pressed.apply_actions(self.parent.app, self))

    async def when_key_released(self, force=False):
        if not force and not self._pressed:
            self.parent.app.logger.debug("Button press was masked.")
            return
        self._pressed = False

        if self.released is not None:
            get_running_loop().create_task(self.released.apply_actions(self.parent.app, self))

    def reset(self, *, with_state=False):
        self.text = ""
        self.font = ""
        self.size = "10"
        self.image = ""
        self.bg = "#000"
        self.fg = "#FFF"
        if with_state:
            self.state = ""
            self._current_state = None

        self.pressed = None
        self.released = None

        self._pressed = False

    def __repr__(self):
        return f"<Button ({self.x},{self.y})>"

    @state.changed
    def state(self, old, new):
        if self._current_state is not None:
            get_running_loop().create_task(self._current_state.when_leaving(self.parent.app, self))

        self._current_state = self.parent.get_state_of(self, new)
        self.parent.apply_button_contexts(self)
        self._pressed = False

        if self._current_state is not None:
            get_running_loop().create_task(self._current_state.when_entered(self.parent.app, self))


class Display(State):
    fps = StateVariable.with_parser(float, 0)
    brightness = StateVariable.with_parser(float, 1.0)

    menu = StateVariable()


    def __init__(self, app: 'streamdeckd.application.Streamdeckd', ctx: 'streamdeckd.config.streamdeck.StreamDeckContext', deck: StreamDeck):
        super().__init__(None)
        self.app = app
        self.deck = deck
        self.ctx = ctx
        self._should_render = False

        self.d_vars = {}
        self.s_vars = self.app.variables.make_child()
        self.s_vars.add_map(self.d_vars)

        self.current_menu = None

        self.buttons: Dict[Tuple[int, int], Button] = {}

    async def when_key_state_changed(self, _, kid: int, pressed: bool):
        y, x = divmod(kid, self.deck.key_layout()[1])
        btn = self.buttons[(x, y)]
        if pressed:
            self.app.logger.info(f"Pressed button {x},{y}")
            await btn.when_key_pressed()
        else:
            self.app.logger.info(f"Released button {x},{y}")
            await btn.when_key_released()

    def get_state_of(self, btn: Button, name: Optional[str]=None):
        bctx = self.current_menu.buttons.get((btn.x, btn.y), None)

        if name is None:
            name = btn.state

        sctx = None
        if bctx is not None:
            sctx = bctx.get_state(name)

        return sctx

    def apply_button_contexts(self, btn: Button):
        loc = (btn.x, btn.y)
        bctx = self.current_menu.buttons.get(loc, None)
        sctx = None
        if bctx is not None:
            sctx = bctx.get_state(btn.state)

        btn.reset()
        btn.apply(self.ctx.state, exclude_classes=[Display])
        btn.apply(self.current_menu.state, exclude_classes=[Display])
        if bctx is not None:
            btn.apply(bctx.state, exclude_classes=[Display])
        if sctx is not None:
            btn.apply(sctx.state, exclude_classes=[Display])

    async def _update(self):
        self.render_now()

    def render(self) -> None:
        if self._should_render:
            return

        self._should_render = True
        get_running_loop().call_later(0.05, self.render_now)

    def render_now(self) -> None:
        self._should_render = False
        self.app.logger.debug(f"Rendering {self.deck.id()}")
        width = self.deck.key_layout()[1]

        self.deck.set_brightness(self.brightness)

        for (x, y), btn in self.buttons.items():
            p = y*width + x

            raw = self._draw(x, y, btn)
            if raw is None:
                continue
            self.deck.set_key_image(p, raw)

    def _draw(self, x: int, y: int, btn: Button):
        img = btn.draw()
        if img is None:
            return None
        return PILHelper.to_native_format(self.deck, img)
        
    def open(self) -> None:
        self.deck.open()
        self.deck.set_key_callback_async(self.when_key_state_changed)

        self.apply(self.ctx.state)
        self.d_vars["serial_number"] = self.deck.get_serial_number()
        self.d_vars["firmware_version"] = self.deck.get_firmware_version()

        layout = self.deck.key_layout()
        for y in range(layout[0]):
            for x in range(layout[1]):
                self.buttons[(x, y)] = Button(x, y, self)

        self.menu = None
        
        fakebtn = Button(-1, -1, self)
        if self.ctx.connected is not None:
            get_running_loop().create_task(self.ctx.connected.apply_actions(self.app, Button(-1, -1, self)))

        sigcbs = []
        for signal, sig_ctx, cb_holder in self.ctx.signals:
            cb = (lambda ctx: (lambda: ctx.apply_actions(self.app, fakebtn)))(sig_ctx)
            cb_holder[0] = cb
            signal.register(cb)

        if self.fps:
            self.app.scheduler.add_recurring(1.0 / self.fps, self._update)

    def close(self) -> None:
        try:
            for signal, sig_ctx, cb_holder in self.ctx.signals:
                cb = cb_holder[0]
                signal.unregister(cb)
                cb_holder[0] = None

            self.deck.reset()
        finally:
            self.deck.close()
    
    @menu.changed
    def menu(self, old, new):
        if self.current_menu is not None and self.current_menu.closed is not None:
            get_running_loop().create_task(self.current_menu.closed.apply_actions(self.app, Button(-1, -1, self)))

        self.current_menu = self.ctx.get_menu(new)

        for loc, btn in self.buttons.items():
            btn.reset(with_state=True)

            bctx = self.current_menu.buttons.get(loc, None)
            if bctx is not None:
                self.apply_button_contexts(btn)
                btn.apply({"state": bctx.get_state(None).name})

        if self.current_menu is not None and self.current_menu.opened is not None:
            get_running_loop().create_task(self.current_menu.opened.apply_actions(self.app, Button(-1, -1, self)))
        
        self.render_now()

