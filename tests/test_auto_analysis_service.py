from pathlib import Path

from poe_market_analyser.application.auto_analysis_service import AutoAnalysisService
from poe_market_analyser.application.recipe_market_requirements import collect_required_market_types, summarize_market_requirements
from poe_market_analyser.application.recipe_service import RecipeImportService
from poe_market_analyser.domain.market import MarketContext, MarketPrice, MarketSnapshot
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository
from poe_market_analyser.infrastructure.storage.sqlite_recipe_repository import SqliteRecipeRepository

SAMPLE_RECIPE = Path("data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml")


class FakeMarketProvider:
    def fetch_currency_prices(self, league: str, currency_type: str = "Currency") -> MarketSnapshot:
        return MarketSnapshot(
            context=MarketContext(game="poe1", league=league, source="poe_ninja"),
            item_type=currency_type,
            prices=_prices_for_type(currency_type),
        )

    def fetch_item_prices(self, league: str, item_type: str) -> MarketSnapshot:
        return MarketSnapshot(
            context=MarketContext(game="poe1", league=league, source="poe_ninja"),
            item_type=item_type,
            prices=_prices_for_type(item_type),
        )


def _price(name: str, chaos: float, item_type: str, listings: int = 100) -> MarketPrice:
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


def _prices_for_type(item_type: str) -> tuple[MarketPrice, ...]:
    if item_type == "BaseType":
        return (_price("Spiked Gloves", 25.0, item_type="BaseType"),)
    if item_type == "Fossil":
        return (_price("Gilded Fossil", 30.0, item_type="Fossil", listings=45),)
    if item_type == "Beast":
        return (_price("Craicic Chimeral", 1617.0, item_type="Beast", listings=3181),)
    if item_type == "Currency":
        return (
            _price("Orb of Alteration", 0.05, item_type="Currency"),
            _price("Regal Orb", 1.0, item_type="Currency"),
            _price("Orb of Annulment", 20.0, item_type="Currency"),
            _price("Orb of Scouring", 0.5, item_type="Currency"),
            _price("Maven's Orb", 3479.0, item_type="Currency"),
            _price("Awakener's Orb", 1440.0, item_type="Currency"),
            _price("Veiled Exalted Orb", 8624.0, item_type="Currency"),
            _price("Vaal Orb", 1.0, item_type="Currency"),
            _price("Divine Orb", 539.0, item_type="Currency"),
        )
    return ()


def test_collect_required_market_types_from_imported_recipe(tmp_path):
    repository = SqliteRecipeRepository(tmp_path / "poe_market.db")
    recipe = RecipeImportService(repository).import_yaml(SAMPLE_RECIPE)

    assert collect_required_market_types((recipe,)) == ("BaseType", "Beast", "Currency", "Fossil")

    requirements = summarize_market_requirements((recipe,))
    assert [requirement.item_type for requirement in requirements] == ["BaseType", "Beast", "Currency", "Fossil"]
    currency = next(requirement for requirement in requirements if requirement.item_type == "Currency")
    assert currency.ingredient_count == 10
    assert currency.recipe_count == 1


def test_auto_analysis_service_imports_refreshes_required_market_and_ranks(tmp_path):
    recipes_dir = tmp_path / "recipes"
    recipes_dir.mkdir()
    (recipes_dir / SAMPLE_RECIPE.name).write_text(SAMPLE_RECIPE.read_text(encoding="utf-8"), encoding="utf-8")

    database = tmp_path / "poe_market.db"
    service = AutoAnalysisService(
        recipe_repository=SqliteRecipeRepository(database),
        market_repository=SqliteMarketRepository(database),
        market_provider=FakeMarketProvider(),
    )

    result = service.import_refresh_and_rank(league="Mirage", recipe_dir=recipes_dir)

    assert result.imported_recipe_count == 1
    assert result.refreshed_market_types == ("BaseType", "Beast", "Currency", "Fossil")
    assert [summary.item_type for summary in result.fetch_summaries] == ["BaseType", "Beast", "Currency", "Fossil"]
    assert len(result.ranking_rows) == 1
    row = result.ranking_rows[0]
    assert row.recipe_id == "poe1_mirage_viper_touch_spiked_gloves"
    assert row.missing_price_count == 0
    assert row.status == "ready"
