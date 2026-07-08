from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import requests

from poe_market_analyser.domain.market import MarketContext, MarketPrice, MarketSnapshot


POE1_EXCHANGE_OVERVIEW_TYPES = frozenset(
    {
        "Currency",
        "Fragment",
        "Runegraft",
        "AllflameEmber",
        "Tattoo",
        "Omen",
        "DjinnCoin",
        "DivinationCard",
        "Artifact",
        "Oil",
        "DeliriumOrb",
        "Scarab",
        "Astrolabe",
        "Fossil",
        "Resonator",
        "Essence",
    }
)

POE1_STASH_ITEM_OVERVIEW_TYPES = frozenset(
    {
        "Wombgift",
        "Incubator",
        "UniqueWeapon",
        "UniqueArmour",
        "UniqueAccessory",
        "UniqueFlask",
        "UniqueJewel",
        "ForbiddenJewel",
        "ShrineBelt",
        "UniqueTincture",
        "UniqueRelic",
        "SkillGem",
        "ImbuedGem",
        "ClusterJewel",
        "Map",
        "BlightedMap",
        "BlightRavagedMap",
        "UniqueMap",
        "ValdoMap",
        "Invitation",
        "Memory",
        "IncursionTemple",
        "BaseType",
        "Beast",
        "Vial",
    }
)


class PoeNinjaProviderError(RuntimeError):
    pass


class PoeNinjaProvider:
    """Adapter for poe.ninja economy endpoints.

    The current PoE1 economy API exposes two important endpoint families:
    - exchange/current/overview for exchange-like categories, e.g. Currency, Fossil, Essence
    - stash/current/item/overview for stash-priced items, e.g. Beast, BaseType, uniques

    Keep this class isolated from the domain and profit engine. If poe.ninja
    changes URL shape later, only this adapter should need to change.
    """

    def __init__(
        self,
        base_url: str = "https://poe.ninja/poe1/api/economy",
        timeout_seconds: float = 20.0,
        session: requests.Session | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.session = session or requests.Session()
        self.session.headers.setdefault(
            "User-Agent",
            "POE-Market-Analyser-MVP/0.1 (+local desktop app; contact: user-configured)",
        )

    def fetch_currency_prices(self, league: str, currency_type: str = "Currency") -> MarketSnapshot:
        """Fetch exchange overview prices.

        The method name remains generic for the first MVP interface, but poe.ninja
        uses this endpoint for more than Currency/Fragment, including Fossil,
        Resonator, Essence, Scarab, Oil and similar exchangeable categories.
        """
        payload = self._get_json(
            "exchange/current/overview",
            {
                "league": league,
                "type": currency_type,
            },
        )
        lines = _ensure_lines(payload, "exchange/current/overview")
        core_items = _build_core_item_lookup(payload)
        fetched_at = datetime.now(UTC)
        prices = tuple(
            self._map_exchange_line(
                line,
                item_type=currency_type,
                fetched_at=fetched_at,
                core_items=core_items,
            )
            for line in lines
        )
        return MarketSnapshot(
            context=MarketContext(game="poe1", league=league, source="poe_ninja"),
            item_type=currency_type,
            prices=prices,
            fetched_at_utc=fetched_at,
        )

    def fetch_item_prices(self, league: str, item_type: str) -> MarketSnapshot:
        payload = self._get_json(
            "stash/current/item/overview",
            {
                "league": league,
                "type": item_type,
            },
        )
        lines = _ensure_lines(payload, "stash/current/item/overview")
        fetched_at = datetime.now(UTC)
        prices = tuple(
            self._map_item_line(line, item_type=item_type, fetched_at=fetched_at)
            for line in lines
        )
        return MarketSnapshot(
            context=MarketContext(game="poe1", league=league, source="poe_ninja"),
            item_type=item_type,
            prices=prices,
            fetched_at_utc=fetched_at,
        )

    def _get_json(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/{endpoint}"
        response = self.session.get(url, params=params, timeout=self.timeout_seconds)
        try:
            response.raise_for_status()
        except requests.HTTPError as error:
            raise PoeNinjaProviderError(
                f"poe.ninja request failed: {response.status_code} {response.reason}; url={response.url}"
            ) from error

        try:
            payload = response.json()
        except ValueError as error:
            raise PoeNinjaProviderError("poe.ninja returned non-JSON response.") from error

        if not isinstance(payload, dict):
            raise PoeNinjaProviderError("poe.ninja response root must be a JSON object.")
        return payload

    def _map_exchange_line(
        self,
        line: dict[str, Any],
        item_type: str,
        fetched_at: datetime,
        core_items: dict[str, dict[str, Any]] | None = None,
    ) -> MarketPrice:
        core_items = core_items or {}
        line_id = _optional_str(line.get("id"))
        core_item = core_items.get(line_id or "", {})

        name = str(
            line.get("currencyTypeName")
            or line.get("name")
            or core_item.get("name")
            or line_id
            or ""
        )
        details_id = _optional_str(line.get("detailsId") or core_item.get("detailsId"))
        price_id = details_id or line_id or _normalize_id(name)
        chaos_value = _as_float(
            line.get("chaosEquivalent")
            if line.get("chaosEquivalent") is not None
            else line.get("primaryValue"),
            default=0.0,
        )
        listing_count = _extract_listing_count(line)
        return MarketPrice(
            id=price_id,
            name=name,
            item_type=item_type,
            category=str(core_item.get("category") or "exchange"),
            chaos_value=chaos_value,
            divine_value=None,
            listing_count=listing_count,
            details_id=details_id,
            source="poe_ninja",
            fetched_at_utc=fetched_at,
            raw=line,
        )

    def _map_item_line(self, line: dict[str, Any], item_type: str, fetched_at: datetime) -> MarketPrice:
        name = str(line.get("name") or line.get("baseType") or "")
        base_type = _optional_str(line.get("baseType"))
        details_id = _optional_str(line.get("detailsId"))
        price_id = details_id or _optional_str(line.get("id")) or _normalize_id(f"{name}-{base_type or item_type}")
        return MarketPrice(
            id=price_id,
            name=name,
            item_type=item_type,
            category=str(line.get("category") or "item"),
            chaos_value=_as_float(line.get("chaosValue") if line.get("chaosValue") is not None else line.get("primaryValue"), default=0.0),
            divine_value=_optional_float(line.get("divineValue")),
            listing_count=_optional_int(line.get("listingCount") or line.get("count")),
            details_id=details_id,
            source="poe_ninja",
            fetched_at_utc=fetched_at,
            raw=line,
        )


def _ensure_lines(payload: dict[str, Any], endpoint: str) -> list[dict[str, Any]]:
    lines = payload.get("lines", [])
    if not isinstance(lines, list):
        raise PoeNinjaProviderError(f"poe.ninja {endpoint} response field 'lines' must be a list.")
    result: list[dict[str, Any]] = []
    for line in lines:
        if isinstance(line, dict):
            result.append(line)
    return result


def _build_core_item_lookup(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    core = payload.get("core")
    if not isinstance(core, dict):
        return {}
    items = core.get("items")
    if isinstance(items, dict):
        item_iterable = items.values()
    elif isinstance(items, list):
        item_iterable = items
    else:
        return {}

    lookup: dict[str, dict[str, Any]] = {}
    for item in item_iterable:
        if not isinstance(item, dict):
            continue
        item_id = _optional_str(item.get("id"))
        if item_id:
            lookup[item_id] = item
    return lookup


def _extract_listing_count(line: dict[str, Any]) -> int | None:
    if line.get("volumePrimaryValue") is not None:
        listing_count = _optional_int(line.get("volumePrimaryValue"))
        if listing_count is not None:
            return listing_count
    receive = line.get("receive")
    if isinstance(receive, dict):
        listing_count = _optional_int(receive.get("listing_count") or receive.get("count"))
        if listing_count is not None:
            return listing_count
    pay = line.get("pay")
    if isinstance(pay, dict):
        listing_count = _optional_int(pay.get("listing_count") or pay.get("count"))
        if listing_count is not None:
            return listing_count
    return _optional_int(line.get("listingCount") or line.get("count"))


def _as_float(value: Any, default: float) -> float:
    parsed = _optional_float(value)
    return default if parsed is None else parsed


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _normalize_id(value: str) -> str:
    normalized = value.strip().lower().replace("'", "")
    for char in [" ", "/", "_", ":", ",", ".", "(", ")"]:
        normalized = normalized.replace(char, "-")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized.strip("-")
