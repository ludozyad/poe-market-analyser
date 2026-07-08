from __future__ import annotations

from dataclasses import dataclass

from poe_market_analyser.application.output_pricing import OutputPriceResolution
from poe_market_analyser.domain.models import CraftingRecipe
from poe_market_analyser.domain.pricing import PriceBook


@dataclass(frozen=True)
class RecipeQualityAssessment:
    confidence_score: int
    flags: tuple[str, ...]


_DRAFT_WORDS = ("draft", "manual", "estimate", "fallback", "unknown")
_STRONG_WORDS = ("checked", "trade", "market", "cache", "verified")


def assess_recipe_quality(
    recipe: CraftingRecipe,
    price_book: PriceBook,
    output_price: OutputPriceResolution,
    missing_price_count: int,
    warning_count: int,
) -> RecipeQualityAssessment:
    """Build a small, deterministic quality score for automatic ranking.

    The score is intentionally conservative. It does not claim that a craft is
    profitable; it tells the UI/ranking how much human review the imported data
    probably needs. This lets recipe packs be useful while still surfacing draft
    assumptions and fallback prices.
    """
    score = 100
    flags: list[str] = []

    if str(recipe.recipe.status).strip().lower() != "active":
        score -= 8
        flags.append(f"recipe_status:{recipe.recipe.status}")

    if missing_price_count:
        score -= min(45, missing_price_count * 15)
        flags.append(f"missing_prices:{missing_price_count}")

    if warning_count:
        score -= min(30, warning_count * 10)
        flags.append(f"price_warnings:{warning_count}")

    recipe_fallback_count = sum(1 for entry in price_book.entries if entry.price_source == "recipe_fallback")
    manual_override_count = sum(1 for entry in price_book.entries if entry.price_source == "manual_override")
    low_confidence_entry_count = sum(
        1
        for entry in price_book.entries
        if _is_low_confidence(entry.confidence) or entry.price_source == "recipe_fallback"
    )

    if recipe_fallback_count:
        score -= min(25, recipe_fallback_count * 3)
        flags.append(f"recipe_fallback_prices:{recipe_fallback_count}")

    if manual_override_count:
        score -= min(10, manual_override_count * 2)
        flags.append(f"manual_overrides:{manual_override_count}")

    if low_confidence_entry_count:
        score -= min(20, low_confidence_entry_count * 2)
        flags.append(f"low_confidence_prices:{low_confidence_entry_count}")

    if not output_price.has_sale_price:
        score -= 30
        flags.append("missing_output_price")
    elif _is_low_confidence(output_price.confidence) or output_price.source == "recipe_import":
        score -= 15
        flags.append(f"output_price:{output_price.source}/{output_price.confidence}")
    elif _is_strong_confidence(output_price.confidence):
        score += 5

    return RecipeQualityAssessment(
        confidence_score=max(0, min(100, score)),
        flags=tuple(flags),
    )


def _is_low_confidence(value: str | None) -> bool:
    if not value:
        return True
    normalized = value.strip().lower()
    return any(word in normalized for word in _DRAFT_WORDS)


def _is_strong_confidence(value: str | None) -> bool:
    if not value:
        return False
    normalized = value.strip().lower()
    return any(word in normalized for word in _STRONG_WORDS) and not _is_low_confidence(normalized)
