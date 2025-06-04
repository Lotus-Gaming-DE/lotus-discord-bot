from collections import defaultdict
from discord.ext import commands
import discord
import asyncio

from log_setup import get_logger, create_logged_task

from .question_state import QuestionStateManager
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

        if not self.bot.quiz_data:
            logger.warning("[QuizCog] Keine Quiz-Konfiguration geladen.")

        self.current_questions: dict[str, dict] = {}
        self.answered_users: dict[str, set[int]] = defaultdict(set)
        self.awaiting_activity: dict[int, tuple[str, float]] = {}

        # Keep track of schedulers to properly clean them up on unload
        self.schedulers: list[QuizScheduler] = []

        # ``quiz_data`` might be empty if no areas are configured. In that case
        # fall back to a fresh ``QuestionStateManager`` so the cog can start
        # without raising an exception during initialization.
        self.state: QuestionStateManager = next(
            (cfg.get("question_state") for cfg in self.bot.quiz_data.values()
             if "question_state" in cfg),
            QuestionStateManager("data/pers/quiz/question_state.json")
        )

        self.manager = QuestionManager(self)
        self.tracker = MessageTracker(bot=self.bot, on_threshold=self.manager.ask_question)
        self.closer = QuestionCloser(bot=self.bot, state=self.state)

        create_logged_task(self.tracker.initialize(), logger)

        self.restorer = QuestionRestorer(
            bot=self.bot, state_manager=self.state)
        self.restorer.restore_all()

        for area, cfg in self.bot.quiz_data.items():
            if cfg.get("active"):
                scheduler = QuizScheduler(
                    bot=self.bot,
                    area=area,
                    prepare_question_callback=self.manager.prepare_question,
                    close_question_callback=self.closer.close_question
                )
                self.schedulers.append(scheduler)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        self.tracker.register_message(message)

    def cog_unload(self):
        """Cancel all running scheduler tasks when the cog is unloaded."""
        for scheduler in self.schedulers:
            scheduler.task.cancel()
