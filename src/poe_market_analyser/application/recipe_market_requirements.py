from __future__ import annotations

from dataclasses import dataclass

from poe_market_analyser.domain.models import CraftingRecipe, Ingredient


@dataclass(frozen=True)
class MarketRequirement:
    item_type: str
    ingredient_count: int
    recipe_count: int


def collect_required_market_types(recipes: tuple[CraftingRecipe, ...] | list[CraftingRecipe]) -> tuple[str, ...]:
    """Return poe.ninja item types needed by imported recipes.

    Recipe files should normally provide ``market_type`` per priced ingredient.
    Conservative fallbacks keep early MVP recipes usable while still making the
    required market refresh automatic.
    """
    item_types: set[str] = set()
    for recipe in recipes:
        for ingredient in recipe.ingredients:
            if not ingredient.price_lookup:
                continue
            item_type = infer_ingredient_market_type(ingredient)
            if item_type:
                item_types.add(item_type)
    return tuple(sorted(item_types))


def summarize_market_requirements(recipes: tuple[CraftingRecipe, ...] | list[CraftingRecipe]) -> tuple[MarketRequirement, ...]:
    recipe_ids_by_type: dict[str, set[str]] = {}
    ingredient_count_by_type: dict[str, int] = {}
    for recipe in recipes:
        for ingredient in recipe.ingredients:
            if not ingredient.price_lookup:
                continue
            item_type = infer_ingredient_market_type(ingredient)
            if not item_type:
                continue
            recipe_ids_by_type.setdefault(item_type, set()).add(recipe.id)
            ingredient_count_by_type[item_type] = ingredient_count_by_type.get(item_type, 0) + 1

    return tuple(
        MarketRequirement(
            item_type=item_type,
            ingredient_count=ingredient_count_by_type[item_type],
            recipe_count=len(recipe_ids_by_type[item_type]),
        )
        for item_type in sorted(recipe_ids_by_type)
    )


def infer_ingredient_market_type(ingredient: Ingredient) -> str | None:
    explicit = _optional_str(ingredient.metadata.get("market_type"))
    if explicit:
        return explicit
    if ingredient.type == "beast":
        return "Beast"
    if ingredient.type == "base_item":
        return "BaseType"
    return None


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None
