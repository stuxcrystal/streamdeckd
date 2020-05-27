import traceback
from typing import Union, Callable, Awaitable, Any, Dict, Optional, cast
from datetime import timedelta
from asyncio import AbstractEventLoop, Handle, Task


class Scheduler:

    def __init__(self, loop: AbstractEventLoop):
        super().__init__()
        self.loop = loop
        self.jobs: Dict[int, Optional[Handle]] = {}
        self.running: Dict[int, Task] = {}
        self._idx = 0

    def _register_recurring(self, every: float, idx:int , cb: Callable[[], Awaitable[Any]]):
        if idx not in self.jobs:
            return

        self.jobs[idx] = self.loop.call_later(every, lambda: self._run_recurring(every, idx, cb))

    def _run_recurring(self, every: float, idx, cb):
        async def bootstrap_recurring():
            try:
                await cb()
            except Exception as e:
                traceback.print_exception(type(e), e, e.__traceback__)
            finally:
                self.running.pop(idx, None)
                self._register_recurring(every, idx, cb)
        self.running[idx] = self.loop.create_task(bootstrap_recurring())

    def add_recurring(self, every: Union[timedelta, int, float], cb: Callable[[], Awaitable[Any]]) -> int:
        if isinstance(every, timedelta):
            every = cast(float, every.total_seconds())

        idx = self._idx
        self._idx += 1
        self.jobs[idx] = None
        self._register_recurring(every, idx, cb)
        return idx

    def remove_recurring(self, id: int):
        handle: Optional[Handle] = self.jobs.pop(id, None)
        if not handle:
            return
        handle.cancel()

    def close(self):
        for id_job in list(self.jobs.keys()):
            self.remove_recurring(id_job)

        for id_task in list(self.running.keys()):
            self.running[id_task].cancel()