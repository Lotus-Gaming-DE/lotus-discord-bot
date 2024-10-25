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
        {'frage': 'Welche Einheit wird oft als „Tank“ bezeichnet?', 'antwort': 'Golem'},
        {'frage': 'In welchem Gebiet kämpft man gegen Hogger?',
            'antwort': 'Elwynn Forest'},
        {'frage': 'Welche Talentwahl wird im PvP oft für die Banshee genutzt?',
            'antwort': 'Will of the Necropolis'},
        {'frage': 'Wie heißt der Anführer der Skeletteinheiten?',
            'antwort': 'Baron Rivendare'},
        {'frage': 'Welche Einheit kann die Fähigkeit „Blizzard“ nutzen?',
            'antwort': 'Frostmage'},
        {'frage': 'Welcher Talentpunkt wird oft im PvE für „Flammendes Fass“ gewählt?',
            'antwort': 'Enchanted Vials'},
        {'frage': 'Welche Einheit ist bekannt für „Snackrifice“?',
            'antwort': 'Angry Chickens'},
        {'frage': 'Welche Einheit kann sich in eine „Schutzkiste“ verwandeln?',
            'antwort': 'Walking Crate'},
        {'frage': 'Wer ist der Anführer im Gebiet „Stranglethorn Vale“?',
            'antwort': 'King Mukla'},
        {'frage': 'Welche Einheit nutzt die Fähigkeit „Lavawelle“?',
            'antwort': 'Lava Elemental'},
        {'frage': 'Welche Einheit hat die Fähigkeit „Seelenexplosion“?',
            'antwort': 'Banshee'},
        {'frage': 'Wie heißt das Talent, das Skeletten „Blutrausch“ verleiht?',
            'antwort': 'Skeletal Frenzy'},
        {'frage': 'Welche Einheit ist im PvP als „Support-Einheit“ beliebt?',
            'antwort': 'Blizzard Frostmage'},
        {'frage': 'Wie heißt das Gebiet, in dem Gazlowe als Gegner vorkommt?',
            'antwort': 'The Barrens'},
        {'frage': 'Welche Kreatur kann durch „Polymorph“ verwandelt werden?',
            'antwort': 'Schafe'},
        {'frage': 'Welche Einheit setzt auf das Talent „Feuriger Überschuss“?',
            'antwort': 'Bat Rider'},
        {'frage': 'Welche Einheit ist besonders gegen Gargoyles effektiv?',
            'antwort': 'Banshee'},
        {'frage': 'Wie heißt die Eliteeinheit, die in „Westfall“ gefunden wird?',
            'antwort': 'Marshal Redpaw'},
        {'frage': 'Wer ist der berühmte Schurke im Gebiet „Duskwood“?',
            'antwort': 'Morbent Fel'},
    ],
    'diablo_iv': [
        {'frage': 'Wer ist der Hauptantagonist in Diablo IV?', 'antwort': 'Lilith'},
        {'frage': 'Welche Klasse kann als Werwolf kämpfen?', 'antwort': 'Druide'},
        {'frage': 'In welcher Zone steht der „Altar von Lilith“?',
            'antwort': 'Sanctuary'},
        {'frage': 'Welche Klasse beschwört Skelette?', 'antwort': 'Totenbeschwörer'},
        {'frage': 'Wie viele Hauptakte hat Diablo IV?', 'antwort': 'Fünf'},
        {'frage': 'Welche Klasse verwendet Elementarmagie?', 'antwort': 'Zauberin'},
        {'frage': 'Welche Kreatur ist Liliths Vater?', 'antwort': 'Mephisto'},
        {'frage': 'In welchem Jahr erschien Diablo IV?', 'antwort': '2023'},
        {'frage': 'Welche Klasse benutzt das „Blut“-Skill-Set?',
            'antwort': 'Totenbeschwörer'},
        {'frage': 'Wie heißt die Stadt, die als Hauptquartier dient?',
            'antwort': 'Kyovashad'},
        {'frage': 'Wer ist der Erzengel des Mutes?', 'antwort': 'Imperius'},
        {'frage': 'Welche Klasse benutzt Bogen und Fallen?', 'antwort': 'Jägerin'},
        {'frage': 'Wie nennt sich das saisonale Event in Diablo IV Saison 2?',
            'antwort': 'Blutsaison'},
        {'frage': 'Wie lautet Liliths Beziehung zu Inarius?', 'antwort': 'Geliebte'},
        {'frage': 'Welche Klasse besitzt die Fähigkeit „Blitzkette“?',
            'antwort': 'Zauberin'},
        {'frage': 'Welches Land ist von Festungen umgeben?', 'antwort': 'Kehjistan'},
        {'frage': 'Wer zerstörte den Schwarzen Seelenstein?', 'antwort': 'Malthael'},
        {'frage': 'Welche Klasse kann ein Wolf begleiten?', 'antwort': 'Druide'},
        {'frage': 'Wie nennt man die Schatzkiste-Events im Spiel?',
            'antwort': 'Höllenflut'},
        {'frage': 'Welches Symbol repräsentiert Lilith?',
            'antwort': 'Schlangensymbol'},
    ],
    # Weitere Bereiche hinzufügen
}


# Konfiguration der Bereiche
areas_config = {
    'warcraft_rumble': {
        # Ersetze durch die Kanal-ID für Warcraft Rumble
        'channel_id': 1290804058281607189,
        'interval_hours': 0.1,  # Intervall in Stunden
    },
    'diablo': {
        'channel_id': 1290804058281607189,  # Ersetze durch die Kanal-ID für Diablo
        'interval_hours': 0.1,
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
