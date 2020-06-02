import time
import pulsectl

from streamdeckd.application import Streamdeckd
from streamdeckd.signals import Signal, register
from streamdeckd.config.validators import validated
from streamdeckd.config.application import ApplicationContext
from streamdeckd.config.action import ActionableContext, ActionContext


PULSE_INSTANCE: pulsectl.Pulse = None


class PulseStream:

    def __init__(self, stream):
        self.stream = stream

    def __format__(self, spec):
        if spec == "muted":
            return str(self.stream.mute)


class PulseValues:

    def __format__(self, spec):
        name, spec = spec.split(":", 1)
        return PulseStream(get_stream_by_name(name)).__format__(spec)


def get_stream_by_name(name):
    try:
        return PULSE_INSTANCE.get_sink_by_name(name)
    except pulsectl.PulseError:
        return PULSE_INSTANCE.get_source_by_name(name)


class PulseAudioActions(ActionContext):

    @validated(min_args=2, max_args=2, with_block=False)
    def on_pa_volume(self, args, block):
        sink = None

        @self.actions.append
        @ActionableContext.simple
        async def _pa_op(_, __):
            nonlocal sink
            if sink is None:
                sink = get_stream_by_name(args[0])
            
            PULSE_INSTANCE.volume_set_all_chans(sink, float(args[1]))
        return _pa_op

    @validated(min_args=1, max_args=2, with_block=False)
    def on_pa_mute(self, args, block):
        sink = None

        @self.actions.append
        @ActionableContext.simple
        async def _pa_op(_, __):
            nonlocal sink
            if sink is None:
                sink = get_stream_by_name(args[0])

            if len(args) == 1:
                mode = "mute"
            else:
                mode = args[1]

            if mode == "mute":
                PULSE_INSTANCE.mute(sink, True)
            elif mode == "unmute":
                PULSE_INSTANCE.mute(sink, False)
            elif mode == "toggle":
                PULSE_INSTANCE.mute(sink, not sink.mute)
        return _pa_op


def load(app: Streamdeckd, ctx: ApplicationContext):
    ActionContext.register(PulseAudioActions)

async def start(app: Streamdeckd):
    global PULSE_INSTANCE
    PULSE_INSTANCE = pulsectl.Pulse('streamdeckd', connect=False)
    PULSE_INSTANCE.connect()

    app.variables.add_map({"pulse": PulseValues()})

async def stop(app: Streamdeckd):
    global PULSE_INSTANCE
    if PULSE_INSTANCE is not None:
        PULSE_INSTANCE.disconnect()
        PULSE_INSTANCE = None
