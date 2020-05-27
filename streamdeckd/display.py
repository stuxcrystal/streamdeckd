from asyncio import get_running_loop
from typing import Dict, Tuple, Optional

from PIL import Image, ImageDraw, ImageFont

from StreamDeck.ImageHelpers import PILHelper
from StreamDeck.Devices.StreamDeck import StreamDeck

from streamdeckd.state import State, StateVariable
from streamdeckd.utils import parse_color, ColorStateVariable, TimeSpanStateVariable, ImageStateVariable
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
        self.reset()

        self._shown_image: Image.Image = PILHelper.create_image(self.parent.deck)

        self._pressed = 0

    def _get_font(self):
        if not self.font:
            return ImageFont.load_default()

        key = (self.font, self.image)
        if key in _FONTCACHE:
            return _FONTCACHE[key]
        
        font = ImageFont.truetype(self.font, size=self.image)
        _FONTCACHE[key] = font

        return font

    def draw(self, variables: Variables) -> Image.Image:
        img = self._shown_image

        text = variables.format(self.text)

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
            img.paste(self.image.resize((iw, ih), Image.BICUBIC), ((img.width - iw)//2, 5))
            ty = img.height - 5 - th

        draw.text((tx, ty), text, font=font, fill=self.fg)
        return img

    async def when_key_pressed(self):
        self._pressed += 1

        if self.pressed is not None:
            get_running_loop().create_task(self.pressed.apply_actions(self.parent.app, self))

    async def when_key_released(self):
        if self._pressed == 0:
            self.parent.app.logger.debug("Button press was masked.")
            return
        self._pressed -= 1

        if self.released is not None:
            get_running_loop().create_task(self.released.apply_actions(self.parent.app, self))

    def reset(self):
        self.text = ""
        self.font = ""
        self.size = "10"
        self.image = ""
        self.bg = "#000"
        self.fg = "#FFF"

        self.pressed = None
        self.released = None

    def __repr__(self):
        return f"<Button ({self.x},{self.y})>"

    def apply(self, settings, unseen=None, exclude_classes=[]):
        if unseen is None:
            unseen = set(settings.keys())
        if "state" in unseen and "state" in settings:
            unseen.remove("state")
            self.state = settings["state"]
            self.parent.apply_button_contexts(self)
        super().apply(settings, unseen, exclude_classes)


class Display(State):
    fps = StateVariable.with_parser(float, 0)
    brightness = StateVariable.with_parser(float, 1.0)


    def __init__(self, app: 'streamdeckd.application.Streamdeckd', ctx: 'streamdeckd.config.streamdeck.StreamDeckContext', deck: StreamDeck):
        super().__init__(None)
        self.app = app
        self.deck = deck
        self.ctx = ctx

        self.current_menu = None

        self.buttons: Dict[Tuple[int, int], Button] = {}

    @property
    def menu(self):
        return self.current_menu

    @menu.setter
    def menu(self, name: Optional[str]):
        self.current_menu = self.ctx.get_menu(name)
        for btn in self.buttons.values():
            self.apply_button_contexts(btn)

        self.render()
    
    async def when_key_state_changed(self, _, kid: int, pressed: bool):
        y, x = divmod(kid, self.deck.key_layout()[1])
        btn = self.buttons[(x, y)]
        if pressed:
            self.app.logger.info(f"Pressed button {x},{y}")
            await btn.when_key_pressed()
        else:
            self.app.logger.info(f"Released button {x},{y}")
            await btn.when_key_released()

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

    def open(self) -> None:
        self.deck.set_key_callback_async(self.when_key_state_changed)
        self.apply(self.ctx.state)

        self.deck.open()

        layout = self.deck.key_layout()
        for y in range(layout[0]):
            for x in range(layout[1]):
                self.buttons[(x, y)] = Button(x, y, self)

        self.menu = None

        if self.fps:
            self.app.scheduler.add_recurring(1.0 / self.fps, self._update)

    async def _update(self):
        self.render()

    def render(self) -> None:
        self.app.logger.debug(f"Rendering {self.deck.id()}")
        width = self.deck.key_layout()[1]
        _vardata: dict = {}
        txtvars = self.app.variables.make_child()
        txtvars.add_map(_vardata)

        self.deck.set_brightness(self.brightness)

        for (x, y), btn in self.buttons.items():
            p = y*width + x
            _vardata.update(x=x, y=y, p=p)

            raw = self._draw(x, y, btn, txtvars)
            self.deck.set_key_image(p, raw)

    def _draw(self, x: int, y: int, btn: Button, txtvars: Variables):
        img = btn.draw(txtvars)
        return PILHelper.to_native_format(self.deck, img)
        
    def close(self) -> None:
        try:
            self.deck.reset()
        finally:
            self.deck.close()

    def apply(self, settings, unseen=None, exclude_classes=[]):
        if unseen is None:
            unseen = set(settings.keys())
        if "menu" in unseen and "menu" in settings:
            unseen.remove("menu")
            self.menu = settings["menu"]

        super().apply(settings, unseen, exclude_classes)