# Lotus Discord Bot

Lotus Gaming's community bot built with [discord.py](https://discordpy.readthedocs.io/).

## Setup

1. Install Python **3.11**.
2. Install runtime dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install development tools and pre-commit hooks:
   ```bash
   pip install -r requirements-dev.txt
   pre-commit install
   ```
4. Copy `.env.example` to `.env` and adjust the values.

## Usage

Run the bot locally:

```bash
python -m lotus_bot
```

## Utility Scripts

Synchronise or inspect data via the provided CLI tools:

- `scripts/fetch_wcr.py` – fetches Warcraft Rumble data and prints the number of units.
  ```bash
  python scripts/fetch_wcr.py --help
  ```

## Development

Source code lives in `src/lotus_bot/` while tests reside in `tests/`.
Before committing code run:

```bash
pre-commit run --all-files
pytest --cov=. --cov-fail-under=90
```

`pre-commit` handles formatting, linting and `pip-audit`. Security scans also
run in CI via Snyk when `SNYK_TOKEN` is configured.
Dependabot checks dependencies daily and opens pull requests that run the full
CI pipeline.

## Deployment

The bot is deployed on Railway. Logs are written to files named
`logs/runtime-<YYYY-MM-DD-HH>.json` and CI uploads
`logs/latest_railway.log` as an artifact. Internal log messages are in English
while user-facing messages are in German.

All environment variables are documented in `.env.example` and supplied via
Railway.

CI jobs access Railway via the CLI. They expect `RAILWAY_TOKEN` to be defined as
 a secret and the variables `RAILWAY_PROJECT` and `RAILWAY_SERVICE` to be
 available at the repository or organisation level.
