from pathlib import Path

import yaml

from poe_market_analyser.application.recipe_ranking_service import RecipeRankingService
from poe_market_analyser.application.recipe_service import RecipeImportService
from poe_market_analyser.domain.market import MarketContext, MarketPrice, MarketSnapshot
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository
from poe_market_analyser.infrastructure.storage.sqlite_recipe_repository import SqliteRecipeRepository

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


def _save_full_test_market(repository: SqliteMarketRepository, base_chaos: float = 25.0) -> None:
    context = MarketContext(game="poe1", league="Mirage", source="poe_ninja")
    repository.save_snapshot(
        MarketSnapshot(
            context=context,
            item_type="BaseType",
            prices=(_price("Spiked Gloves", base_chaos, item_type="BaseType"),),
        )
    )
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


def _write_recipe_without_fallbacks(tmp_path: Path) -> Path:
    document = yaml.safe_load(SAMPLE_RECIPE.read_text(encoding="utf-8"))
    fallback_keys = {
        "fallback_unit_price_chaos",
        "fallback_unit_price_divine",
        "fallback_listing_count",
        "fallback_price_confidence",
        "fallback_pricing_note",
        "fallback_price_source",
        "prefer_recipe_fallback",
    }
    for ingredient in document["ingredients"]:
        for key in fallback_keys:
            ingredient.pop(key, None)
    target = tmp_path / SAMPLE_RECIPE.name
    target.write_text(yaml.safe_dump(document, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return target


def test_recipe_ranking_service_lists_imported_recipes_with_auto_success_assumption(tmp_path):
    database = tmp_path / "poe_market.db"
    recipe_repository = SqliteRecipeRepository(database)
    RecipeImportService(recipe_repository).import_yaml(SAMPLE_RECIPE)

    market_repository = SqliteMarketRepository(database)
    _save_full_test_market(market_repository)

    rows = RecipeRankingService(recipe_repository, market_repository).rank_recipes(league="Mirage")

    assert len(rows) == 1
    row = rows[0]
    assert row.recipe_id == "poe1_mirage_viper_touch_spiked_gloves"
    assert row.known_one_attempt_cost_chaos > 30_000.0
    assert row.success_assumption_id == "vaal_success_chance"
    assert round(row.expected_cost_to_success_chaos) == round(row.known_one_attempt_cost_chaos / 0.005952381)
    assert row.estimated_sale_price_chaos == 350000.0
    assert row.expected_profit_chaos == row.estimated_sale_price_chaos - row.expected_cost_to_success_chaos
    assert row.roi_percent is not None
    assert row.output_price_source == "recipe_import"
    assert row.status == "ready"


def test_recipe_ranking_service_can_filter_by_min_profit(tmp_path):
    database = tmp_path / "poe_market.db"
    recipe_repository = SqliteRecipeRepository(database)
    RecipeImportService(recipe_repository).import_yaml(SAMPLE_RECIPE)

    market_repository = SqliteMarketRepository(database)
    _save_full_test_market(market_repository)

    rows = RecipeRankingService(recipe_repository, market_repository).rank_recipes(
        league="Mirage",
        min_profit_chaos=1_000_000,
    )

    assert rows == ()


def test_recipe_ranking_service_does_not_double_count_missing_ingredient_prices(tmp_path):
    database = tmp_path / "poe_market.db"
    recipe_repository = SqliteRecipeRepository(database)
    RecipeImportService(recipe_repository).import_yaml(_write_recipe_without_fallbacks(tmp_path))

    market_repository = SqliteMarketRepository(database)
    _save_full_test_market(market_repository)

    # Replace the latest Currency snapshot with one missing Divine Orb. The resolver
    # and the profit engine both notice the missing ingredient, but ranking should
    # report it once.
    context = MarketContext(game="poe1", league="Mirage", source="poe_ninja")
    market_repository.save_snapshot(
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
            ),
        )
    )

    rows = RecipeRankingService(recipe_repository, market_repository).rank_recipes(league="Mirage")

    assert len(rows) == 1
    assert rows[0].missing_price_count == 2  # two recipe ingredients use Divine Orb


def test_recipe_ranking_service_uses_recipe_fallbacks_to_keep_recipe_complete(tmp_path):
    database = tmp_path / "poe_market.db"
    recipe_repository = SqliteRecipeRepository(database)
    RecipeImportService(recipe_repository).import_yaml(SAMPLE_RECIPE)

    market_repository = SqliteMarketRepository(database)

    rows = RecipeRankingService(recipe_repository, market_repository).rank_recipes(league="Mirage")

    assert len(rows) == 1
    assert rows[0].missing_price_count == 0
    assert rows[0].status == "ready"


def test_recipe_ranking_service_can_filter_by_min_confidence_score(tmp_path):
    database = tmp_path / "poe_market.db"
    recipe_repository = SqliteRecipeRepository(database)
    RecipeImportService(recipe_repository).import_yaml(SAMPLE_RECIPE)

    rows = RecipeRankingService(recipe_repository, SqliteMarketRepository(database)).rank_recipes(
        league="Mirage",
        min_confidence_score=95,
    )

    assert rows == ()

    rows = RecipeRankingService(recipe_repository, SqliteMarketRepository(database)).rank_recipes(
        league="Mirage",
        min_confidence_score=30,
    )

    assert len(rows) == 1
