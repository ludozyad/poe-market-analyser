from __future__ import annotations

from copy import deepcopy
from typing import Any

from poe_market_analyser.domain.models import CraftingRecipe, TextMod


ITEM_CLASS_TO_TRADE_CATEGORY = {
    "Gloves": "armour.gloves",
    "Boots": "armour.boots",
    "Body Armours": "armour.chest",
    "Body Armour": "armour.chest",
    "Helmets": "armour.helmet",
    "Helmet": "armour.helmet",
    "Rings": "accessory.ring",
    "Ring": "accessory.ring",
    "Amulets": "accessory.amulet",
    "Amulet": "accessory.amulet",
    "Belts": "accessory.belt",
    "Belt": "accessory.belt",
    "Jewels": "jewel",
    "Jewel": "jewel",
}

INFLUENCE_TO_TRADE_FILTER = {
    "shaper": "shaper_item",
    "elder": "elder_item",
    "crusader": "crusader_item",
    "redeemer": "redeemer_item",
    "hunter": "hunter_item",
    "warlord": "warlord_item",
}


def build_trade_query_from_recipe(recipe: CraftingRecipe, online_only: bool = True) -> dict[str, Any]:
    """Build the initial PoE trade query for a finished crafted output.

    Priority:
    1. pricing.output.trade_search.query in YAML - exact user/research supplied query.
    2. A generated best-effort query from target base and mods with stat_id.

    The generated query is intentionally conservative. Without stat_id values it
    searches comparable items by base/influence/corruption only, which is useful
    for debugging but too broad for final rare-item pricing.
    """
    configured_query = _configured_trade_query(recipe)
    if configured_query is not None:
        return configured_query

    base = recipe.target.base
    query: dict[str, Any] = {
        "status": {"option": "online" if online_only else "any"},
        "type": base.base_type,
        "stats": _build_stat_groups(recipe),
        "filters": {},
    }

    type_filters: dict[str, Any] = {}
    category = ITEM_CLASS_TO_TRADE_CATEGORY.get(base.item_class)
    if category:
        type_filters["category"] = {"option": category}
    if type_filters:
        query["filters"]["type_filters"] = {"filters": type_filters}

    misc_filters: dict[str, Any] = {}
    if base.item_level_min is not None:
        misc_filters["ilvl"] = {"min": base.item_level_min}
    misc_filters["corrupted"] = {"option": "true" if base.corrupted else "false"}
    for influence in base.influences:
        filter_id = INFLUENCE_TO_TRADE_FILTER.get(str(influence).strip().lower())
        if filter_id:
            misc_filters[filter_id] = {"option": "true"}
    if misc_filters:
        query["filters"]["misc_filters"] = {"filters": misc_filters}

    return {"query": query, "sort": {"price": "asc"}}


def _configured_trade_query(recipe: CraftingRecipe) -> dict[str, Any] | None:
    output = recipe.pricing.output
    if output is None:
        return None
    trade_search = output.metadata.get("trade_search")
    if not isinstance(trade_search, dict):
        return None
    query = trade_search.get("query")
    if isinstance(query, dict):
        return deepcopy(query)
    return None


def _build_stat_groups(recipe: CraftingRecipe) -> list[dict[str, Any]]:
    filters: list[dict[str, Any]] = []
    for mod in recipe.target.required_implicits:
        maybe_filter = _stat_filter_from_mod(mod)
        if maybe_filter is not None:
            filters.append(maybe_filter)
    for mod in recipe.target.required_affixes:
        maybe_filter = _stat_filter_from_mod(mod)
        if maybe_filter is not None:
            filters.append(maybe_filter)
    if not filters:
        return [{"type": "and", "filters": []}]

    groups: list[dict[str, Any]] = [{"type": "and", "filters": filters}]
    for group in recipe.target.any_of_affix_groups:
        option_filters = [item for item in (_stat_filter_from_mod(mod) for mod in group.options) if item is not None]
        if option_filters:
            groups.append({"type": "count", "value": {"min": group.min_required}, "filters": option_filters})
    return groups


def _stat_filter_from_mod(mod: TextMod) -> dict[str, Any] | None:
    if not mod.stat_id:
        return None
    value: dict[str, Any] = {}
    if "min" in mod.metadata:
        value["min"] = float(mod.metadata["min"])
    if "max" in mod.metadata:
        value["max"] = float(mod.metadata["max"])
    result: dict[str, Any] = {"id": mod.stat_id}
    if value:
        result["value"] = value
    return result
