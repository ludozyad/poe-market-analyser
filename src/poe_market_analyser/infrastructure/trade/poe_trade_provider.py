from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

import requests

from poe_market_analyser.domain.trade import TradeListing, TradeListingPrice, TradeSearchResult


class PoeTradeProviderError(RuntimeError):
    pass


class PoeTradeProvider:
    """Small client for the pathofexile.com trade-search endpoints.

    The provider is intentionally isolated behind an adapter because these
    endpoints are less stable than the local domain model. Unit tests mock the
    HTTP session; production callers should use conservative result limits.
    """

    def __init__(
        self,
        base_url: str = "https://www.pathofexile.com/api/trade",
        session: requests.Session | None = None,
        timeout_seconds: float = 20.0,
        user_agent: str | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent or os.getenv(
            "POE_MARKET_ANALYSER_USER_AGENT",
            "POE-Market-Analyser-MVP/0.1 (+https://github.com/ludozyad/poe-market-analyser)",
        )

    def search(self, league: str, query: dict[str, Any], fetch_limit: int = 20) -> TradeSearchResult:
        if fetch_limit < 0:
            raise ValueError("fetch_limit cannot be negative")

        payload = _ensure_trade_query_payload(query)
        search_url = f"{self.base_url}/search/{quote(league, safe='')}"
        response = self.session.post(
            search_url,
            json=payload,
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            raise PoeTradeProviderError(
                f"PoE trade search failed: {response.status_code} {response.reason}; url={response.url}"
            ) from error

        data = response.json()
        query_id = str(data.get("id") or "")
        result_ids = tuple(str(item) for item in data.get("result", []) or [])
        if not query_id:
            raise PoeTradeProviderError("PoE trade search response did not contain query id")

        listings: list[TradeListing] = []
        ids_to_fetch = result_ids[:fetch_limit]
        for chunk in _chunks(ids_to_fetch, 10):
            listings.extend(self._fetch_listings(query_id, chunk))

        return TradeSearchResult(
            query_id=query_id,
            result_ids=result_ids,
            total_result_count=int(data.get("total", len(result_ids)) or len(result_ids)),
            listings=tuple(listings),
            search_url=f"https://www.pathofexile.com/trade/search/{quote(league, safe='')}/{query_id}",
            fetched_at_utc=datetime.now(UTC),
        )

    def _fetch_listings(self, query_id: str, listing_ids: tuple[str, ...]) -> tuple[TradeListing, ...]:
        if not listing_ids:
            return ()
        fetch_url = f"{self.base_url}/fetch/{','.join(listing_ids)}"
        response = self.session.get(
            fetch_url,
            params={"query": query_id},
            headers=self._headers(),
            timeout=self.timeout_seconds,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            raise PoeTradeProviderError(
                f"PoE trade fetch failed: {response.status_code} {response.reason}; url={response.url}"
            ) from error

        data = response.json()
        return tuple(_map_trade_listing(item) for item in data.get("result", []) or [])

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }


def _ensure_trade_query_payload(query: dict[str, Any]) -> dict[str, Any]:
    if "query" in query and "sort" in query:
        return query
    if "query" in query:
        return {"query": query["query"], "sort": query.get("sort", {"price": "asc"})}
    return {"query": query, "sort": {"price": "asc"}}


def _map_trade_listing(item: dict[str, Any]) -> TradeListing:
    listing = item.get("listing", {}) or {}
    price = listing.get("price") or None
    mapped_price: TradeListingPrice | None = None
    if isinstance(price, dict) and price.get("amount") is not None and price.get("currency"):
        mapped_price = TradeListingPrice(
            amount=float(price["amount"]),
            currency=str(price["currency"]),
        )

    item_data = item.get("item", {}) or {}
    account_data = listing.get("account", {}) or {}
    return TradeListing(
        listing_id=str(item.get("id") or listing.get("id") or ""),
        price=mapped_price,
        item_name=_optional_str(item_data.get("name")),
        item_type=_optional_str(item_data.get("typeLine")),
        account=_optional_str(account_data.get("name")),
        indexed_at=_optional_str(listing.get("indexed")),
        raw=item,
    )


def _chunks(values: tuple[str, ...], size: int):
    for index in range(0, len(values), size):
        yield values[index : index + size]


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
