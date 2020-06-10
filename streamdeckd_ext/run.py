import asyncio

from streamdeckd.application import Streamdeckd
from streamdeckd.config.application import ApplicationContext

from streamdeckd.config.action import ActionableContext, ActionContext
from streamdeckd.config.validators import validated


EXITCODE_VARS = {}


class SimpleActions(ActionContext):
    @validated(min_args=1, max_args=2, with_block=False)
    def on_run(self, args, block):
        exitvar = "exitcode"
        if len(args) == 2:
            exitvar = args[1]

        EXITCODE_VARS[exitvar] = ""

        @self.actions.append
        @ActionableContext.simple
        async def _op(app: Streamdeckd, _):
            command = app.variables.format(args[0])
            run = await asyncio.create_subprocess_shell(command)
            exitcode = await run.wait()
            EXITCODE_VARS[exitvar] = str(exitcode)


def load(app: Streamdeckd, ctx: ApplicationContext):
    ActionContext.register(SimpleActions)

async def start(app: Streamdeckd):
    app.variables.add_map(EXITCODE_VARS)

async def stop(app: Streamdeckd):
    app.variables.remove_map(EXITCODE_VARS)
