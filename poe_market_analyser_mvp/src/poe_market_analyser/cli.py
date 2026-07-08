from __future__ import annotations

import argparse
from pathlib import Path

from poe_market_analyser.application.recipe_service import RecipeImportService
from poe_market_analyser.infrastructure.storage.sqlite_recipe_repository import SqliteRecipeRepository


def main() -> None:
    parser = argparse.ArgumentParser(description="POE Market Analyser MVP CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import", help="Import a YAML crafting recipe.")
    import_parser.add_argument("path", type=Path)
    import_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))

    list_parser = subparsers.add_parser("list", help="List imported recipes.")
    list_parser.add_argument("--db", type=Path, default=Path("poe_market.db"))

    args = parser.parse_args()

    repository = SqliteRecipeRepository(args.db)

    if args.command == "import":
        service = RecipeImportService(repository)
        recipe = service.import_yaml(args.path)
        print(f"Imported recipe: {recipe.id} ({recipe.name})")
        return

    if args.command == "list":
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

    raise AssertionError(f"Unhandled command: {args.command}")


if __name__ == "__main__":
    main()
