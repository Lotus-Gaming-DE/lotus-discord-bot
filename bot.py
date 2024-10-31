import discord
from discord.ext import commands
import os
import json

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True  # Stelle sicher, dass die Guilds-Intents aktiviert sind


class MyBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Server-IDs aus den Umgebungsvariablen lesen
        self.main_server_id = os.getenv('server_id')
        self.emoji_server_id = os.getenv('emoji_server_id')

        if self.main_server_id is None or self.emoji_server_id is None:
            print("Eine oder beide Server-IDs wurden nicht gefunden. Bitte stelle sicher, dass die Environment-Variablen 'server_id' und 'emoji_server_id' gesetzt sind.")
            exit(1)

    async def setup_hook(self):
        # Lade deine Cogs hier
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')

        # Emoji-Laden und Befehle synchronisieren
        await self.load_emojis_and_sync_commands()

    async def load_emojis_and_sync_commands(self):
        try:
            # Emoji-Laden für den Hauptserver
            main_guild = self.get_guild(int(self.main_server_id))
            if main_guild is None:
                main_guild = await self.fetch_guild(int(self.main_server_id))
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
            emoji_guild = self.get_guild(int(self.emoji_server_id))
            if emoji_guild is None:
                emoji_guild = await self.fetch_guild(int(self.emoji_server_id))
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
            guild = discord.Object(id=int(self.main_server_id))

            # **Globale Befehle löschen**
            await self.tree.clear_commands(guild=None)
            await self.tree.sync(guild=None)
            print('Globale Befehle wurden gelöscht.')

            # **Guild-spezifische Befehle synchronisieren**
            await self.tree.sync(guild=guild)
            print(f'Befehle wurden für den Server {
                  self.main_server_id} synchronisiert.')

        except Exception as e:
            print(
                f"Ein Fehler ist beim Laden der Emojis und Synchronisieren der Befehle aufgetreten: {e}")
            import traceback
            traceback.print_exc()

    async def on_ready(self):
        print(f'Bot ist online als {self.user}.')


if __name__ == '__main__':
    # Lies den Token aus der Environment-Variable
    bot_token = os.getenv('bot_key')
    if bot_token is None:
        print("Bot Token nicht gefunden. Stelle sicher, dass die Environment-Variable 'bot_key' gesetzt ist.")
    else:
        bot = MyBot(command_prefix="", intents=intents)
        bot.run(bot_token)
