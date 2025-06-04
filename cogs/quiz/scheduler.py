import random
import asyncio
import datetime

from log_setup import get_logger, create_logged_task

logger = get_logger(__name__)


class QuizScheduler:
    def __init__(self, bot, area: str, prepare_question_callback, close_question_callback) -> None:
        """Schedule automatic quiz questions for one area."""
        self.bot = bot
        self.area = area
        self.prepare_question = prepare_question_callback
        self.close_question = close_question_callback
        self.task = create_logged_task(self.run(), logger)

    async def run(self) -> None:
        """Background task loop scheduling questions in random intervals."""
        await self.bot.wait_until_ready()
        if self.area not in self.bot.quiz_data:
            logger.warning(
                f"[Scheduler] '{self.area}' nicht in quiz_data vorhanden.")
            return

        while True:
            cfg = self.bot.quiz_data[self.area]
            time_window = cfg.get(
                "time_window", datetime.timedelta(minutes=15))

            now = datetime.datetime.utcnow()
            window_start = now.replace(second=0, microsecond=0)
            window_end = window_start + time_window

            next_time = window_start + \
                datetime.timedelta(seconds=random.uniform(
                    0, time_window.total_seconds() / 2))
            post_time = next_time + \
                datetime.timedelta(seconds=random.uniform(0, 10))

            logger.info(
                f"[Scheduler] Neues Zeitfenster für '{self.area}' bis {window_end:%H:%M}. "
                f"Frage geplant für ca. {post_time:%H:%M:%S}"
            )

            await asyncio.sleep((next_time - now).total_seconds())
            await asyncio.sleep((post_time - next_time).total_seconds())

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
