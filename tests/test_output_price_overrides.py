from pathlib import Path

from poe_market_analyser.application.output_pricing import OutputPriceOverride, resolve_output_price
from poe_market_analyser.application.recipe_ranking_service import RecipeRankingService
from poe_market_analyser.application.recipe_service import RecipeImportService
from poe_market_analyser.infrastructure.importers.yaml_recipe_importer import YamlRecipeImporter
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository
from poe_market_analyser.infrastructure.storage.sqlite_recipe_repository import SqliteRecipeRepository

SAMPLE_RECIPE = Path("data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml")


def test_stored_output_override_wins_over_recipe_estimate():
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)
    override = OutputPriceOverride(
        game="poe1",
        league="Mirage",
        recipe_id=recipe.id,
        estimated_sale_price_chaos=999.0,
        failed_resale_value_chaos=12.0,
        confidence="checked_trade_output",
        source="manual_override",
        note="checked comparable listings",
    )

    output = resolve_output_price(recipe, stored_override=override)

    assert output.estimated_sale_price_chaos == 999.0
    assert output.failed_resale_value_chaos == 12.0
    assert output.source == "manual_override"
    assert output.confidence == "checked_trade_output"
    assert output.note == "checked comparable listings"


def test_cli_output_override_still_wins_over_stored_output_override():
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)
    stored = OutputPriceOverride(
        game="poe1",
        league="Mirage",
        recipe_id=recipe.id,
        estimated_sale_price_chaos=999.0,
    )

    output = resolve_output_price(
        recipe,
        sale_price_override_chaos=123.0,
        failed_resale_override_chaos=5.0,
        stored_override=stored,
    )

    assert output.estimated_sale_price_chaos == 123.0
    assert output.failed_resale_value_chaos == 5.0
    assert output.source == "cli_override"


def test_sqlite_recipe_repository_persists_output_price_override(tmp_path):
    repository = SqliteRecipeRepository(tmp_path / "poe_market.db")
    override = OutputPriceOverride(
        game="poe1",
        league="Mirage",
        recipe_id="recipe-a",
        estimated_sale_price_chaos=1500.0,
        failed_resale_value_chaos=100.0,
        confidence="checked_trade_output",
        source="manual_override",
        note="test note",
    )

    repository.save_output_price_override(override)

    loaded = repository.find_output_price_override("recipe-a", league="Mirage")
    assert loaded is not None
    assert loaded.estimated_sale_price_chaos == 1500.0
    assert loaded.failed_resale_value_chaos == 100.0
    assert loaded.confidence == "checked_trade_output"
    assert loaded.note == "test note"


def test_ranking_uses_stored_output_price_override(tmp_path):
    database = tmp_path / "poe_market.db"
    recipe_repository = SqliteRecipeRepository(database)
    recipe = RecipeImportService(recipe_repository).import_yaml(SAMPLE_RECIPE)
    recipe_repository.save_output_price_override(
        OutputPriceOverride(
            game="poe1",
            league="Mirage",
            recipe_id=recipe.id,
            estimated_sale_price_chaos=999_999.0,
            confidence="checked_trade_output",
        )
    )

    rows = RecipeRankingService(recipe_repository, SqliteMarketRepository(database)).rank_recipes(league="Mirage")

    assert len(rows) == 1
    assert rows[0].estimated_sale_price_chaos == 999_999.0
    assert rows[0].output_price_source == "manual_override"
    assert rows[0].output_price_confidence == "checked_trade_output"


def test_ranking_exposes_cost_driver_details(tmp_path):
    database = tmp_path / "poe_market.db"
    recipe_repository = SqliteRecipeRepository(database)
    RecipeImportService(recipe_repository).import_yaml(SAMPLE_RECIPE)

    rows = RecipeRankingService(recipe_repository, SqliteMarketRepository(database)).rank_recipes(league="Mirage")

    assert rows[0].cost_driver_details
    assert any("chaos" in detail for detail in rows[0].cost_driver_details)
