import datetime

from streamdeckd.utils import parse_timespan
from streamdeckd.signals import Signal, register
from streamdeckd.application import Streamdeckd
from streamdeckd.config.validators import validated
from streamdeckd.config.application import ApplicationContext


class CurrentTime:
    def __format__(self, spec):
        return datetime.datetime.now().__format__(spec)


class EverySignal(Signal):
    def __init__(self, app: Streamdeckd):
        self.app = app
        self.ts = None
        self.id = None

    @validated(min_args=1, max_args=1)
    def configure(self, args, _):
        self.ts = parse_timespan(args[0])

    def register(self, cb):
        if self.id is not None:
            return

        self.id = self.app.scheduler.add_recurring(self.ts, cb)

    def unregister(self, cb):
        if self.id is None:
            return

        self.app.scheduler.remove_recurring(self.id)
        self.id = None


def load(app: Streamdeckd, ctx: ApplicationContext):
    register("every")(lambda: EverySignal(app))

async def start(app: Streamdeckd):
    app.variables.add_map({"now": CurrentTime()})

async def stop(app: Streamdeckd):
    pass