import asyncio

from streamdeckd.utils import parse_timespan
from streamdeckd.application import Streamdeckd
from streamdeckd.config.application import ApplicationContext

from streamdeckd.config.action import ActionableContext, ActionContext
from streamdeckd.config.validators import validated


class ExitAction(ActionableContext):

    @validated(min_args=0, max_args=0, with_block=False)
    def on_exit(self, args, block):
        pass

    async def apply_actions(self, _, __):
        asyncio.get_running_loop().stop()


class SimpleActions(ActionContext):

    @validated(min_args=1, max_args=1, with_block=False)
    def on_delay(self, args, block):
        seconds = parse_timespan(args[0]).total_seconds()

        @self.actions.append
        @ActionableContext.simple
        async def _op(_, __):
            await asyncio.sleep(seconds)
        
    @validated(min_args=1, max_args=1, with_block=False)
    def on_run(self, args, block):
        @self.actions.append
        @ActionableContext.simple
        async def _op(app: Streamdeckd, _):
            command = app.variables.format(args[0])
            run = await asyncio.create_subprocess_shell(command)
            await run.wait()


def load(app: Streamdeckd, ctx: ApplicationContext):
    ActionContext.register(ExitAction)
    ActionContext.register(SimpleActions)

async def start(app: Streamdeckd):
    pass

async def stop(app: Streamdeckd):
    pass
