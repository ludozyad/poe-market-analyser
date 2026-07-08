from dataclasses import replace
from pathlib import Path

from poe_market_analyser.application.price_resolver import MarketPriceResolver
from poe_market_analyser.domain.market import MarketContext, MarketPrice, MarketSnapshot
from poe_market_analyser.infrastructure.importers.yaml_recipe_importer import YamlRecipeImporter
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository

SAMPLE_RECIPE = Path("data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml")


def _price(name: str, chaos: float, item_type: str = "Currency", listings: int = 100) -> MarketPrice:
    key = name.lower().replace("'", "").replace(" ", "-")
    return MarketPrice(
        id=key,
        name=name,
        item_type=item_type,
        category="exchange" if item_type in {"Currency", "Fossil"} else "item",
        chaos_value=chaos,
        listing_count=listings,
        details_id=key,
        raw={"name": name},
    )


def _save_full_test_market(repository: SqliteMarketRepository, base_chaos: float = 10.0) -> None:
    context = MarketContext(game="poe1", league="Mirage", source="poe_ninja")
    repository.save_snapshot(
        MarketSnapshot(
            context=context,
            item_type="Fossil",
            prices=(_price("Gilded Fossil", 30.0, item_type="Fossil", listings=45),),
        )
    )
    repository.save_snapshot(
        MarketSnapshot(
            context=context,
            item_type="Beast",
            prices=(_price("Craicic Chimeral", 1617.0, item_type="Beast", listings=3181),),
        )
    )
    repository.save_snapshot(
        MarketSnapshot(
            context=context,
            item_type="BaseType",
            prices=(_price("Spiked Gloves", base_chaos, item_type="BaseType", listings=100),),
        )
    )
    repository.save_snapshot(
        MarketSnapshot(
            context=context,
            item_type="Currency",
            prices=(
                _price("Orb of Alteration", 0.05),
                _price("Regal Orb", 1.0),
                _price("Orb of Annulment", 20.0),
                _price("Orb of Scouring", 0.5),
                _price("Maven's Orb", 3479.0),
                _price("Awakener's Orb", 1440.0),
                _price("Veiled Exalted Orb", 8624.0),
                _price("Vaal Orb", 1.0),
                _price("Divine Orb", 539.0),
            ),
        )
    )


def _strip_recipe_fallbacks(recipe):
    stripped_ingredients = []
    fallback_keys = {
        "fallback_unit_price_chaos",
        "fallback_unit_price_divine",
        "fallback_listing_count",
        "fallback_price_confidence",
        "fallback_pricing_note",
        "fallback_price_source",
        "prefer_recipe_fallback",
    }
    for ingredient in recipe.ingredients:
        stripped_ingredients.append(
            replace(
                ingredient,
                metadata={key: value for key, value in ingredient.metadata.items() if key not in fallback_keys},
            )
        )
    return replace(recipe, ingredients=tuple(stripped_ingredients))


def test_price_resolver_resolves_recipe_ingredients_from_latest_market_cache(tmp_path):
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)
    repository = SqliteMarketRepository(tmp_path / "poe_market.db")
    _save_full_test_market(repository)

    resolution = MarketPriceResolver(repository).resolve_recipe_prices(recipe, league="Mirage")

    assert resolution.recipe_id == "poe1_mirage_viper_touch_spiked_gloves"
    assert resolution.missing_prices == ()
    assert {entry.ingredient_id for entry in resolution.price_book.entries} == {
        ingredient.id for ingredient in recipe.ingredients
    }
    alteration = next(entry for entry in resolution.price_book.entries if entry.ingredient_id == "orb_of_alteration")
    assert alteration.quantity == 600.0
    assert alteration.quantity_mode == "expected"
    assert alteration.total_price_chaos == 30.0
    assert resolution.price_book.total_known_cost_chaos() > 30_000.0


def test_price_resolver_reports_missing_market_price_when_no_cache_and_no_recipe_fallback(tmp_path):
    recipe = _strip_recipe_fallbacks(YamlRecipeImporter().import_file(SAMPLE_RECIPE))
    repository = SqliteMarketRepository(tmp_path / "poe_market.db")

    resolution = MarketPriceResolver(repository).resolve_recipe_prices(recipe, league="Mirage")

    assert len(resolution.missing_prices) == len(recipe.ingredients)
    assert {missing.ingredient_id for missing in resolution.missing_prices} == {
        ingredient.id for ingredient in recipe.ingredients
    }


def test_price_resolver_uses_recipe_fallback_when_market_cache_is_missing(tmp_path):
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)
    repository = SqliteMarketRepository(tmp_path / "poe_market.db")

    resolution = MarketPriceResolver(repository).resolve_recipe_prices(recipe, league="Mirage")

    assert resolution.missing_prices == ()
    assert {entry.price_source for entry in resolution.price_book.entries} == {"recipe_fallback"}
    base = next(entry for entry in resolution.price_book.entries if entry.ingredient_id == "hunter_spiked_gloves_ilvl86")
    assert base.unit_price_chaos == 25.0
    assert base.confidence == "checked_recipe_fallback"
