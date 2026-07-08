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
        {
            "hunter_spiked_gloves_ilvl86": 0.5,
            "gilded_fossil": 0.1,
            "craicic_chimeral": 1.4,
        },
        base_currency="divine",
    )

    result = SimpleExpectedValueProfitEngine().calculate(
        recipe=recipe,
        price_book=price_book,
        estimated_sale_price=500.0,
        success_assumption_id="vaal_success_chance",
    )

    assert result.ingredient_cost == 2.0
    assert round(result.expected_attempts) == 168
    assert round(result.expected_cost_to_success) == 336
    assert round(result.expected_profit) == 164
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
        "hunter_spiked_gloves_ilvl86",
        "craicic_chimeral",
    }
