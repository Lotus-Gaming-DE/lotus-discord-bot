# AGENTS.md

Guidelines for AI agents (Claude, Codex, etc.) working on this project. The only readers are AI sessions: keep this file dense and current, and fix a stale line when you notice it.

## Project Overview

Discord bot of the Lotus Gaming community (guild "Black Lotus"). Python 3.13, discord.py 2.x, SQLite (aiosqlite) under `data/pers/`, hosted on Railway. Written entirely by AI agents; the operator (gs3rr4) does not code, speaks German and often reads replies on the phone: answer in short German.

**Current focus: WoW Forever** (launched 04.11.2026, a Retail-based client with Classic-era content). The Classic Hardcore guild on Soulseeker is on hold; its features stay in the code but several are switched off (see "Switches").

Related repositories (separate, do not edit from here): `lotus-wow-addons` (in-game addons, incl. LotusDiscordBridge whose export the WoW cog imports) and `lotus-link` (central group finder bot for Forever).

## Repository Layout

```
src/lotus_bot/
  bot.py                Entry point: loads central data, registers cogs, syncs guild commands
  backup.py             Backup of everything in data/pers
  permissions.py        Owner-only command check
  utils/                ManagedTaskCog (tracks background tasks), setup helpers, ephemeral replies
  cogs/
    wow/                WoW hub: roster sync, claims, daily digest, champion points,
                        hub panels (cog.py), Forever guild roles + interest panel
                        (forever_panel.py, forever_roles.py), WoW-Duo level partners
                        (duo_*.py), marketplace forum (marketplace_*.py)
    community/          Server-wide info panel in #infos-und-regeln
    champion/           Points and champion roles (data/champion/roles.json)
    quiz/               Quiz (WoW + WCR questions, duels, scheduler)
    wcr/                Warcraft Rumble
    ptcgp/              Pokémon TCG Pocket
    backup/             Daily backup, weekly also to Discord
    dev/                Owner-only helper commands
data/
  wow/classic_hc/       Static Classic HC data (items.json, instance_drops.json, …)
  quiz/                 Questions and templates
  pers/                 Persistent databases (gitignored)
tests/                  pytest, mirrors src/
scripts/                Utility scripts (WoW data import/audit, WCR fetch, …)
wow_crystal_work/       Local scratch, gitignored, not part of the bot
```

## Conventions

- All slash commands are guild-scoped (`guild=bot.main_guild`); `setup_hook` clears global commands. No global commands.
- Channel, role and message IDs are module constants in the cog (e.g. `DEFAULT_PANEL_CHANNEL_ID`), not env vars.
- Panels follow the "find own message, edit or repost" pattern; message/thread IDs are stored in the cog's settings store.
- Background work goes through `ManagedTaskCog.create_task` so unload/shutdown stops it.
- Code, comments and logs in English; user-facing text in German.
- Only delete Discord messages/threads the bot created and tracks itself.

## Switches (module constants)

| Constant | File | State | Why |
|---|---|---|---|
| `CLASSIC_PANEL_ENABLED` | `cogs/wow/cog.py` | False | Classic HC guild on hold since the Forever launch |
| `DUNGEONS_GUIDE_ENABLED` | `cogs/wow/cog.py` | False | A separate dungeon bot handles dungeon runs (04.11.2026) |
| `MARKETPLACE_HUB_ENABLED` | `cogs/wow/marketplace_cog.py` | False | Market hub post switched off (04.11.2026) |
| `PANEL_LAYOUT` | `cogs/wow/cog.py` | "three-panels-v3" | Bump the string to make the bot delete and repost all hub panels once |

When off, the feature removes its own existing post once. Record a new switch or decision in this table with its reason.

## Definition of Done — MANDATORY before reporting work as complete

The operator merges through GitHub Desktop and cannot fix CI failures. Every red CI run means another agent round trip. Run locally, every time:

```
python -m black src/ tests/ scripts/
python -m black --check src/ tests/ scripts/   # must report 0 changes
python -m pytest -q                            # must be all green
pre-commit run --all-files                     # EOL/whitespace/YAML hooks, ruff, pip-audit
```

Black is pinned (see `.pre-commit-config.yaml`). CI runs pre-commit with `--all-files`, so it flags old files too; fix them in your commit. If `black` reformats anything, include it. If a test fails because you intentionally changed behaviour, update the test to the new intent.

**Tests encode guarantees, not wording:**

- ❌ `assert "Folgende seltene Rezepte" in msg`
- ✅ `assert event.points == 3`
- ✅ `assert "Voidok" in msg and "Level **40**" in msg` (structural facts)

Tests must close every aiosqlite connection they open; an open one keeps pytest alive after the summary and hangs CI.

**Windows:** never pass `--basetemp=C:\...` through Bash (backslashes get eaten).

## Environment Variables

Full list in `.env.example`. Key ones: `bot_key` (Discord token), `server_id` (guild ID), `BLIZZARD_CLIENT_ID` / `BLIZZARD_CLIENT_SECRET`, `WCR_API_URL`, `LOG_LEVEL`. CI uses `RAILWAY_TOKEN` (secret) plus `RAILWAY_PROJECT` / `RAILWAY_SERVICE` (repository variables).

## Hosting and CI

Railway hosts the bot; env vars live in the Railway dashboard. Logs: `logs/runtime-<YYYY-MM-DD-HH>.json`, `railway logs`, or the artifact of the `railway_logs` workflow. Dependabot opens dependency PRs; minor/patch groups are merged automatically once "Run tests" succeeds (`dependabot-auto-merge.yml`).

## WoW Notes

- Classic Era 1x namespace: `profile-classic1x-eu`. `/professions` and `/reputations` return 404 there.
- Item levels come from `data/wow/classic_hc/items.json`; the equipment API returns none.
- Daily digest posts at 09:00 Europe/Berlin.
- WoW Forever API facts are measured in `lotus-link/docs/forever-api.md`; do not assume Classic or Retail behaviour.

## Git

- Work on a branch, never directly on `main`. Ask before pushing, opening a PR or merging.
- End commit messages with the attribution line the session provides.
