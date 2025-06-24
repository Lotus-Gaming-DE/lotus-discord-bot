# cogs/wcr/embed_builder.py
"""Funktionen zum Erstellen von Discord-Embeds für Minis."""

from __future__ import annotations

import os
import discord
from typing import Any, Dict, List, Tuple

from log_setup import get_logger
from . import helpers

logger = get_logger(__name__)


def _prepare_stat_rows(
    emojis: Dict[str, str],
    unit_data: Dict[str, Any],
    stat_labels: Dict[str, str],
    type_name: str,
    speed_name: str,
) -> Tuple[List[Dict], List[Dict], List[Dict], Dict[str, Any], set[str]]:
    """Erstellt Statistikzeilen und liefert verwendete Stat-Schlüssel."""
    stats = unit_data.get("stats", {})

    row1_stats: List[Dict] = []
    row2_stats: List[Dict] = []
    row3_stats: List[Dict] = []

    cost = unit_data.get("cost", "N/A")
    row1_stats.append(
        {
            "name": f"{emojis.get('wcr_cost', '')} {stat_labels.get('cost', 'Kosten')}",
            "value": str(cost),
            "inline": True,
        }
    )
    row1_stats.append(
        {
            "name": f"{emojis.get('wcr_type', '')} {stat_labels.get('type_id', 'Typ')}",
            "value": type_name,
            "inline": True,
        }
    )

    health = stats.get("health")
    if health is not None:
        row2_stats.append(
            {
                "name": f"{emojis.get('wcr_health', '')} {stat_labels.get('health', 'Gesundheit')}",
                "value": str(health),
                "inline": True,
            }
        )
    if speed_name:
        row2_stats.append(
            {
                "name": f"{emojis.get('wcr_speed', '')} {stat_labels.get('speed_id', 'Geschwindigkeit')}",
                "value": speed_name,
                "inline": True,
            }
        )

    is_elemental = "8" in unit_data.get("trait_ids", [])
    if "damage" in stats or "area_damage" in stats:
        if "damage" in stats:
            damage_value = stats["damage"]
            if is_elemental:
                damage_label = stat_labels.get("damage", "Elementarschaden")
                damage_emoji = emojis.get("wcr_damage_ele", "")
            else:
                damage_label = stat_labels.get("damage", "Schaden")
                damage_emoji = emojis.get("wcr_damage", "")
        else:
            damage_value = stats["area_damage"]
            if is_elemental:
                damage_label = stat_labels.get("area_damage", "Elementarflächenschaden")
                damage_emoji = emojis.get("wcr_damage_ele", "")
            else:
                damage_label = stat_labels.get("area_damage", "Flächenschaden")
                damage_emoji = emojis.get("wcr_damage", "")
        row3_stats.append(
            {
                "name": f"{damage_emoji} {damage_label}",
                "value": str(damage_value),
                "inline": True,
            }
        )

    attack_speed = stats.get("attack_speed")
    if attack_speed is not None:
        row3_stats.append(
            {
                "name": f"{emojis.get('wcr_attack_speed', '')} {stat_labels.get('attack_speed', 'Angriffsgeschwindigkeit')}",
                "value": str(attack_speed),
                "inline": True,
            }
        )

    dps = stats.get("dps")
    if dps is not None:
        row3_stats.append(
            {
                "name": f"{emojis.get('wcr_dps', '')} {stat_labels.get('dps', 'DPS')}",
                "value": str(dps),
                "inline": True,
            }
        )

    used_stats_keys = {"damage", "area_damage", "attack_speed", "dps", "health"}
    return row1_stats, row2_stats, row3_stats, stats, used_stats_keys


def _prepare_extra_stats(
    emojis: Dict[str, str],
    stats: Dict[str, Any],
    stat_labels: Dict[str, str],
    used_stats_keys: set[str],
) -> List[Dict]:
    """Bereite zusätzliche Stats für das Embed auf."""
    extra_stats: List[Dict] = []
    for stat_key, emoji_name in [
        ("range", "wcr_range"),
        ("duration", "wcr_duration"),
        ("healing", "wcr_healing"),
        ("radius", "wcr_radius"),
        ("lvl_advantage", "wcr_advantage"),
        ("percent_dmg", "wcr_percent_dmg"),
        ("percent_dps", "wcr_percent_dps"),
        ("fan_damage", "wcr_fan_damage"),
        ("crash_damage", "wcr_crash_damage"),
        ("area_healing", "wcr_area_healing"),
        ("dwarf_dmg", "wcr_damage"),
        ("bear_dmg", "wcr_damage"),
        ("dwarf_dps", "wcr_dps"),
        ("bear_dps", "wcr_dps"),
        ("dwarf_health", "wcr_health"),
        ("bear_health", "wcr_health"),
        ("dwarf_range", "wcr_range"),
    ]:
        if stat_key in stats and stat_key not in used_stats_keys:
            label = stat_labels.get(stat_key, stat_key.capitalize())
            extra_stats.append(
                {
                    "name": f"{emojis.get(emoji_name, '')} {label}",
                    "value": str(stats[stat_key]),
                    "inline": True,
                }
            )
            used_stats_keys.add(stat_key)
    return extra_stats


def _prepare_talent_fields(talents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Gibt Felder für Talente zurück."""
    fields: List[Dict[str, Any]] = []
    if not talents:
        return fields
    fields.append({"name": "\u200b", "value": "**Talents**", "inline": False})
    for talent in talents[:3]:
        fields.append(
            {
                "name": talent.get("name", "Unbekanntes Talent"),
                "value": talent.get("description", "Beschreibung fehlt"),
                "inline": True,
            }
        )
    remainder = len(talents[:3]) % 3
    if remainder:
        for _ in range(3 - remainder):
            fields.append({"name": "\u200b", "value": "\u200b", "inline": True})
    return fields


def _prepare_traits_field(
    unit_data: Dict[str, Any],
    lang: str,
    stat_labels: Dict[str, str],
    lang_lookup: Dict[str, Any],
) -> Dict[str, Any] | None:
    """Fügt Traits als Feld hinzu, falls vorhanden."""
    traits_ids = unit_data.get("trait_ids", [])
    trait_lookup = (lang_lookup.get(lang) or lang_lookup.get("en", {})).get(
        "traits", {}
    )
    names = [trait_lookup[i]["name"] for i in traits_ids if i in trait_lookup]
    if not names:
        return None
    return {
        "name": stat_labels.get("traits", "Traits"),
        "value": ", ".join(names),
        "inline": False,
    }


def build_mini_embed(
    unit_id: str,
    unit_data: Dict[str, Any],
    lang: str,
    emojis: Dict[str, str],
    languages: Dict[str, Any],
    lang_category_lookup: Dict[str, Any],
    stat_labels_map: Dict[str, Dict[str, str]],
    faction_combinations: Dict[str, str],
) -> Tuple[discord.Embed, discord.File | None]:
    """Erstellt ein Embed mit den Details eines Minis."""
    unit_name, unit_description, talents = helpers.get_text_data(
        unit_id, lang, languages
    )

    stat_labels = stat_labels_map.get(lang) or stat_labels_map.get("en", {})
    factions = unit_data.get("faction_ids") or [unit_data.get("faction_id")]
    factions = [str(f) for f in factions if f is not None]
    primary_faction = factions[0] if factions else None
    faction_data = helpers.get_faction_data(primary_faction, lang_category_lookup)
    embed_color = int(faction_data.get("color", "#3498db").strip("#"), 16)
    icon_name = ""
    if len(factions) > 1:
        key = f"{factions[0]}_{factions[1]}"
        icon_name = faction_combinations.get(key)
        if not icon_name:
            key = f"{factions[1]}_{factions[0]}"
            icon_name = faction_combinations.get(key, faction_data.get("icon", ""))
    else:
        icon_name = faction_data.get("icon", "")
    faction_emoji = emojis.get(icon_name, "")

    type_name = helpers.get_category_name(
        "types", unit_data.get("type_id"), lang, lang_category_lookup
    )
    speed_name = helpers.get_category_name(
        "speeds", unit_data.get("speed_id"), lang, lang_category_lookup
    )

    row1, row2, row3, stats, used_keys = _prepare_stat_rows(
        emojis, unit_data, stat_labels, type_name, speed_name
    )
    extra_stats = _prepare_extra_stats(emojis, stats, stat_labels, used_keys)
    talent_fields = _prepare_talent_fields(talents)
    traits_field = _prepare_traits_field(
        unit_data, lang, stat_labels, lang_category_lookup
    )

    embed = discord.Embed(
        title=f"{faction_emoji} {unit_name}",
        description=f"{unit_description}\n\n**Stats**",
        color=embed_color,
    )

    def _add_group(fields: List[Dict]):
        for field in fields:
            embed.add_field(
                name=field["name"],
                value=field["value"],
                inline=field.get("inline", True),
            )
        while len(fields) < 3:
            embed.add_field(name="\u200b", value="\u200b", inline=True)
            fields.append(None)

    for group in (row1, row2, row3):
        if group:
            _add_group(group)

    for i in range(0, len(extra_stats), 3):
        _add_group(extra_stats[i : i + 3])

    for field in talent_fields:
        embed.add_field(
            name=field["name"], value=field["value"], inline=field.get("inline", True)
        )

    if traits_field:
        embed.add_field(
            name=traits_field["name"],
            value=traits_field["value"],
            inline=traits_field.get("inline", True),
        )

    pose_url = helpers.get_pose_url(unit_data)
    if pose_url:
        embed.set_thumbnail(url=pose_url)

    logo_filename = "LotusGaming.png"
    logo_path = os.path.join("data", "media", logo_filename)
    if os.path.exists(logo_path):
        embed.set_footer(
            text="a service brought to you by Lotus Gaming",
            icon_url=f"attachment://{logo_filename}",
        )
        logo_file = discord.File(logo_path, filename=logo_filename)
    else:
        embed.set_footer(text="a service brought to you by Lotus Gaming")
        logo_file = None

    return embed, logo_file
