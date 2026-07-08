from pathlib import Path

from poe_market_analyser.application.profit_engine import (
    ManualPriceBook,
    SimpleExpectedValueProfitEngine,
)
from poe_market_analyser.infrastructure.importers.yaml_recipe_importer import YamlRecipeImporter

SAMPLE_RECIPE = Path("data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml")


def test_simple_profit_engine_calculates_expected_cost_from_manual_prices():
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)
    price_book = ManualPriceBook.from_plain_prices(
        {ingredient.id: 1.0 for ingredient in recipe.ingredients},
        base_currency="divine",
    )

    result = SimpleExpectedValueProfitEngine().calculate(
        recipe=recipe,
        price_book=price_book,
        estimated_sale_price=200_000.0,
        success_assumption_id="vaal_success_chance",
    )

    assert result.ingredient_cost == 627.0
    assert round(result.expected_attempts) == 168
    assert round(result.expected_cost_to_success) == round(627.0 / 0.005952381)
    assert result.expected_profit == result.estimated_sale_price - result.expected_cost_to_success
    assert result.missing_prices == ()


def test_simple_profit_engine_reports_missing_prices():
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)
    price_book = ManualPriceBook.from_plain_prices(
        {
            "gilded_fossil": 0.1,
        },
        base_currency="divine",
    )

    result = SimpleExpectedValueProfitEngine().calculate(
        recipe=recipe,
        price_book=price_book,
    )

    assert {missing.item_id for missing in result.missing_prices} == {
        ingredient.id for ingredient in recipe.ingredients if ingredient.id != "gilded_fossil"
    }
