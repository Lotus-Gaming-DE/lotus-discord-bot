import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

from cogs.quiz.data_loader import DataLoader as QuizDataLoader
from cogs.wcr.data_loader import load_wcr_data

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)
bot.quiz_data = {}


@bot.event
async def on_ready():
    print(f"[bot] Bot is online as {bot.user} (ID: {bot.user.id})")


async def load_all_data():
    # Quiz
    quiz_loader = QuizDataLoader()
    quiz_questions, quiz_languages = quiz_loader.load_all_languages()
    bot.quiz_data["questions"] = quiz_questions
    bot.quiz_data["languages"] = quiz_languages

    # WCR
    wcr_data = load_wcr_data()
    bot.quiz_data["wcr"] = wcr_data

    print("[bot] Gemeinsame Daten geladen: ['questions', 'languages', 'wcr']")


async def load_extensions():
    await bot.load_extension("cogs.quiz.__init__")
    await bot.load_extension("cogs.champion.__init__")
    await bot.load_extension("cogs.wcr.__init__")


async def main():
    await load_all_data()
    await load_extensions()
    await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
