from pathlib import Path

from poe_market_analyser.domain.validation import validate_recipe
from poe_market_analyser.infrastructure.importers.yaml_recipe_importer import YamlRecipeImporter

SAMPLE_RECIPE = Path("data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml")


def test_cleaned_recipe_has_no_validation_issues():
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE, validate=False)

    issues = validate_recipe(recipe)

    assert issues == ()
