from poe_market_analyser.domain.market import MarketContext, MarketPrice, MarketSnapshot
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository


def _price(price_id: str, name: str, chaos: float = 1.0) -> MarketPrice:
    return MarketPrice(
        id=price_id,
        name=name,
        item_type="Currency",
        category="exchange",
        chaos_value=chaos,
        details_id=price_id,
        listing_count=100,
        raw={"id": price_id, "name": name},
    )


def test_find_latest_price_matches_shortened_poe_ninja_currency_slug(tmp_path):
    repository = SqliteMarketRepository(tmp_path / "poe_market.db")
    repository.save_snapshot(
        MarketSnapshot(
            context=MarketContext(game="poe1", league="Mirage", source="poe_ninja"),
            item_type="Currency",
            prices=(
                _price("alteration", "alteration", 0.05),
                _price("annulment", "annulment", 20.0),
                _price("scouring", "scouring", 0.5),
                _price("vaal", "vaal", 1.0),
                _price("regal", "regal", 1.0),
            ),
        )
    )

    assert repository.find_latest_price("Mirage", "Currency", "Orb of Alteration").id == "alteration"
    assert repository.find_latest_price("Mirage", "Currency", "Orb of Annulment").id == "annulment"
    assert repository.find_latest_price("Mirage", "Currency", "Orb of Scouring").id == "scouring"
    assert repository.find_latest_price("Mirage", "Currency", "Vaal Orb").id == "vaal"
    assert repository.find_latest_price("Mirage", "Currency", "Regal Orb").id == "regal"
