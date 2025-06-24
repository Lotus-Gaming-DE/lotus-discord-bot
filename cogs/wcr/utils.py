# cogs/wcr/utils.py

"""Hilfsfunktionen zum Laden der WCR-Daten."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import aiohttp
import asyncio
import json

from log_setup import get_logger

logger = get_logger(__name__)

BASE_PATH = Path("data/wcr")


async def fetch_wcr_data(base_url: str) -> dict[str, Any]:
    """Ruft alle WCR-Endpunkte von ``base_url`` ab.

    Erwartet die Unterpfade ``/units``, ``/categories``, ``/pictures`` und
    ``/stat_labels``.
    """

    endpoints = ["units", "categories", "pictures", "stat_labels"]
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
            item["id"]: {k: item[k] for k in ("icon", "color") if k in item}
            for item in meta.get("factions", [])
        }
        for faction in data["categories"].get("factions", []):
            faction.update(meta_map.get(faction.get("id"), {}))

    return data


async def load_wcr_data(base_url: str | None = None) -> dict[str, Any]:
    """Lädt alle benötigten WCR-Daten über ``fetch_wcr_data``."""

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

    return {
        "units": units_list,
        "locals": locals_,
        "pictures": api_data.get("pictures", {}),
        "categories": api_data.get("categories", {}),
        "stat_labels": api_data.get("stat_labels", {}),
    }
