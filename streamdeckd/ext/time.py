import datetime

from streamdeckd.application import Streamdeckd
from streamdeckd.config.application import ApplicationContext

def load(app: Streamdeckd, ctx: ApplicationContext):
    pass


class CurrentTime:
    def __format__(self, spec):
        return datetime.datetime.now().__format__(spec)

async def start(app: Streamdeckd):
    app.variables.add_map({"now": CurrentTime()})

async def stop(app: Streamdeckd):
    pass