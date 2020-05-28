from typing import Optional, Sequence, Callable, Awaitable


class Signal:

    def configure(self, args: Sequence[str], block: None):
        pass

    def register(self, cb: Callable[[], Awaitable[None]]):
        pass

    def unregister(self, cb: Callable[[], Awaitable[None]]):
        pass

SIGNALS = {}

def register(name: str):
    def _decorator(cls):
        SIGNALS[name] = cls
        return cls
    return _decorator


def create(name, args, block):
    signal = SIGNALS[name]()
    signal.configure(args, block)
    return signal