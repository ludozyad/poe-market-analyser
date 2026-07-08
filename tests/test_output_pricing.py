from pathlib import Path

from poe_market_analyser.application.output_pricing import resolve_output_price
from poe_market_analyser.infrastructure.importers.yaml_recipe_importer import YamlRecipeImporter

SAMPLE_RECIPE = Path("data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml")


def test_resolves_recipe_output_price_from_imported_estimate():
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)

    output = resolve_output_price(recipe)

    assert output.estimated_sale_price_chaos == 350000.0
    assert output.failed_resale_value_chaos == 0.0
    assert output.source == "recipe_import"
    assert output.confidence == "draft_manual"


def test_cli_like_output_price_override_wins_over_recipe_estimate():
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)

    output = resolve_output_price(recipe, sale_price_override_chaos=123.0, failed_resale_override_chaos=5.0)

    assert output.estimated_sale_price_chaos == 123.0
    assert output.failed_resale_value_chaos == 5.0
    assert output.source == "cli_override"
