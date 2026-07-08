from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class TradeListingPrice:
    amount: float
    currency: str
    amount_chaos: float | None = None


@dataclass(frozen=True)
class TradeListing:
    listing_id: str
    price: TradeListingPrice | None
    item_name: str | None = None
    item_type: str | None = None
    account: str | None = None
    indexed_at: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TradeSearchResult:
    query_id: str
    result_ids: tuple[str, ...]
    total_result_count: int
    listings: tuple[TradeListing, ...]
    search_url: str | None = None
    fetched_at_utc: datetime = datetime.now(UTC)


@dataclass(frozen=True)
class TradePriceEstimate:
    recipe_id: str
    league: str
    estimated_sale_price_chaos: float | None
    min_price_chaos: float | None
    median_price_chaos: float | None
    mean_price_chaos: float | None
    used_listing_count: int
    total_result_count: int
    skipped_listing_count: int
    query_id: str | None
    search_url: str | None
    confidence: str
    source: str = "poe_trade_search"
    note: str | None = None
    listing_prices_chaos: tuple[float, ...] = ()
