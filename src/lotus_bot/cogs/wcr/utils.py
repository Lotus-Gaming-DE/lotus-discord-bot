# cogs/wcr/utils.py

"""Hilfsfunktionen zum Laden der WCR-Daten."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import aiohttp
import asyncio
import json

from lotus_bot.log_setup import get_logger

logger = get_logger(__name__)

BASE_PATH = Path("data/wcr")

# Cache-Datei für API-Daten
CACHE_FILE = Path("data/pers/wcr_cache.json")
# Standard-TTL (in Sekunden) kann über ``WCR_CACHE_TTL`` angepasst werden
CACHE_TTL = int(os.getenv("WCR_CACHE_TTL", "86400"))


async def fetch_wcr_data(base_url: str) -> dict[str, Any]:
    """Ruft alle WCR-Endpunkte von ``base_url`` ab.

    Erwartet die Unterpfade ``/units`` und ``/categories``.
    """

    endpoints = ["units", "categories"]
    data: dict[str, Any] = {}
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:

        async def fetch(ep: str) -> tuple[str, Any]:
            url = f"{base_url.rstrip('/')}/{ep}"
            try:
                async with session.get(url) as resp:
                    resp.raise_for_status()
                    payload = await resp.json()
                logger.info("[WCRUtils] '%s' erfolgreich geladen.", ep)
                return ep, payload
            except asyncio.TimeoutError:
                logger.error("[WCRUtils] Timeout beim Abrufen von %s", ep)
            except Exception as exc:  # pragma: no cover - unexpected errors
                logger.error("[WCRUtils] Fehler beim Abrufen von %s: %s", ep, exc)
            return ep, {}

        results = await asyncio.gather(*(fetch(ep) for ep in endpoints))
        data.update(dict(results))

    # Fraktions-Metadaten aus lokaler Datei zusammenführen
    meta_file = BASE_PATH / "faction_meta.json"
    if meta_file.exists() and "categories" in data:
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
        except Exception as exc:  # pragma: no cover - should not happen in tests
            logger.error("[WCRUtils] Fehler beim Laden von faction_meta.json: %s", exc)
            meta = {}

        meta_map = {
            str(item["id"]): {k: item[k] for k in ("icon", "color") if k in item}
            for item in meta.get("factions", [])
        }
        data["faction_combinations"] = meta.get("combinations", {})
        for faction in data["categories"].get("factions", []):
            faction.update(meta_map.get(str(faction.get("id")), {}))

    return data


async def load_wcr_data(base_url: str | None = None) -> dict[str, Any]:
    """Lädt alle benötigten WCR-Daten.

    Bei vorhandenem und gültigem Cache werden die Daten aus
    :data:`CACHE_FILE` geladen. Andernfalls erfolgt ein API-Aufruf über
    :func:`fetch_wcr_data` und das Ergebnis wird im Cache gespeichert.
    """

    # Zuerst Cache prüfen
    if CACHE_FILE.exists():
        age = time.time() - CACHE_FILE.stat().st_mtime
        if age < CACHE_TTL:
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                logger.info("[WCRUtils] Daten aus Cache geladen.")
                return cached
            except Exception as exc:  # pragma: no cover - should not happen
                logger.error("[WCRUtils] Fehler beim Lesen des Caches: %s", exc)

    base_url = base_url or os.getenv("WCR_API_URL")
    if not base_url:
        logger.error("[WCRUtils] Basis-URL f\u00fcr die WCR-API fehlt.")
        return {}

    api_data = await fetch_wcr_data(base_url)

    units = api_data.get("units", {})
    units_list = units.get("units", units)

    locals_ = units.get("locals", {})
    if not locals_:
        for unit in units_list:
            texts = unit.get("texts", {})
            for lang, info in texts.items():
                lang_data = locals_.setdefault(lang, {})
                lang_units = lang_data.setdefault("units", [])
                entry = {"id": unit.get("id")}
                entry.update(info)
                lang_units.append(entry)

    # Stat-Labels lokal laden
    stat_labels_file = BASE_PATH / "stat_labels.json"
    stat_labels = {}
    if stat_labels_file.exists():
        try:
            with open(stat_labels_file, "r", encoding="utf-8") as f:
                stat_labels = json.load(f)
        except Exception as exc:  # pragma: no cover - should not happen in tests
            logger.error("[WCRUtils] Fehler beim Laden von stat_labels.json: %s", exc)

    result = {
        "units": units_list,
        "locals": locals_,
        "categories": api_data.get("categories", {}),
        "stat_labels": stat_labels,
        "faction_combinations": api_data.get("faction_combinations", {}),
    }

    # Cache speichern
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(result, f)
        logger.info("[WCRUtils] Cache aktualisiert.")
    except Exception as exc:  # pragma: no cover - should not happen
        logger.error("[WCRUtils] Fehler beim Schreiben des Caches: %s", exc)

    return result
