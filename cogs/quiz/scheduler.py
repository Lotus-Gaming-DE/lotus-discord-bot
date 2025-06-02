# cogs/quiz/scheduler.py

import logging
import random
import asyncio
import datetime

logger = logging.getLogger(__name__)


class QuizScheduler:
    def __init__(self, bot, area: str, prepare_question_callback, close_question_callback):
        self.bot = bot
        self.area = area
        self.prepare_question = prepare_question_callback
        self.close_question = close_question_callback
        self.time_window = datetime.timedelta(minutes=15)

        self.task = self.bot.loop.create_task(self.run())

    async def run(self):
        await self.bot.wait_until_ready()
        if self.area not in self.bot.quiz_data:
            logger.warning(
                f"[Scheduler] '{self.area}' nicht in quiz_data vorhanden.")
            return

        while True:
            now = datetime.datetime.utcnow()
            window_start = now.replace(second=0, microsecond=0)
            window_end = window_start + self.time_window

            latest = window_start + (self.time_window / 2)
            delta = max((latest - now).total_seconds(), 0)
            next_time = now + \
                datetime.timedelta(seconds=random.uniform(0, delta))
            delay = random.uniform(0, self.time_window.total_seconds() / 2)
            post_time = next_time + datetime.timedelta(seconds=delay)

            logger.info(
                f"[Scheduler] Neues Zeitfenster für '{self.area}': "
                f"{window_start:%H:%M:%S} bis {window_end:%H:%M:%S} – Frage geplant für ca. {post_time:%H:%M:%S}"
            )

            await asyncio.sleep((next_time - now).total_seconds())
            await asyncio.sleep(delay)

            if self.area not in self.bot.quiz_data:
                logger.warning(
                    f"[Scheduler] '{self.area}' nicht mehr in quiz_data.")
                return

            logger.debug(
                f"[Scheduler] Wache auf – prüfe Bedingungen für '{self.area}'...")
            await self.prepare_question(self.area, window_end)

            await asyncio.sleep(max((window_end - datetime.datetime.utcnow()).total_seconds(), 0))

            cid = self.bot.quiz_data[self.area]["channel_id"]
            self.bot.quiz_cog.awaiting_activity.pop(cid, None)
            if self.area in self.bot.quiz_cog.current_questions:
                await self.close_question(self.area, timed_out=True)
