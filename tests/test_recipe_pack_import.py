from pathlib import Path

import yaml

from poe_market_analyser.application.recipe_service import RecipeImportService
from poe_market_analyser.infrastructure.storage.sqlite_recipe_repository import SqliteRecipeRepository

SAMPLE_RECIPE = Path("data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml")


def _write_recipe_copy(source: Path, destination: Path, recipe_id: str, name: str) -> None:
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    document["recipe"]["id"] = recipe_id
    document["recipe"]["name"] = name
    destination.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")


def test_recipe_import_service_imports_all_yaml_files_from_directory(tmp_path):
    recipes_dir = tmp_path / "recipes"
    nested_dir = recipes_dir / "nested"
    nested_dir.mkdir(parents=True)
    _write_recipe_copy(SAMPLE_RECIPE, recipes_dir / "recipe_a.yaml", "recipe_a", "Recipe A")
    _write_recipe_copy(SAMPLE_RECIPE, nested_dir / "recipe_b.yml", "recipe_b", "Recipe B")
    (recipes_dir / "ignore.txt").write_text("not yaml", encoding="utf-8")

    repository = SqliteRecipeRepository(tmp_path / "poe_market.db")
    imported = RecipeImportService(repository).import_directory(recipes_dir)

    assert [recipe.id for recipe in imported] == ["recipe_a", "recipe_b"]
    assert set(repository.list_recipe_ids()) == {"recipe_a", "recipe_b"}


def test_recipe_import_service_can_import_directory_without_recursion(tmp_path):
    recipes_dir = tmp_path / "recipes"
    nested_dir = recipes_dir / "nested"
    nested_dir.mkdir(parents=True)
    _write_recipe_copy(SAMPLE_RECIPE, recipes_dir / "recipe_a.yaml", "recipe_a", "Recipe A")
    _write_recipe_copy(SAMPLE_RECIPE, nested_dir / "recipe_b.yml", "recipe_b", "Recipe B")

    repository = SqliteRecipeRepository(tmp_path / "poe_market.db")
    imported = RecipeImportService(repository).import_directory(recipes_dir, recursive=False)

    assert [recipe.id for recipe in imported] == ["recipe_a"]
