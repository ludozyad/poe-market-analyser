# POE Market Analyser - MVP core

Pierwszy etap implementacji dla projektu desktopowej aplikacji do analizy rynku craftingu w Path of Exile 1.

Zakres tego etapu:

- PoE1 jako pierwszy target projektowy.
- Liga domyslna: Mirage.
- Import receptur craftingu z YAML `schema_version: "0.3"`.
- Model domenowy niezalezny od UI i zrodel danych.
- Walidacja receptury.
- Prosty zapis receptur do SQLite.
- Minimalny profit engine oparty na manualnych cenach.

## Struktura

```text
src/poe_market_analyser/
  domain/                 # dataclasses i walidacja domeny
  infrastructure/
    importers/            # YAML -> model domenowy
    storage/              # SQLite repository
  application/            # use-case'y i profit engine
  cli.py                  # minimalny smoke-test CLI

data/recipes/             # przykladowe receptury YAML
tests/                    # testy MVP core
```

## Uruchomienie testow

```bash
pip install -e .[dev]
pytest
```

## Przykladowe uzycie CLI

```bash
poe-market-analyser import data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml --db poe_market.db
poe-market-analyser list --db poe_market.db
```

## Co dalej

Nastepne etapy:

1. Dodanie `MarketDataProvider` i adaptera `PoeNinjaProvider`.
2. Rozszerzenie modelu skladnikow o ilosci, typ ceny i walute.
3. Dodanie pierwszego ekranu PySide6 do importu i listowania receptur.
4. Rozszerzenie profit engine o checkpointy, salvage i osobne koszty etapow craftingu.
