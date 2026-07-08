from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Any

from poe_market_analyser.domain.models import CraftingRecipe


class SqliteRecipeRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS crafting_recipes (
                    recipe_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    game TEXT NOT NULL,
                    default_league TEXT NOT NULL,
                    status TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    document_json TEXT NOT NULL,
                    imported_at_utc TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS crafting_recipe_ingredients (
                    recipe_id TEXT NOT NULL,
                    ingredient_id TEXT NOT NULL,
                    ingredient_type TEXT NOT NULL,
                    quantity REAL NOT NULL,
                    price_lookup INTEGER NOT NULL,
                    PRIMARY KEY (recipe_id, ingredient_id),
                    FOREIGN KEY (recipe_id) REFERENCES crafting_recipes(recipe_id) ON DELETE CASCADE
                )
                """
            )
            connection.commit()

    def save(self, recipe: CraftingRecipe) -> None:
        self.initialize()
        document_json = json.dumps(_recipe_to_jsonable_dict(recipe), ensure_ascii=False, sort_keys=True)
        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                INSERT INTO crafting_recipes (
                    recipe_id,
                    name,
                    game,
                    default_league,
                    status,
                    schema_version,
                    document_json,
                    imported_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(recipe_id) DO UPDATE SET
                    name = excluded.name,
                    game = excluded.game,
                    default_league = excluded.default_league,
                    status = excluded.status,
                    schema_version = excluded.schema_version,
                    document_json = excluded.document_json,
                    imported_at_utc = CURRENT_TIMESTAMP
                """,
                (
                    recipe.id,
                    recipe.name,
                    recipe.game,
                    recipe.default_league,
                    recipe.recipe.status,
                    recipe.schema_version,
                    document_json,
                ),
            )
            connection.execute(
                "DELETE FROM crafting_recipe_ingredients WHERE recipe_id = ?",
                (recipe.id,),
            )
            connection.executemany(
                """
                INSERT INTO crafting_recipe_ingredients (
                    recipe_id,
                    ingredient_id,
                    ingredient_type,
                    quantity,
                    price_lookup
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        recipe.id,
                        ingredient.id,
                        ingredient.type,
                        ingredient.quantity,
                        1 if ingredient.price_lookup else 0,
                    )
                    for ingredient in recipe.ingredients
                ],
            )
            connection.commit()

    def list_summaries(self) -> list[dict[str, Any]]:
        self.initialize()
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT
                    recipe_id,
                    name,
                    game,
                    default_league,
                    status,
                    schema_version,
                    imported_at_utc
                FROM crafting_recipes
                ORDER BY imported_at_utc DESC, recipe_id ASC
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_document_json(self, recipe_id: str) -> dict[str, Any] | None:
        self.initialize()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT document_json FROM crafting_recipes WHERE recipe_id = ?",
                (recipe_id,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)


def _recipe_to_jsonable_dict(recipe: CraftingRecipe) -> dict[str, Any]:
    result = asdict(recipe)
    # The original raw YAML can duplicate the normalized object and may contain
    # non-normalized structures. Keep it, but ensure everything is JSON serializable.
    return result
