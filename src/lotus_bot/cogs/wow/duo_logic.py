"""Pure, Discord-free helpers for the WoW-Duo (level-partner) feature.

Kept separate from :mod:`duo_cog` so the matching maths, time-window encoding
and team-name pool can be unit-tested without a running bot. Nothing in here
touches SQLite or discord.py.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Iterable

# Coarse play-time windows. Deliberately few and fuzzy so casual players can
# pick "when do I usually play" in a single multi-select instead of fiddling
# with clock times. Order here is the canonical display/storage order.
TIME_WINDOWS: dict[str, str] = {
    "wd_vormittag": "Werktags vormittags",
    "wd_nachmittag": "Werktags nachmittags",
    "wd_abend": "Werktags abends",
    "we_tag": "Wochenende tagsüber",
    "we_abend": "Wochenende abends",
    "spaet": "Spätabends & Nachts",
}

# Curated pool of duo team names. On match the bot proposes a random unused
# one; members can rename. Kept WoW/Horde-flavoured and short so they read
# well as a forum-post title ("🤝 Team Aschefaust").
TEAM_NAME_POOL: list[str] = [
    "Team Phoenix",
    "Team Aschefaust",
    "Team Nachtklinge",
    "Team Blutmond",
    "Team Wolfsrudel",
    "Team Donnerhuf",
    "Team Schattenpfad",
    "Team Eisenwolf",
    "Team Grimmzahn",
    "Team Sturmwind",
    "Team Kriegsherz",
    "Team Rabenschwinge",
    "Team Glutkern",
    "Team Frostbiss",
    "Team Wildherz",
    "Team Silberklaue",
    "Team Drachenblut",
    "Team Dornenritter",
    "Team Mondschatten",
    "Team Feuersturm",
    "Team Steinfaust",
    "Team Geisterwolf",
    "Team Schwarzdorn",
    "Team Bluteiche",
    "Team Wüstenwind",
    "Team Nebelgänger",
    "Team Flammenzunge",
    "Team Eisenherz",
    "Team Schädelbrecher",
    "Team Klingenwirbel",
]


def encode_windows(keys: Iterable[str]) -> str:
    """Serialise selected window keys to a canonical, comma-separated string.

    Invalid keys are dropped, duplicates collapsed, and the result is ordered
    to match :data:`TIME_WINDOWS` so equality/round-trips are stable.
    """
    selected = {k for k in keys if k in TIME_WINDOWS}
    return ",".join(key for key in TIME_WINDOWS if key in selected)


def decode_windows(raw: str | None) -> list[str]:
    """Parse a stored window string back into canonical-ordered valid keys."""
    if not raw:
        return []
    parts = {part.strip() for part in raw.split(",") if part.strip()}
    return [key for key in TIME_WINDOWS if key in parts]


def window_labels(keys: Iterable[str]) -> list[str]:
    """Human-readable labels for the given window keys, canonical order."""
    key_set = {k for k in keys if k in TIME_WINDOWS}
    return [label for key, label in TIME_WINDOWS.items() if key in key_set]


def format_windows(keys: Iterable[str]) -> str:
    """Comma-joined labels, or a dash when nothing is set."""
    labels = window_labels(keys)
    return ", ".join(labels) if labels else "—"


def overlap_keys(a: Iterable[str], b: Iterable[str]) -> list[str]:
    """Shared window keys between two selections, canonical order."""
    set_a = {k for k in a if k in TIME_WINDOWS}
    set_b = {k for k in b if k in TIME_WINDOWS}
    shared = set_a & set_b
    return [key for key in TIME_WINDOWS if key in shared]


@dataclass
class Candidate:
    """A potential partner ranked against the searching user."""

    discord_user_id: int
    character_name: str
    level: int
    windows: list[str]
    overlap: list[str]
    level_distance: int

    @property
    def overlap_count(self) -> int:
        return len(self.overlap)


def rank_candidates(
    my_windows: Iterable[str],
    my_level: int,
    others: Iterable[tuple[int, str, int, list[str]]],
) -> list[Candidate]:
    """Rank open signups against the searcher.

    ``others`` items are ``(discord_user_id, character_name, level, windows)``.
    Best first: most time-window overlap, then smallest level distance, then
    name for a stable tie-break. Candidates with zero overlap are still
    returned (so a lonely searcher always sees *someone*) but sort last.
    """
    my_window_list = [k for k in my_windows if k in TIME_WINDOWS]
    ranked: list[Candidate] = []
    for user_id, name, level, windows in others:
        shared = overlap_keys(my_window_list, windows)
        ranked.append(
            Candidate(
                discord_user_id=user_id,
                character_name=name,
                level=level,
                windows=[k for k in windows if k in TIME_WINDOWS],
                overlap=shared,
                level_distance=abs(int(level) - int(my_level)),
            )
        )
    ranked.sort(
        key=lambda c: (-c.overlap_count, c.level_distance, c.character_name.casefold())
    )
    return ranked


def pick_team_name(used: Iterable[str], rng: random.Random | None = None) -> str:
    """Return a team name not already in ``used``.

    Picks randomly from the free names in the pool. If every pooled name is
    taken, falls back to numbered variants ("Team Phoenix 2", …) so team
    creation can never fail for lack of a name.
    """
    rng = rng or random
    used_set = {name.casefold() for name in used}
    free = [name for name in TEAM_NAME_POOL if name.casefold() not in used_set]
    if free:
        return rng.choice(free)
    base = rng.choice(TEAM_NAME_POOL)
    suffix = 2
    while f"{base} {suffix}".casefold() in used_set:
        suffix += 1
    return f"{base} {suffix}"
