import discord
from discord.ext import commands
import os
import json
import asyncio

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

    guild = bot.get_guild(int(server_id))

    if guild:
        emojis_data = {}
        for emoji in guild.emojis:
            emojis_data[emoji.name] = {
                "id": emoji.id,
                "animated": emoji.animated,
                "syntax": f"{'<a:' if emoji.animated else '<:'}{emoji.name}:{emoji.id}>"
            }

        # Speichern in JSON-Datei im data-Ordner
        os.makedirs("data", exist_ok=True)
        with open("data/server_emojis.json", "w", encoding="utf-8") as f:
            json.dump(emojis_data, f, indent=4, ensure_ascii=False)

        print("Emoji-Liste wurde erfolgreich in 'data/server_emojis.json' gespeichert.")

    # Synchronisiere Slash-Commands nur für diesen Server
    await bot.tree.sync(guild=discord.Object(id=int(server_id)))
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
