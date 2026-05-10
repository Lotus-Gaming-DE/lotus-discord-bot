import argparse
import copy
import json

import pytest

from lotus_bot.bot import load_wow_data
from lotus_bot.cogs.quiz.area_providers import wow_importer
from lotus_bot.cogs.quiz.area_providers.wow_importer import (
    extract_spell_rows,
    import_professions,
    import_spells,
    import_zones,
    import_instances,
    merge_records,
    normalize_drop,
    normalize_item,
    parse_instance_page,
    run_import,
)


DE_PAGE = """
<html>
<head><title>Testhöhle - Zone - World of Warcraft: Classic</title></head>
<body>
<script>
WH.markup.printHtml("[ul][li]Stufe: 42 - 52[\\/li][li]Territorium: Umk\\u00e4mpft[\\/li][li]Instanzart: Dungeon[\\/li][li]Anzahl an Spielern: 5[\\/li][li]Zone ID: 9999[\\/li][li]Englische: [copy button=false]Test Cavern[\\/copy][\\/li][\\/ul]", "infobox-contents-0", {});
</script>
<script>
new Listview({template: 'item', id: 'drops', data:[
{"classs":2,"id":111,"level":54,"name":"Testdolch","quality":3,"reqlevel":49,"slot":21,"slotbak":21,"source":[2],"sourcemore":[{"n":"Testboss","z":9999}],"subclass":15,"modes":{"mode":[1,201]}},
{"classs":12,"id":222,"level":1,"name":"Questding","quality":1,"source":[2],"sourcemore":[{"n":"Testboss","z":9999}],"subclass":0,"modes":{"mode":[1]}},
{"classs":2,"id":333,"level":60,"name":"Sodklinge","quality":4,"slot":17,"slotbak":17,"source":[2],"sourcemore":[{"n":"Testboss","z":9999}],"subclass":8,"modes":{"mode":[201]}}
]});
</script>
</body>
</html>
"""

EN_PAGE = """
<html>
<head><title>Test Cavern - Zone - World of Warcraft: Classic</title></head>
<body>
<script>
WH.markup.printHtml("[ul][li]Level: 42 - 52[\\/li][li]Territory: Contested[\\/li][li]Type: Dungeon[\\/li][li]Players: 5[\\/li][\\/ul]", "infobox-contents-0", {});
</script>
<script>
new Listview({template: 'item', id: 'drops', data:[
{"classs":2,"id":111,"level":54,"name":"Test Dagger","quality":3,"reqlevel":49,"slot":21,"slotbak":21,"source":[2],"sourcemore":[{"n":"Test Boss","z":9999}],"subclass":15,"modes":{"mode":[1,201]}},
{"classs":12,"id":222,"level":1,"name":"Quest Thing","quality":1,"source":[2],"sourcemore":[{"n":"Test Boss","z":9999}],"subclass":0,"modes":{"mode":[1]}}
]});
</script>
</body>
</html>
"""

ZONE_DE_PAGE = """
<script type="application/json" id="data.page.listPage.listviews">[{"id":"zones","template":"zone","data":[{"category":0,"id":47,"instance":0,"maxlevel":50,"minlevel":40,"name":"Hinterland","territory":2},{"category":0,"id":10,"instance":0,"maxlevel":30,"minlevel":10,"name":"Dämmerwald","territory":2}]}]</script>
"""

ZONE_EN_PAGE = """
<script type="application/json" id="data.page.listPage.listviews">[{"id":"zones","template":"zone","data":[{"category":0,"id":47,"instance":0,"maxlevel":50,"minlevel":40,"name":"The Hinterlands","territory":2},{"category":0,"id":10,"instance":0,"maxlevel":30,"minlevel":10,"name":"Duskwood","territory":2}]}]</script>
"""

SPELL_DE_PAGE = """
<html><head><title>Classic - Kampf Schurke Talente - World of Warcraft: Classic</title></head>
<script>WH.Gatherer.addData(6, 4, {"13845":{"name_dede":"Präzision","description_dede":"Erhöht Eure Trefferchance."}});</script>
<script>var listviewspells = [{cat:-2,chrclass:8,id:13845,level:0,name:"Präzision",rank:"Rang 5",reqclass:8,skill:[38],talentspec:[181],quality:-1}];</script></html>
"""

SPELL_EN_PAGE = """
<html><head><title>Classic - Combat Rogue Talents - Classic World of Warcraft</title></head>
<script>WH.Gatherer.addData(6, 4, {"13845":{"name_enus":"Precision","description_enus":"Increases your hit chance."}});</script>
<script>var listviewspells = [{cat:-2,chrclass:8,id:13845,level:0,name:"Precision",rank:"Rank 5",reqclass:8,skill:[38],talentspec:[181],quality:-1}];</script></html>
"""

PROFESSION_DE_PAGE = """
<script>WH.Gatherer.addData(6, 4, {"2330":{"name_dede":"Schwacher Heiltrank","description_dede":"Stellt einen schwachen Heiltrank her."}});</script>
<script>var listviewspells = [{cat:11,colors:[1,55,75,95],creates:[118,1,1],id:2330,learnedat:1,level:0,name:"Schwacher Heiltrank",quality:1,skill:[171],source:[6]}];</script>
"""

PROFESSION_EN_PAGE = """
<script>WH.Gatherer.addData(6, 4, {"2330":{"name_enus":"Minor Healing Potion","description_enus":"Creates a Minor Healing Potion."}});</script>
<script>var listviewspells = [{cat:11,colors:[1,55,75,95],creates:[118,1,1],id:2330,learnedat:1,level:0,name:"Minor Healing Potion",quality:1,skill:[171],source:[6]}];</script>
"""


def test_parse_instance_page_normalizes_instance_drop_and_item():
    records = parse_instance_page(9999, {"de": DE_PAGE, "en": EN_PAGE})

    assert records["dungeons"] == [
        {
            "id": "instance.test_cavern",
            "zone_id": "zone.9999",
            "wowhead_id": 9999,
            "type": "dungeon",
            "name": {"de": "Testhöhle", "en": "Test Cavern"},
            "level_range": "42-52",
            "territory_id": "contested",
            "player_count": 5,
            "hardcore_enabled": True,
            "source_url": "https://www.wowhead.com/classic/de/zone=9999",
            "source_urls": {
                "de": "https://www.wowhead.com/classic/de/zone=9999",
                "en": "https://www.wowhead.com/classic/zone=9999",
            },
            "answers": {
                "level_range": ["42-52", "42 bis 52", "42 to 52"],
                "name": ["Testhöhle", "Test Cavern"],
            },
        }
    ]
    assert records["items"][0]["item_class"] == "weapon"
    assert records["items"][0]["item_subclass"] == "dagger"
    assert records["items"][0]["quality"] == "rare"
    assert records["items"][0]["is_quest_item"] is False
    assert records["items"][0]["source_urls"]["de"].endswith("/de/item=111")
    assert records["instance_drops"] == [
        {
            "id": "drop.test_cavern.test_dagger",
            "instance_id": "instance.test_cavern",
            "item_id": "item.111",
            "source_name": {"de": "Testboss", "en": "Test Boss"},
            "mode": "normal",
            "season": "classic_era",
            "include_in_hardcore_quiz": True,
        }
    ]


def test_parse_instance_page_filters_quest_items_and_sod_only_drops():
    records = parse_instance_page(9999, {"de": DE_PAGE, "en": EN_PAGE})

    item_ids = {item["id"] for item in records["items"]}

    assert item_ids == {"item.111"}


def test_limit_drops_keeps_sample_small():
    records = parse_instance_page(9999, {"de": DE_PAGE, "en": EN_PAGE}, limit_drops=1)

    assert len(records["items"]) == 1
    assert len(records["instance_drops"]) == 1


def test_extract_spell_rows_parses_wowhead_jsonish_listview():
    rows = extract_spell_rows(SPELL_DE_PAGE)

    assert rows[0]["id"] == 13845
    assert rows[0]["name"] == "Präzision"


def test_import_zones_normalizes_listpage_records():
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))

    result = import_zones(
        data,
        {
            "/zones/eastern-kingdoms": {"de": ZONE_DE_PAGE, "en": ZONE_EN_PAGE},
            "/zones/kalimdor": {"de": ZONE_DE_PAGE, "en": ZONE_EN_PAGE},
        },
        limit_records=1,
    )

    zone = next(row for row in result.data["zones"] if row["id"] == "zone.47")
    assert zone["name"]["en"] == "The Hinterlands"
    assert zone["level_range"] == "40-50"


def test_import_spells_normalizes_talent_spell_and_record(monkeypatch):
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    empty_spell_page = "<script>var listviewspells = [];</script>"
    pages = {}
    for path in wow_importer.spell_list_paths():
        if "/spells/talents/warrior/arms" == path:
            pages[path] = {"de": SPELL_DE_PAGE, "en": SPELL_EN_PAGE}
        else:
            pages[path] = {"de": empty_spell_page, "en": empty_spell_page}

    result = import_spells(data, pages, limit_records=1)

    spell = next(row for row in result.data["spells"] if row["id"] == "spell.13845")
    imported_talents = [
        row
        for row in result.data["talents"]
        if row["spell_id"] == "spell.13845" and row["id"].endswith(".13845")
    ]
    assert spell["description"]["de"] == "Erhöht Eure Trefferchance."
    assert any(talent["class_id"] == "warrior" for talent in imported_talents)


def test_import_professions_normalizes_recipe_spell_and_created_item():
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    pages = {
        path: {"de": PROFESSION_DE_PAGE, "en": PROFESSION_EN_PAGE}
        for path in wow_importer.profession_list_paths()
    }

    result = import_professions(data, pages, limit_records=1)

    recipe = next(
        row
        for row in result.data["profession_recipes"]
        if row["spell_id"] == "spell.2330"
    )
    assert recipe["profession_id"] == "alchemy"
    assert recipe["creates_item_id"] == "item.118"
    assert recipe["required_skill"] == 1
    assert recipe["learned_from"] == "trainer"


def test_merge_records_updates_by_id_without_replacing_unrelated_records():
    existing = [{"id": "a", "value": 1}, {"id": "b", "value": 2}]
    incoming = [{"id": "b", "value": 3}, {"id": "c", "value": 4}]

    added, updated = merge_records(existing, incoming)

    assert added == 1
    assert updated == 1
    assert existing == [
        {"id": "a", "value": 1},
        {"id": "b", "value": 3},
        {"id": "c", "value": 4},
    ]


def test_merge_records_updates_by_wowhead_id_when_slug_changes():
    existing = [{"id": "instance.zulgurub", "wowhead_id": 1977, "name": "old"}]
    incoming = [{"id": "instance.zul_gurub", "wowhead_id": 1977, "name": "new"}]

    added, updated = merge_records(existing, incoming)

    assert added == 0
    assert updated == 1
    assert existing == [{"id": "instance.zul_gurub", "wowhead_id": 1977, "name": "new"}]


def test_import_instances_returns_valid_merged_data():
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))

    result = import_instances(data, {9999: {"de": DE_PAGE, "en": EN_PAGE}})

    assert result.added["dungeons"] == 1
    assert result.added["items"] == 1
    assert result.added["instance_drops"] == 1


@pytest.mark.asyncio
async def test_run_import_preview_does_not_write(monkeypatch, tmp_path):
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    (tmp_path / "items.json").write_text(json.dumps(data["items"]), encoding="utf-8")

    monkeypatch.setattr(
        wow_importer.WowheadFetcher,
        "fetch_instance_pages",
        lambda self, ids: _async_result({9999: {"de": DE_PAGE, "en": EN_PAGE}}),
    )
    monkeypatch.setattr(wow_importer, "load_wow_data", lambda path: copy.deepcopy(data))

    args = argparse.Namespace(
        slice="instances",
        ids="9999",
        data_path=str(tmp_path),
        limit_drops=None,
        write=False,
        preview=True,
    )

    await run_import(args)

    written_items = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    assert written_items == data["items"]


@pytest.mark.asyncio
async def test_run_import_write_persists_and_validates(monkeypatch, tmp_path):
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    for table, records in data.items():
        (tmp_path / f"{table}.json").write_text(json.dumps(records), encoding="utf-8")

    monkeypatch.setattr(
        wow_importer.WowheadFetcher,
        "fetch_instance_pages",
        lambda self, ids: _async_result({9999: {"de": DE_PAGE, "en": EN_PAGE}}),
    )

    args = argparse.Namespace(
        slice="instances",
        ids="9999",
        data_path=str(tmp_path),
        limit_drops=None,
        write=True,
        preview=False,
    )

    await run_import(args)

    items = json.loads((tmp_path / "items.json").read_text(encoding="utf-8"))
    assert any(item["id"] == "item.111" for item in items)


@pytest.mark.asyncio
async def test_run_import_write_aborts_on_invalid_validation(monkeypatch, tmp_path):
    data = copy.deepcopy(load_wow_data("data/wow/classic_hc"))
    for table, records in data.items():
        (tmp_path / f"{table}.json").write_text(json.dumps(records), encoding="utf-8")

    def invalid_import(current, pages, *, limit_drops=None):
        current["instance_drops"].append(
            normalize_drop("instance.missing", 9999, {"id": 111, "name": "X"}, {})
        )
        return wow_importer.ImportResult(data=current)

    monkeypatch.setattr(
        wow_importer.WowheadFetcher,
        "fetch_instance_pages",
        lambda self, ids: _async_result({9999: {"de": DE_PAGE, "en": EN_PAGE}}),
    )
    monkeypatch.setattr(wow_importer, "import_instances", invalid_import)

    args = argparse.Namespace(
        slice="instances",
        ids="9999",
        data_path=str(tmp_path),
        limit_drops=None,
        write=True,
        preview=False,
    )

    with pytest.raises(ValueError):
        await run_import(args)

    drops = json.loads((tmp_path / "instance_drops.json").read_text(encoding="utf-8"))
    assert not any(drop["instance_id"] == "instance.missing" for drop in drops)


async def _async_result(value):
    return value
