from __future__ import annotations

import asyncio
from collections import defaultdict

import discord
from discord.ext import commands

from log_setup import create_logged_task, get_logger

from .message_tracker import MessageTracker
from .question_closer import QuestionCloser
from .question_manager import QuestionManager
from .question_restorer import QuestionRestorer
from .question_state import QuestionInfo, QuestionStateManager
from .scheduler import QuizScheduler
from .duel_stats import DuelStats

logger = get_logger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        # Allow other modules to access the cog instance
        self.bot.quiz_cog = self

        # list of asyncio.Task objects created via ``_track_task``
        self.tasks: list[asyncio.Task] = []

        def _track_task(coro: asyncio.coroutine) -> asyncio.Task:
            task = create_logged_task(coro, logger)
            self.tasks.append(task)
            return task

        self._track_task = _track_task

        if not self.bot.quiz_data:
            logger.warning("[QuizCog] Keine Quiz-Konfiguration geladen.")

        self.current_questions: dict[str, QuestionInfo] = {}
        self.answered_users: dict[str, set[int]] = defaultdict(set)
        self.awaiting_activity: dict[int, tuple[str, float]] = {}
        self.schedulers: dict[str, QuizScheduler] = {}

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

        self.duel_stats = DuelStats("data/pers/quiz/duel_stats.db")

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
            self.schedulers[area] = scheduler

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.author.bot:
            return
        self.tracker.register_message(message)

    def cog_unload(self) -> None:
        for scheduler in self.schedulers.values():
            scheduler.task.cancel()
        if hasattr(self.restorer, "cancel_all"):
            self.restorer.cancel_all()
        for task in self.tasks:
            task.cancel()
        create_logged_task(self.duel_stats.close(), logger)
