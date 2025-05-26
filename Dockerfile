# 1) Basis-Image mit Python 3.12
FROM python:3.12-slim

# 2) Arbeitsverzeichnis im Container
WORKDIR /app

# 3) Abhängigkeiten installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4) Deinen Bot-Code kopieren
COPY . .

# 5) Kommando, das beim Start ausgeführt wird
CMD ["python", "bot.py"]
