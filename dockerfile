# ─── Basis‐Image ───────────────────────────────────────────────────────────
FROM python:3.12-slim

# ─── Arbeitsverzeichnis setzen ──────────────────────────────────────────────
WORKDIR /app

# ─── requirements.txt kopieren und installieren ─────────────────────────────
COPY requirements.txt .

# Installiere immer die jeweils aktuelle Version von discord.py & Unidecode
RUN pip install --no-cache-dir -r requirements.txt

# ─── gesamten Bot‐Code kopieren ───────────────────────────────────────────────
COPY . .

# ─── Standard‐Port (wird von Cloud Run verwendet) ────────────────────────────
# Falls du keinen eigenen Health‐Check‐Server im Bot hast, lauscht Cloud Run automatisch
# auf den PORT (z. B. 8080), aber bei einem Discord‐Bot ist das meist nicht nötig.
# Wir überlassen Cloud Run die Wahl. Viele Bot‐Beispiele öffnen gar keinen HTTP‐Port.
# Dennoch setzen wir hier den PORT‐Env für den Fall, dass du später Health‐Checks einbaust.
ENV PORT=8080

# ─── Entry‐Point: Starte deinen Bot mit python bot.py ────────────────────────
CMD ["python", "bot.py"]
