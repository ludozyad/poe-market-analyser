from __future__ import annotations

from pathlib import Path

from poe_market_analyser.domain.models import CraftingRecipe
from poe_market_analyser.infrastructure.importers.yaml_recipe_importer import YamlRecipeImporter
from poe_market_analyser.infrastructure.storage.sqlite_recipe_repository import SqliteRecipeRepository


class RecipeImportService:
    def __init__(self, repository: SqliteRecipeRepository, importer: YamlRecipeImporter | None = None):
        self.repository = repository
        self.importer = importer or YamlRecipeImporter()

    def import_yaml(self, path: str | Path) -> CraftingRecipe:
        recipe = self.importer.import_file(path, validate=True)
        self.repository.save(recipe)
        return recipe

    def import_directory(self, path: str | Path, recursive: bool = True) -> tuple[CraftingRecipe, ...]:
        """Import every YAML recipe file from a directory.

        This is the first step toward a hands-off workflow: a recipe pack can be
        dropped into ``data/recipes`` and imported in one command instead of one
        file at a time.
        """
        directory = Path(path)
        if not directory.exists():
            raise FileNotFoundError(f"Recipe directory does not exist: {directory}")
        if not directory.is_dir():
            raise NotADirectoryError(f"Recipe import path is not a directory: {directory}")

        recipes: list[CraftingRecipe] = []
        for recipe_path in _iter_recipe_paths(directory, recursive=recursive):
            recipes.append(self.import_yaml(recipe_path))
        return tuple(recipes)

    def load_recipe(self, recipe_id: str) -> CraftingRecipe | None:
        document = self.repository.get_document_json(recipe_id)
        if document is None:
            return None
        return self.importer.import_document(document, validate=True)

    def load_all_recipes(self) -> tuple[CraftingRecipe, ...]:
        recipes: list[CraftingRecipe] = []
        for recipe_id in self.repository.list_recipe_ids():
            recipe = self.load_recipe(recipe_id)
            if recipe is not None:
                recipes.append(recipe)
        return tuple(recipes)


def _iter_recipe_paths(directory: Path, recursive: bool) -> tuple[Path, ...]:
    patterns = ("*.yaml", "*.yml")
    paths: list[Path] = []
    for pattern in patterns:
        iterator = directory.rglob(pattern) if recursive else directory.glob(pattern)
        paths.extend(path for path in iterator if path.is_file())
    return tuple(sorted(paths, key=lambda value: (len(value.relative_to(directory).parts), str(value.relative_to(directory)).lower())))
