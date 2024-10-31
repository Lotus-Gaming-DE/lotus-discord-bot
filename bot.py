import discord
from discord.ext import commands
import os
import json
import asyncio

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True  # Stelle sicher, dass die Guilds-Intents aktiviert sind

bot = commands.Bot(command_prefix="", intents=intents)


async def load_cogs():
    for filename in os.listdir('./cogs'):
        if filename.endswith('.py'):
            await bot.load_extension(f'cogs.{filename[:-3]}')


@bot.event
async def on_ready():
    try:
        # Server-IDs aus den Umgebungsvariablen lesen
        main_server_id = os.getenv('server_id')
        emoji_server_id = os.getenv('emoji_server_id')

        if main_server_id is None or emoji_server_id is None:
            print("Eine oder beide Server-IDs wurden nicht gefunden. Bitte stelle sicher, dass die Environment-Variablen 'server_id' und 'emoji_server_id' gesetzt sind.")
            return

        # Emoji-Laden für den Hauptserver
        main_guild = bot.get_guild(int(main_server_id))
        if main_guild is None:
            main_guild = await bot.fetch_guild(int(main_server_id))
        if main_guild:
            emojis_data = {}
            for emoji in main_guild.emojis:
                emojis_data[emoji.name] = {
                    "id": emoji.id,
                    "animated": emoji.animated,
                    "syntax": f"{'<a:' if emoji.animated else '<:'}{emoji.name}:{emoji.id}>"
                }

            # Speichern in JSON-Datei im data-Ordner
            os.makedirs("data", exist_ok=True)
            with open("data/emojis.json", "w", encoding="utf-8") as f:
                json.dump(emojis_data, f, indent=4, ensure_ascii=False)

            print(
                "Emoji-Liste vom Hauptserver wurde erfolgreich in 'data/emojis.json' gespeichert.")

        # Emoji-Laden für den Emoji-Server
        emoji_guild = bot.get_guild(int(emoji_server_id))
        if emoji_guild is None:
            emoji_guild = await bot.fetch_guild(int(emoji_server_id))
        if emoji_guild:
            emojis_extension_data = {}
            for emoji in emoji_guild.emojis:
                emojis_extension_data[emoji.name] = {
                    "id": emoji.id,
                    "animated": emoji.animated,
                    "syntax": f"{'<a:' if emoji.animated else '<:'}{emoji.name}:{emoji.id}>"
                }

            # Speichern in separater JSON-Datei
            with open("data/emojis_extension_01.json", "w", encoding="utf-8") as f:
                json.dump(emojis_extension_data, f,
                          indent=4, ensure_ascii=False)

            print(
                "Emoji-Liste vom Emoji-Server wurde erfolgreich in 'data/emojis_extension_01.json' gespeichert.")

        # Synchronisiere die Befehle
        guild = discord.Object(id=int(main_server_id))

        # **Globale Befehle löschen**
        await bot.tree.clear_commands(guild=None)
        await bot.tree.sync(guild=None)
        print('Globale Befehle wurden gelöscht.')

        # **Guild-spezifische Befehle synchronisieren**
        await bot.tree.sync(guild=guild)
        print(f'Befehle wurden für den Server {
              main_server_id} synchronisiert.')

        print(f'Bot ist online als {
              bot.user} und mit dem Server synchronisiert.')

    except Exception as e:
        print(f"Ein Fehler ist im on_ready Event aufgetreten: {e}")
        import traceback
        traceback.print_exc()


# Statt asyncio.run(main()), direkt bot.run() verwenden
if __name__ == '__main__':
    # Lies den Token aus der Environment-Variable
    bot_token = os.getenv('bot_key')
    if bot_token is None:
        print("Bot Token nicht gefunden. Stelle sicher, dass die Environment-Variable 'bot_key' gesetzt ist.")
    else:
        bot.loop.create_task(load_cogs())
        bot.run(bot_token)
