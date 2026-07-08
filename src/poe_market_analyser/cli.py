from __future__ import annotations

import argparse
import csv
from pathlib import Path

from poe_market_analyser.application.auto_analysis_service import AutoAnalysisService
from poe_market_analyser.application.market_service import MarketDataService
from poe_market_analyser.application.output_pricing import OutputPriceOverride, resolve_output_price
from poe_market_analyser.application.price_resolver import MarketPriceResolver
from poe_market_analyser.application.profit_engine import SimpleExpectedValueProfitEngine
from poe_market_analyser.application.recipe_market_requirements import summarize_market_requirements
from poe_market_analyser.application.recipe_ranking_service import RecipeRankingRow, RecipeRankingService
from poe_market_analyser.application.recipe_service import RecipeImportService
from poe_market_analyser.domain.market import ManualPriceOverride
from poe_market_analyser.infrastructure.market.poe_ninja_provider import PoeNinjaProvider
from poe_market_analyser.infrastructure.storage.sqlite_market_repository import SqliteMarketRepository
from poe_market_analyser.infrastructure.storage.sqlite_recipe_repository import SqliteRecipeRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="POE Market Analyser MVP CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="Import a YAML crafting recipe.")
    import_parser.add_argument("path", type=Path)
    import_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))

    import_dir_parser = subparsers.add_parser("import-dir", help="Import every YAML recipe from a directory.")
    import_dir_parser.add_argument("path", type=Path)
    import_dir_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))
    import_dir_parser.add_argument("--no-recursive", action="store_true")

    list_parser = subparsers.add_parser("list", help="List imported recipes.")
    list_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))

    market_fetch_parser = subparsers.add_parser("market-fetch", help="Fetch poe.ninja market prices into SQLite.")
    market_fetch_parser.add_argument("--league", default="Mirage")
    market_fetch_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))
    market_fetch_parser.add_argument(
        "--types",
        nargs="+",
        default=["Currency", "Fossil", "Beast"],
        help="poe.ninja item types to fetch. Exchange-like types use exchange overview; stash items use stash item overview.",
    )

    market_fetch_required_parser = subparsers.add_parser(
        "market-fetch-required",
        help="Fetch only poe.ninja market types required by imported recipes.",
    )
    market_fetch_required_parser.add_argument("--league", default="Mirage")
    market_fetch_required_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))

    market_requirements_parser = subparsers.add_parser(
        "market-requirements",
        help="Show market types required by imported recipes.",
    )
    market_requirements_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))

    market_list_parser = subparsers.add_parser("market-list", help="List latest stored market prices.")
    market_list_parser.add_argument("--league", default="Mirage")
    market_list_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))
    market_list_parser.add_argument("--type", dest="item_type", default=None)
    market_list_parser.add_argument("--limit", type=int, default=20)

    override_set_parser = subparsers.add_parser(
        "price-override-set",
        help="Save a manual price override for items where poe.ninja is too generic or unreliable.",
    )
    override_set_parser.add_argument("--league", default="Mirage")
    override_set_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))
    override_set_parser.add_argument("--game", default="poe1")
    override_set_parser.add_argument("--type", dest="item_type", required=True)
    override_set_parser.add_argument("--name", required=True)
    override_set_parser.add_argument("--chaos", type=float, required=True)
    override_set_parser.add_argument("--divine", type=float, default=None)
    override_set_parser.add_argument("--listings", type=int, default=None)
    override_set_parser.add_argument("--confidence", default="manual")
    override_set_parser.add_argument("--note", default=None)

    override_list_parser = subparsers.add_parser("price-override-list", help="List saved manual price overrides.")
    override_list_parser.add_argument("--league", default="Mirage")
    override_list_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))
    override_list_parser.add_argument("--game", default="poe1")
    override_list_parser.add_argument("--type", dest="item_type", default=None)
    override_list_parser.add_argument("--limit", type=int, default=50)

    output_override_set_parser = subparsers.add_parser(
        "output-price-override-set",
        help="Save a recipe output sale price override without editing YAML.",
    )
    output_override_set_parser.add_argument("recipe_id")
    output_override_set_parser.add_argument("--league", default="Mirage")
    output_override_set_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))
    output_override_set_parser.add_argument("--game", default="poe1")
    output_override_set_parser.add_argument("--sale-chaos", type=float, required=True)
    output_override_set_parser.add_argument("--failed-resale-chaos", type=float, default=0.0)
    output_override_set_parser.add_argument("--confidence", default="checked_trade_output")
    output_override_set_parser.add_argument("--source", default="manual_override")
    output_override_set_parser.add_argument("--note", default=None)

    output_override_list_parser = subparsers.add_parser(
        "output-price-override-list",
        help="List saved output sale price overrides.",
    )
    output_override_list_parser.add_argument("--league", default="Mirage")
    output_override_list_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))
    output_override_list_parser.add_argument("--game", default="poe1")
    output_override_list_parser.add_argument("--limit", type=int, default=50)

    analyze_parser = subparsers.add_parser(
        "analyze-recipe",
        help="Resolve recipe ingredients from local market cache and calculate a first-pass cost analysis.",
    )
    analyze_parser.add_argument("recipe_id")
    analyze_parser.add_argument("--league", default=None)
    analyze_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))
    analyze_parser.add_argument("--sale-price-chaos", type=float, default=None)
    analyze_parser.add_argument("--failed-resale-chaos", type=float, default=None)
    analyze_parser.add_argument("--success-assumption-id", default=None)

    rank_parser = subparsers.add_parser(
        "rank-recipes",
        help="Automatically analyse all imported recipes and rank them by current known/expected cost.",
    )
    _add_ranking_arguments(rank_parser)

    auto_rank_parser = subparsers.add_parser(
        "auto-rank",
        help="Import recipe directory, refresh required market data, and rank recipes in one command.",
    )
    _add_ranking_arguments(auto_rank_parser)
    auto_rank_parser.add_argument("--recipe-dir", type=Path, default=Path("data/recipes"))
    auto_rank_parser.add_argument("--no-recursive", action="store_true")
    auto_rank_parser.add_argument("--skip-import", action="store_true")
    auto_rank_parser.add_argument("--skip-market-refresh", action="store_true")

    args = parser.parse_args()

    if args.command == "import":
        repository = SqliteRecipeRepository(args.db)
        service = RecipeImportService(repository)
        recipe = service.import_yaml(args.path)
        print(f"Imported recipe: {recipe.id} ({recipe.name})")
        return

    if args.command == "import-dir":
        repository = SqliteRecipeRepository(args.db)
        recipes = RecipeImportService(repository).import_directory(
            args.path,
            recursive=not args.no_recursive,
        )
        if not recipes:
            print("No YAML recipes found.")
            return
        print(f"Imported {len(recipes)} recipes:")
        for recipe in recipes:
            print(f"- {recipe.id} ({recipe.name})")
        return

    if args.command == "list":
        repository = SqliteRecipeRepository(args.db)
        rows = repository.list_summaries()
        if not rows:
            print("No recipes imported yet.")
            return
        for row in rows:
            print(
                f"{row['recipe_id']} | {row['name']} | {row['game']} | "
                f"{row['default_league']} | {row['status']} | schema {row['schema_version']}"
            )
        return

    if args.command == "market-fetch":
        provider = PoeNinjaProvider()
        repository = SqliteMarketRepository(args.db)
        service = MarketDataService(provider, repository)
        summaries = service.fetch_and_store_many(args.league, args.types)
        _print_fetch_summaries(summaries)
        return

    if args.command == "market-fetch-required":
        recipe_repository = SqliteRecipeRepository(args.db)
        recipes = RecipeImportService(recipe_repository).load_all_recipes()
        requirements = summarize_market_requirements(recipes)
        if not requirements:
            print("No market requirements found. Import recipes first.")
            return
        item_types = [requirement.item_type for requirement in requirements]
        print(f"Required market types: {', '.join(item_types)}")
        summaries = MarketDataService(PoeNinjaProvider(), SqliteMarketRepository(args.db)).fetch_and_store_many(
            args.league,
            item_types,
        )
        _print_fetch_summaries(summaries)
        return

    if args.command == "market-requirements":
        recipe_repository = SqliteRecipeRepository(args.db)
        recipes = RecipeImportService(recipe_repository).load_all_recipes()
        requirements = summarize_market_requirements(recipes)
        if not requirements:
            print("No market requirements found. Import recipes first.")
            return
        print("Required market types from imported recipes:")
        for requirement in requirements:
            print(
                f"- {requirement.item_type}: {requirement.ingredient_count} ingredients "
                f"across {requirement.recipe_count} recipes"
            )
        return

    if args.command == "market-list":
        repository = SqliteMarketRepository(args.db)
        rows = repository.list_latest_prices(
            league=args.league,
            item_type=args.item_type,
            limit=args.limit,
        )
        if not rows:
            print("No market prices stored yet.")
            return
        for row in rows:
            divine = "" if row["divine_value"] is None else f" | {row['divine_value']:.4g} divine"
            listings = "" if row["listing_count"] is None else f" | listings {row['listing_count']}"
            print(
                f"{row['item_type']} | {row['name']} | {row['chaos_value']:.4g} chaos"
                f"{divine}{listings} | snapshot {row['snapshot_id']}"
            )
        return

    if args.command == "price-override-set":
        repository = SqliteMarketRepository(args.db)
        override = ManualPriceOverride(
            game=args.game,
            league=args.league,
            item_type=args.item_type,
            market_name=args.name,
            chaos_value=args.chaos,
            divine_value=args.divine,
            listing_count=args.listings,
            confidence=args.confidence,
            note=args.note,
        )
        repository.save_manual_price_override(override)
        print(
            f"Saved manual override: {args.league}/{args.item_type}/{args.name} = "
            f"{args.chaos:.4g} chaos"
        )
        return

    if args.command == "price-override-list":
        repository = SqliteMarketRepository(args.db)
        rows = repository.list_manual_price_overrides(
            league=args.league,
            item_type=args.item_type,
            limit=args.limit,
            game=args.game,
        )
        if not rows:
            print("No manual price overrides stored yet.")
            return
        for row in rows:
            divine = "" if row["divine_value"] is None else f" | {row['divine_value']:.4g} divine"
            listings = "" if row["listing_count"] is None else f" | listings {row['listing_count']}"
            note = "" if not row["note"] else f" | note: {row['note']}"
            print(
                f"{row['item_type']} | {row['market_name']} | {row['chaos_value']:.4g} chaos"
                f"{divine}{listings} | confidence {row['confidence']}{note}"
            )
        return

    if args.command == "output-price-override-set":
        repository = SqliteRecipeRepository(args.db)
        override = OutputPriceOverride(
            game=args.game,
            league=args.league,
            recipe_id=args.recipe_id,
            estimated_sale_price_chaos=args.sale_chaos,
            failed_resale_value_chaos=args.failed_resale_chaos,
            confidence=args.confidence,
            source=args.source,
            note=args.note,
        )
        repository.save_output_price_override(override)
        print(
            f"Saved output price override: {args.league}/{args.recipe_id} = "
            f"{args.sale_chaos:.4g} chaos"
        )
        return

    if args.command == "output-price-override-list":
        repository = SqliteRecipeRepository(args.db)
        rows = repository.list_output_price_overrides(
            league=args.league,
            game=args.game,
            limit=args.limit,
        )
        if not rows:
            print("No output price overrides stored yet.")
            return
        for row in rows:
            note = "" if not row["note"] else f" | note: {row['note']}"
            print(
                f"{row['recipe_id']} | sale {row['estimated_sale_price_chaos']:.4g} chaos | "
                f"failed resale {row['failed_resale_value_chaos']:.4g} chaos | "
                f"source {row['source']} | confidence {row['confidence']}{note}"
            )
        return

    if args.command == "rank-recipes":
        service = RecipeRankingService(
            recipe_repository=SqliteRecipeRepository(args.db),
            market_repository=SqliteMarketRepository(args.db),
        )
        rows = service.rank_recipes(
            league=args.league,
            max_budget_chaos=args.max_budget_chaos,
            min_profit_chaos=args.min_profit_chaos,
            hide_incomplete=args.hide_incomplete,
            hide_without_output_price=args.hide_without_output_price,
            use_auto_success_assumption=not args.no_auto_success_assumption,
            min_confidence_score=args.min_confidence_score,
        )
        _maybe_export_ranking_csv(rows, args.export_csv)
        _print_ranking_rows(rows, show_problems=args.show_problems, show_cost_drivers=args.show_cost_drivers)
        return

    if args.command == "auto-rank":
        service = AutoAnalysisService(
            recipe_repository=SqliteRecipeRepository(args.db),
            market_repository=SqliteMarketRepository(args.db),
            market_provider=PoeNinjaProvider(),
        )
        result = service.import_refresh_and_rank(
            league=args.league,
            recipe_dir=None if args.skip_import else args.recipe_dir,
            recursive=not args.no_recursive,
            max_budget_chaos=args.max_budget_chaos,
            min_profit_chaos=args.min_profit_chaos,
            hide_incomplete=args.hide_incomplete,
            hide_without_output_price=args.hide_without_output_price,
            use_auto_success_assumption=not args.no_auto_success_assumption,
            min_confidence_score=args.min_confidence_score,
            refresh_market=not args.skip_market_refresh,
        )
        if not args.skip_import:
            print(f"Imported {result.imported_recipe_count} recipes from {args.recipe_dir}.")
        if not args.skip_market_refresh:
            print(f"Refreshed market types: {', '.join(result.refreshed_market_types) or 'none'}")
            _print_fetch_summaries(result.fetch_summaries)
        _maybe_export_ranking_csv(result.ranking_rows, args.export_csv)
        _print_ranking_rows(result.ranking_rows, show_problems=args.show_problems, show_cost_drivers=args.show_cost_drivers)
        return

    if args.command == "analyze-recipe":
        recipe_repository = SqliteRecipeRepository(args.db)
        recipe_service = RecipeImportService(recipe_repository)
        recipe = recipe_service.load_recipe(args.recipe_id)
        if recipe is None:
            print(f"Recipe not found in database: {args.recipe_id}")
            print("Import it first with: python -m poe_market_analyser.cli import <recipe.yaml> --db <db>")
            return

        league = args.league or recipe.default_league
        market_repository = SqliteMarketRepository(args.db)
        resolver = MarketPriceResolver(market_repository)
        resolution = resolver.resolve_recipe_prices(recipe, league=league)

        print(f"Recipe: {recipe.name} ({recipe.id})")
        print(f"League: {league}")
        print("Resolved ingredients:")
        if not resolution.price_book.entries:
            print("- none")
        for entry in resolution.price_book.entries:
            listings = "" if entry.listing_count is None else f", listings {entry.listing_count}"
            divine = "" if entry.unit_price_divine is None else f", {entry.unit_price_divine:.4g} divine/unit"
            confidence = "" if entry.confidence is None else f", confidence {entry.confidence}"
            print(
                f"- {entry.ingredient_id}: {entry.quantity:g} x {entry.matched_name} "
                f"({entry.quantity_mode}) "
                f"[{entry.market_type}/{entry.matched_price_id}; source {entry.price_source}] = "
                f"{entry.total_price_chaos:.4g} chaos "
                f"({entry.unit_price_chaos:.4g} chaos/unit{divine}{listings}{confidence})"
            )
            if entry.note:
                print(f"  note: {entry.note}")
            for warning in entry.warnings:
                print(f"  warning: {warning}")

        print(f"Known one-attempt ingredient cost: {resolution.price_book.total_known_cost_chaos():.4g} chaos")

        if resolution.missing_prices:
            print("Missing prices:")
            for missing in resolution.missing_prices:
                location = ""
                if missing.market_type or missing.market_name:
                    location = f" [{missing.market_type or '?'} / {missing.market_name or '?'}]"
                print(f"- {missing.ingredient_id}{location}: {missing.reason}")

        output_override = recipe_repository.find_output_price_override(
            recipe_id=recipe.id,
            league=league,
            game=recipe.game,
        )
        output_price = resolve_output_price(
            recipe,
            sale_price_override_chaos=args.sale_price_chaos,
            failed_resale_override_chaos=args.failed_resale_chaos,
            stored_override=output_override,
        )
        result = SimpleExpectedValueProfitEngine().calculate(
            recipe=recipe,
            price_book=resolution.price_book,
            estimated_sale_price=output_price.estimated_sale_price_chaos,
            estimated_failed_resale_value=output_price.failed_resale_value_chaos,
            success_assumption_id=args.success_assumption_id,
        )
        if args.success_assumption_id:
            print(
                f"Expected attempts using {args.success_assumption_id}: "
                f"{result.expected_attempts:.4g}"
            )
            print(f"Expected cost to success: {result.expected_cost_to_success:.4g} chaos")
        if output_price.estimated_sale_price_chaos is not None:
            source = "" if output_price.source is None else f" from {output_price.source}"
            confidence = "" if output_price.confidence is None else f" ({output_price.confidence})"
            print(f"Estimated sale price{source}{confidence}: {output_price.estimated_sale_price_chaos:.4g} chaos")
            print(f"Estimated failed resale value: {output_price.failed_resale_value_chaos:.4g} chaos")
            if output_price.note:
                print(f"Output pricing note: {output_price.note}")
            if result.expected_profit is not None:
                print(f"Expected profit: {result.expected_profit:.4g} chaos")
        else:
            print("Estimated sale price: missing. Add pricing.output to the recipe or pass --sale-price-chaos.")
        return

    raise AssertionError(f"Unhandled command: {args.command}")


def _add_ranking_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--league", default="Mirage")
    parser.add_argument("--db", type=Path, default=Path("poe_market.db"))
    parser.add_argument("--max-budget-chaos", type=float, default=None)
    parser.add_argument("--min-profit-chaos", type=float, default=None)
    parser.add_argument("--hide-incomplete", action="store_true")
    parser.add_argument("--hide-without-output-price", action="store_true")
    parser.add_argument(
        "--no-auto-success-assumption",
        action="store_true",
        help="Do not automatically use the recipe success assumption when exactly one is available.",
    )
    parser.add_argument(
        "--min-confidence-score",
        type=int,
        default=None,
        help="Hide recipes with data-quality confidence score below this value. Useful values: 50, 60, 75.",
    )
    parser.add_argument(
        "--show-problems",
        action="store_true",
        help="Print missing price and warning details under each ranking row.",
    )
    parser.add_argument(
        "--show-cost-drivers",
        action="store_true",
        help="Print the top ingredient costs under each ranking row.",
    )
    parser.add_argument(
        "--export-csv",
        type=Path,
        default=None,
        help="Optional path to export the ranking as CSV.",
    )


def _print_fetch_summaries(summaries) -> None:
    if not summaries:
        print("No market snapshots fetched.")
        return
    for summary in summaries:
        print(
            f"Fetched {summary.price_count} prices for {summary.league}/{summary.item_type} "
            f"into snapshot {summary.saved_snapshot_id}."
        )


def _print_ranking_rows(
    rows: tuple[RecipeRankingRow, ...],
    show_problems: bool = False,
    show_cost_drivers: bool = False,
) -> None:
    if not rows:
        print("No recipes matched the ranking filters.")
        return
    print("Recipe ranking: expected profit uses imported recipe output estimates when available")
    for index, row in enumerate(rows, start=1):
        assumption = "" if row.success_assumption_id is None else f" | assumption {row.success_assumption_id}"
        sale = "missing" if row.estimated_sale_price_chaos is None else f"{row.estimated_sale_price_chaos:.4g} chaos"
        profit = "missing" if row.expected_profit_chaos is None else f"{row.expected_profit_chaos:.4g} chaos"
        roi = "missing" if row.roi_percent is None else f"{row.roi_percent:.2f}%"
        source = "" if row.output_price_source is None else f" | output-source {row.output_price_source}"
        confidence = "" if row.output_price_confidence is None else f"/{row.output_price_confidence}"
        print(
            f"{index}. {row.recipe_name} ({row.recipe_id}) | status {row.status} | "
            f"one-attempt {row.known_one_attempt_cost_chaos:.4g} chaos | "
            f"expected-cost {row.expected_cost_to_success_chaos:.4g} chaos | "
            f"sale {sale} | profit {profit} | ROI {roi}"
            f"{assumption}{source}{confidence} | confidence {row.confidence_score}/100 | "
            f"missing {row.missing_price_count} | warnings {row.warning_count}"
        )
        if show_problems:
            for flag in row.quality_flags:
                print(f"  quality: {flag}")
            for detail in row.missing_price_details:
                print(f"  missing: {detail}")
            for detail in row.warning_details:
                print(f"  warning: {detail}")
        if show_cost_drivers:
            for detail in row.cost_driver_details:
                print(f"  cost: {detail}")


def _maybe_export_ranking_csv(rows: tuple[RecipeRankingRow, ...], export_path: Path | None) -> None:
    if export_path is None:
        return
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with export_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "recipe_id",
                "recipe_name",
                "league",
                "status",
                "one_attempt_cost_chaos",
                "expected_cost_to_success_chaos",
                "estimated_sale_price_chaos",
                "expected_profit_chaos",
                "roi_percent",
                "success_assumption_id",
                "output_price_source",
                "output_price_confidence",
                "confidence_score",
                "quality_flags",
                "missing_price_count",
                "warning_count",
                "missing_price_details",
                "warning_details",
                "cost_driver_details",
            ],
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "recipe_id": row.recipe_id,
                    "recipe_name": row.recipe_name,
                    "league": row.league,
                    "status": row.status,
                    "one_attempt_cost_chaos": row.known_one_attempt_cost_chaos,
                    "expected_cost_to_success_chaos": row.expected_cost_to_success_chaos,
                    "estimated_sale_price_chaos": row.estimated_sale_price_chaos,
                    "expected_profit_chaos": row.expected_profit_chaos,
                    "roi_percent": row.roi_percent,
                    "success_assumption_id": row.success_assumption_id,
                    "output_price_source": row.output_price_source,
                    "output_price_confidence": row.output_price_confidence,
                    "confidence_score": row.confidence_score,
                    "quality_flags": " | ".join(row.quality_flags),
                    "missing_price_count": row.missing_price_count,
                    "warning_count": row.warning_count,
                    "missing_price_details": " | ".join(row.missing_price_details),
                    "warning_details": " | ".join(row.warning_details),
                    "cost_driver_details": " | ".join(row.cost_driver_details),
                }
            )
    print(f"Exported ranking CSV: {export_path}")


if __name__ == "__main__":
    main()
