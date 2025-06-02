# cogs/quiz/cog.py

import logging
from collections import defaultdict
from discord.ext import commands
import discord

from .question_state import QuestionStateManager
from .scheduler import QuizScheduler
from .question_restorer import QuestionRestorer
from .question_manager import QuestionManager
from .message_tracker import MessageTracker
from .question_closer import QuestionCloser

logger = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.quiz_cog = self  # Referenz für andere Klassen

        # Interner Zustand
        self.current_questions: dict[str, dict] = {}
        self.answered_users: dict[str, set[int]] = defaultdict(set)
        self.awaiting_activity: dict[int, tuple[str, float]] = {}

        # State, Tracker, Manager
        self.state = QuestionStateManager("data/pers/quiz/question_state.json")
        self.tracker = MessageTracker(bot=self.bot)
        self.manager = QuestionManager(self)
        self.closer = QuestionCloser(bot=self.bot, state=self.state)

        # Wiederherstellen
        self.restorer = QuestionRestorer(
            bot=self.bot, state_manager=self.state)
        self.restorer.restore_all()

        # Pro Area: Scheduler starten
        for area in self.bot.quiz_data:
            QuizScheduler(
                bot=self.bot,
                area=area,
                prepare_question_callback=self.manager.prepare_question,
                close_question_callback=self.closer.close_question
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        self.tracker.register_message(message)
