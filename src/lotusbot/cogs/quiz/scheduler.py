import random
import asyncio
import datetime

from lotusbot.log_setup import get_logger


class QuizScheduler:
    def __init__(
        self,
        bot,
        area: str,
        prepare_question_callback,
        close_question_callback,
        post_time: datetime.datetime | None = None,
        window_end: datetime.datetime | None = None,
    ) -> None:
        """Schedule automatic quiz questions for one area."""
        self.bot = bot
        self.area = area
        self.prepare_question = prepare_question_callback
        self.close_question = close_question_callback
        self.logger = get_logger(__name__, area=area)
        self.post_time = post_time
        self.window_end = window_end
        self.task: asyncio.Task | None = None

    async def run(self) -> None:
        """Background task loop scheduling questions in random intervals."""
        await self.bot.wait_until_ready()
        if self.area not in self.bot.quiz_data:
            self.logger.warning(
                f"[Scheduler] '{self.area}' nicht in quiz_data vorhanden."
            )
            return

        while True:
            cfg = self.bot.quiz_data[self.area]
            time_window = cfg.time_window

            if self.post_time and self.window_end:
                post_time = self.post_time
                window_end = self.window_end
                self.post_time = None
                self.window_end = None
                self.logger.info(
                    f"[Scheduler] Wiederaufnahme des Zeitfensters für '{self.area}' "
                    f"bis {window_end:%H:%M}, Frage bei {post_time:%H:%M:%S}"
                )
            else:
                now = datetime.datetime.utcnow()
                window_start = now.replace(second=0, microsecond=0)
                window_end = window_start + time_window

                next_time = window_start + datetime.timedelta(
                    seconds=random.uniform(0, time_window.total_seconds() / 2)
                )
                post_time = next_time + datetime.timedelta(
                    seconds=random.uniform(0, 10)
                )

                await self.bot.quiz_cog.state.set_schedule(
                    self.area, post_time, window_end
                )

                self.logger.info(
                    f"[Scheduler] Neues Zeitfenster für '{self.area}' bis {window_end:%H:%M}. "
                    f"Frage geplant für ca. {post_time:%H:%M:%S}"
                )

            now = datetime.datetime.utcnow()
            await asyncio.sleep(max((post_time - now).total_seconds(), 0))

            if self.area not in self.bot.quiz_data:
                self.logger.warning(
                    f"[Scheduler] '{self.area}' nicht mehr in quiz_data."
                )
                return

            self.logger.debug(
                f"[Scheduler] Wache auf – prüfe Bedingungen für '{self.area}'..."
            )
            await self.prepare_question(self.area, window_end)
            await self.bot.quiz_cog.state.clear_schedule(self.area)

            await asyncio.sleep(
                max((window_end - datetime.datetime.utcnow()).total_seconds(), 0)
            )

            cid = self.bot.quiz_data[self.area].channel_id
            self.bot.quiz_cog.awaiting_activity.pop(cid, None)
            qinfo = self.bot.quiz_cog.current_questions.get(self.area)
            if qinfo:
                await self.close_question(self.area, qinfo=qinfo, timed_out=True)
