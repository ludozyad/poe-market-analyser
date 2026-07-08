from pathlib import Path

from poe_market_analyser.application.recipe_market_requirements import collect_required_market_types
from poe_market_analyser.application.recipe_ranking_service import RecipeRankingService
from poe_market_analyser.application.recipe_service import RecipeImportService
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository
from poe_market_analyser.infrastructure.storage.sqlite_recipe_repository import SqliteRecipeRepository

RECIPES_DIR = Path("data/recipes")


def test_research_recipe_pack_imports_multiple_recipes(tmp_path):
    repository = SqliteRecipeRepository(tmp_path / "poe_market.db")
    recipes = RecipeImportService(repository).import_directory(RECIPES_DIR)

    recipe_ids = {recipe.id for recipe in recipes}

    assert len(recipes) >= 6
    assert "poe1_mirage_large_cluster_alt_regal" in recipe_ids
    assert "poe1_mirage_fractured_spell_suppression_boots_essence" in recipe_ids
    assert "poe1_mirage_amethyst_ring_chaos_res_essence" in recipe_ids
    assert "poe1_mirage_eldritch_attack_speed_gloves_essence" in recipe_ids
    assert "poe1_mirage_medium_cluster_flask_alt_regal" in recipe_ids


def test_research_recipe_pack_market_requirements_include_new_categories(tmp_path):
    repository = SqliteRecipeRepository(tmp_path / "poe_market.db")
    recipes = RecipeImportService(repository).import_directory(RECIPES_DIR)

    required_types = collect_required_market_types(recipes)

    assert "ClusterJewel" in required_types
    assert "Essence" in required_types
    assert "BaseType" in required_types
    assert "Currency" in required_types


def test_ranking_rows_include_quality_score_and_flags(tmp_path):
    database = tmp_path / "poe_market.db"
    recipe_repository = SqliteRecipeRepository(database)
    RecipeImportService(recipe_repository).import_directory(RECIPES_DIR)

    rows = RecipeRankingService(recipe_repository, SqliteMarketRepository(database)).rank_recipes(league="Mirage")

    assert len(rows) >= 6
    assert all(0 <= row.confidence_score <= 100 for row in rows)
    assert any("output_price:recipe_import/draft_research_seed" in row.quality_flags for row in rows)
    assert any(any(flag.startswith("recipe_fallback_prices:") for flag in row.quality_flags) for row in rows)
