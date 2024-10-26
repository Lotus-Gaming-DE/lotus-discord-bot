import discord
from discord.ext import commands
import asyncio
import os

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="", intents=intents)


async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')


@bot.event
async def on_ready():
    # Server-ID aus den Umgebungsvariablen lesen
    server_id = os.getenv('server_id')
    if server_id is None:
        print("Server ID nicht gefunden. Stelle sicher, dass die Environment-Variable 'server_id' gesetzt ist.")
        return

    # ID in eine Ganzzahl konvertieren
    guild = discord.Object(id=int(server_id))
    # Slash-Commands nur für diesen Server synchronisieren
    await bot.tree.sync(guild=guild)
    print(f'Bot ist online als {bot.user} und mit dem Server synchronisiert.')


async def main():
    # Lies den Token aus der Environment-Variable
    bot_token = os.getenv('bot_key')
    if bot_token is None:
        print("Bot Token nicht gefunden. Stelle sicher, dass die Environment-Variable 'bot_key' gesetzt ist.")
        return

    async with bot:
        await load_cogs()
        await bot.start(bot_token)

asyncio.run(main())
