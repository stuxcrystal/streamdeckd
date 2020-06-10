import os
import logging
import asyncio
import importlib
from datetime import timedelta
from typing import Sequence, Callable, Optional, Any

from streamdeckd.utils import load, parse_timespan
from streamdeckd.application import Streamdeckd

from streamdeckd.config.base import Context
from streamdeckd.config.validators import validated, validate


class EventLoopContext(Context):

    def __init__(self):
        self.loop = None
        self.policy = None

    @validated(min_args=1, max_args=1, with_block=False)
    def on_loop(self, args: Sequence[str], block: Sequence[dict]):
        factory: Callable[[], asyncio.AbstractEventLoop] = load(args[0])
        self.loop = factory

    @validated(min_args=1, max_args=1, with_block=False)
    def on_policy(self, args: Sequence[str], block: Sequence[dict]):
        factory: Callable[[], asyncio.AbstractEventLoopPolicy] = load(args[0])
        self.policy = factory

    def prepare(self):
        if self.policy is not None:
            asyncio.set_event_loop_policy(self.policy())
        if self.loop is not None:
            asyncio.set_event_loop(self.loop())


class LoggingContext(Context):

    def __init__(self):
        self.ctx = {}

    def apply(self):
        logging.basicConfig(**self.ctx)

    @validated(min_args=1, max_args=1, with_block=False)
    def on_level(self, args, block):
        validate("level", args, block, min_args=1, max_args=1, with_block=False)
        self.ctx["level"] = getattr(logging, args[0])
        
    def unknown_directive(self, name, args=(), block=()):
        validate(name, args, block, min_args=1, max_args=1, with_block=False)
        if block is not None:
            raise ValueError(f"{name}: Directive does not accept a block.")
        self.ctx[name] = " ".join(args)


class ApplicationContext(Context):

    def __init__(self, app: Streamdeckd):
        self.app = app
        self.rescan: Optional[timedelta] = None
        self.evctx = EventLoopContext()

        self.prepare_list = {
            0: [self.evctx.prepare]
        }

        self._loaded_modules = set()
        self.modules = []

    @validated(min_args=0, max_args=0, with_block=True)
    def on_eventloop(self, args: Sequence[str], block: Sequence[dict]):
        self.evctx.apply_block(block)

    @validated(min_args=0, max_args=0, with_block=True)
    def on_logger(self, args: Sequence[str], block: Sequence[dict]):
        ctx = LoggingContext()
        ctx.apply_block(block)
        ctx.apply()

    @validated(min_args=1, max_args=1, with_block=False)
    def on_rescan(self, args: Sequence[str], block: None):
        self.rescan = parse_timespan(args[0])

    @validated(min_args=1, max_args=1, with_block=False)
    def on_load(self, args: Sequence[str], block: None):
        if args[0] in self._loaded_modules:
            return

        module: Any = importlib.import_module("streamdeckd.ext." + args[0])
        self.modules.append(module)

        module.load(self.app, self)
        self._loaded_modules.add(args[0])

    if hasattr(os, "getreuid") and os.geteuid() == 0:
        @validated(min_args=1, max_args=1, with_block=False)
        def on_uid(self, args: Sequence[str], block: None):
            import pwd

            uid = None
            if args[0].isnumeric():
                uid = int(args[0])
            else:
                uid = pwd.getpwnam(args[0]).pw_uid
                
            self.prepare_list.setdefault(10, [lambda:None, lambda:None])[0] = lambda: os.setreuid(uid)

        @validated(min_args=1, max_args=1, with_block=False)
        def on_gid(self, args: Sequence[str], block: None):
            import grp

            gid = None
            if args[0].isnumeric():
                gid = int(args[0])
            else:
                gid = grp.getgrnam(args[0]).gr_gid

            self.prepare_list.setdefault(10, [lambda:None, lambda:None])[1] = lambda: os.setregid(gid)
    else:
        @validated(min_args=1, max_args=1, with_block=False)
        def on_uid(self, args: Sequence[str], block: None):
            raise ValueError("uid: Cannot drop privileges.")

        @validated(min_args=1, max_args=1, with_block=False)
        def on_gid(self, args: Sequence[str], block: None):
            raise ValueError("gid: Cannot drop privileges.")


    @validated(min_args=1, max_args=2, with_block=True)
    def on_streamdeck(self, args: Sequence[str], block: Sequence[dict]):
        default = False
        if len(args) == 2 and args[1] == "default":
            default = True
        
        from streamdeckd.config.streamdeck import StreamdeckContext
        ctx = StreamdeckContext(self.app, args[0], default=default)
        ctx.apply_block(block)
        self.app.displays.append(ctx)

    def prepare(self):
        for stage in sorted(self.prepare_list.keys()):
            for cb in self.prepare_list[stage]:
                cb()

    async def when_entered(self, app, target):
        pass

    async def when_leaving(self, app, target):
        pass

    async def apply(self):
        if self.rescan:
            self.app.scheduler.add_recurring(self.rescan, self.app.perform_rescan)