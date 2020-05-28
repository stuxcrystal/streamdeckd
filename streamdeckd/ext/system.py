import asyncio

from streamdeckd.utils import parse_timespan
from streamdeckd.application import Streamdeckd
from streamdeckd.config.application import ApplicationContext

from streamdeckd.config.action import ActionableContext, ActionContext, SequentialActionContext
from streamdeckd.config.validators import validated


CUSTOM_VARS = {}


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
    def on_log(self, args, block):
        @self.actions.append
        @ActionableContext.simple
        async def _op(app: Streamdeckd, _):
            message = app.variables.format(args[0])
            app.logger.info(message)

    @validated(min_args=2, max_args=2, with_block=False)
    def on_set(self, args, block):
        CUSTOM_VARS[args[0]] = ""

        @self.actions.append
        @ActionableContext.simple
        async def _op(app: Streamdeckd, _):
            value = app.variables.format(args[1])
            CUSTOM_VARS[args[0]] = value


def check_conj(lhs, rhs, op):
    if op == "==":
        if lhs != rhs: return False
    elif op == "!=":
        if lhs == rhs: return False
    elif op == "in":
        if lhs not in rhs: return False
    elif op == "not in":
        if lhs in rhs: return False
    else:
        return False
    return True


class IfAction(ActionableContext):

    @validated(min_args=3, max_args=3, with_block=True)
    def on_if(self, args, block):
        self.op = args[1]
        if op not in {"==", "!=", "in", "not in"}:
            raise ValueError(f"if: unknown operand {op}")
        self.lhs = args[0]
        self.rhs = args[2]

        ctx = SequentialActionContext()
        ctx.apply_block(block)

        self.actions.append(ctx)

    async def apply_actions(self, app, target):
        lhs = app.variables.format(self.lhs)
        rhs = app.variables.format(self.rhs)

        if check_conj(lhs, rhs, self.op):
            await super().apply_actions(app, target)


class WhileAction(ActionableContext):
    @validated(min_args=3, max_args=3, with_block=True)
    def on_while(self, args, block):
        self.op = args[1]
        if op not in {"==", "!=", "in", "not in"}:
            raise ValueError(f"while: unknown operand {op}")
        self.lhs = args[0]
        self.rhs = args[2]

        ctx = SequentialActionContext()
        ctx.apply_block(block)

        self.actions.append(ctx)

    async def apply_actions(self, app, target):
        lhs = app.variables.format(self.lhs)
        rhs = app.variables.format(self.rhs)

        while check_conj(lhs, rhs, self.op):
            await super().apply_actions(app, target)


def load(app: Streamdeckd, ctx: ApplicationContext):
    ActionContext.register(ExitAction)
    ActionContext.register(SimpleActions)

    ActionContext.register(IfAction)
    ActionContext.register(WhileAction)

async def start(app: Streamdeckd):
    app.variables.add_map(CUSTOM_VARS)

async def stop(app: Streamdeckd):
    app.variables.remove_map(CUSTOM_VARS)
