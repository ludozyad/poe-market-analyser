# Continuation prompt for a new ChatGPT chat

We are building `POE Market Analyser`, a Python/PyCharm desktop-oriented app for Path of Exile 1 crafting market analysis.

Current MVP is in a GitHub/local project named `poe-market-analyser` / `poe_market_analyser_mvp`.

Current goals:

- PoE1 only, league Mirage for now.
- YAML recipe import schema `0.3`.
- poe.ninja market data cache in SQLite.
- Automatic recipe pack import + market refresh + ranking.
- Keep modules scalable for future league selection and PoE2.

What is already implemented:

- YAML recipe importer and validation.
- SQLite storage for recipes and market snapshots.
- poe.ninja adapter for Currency, Fossil, Beast, BaseType, ClusterJewel, Essence and similar types.
- Price resolver using manual overrides, local cache, poe.ninja data and recipe fallback prices.
- Expected-value profit engine.
- Output sale estimate from recipe YAML.
- `auto-rank` command that imports recipes, fetches required market types and ranks recipes by expected profit.
- Ranking quality/confidence score.
- CSV export and problem diagnostics.
- Test suite currently passing.

Important commands:

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m poe_market_analyser.cli auto-rank --recipe-dir data\recipes --league Mirage --db poe_market.db --show-problems
```

Next recommended implementation tasks:

1. Add exact output pricing strategy abstraction, starting with manual/imported trade snapshots.
2. Add `TradeQuery` section to YAML for target item pricing rules.
3. Add GUI skeleton in PySide6 only after core output pricing is stable.
4. Add more recipe seeds, but mark them draft and include confidence/source metadata.
5. Add checkpoint-level expected cost and salvage modeling.

When continuing, inspect `PROJECT_STATE.md`, `README.md`, `data/recipes`, and the test suite first.

Recent update after GitHub push:
- Verified repository is public at https://github.com/ludozyad/poe-market-analyser.
- Added `OutputPriceOverride` support in SQLite so finished item prices can be adjusted without editing recipe YAML.
- Added CLI commands `output-price-override-set` and `output-price-override-list`.
- Ranking now stores `cost_driver_details` and CLI can print them with `--show-cost-drivers`.
- Current tests: 42 passed.

Continue from: implement checkpoint/salvage modelling or a first `OutputPriceProvider` abstraction that can later plug into trade search snapshots.

Recent progress after GitHub push:

- Added experimental PoE trade output pricing.
- Added `PoeTradeProvider` for trade search/fetch.
- Added `TradePriceEstimator` with chaos conversion via local Currency cache.
- Added `trade-price-estimate` CLI, with optional `--save-output-override`.
- Added tests for query builder, provider HTTP mapping, estimator/currency conversion.
- Test count is now `46 passed`.

Next recommended steps:

1. Add `pricing.output.trade_search.query` blocks to selected recipes.
2. Add/collect Path of Exile trade `stat_id` mappings for target mods.
3. Add a command to print generated trade query JSON for debugging.
4. Add rate-limit handling/backoff for live trade endpoint.
5. Add snapshot storage for trade estimate history instead of only overwriting output override.
