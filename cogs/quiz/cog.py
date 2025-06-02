import logging
from collections import defaultdict
import discord
from discord.ext import commands

from .question_state import QuestionStateManager
from .message_tracker import MessageTracker
from .question_closer import QuestionCloser
from .question_manager import QuestionManager
from .question_restorer import QuestionRestorer
from .scheduler import QuizScheduler

logger = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.quiz_cog = self

        # Interner Zustand
        self.current_questions: dict[str, dict] = {}
        self.answered_users: dict[str, set[int]] = defaultdict(set)
        self.awaiting_activity: dict[int, tuple[str, float]] = {}

        # Konfiguration
        self.max_wcr_dynamic_questions = 3
        self.wcr_question_count = 0
        self.time_window = bot.quiz_data.get("wcr", {}).get("time_window")

        # Manager
        self.state = next(iter(bot.quiz_data.values()))["question_state"]
        self.tracker = MessageTracker(bot)
        self.closer = QuestionCloser(bot, self.state)
        self.manager = QuestionManager(self)
        self.restorer = QuestionRestorer(bot, self.state)

        # Initialisierung
        bot.loop.create_task(self.tracker.initialize())
        self.restorer.restore_all()

        for area in bot.quiz_data:
            QuizScheduler(
                bot=bot,
                area=area,
                prepare_question_callback=self.manager.prepare_question,
                close_question_callback=self.closer.close_question
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        self.tracker.register_message(message)
