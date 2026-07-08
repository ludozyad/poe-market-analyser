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
