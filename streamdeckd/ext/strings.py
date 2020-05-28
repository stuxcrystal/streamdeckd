from streamdeckd.variables import Variables
from streamdeckd.application import Streamdeckd
from streamdeckd.config.validators import validated
from streamdeckd.config.application import ApplicationContext


USER_VARS = {}


class SplitAccessor:

    def __init__(self, app, text, split):
        self.app = app
        self.text = text
        self.split = split

    def __format__(self, spec):
        text = self.app.variables.format(self.text).split(self.split)

        nextspec = ""
        if "," in spec:
            spec, nextspec = spec.split(",", 1)
        idx = int(spec)
        if idx >= len(text):
            return ""
        
        return text[idx].__format__(nextspec)


def load(app: Streamdeckd, ctx: ApplicationContext):
    @validated(min_args=3, max_args=3, with_block=False, requires_self=False)
    def on_split_variable(args, block):
        USER_VARS[args[0]] = SplitAccessor(app, args[1], args[2])
    ctx.on_split_variable = on_split_variable


async def start(app: Streamdeckd):
    app.variables.add_map(USER_VARS)

async def stop(app: Streamdeckd):
    app.variables.remove_map(USER_VARS)
