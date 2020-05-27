import sys
import logging
import traceback
from typing import Optional, List, Callable, Awaitable, Set, Any, Dict
from asyncio import get_event_loop, get_running_loop, AbstractEventLoop

import crossplane
import aiorun

from streamdeckd.scheduler import Scheduler
from streamdeckd.variables import Variables
from streamdeckd.devices import get_default_source, DeviceSource
from streamdeckd.display import Display



class Streamdeckd:

    def __init__(self, config_file: str):
        self.config_file = config_file
        self.logger = logging.getLogger("streamdeckd")

        self._bootstrap_commands: Optional[List[Callable[[], Awaitable[None]]]] = []

        self.variables: Optional[Variables] = None
        self.scheduler: Optional[Scheduler] = None
        self.scanner: Optional[DeviceSource] = None

        self.displays: List[Any] = []
        self.plugins: List[Any] = []

        self._controlled_devices: Dict[str, Display] = {}
        self._known_devices: Set[str] = set()

    async def when_connect(self, identifier: str):
        self.logger.debug(f"Found device: {identifier}")
        deck = self.scanner.get_scanned(identifier)

        for display_ctx in self.displays:
            if display_ctx.matches(deck):
                break
        else:
            for display_ctx in self.displays:
                if display_ctx.default:
                    break
            else:
                self.logger.info(f"Got unconfigured device: {identifier}")
                return

        disp = Display(self, display_ctx, deck)
        self._controlled_devices[identifier] = disp
        disp.open()

    async def when_disconnect(self, identifier: str):
        self.logger.debug(f"Lost device: {identifier}")
        if identifier in self._controlled_devices:
            self._controlled_devices.pop(identifier).close()

    async def perform_rescan(self):
        self.logger.debug("Performing rescan.")
        devices = set(self.scanner.rescan())
        
        new = devices - self._known_devices
        old = self._known_devices - devices
        self._known_devices |= devices

        for dev in old:
            await self.when_disconnect(dev)
        for dev in new:
            await self.when_connect(dev)

    def parse_configuration(self):
        if self.config_file is None:
            self.logger.critical("Could not find config file.")
            sys.exit(1)

        parsed = crossplane.parse(self.config_file, combine=True)
        if parsed["status"] != "ok":
            self.logger.critical("Failed to parse the configuration file.")
            for error in parsed["errors"]:
                self.logger.critical(f"In {error['file']} on {error['line']}: {error['error']!r}")
                sys.exit(1)
        block = parsed["config"][0]['parsed']

        from streamdeckd.config.application import ApplicationContext
        ctx = ApplicationContext(self)
        ctx.apply_directive("load", ("system",), None)
        ctx.apply_block(block)

        self.plugins = ctx.modules
        self._bootstrap_commands.append(ctx.apply)

    async def _start(self):
        try:
            await self.run()

        except Exception as e:
            for l in "".join(traceback.format_exception(type(e), e, e.__traceback__)).splitlines():
                self.logger.critical(l)
            get_running_loop().stop()

    async def run(self):
        self.variables = Variables()
        self.scheduler = Scheduler(get_running_loop())
        self.scanner = get_default_source()

        self.logger.info("Booting up...") 
        for command in self._bootstrap_commands:
            await command()
        self._bootstrap_commands = None

        for module in self.plugins:
            await module.start(self)

        for disp in self.displays:
            disp.apply_devices(self.scanner)

        self.logger.info("Boot completed.")

        await self.perform_rescan()

    async def end(self):
        self.scheduler.close()
        for dev in list(self._known_devices):
            await self.when_disconnect(dev)

        for module in self.plugins:
            await module.stop(self)

    def start(self) -> int:
        self.parse_configuration()
        loop = get_event_loop()
        loop.create_task(self._start())
        aiorun.run(loop=loop)
        loop.run_until_complete(self.end())
        return 0