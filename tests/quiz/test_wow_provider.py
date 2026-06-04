from lotus_bot.bot import load_json, load_wow_data
from lotus_bot.cogs.quiz.area_providers.wow import WoWQuestionProvider


class DummyBot:
    def __init__(self, wow_data=None):
        self.data = {
            "wow": wow_data or load_wow_data("data/wow/classic_hc"),
            "quiz": {"templates": {"wow": load_json("data/quiz/templates/wow.json")}},
        }


def test_wow_provider_generates_broad_question_catalog():
    provider = WoWQuestionProvider(DummyBot(), language="de")
    questions = provider.generate_all_types(context="scheduled")
    duel_questions = provider.generate_all_types(context="duel")

    assert len(questions) >= 12
    assert len(duel_questions) > len(questions)
    assert all("frage" in q and "antwort" in q and "id" in q for q in questions)
    assert all(q.get("difficulty") in {"easy", "medium", "hard"} for q in questions)
    assert all(q.get("difficulty") != "easy" for q in questions)


def test_wow_provider_uses_question_language_and_bilingual_answers(monkeypatch):
    provider = WoWQuestionProvider(DummyBot(), language="de")

    def choose_precision(records):
        for record in records:
            spell = provider._spell_for(record)
            if spell.get("wowhead_id") == 13845:
                return record
        return records[0]

    monkeypatch.setattr("random.choice", choose_precision)

    question = provider.generate_talent_tree()

    assert "Präzision" in question["frage"]
    assert "Schurke" in question["frage"]
    assert "kampf" in question["antwort"]
    assert "combat" in question["antwort"]


def test_wow_provider_ids_are_stable(monkeypatch):
    provider = WoWQuestionProvider(DummyBot(), language="de")
    monkeypatch.setattr("random.choice", lambda records: records[0])

    first = provider.generate_talent_tree()["id"]
    second = provider.generate_talent_tree()["id"]

    assert first == second


def test_talent_description_disambiguates_class_and_tree(monkeypatch):
    provider = WoWQuestionProvider(DummyBot(), language="de")

    def choose_precision(records):
        for record in records:
            spell = provider._spell_for(record)
            if spell.get("wowhead_id") == 13845:
                return record
        return records[0]

    monkeypatch.setattr("random.choice", choose_precision)

    question = provider.generate_talent_description()

    assert "Schurke" in question["frage"]
    assert "Kampf" in question["frage"]
    assert "präzision" in question["antwort"]
    assert question["source_url"].startswith("https://www.wowhead.com/classic/de/")


def test_talent_class_accepts_all_classes_with_same_named_talent(monkeypatch):
    """The Schwert-Spezialisierung case: Warrior AND Rogue have a talent
    with that name. The question gives no class hint, so both must be
    accepted as correct answers."""
    provider = WoWQuestionProvider(DummyBot(), language="de")

    def pick_warrior_sword_spec(records):
        # Pick the Warrior 'Schwert-Spezialisierung' specifically.
        for record in records:
            if record.get("class_id") != "warrior":
                continue
            spell = provider._spell_for(record)
            name = (spell.get("name") or {}).get("de") or ""
            if "Schwert-Spezialisierung" in name:
                return record
        return records[0]

    monkeypatch.setattr("random.choice", pick_warrior_sword_spec)

    question = provider.generate_talent_class()

    assert question is not None
    answers = question["antwort"]
    # Both classes must be valid answers, in both languages.
    assert "krieger" in answers
    assert "warrior" in answers
    assert "schurke" in answers
    assert "rogue" in answers


def test_item_subclass_plate_accepts_german_alias(monkeypatch):
    """The Plattenrüstung case: 'plate' item must accept the German
    label AND the short alias 'Platte', not just the raw English key."""
    provider = WoWQuestionProvider(DummyBot(), language="de")

    def pick_plate(records):
        for record in records:
            if record.get("item_subclass") == "plate":
                return record
        return records[0]

    monkeypatch.setattr("random.choice", pick_plate)

    question = provider.generate_item_subclass()

    assert question is not None
    answers = question["antwort"]
    assert "plate" in answers
    assert "plattenrüstung" in answers
    assert "platte" in answers


def test_item_subclass_labels_cover_all_live_subclasses():
    """Guard against silent regressions: every item_subclass that actually
    appears in live items.json data must have a German label."""
    from lotus_bot.cogs.quiz.area_providers.wow import ITEM_SUBCLASS_LABELS
    from lotus_bot.bot import load_wow_data

    data = load_wow_data("data/wow/classic_hc")
    live_subclasses = {
        item["item_subclass"]
        for item in data.get("items", [])
        if item.get("item_subclass")
    }
    missing = [sub for sub in live_subclasses if sub not in ITEM_SUBCLASS_LABELS["de"]]
    assert missing == [], f"item subclasses missing a German label: {missing}"
    missing_en = [
        sub for sub in live_subclasses if sub not in ITEM_SUBCLASS_LABELS["en"]
    ]
    assert missing_en == [], f"item subclasses missing an English label: {missing_en}"


def test_racial_trait_description_accepts_both_languages(monkeypatch):
    """The Human 'Diplomacy' case: a player answering 'human' should be
    accepted even though the prompt is in German. Race-name answers must
    carry both DE and EN aliases."""
    provider = WoWQuestionProvider(DummyBot(), language="de")

    def pick_diplomacy(records):
        for record in records:
            spell = provider._spell_for(record)
            if spell.get("id") == "spell.20599":
                return record
        return records[0]

    monkeypatch.setattr("random.choice", pick_diplomacy)

    question = provider.generate_racial_trait_description()

    assert question is not None
    answers = question["antwort"]
    assert "mensch" in answers
    assert "human" in answers


def test_mask_helper_word_boundary():
    """Helper must not partial-match — 'Heal' should not be masked in 'Healing'."""
    provider = WoWQuestionProvider(DummyBot(), language="de")

    masked = provider._mask_answer_in_text(
        "Casts a Healing spell on the target.", ["Heal"]
    )

    # 'Heal' alone never appears as a standalone word, so the text is untouched.
    assert masked == "Casts a Healing spell on the target."

    # When the token IS a full word it gets masked.
    masked2 = provider._mask_answer_in_text("Heal yourself for 100 HP.", ["Heal"])
    assert "Heal " not in masked2
    assert "[diese Fähigkeit]" in masked2


def test_ability_description_masks_answer_token(monkeypatch):
    """The Starshards/Sternensplitter case: the German description literally
    contains the spell name. We must mask it so the question is not trivial."""
    provider = WoWQuestionProvider(DummyBot(), language="de")

    def pick_starshards(records):
        for record in records:
            spell = provider._spell_for(record)
            if spell.get("id") == "spell.10797":
                return record
        return records[0]

    monkeypatch.setattr("random.choice", pick_starshards)

    question = provider.generate_ability_description()

    assert question is not None
    text = question["frage"]
    assert "Sternensplitter" not in text
    assert "[diese Fähigkeit]" in text
    # The actual answer list still contains the spell name — only the
    # rendered description text is masked. _answer_aliases lowercases.
    answers = question["antwort"]
    answers = answers if isinstance(answers, list) else [answers]
    assert any("sternensplitter" in a.casefold() for a in answers)


def test_missing_required_level_does_not_generate_broken_question(monkeypatch):
    data = load_wow_data("data/wow/classic_hc")
    data["spells"] = [
        spell
        for spell in data["spells"]
        if spell["id"] != data["abilities"][0]["spell_id"]
    ]
    provider = WoWQuestionProvider(DummyBot(data), language="de")
    monkeypatch.setattr("random.choice", lambda records: records[0])

    question = provider.generate_ability_required_level()

    assert question is not None
    assert "Ab welchem Level" in question["frage"]


def test_missing_german_description_is_skipped(monkeypatch):
    data = load_wow_data("data/wow/classic_hc")
    talent_spell_ids = {talent["spell_id"] for talent in data["talents"]}
    for spell in data["spells"]:
        if spell["id"] in talent_spell_ids:
            spell["description"].pop("de", None)
    provider = WoWQuestionProvider(DummyBot(data), language="de")
    monkeypatch.setattr("random.choice", lambda records: records[0])

    question = provider.generate_talent_description()

    assert question is None


def test_quiz_eligible_false_records_are_skipped(monkeypatch):
    data = load_wow_data("data/wow/classic_hc")
    for talent in data["talents"]:
        talent["quiz_eligible"] = False
    provider = WoWQuestionProvider(DummyBot(data), language="de")
    monkeypatch.setattr("random.choice", lambda records: records[0])

    assert provider.generate_talent_tree() is None


def test_fallback_descriptions_are_skipped(monkeypatch):
    data = load_wow_data("data/wow/classic_hc")
    talent_spell_ids = {talent["spell_id"] for talent in data["talents"]}
    for spell in data["spells"]:
        if spell["id"] in talent_spell_ids:
            spell["description"]["de"] = spell["name"]["de"]
    provider = WoWQuestionProvider(DummyBot(data), language="de")
    monkeypatch.setattr("random.choice", lambda records: records[0])

    assert provider.generate_talent_description() is None


def test_item_subclass_question_requires_subclass(monkeypatch):
    data = load_wow_data("data/wow/classic_hc")
    for item in data["items"]:
        item.pop("item_subclass", None)
    provider = WoWQuestionProvider(DummyBot(data), language="de")
    monkeypatch.setattr("random.choice", lambda records: records[0])

    assert provider.generate_item_subclass() is None


def test_item_subclass_question_skips_miscellaneous(monkeypatch):
    data = load_wow_data("data/wow/classic_hc")
    for item in data["items"]:
        item["item_subclass"] = "miscellaneous"
    provider = WoWQuestionProvider(DummyBot(data), language="de")
    monkeypatch.setattr("random.choice", lambda records: records[0])

    assert provider.generate_item_subclass() is None


def test_drop_source_question_requires_source_name(monkeypatch):
    data = load_wow_data("data/wow/classic_hc")
    for drop in data["instance_drops"]:
        drop["source_name"] = {"de": "", "en": ""}
    provider = WoWQuestionProvider(DummyBot(data), language="de")
    monkeypatch.setattr("random.choice", lambda records: records[0])

    assert provider.generate_drop_source() is None


def test_filters_exclude_battlegrounds_and_quest_items(monkeypatch):
    data = load_wow_data("data/wow/classic_hc")
    for zone in data["zones"]:
        if zone["type"] == "battleground":
            zone["hardcore_enabled"] = False
    drop_item_ids = {drop["item_id"] for drop in data["instance_drops"]}
    for item in data["items"]:
        if item["id"] in drop_item_ids:
            item["is_quest_item"] = True
    provider = WoWQuestionProvider(DummyBot(data), language="de")
    monkeypatch.setattr("random.choice", lambda records: records[-1])

    zone_question = provider.generate_zone_type()
    drop_question = provider.generate_drop_instance()

    assert "Warsongschlucht" not in zone_question["frage"]
    assert drop_question is None


def test_easy_questions_are_duel_only():
    provider = WoWQuestionProvider(DummyBot(), language="de")

    scheduled = provider.generate_all_types(context="scheduled")
    duel = provider.generate_all_types(context="duel")

    assert not any(q["frage"].startswith("Zu welcher Fraktion") for q in scheduled)
    assert any(q["frage"].startswith("Zu welcher Fraktion") for q in duel)


def test_race_class_can_generate_negative_answer(monkeypatch):
    provider = WoWQuestionProvider(DummyBot(), language="de")

    def choose_last(records):
        return records[-1]

    monkeypatch.setattr("random.choice", choose_last)

    question = provider.generate_race_class_allowed()

    assert "nein" in question["antwort"]


def test_drop_question_uses_item_subclass(monkeypatch):
    provider = WoWQuestionProvider(DummyBot(), language="de")

    def choose_dagger(records):
        for record in records:
            item = provider._item_for(record)
            if item.get("item_subclass") == "dagger":
                return record
        return records[0]

    monkeypatch.setattr("random.choice", choose_dagger)

    question = provider.generate_drop_instance()

    assert "Dolch" in question["frage"]


def test_level_fit_questions_use_yes_no(monkeypatch):
    provider = WoWQuestionProvider(DummyBot(), language="de")

    monkeypatch.setattr("random.choice", lambda records: records[0])
    monkeypatch.setattr("random.randint", lambda low, high: low)

    zone_question = provider.generate_zone_level_fit()
    instance_question = provider.generate_instance_level_fit()

    assert "ja" in zone_question["antwort"]
    assert "ja" in instance_question["antwort"]
