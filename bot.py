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
        # Server-ID aus der Umgebungsvariablen lesen
        self.main_server_id = os.getenv('server_id')

        if self.main_server_id is None:
            print("Die Environment-Variable 'server_id' wurde nicht gefunden. Bitte stelle sicher, dass sie gesetzt ist.")
            exit(1)

    async def setup_hook(self):
        # Lade deine Cogs hier
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')

        # Emojis laden und Befehle synchronisieren
        await self.load_emojis_and_sync_commands()

    async def load_emojis_and_sync_commands(self):
        try:
            # Emojis vom Hauptserver laden
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
            else:
                print(f"Hauptserver mit ID {
                      self.main_server_id} nicht gefunden.")

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
