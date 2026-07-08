from __future__ import annotations

from dataclasses import dataclass

from poe_market_analyser.domain.models import CraftingRecipe


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
) -> OutputPriceResolution:
    """Resolve the finished-item price used by the first-pass profit engine.

    Priority is intentionally simple for MVP:
    1. explicit CLI override,
    2. imported recipe output estimate,
    3. missing output price.

    This keeps regular usage hands-off when recipe packs already contain output
    estimates, but still lets a user experiment without editing YAML.
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
