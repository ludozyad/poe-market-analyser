from __future__ import annotations

from poe_market_analyser.domain.market import ManualPriceOverride, MarketPrice
from poe_market_analyser.domain.models import CraftingRecipe, Ingredient
from poe_market_analyser.domain.pricing import (
    MissingIngredientPrice,
    PriceBook,
    PriceBookEntry,
    RecipePriceResolution,
)
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository


class MarketPriceResolver:
    """Resolve recipe ingredients against manual overrides and local market cache.

    The resolver intentionally depends on the repository, not on poe.ninja. The
    analysis stage should use the latest cached prices regardless of where they
    came from in the future.
    """

    def __init__(self, repository: SqliteMarketRepository, low_listing_threshold: int = 10):
        self.repository = repository
        self.low_listing_threshold = low_listing_threshold

    def resolve_recipe_prices(
        self,
        recipe: CraftingRecipe,
        league: str | None = None,
        game: str = "poe1",
        source: str = "poe_ninja",
    ) -> RecipePriceResolution:
        target_league = league or recipe.default_league
        entries: list[PriceBookEntry] = []
        missing: list[MissingIngredientPrice] = []

        for ingredient in recipe.ingredients:
            if not ingredient.price_lookup:
                continue

            market_type = _get_market_type(ingredient)
            market_name = _get_market_name(ingredient)

            if not market_type:
                missing.append(
                    MissingIngredientPrice(
                        ingredient_id=ingredient.id,
                        ingredient_type=ingredient.type,
                        reason="Ingredient has price_lookup=true but no market_type metadata.",
                        market_name=market_name,
                    )
                )
                continue

            if not market_name:
                missing.append(
                    MissingIngredientPrice(
                        ingredient_id=ingredient.id,
                        ingredient_type=ingredient.type,
                        reason="Ingredient has price_lookup=true but no market_name metadata.",
                        market_type=market_type,
                    )
                )
                continue

            entry = self._resolve_single_entry(
                recipe=recipe,
                ingredient=ingredient,
                market_type=market_type,
                market_name=market_name,
                target_league=target_league,
                game=game,
                source=source,
            )
            if entry is None:
                missing.append(
                    MissingIngredientPrice(
                        ingredient_id=ingredient.id,
                        ingredient_type=ingredient.type,
                        reason="No matching manual override or latest market price found in local cache.",
                        market_type=market_type,
                        market_name=market_name,
                    )
                )
                continue

            entries.append(entry)

        return RecipePriceResolution(
            recipe_id=recipe.id,
            recipe_name=recipe.name,
            league=target_league,
            price_book=PriceBook(entries=tuple(entries), base_currency="chaos"),
            missing_prices=tuple(missing),
        )

    def _resolve_single_entry(
        self,
        recipe: CraftingRecipe,
        ingredient: Ingredient,
        market_type: str,
        market_name: str,
        target_league: str,
        game: str,
        source: str,
    ) -> PriceBookEntry | None:
        price_sources = _build_price_source_order(recipe, ingredient)

        for price_source in price_sources:
            normalized_source = price_source.strip().lower()
            if normalized_source == "manual_override":
                override = self.repository.find_manual_price_override(
                    league=target_league,
                    item_type=market_type,
                    name=market_name,
                    game=game,
                )
                if override is not None:
                    return self._entry_from_manual_override(ingredient, market_type, market_name, override)

            if normalized_source == "recipe_fallback":
                entry = self._entry_from_recipe_fallback(ingredient, market_type, market_name)
                if entry is not None:
                    return entry

            if normalized_source in {"local_cache", "poe_ninja", source.strip().lower()}:
                price = self.repository.find_latest_price(
                    league=target_league,
                    item_type=market_type,
                    name=market_name,
                    game=game,
                    source=source,
                )
                if price is not None:
                    return self._entry_from_market_price(ingredient, market_type, market_name, price)

        return None

    def _entry_from_manual_override(
        self,
        ingredient: Ingredient,
        market_type: str,
        market_name: str,
        override: ManualPriceOverride,
    ) -> PriceBookEntry:
        note = _merge_notes(
            _optional_str(ingredient.metadata.get("pricing_note")),
            override.note,
        )
        return PriceBookEntry(
            ingredient_id=ingredient.id,
            ingredient_type=ingredient.type,
            market_type=market_type,
            market_name=market_name,
            matched_name=override.market_name,
            matched_price_id=f"manual:{override.market_name}",
            quantity=ingredient.resolved_quantity,
            quantity_mode=ingredient.quantity_label,
            unit_price_chaos=override.chaos_value,
            total_price_chaos=ingredient.resolved_quantity * override.chaos_value,
            unit_price_divine=override.divine_value,
            listing_count=override.listing_count,
            note=note,
            price_source="manual_override",
            confidence=override.confidence,
            warnings=tuple(_build_price_warnings(override.listing_count, self.low_listing_threshold)),
        )

    def _entry_from_recipe_fallback(
        self,
        ingredient: Ingredient,
        market_type: str,
        market_name: str,
    ) -> PriceBookEntry | None:
        chaos_value = _optional_float(ingredient.metadata.get("fallback_unit_price_chaos"))
        if chaos_value is None:
            return None
        divine_value = _optional_float(ingredient.metadata.get("fallback_unit_price_divine"))
        listing_count = _optional_int(ingredient.metadata.get("fallback_listing_count"))
        confidence = _optional_str(ingredient.metadata.get("fallback_price_confidence")) or "recipe_fallback"
        source_note = _optional_str(ingredient.metadata.get("fallback_price_source"))
        note = _merge_notes(
            _optional_str(ingredient.metadata.get("pricing_note")),
            _optional_str(ingredient.metadata.get("fallback_pricing_note")),
            source_note,
        )
        return PriceBookEntry(
            ingredient_id=ingredient.id,
            ingredient_type=ingredient.type,
            market_type=market_type,
            market_name=market_name,
            matched_name=market_name,
            matched_price_id=f"recipe_fallback:{market_name}",
            quantity=ingredient.resolved_quantity,
            quantity_mode=ingredient.quantity_label,
            unit_price_chaos=chaos_value,
            total_price_chaos=ingredient.resolved_quantity * chaos_value,
            unit_price_divine=divine_value,
            listing_count=listing_count,
            note=note,
            price_source="recipe_fallback",
            confidence=confidence,
            warnings=(),
        )

    def _entry_from_market_price(
        self,
        ingredient: Ingredient,
        market_type: str,
        market_name: str,
        price: MarketPrice,
    ) -> PriceBookEntry:
        return PriceBookEntry(
            ingredient_id=ingredient.id,
            ingredient_type=ingredient.type,
            market_type=market_type,
            market_name=market_name,
            matched_name=price.name,
            matched_price_id=price.id,
            quantity=ingredient.resolved_quantity,
            quantity_mode=ingredient.quantity_label,
            unit_price_chaos=price.chaos_value,
            total_price_chaos=ingredient.resolved_quantity * price.chaos_value,
            unit_price_divine=price.divine_value,
            listing_count=price.listing_count,
            note=_optional_str(ingredient.metadata.get("pricing_note")),
            price_source="local_cache",
            confidence="market_cache",
            warnings=tuple(_build_price_warnings(price.listing_count, self.low_listing_threshold)),
        )


def _build_price_source_order(recipe: CraftingRecipe, ingredient: Ingredient) -> tuple[str, ...]:
    configured = list(recipe.pricing.price_sources or ("manual_override", "local_cache", "poe_ninja"))
    has_fallback = _optional_float(ingredient.metadata.get("fallback_unit_price_chaos")) is not None
    if not has_fallback:
        return tuple(_dedupe_preserve_order(configured))

    prefer_fallback = _optional_bool(ingredient.metadata.get("prefer_recipe_fallback"))
    if "recipe_fallback" in {source.strip().lower() for source in configured}:
        return tuple(_dedupe_preserve_order(configured))

    if prefer_fallback:
        result: list[str] = []
        inserted = False
        for source in configured:
            result.append(source)
            if source.strip().lower() == "manual_override":
                result.append("recipe_fallback")
                inserted = True
        if not inserted:
            result.insert(0, "recipe_fallback")
        return tuple(_dedupe_preserve_order(result))

    return tuple(_dedupe_preserve_order([*configured, "recipe_fallback"]))


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        result.append(value)
        seen.add(normalized)
    return result


def _get_market_type(ingredient: Ingredient) -> str | None:
    explicit = _optional_str(ingredient.metadata.get("market_type"))
    if explicit:
        return explicit

    # Conservative fallbacks for early MVP recipes. Explicit market_type should
    # be preferred in real recipe files because PoE item categories are messy.
    if ingredient.type == "beast":
        return "Beast"
    if ingredient.type == "base_item":
        return "BaseType"
    return None


def _get_market_name(ingredient: Ingredient) -> str | None:
    return _optional_str(ingredient.metadata.get("market_name"))


def _build_price_warnings(listing_count: int | None, low_listing_threshold: int) -> list[str]:
    warnings: list[str] = []
    if listing_count is not None and listing_count < low_listing_threshold:
        warnings.append(
            f"Low listing count ({listing_count}); price may be unreliable."
        )
    return warnings


def _merge_notes(*notes: str | None) -> str | None:
    present = [note for note in notes if note]
    if not present:
        return None
    return " ".join(present)


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}
