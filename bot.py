import discord
from discord.ext import commands, tasks
import asyncio
import random
import json  # Für das Arbeiten mit JSON-Dateien

SCORES_FILE = 'scores.json'  # Dateiname für die Punkte

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Fragen nach Bereichen organisiert
questions_by_area = {
    'warcraft_rumble': [
        {'frage': 'Wer ist der Hauptantagonist in Warcraft Rumble?',
            'antwort': 'Morton der Unbezwingbare'},
        # Weitere Fragen hinzufügen
    ],
    'diablo': [
        {'frage': 'Wie heißt der Endgegner in Diablo III?', 'antwort': 'Diablo'},
        # Weitere Fragen hinzufügen
    ],
    # Weitere Bereiche hinzufügen
}

# Konfiguration der Bereiche
areas_config = {
    'warcraft_rumble': {
        # Ersetze durch die Kanal-ID für Warcraft Rumble
        'channel_id': 123456789012345678,
        'interval_hours': 2,  # Intervall in Stunden
    },
    'diablo': {
        'channel_id': 987654321098765432,  # Ersetze durch die Kanal-ID für Diablo
        'interval_hours': 3,
    },
    # Weitere Bereiche hinzufügen
}

# Lade die Benutzerpunkte aus der Datei
try:
    with open(SCORES_FILE, 'r') as f:
        user_scores = json.load(f)
        # Konvertiere die Schlüssel von Strings zu Integers
        user_scores = {int(k): v for k, v in user_scores.items()}
except FileNotFoundError:
    user_scores = {}


def save_scores():
    with open(SCORES_FILE, 'w') as f:
        json.dump(user_scores, f)


@bot.event
async def on_ready():
    print(f'Bot ist online als {bot.user}')
    # Starte die Tasks für alle Bereiche
    for area in areas_config:
        start_quiz_task(area)


def start_quiz_task(area):
    config = areas_config[area]
    interval = config['interval_hours']

    @tasks.loop(hours=interval)
    async def quiz_loop():
        await run_quiz(area)

    @quiz_loop.before_loop
    async def before_quiz():
        await bot.wait_until_ready()

    quiz_loop.start()


async def run_quiz(area):
    config = areas_config[area]
    channel = bot.get_channel(config['channel_id'])
    if channel is None:
        print(f"Konnte Kanal mit ID {config['channel_id']} nicht finden.")
        return

    questions = questions_by_area[area]
    frage = random.choice(questions)
    question_message = await channel.send(frage['frage'])

    def check(m):
        return (
            m.channel == channel and
            m.author != bot.user and
            m.reference and
            m.reference.message_id == question_message.id
        )

    while True:
        try:
            antwort = await bot.wait_for('message', timeout=60.0, check=check)
            if antwort.content.strip().lower() == frage['antwort'].strip().lower():
                await channel.send(f'Richtig, {antwort.author.mention}!')
                user_id = antwort.author.id
                user_scores[user_id] = user_scores.get(user_id, 0) + 1
                save_scores()  # Speichere die Punkte nach der Änderung
                break
            else:
                await channel.send(f'Leider falsch, {antwort.author.mention}. Versuche es erneut!')
        except asyncio.TimeoutError:
            await channel.send('Zeit abgelaufen! Keine korrekte Antwort wurde gegeben.')
            break


@bot.command()
async def punkte(ctx):
    user_id = ctx.author.id
    score = user_scores.get(user_id, 0)
    await ctx.send(f'Du hast insgesamt {score} Punkt(e), {ctx.author.name}.')


@bot.command()
async def rangliste(ctx):
    sorted_scores = sorted(user_scores.items(),
                           key=lambda x: x[1], reverse=True)
    message = '🏆 **Rangliste:**\n'
    for user_id, score in sorted_scores[:10]:  # Top 10
        user = await bot.fetch_user(user_id)
        message += f'{user.name}: {score} Punkt(e)\n'
    await ctx.send(message)

bot.run('MTI5MDc4NTg3OTM5MjI2MDE3OA.GhJmct.m81o4hzI2Dw9lNJ2hzVPaQStp6sVD_Yzpjq4A4')
