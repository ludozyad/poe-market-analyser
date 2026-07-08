from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Protocol

from poe_market_analyser.application.output_pricing import OutputPriceOverride
from poe_market_analyser.application.trade_query_builder import build_trade_query_from_recipe
from poe_market_analyser.domain.models import CraftingRecipe
from poe_market_analyser.domain.trade import TradeListing, TradePriceEstimate, TradeSearchResult
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository


class TradeSearchProvider(Protocol):
    def search(self, league: str, query: dict, fetch_limit: int = 20) -> TradeSearchResult:
        ...


@dataclass(frozen=True)
class TradePriceEstimatorConfig:
    max_results: int = 20
    sample_size: int = 5
    online_only: bool = True


class TradeCurrencyConverter:
    def __init__(self, market_repository: SqliteMarketRepository, game: str = "poe1"):
        self.market_repository = market_repository
        self.game = game

    def to_chaos(self, amount: float, currency: str, league: str) -> float | None:
        key = _normalize_trade_currency(currency)
        if key in {"chaos", "chaos-orb"}:
            return amount
        market_name = TRADE_CURRENCY_TO_MARKET_NAME.get(key)
        if market_name is None:
            return None
        market_price = self.market_repository.find_latest_price(
            league=league,
            item_type="Currency",
            name=market_name,
            game=self.game,
        )
        if market_price is None:
            return None
        return amount * market_price.chaos_value


class TradePriceEstimator:
    def __init__(
        self,
        provider: TradeSearchProvider,
        market_repository: SqliteMarketRepository,
        game: str = "poe1",
    ):
        self.provider = provider
        self.converter = TradeCurrencyConverter(market_repository, game=game)
        self.game = game

    def estimate_recipe_output(
        self,
        recipe: CraftingRecipe,
        league: str,
        config: TradePriceEstimatorConfig | None = None,
    ) -> TradePriceEstimate:
        config = config or TradePriceEstimatorConfig()
        query = build_trade_query_from_recipe(recipe, online_only=config.online_only)
        search = self.provider.search(league=league, query=query, fetch_limit=config.max_results)

        chaos_prices: list[float] = []
        skipped = 0
        for listing in search.listings:
            chaos = self._listing_price_chaos(listing, league)
            if chaos is None:
                skipped += 1
                continue
            chaos_prices.append(chaos)

        chaos_prices.sort()
        sample = chaos_prices[: max(1, config.sample_size)]
        estimate = median(sample) if sample else None
        confidence = _estimate_confidence(sample, search.total_result_count, skipped)
        note = _estimate_note(sample, search.total_result_count, skipped)
        return TradePriceEstimate(
            recipe_id=recipe.id,
            league=league,
            estimated_sale_price_chaos=estimate,
            min_price_chaos=min(chaos_prices) if chaos_prices else None,
            median_price_chaos=median(sample) if sample else None,
            mean_price_chaos=mean(sample) if sample else None,
            used_listing_count=len(sample),
            total_result_count=search.total_result_count,
            skipped_listing_count=skipped,
            query_id=search.query_id,
            search_url=search.search_url,
            confidence=confidence,
            note=note,
            listing_prices_chaos=tuple(sample),
        )

    def build_output_override(self, estimate: TradePriceEstimate) -> OutputPriceOverride:
        if estimate.estimated_sale_price_chaos is None:
            raise ValueError("Cannot build output override without an estimated sale price")
        return OutputPriceOverride(
            game=self.game,
            league=estimate.league,
            recipe_id=estimate.recipe_id,
            estimated_sale_price_chaos=estimate.estimated_sale_price_chaos,
            failed_resale_value_chaos=0.0,
            confidence=estimate.confidence,
            source=estimate.source,
            note=estimate.note,
        )

    def _listing_price_chaos(self, listing: TradeListing, league: str) -> float | None:
        if listing.price is None:
            return None
        return self.converter.to_chaos(listing.price.amount, listing.price.currency, league)


TRADE_CURRENCY_TO_MARKET_NAME = {
    "divine": "Divine Orb",
    "divine-orb": "Divine Orb",
    "exalted": "Exalted Orb",
    "exalted-orb": "Exalted Orb",
    "mirror": "Mirror of Kalandra",
    "mirror-of-kalandra": "Mirror of Kalandra",
    "annul": "Orb of Annulment",
    "annulment": "Orb of Annulment",
    "regal": "Regal Orb",
    "regal-orb": "Regal Orb",
    "alchemy": "Orb of Alchemy",
    "alchemy-orb": "Orb of Alchemy",
}


def _normalize_trade_currency(value: str) -> str:
    normalized = str(value).strip().lower().replace("_", "-").replace(" ", "-")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized.strip("-")


def _estimate_confidence(sample: list[float], total_result_count: int, skipped: int) -> str:
    if not sample:
        return "trade_search_no_price"
    if len(sample) >= 5 and total_result_count >= 20 and skipped == 0:
        return "trade_search_sampled"
    if len(sample) >= 3:
        return "trade_search_thin_sample"
    return "trade_search_low_sample"


def _estimate_note(sample: list[float], total_result_count: int, skipped: int) -> str:
    if not sample:
        return f"No priced listings could be converted to chaos. total_results={total_result_count}, skipped={skipped}."
    prices = ", ".join(f"{value:.4g}c" for value in sample)
    return f"Trade search estimate from cheapest converted listings: {prices}. total_results={total_result_count}, skipped={skipped}."
