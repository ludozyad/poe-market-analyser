from poe_market_analyser.infrastructure.trade.poe_trade_provider import PoeTradeProvider


class FakeResponse:
    def __init__(self, payload, status_code=200, reason="OK", url="https://example.test"):
        self._payload = payload
        self.status_code = status_code
        self.reason = reason
        self.url = url

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests

            raise requests.HTTPError("error", response=self)


class FakeSession:
    def __init__(self):
        self.posts = []
        self.gets = []

    def post(self, url, json, headers, timeout):
        self.posts.append((url, json, headers, timeout))
        return FakeResponse({"id": "query123", "result": ["a", "b"], "total": 2}, url=url)

    def get(self, url, params, headers, timeout):
        self.gets.append((url, params, headers, timeout))
        return FakeResponse(
            {
                "result": [
                    {
                        "id": "a",
                        "listing": {"price": {"amount": 2, "currency": "divine"}, "account": {"name": "seller"}},
                        "item": {"name": "", "typeLine": "Spiked Gloves"},
                    },
                    {
                        "id": "b",
                        "listing": {"price": {"amount": 100, "currency": "chaos"}},
                        "item": {"typeLine": "Spiked Gloves"},
                    },
                ]
            },
            url=url,
        )


def test_poe_trade_provider_searches_and_fetches_listings():
    session = FakeSession()
    provider = PoeTradeProvider(base_url="https://www.pathofexile.com/api/trade", session=session)

    result = provider.search("Mirage", {"query": {"status": {"option": "online"}}, "sort": {"price": "asc"}})

    assert result.query_id == "query123"
    assert result.total_result_count == 2
    assert result.search_url == "https://www.pathofexile.com/trade/search/Mirage/query123"
    assert len(result.listings) == 2
    assert result.listings[0].price.amount == 2
    assert result.listings[0].price.currency == "divine"
    assert session.posts[0][0].endswith("/search/Mirage")
    assert session.gets[0][0].endswith("/fetch/a,b")
    assert session.gets[0][1] == {"query": "query123"}
