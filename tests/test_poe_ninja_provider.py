from __future__ import annotations

import requests

from poe_market_analyser.infrastructure.market.poe_ninja_provider import PoeNinjaProvider


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200, reason: str = "OK", url: str = ""):
        self._payload = payload
        self.status_code = status_code
        self.reason = reason
        self.url = url

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}", response=self)

    def json(self) -> dict:
        return self._payload


class FakeSession:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls: list[dict] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, params: dict, timeout: float) -> FakeResponse:
        self.calls.append({"url": url, "params": params, "timeout": timeout})
        return FakeResponse(self.payload, url=url)


def test_fetch_currency_prices_maps_current_poe_ninja_exchange_response():
    session = FakeSession(
        {
            "core": {
                "items": [
                    {
                        "id": "divine",
                        "name": "Divine Orb",
                        "category": "Currency",
                        "detailsId": "divine-orb",
                    }
                ]
            },
            "lines": [
                {
                    "id": "divine",
                    "primaryValue": 548.4,
                    "volumePrimaryValue": 276023,
                }
            ],
        }
    )
    provider = PoeNinjaProvider(base_url="https://example.test/poe1/api/economy", session=session)

    snapshot = provider.fetch_currency_prices("Mirage")

    assert snapshot.context.game == "poe1"
    assert snapshot.context.league == "Mirage"
    assert snapshot.item_type == "Currency"
    assert len(snapshot.prices) == 1
    price = snapshot.prices[0]
    assert price.id == "divine-orb"
    assert price.name == "Divine Orb"
    assert price.chaos_value == 548.4
    assert price.listing_count == 276023
    assert price.category == "Currency"
    assert session.calls[0]["url"] == "https://example.test/poe1/api/economy/exchange/current/overview"
    assert session.calls[0]["params"] == {"league": "Mirage", "type": "Currency"}


def test_fetch_fossil_prices_uses_exchange_overview_shape():
    session = FakeSession(
        {
            "core": {
                "items": [
                    {
                        "id": "gilded-fossil",
                        "name": "Gilded Fossil",
                        "category": "Fossil",
                        "detailsId": "gilded-fossil",
                    }
                ]
            },
            "lines": [
                {
                    "id": "gilded-fossil",
                    "primaryValue": 12.25,
                    "volumePrimaryValue": 120,
                }
            ],
        }
    )
    provider = PoeNinjaProvider(base_url="https://example.test/poe1/api/economy", session=session)

    snapshot = provider.fetch_currency_prices("Mirage", "Fossil")

    assert snapshot.item_type == "Fossil"
    assert len(snapshot.prices) == 1
    price = snapshot.prices[0]
    assert price.id == "gilded-fossil"
    assert price.name == "Gilded Fossil"
    assert price.chaos_value == 12.25
    assert price.category == "Fossil"
    assert price.listing_count == 120
    assert session.calls[0]["url"] == "https://example.test/poe1/api/economy/exchange/current/overview"
    assert session.calls[0]["params"] == {"league": "Mirage", "type": "Fossil"}


def test_fetch_currency_prices_still_maps_legacy_response_shape():
    session = FakeSession(
        {
            "lines": [
                {
                    "currencyTypeName": "Divine Orb",
                    "chaosEquivalent": 178.5,
                    "detailsId": "divine-orb",
                    "receive": {"listing_count": 201000},
                }
            ]
        }
    )
    provider = PoeNinjaProvider(base_url="https://example.test/poe1/api/economy", session=session)

    snapshot = provider.fetch_currency_prices("Mirage")

    price = snapshot.prices[0]
    assert price.id == "divine-orb"
    assert price.name == "Divine Orb"
    assert price.chaos_value == 178.5
    assert price.listing_count == 201000


def test_fetch_item_prices_maps_current_stash_item_response():
    session = FakeSession(
        {
            "lines": [
                {
                    "name": "Craicic Chimeral",
                    "baseType": "Craicic Chimeral",
                    "chaosValue": 48.0,
                    "divineValue": 0.087,
                    "listingCount": 120,
                    "detailsId": "craicic-chimeral",
                }
            ]
        }
    )
    provider = PoeNinjaProvider(base_url="https://example.test/poe1/api/economy", session=session)

    snapshot = provider.fetch_item_prices("Mirage", "Beast")

    assert snapshot.item_type == "Beast"
    assert len(snapshot.prices) == 1
    price = snapshot.prices[0]
    assert price.id == "craicic-chimeral"
    assert price.name == "Craicic Chimeral"
    assert price.chaos_value == 48.0
    assert price.divine_value == 0.087
    assert price.listing_count == 120
    assert session.calls[0]["url"] == "https://example.test/poe1/api/economy/stash/current/item/overview"
    assert session.calls[0]["params"] == {"league": "Mirage", "type": "Beast"}
