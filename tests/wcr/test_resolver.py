from cogs.wcr import resolver


def test_build_lookup_tables_contains_tokens(wcr_data):
    languages = wcr_data["locals"]
    unit_name_map, id_name_map, token_index = resolver.build_lookup_tables(languages)
    assert "de" in unit_name_map
    assert "sylvanas" in token_index["de"]


def test_find_unit_id_by_name(wcr_data):
    languages = wcr_data["locals"]
    maps = resolver.build_lookup_tables(languages)
    unit_id, lang = resolver.find_unit_id_by_name(
        "sylvanas",
        "de",
        *maps,
    )
    assert unit_id == "62"
    assert lang == "de"
