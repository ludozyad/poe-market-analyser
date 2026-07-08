from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from poe_market_analyser.domain.models import (
    AnyOfAffixGroup,
    Assumption,
    CraftingCheckpoint,
    CraftingFlow,
    CraftingRecipe,
    CraftingStep,
    Ingredient,
    LeagueScope,
    PricingConfig,
    RecipeInfo,
    SimulationConfig,
    TargetBase,
    TargetItem,
    TextMod,
)
from poe_market_analyser.domain.validation import ensure_valid_recipe


class YamlRecipeImportError(ValueError):
    pass


class YamlRecipeImporter:
    def import_file(self, path: str | Path, validate: bool = True) -> CraftingRecipe:
        file_path = Path(path)
        if not file_path.exists():
            raise YamlRecipeImportError(f"Recipe file does not exist: {file_path}")
        if not file_path.is_file():
            raise YamlRecipeImportError(f"Recipe path is not a file: {file_path}")

        with file_path.open("r", encoding="utf-8") as file:
            document = yaml.safe_load(file) or {}

        if not isinstance(document, dict):
            raise YamlRecipeImportError("Recipe YAML root must be a mapping/object.")

        recipe = self.import_document(document, validate=validate)
        return recipe

    def import_document(self, document: dict[str, Any], validate: bool = True) -> CraftingRecipe:
        recipe = self._map_document(document)
        if validate:
            ensure_valid_recipe(recipe)
        return recipe

    def _map_document(self, document: dict[str, Any]) -> CraftingRecipe:
        recipe_section = _required_mapping(document, "recipe")
        target_section = _required_mapping(document, "target")
        pricing_section = _required_mapping(document, "pricing")
        flow_section = _required_mapping(document, "crafting_flow")

        league_scope_section = _required_mapping(recipe_section, "league_scope")
        recipe_info = RecipeInfo(
            id=str(recipe_section.get("id", "")),
            name=str(recipe_section.get("name", "")),
            game=str(recipe_section.get("game", "")),
            league_scope=LeagueScope(
                default_league=str(league_scope_section.get("default_league", "")),
                compatible_with_other_leagues=bool(league_scope_section.get("compatible_with_other_leagues", False)),
            ),
            status=str(recipe_section.get("status", "draft")),
        )

        base_section = _required_mapping(target_section, "base")
        target_base = TargetBase(
            item_class=str(base_section.get("item_class", "")),
            base_type=str(base_section.get("base_type", "")),
            item_level_min=_optional_int(base_section.get("item_level_min")),
            influences=tuple(str(value) for value in base_section.get("influences", []) or []),
            corrupted=bool(base_section.get("corrupted", False)),
        )

        implicits_section = _optional_mapping(target_section, "implicits")
        affixes_section = _optional_mapping(target_section, "affixes")

        target = TargetItem(
            base=target_base,
            required_implicits=tuple(
                _map_text_mod(mod) for mod in implicits_section.get("required", []) or []
            ),
            required_affixes=tuple(
                _map_text_mod(mod) for mod in affixes_section.get("required", []) or []
            ),
            any_of_affix_groups=tuple(
                _map_any_of_group(group) for group in affixes_section.get("any_of", []) or []
            ),
        )

        pricing = PricingConfig(
            base_currency=str(pricing_section.get("base_currency", "")),
            price_sources=tuple(str(value) for value in pricing_section.get("price_sources", []) or []),
        )

        ingredients = tuple(
            _map_ingredient(item) for item in document.get("ingredients", []) or []
        )

        crafting_flow = CraftingFlow(
            checkpoints=tuple(
                _map_checkpoint(item) for item in flow_section.get("checkpoints", []) or []
            ),
            steps=tuple(_map_step(item) for item in flow_section.get("steps", []) or []),
        )

        assumptions = tuple(
            _map_assumption(item) for item in document.get("assumptions", []) or []
        )

        simulation_section = _optional_mapping(document, "simulation")
        simulation = SimulationConfig(
            mode=str(simulation_section.get("mode", "expected_value")),
            include_failed_vaal_resale=bool(simulation_section.get("include_failed_vaal_resale", False)),
            default_monte_carlo_attempts=int(simulation_section.get("default_monte_carlo_attempts", 10000)),
            metadata=_without_keys(
                simulation_section,
                {"mode", "include_failed_vaal_resale", "default_monte_carlo_attempts"},
            ),
        )

        return CraftingRecipe(
            schema_version=str(document.get("schema_version", "")),
            recipe=recipe_info,
            target=target,
            pricing=pricing,
            ingredients=ingredients,
            crafting_flow=crafting_flow,
            assumptions=assumptions,
            simulation=simulation,
            raw=document,
        )


def _required_mapping(document: dict[str, Any], key: str) -> dict[str, Any]:
    value = document.get(key)
    if not isinstance(value, dict):
        raise YamlRecipeImportError(f"Required section '{key}' must be a mapping/object.")
    return value


def _optional_mapping(document: dict[str, Any], key: str) -> dict[str, Any]:
    value = document.get(key, {})
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise YamlRecipeImportError(f"Optional section '{key}' must be a mapping/object when provided.")
    return value


def _map_text_mod(document: dict[str, Any]) -> TextMod:
    if not isinstance(document, dict):
        raise YamlRecipeImportError("Mod entry must be a mapping/object.")
    return TextMod(
        id=str(document.get("id", "")),
        text=str(document.get("text", "")),
        stat_id=_optional_str(document.get("stat_id")),
        metadata=_without_keys(document, {"id", "text", "stat_id"}),
    )


def _map_any_of_group(document: dict[str, Any]) -> AnyOfAffixGroup:
    if not isinstance(document, dict):
        raise YamlRecipeImportError("Any-of affix group must be a mapping/object.")
    return AnyOfAffixGroup(
        group_id=str(document.get("group_id", "")),
        min_required=int(document.get("min_required", 1)),
        options=tuple(_map_text_mod(item) for item in document.get("options", []) or []),
    )


def _map_ingredient(document: dict[str, Any]) -> Ingredient:
    if not isinstance(document, dict):
        raise YamlRecipeImportError("Ingredient entry must be a mapping/object.")
    return Ingredient(
        id=str(document.get("id", "")),
        type=str(document.get("type", "")),
        price_lookup=bool(document.get("price_lookup", True)),
        quantity=float(document.get("quantity", 1.0)),
        metadata=_without_keys(document, {"id", "type", "price_lookup", "quantity"}),
    )


def _map_checkpoint(document: dict[str, Any]) -> CraftingCheckpoint:
    if not isinstance(document, dict):
        raise YamlRecipeImportError("Checkpoint entry must be a mapping/object.")
    return CraftingCheckpoint(
        id=str(document.get("id", "")),
        metadata=_without_keys(document, {"id"}),
    )


def _map_step(document: dict[str, Any]) -> CraftingStep:
    if not isinstance(document, dict):
        raise YamlRecipeImportError("Crafting step entry must be a mapping/object.")
    return CraftingStep(
        id=str(document.get("id", "")),
        type=str(document.get("type", "")),
        metadata=_without_keys(document, {"id", "type"}),
    )


def _map_assumption(document: dict[str, Any]) -> Assumption:
    if not isinstance(document, dict):
        raise YamlRecipeImportError("Assumption entry must be a mapping/object.")
    return Assumption(
        id=str(document.get("id", "")),
        value=float(document.get("value", 0)),
        text=_optional_str(document.get("text")),
        confidence=str(document.get("confidence", "unknown")),
        source=str(document.get("source", "manual")),
        can_override=bool(document.get("can_override", True)),
        metadata=_without_keys(document, {"id", "value", "text", "confidence", "source", "can_override"}),
    )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _without_keys(document: dict[str, Any], keys: set[str]) -> dict[str, Any]:
    return {key: value for key, value in document.items() if key not in keys}
