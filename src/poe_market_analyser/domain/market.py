from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class MarketContext:
    game: str
    league: str
    source: str = "poe_ninja"


@dataclass(frozen=True)
class MarketPrice:
    id: str
    name: str
    item_type: str
    category: str
    chaos_value: float
    divine_value: float | None = None
    listing_count: int | None = None
    details_id: str | None = None
    source: str = "poe_ninja"
    fetched_at_utc: datetime = field(default_factory=lambda: datetime.now(UTC))
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MarketSnapshot:
    context: MarketContext
    item_type: str
    prices: tuple[MarketPrice, ...]
    fetched_at_utc: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ManualPriceOverride:
    """User-defined price used when market data is too noisy or too generic.

    Example: poe.ninja BaseType can aggregate influenced or otherwise unusual
    bases. For crafting bases and donor items, a manual override is often more
    trustworthy until exact trade search support is implemented.
    """

    game: str
    league: str
    item_type: str
    market_name: str
    chaos_value: float
    divine_value: float | None = None
    listing_count: int | None = None
    confidence: str = "manual"
    note: str | None = None
    updated_at_utc: datetime = field(default_factory=lambda: datetime.now(UTC))


class MarketDataProvider(Protocol):
    def fetch_currency_prices(self, league: str, currency_type: str = "Currency") -> MarketSnapshot:
        raise NotImplementedError

    def fetch_item_prices(self, league: str, item_type: str) -> MarketSnapshot:
        raise NotImplementedError
