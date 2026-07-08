from __future__ import annotations

import json
import sqlite3
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

    def list_recipe_ids(self) -> list[str]:
        self.initialize()
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT recipe_id
                FROM crafting_recipes
                ORDER BY imported_at_utc DESC, recipe_id ASC
                """
            ).fetchall()
        return [str(row[0]) for row in rows]

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



def _pricing_to_jsonable_dict(recipe: CraftingRecipe) -> dict[str, Any]:
    pricing: dict[str, Any] = {
        "base_currency": recipe.pricing.base_currency,
        "price_sources": list(recipe.pricing.price_sources),
    }
    if recipe.pricing.output is not None:
        output = recipe.pricing.output
        pricing["output"] = {
            "mode": output.mode,
            "estimated_sale_price_chaos": output.estimated_sale_price_chaos,
            "failed_resale_value_chaos": output.failed_resale_value_chaos,
            "confidence": output.confidence,
            "source": output.source,
            "note": output.note,
            **output.metadata,
        }
    return pricing

def _recipe_to_jsonable_dict(recipe: CraftingRecipe) -> dict[str, Any]:
    # Store the original YAML-shaped document when available. This keeps the
    # database document importable by YamlRecipeImporter and avoids coupling the
    # repository to dataclass internals.
    if recipe.raw:
        return recipe.raw
    return {
        "schema_version": recipe.schema_version,
        "recipe": {
            "id": recipe.id,
            "name": recipe.name,
            "game": recipe.game,
            "league_scope": {
                "default_league": recipe.default_league,
                "compatible_with_other_leagues": recipe.recipe.league_scope.compatible_with_other_leagues,
            },
            "status": recipe.recipe.status,
        },
        "target": {
            "base": {
                "item_class": recipe.target.base.item_class,
                "base_type": recipe.target.base.base_type,
                "item_level_min": recipe.target.base.item_level_min,
                "influences": list(recipe.target.base.influences),
                "corrupted": recipe.target.base.corrupted,
            },
        },
        "pricing": _pricing_to_jsonable_dict(recipe),
        "ingredients": [
            {
                "id": ingredient.id,
                "type": ingredient.type,
                "price_lookup": ingredient.price_lookup,
                "quantity": ingredient.quantity,
                **ingredient.metadata,
            }
            for ingredient in recipe.ingredients
        ],
        "crafting_flow": {
            "checkpoints": [{"id": checkpoint.id, **checkpoint.metadata} for checkpoint in recipe.crafting_flow.checkpoints],
            "steps": [{"id": step.id, "type": step.type, **step.metadata} for step in recipe.crafting_flow.steps],
        },
        "assumptions": [
            {
                "id": assumption.id,
                "value": assumption.value,
                "text": assumption.text,
                "confidence": assumption.confidence,
                "source": assumption.source,
                "can_override": assumption.can_override,
                **assumption.metadata,
            }
            for assumption in recipe.assumptions
        ],
        "simulation": {
            "mode": recipe.simulation.mode,
            "include_failed_vaal_resale": recipe.simulation.include_failed_vaal_resale,
            "default_monte_carlo_attempts": recipe.simulation.default_monte_carlo_attempts,
            **recipe.simulation.metadata,
        },
    }
