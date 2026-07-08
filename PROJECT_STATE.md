# POE Market Analyser - Project state

## Current scope

Desktop-oriented Python MVP core for Path of Exile 1 market/crafting profitability analysis.

Current default target:

- Game: Path of Exile 1
- League: Mirage
- IDE: PyCharm
- Runtime: Python 3.11+
- Storage: SQLite
- Recipe import: YAML schema `0.3`
- Market source: poe.ninja adapter

## Implemented workflow

The main hands-off command is:

```powershell
python -m poe_market_analyser.cli auto-rank --recipe-dir data\recipes --league Mirage --db poe_market.db --show-problems
```

It performs:

1. Import all YAML recipes from `data/recipes`.
2. Detect required market types from recipe ingredients.
3. Refresh required poe.ninja market snapshots.
4. Resolve ingredient prices from manual overrides, local cache, poe.ninja data, or recipe fallbacks.
5. Calculate one-attempt cost, expected cost, estimated sale price, profit and ROI.
6. Rank recipes and show data quality confidence.

## Implemented modules

- `domain.models` - crafting recipe model, ingredients, target item, assumptions, output pricing.
- `domain.market` - market snapshot and price abstractions.
- `domain.pricing` - resolved price book and missing price model.
- `infrastructure.importers.yaml_recipe_importer` - YAML -> domain model importer.
- `infrastructure.market.poe_ninja_provider` - poe.ninja market adapter.
- `infrastructure.storage.sqlite_recipe_repository` - recipe persistence.
- `infrastructure.storage.sqlite_market_repository` - market snapshots and manual price overrides.
- `application.price_resolver` - ingredient -> market cache/fallback resolution.
- `application.profit_engine` - simple expected-value profit engine.
- `application.output_pricing` - recipe-level output price estimates.
- `application.recipe_ranking_service` - automatic recipe ranking.
- `application.auto_analysis_service` - import + refresh + rank orchestration.
- `application.recipe_quality` - confidence score and quality flags.

## Recipe pack

Current recipe files:

- `poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml`
- `poe1_mirage_large_cluster_alt_regal_recipe.yaml`
- `poe1_mirage_fractured_spell_suppression_boots_essence_recipe.yaml`
- `poe1_mirage_amethyst_ring_chaos_res_essence_recipe.yaml`
- `poe1_mirage_eldritch_attack_speed_gloves_essence_recipe.yaml`
- `poe1_mirage_medium_cluster_flask_alt_regal_recipe.yaml`

All non-user-supplied extra recipes are draft research seeds. They are useful for testing automated ranking, but output price estimates and expected quantities should be replaced later by trade-search and mod-weight based data.

## Useful commands

Install/update dependencies:

```powershell
python -m pip install -e ".[dev]"
```

Run tests:

```powershell
python -m pytest
```

Import all recipes:

```powershell
python -m poe_market_analyser.cli import-dir data\recipes --db poe_market.db
```

Fetch required market types only:

```powershell
python -m poe_market_analyser.cli market-fetch-required --league Mirage --db poe_market.db
```

Auto-rank all recipes:

```powershell
python -m poe_market_analyser.cli auto-rank --recipe-dir data\recipes --league Mirage --db poe_market.db --show-problems
```

Export CSV ranking:

```powershell
python -m poe_market_analyser.cli auto-rank --recipe-dir data\recipes --league Mirage --db poe_market.db --export-csv exports\ranking.csv
```

Filter by confidence:

```powershell
python -m poe_market_analyser.cli auto-rank --skip-import --league Mirage --db poe_market.db --min-confidence-score 70
```

## Missing / next major elements

1. Exact output item pricing using trade search or a user-supplied snapshot.
2. Better base item pricing for rare/fractured/influenced bases.
3. Mod/stat IDs instead of text-only target mods.
4. More recipes with better assumptions and sources.
5. Checkpoint-level simulation and salvage values.
6. GUI in PySide6.
7. Configuration screen for league/source selection.
8. PoE2 support after PoE1 workflow stabilizes.

## Current known limitation

Profit ranking depends heavily on `pricing.output.estimated_sale_price_chaos` in YAML. Until exact trade pricing is implemented, ranking should be treated as a draft opportunity scanner, not a final buy/craft recommendation.

## Latest continuation update

Added stored output sale price overrides and ranking cost-driver details.

New CLI commands:

    python -m poe_market_analyser.cli output-price-override-set <recipe_id> --league Mirage --sale-chaos <price> --db poe_market.db
    python -m poe_market_analyser.cli output-price-override-list --league Mirage --db poe_market.db

New ranking flag:

    --show-cost-drivers

Output price resolution priority is now CLI override > stored SQLite output override > YAML `pricing.output` > missing.

Test count after this update: 42 passed.

## Latest iteration: experimental trade output pricing

Added an isolated `PoeTradeProvider` adapter for pathofexile.com trade search/fetch endpoints, plus `TradePriceEstimator` and `trade-price-estimate` CLI.

New modules:

- `domain/trade.py`
- `application/trade_query_builder.py`
- `application/trade_price_estimator.py`
- `infrastructure/trade/poe_trade_provider.py`

New command:

```powershell
python -m poe_market_analyser.cli trade-price-estimate <recipe_id> --league Mirage --db poe_market.db --max-results 20 --sample-size 5 --save-output-override
```

Current behavior:

1. Loads recipe from SQLite.
2. Builds trade query from `pricing.output.trade_search.query`, or generates a broad fallback query from target base/influence/corruption/item level.
3. Searches pathofexile.com trade and fetches listings.
4. Converts listing currencies to chaos using local poe.ninja `Currency` cache.
5. Uses the median of the cheapest converted sample as output estimate.
6. Optionally stores it as an output-price override for ranking.

Known limitations:

- Exact rare pricing is only reliable once recipes contain trade stat ids or explicit `pricing.output.trade_search.query` JSON.
- Generated fallback queries are useful for smoke tests and base comparable pricing, not final profit decisions for complex rare outputs.
- The trade endpoint is isolated as an adapter because it can change and may be rate-limited.
