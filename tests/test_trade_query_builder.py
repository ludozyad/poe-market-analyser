from pathlib import Path

from poe_market_analyser.application.trade_query_builder import build_trade_query_from_recipe
from poe_market_analyser.infrastructure.importers.yaml_recipe_importer import YamlRecipeImporter

SAMPLE_RECIPE = Path("data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml")


def test_builds_base_query_from_recipe_target_when_no_trade_query_configured():
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)

    query = build_trade_query_from_recipe(recipe)

    assert query["sort"] == {"price": "asc"}
    assert query["query"]["status"]["option"] == "online"
    assert query["query"]["type"] == "Spiked Gloves"
    filters = query["query"]["filters"]
    assert filters["misc_filters"]["filters"]["ilvl"] == {"min": 86}
    assert filters["misc_filters"]["filters"]["corrupted"] == {"option": "true"}
    assert filters["misc_filters"]["filters"]["hunter_item"] == {"option": "true"}
    assert filters["misc_filters"]["filters"]["warlord_item"] == {"option": "true"}
    assert filters["type_filters"]["filters"]["category"] == {"option": "armour.gloves"}


def test_configured_trade_query_from_pricing_output_metadata_wins():
    document = YamlRecipeImporter().import_file(SAMPLE_RECIPE).raw
    document = dict(document)
    document["pricing"] = dict(document["pricing"])
    document["pricing"]["output"] = dict(document["pricing"]["output"])
    document["pricing"]["output"]["trade_search"] = {
        "query": {
            "query": {"status": {"option": "any"}, "name": "Some Unique"},
            "sort": {"price": "asc"},
        }
    }
    recipe = YamlRecipeImporter().import_document(document)

    query = build_trade_query_from_recipe(recipe)

    assert query["query"]["name"] == "Some Unique"
    assert query["query"]["status"]["option"] == "any"
