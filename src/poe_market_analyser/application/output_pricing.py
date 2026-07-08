from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from poe_market_analyser.domain.models import CraftingRecipe


@dataclass(frozen=True)
class OutputPriceOverride:
    """Stored finished-item price override for one recipe and league.

    This is intentionally recipe-level, not ingredient-level. It lets the user or
    a future trade-search provider update output pricing without editing YAML
    recipe packs. Priority is below explicit CLI overrides and above imported
    recipe estimates.
    """

    game: str
    league: str
    recipe_id: str
    estimated_sale_price_chaos: float
    failed_resale_value_chaos: float = 0.0
    confidence: str = "manual_output_override"
    source: str = "manual_override"
    note: str | None = None
    updated_at_utc: datetime = datetime.now(UTC)


@dataclass(frozen=True)
class OutputPriceResolution:
    estimated_sale_price_chaos: float | None
    failed_resale_value_chaos: float
    source: str | None
    confidence: str | None
    note: str | None = None

    @property
    def has_sale_price(self) -> bool:
        return self.estimated_sale_price_chaos is not None


def resolve_output_price(
    recipe: CraftingRecipe,
    sale_price_override_chaos: float | None = None,
    failed_resale_override_chaos: float | None = None,
    stored_override: OutputPriceOverride | None = None,
) -> OutputPriceResolution:
    """Resolve the finished-item price used by the first-pass profit engine.

    Priority:
    1. explicit CLI override,
    2. stored output price override from SQLite,
    3. imported recipe output estimate,
    4. missing output price.

    This gives us a path from draft recipe estimates to more reliable prices
    without changing the recipe file format or ranking API.
    """
    if sale_price_override_chaos is not None:
        failed_resale = 0.0 if failed_resale_override_chaos is None else failed_resale_override_chaos
        return OutputPriceResolution(
            estimated_sale_price_chaos=sale_price_override_chaos,
            failed_resale_value_chaos=failed_resale,
            source="cli_override",
            confidence="manual_cli",
            note="Output sale price supplied from CLI argument.",
        )

    if stored_override is not None:
        failed_resale = (
            stored_override.failed_resale_value_chaos
            if failed_resale_override_chaos is None
            else failed_resale_override_chaos
        )
        return OutputPriceResolution(
            estimated_sale_price_chaos=stored_override.estimated_sale_price_chaos,
            failed_resale_value_chaos=failed_resale,
            source=stored_override.source,
            confidence=stored_override.confidence,
            note=stored_override.note,
        )

    output = recipe.pricing.output
    if output is not None and output.estimated_sale_price_chaos is not None:
        failed_resale = (
            output.failed_resale_value_chaos
            if failed_resale_override_chaos is None
            else failed_resale_override_chaos
        )
        return OutputPriceResolution(
            estimated_sale_price_chaos=output.estimated_sale_price_chaos,
            failed_resale_value_chaos=failed_resale,
            source=output.source or output.mode,
            confidence=output.confidence,
            note=output.note,
        )

    failed_resale = 0.0 if failed_resale_override_chaos is None else failed_resale_override_chaos
    return OutputPriceResolution(
        estimated_sale_price_chaos=None,
        failed_resale_value_chaos=failed_resale,
        source=None,
        confidence=None,
        note=None,
    )
