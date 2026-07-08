from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from poe_market_analyser.domain.market import ManualPriceOverride, MarketContext, MarketPrice, MarketSnapshot


class SqliteMarketRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS market_snapshots (
                    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game TEXT NOT NULL,
                    league TEXT NOT NULL,
                    source TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    fetched_at_utc TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS market_prices (
                    snapshot_id INTEGER NOT NULL,
                    price_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    category TEXT NOT NULL,
                    chaos_value REAL NOT NULL,
                    divine_value REAL,
                    listing_count INTEGER,
                    details_id TEXT,
                    source TEXT NOT NULL,
                    fetched_at_utc TEXT NOT NULL,
                    raw_json TEXT NOT NULL,
                    PRIMARY KEY (snapshot_id, price_id),
                    FOREIGN KEY (snapshot_id) REFERENCES market_snapshots(snapshot_id) ON DELETE CASCADE
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_market_prices_lookup
                ON market_prices (item_type, name, details_id)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS manual_price_overrides (
                    game TEXT NOT NULL,
                    league TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    market_name TEXT NOT NULL,
                    normalized_name TEXT NOT NULL,
                    chaos_value REAL NOT NULL,
                    divine_value REAL,
                    listing_count INTEGER,
                    confidence TEXT NOT NULL,
                    note TEXT,
                    updated_at_utc TEXT NOT NULL,
                    PRIMARY KEY (game, league, item_type, normalized_name)
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_manual_price_overrides_lookup
                ON manual_price_overrides (game, league, item_type, normalized_name)
                """
            )
            connection.commit()

    def save_snapshot(self, snapshot: MarketSnapshot) -> int:
        self.initialize()
        fetched_at = _format_dt(snapshot.fetched_at_utc)
        with self._connect() as connection:
            connection.execute("PRAGMA foreign_keys = ON")
            cursor = connection.execute(
                """
                INSERT INTO market_snapshots (game, league, source, item_type, fetched_at_utc)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    snapshot.context.game,
                    snapshot.context.league,
                    snapshot.context.source,
                    snapshot.item_type,
                    fetched_at,
                ),
            )
            snapshot_id = int(cursor.lastrowid)
            connection.executemany(
                """
                INSERT INTO market_prices (
                    snapshot_id,
                    price_id,
                    name,
                    item_type,
                    category,
                    chaos_value,
                    divine_value,
                    listing_count,
                    details_id,
                    source,
                    fetched_at_utc,
                    raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        snapshot_id,
                        price.id,
                        price.name,
                        price.item_type,
                        price.category,
                        price.chaos_value,
                        price.divine_value,
                        price.listing_count,
                        price.details_id,
                        price.source,
                        _format_dt(price.fetched_at_utc),
                        json.dumps(price.raw, ensure_ascii=False, sort_keys=True),
                    )
                    for price in snapshot.prices
                ],
            )
            connection.commit()
        return snapshot_id

    def list_latest_prices(
        self,
        league: str,
        item_type: str | None = None,
        limit: int = 50,
        game: str = "poe1",
        source: str = "poe_ninja",
    ) -> list[dict[str, Any]]:
        self.initialize()
        conditions = ["s.game = ?", "s.league = ?", "s.source = ?"]
        params: list[Any] = [game, league, source]
        if item_type is not None:
            conditions.append("s.item_type = ?")
            params.append(item_type)
        where_sql = " AND ".join(conditions)
        params.append(limit)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT
                    p.price_id,
                    p.name,
                    p.item_type,
                    p.category,
                    p.chaos_value,
                    p.divine_value,
                    p.listing_count,
                    p.details_id,
                    p.source,
                    p.fetched_at_utc,
                    s.league,
                    s.snapshot_id
                FROM market_prices p
                JOIN market_snapshots s ON s.snapshot_id = p.snapshot_id
                WHERE {where_sql}
                  AND s.snapshot_id IN (
                    SELECT MAX(snapshot_id)
                    FROM market_snapshots
                    WHERE game = ? AND league = ? AND source = ?
                    GROUP BY item_type
                  )
                ORDER BY p.chaos_value DESC, p.name ASC
                LIMIT ?
                """,
                (*params[:-1], game, league, source, params[-1]),
            ).fetchall()
        return [dict(row) for row in rows]

    def find_latest_price(
        self,
        league: str,
        item_type: str,
        name: str,
        game: str = "poe1",
        source: str = "poe_ninja",
    ) -> MarketPrice | None:
        """Find a price in the latest snapshot for an item type.

        poe.ninja sometimes returns human-readable names ("Gilded Fossil") and
        sometimes slug-like values ("gilded-fossil") depending on endpoint and
        response shape. Match against name, price_id and details_id using a
        shared normalized key so recipe files can stay readable.
        """
        self.initialize()
        expected_key = _normalize_market_key(name)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                """
                SELECT p.*
                FROM market_prices p
                JOIN market_snapshots s ON s.snapshot_id = p.snapshot_id
                WHERE s.game = ?
                  AND s.league = ?
                  AND s.source = ?
                  AND s.item_type = ?
                  AND s.snapshot_id = (
                    SELECT MAX(snapshot_id)
                    FROM market_snapshots
                    WHERE game = ? AND league = ? AND source = ? AND item_type = ?
                  )
                ORDER BY p.chaos_value DESC, p.name ASC
                """,
                (game, league, source, item_type, game, league, source, item_type),
            ).fetchall()
        expected_aliases = _market_key_aliases(expected_key)
        candidates: list[dict[str, Any]] = []
        for row in rows:
            data = dict(row)
            candidate_aliases: set[str] = set()
            for value in (data.get("name"), data.get("price_id"), data.get("details_id")):
                candidate_aliases.update(_market_key_aliases(value))
            if expected_aliases.intersection(candidate_aliases):
                candidates.append(data)

        best = _select_best_market_price_row(candidates, expected_key, item_type)
        if best is None:
            return None
        return _row_to_market_price(best)

    def save_manual_price_override(self, override: ManualPriceOverride) -> None:
        self.initialize()
        normalized_name = _normalize_market_key(override.market_name)
        updated_at = _format_dt(override.updated_at_utc)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO manual_price_overrides (
                    game,
                    league,
                    item_type,
                    market_name,
                    normalized_name,
                    chaos_value,
                    divine_value,
                    listing_count,
                    confidence,
                    note,
                    updated_at_utc
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(game, league, item_type, normalized_name) DO UPDATE SET
                    market_name = excluded.market_name,
                    chaos_value = excluded.chaos_value,
                    divine_value = excluded.divine_value,
                    listing_count = excluded.listing_count,
                    confidence = excluded.confidence,
                    note = excluded.note,
                    updated_at_utc = excluded.updated_at_utc
                """,
                (
                    override.game,
                    override.league,
                    override.item_type,
                    override.market_name,
                    normalized_name,
                    override.chaos_value,
                    override.divine_value,
                    override.listing_count,
                    override.confidence,
                    override.note,
                    updated_at,
                ),
            )
            connection.commit()

    def find_manual_price_override(
        self,
        league: str,
        item_type: str,
        name: str,
        game: str = "poe1",
    ) -> ManualPriceOverride | None:
        self.initialize()
        normalized_name = _normalize_market_key(name)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT *
                FROM manual_price_overrides
                WHERE game = ?
                  AND league = ?
                  AND item_type = ?
                  AND normalized_name = ?
                """,
                (game, league, item_type, normalized_name),
            ).fetchone()
        if row is None:
            return None
        return _row_to_manual_price_override(dict(row))

    def list_manual_price_overrides(
        self,
        league: str,
        item_type: str | None = None,
        limit: int = 50,
        game: str = "poe1",
    ) -> list[dict[str, Any]]:
        self.initialize()
        conditions = ["game = ?", "league = ?"]
        params: list[Any] = [game, league]
        if item_type is not None:
            conditions.append("item_type = ?")
            params.append(item_type)
        params.append(limit)
        where_sql = " AND ".join(conditions)
        with self._connect() as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f"""
                SELECT *
                FROM manual_price_overrides
                WHERE {where_sql}
                ORDER BY item_type ASC, market_name ASC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return [dict(row) for row in rows]

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)



def _select_best_market_price_row(
    candidates: list[dict[str, Any]],
    expected_key: str,
    item_type: str,
) -> dict[str, Any] | None:
    if not candidates:
        return None

    return max(
        candidates,
        key=lambda row: _market_price_match_score(row, expected_key, item_type),
    )


def _market_price_match_score(row: dict[str, Any], expected_key: str, item_type: str) -> tuple[float, float, float]:
    name_key = _normalize_market_key(row.get("name"))
    price_id_key = _normalize_market_key(row.get("price_id"))
    details_id_key = _normalize_market_key(row.get("details_id"))
    expected_aliases = _market_key_aliases(expected_key)
    name_aliases = _market_key_aliases(name_key)
    price_id_aliases = _market_key_aliases(price_id_key)
    details_id_aliases = _market_key_aliases(details_id_key)

    score = 0.0

    # Strongest signal: the unique poe.ninja identifier is exactly the item we asked for.
    if details_id_key == expected_key:
        score += 100.0
    elif expected_aliases.intersection(details_id_aliases):
        score += 85.0
    if price_id_key == expected_key:
        score += 90.0
    elif expected_aliases.intersection(price_id_aliases):
        score += 75.0
    if name_key == expected_key:
        score += 60.0
    elif expected_aliases.intersection(name_aliases):
        score += 45.0

    listing_count = row.get("listing_count")
    if listing_count is not None:
        score += min(float(listing_count), 1000.0) / 100.0
        if int(listing_count) < 10:
            score -= 20.0

    if str(item_type).lower() == "basetype":
        combined_key = f"{price_id_key}-{details_id_key}"
        influence_words = (
            "hunter",
            "warlord",
            "elder",
            "shaper",
            "crusader",
            "redeemer",
            "synthesised",
            "synthesized",
            "fractured",
        )
        looks_specialised = any(word in combined_key for word in influence_words)
        identifier_is_exact = price_id_key == expected_key or details_id_key == expected_key
        if looks_specialised and not identifier_is_exact:
            score -= 50.0

    # Deterministic tie-breakers: prefer deeper market and then lower ask-like value.
    tie_listing_count = float(listing_count or 0)
    chaos_value = float(row.get("chaos_value") or 0.0)
    return (score, tie_listing_count, -chaos_value)

def _row_to_market_price(row: dict[str, Any]) -> MarketPrice:
    return MarketPrice(
        id=row["price_id"],
        name=row["name"],
        item_type=row["item_type"],
        category=row["category"],
        chaos_value=float(row["chaos_value"]),
        divine_value=None if row["divine_value"] is None else float(row["divine_value"]),
        listing_count=None if row["listing_count"] is None else int(row["listing_count"]),
        details_id=row["details_id"],
        source=row["source"],
        fetched_at_utc=_parse_dt(row["fetched_at_utc"]),
        raw=json.loads(row["raw_json"]),
    )


def _row_to_manual_price_override(row: dict[str, Any]) -> ManualPriceOverride:
    return ManualPriceOverride(
        game=row["game"],
        league=row["league"],
        item_type=row["item_type"],
        market_name=row["market_name"],
        chaos_value=float(row["chaos_value"]),
        divine_value=None if row["divine_value"] is None else float(row["divine_value"]),
        listing_count=None if row["listing_count"] is None else int(row["listing_count"]),
        confidence=row["confidence"],
        note=row["note"],
        updated_at_utc=_parse_dt(row["updated_at_utc"]),
    )


def _format_dt(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _parse_dt(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _normalize_market_key(value: Any) -> str:
    if value is None:
        return ""
    normalized = str(value).strip().lower().replace("'", "")
    for char in [" ", "/", "_", ":", ",", ".", "(", ")"]:
        normalized = normalized.replace(char, "-")
    while "--" in normalized:
        normalized = normalized.replace("--", "-")
    return normalized.strip("-")


def _market_key_aliases(value: Any) -> set[str]:
    """Return common poe.ninja aliases for readable recipe item names.

    The current poe.ninja exchange endpoint often uses shortened currency ids,
    for example ``alteration`` instead of ``orb-of-alteration``. Recipe files
    should remain readable, so the repository expands a small set of mechanical
    aliases during lookup instead of forcing users to know poe.ninja slugs.
    """
    key = _normalize_market_key(value)
    if not key:
        return set()

    aliases = {key}

    if key.startswith("orb-of-"):
        core = key.removeprefix("orb-of-")
        if core:
            aliases.add(core)
            aliases.add(f"{core}-orb")

    if key.endswith("-orb"):
        core = key.removesuffix("-orb")
        if core:
            aliases.add(core)
            aliases.add(f"orb-of-{core}")

    # A few common names use a reversed natural-language form.
    if key == "mirror-of-kalandra":
        aliases.add("mirror")
    if key == "orb-of-annulment":
        aliases.add("annulment")
    if key == "orb-of-alteration":
        aliases.add("alteration")
    if key == "orb-of-scouring":
        aliases.add("scouring")
    if key == "vaal-orb":
        aliases.add("vaal")
        aliases.add("orb-of-vaal")
    if key == "regal-orb":
        aliases.add("regal")
        aliases.add("orb-of-regal")

    return {alias for alias in aliases if alias}
