from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from poe_market_analyser.domain.market import MarketDataProvider, MarketSnapshot
from poe_market_analyser.infrastructure.market.poe_ninja_provider import POE1_EXCHANGE_OVERVIEW_TYPES
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository


@dataclass(frozen=True)
class MarketFetchSummary:
    league: str
    item_type: str
    saved_snapshot_id: int
    price_count: int


class MarketDataService:
    def __init__(self, provider: MarketDataProvider, repository: SqliteMarketRepository):
        self.provider = provider
        self.repository = repository

    def fetch_and_store_currency(self, league: str, currency_type: str = "Currency") -> MarketFetchSummary:
        snapshot = self.provider.fetch_currency_prices(league=league, currency_type=currency_type)
        return self._save_snapshot(snapshot)

    def fetch_and_store_items(self, league: str, item_type: str) -> MarketFetchSummary:
        snapshot = self.provider.fetch_item_prices(league=league, item_type=item_type)
        return self._save_snapshot(snapshot)

    def fetch_and_store_many(self, league: str, item_types: Iterable[str]) -> tuple[MarketFetchSummary, ...]:
        summaries: list[MarketFetchSummary] = []
        for item_type in item_types:
            if item_type in POE1_EXCHANGE_OVERVIEW_TYPES:
                summaries.append(self.fetch_and_store_currency(league, item_type))
            else:
                summaries.append(self.fetch_and_store_items(league, item_type))
        return tuple(summaries)

    def _save_snapshot(self, snapshot: MarketSnapshot) -> MarketFetchSummary:
        snapshot_id = self.repository.save_snapshot(snapshot)
        return MarketFetchSummary(
            league=snapshot.context.league,
            item_type=snapshot.item_type,
            saved_snapshot_id=snapshot_id,
            price_count=len(snapshot.prices),
        )
