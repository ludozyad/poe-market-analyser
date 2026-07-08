from __future__ import annotations

from dataclasses import dataclass

from poe_market_analyser.domain.models import CraftingRecipe


@dataclass(frozen=True)
class PriceEntry:
    item_id: str
    price: float
    currency: str = "divine"


@dataclass(frozen=True)
class ManualPriceBook:
    prices: dict[str, PriceEntry]
    base_currency: str = "divine"

    @classmethod
    def from_plain_prices(cls, prices: dict[str, float], base_currency: str = "divine") -> "ManualPriceBook":
        return cls(
            prices={
                item_id: PriceEntry(item_id=item_id, price=price, currency=base_currency)
                for item_id, price in prices.items()
            },
            base_currency=base_currency,
        )

    def get_price(self, item_id: str) -> PriceEntry | None:
        return self.prices.get(item_id)


@dataclass(frozen=True)
class MissingPrice:
    item_id: str
    reason: str


@dataclass(frozen=True)
class ProfitAnalysisResult:
    recipe_id: str
    recipe_name: str
    currency: str
    ingredient_cost: float
    expected_attempts: float
    expected_cost_to_success: float
    estimated_sale_price: float | None
    estimated_failed_resale_value: float
    expected_profit: float | None
    missing_prices: tuple[MissingPrice, ...]
    success_assumption_id: str | None = None


class SimpleExpectedValueProfitEngine:
    """Minimal MVP expected-value calculator.

    This engine is intentionally simple. It does not yet understand checkpoint-level
    costs, salvage per branch, trade liquidity, or mod-weight simulations.
    It gives us a stable first use case for imported recipes and manual prices.
    """

    def calculate(
        self,
        recipe: CraftingRecipe,
        price_book: ManualPriceBook,
        estimated_sale_price: float | None = None,
        estimated_failed_resale_value: float = 0.0,
        success_assumption_id: str | None = None,
    ) -> ProfitAnalysisResult:
        missing_prices: list[MissingPrice] = []
        ingredient_cost = 0.0

        for ingredient in recipe.ingredients:
            if not ingredient.price_lookup:
                continue
            price = price_book.get_price(ingredient.id)
            if price is None:
                missing_prices.append(MissingPrice(ingredient.id, "No manual price provided."))
                continue
            if price.currency != price_book.base_currency:
                missing_prices.append(
                    MissingPrice(
                        ingredient.id,
                        f"Currency mismatch: expected {price_book.base_currency}, got {price.currency}.",
                    )
                )
                continue
            ingredient_cost += ingredient.quantity * price.price

        expected_attempts = 1.0
        if success_assumption_id:
            assumption = recipe.assumption_by_id(success_assumption_id)
            if assumption is None:
                missing_prices.append(
                    MissingPrice(success_assumption_id, "Success assumption id was not found in recipe.")
                )
            elif assumption.value > 0:
                expected_attempts = 1.0 / assumption.value

        expected_cost_to_success = ingredient_cost * expected_attempts
        expected_profit = None
        if estimated_sale_price is not None:
            expected_profit = (
                estimated_sale_price + estimated_failed_resale_value - expected_cost_to_success
            )

        return ProfitAnalysisResult(
            recipe_id=recipe.id,
            recipe_name=recipe.name,
            currency=price_book.base_currency,
            ingredient_cost=ingredient_cost,
            expected_attempts=expected_attempts,
            expected_cost_to_success=expected_cost_to_success,
            estimated_sale_price=estimated_sale_price,
            estimated_failed_resale_value=estimated_failed_resale_value,
            expected_profit=expected_profit,
            missing_prices=tuple(missing_prices),
            success_assumption_id=success_assumption_id,
        )
