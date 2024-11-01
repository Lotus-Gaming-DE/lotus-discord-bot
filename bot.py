# bot.py
import discord
from discord.ext import commands
import os
import json
import logging

# Setze das Logging-Level und das Format
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(levelname)s:%(name)s: %(message)s')

# Logger für dein Bot-Modul
logger = logging.getLogger('bot')

intents = discord.Intents.default()
intents.message_content = True  # Notwendig für den quiz_cog
intents.guilds = True  # Notwendig für Guild-Events und Befehle


class MyBot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(command_prefix='§', intents=intents, **kwargs)
        # Server-ID aus der Umgebungsvariablen lesen
        self.main_server_id = os.getenv('server_id')

        if self.main_server_id is None:
            logger.error(
                "Die Environment-Variable 'server_id' wurde nicht gefunden. Bitte stelle sicher, dass sie gesetzt ist.")
            exit(1)

    async def setup_hook(self):
        # Lade deine Cogs hier
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                await self.load_extension(f'cogs.{filename[:-3]}')
            elif os.path.isdir(os.path.join('./cogs', filename)):
                # Falls der Cog in einem Unterverzeichnis ist
                await self.load_extension(f'cogs.{filename}')

        # Emojis laden und Befehle synchronisieren
        await self.load_emojis_and_sync_commands()

        # Synchronisiere die Befehle für den Hauptserver
        try:
            guild = discord.Object(id=int(self.main_server_id))
            await self.tree.sync(guild=guild)
            logger.info(
                f'Slash-Befehle wurden für den Server {self.main_server_id} synchronisiert.')
        except Exception as e:
            logger.error(
                f"Fehler beim Synchronisieren der Slash-Befehle: {e}", exc_info=True)

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

                logger.info(
                    "Emoji-Liste vom Hauptserver wurde erfolgreich in 'data/emojis.json' gespeichert.")
            else:
                logger.warning(f"Hauptserver mit ID {
                               self.main_server_id} nicht gefunden.")

            # Synchronisiere die Befehle
            guild = discord.Object(id=int(self.main_server_id))

            # **Globale Befehle löschen**
            self.tree.clear_commands(guild=None)
            await self.tree.sync(guild=None)
            logger.info('Globale Befehle wurden gelöscht.')

            # **Guild-spezifische Befehle synchronisieren**
            await self.tree.sync(guild=guild)
            logger.info(f'Befehle wurden für den Server {
                        self.main_server_id} synchronisiert.')

        except Exception as e:
            logger.error(f"Ein Fehler ist beim Laden der Emojis und Synchronisieren der Befehle aufgetreten: {
                         e}", exc_info=True)

    async def on_ready(self):
        logger.info(f'Bot ist online als {self.user}.')

    async def on_message(self, message):
        # Verhindere, dass der Bot versucht, Präfixbefehle zu verarbeiten
        if message.author.bot:
            return  # Ignoriere Nachrichten von Bots

        # Lasse andere Cogs (wie quiz_cog) das on_message-Event verarbeiten
        await self.invoke_cog_message_listeners(message)

    async def invoke_cog_message_listeners(self, message):
        """Hilfsfunktion, um on_message-Events an Cogs weiterzugeben."""
        for cog in self.cogs.values():
            if hasattr(cog, 'on_message'):
                await cog.on_message(message)


if __name__ == '__main__':
    # Lies den Token aus der Environment-Variable
    bot_token = os.getenv('bot_key')
    if bot_token is None:
        logger.error(
            "Bot Token nicht gefunden. Stelle sicher, dass die Environment-Variable 'bot_key' gesetzt ist.")
    else:
        bot = MyBot()
        bot.run(bot_token)
