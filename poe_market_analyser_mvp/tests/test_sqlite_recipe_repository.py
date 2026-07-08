from pathlib import Path

from poe_market_analyser.infrastructure.importers.yaml_recipe_importer import YamlRecipeImporter
from poe_market_analyser.infrastructure.storage.sqlite_recipe_repository import SqliteRecipeRepository

SAMPLE_RECIPE = Path("data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml")


def test_repository_saves_and_lists_recipe(tmp_path):
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)
    repository = SqliteRecipeRepository(tmp_path / "poe_market.db")

    repository.save(recipe)
    rows = repository.list_summaries()

    assert len(rows) == 1
    assert rows[0]["recipe_id"] == "poe1_mirage_viper_touch_spiked_gloves"
    assert rows[0]["name"] == "Viper Touch Spiked Gloves"
    assert rows[0]["default_league"] == "Mirage"

    document = repository.get_document_json("poe1_mirage_viper_touch_spiked_gloves")
    assert document is not None
    assert document["schema_version"] == "0.3"
