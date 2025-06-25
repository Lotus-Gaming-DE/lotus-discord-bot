# Lotus Discord Bot

This project contains the source code for Lotus Gaming's community bot.
It is developed using the [discord.py](https://discordpy.readthedocs.io/) library.

## Quick start

1. Install Python 3.11.
2. Install the runtime dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Install development tools:
   ```bash
   pip install -r requirements-dev.txt
   pre-commit install
   ```
4. Copy `.env.example` to `.env` and adjust the values.
5. Run the bot:
   ```bash
   python -m lotus_bot
   ```

## Development

All source code lives under `src/lotus_bot/` using the src layout.  Tests
reside in the `tests/` directory and are executed with `pytest`.

The project uses `pre-commit` to enforce formatting and linting
(Black, Flake8, Ruff and pip-audit).  Security scans run automatically in
CI using Snyk if the `SNYK_TOKEN` secret is configured.

## Dependency management

Dependabot checks the `requirements*.txt` files and GitHub Actions
workflows weekly. It opens pull requests which trigger the full CI
pipeline, ensuring updates are tested before merge.

```bash
pre-commit run --all-files
pytest -q
```

## Deployment

The bot runs on Railway. Logs are written to `logs/bot.json` in JSON
format using structlog.  CI uploads the latest Railway logs as build
artifacts.
