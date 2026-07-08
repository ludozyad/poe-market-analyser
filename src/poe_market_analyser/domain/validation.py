from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from poe_market_analyser.domain.models import CraftingRecipe, SUPPORTED_SCHEMA_VERSION


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    severity: str = "error"


class RecipeValidationError(ValueError):
    def __init__(self, issues: Iterable[ValidationIssue]):
        self.issues = tuple(issues)
        message = "; ".join(f"{issue.path}: {issue.message}" for issue in self.issues)
        super().__init__(message)


def validate_recipe(recipe: CraftingRecipe) -> tuple[ValidationIssue, ...]:
    issues: list[ValidationIssue] = []

    if recipe.schema_version != SUPPORTED_SCHEMA_VERSION:
        issues.append(
            ValidationIssue(
                "schema_version",
                f"Unsupported schema version '{recipe.schema_version}'. Expected '{SUPPORTED_SCHEMA_VERSION}'.",
            )
        )

    if not recipe.recipe.id:
        issues.append(ValidationIssue("recipe.id", "Recipe id is required."))
    if not recipe.recipe.name:
        issues.append(ValidationIssue("recipe.name", "Recipe name is required."))
    if recipe.recipe.game != "poe1":
        issues.append(
            ValidationIssue(
                "recipe.game",
                "MVP supports only 'poe1'. Keep other games behind future adapters.",
            )
        )
    if not recipe.recipe.league_scope.default_league:
        issues.append(ValidationIssue("recipe.league_scope.default_league", "Default league is required."))

    if not recipe.target.base.item_class:
        issues.append(ValidationIssue("target.base.item_class", "Target item class is required."))
    if not recipe.target.base.base_type:
        issues.append(ValidationIssue("target.base.base_type", "Target base type is required."))
    if recipe.target.base.item_level_min is not None and recipe.target.base.item_level_min <= 0:
        issues.append(ValidationIssue("target.base.item_level_min", "Item level must be greater than 0."))

    _check_unique_ids(issues, "ingredients", [ingredient.id for ingredient in recipe.ingredients])
    for index, ingredient in enumerate(recipe.ingredients):
        path = f"ingredients[{index}]"
        if not ingredient.id:
            issues.append(ValidationIssue(f"{path}.id", "Ingredient id is required."))
        if not ingredient.type:
            issues.append(ValidationIssue(f"{path}.type", "Ingredient type is required."))
        if ingredient.quantity <= 0:
            issues.append(ValidationIssue(f"{path}.quantity", "Ingredient quantity must be greater than 0."))
        if ingredient.expected_quantity is not None and ingredient.expected_quantity <= 0:
            issues.append(
                ValidationIssue(
                    f"{path}.expected_quantity",
                    "Ingredient expected_quantity must be greater than 0 when provided.",
                )
            )
        if not ingredient.quantity_mode:
            issues.append(ValidationIssue(f"{path}.quantity_mode", "Ingredient quantity_mode is required."))

    _check_unique_ids(issues, "crafting_flow.steps", [step.id for step in recipe.crafting_flow.steps])
    for index, step in enumerate(recipe.crafting_flow.steps):
        path = f"crafting_flow.steps[{index}]"
        if not step.id:
            issues.append(ValidationIssue(f"{path}.id", "Step id is required."))
        if not step.type:
            issues.append(ValidationIssue(f"{path}.type", "Step type is required."))

    _check_unique_ids(issues, "crafting_flow.checkpoints", [checkpoint.id for checkpoint in recipe.crafting_flow.checkpoints])

    _check_unique_ids(issues, "assumptions", [assumption.id for assumption in recipe.assumptions])
    for index, assumption in enumerate(recipe.assumptions):
        path = f"assumptions[{index}]"
        if not assumption.id:
            issues.append(ValidationIssue(f"{path}.id", "Assumption id is required."))
        if assumption.value <= 0:
            issues.append(ValidationIssue(f"{path}.value", "Assumption value must be greater than 0."))
        if not assumption.confidence:
            issues.append(ValidationIssue(f"{path}.confidence", "Assumption confidence is required."))

    if not recipe.pricing.base_currency:
        issues.append(ValidationIssue("pricing.base_currency", "Base currency is required."))
    if not recipe.pricing.price_sources:
        issues.append(ValidationIssue("pricing.price_sources", "At least one price source is required."))

    if recipe.pricing.output is not None:
        if not recipe.pricing.output.mode:
            issues.append(ValidationIssue("pricing.output.mode", "Output pricing mode is required when output pricing is provided."))
        if recipe.pricing.output.estimated_sale_price_chaos is not None and recipe.pricing.output.estimated_sale_price_chaos < 0:
            issues.append(ValidationIssue("pricing.output.estimated_sale_price_chaos", "Estimated sale price cannot be negative."))
        if recipe.pricing.output.failed_resale_value_chaos < 0:
            issues.append(ValidationIssue("pricing.output.failed_resale_value_chaos", "Failed resale value cannot be negative."))
        if not recipe.pricing.output.confidence:
            issues.append(ValidationIssue("pricing.output.confidence", "Output pricing confidence is required."))

    if recipe.simulation.default_monte_carlo_attempts <= 0:
        issues.append(
            ValidationIssue(
                "simulation.default_monte_carlo_attempts",
                "Default Monte Carlo attempts must be greater than 0.",
            )
        )

    return tuple(issues)


def ensure_valid_recipe(recipe: CraftingRecipe) -> None:
    issues = validate_recipe(recipe)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        raise RecipeValidationError(errors)


def _check_unique_ids(issues: list[ValidationIssue], path: str, ids: list[str]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in ids:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    for duplicate in sorted(duplicates):
        if duplicate:
            issues.append(ValidationIssue(path, f"Duplicate id '{duplicate}'."))
