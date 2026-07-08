from pathlib import Path

from poe_market_analyser.application.trade_price_estimator import TradePriceEstimator, TradePriceEstimatorConfig
from poe_market_analyser.domain.market import MarketContext, MarketPrice, MarketSnapshot
from poe_market_analyser.domain.trade import TradeListing, TradeListingPrice, TradeSearchResult
from poe_market_analyser.infrastructure.importers.yaml_recipe_importer import YamlRecipeImporter
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository

SAMPLE_RECIPE = Path("data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml")


class FakeTradeProvider:
    def search(self, league: str, query: dict, fetch_limit: int = 20) -> TradeSearchResult:
        assert league == "Mirage"
        assert fetch_limit == 4
        return TradeSearchResult(
            query_id="query123",
            result_ids=("1", "2", "3", "4"),
            total_result_count=12,
            listings=(
                TradeListing("1", TradeListingPrice(1, "divine")),
                TradeListing("2", TradeListingPrice(550, "chaos")),
                TradeListing("3", TradeListingPrice(2, "divine")),
                TradeListing("4", None),
            ),
            search_url="https://www.pathofexile.com/trade/search/Mirage/query123",
        )


def test_trade_price_estimator_converts_listing_prices_and_builds_override(tmp_path):
    market_repository = SqliteMarketRepository(tmp_path / "market.db")
    market_repository.save_snapshot(
        MarketSnapshot(
            context=MarketContext(game="poe1", league="Mirage", source="poe_ninja"),
            item_type="Currency",
            prices=(
                MarketPrice(
                    id="divine",
                    name="Divine Orb",
                    item_type="Currency",
                    category="Currency",
                    chaos_value=500.0,
                    divine_value=1.0,
                    listing_count=100,
                    details_id="divine",
                ),
            ),
        )
    )
    recipe = YamlRecipeImporter().import_file(SAMPLE_RECIPE)
    estimator = TradePriceEstimator(FakeTradeProvider(), market_repository)

    estimate = estimator.estimate_recipe_output(
        recipe,
        league="Mirage",
        config=TradePriceEstimatorConfig(max_results=4, sample_size=3),
    )

    assert estimate.estimated_sale_price_chaos == 550.0
    assert estimate.listing_prices_chaos == (500.0, 550.0, 1000.0)
    assert estimate.skipped_listing_count == 1
    assert estimate.query_id == "query123"
    override = estimator.build_output_override(estimate)
    assert override.estimated_sale_price_chaos == 550.0
    assert override.source == "poe_trade_search"
