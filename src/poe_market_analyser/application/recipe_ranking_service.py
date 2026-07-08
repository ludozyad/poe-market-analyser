from __future__ import annotations

from dataclasses import dataclass

from poe_market_analyser.application.output_pricing import resolve_output_price
from poe_market_analyser.application.price_resolver import MarketPriceResolver
from poe_market_analyser.application.profit_engine import SimpleExpectedValueProfitEngine
from poe_market_analyser.application.recipe_quality import assess_recipe_quality
from poe_market_analyser.application.recipe_service import RecipeImportService
from poe_market_analyser.domain.models import CraftingRecipe
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository
from poe_market_analyser.infrastructure.storage.sqlite_recipe_repository import SqliteRecipeRepository


@dataclass(frozen=True)
class RecipeRankingRow:
    recipe_id: str
    recipe_name: str
    league: str
    known_one_attempt_cost_chaos: float
    expected_cost_to_success_chaos: float
    success_assumption_id: str | None
    estimated_sale_price_chaos: float | None
    failed_resale_value_chaos: float
    expected_profit_chaos: float | None
    roi_percent: float | None
    output_price_source: str | None
    output_price_confidence: str | None
    confidence_score: int
    quality_flags: tuple[str, ...]
    missing_price_count: int
    warning_count: int
    missing_price_details: tuple[str, ...]
    warning_details: tuple[str, ...]
    status: str


class RecipeRankingService:
    """Build an automatic recipe ranking over imported recipe definitions.

    Ingredient costs come from the local market cache. Output sale prices come
    from recipe-level output estimates for now; a future TradeProvider can replace
    that source without changing the ranking API.
    """

    def __init__(
        self,
        recipe_repository: SqliteRecipeRepository,
        market_repository: SqliteMarketRepository,
    ):
        self.recipe_repository = recipe_repository
        self.market_repository = market_repository

    def rank_recipes(
        self,
        league: str | None = None,
        max_budget_chaos: float | None = None,
        min_profit_chaos: float | None = None,
        hide_incomplete: bool = False,
        hide_without_output_price: bool = False,
        use_auto_success_assumption: bool = True,
        min_confidence_score: int | None = None,
    ) -> tuple[RecipeRankingRow, ...]:
        recipes = RecipeImportService(self.recipe_repository).load_all_recipes()
        resolver = MarketPriceResolver(self.market_repository)
        engine = SimpleExpectedValueProfitEngine()
        rows: list[RecipeRankingRow] = []

        for recipe in recipes:
            target_league = league or recipe.default_league
            resolution = resolver.resolve_recipe_prices(recipe, league=target_league)
            price_book = resolution.price_book
            one_attempt_cost = price_book.total_known_cost_chaos()
            success_assumption_id = (
                _choose_default_success_assumption_id(recipe)
                if use_auto_success_assumption
                else None
            )
            output_price = resolve_output_price(recipe)
            result = engine.calculate(
                recipe=recipe,
                price_book=price_book,
                estimated_sale_price=output_price.estimated_sale_price_chaos,
                estimated_failed_resale_value=output_price.failed_resale_value_chaos,
                success_assumption_id=success_assumption_id,
            )
            warning_details = _build_warning_details(price_book)
            warning_count = len(warning_details)
            missing_details = _build_missing_price_details(recipe, resolution, result)
            missing_count = len(missing_details)
            expected_cost = result.expected_cost_to_success
            expected_profit = result.expected_profit
            roi_percent = _calculate_roi_percent(expected_profit, expected_cost)
            quality = assess_recipe_quality(
                recipe=recipe,
                price_book=price_book,
                output_price=output_price,
                missing_price_count=missing_count,
                warning_count=warning_count,
            )

            if hide_incomplete and missing_count > 0:
                continue
            if hide_without_output_price and expected_profit is None:
                continue
            if max_budget_chaos is not None and expected_cost > max_budget_chaos:
                continue
            if min_profit_chaos is not None and (expected_profit is None or expected_profit < min_profit_chaos):
                continue
            if min_confidence_score is not None and quality.confidence_score < min_confidence_score:
                continue

            rows.append(
                RecipeRankingRow(
                    recipe_id=recipe.id,
                    recipe_name=recipe.name,
                    league=target_league,
                    known_one_attempt_cost_chaos=one_attempt_cost,
                    expected_cost_to_success_chaos=expected_cost,
                    success_assumption_id=success_assumption_id,
                    estimated_sale_price_chaos=output_price.estimated_sale_price_chaos,
                    failed_resale_value_chaos=output_price.failed_resale_value_chaos,
                    expected_profit_chaos=expected_profit,
                    roi_percent=roi_percent,
                    output_price_source=output_price.source,
                    output_price_confidence=output_price.confidence,
                    confidence_score=quality.confidence_score,
                    quality_flags=quality.flags,
                    missing_price_count=missing_count,
                    warning_count=warning_count,
                    missing_price_details=missing_details,
                    warning_details=warning_details,
                    status=_ranking_status(missing_count, warning_count, output_price.has_sale_price),
                )
            )

        return tuple(sorted(rows, key=_ranking_sort_key))


def _choose_default_success_assumption_id(recipe: CraftingRecipe) -> str | None:
    explicit = recipe.simulation.metadata.get("primary_success_assumption_id")
    if explicit:
        return str(explicit)
    if len(recipe.assumptions) == 1:
        return recipe.assumptions[0].id
    return None


def _ranking_status(missing_count: int, warning_count: int, has_output_price: bool) -> str:
    if missing_count > 0:
        return "incomplete"
    if not has_output_price:
        return "missing_output_price"
    if warning_count > 0:
        return "needs_review"
    return "ready"


def _calculate_roi_percent(expected_profit: float | None, expected_cost: float) -> float | None:
    if expected_profit is None or expected_cost <= 0:
        return None
    return expected_profit / expected_cost * 100.0


def _ranking_sort_key(row: RecipeRankingRow) -> tuple[bool, bool, bool, float, int, float, str]:
    has_missing = row.missing_price_count > 0
    has_no_output = row.expected_profit_chaos is None
    has_warnings = row.warning_count > 0
    profit_sort = row.expected_profit_chaos if row.expected_profit_chaos is not None else float("-inf")
    return (
        has_missing,
        has_no_output,
        has_warnings,
        -profit_sort,
        -row.confidence_score,
        row.expected_cost_to_success_chaos,
        row.recipe_name,
    )


def _build_missing_price_details(recipe: CraftingRecipe, resolution, result) -> tuple[str, ...]:
    details_by_id: dict[str, str] = {}
    for missing in resolution.missing_prices:
        location = ""
        if missing.market_type or missing.market_name:
            location = f" [{missing.market_type or '?'} / {missing.market_name or '?'}]"
        details_by_id[missing.ingredient_id] = f"{missing.ingredient_id}{location}: {missing.reason}"

    ingredient_ids = {ingredient.id for ingredient in recipe.ingredients}
    for missing in result.missing_prices:
        # Ingredient prices are already reported by the resolver; avoid double-counting
        # them in ranking status. Keep non-ingredient missing inputs such as an invalid
        # success assumption id.
        if missing.item_id not in ingredient_ids:
            details_by_id[missing.item_id] = f"{missing.item_id}: {missing.reason}"

    return tuple(details_by_id[key] for key in sorted(details_by_id))


def _build_warning_details(price_book) -> tuple[str, ...]:
    details: list[str] = []
    for entry in price_book.entries:
        for warning in entry.warnings:
            details.append(f"{entry.ingredient_id} [{entry.market_type}/{entry.matched_name}]: {warning}")
    return tuple(details)
