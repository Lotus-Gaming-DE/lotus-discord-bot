from __future__ import annotations

from collections import defaultdict

import discord
from discord.ext import commands

from lotus_bot.log_setup import get_logger
from lotus_bot.utils.managed_cog import ManagedTaskCog

from .message_tracker import MessageTracker
from .question_closer import QuestionCloser
from .question_manager import QuestionManager
from .question_restorer import QuestionRestorer
from .question_state import QuestionInfo, QuestionStateManager
from .scheduler import QuizScheduler
from .stats import QuizStats

logger = get_logger(__name__)


class QuizCog(ManagedTaskCog):
    def __init__(self, bot: commands.Bot) -> None:
        super().__init__()
        self.bot = bot
        # Allow other modules to access the cog instance
        self.bot.quiz_cog = self

        self._track_task = self.create_task

        if not self.bot.quiz_data:
            logger.warning("[QuizCog] No quiz configuration loaded.")

        self.current_questions: dict[str, QuestionInfo] = {}
        self.answered_users: dict[str, set[int]] = defaultdict(set)
        self.awaiting_activity: dict[int, tuple[str, float]] = {}
        self.schedulers: dict[str, QuizScheduler] = {}
        self.active_duels: set[int] = set()
        self.stats = QuizStats("data/pers/quiz/stats.json")

        # Find existing QuestionStateManager or create a default one
        state = None
        for cfg in self.bot.quiz_data.values():
            if hasattr(cfg, "question_state"):
                state = cfg.question_state
                break
            if isinstance(cfg, dict) and "question_state" in cfg:
                state = cfg["question_state"]
                break
        if state is None:
            state = QuestionStateManager("data/pers/quiz/question_state.json")
        self.state: QuestionStateManager = state

        self.manager = QuestionManager(self)
        self.tracker = MessageTracker(self.bot, self.manager.ask_question)
        self.closer = QuestionCloser(bot=self.bot, state=self.state)

        self._track_task(self.tracker.initialize())

        self.restorer = QuestionRestorer(
            bot=self.bot, state_manager=self.state, create_task=self._track_task
        )
        self._track_task(self.restorer.restore_all())

        for area, cfg in self.bot.quiz_data.items():
            active = cfg.active if hasattr(cfg, "active") else cfg.get("active")
            if not active:
                continue
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
            scheduler.task = self._track_task(scheduler.run())
            self.schedulers[area] = scheduler

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        self.tracker.register_message(message)

    def cog_unload(self) -> None:
        """Remove background tasks and clear ``bot.quiz_cog`` reference."""
        super().cog_unload()
        if hasattr(self.bot, "quiz_cog"):
            del self.bot.quiz_cog
