# AGENTS.md

Guidelines for AI agents (Claude, Codex, etc.) working on this project.

## Project Overview

Discord bot for the WoW Classic Hardcore guild "Black Lotus" on EU server Soulseeker.
Written entirely by AI agents — no human writes code directly.
Hosted on Railway. Python 3.13, discord.py 2.x.

## Repository Layout

```
src/lotus_bot/          Main bot package
  bot.py                Entry point, loads cogs
  cogs/
    wow/                WoW Classic cog — roster sync, daily digest, champion points
    quiz/               Quiz system — WoW + WCR questions, duels, scheduler
    champion/           Points leaderboard
    wcr/                Warcraft Rumble cog
    ptcgp/              Pokémon TCG Pocket cog
data/
  wow/classic_hc/       Static WoW data (items.json, instance_drops.json, …)
  quiz/templates/       Question templates (wow.json, wcr.json)
tests/                  pytest test suite — mirrors src/ structure
scripts/                One-off utility scripts (WoW data import, etc.)
```

## Code Conventions

- Python 3.13, async/await throughout
- All slash commands are guild-scoped: `bot.tree.add_command(..., guild=bot.main_guild)` + sync
- Persistent data goes in `data/pers/` (gitignored)
- Logs go in `logs/` (gitignored)
- No global slash commands

## Tooling

- Formatter: **black 26.3.1** — pinned, must match `.pre-commit-config.yaml`
- Linter: **ruff** — configured in `pyproject.toml`
- Tests: `pytest` — run from project root
- Pre-commit: all hooks defined in `.pre-commit-config.yaml`

## Definition of Done — MANDATORY before reporting work as complete

The user (gs3rr4) does **not** code and pushes via GitHub Desktop. They cannot fix CI failures themselves. Every red CI run = back to an agent = wasted tokens. So:

**Run these locally before saying "done" — every time, no exceptions:**

```
python -m black src/ tests/ scripts/
python -m black --check src/ tests/ scripts/   # must report 0 changes
python -m pytest -q                            # must be all green
```

If `black` reformats anything, those changes are part of your work — include them.
If a test fails because **you intentionally changed behavior**, update the test to match the new intent. Don't push and hope.

**Writing new tests — avoid brittle assertions:**

- ❌ `assert "Folgende seltene Rezepte" in msg` — breaks on any copy tweak
- ❌ `assert "Level **37** gestorben" in line` — breaks on any wording change
- ✅ `assert event.points == 3` — encodes a real design decision
- ✅ `assert "Voidok" in msg and "Level **40**" in msg` — structural facts

Test what the code is *supposed to guarantee*, not the exact German wording. Copy gets tweaked all the time; behaviour shouldn't break tests.

**Temp paths on Windows:** never pass `--basetemp=C:\...` through Bash — the backslashes get eaten and pytest creates a `C__...` directory inside the repo. Use forward slashes or omit the flag.

## Environment Variables

See `.env.example` for the full list. Key vars:
- `DISCORD_TOKEN` — bot token
- `server_id` — Discord guild ID
- `BLIZZARD_CLIENT_ID` / `BLIZZARD_CLIENT_SECRET` — Battle.net API
- `RAILWAY_TOKEN` — Railway deployment

## Hosting

- Deployed on Railway (production)
- Env vars managed via Railway dashboard or CLI
- Logs accessible via `railway logs` or GitHub Actions artifacts

## WoW Cog Notes

- Classic Era 1x namespace: `profile-classic1x-eu`
- The `/professions` and `/reputations` Blizzard API endpoints return 404 for Classic Era 1x
- Item levels are resolved via a local lookup (data/wow/classic_hc/items.json) — the equipment API does not return iLvl
- Daily digest posts at 09:00 Europe/Berlin time
