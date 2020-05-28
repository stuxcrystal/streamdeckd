from typing import TypeVar, Dict, Optional, Callable
from datetime import timedelta
from importlib import import_module

from PIL import Image, ImageColor

from streamdeckd.state import StateVariable


T = TypeVar("T")


def load(path: str) -> T:
    module, attr = path.split(":")
    mod = import_module(module)
    return getattr(mod, attr)


TIME_UNITS = {
    "ms": 0.001,
    "s": 1,
    "m": 60,
    "h": 60*60,
    "d": 60*60*24,
    "m": 60*60*24*30,
    "y": 60*60*365
}


def parse_timespan(tinfo: str) -> timedelta:
    if tinfo.isnumeric():
        return timedelta(seconds=int(tinfo))
    if tinfo[:-1].isnumeric():
        return timedelta(seconds=int(tinfo[:-1])*TIME_UNITS[tinfo[-1]])
    raise ValueError("Cannot parse timespan.")


def parse_color(data: str):
    return ImageColor.getrgb(data)


_IMAGE_CACHE: Dict[str, Image.Image] = {}


def parse_img(path: str, sz=None) -> Optional[Image.Image]:
    if not path:
        return None

    if path in _IMAGE_CACHE:
        img = _IMAGE_CACHE[path]
    else:
        with open(path, "rb") as f:
            img = Image.open(f)
            img = img.copy()
        _IMAGE_CACHE[path] = img

    if sz is not None:
        img = img.resize(sz, Image.BICUBIC)

    return img


def parse_color_or_img(data: str, sz=None) -> Image.Image:
    if data.startswith("#"):
        if sz is None:
            sz = (1,1)
        return Image.new("RGB", sz, color=data)
    elif not data:
        return None
    else:
        return parse_img(data, sz)


TimeSpanStateVariable = StateVariable.from_parser(parse_timespan)
ColorStateVariable = StateVariable.from_parser(parse_color)
ImageOrColorStateVariable = StateVariable.from_parser(parse_color_or_img)
ImageStateVariable = StateVariable.from_parser(parse_img)



class LiveVariable:

    def __init__(self, cb: Callable[[], str]):
        self.cb = cb

    def __format__(self, spec: str):
        return self.cb().__format__(spec)