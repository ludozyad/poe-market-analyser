from pathlib import Path

from poe_market_analyser.application.price_resolver import MarketPriceResolver
from poe_market_analyser.domain.market import ManualPriceOverride, MarketContext, MarketPrice, MarketSnapshot
from poe_market_analyser.infrastructure.importers.yaml_recipe_importer import YamlRecipeImporter
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository

SAMPLE_RECIPE = Path("data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml")


def test_sqlite_market_repository_saves_and_finds_manual_price_override(tmp_path):
    repository = SqliteMarketRepository(tmp_path / "poe_market.db")
    repository.save_manual_price_override(
        ManualPriceOverride(
            game="poe1",
            league="Mirage",
            item_type="BaseType",
            market_name="Spiked Gloves",
            chaos_value=25.0,
            confidence="checked_trade",
            note="Manual base check.",
        )
    )

    override = repository.find_manual_price_override(
        league="Mirage",
        item_type="BaseType",
        name="spiked-gloves",
        game="poe1",
    )

    assert override is not None
    assert override.market_name == "Spiked Gloves"
    assert override.chaos_value == 25.0
    assert override.confidence == "checked_trade"


def test_price_resolver_prefers_manual_override_over_market_cache(tmp_path):
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)
    repository = SqliteMarketRepository(tmp_path / "poe_market.db")
    repository.save_manual_price_override(
        ManualPriceOverride(
            game="poe1",
            league="Mirage",
            item_type="BaseType",
            market_name="Spiked Gloves",
            chaos_value=25.0,
            confidence="checked_trade",
            note="Manual base check.",
        )
    )
    repository.save_snapshot(
        MarketSnapshot(
            context=MarketContext(game="poe1", league="Mirage", source="poe_ninja"),
            item_type="BaseType",
            prices=(
                MarketPrice(
                    id="spiked-gloves-82-warlord-hunter",
                    name="Spiked Gloves",
                    item_type="BaseType",
                    category="item",
                    chaos_value=188600.0,
                    divine_value=350.0,
                    listing_count=2,
                    details_id="spiked-gloves-82-warlord-hunter",
                    raw={"name": "Spiked Gloves"},
                ),
            ),
        )
    )

    resolution = MarketPriceResolver(repository).resolve_recipe_prices(recipe, league="Mirage")
    base_entry = next(entry for entry in resolution.price_book.entries if entry.ingredient_id == "hunter_spiked_gloves_ilvl86")

    assert base_entry.price_source == "manual_override"
    assert base_entry.unit_price_chaos == 25.0
    assert base_entry.confidence == "checked_trade"
    assert "Manual base check." in (base_entry.note or "")
