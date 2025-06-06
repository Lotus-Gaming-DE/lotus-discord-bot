from collections import defaultdict
from discord.ext import commands
import discord

from log_setup import get_logger, create_logged_task
import asyncio

from .question_state import QuestionStateManager, QuestionInfo
from .scheduler import QuizScheduler
from .question_restorer import QuestionRestorer
from .question_manager import QuestionManager
from .message_tracker import MessageTracker
from .question_closer import QuestionCloser

logger = get_logger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.quiz_cog = self

        # Track created background tasks to cancel them on unload
        self.tasks: list[asyncio.Task] = []

        def _track_task(coro, logger=logger):
            task = create_logged_task(coro, logger)
            self.tasks.append(task)
            return task

        self._track_task = _track_task

        if not self.bot.quiz_data:
            logger.warning("[QuizCog] Keine Quiz-Konfiguration geladen.")

        self.current_questions: dict[str, QuestionInfo] = {}
        self.answered_users: dict[str, set[int]] = defaultdict(set)
        self.awaiting_activity: dict[int, tuple[str, float]] = {}

        # Keep track of schedulers to properly clean them up on unload
        # Mapping area -> QuizScheduler
        self.schedulers: dict[str, QuizScheduler] = {}

        # ``quiz_data`` might be empty if no areas are configured. In that case
        # fall back to a fresh ``QuestionStateManager`` so the cog can start
        # without raising an exception during initialization.
        self.state: QuestionStateManager = next(
            (
                cfg.question_state
                if hasattr(cfg, "question_state")
                else cfg.get("question_state")
                for cfg in self.bot.quiz_data.values()
                if hasattr(cfg, "question_state")
                or (isinstance(cfg, dict) and "question_state" in cfg)
            ),
            QuestionStateManager("data/pers/quiz/question_state.json"),
        )

        self.manager = QuestionManager(self)
        self.tracker = MessageTracker(bot=self.bot, on_threshold=self.manager.ask_question)
        self.closer = QuestionCloser(bot=self.bot, state=self.state)

        self.init_task = create_logged_task(self.tracker.initialize(), logger)
        self.tasks.append(create_logged_task(self.tracker.initialize(), logger))

        self.restorer = QuestionRestorer(
            bot=self.bot, state_manager=self.state, create_task=self._track_task
        )
        self.restorer.restore_all()

        for area, cfg in self.bot.quiz_data.items():
            active = cfg.active if hasattr(cfg, "active") else cfg.get("active")
            if active:
                sched_info = self.state.get_schedule(area)
                if sched_info:
                    post_time, window_end = sched_info
                else:
                    post_time = window_end = None
                scheduler = QuizScheduler(
                    bot=self.bot,
                    area=area,
                    prepare_question_callback=self.manager.prepare_question,
                    close_question_callback=self.closer.close_question,
                    post_time=post_time,
                    window_end=window_end,
                )
                self.schedulers[area] = scheduler
                self.tasks.append(scheduler.task)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        self.tracker.register_message(message)

    def cog_unload(self):
        """Cancel all running tasks when the cog is unloaded."""
        for scheduler in self.schedulers.values():
            scheduler.task.cancel()
        if hasattr(self, "init_task"):
            self.init_task.cancel()
        if hasattr(self.restorer, "cancel_all"):
            self.restorer.cancel_all()
        """Cancel all running background tasks when the cog is unloaded."""
        for scheduler in self.schedulers.values():
            scheduler.task.cancel()
        for task in self.tasks:
            task.cancel()
