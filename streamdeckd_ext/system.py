import asyncio

from streamdeckd.utils import parse_timespan
from streamdeckd.application import Streamdeckd
from streamdeckd.signals import Signal, register as register_signal
from streamdeckd.config.application import ApplicationContext

from streamdeckd.config.action import ActionableContext, ActionContext, SequentialActionContext
from streamdeckd.config.validators import validated


CUSTOM_VARS = {}
SIGNALS = {}


class ExitAction(ActionableContext):

    @validated(min_args=0, max_args=0, with_block=False)
    def on_exit(self, args, block):
        pass

    async def apply_actions(self, _, __):
        asyncio.get_running_loop().stop()


class WhenSignal(Signal):

    def __init__(self, app: Streamdeckd):
        self.app = app
        self.sigs = {}

    @validated(min_args=1, max_args=1)
    def configure(self, args, _):
        self.lhs, self.op, self.rhs = args

    def register(self, cb):
        last_value = [None, None]
        async def _check(self):
            nonlocal last_value
            current_value_lhs = self.app.variables.format(self.lhs)
            current_value_rhs = self.app.variables.format(self.rhs)
            if [current_value_lhs, current_value_rhs] == last_value:
                return
            last_value = [current_value_lhs, current_value_rhs]
            if check_conj(current_value_lhs, current_value_rhs, self.op):
                await cb()

        self.sigs[cb] = self.app.scheduler.add_recurring(0.1, _check)

    def unregister(self, cb):
        handle = self.sigs.pop(cb, None)
        if handle is None:
            self.app.scheduler.remove_recurring(handle)


class ChangedSignal(Signal):

    def __init__(self, app: Streamdeckd):
        self.app = app
        self.sigs = {}

    @validated(min_args=1, max_args=1)
    def configure(self, args, _):
        self.data = args[0]

    def register(self, cb):
        last_value = None

        async def _check():
            nonlocal last_value

            current_value = self.app.variables.format(self.data)
            if current_value == last_value:
                return
            last_value = current_value

            await cb()

        self.sigs[cb] = self.app.scheduler.add_recurring(0.1, _check)

    def unregister(self, cb):
        handle = self.sigs.pop(cb, None)
        if handle is not None:
            self.app.scheduler.remove_recurring(handle)


class CustomSignals(Signal):
    def __init__(self):
        self._name = None

    @validated(min_args=1, max_args=1)
    def configure(self, args, _):
        self._name = args[0]
        SIGNALS[args[0]] = []

    def register(self, cb):
        if cb not in SIGNALS:
            SIGNALS[self._name].append(cb)

    def unregister(self, cb):
        while cb in SIGNALS:
            SIGNALS[self._name].remove(cb)


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

    @validated(min_args=1, max_args=1, with_block=False)
    def on_emit(self, args, block):
        @self.actions.append
        @ActionableContext.simple
        async def _op(app, __):
            value = app.variables.format(args[0])
            if value not in SIGNALS:
                return
            await asyncio.gather(*(sig() for sig in SIGNALS[value]))


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


class IfAction(ActionContext):

    @validated(min_args=3, max_args=3, with_block=True)
    def on_if(self, args, block):
        self.op = args[1]
        if self.op not in {"==", "!=", "in", "not in"}:
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


class WhileAction(ActionContext):
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

    register_signal("custom")(CustomSignals)
    register_signal("when")(lambda: WhenSignal(app))
    register_signal("changed")(lambda: ChangedSignal(app))

async def start(app: Streamdeckd):
    app.variables.add_map(CUSTOM_VARS)

async def stop(app: Streamdeckd):
    app.variables.remove_map(CUSTOM_VARS)
