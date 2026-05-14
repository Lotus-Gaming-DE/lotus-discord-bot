"""Refresh learned_from + recipe_item_* fields by re-parsing wowhead spell pages.

The bundled importer (``wow_importer.py --slice professions``) crawls
``/items/recipes/<profession>`` pages to discover recipe items. Those
overview pages are nachweislich incomplete — e.g. ``Recipe: Elixir of
Greater Firepower`` (item 21547) is not listed for alchemy even though it
exists. Consequence: hundreds of legit drop-recipes end up classified as
``learned_from: "trainer"`` and are filtered out of /wow crafting recipes.

This one-off script uses the per-spell wowhead page as authoritative
source. For each recipe in ``profession_recipes.json`` it fetches
``/classic/spell=<id>`` (en + de), extracts the ``taught-by-item``
Listview, and updates:

  * ``learned_from`` — ``recipe`` if the spell has at least one teaching
    item, else ``trainer``.
  * ``recipe_item_*`` fields — built from the highest-priority source
    (world_drop > drop > pickpocketed > quest > vendor).
  * ``items.json`` — appended with missing recipe items so the validator
    referential-integrity check stays green.

Usage::

    python scripts/refresh_recipe_data.py --spell 26277      # Phase A smoketest
    python scripts/refresh_recipe_data.py                     # Phase B dry-run
    python scripts/refresh_recipe_data.py --write             # Phase C commit

Re-runs are cheap: wowhead pages are cached under
``data/pers/wow_import_cache/``. A timestamped backup of the originals
is taken before any write.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

# Imports after sys.path fix.
from lotus_bot.bot import load_wow_data  # noqa: E402
from lotus_bot.cogs.quiz.area_providers.wow_importer import (  # noqa: E402
    WowheadFetcher,
    _jsonish_to_json,
    _matching_json_array_end,
    _primary_recipe_item,
    extract_listpage_json,
    normalize_item,
    normalize_recipe_source_item,
)
from lotus_bot.cogs.quiz.area_providers.wow_validation import (  # noqa: E402
    assert_valid_wow_data,
)

DATA_DIR = ROOT / "data" / "wow" / "classic_hc"
CACHE_DIR = ROOT / "data" / "pers" / "wow_import_cache"
BACKUP_ROOT = ROOT / "data" / "pers" / "wow_backup"
RECIPES_FILE = DATA_DIR / "profession_recipes.json"
ITEMS_FILE = DATA_DIR / "items.json"

WOWHEAD = "https://www.wowhead.com/classic"

# Fields owned by the "linked recipe item" — wiped before we re-apply,
# so a recipe that used to have a stale link doesn't keep stale fields.
RECIPE_ITEM_FIELDS = (
    "recipe_item_id",
    "recipe_item_name",
    "recipe_item_sources",
    "recipe_item_side",
    "recipe_item_required_skill",
    "recipe_item_profession_id",
    "recipe_item_source_urls",
    "recipe_items",
)


def _strip_recipe_item_fields(recipe: dict[str, Any]) -> None:
    for key in RECIPE_ITEM_FIELDS:
        recipe.pop(key, None)


async def _fetch_with_long_backoff(
    fetcher: WowheadFetcher, url: str, *, max_attempts: int = 4
) -> str:
    """Wrap ``fetcher.fetch_url`` with extra-long sleeps on rate-limit failures.

    The bundled fetcher already retries 403/429/5xx 3x with up to 4.5s
    of total sleep — but wowhead's CDN keeps serving 403 for tens of
    seconds after a burst. This wrapper sleeps 30/60/90s with jitter
    between top-level retries so a transient block clears between
    attempts.
    """
    for attempt in range(max_attempts):
        try:
            return await fetcher.fetch_url(url)
        except RuntimeError as exc:
            if attempt + 1 >= max_attempts:
                raise
            wait = 30 * (attempt + 1) + random.uniform(0, 10)
            print(
                f"  [retry] {url}: {exc} -- sleeping {wait:.0f}s "
                f"(attempt {attempt + 2}/{max_attempts})",
                flush=True,
            )
            await asyncio.sleep(wait)
    raise RuntimeError(f"Exhausted retries for {url}")


async def _fetch_spell_pages(fetcher: WowheadFetcher, spell_id: int) -> tuple[str, str]:
    en = await _fetch_with_long_backoff(fetcher, f"{WOWHEAD}/spell={spell_id}")
    try:
        de = await _fetch_with_long_backoff(fetcher, f"{WOWHEAD}/de/spell={spell_id}")
    except RuntimeError as exc:
        # DE failure is recoverable — fall back to EN page for German names
        # so the recipe still gets correct learned_from / source data; the
        # name reads English instead of German for those few spells.
        print(
            f"  [warn] DE page failed for spell {spell_id}, using EN as fallback: {exc}",
            flush=True,
        )
        de = en
    return en, de


def _extract_listview_after_id(page: str, listview_id: str) -> list[dict[str, Any]]:
    """Extract the ``data: [...]`` payload of a specific Listview.

    Wowhead's legacy spell pages render listviews as
    ``new Listview({template: 'item', id: '<listview_id>', ..., data: [...]});``.
    The bundled :func:`extract_listview_data` helper assumes the layout
    ``data: [...], id: '<listview_id>'`` (data BEFORE id) and uses
    ``rfind`` to anchor — that fails here. This implementation looks for
    ``data:`` strictly AFTER the ``id:`` marker but still within the same
    ``new Listview`` block.
    """
    json_data = extract_listpage_json(page, listview_id)
    if json_data is not None:
        return json_data
    for needle in (f"id: '{listview_id}'", f'id: "{listview_id}"'):
        start = page.find(needle)
        if start != -1:
            break
    else:
        return []
    next_listview = page.find("new Listview", start + 1)
    end = next_listview if next_listview != -1 else len(page)
    data_pos = page.find("data:", start, end)
    if data_pos == -1:
        return []
    array_start = page.find("[", data_pos, end)
    if array_start == -1:
        return []
    array_end = _matching_json_array_end(page, array_start)
    if array_end == -1 or array_end >= end:
        return []
    return json.loads(_jsonish_to_json(page[array_start : array_end + 1]))


def _parse_teaching_items(
    en_page: str, de_page: str
) -> tuple[list[dict[str, Any]], dict[int, dict[str, Any]]]:
    """Return (en_rows, de_rows_by_id) from the ``taught-by-item`` Listview."""
    en_rows = _extract_listview_after_id(en_page, "taught-by-item")
    de_rows = _extract_listview_after_id(de_page, "taught-by-item")
    de_by_id = {int(row["id"]): row for row in de_rows if "id" in row}
    return en_rows, de_by_id


def _update_recipe(
    recipe: dict[str, Any],
    en_rows: list[dict[str, Any]],
    de_by_id: dict[int, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Rewrite recipe in place. Return (recipe_item_dicts, change_log).

    ``recipe_item_dicts`` is the list of normalized source items (one per
    teaching item on the spell page) — caller uses these to backfill
    items.json. ``change_log`` is human-readable for the diff summary.
    """
    changes: list[str] = []
    old_learned_from = recipe.get("learned_from")
    old_item_id = recipe.get("recipe_item_id")
    profession_id = recipe["profession_id"]

    if not en_rows:
        _strip_recipe_item_fields(recipe)
        recipe["learned_from"] = "trainer"
        if old_learned_from != "trainer":
            changes.append(
                f"{recipe['id']}: learned_from {old_learned_from!r} -> 'trainer'"
            )
        if old_item_id:
            changes.append(f"{recipe['id']}: recipe_item dropped ({old_item_id})")
        return [], changes

    sources: list[dict[str, Any]] = []
    for en in en_rows:
        item_id = int(en["id"])
        de = de_by_id.get(item_id, en)
        sources.append(normalize_recipe_source_item(de, en, profession_id))

    primary = _primary_recipe_item(sources)
    _strip_recipe_item_fields(recipe)
    recipe["learned_from"] = "recipe"
    if primary:
        recipe.update(primary)
        if len(sources) > 1:
            recipe["recipe_items"] = sorted(
                sources, key=lambda item: item["recipe_item_id"]
            )

    if old_learned_from != "recipe":
        changes.append(f"{recipe['id']}: learned_from {old_learned_from!r} -> 'recipe'")
    new_item_id = primary["recipe_item_id"] if primary else None
    if old_item_id != new_item_id:
        changes.append(
            f"{recipe['id']}: recipe_item_id {old_item_id!r} -> {new_item_id!r}"
        )
    return sources, changes


def _items_to_add(
    en_rows: list[dict[str, Any]],
    de_by_id: dict[int, dict[str, Any]],
    items_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    new: list[dict[str, Any]] = []
    for en in en_rows:
        item_id = int(en["id"])
        key = f"item.{item_id}"
        if key in items_by_id:
            continue
        de = de_by_id.get(item_id, en)
        normalized = normalize_item(de, en)
        new.append(normalized)
        items_by_id[key] = normalized  # mark as known for subsequent loops
    return new


def _write_atomic(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    tmp.replace(path)


async def _process_one(
    fetcher: WowheadFetcher,
    recipe: dict[str, Any],
    items_by_id: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str], str | None]:
    spell_full = recipe.get("spell_id", "")
    if not isinstance(spell_full, str) or not spell_full.startswith("spell."):
        return [], [], f"{recipe.get('id')}: skipped (no spell_id)"
    spell_id = int(spell_full.removeprefix("spell."))
    try:
        en_page, de_page = await _fetch_spell_pages(fetcher, spell_id)
    except Exception as exc:
        return [], [], f"{recipe['id']} (spell {spell_id}): fetch failed: {exc}"

    try:
        en_rows, de_by_id = _parse_teaching_items(en_page, de_page)
    except Exception as exc:
        return [], [], f"{recipe['id']} (spell {spell_id}): parse failed: {exc}"

    _, changes = _update_recipe(recipe, en_rows, de_by_id)
    new_items = _items_to_add(en_rows, de_by_id, items_by_id)
    return new_items, changes, None


async def _smoketest(spell_id: int) -> int:
    fetcher = WowheadFetcher(cache_path=CACHE_DIR)
    recipes = json.loads(RECIPES_FILE.read_text(encoding="utf-8"))
    items_by_id = {
        item["id"]: item for item in json.loads(ITEMS_FILE.read_text(encoding="utf-8"))
    }
    target = next(
        (r for r in recipes if r.get("spell_id") == f"spell.{spell_id}"), None
    )
    if not target:
        print(f"No recipe for spell.{spell_id} in profession_recipes.json", flush=True)
        return 1
    print(f"Smoketest: {target['id']} (spell.{spell_id})", flush=True)
    new_items, changes, error = await _process_one(fetcher, target, items_by_id)
    if error:
        print(error, flush=True)
        return 1
    print(f"  new items to add: {[it['id'] for it in new_items]}", flush=True)
    print(f"  changes: {changes}", flush=True)
    print(
        "  recipe after rewrite:\n" + json.dumps(target, indent=2, ensure_ascii=False),
        flush=True,
    )
    return 0


async def _run_bulk(write: bool, limit: int | None) -> int:
    # 0.5s base delay (vs. importer default 0.3s) — empirically wowhead's
    # CDN starts serving 403 around 0.3s with no jitter on our IP.
    fetcher = WowheadFetcher(cache_path=CACHE_DIR, delay_seconds=0.5)
    recipes = json.loads(RECIPES_FILE.read_text(encoding="utf-8"))
    items = json.loads(ITEMS_FILE.read_text(encoding="utf-8"))
    items_by_id = {item["id"]: item for item in items}

    targets = recipes if limit is None else recipes[:limit]
    total = len(targets)
    all_changes: list[str] = []
    new_items_collected: list[dict[str, Any]] = []
    errors: list[str] = []

    start = time.time()
    for idx, recipe in enumerate(targets, 1):
        new_items, changes, error = await _process_one(fetcher, recipe, items_by_id)
        if error:
            errors.append(error)
            # Log immediately so failures are visible during long runs.
            print(f"[{idx}/{total}] ERROR: {error}", flush=True)
            continue
        new_items_collected.extend(new_items)
        all_changes.extend(changes)
        if idx % 50 == 0 or idx == total:
            elapsed = time.time() - start
            print(
                f"[{idx}/{total}] elapsed={elapsed:.0f}s "
                f"changes={len(all_changes)} new_items={len(new_items_collected)} "
                f"errors={len(errors)}",
                flush=True,
            )

    print("\n=== Summary ===", flush=True)
    print(f"Recipes processed: {total}", flush=True)
    print(f"Field changes recorded: {len(all_changes)}", flush=True)
    print(
        f"New recipe items to add to items.json: {len(new_items_collected)}", flush=True
    )
    print(f"Per-recipe errors: {len(errors)}", flush=True)
    if errors[:5]:
        print("First few errors:", flush=True)
        for line in errors[:5]:
            print(f"  - {line}", flush=True)
    if all_changes[:10]:
        print("First few changes:", flush=True)
        for line in all_changes[:10]:
            print(f"  - {line}", flush=True)

    if not write:
        print(
            "\n(dry-run — pass --write to persist; backup will be made automatically)",
            flush=True,
        )
        return 0

    # Phase C: backup + write + validate
    items.extend(new_items_collected)
    items_sorted = sorted(items, key=lambda it: int(it.get("wowhead_id", 0)))

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = BACKUP_ROOT / timestamp
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(RECIPES_FILE, backup / RECIPES_FILE.name)
    shutil.copy2(ITEMS_FILE, backup / ITEMS_FILE.name)
    print(f"\nBackup written to {backup.relative_to(ROOT)}", flush=True)

    _write_atomic(RECIPES_FILE, recipes)
    _write_atomic(ITEMS_FILE, items_sorted)

    try:
        data = load_wow_data(str(DATA_DIR))
        assert_valid_wow_data(data)
        print("Validator: OK", flush=True)
    except Exception as exc:
        print(f"Validator FAILED: {exc}", flush=True)
        print(f"Restoring originals from {backup.relative_to(ROOT)}", flush=True)
        shutil.copy2(backup / RECIPES_FILE.name, RECIPES_FILE)
        shutil.copy2(backup / ITEMS_FILE.name, ITEMS_FILE)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--spell",
        type=int,
        default=None,
        help="Process a single spell_id and print the result (Phase A smoketest).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Persist changes (default: dry-run, no files written).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Process only the first N recipes (useful for staged runs).",
    )
    args = parser.parse_args(argv)
    if args.spell is not None:
        return asyncio.run(_smoketest(args.spell))
    return asyncio.run(_run_bulk(write=args.write, limit=args.limit))


if __name__ == "__main__":
    raise SystemExit(main())
