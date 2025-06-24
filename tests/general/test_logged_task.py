import asyncio
import logging
import pytest

import log_setup


@pytest.mark.asyncio
async def test_cancelled_task_is_ignored(caplog):
    async def coro():
        await asyncio.sleep(0)

    task = log_setup.create_logged_task(coro(), logging.getLogger(__name__))
    await asyncio.sleep(0)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)

    assert not caplog.records
