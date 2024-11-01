# cogs/quiz_cog.py
import discord
from discord.ext import commands
import logging

logger = logging.getLogger(__name__)


class QuizCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Hier kannst du weitere Initialisierungen vornehmen
        self.current_question = None
        self.current_answer = None
        self.active = False

    @commands.command(name="start_quiz")
    async def start_quiz(self, ctx):
        if self.active:
            await ctx.send("Ein Quiz läuft bereits!")
            return
        self.active = True
        # Beispiel für eine Frage
        self.current_question = "Was ist die Hauptstadt von Frankreich?"
        self.current_answer = "Paris"
        await ctx.send(f"Quiz gestartet!\nFrage: {self.current_question}")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author == self.bot.user:
            return  # Ignoriere Nachrichten vom Bot selbst

        if not self.active:
            return  # Kein aktives Quiz

        if self.current_question and message.content.lower() == self.current_answer.lower():
            await message.channel.send(f"Glückwunsch {message.author.mention}, das ist korrekt!")
            logger.info(f"{message.author} hat die richtige Antwort gegeben.")
            self.current_question = None
            self.current_answer = None
            self.active = False
        else:
            # Optional: Rückmeldung bei falscher Antwort
            logger.info(f"{message.author} hat eine falsche Antwort gegeben: {
                        message.content}")
            pass  # Keine Aktion bei falscher Antwort

    @commands.command(name="stop_quiz")
    async def stop_quiz(self, ctx):
        if not self.active:
            await ctx.send("Es läuft kein Quiz.")
            return
        self.active = False
        self.current_question = None
        self.current_answer = None
        await ctx.send("Quiz gestoppt.")


async def setup(bot):
    await bot.add_cog(QuizCog(bot))
