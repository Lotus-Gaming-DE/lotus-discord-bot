import asyncio
from typing import Coroutine, Any
from discord.ext import commands

import lotusbot.log_setup as log_setup
from lotusbot.log_setup import get_logger


class ManagedTaskCog(commands.Cog):
    """Cog base class that tracks created tasks."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__()
        self.tasks: set[asyncio.Task] = set()
        self._logger = get_logger(self.__class__.__name__)

    def create_task(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task:
        """Create and register a task logging uncaught exceptions."""
        task = log_setup.create_logged_task(coro, self._logger)
        self.tasks.add(task)
        if hasattr(task, "add_done_callback"):
            task.add_done_callback(lambda t: self.tasks.discard(t))
        return task

    async def wait_closed(self) -> None:
        to_await = [
            t for t in self.tasks if asyncio.isfuture(t) or asyncio.iscoroutine(t)
        ]
        if to_await:
            await asyncio.gather(*to_await, return_exceptions=True)

    def cog_unload(self) -> None:
        for task in list(self.tasks):
            task.cancel()
