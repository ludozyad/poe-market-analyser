from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PriceBookEntry:
    ingredient_id: str
    ingredient_type: str
    market_type: str
    market_name: str
    matched_name: str
    matched_price_id: str
    quantity: float
    quantity_mode: str
    unit_price_chaos: float
    total_price_chaos: float
    unit_price_divine: float | None = None
    listing_count: int | None = None
    note: str | None = None
    price_source: str = "local_cache"
    confidence: str | None = None
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class PriceBook:
    entries: tuple[PriceBookEntry, ...]
    base_currency: str = "chaos"

    def get_unit_price(self, ingredient_id: str) -> float | None:
        for entry in self.entries:
            if entry.ingredient_id == ingredient_id:
                return entry.unit_price_chaos
        return None

    def total_known_cost_chaos(self) -> float:
        return sum(entry.total_price_chaos for entry in self.entries)


@dataclass(frozen=True)
class MissingIngredientPrice:
    ingredient_id: str
    ingredient_type: str
    reason: str
    market_type: str | None = None
    market_name: str | None = None


@dataclass(frozen=True)
class RecipePriceResolution:
    recipe_id: str
    recipe_name: str
    league: str
    price_book: PriceBook
    missing_prices: tuple[MissingIngredientPrice, ...]

    @property
    def has_missing_prices(self) -> bool:
        return bool(self.missing_prices)
