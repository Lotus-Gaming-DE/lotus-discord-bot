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

# How much time per session — the "how long" the windows can't express.
# "Jeden Abend 1h" and "nur mittwochs 5h" both pick "Werktags abends" but are
# very different partners, so this is a required single-choice.
INTENSITY: dict[str, str] = {
    "chill": "Chillig · so 1–2 h",
    "regular": "Regelmäßig · 2–4 h",
    "grind": "Marathon · 5 h+",
}

# Optional play-style tags. Self-found is the one that really gates
# compatibility in Hardcore; the rest are colour. All opt-in (min_values=0).
PLAY_TAGS: dict[str, str] = {
    "selffound": "Self-Found (kein AH / kein Twink-Support)",
    "voice": "Mit Voice / TeamSpeak",
    "relaxed": "Entspannt, kein Stress",
    "push": "Zügig pushen",
}
SELF_FOUND_TAG = "selffound"

# Above this level gap, a pairing is deprioritised hard — leveling together
# only works if both are roughly at the same point.
LEVEL_BRACKET = 10

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


def _encode(keys: Iterable[str], valid: dict[str, str]) -> str:
    """Canonical comma-separated encoding of ``keys`` limited to ``valid``."""
    selected = {k for k in keys if k in valid}
    return ",".join(key for key in valid if key in selected)


def _decode(raw: str | None, valid: dict[str, str]) -> list[str]:
    """Parse a stored string back into canonical-ordered valid keys."""
    if not raw:
        return []
    parts = {part.strip() for part in raw.split(",") if part.strip()}
    return [key for key in valid if key in parts]


def _format(keys: Iterable[str], valid: dict[str, str]) -> str:
    key_set = {k for k in keys if k in valid}
    labels = [label for key, label in valid.items() if key in key_set]
    return ", ".join(labels) if labels else "—"


def encode_windows(keys: Iterable[str]) -> str:
    """Serialise selected window keys to a canonical, comma-separated string."""
    return _encode(keys, TIME_WINDOWS)


def decode_windows(raw: str | None) -> list[str]:
    """Parse a stored window string back into canonical-ordered valid keys."""
    return _decode(raw, TIME_WINDOWS)


def window_labels(keys: Iterable[str]) -> list[str]:
    """Human-readable labels for the given window keys, canonical order."""
    key_set = {k for k in keys if k in TIME_WINDOWS}
    return [label for key, label in TIME_WINDOWS.items() if key in key_set]


def format_windows(keys: Iterable[str]) -> str:
    """Comma-joined window labels, or a dash when nothing is set."""
    return _format(keys, TIME_WINDOWS)


def encode_prefs(keys: Iterable[str]) -> str:
    """Serialise selected play-style tags to a canonical string."""
    return _encode(keys, PLAY_TAGS)


def decode_prefs(raw: str | None) -> list[str]:
    """Parse stored play-style tags back into canonical-ordered valid keys."""
    return _decode(raw, PLAY_TAGS)


def format_prefs(keys: Iterable[str]) -> str:
    """Comma-joined play-style labels, or a dash when nothing is set."""
    return _format(keys, PLAY_TAGS)


def intensity_label(key: str | None) -> str:
    """Human label for an intensity key, or a dash."""
    return INTENSITY.get(key or "", "—")


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
    self_found: bool = False
    intensity: str | None = None
    self_found_match: bool = True
    intensity_match: bool = True

    @property
    def overlap_count(self) -> int:
        return len(self.overlap)

    @property
    def level_far(self) -> bool:
        return self.level_distance > LEVEL_BRACKET


def rank_candidates(
    my_windows: Iterable[str],
    my_level: int,
    others: Iterable[tuple],
    *,
    my_self_found: bool = False,
    my_intensity: str | None = None,
) -> list[Candidate]:
    """Rank open signups against the searcher.

    ``others`` items are ``(discord_user_id, character_name, level, windows)``
    and may optionally carry ``self_found`` and ``intensity`` as a 5th/6th
    element. Best first, in priority order: most time-window overlap; then a
    roughly matching level (gap within :data:`LEVEL_BRACKET`); then same
    self-found stance; then same intensity; then closest level; then name.
    Zero-overlap candidates are still returned but sort last.
    """
    my_window_list = [k for k in my_windows if k in TIME_WINDOWS]
    ranked: list[Candidate] = []
    for other in others:
        user_id, name, level, windows = other[0], other[1], other[2], other[3]
        self_found = bool(other[4]) if len(other) > 4 else False
        intensity = other[5] if len(other) > 5 else None
        shared = overlap_keys(my_window_list, windows)
        ranked.append(
            Candidate(
                discord_user_id=user_id,
                character_name=name,
                level=level,
                windows=[k for k in windows if k in TIME_WINDOWS],
                overlap=shared,
                level_distance=abs(int(level) - int(my_level)),
                self_found=self_found,
                intensity=intensity,
                self_found_match=(self_found == my_self_found),
                intensity_match=(
                    bool(intensity) and bool(my_intensity) and intensity == my_intensity
                ),
            )
        )
    ranked.sort(
        key=lambda c: (
            -c.overlap_count,
            1 if c.level_far else 0,
            0 if c.self_found_match else 1,
            0 if c.intensity_match else 1,
            c.level_distance,
            c.character_name.casefold(),
        )
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
