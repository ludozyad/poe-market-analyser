from poe_market_analyser.domain.market import MarketContext, MarketPrice, MarketSnapshot
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository


def test_market_repository_saves_and_lists_latest_prices(tmp_path):
    repository = SqliteMarketRepository(tmp_path / "poe_market.db")
    snapshot = MarketSnapshot(
        context=MarketContext(game="poe1", league="Mirage", source="poe_ninja"),
        item_type="Fossil",
        prices=(
            MarketPrice(
                id="gilded-fossil",
                name="Gilded Fossil",
                item_type="Fossil",
                category="item",
                chaos_value=12.25,
                divine_value=0.07,
                listing_count=120,
                details_id="gilded-fossil",
                raw={"name": "Gilded Fossil"},
            ),
        ),
    )

    snapshot_id = repository.save_snapshot(snapshot)
    rows = repository.list_latest_prices("Mirage", item_type="Fossil")

    assert snapshot_id == 1
    assert len(rows) == 1
    assert rows[0]["name"] == "Gilded Fossil"
    assert rows[0]["chaos_value"] == 12.25
    assert rows[0]["snapshot_id"] == 1


def test_market_repository_finds_latest_price_by_name(tmp_path):
    repository = SqliteMarketRepository(tmp_path / "poe_market.db")
    snapshot = MarketSnapshot(
        context=MarketContext(game="poe1", league="Mirage", source="poe_ninja"),
        item_type="Beast",
        prices=(
            MarketPrice(
                id="craicic-chimeral",
                name="Craicic Chimeral",
                item_type="Beast",
                category="item",
                chaos_value=55.0,
                details_id="craicic-chimeral",
                raw={"name": "Craicic Chimeral"},
            ),
        ),
    )

    repository.save_snapshot(snapshot)
    price = repository.find_latest_price("Mirage", "Beast", "craicic chimeral")

    assert price is not None
    assert price.name == "Craicic Chimeral"
    assert price.chaos_value == 55.0


def test_market_repository_finds_latest_price_by_slug_or_details_id(tmp_path):
    repository = SqliteMarketRepository(tmp_path / "poe_market.db")
    snapshot = MarketSnapshot(
        context=MarketContext(game="poe1", league="Mirage", source="poe_ninja"),
        item_type="Fossil",
        prices=(
            MarketPrice(
                id="gilded-fossil",
                name="gilded-fossil",
                item_type="Fossil",
                category="exchange",
                chaos_value=30.0,
                details_id="gilded-fossil",
                raw={"id": "gilded-fossil"},
            ),
        ),
    )

    repository.save_snapshot(snapshot)
    price = repository.find_latest_price("Mirage", "Fossil", "Gilded Fossil")

    assert price is not None
    assert price.id == "gilded-fossil"
    assert price.chaos_value == 30.0


def test_market_repository_prefers_exact_identifier_over_expensive_name_only_base_candidate(tmp_path):
    repository = SqliteMarketRepository(tmp_path / "poe_market.db")
    snapshot = MarketSnapshot(
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
            MarketPrice(
                id="spiked-gloves",
                name="Spiked Gloves",
                item_type="BaseType",
                category="item",
                chaos_value=25.0,
                listing_count=100,
                details_id="spiked-gloves",
                raw={"name": "Spiked Gloves"},
            ),
        ),
    )

    repository.save_snapshot(snapshot)
    price = repository.find_latest_price("Mirage", "BaseType", "Spiked Gloves")

    assert price is not None
    assert price.id == "spiked-gloves"
    assert price.chaos_value == 25.0
