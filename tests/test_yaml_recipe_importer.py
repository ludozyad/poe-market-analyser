from pathlib import Path

from poe_market_analyser.infrastructure.importers.yaml_recipe_importer import YamlRecipeImporter

SAMPLE_RECIPE = Path("data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml")


def test_imports_cleaned_viper_touch_recipe():
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)

    assert recipe.schema_version == "0.3"
    assert recipe.id == "poe1_mirage_viper_touch_spiked_gloves"
    assert recipe.name == "Viper Touch Spiked Gloves"
    assert recipe.game == "poe1"
    assert recipe.default_league == "Mirage"

    assert recipe.target.base.item_class == "Gloves"
    assert recipe.target.base.base_type == "Spiked Gloves"
    assert recipe.target.base.item_level_min == 86
    assert recipe.target.base.influences == ("Hunter", "Warlord")
    assert recipe.target.base.corrupted is True

    assert len(recipe.ingredients) == 13
    assert {ingredient.id for ingredient in recipe.ingredients} >= {
        "hunter_spiked_gloves_ilvl86",
        "gilded_fossil",
        "orb_of_alteration",
        "orb_of_dominance",
        "awakeners_orb",
        "veiled_exalted_orb",
        "vaal_orb",
        "craicic_chimeral",
    }
    alteration = next(ingredient for ingredient in recipe.ingredients if ingredient.id == "orb_of_alteration")
    assert alteration.quantity_mode == "expected"
    assert alteration.expected_quantity == 600.0
    assert alteration.resolved_quantity == 600.0

    assert len(recipe.crafting_flow.steps) == 6
    assert recipe.assumption_by_id("vaal_success_chance") is not None


def test_import_preserves_any_of_affix_group():
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)

    groups = recipe.target.any_of_affix_groups
    assert len(groups) == 1
    assert groups[0].group_id == "desired_veiled_suffix"
    assert groups[0].min_required == 1
    assert {option.id for option in groups[0].options} == {
        "global_crit_chance",
        "elemental_damage_if_crit_recently",
    }


def test_import_preserves_market_metadata():
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)

    ingredient = next(item for item in recipe.ingredients if item.id == "gilded_fossil")

    assert ingredient.metadata["market_name"] == "Gilded Fossil"
    assert ingredient.metadata["market_type"] == "Fossil"


def test_import_preserves_recipe_output_pricing():
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)

    assert recipe.pricing.output is not None
    assert recipe.pricing.output.mode == "manual_estimate"
    assert recipe.pricing.output.estimated_sale_price_chaos == 350000.0
    assert recipe.pricing.output.failed_resale_value_chaos == 0.0
    assert recipe.pricing.output.confidence == "draft_manual"
    assert recipe.pricing.output.source == "recipe_import"
    assert recipe.simulation.metadata["primary_success_assumption_id"] == "vaal_success_chance"
