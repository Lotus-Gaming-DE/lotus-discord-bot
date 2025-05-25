import logging
import discord

logger = logging.getLogger(__name__)  # e.g. 'cogs.quiz.views'


async def display_question(channel: discord.TextChannel, question_text: str) -> None:
    """Sendet die Quizfrage in den Channel."""
    await channel.send(f"**Quizfrage:** {question_text}")


async def display_correct_answer(channel: discord.TextChannel, user: discord.Member) -> None:
    """Meldet dem Nutzer eine richtige Antwort."""
    await channel.send(f"Richtig, {user.mention}! 🎉")


async def display_incorrect_answer(channel: discord.TextChannel, user: discord.Member) -> None:
    """Meldet dem Nutzer eine falsche Antwort."""
    await channel.send(f"Das ist leider falsch, {user.mention}. 😔 Versuche es erneut!")
