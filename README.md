# Lotus Discord Bot

Lotus Gaming's community bot built with
[discord.py](https://discordpy.readthedocs.io/).

## Setup

1. Install Python **3.11**.
2. Install the runtime dependencies:
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

## Development

Source code lives under `src/lotus_bot/` while tests reside in `tests/`.
Run the following commands before committing code:

```bash
pre-commit run --all-files
pytest --cov=.
```

`pre-commit` enforces formatting and linting (Black, Flake8, Ruff) and
executes `pip-audit`. Security scans also run in CI via Snyk when
`SNYK_TOKEN` is configured. The Snyk step only runs for pull requests
originating from this repository, preventing failures on forks where
secrets are unavailable.

Dependabot checks dependencies daily and opens pull requests that run the
full CI pipeline.

## Deployment

The bot is deployed on Railway. Logs are written to `logs/bot.json` in
JSON format using structlog. Internal log messages are in English while
user-facing messages are German. CI uploads the latest Railway logs as
build artifacts.

Environment variables such as `bot_key` and `server_id` are provided via
Railway. The `.env.example` file lists all required values.
