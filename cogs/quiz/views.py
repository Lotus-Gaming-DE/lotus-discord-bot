# cogs/quiz/views.py
import discord


async def display_question(channel, question_text):
    """Sendet die Frage an den angegebenen Kanal."""
    await channel.send(f"**Quizfrage:** {question_text}")


async def display_correct_answer(channel, user):
    """Teilt dem Nutzer mit, dass seine Antwort korrekt war."""
    await channel.send(f"Richtig, {user.mention}! 🎉")


async def display_incorrect_answer(channel, user):
    """Teilt dem Nutzer mit, dass seine Antwort falsch war."""
    await channel.send(f"Das ist leider falsch, {user.mention}. 😔 Versuche es erneut!")
