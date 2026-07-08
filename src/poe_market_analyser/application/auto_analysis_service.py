from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from poe_market_analyser.application.market_service import MarketDataService, MarketFetchSummary
from poe_market_analyser.application.recipe_market_requirements import collect_required_market_types
from poe_market_analyser.application.recipe_ranking_service import RecipeRankingRow, RecipeRankingService
from poe_market_analyser.application.recipe_service import RecipeImportService
from poe_market_analyser.domain.market import MarketDataProvider
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository
from poe_market_analyser.infrastructure.storage.sqlite_recipe_repository import SqliteRecipeRepository


@dataclass(frozen=True)
class AutoRankResult:
    imported_recipe_count: int
    refreshed_market_types: tuple[str, ...]
    fetch_summaries: tuple[MarketFetchSummary, ...]
    ranking_rows: tuple[RecipeRankingRow, ...]


class AutoAnalysisService:
    """High-level orchestration for the desired hands-off workflow.

    One call can import a recipe pack, refresh only market types required by the
    imported recipes, and produce the current ranking. The UI can later call this
    service directly instead of repeating CLI-specific logic.
    """

    def __init__(
        self,
        recipe_repository: SqliteRecipeRepository,
        market_repository: SqliteMarketRepository,
        market_provider: MarketDataProvider,
    ):
        self.recipe_repository = recipe_repository
        self.market_repository = market_repository
        self.market_provider = market_provider

    def import_refresh_and_rank(
        self,
        league: str,
        recipe_dir: str | Path | None = None,
        recursive: bool = True,
        max_budget_chaos: float | None = None,
        min_profit_chaos: float | None = None,
        hide_incomplete: bool = False,
        hide_without_output_price: bool = False,
        use_auto_success_assumption: bool = True,
        min_confidence_score: int | None = None,
        refresh_market: bool = True,
    ) -> AutoRankResult:
        recipe_service = RecipeImportService(self.recipe_repository)
        imported_count = 0
        if recipe_dir is not None:
            imported_count = len(recipe_service.import_directory(recipe_dir, recursive=recursive))

        recipes = recipe_service.load_all_recipes()
        required_types = collect_required_market_types(recipes)
        fetch_summaries: tuple[MarketFetchSummary, ...] = ()
        if refresh_market and required_types:
            fetch_summaries = MarketDataService(self.market_provider, self.market_repository).fetch_and_store_many(
                league=league,
                item_types=required_types,
            )

        ranking_rows = RecipeRankingService(self.recipe_repository, self.market_repository).rank_recipes(
            league=league,
            max_budget_chaos=max_budget_chaos,
            min_profit_chaos=min_profit_chaos,
            hide_incomplete=hide_incomplete,
            hide_without_output_price=hide_without_output_price,
            use_auto_success_assumption=use_auto_success_assumption,
            min_confidence_score=min_confidence_score,
        )
        return AutoRankResult(
            imported_recipe_count=imported_count,
            refreshed_market_types=required_types,
            fetch_summaries=fetch_summaries,
            ranking_rows=ranking_rows,
        )
