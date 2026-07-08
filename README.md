# POE Market Analyser - MVP core

Pierwszy etap implementacji dla projektu desktopowej aplikacji do analizy rynku craftingu w Path of Exile 1.

Zakres aktualnej wersji:

- PoE1 jako pierwszy target projektowy.
- Liga domyslna: Mirage.
- Import receptur craftingu z YAML `schema_version: "0.3"`.
- Model domenowy niezalezny od UI i zrodel danych.
- Walidacja receptury.
- Zapis receptur do SQLite.
- Modul rynku: `MarketDataProvider`, adapter `PoeNinjaProvider`, zapis snapshotow cen do SQLite.
- `MarketPriceResolver`: dopasowanie skladnikow receptury do manualnych override albo najnowszych cen z lokalnego cache.
- Manualne price override dla przypadkow, gdzie poe.ninja jest zbyt ogolne albo ma niska plynnosc.
- Automatyczny wybor najlepszego kandydata cenowego, z preferencja dla dokladnego identyfikatora zamiast podejrzanych wariantow z ta sama nazwa.
- Pierwsza analiza kosztu receptury na podstawie cen pobranych z poe.ninja oraz recznych korekt.
- Importowana wycena outputu (`pricing.output`) jako pierwszy krok do rankingu profitow bez recznej ingerencji.
- Ranking wszystkich zaimportowanych receptur po aktualnym expected profit, gdy receptura zawiera output estimate.
- Obsluga `quantity_mode` i `expected_quantity` w skladnikach receptury, np. alt-spam, dominance 50/50, benchcrafty i beast-lock/imprint.
- Aliasowanie nazw poe.ninja dla walut, np. `Orb of Alteration` moze dopasowac sie do skroconego sluga `alteration`.
- Minimalny profit engine oparty bezposrednio na `PriceBook` z resolvera cen, bez posredniego manualnego price booka.
- CLI do importu pojedynczych receptur i calych katalogow, automatycznego pobierania wymaganych typow rynku, listowania cen, ustawiania manualnych cen, analizy kosztu receptury i rankingu wszystkich receptur.
- Komenda `auto-rank`, ktora w jednym przebiegu importuje recipe pack, odswieza wymagane market typy i tworzy ranking profitow.

- Recipe-level fallback prices for ingredients (`fallback_unit_price_chaos`) so recipe packs can stay self-contained when poe.ninja has no exact match.
- Per-ingredient `prefer_recipe_fallback`, useful for bases where generic poe.ninja `BaseType` data can accidentally match expensive influenced/fractured variants.
- Detailed ranking diagnostics with `--show-problems`, showing missing price and warning details under each recipe.
- Optional CSV export for rankings with `--export-csv`.

## Struktura

```text
src/poe_market_analyser/
  domain/                 # dataclasses i walidacja domeny
    market.py             # neutralny model cen rynkowych i provider protocol
    pricing.py            # price book i wynik resolvowania cen skladnikow
  infrastructure/
    importers/            # YAML -> model domenowy
    market/               # adaptery zrodel rynku, np. poe.ninja
    storage/              # SQLite repositories
  application/            # use-case'y, profit engine, market service, price resolver
  cli.py                  # minimalny smoke-test CLI

data/recipes/             # przykladowe receptury YAML
tests/                    # testy MVP core
```

## Uruchomienie testow

```bash
pip install -e .[dev]
pytest
```

Na Windowsie w PyCharm Terminal:

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

## Przykladowe uzycie CLI

Import receptury albo calego katalogu receptur:

```bash
poe-market-analyser import data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml --db poe_market.db
poe-market-analyser import-dir data/recipes --db poe_market.db
poe-market-analyser list --db poe_market.db
```

Pobranie cen z poe.ninja dla ligi Mirage recznie albo automatycznie na podstawie zaimportowanych receptur:

```bash
poe-market-analyser market-fetch --league Mirage --types Currency Fossil Beast BaseType --db poe_market.db
poe-market-analyser market-requirements --db poe_market.db
poe-market-analyser market-fetch-required --league Mirage --db poe_market.db
```

Wyswietlenie ostatnio zapisanych cen:

```bash
poe-market-analyser market-list --league Mirage --type Fossil --limit 20 --db poe_market.db
```

Analiza kosztu receptury na podstawie lokalnego cache cen:

```bash
poe-market-analyser analyze-recipe poe1_mirage_viper_touch_spiked_gloves --league Mirage --db poe_market.db
```
Manualna korekta ceny, gdy poe.ninja daje zbyt ogolna albo podejrzana cene, np. baza `Spiked Gloves` z bardzo mala liczba listingow:

```bash
poe-market-analyser price-override-set --league Mirage --type BaseType --name "Spiked Gloves" --chaos 25 --confidence checked_trade --note "Manual trade check for clean ilvl 86 Hunter base." --db poe_market.db
poe-market-analyser price-override-list --league Mirage --db poe_market.db
```

Po zapisaniu override `analyze-recipe` uzyje ceny manualnej przed cena z lokalnego cache, zgodnie z kolejnoscia `pricing.price_sources` w YAML.


Analiza expected value z uzyciem zalozenia sukcesu z receptury. Jesli receptura zawiera `pricing.output`, cena sprzedazy zostanie wzieta z YAML bez podawania jej recznie:

```bash
poe-market-analyser analyze-recipe poe1_mirage_viper_touch_spiked_gloves --league Mirage --db poe_market.db --success-assumption-id vaal_success_chance
```

Ranking wszystkich zaimportowanych receptur bez wskazywania konkretnego craftu:

```bash
poe-market-analyser rank-recipes --league Mirage --db poe_market.db
poe-market-analyser rank-recipes --league Mirage --db poe_market.db --show-problems
poe-market-analyser rank-recipes --league Mirage --db poe_market.db --export-csv exports/ranking.csv
```
Workflow docelowy dla MVP: import recipe packa, pobranie wymaganych market typow i ranking w jednym przebiegu:

```bash
poe-market-analyser auto-rank --recipe-dir data/recipes --league Mirage --db poe_market.db
poe-market-analyser auto-rank --recipe-dir data/recipes --league Mirage --db poe_market.db --show-problems --export-csv exports/auto_ranking.csv
```

Gdy receptury sa juz zaimportowane, mozna pominac import i tylko odswiezyc rynek oraz ranking:

```bash
poe-market-analyser auto-rank --skip-import --league Mirage --db poe_market.db
```


Opcjonalnie mozna ograniczyc ranking budzetem, minimalnym profitem albo ukryc receptury z brakujacymi cenami/outputem:

```bash
poe-market-analyser rank-recipes --league Mirage --max-budget-chaos 10000 --min-profit-chaos 1000 --hide-incomplete --hide-without-output-price --db poe_market.db
```

Na Windowsie mozna tez uzywac formy:

```bash
python -m poe_market_analyser.cli import data/recipes/poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml --db poe_market.db
python -m poe_market_analyser.cli market-fetch --league Mirage --types Currency Fossil Beast BaseType --db poe_market.db
python -m poe_market_analyser.cli analyze-recipe poe1_mirage_viper_touch_spiked_gloves --league Mirage --db poe_market.db
```

## Aktualne mapowanie poe.ninja

Adapter uzywa dwoch rodzin endpointow PoE1 economy:

- `exchange/current/overview` dla typow wymienialnych, np. `Currency`, `Fragment`, `Fossil`, `Resonator`, `Essence`, `Scarab`, `Oil`.
- `stash/current/item/overview` dla itemow wycenianych ze stashy, np. `BaseType`, `Beast`, unikatow, map i gemow.

Dzieki temu ta sama komenda `market-fetch` moze pobrac jednoczesnie `Currency Fossil Beast BaseType`, a aplikacja sama wybierze wlasciwa sciezke.

## Uwagi o pierwszej analizie kosztu

Aktualna komenda `analyze-recipe` liczy tylko pierwszy, prosty koszt skladnikow z receptury, ktore maja `price_lookup: true` i metadane `market_type` / `market_name`.

Dla receptury Viper Touch obecnie resolvowane sa m.in.:

- `hunter_spiked_gloves_ilvl86` -> `BaseType` / `Spiked Gloves`
- `gilded_fossil` -> `Fossil` / `Gilded Fossil`
- `orb_of_alteration` -> `Currency` / `Orb of Alteration`, z `expected_quantity`
- `orb_of_dominance` -> `Currency` / `Maven's Orb`, z `expected_quantity`
- `prefixes_cannot_be_changed_divine_cost` -> `Currency` / `Divine Orb`, z `expected_quantity`
- `craicic_chimeral` -> `Beast` / `Craicic Chimeral`, z `expected_quantity`

Cena bazy z poe.ninja `BaseType` nie filtruje jeszcze dokladnie influence ani item level, wiec traktujemy ja jako orientacyjna i oznaczamy note w YAML. Resolver probuje jednak ograniczyc ingerencje uzytkownika: gdy poe.ninja ma kilka pozycji z ta sama nazwa, preferuje dokladny identyfikator ceny (`price_id` / `details_id`) i dopiero potem dopasowanie po samej nazwie. Dzieki temu podejrzane warianty typu droga baza influenced z mala liczba listingow nie powinny automatycznie wygrywac z czysta baza o dokladnym identyfikatorze. Manualne `price-override-set` zostaje jako mechanizm awaryjny, a nie docelowy podstawowy workflow.

## Expected quantities w skladnikach

Receptura moze podac ilosc stala albo oczekiwana:

```yaml
ingredients:
  - id: "orb_of_alteration"
    type: "currency"
    price_lookup: true
    quantity_mode: "expected"
    expected_quantity: 600
    market_name: "Orb of Alteration"
    market_type: "Currency"
```

Importer zapisuje `quantity`, `quantity_mode` i `expected_quantity`, a resolver/profit engine uzywaja `expected_quantity`, jezeli jest podane. Dzieki temu paczka receptur moze zawierac srednie zuzycie currency bez recznego dopisywania cen przez uzytkownika.


## Recipe fallback prices

Recipe pack moze zawierac awaryjna cene skladnika:

```yaml
ingredients:
  - id: "hunter_spiked_gloves_ilvl86"
    type: "base_item"
    market_name: "Spiked Gloves"
    market_type: "BaseType"
    fallback_unit_price_chaos: 25
    fallback_price_confidence: "checked_recipe_fallback"
    prefer_recipe_fallback: true
```

Resolver probuje najpierw manual override, potem - jesli skladnik ma `prefer_recipe_fallback: true` - cene z receptury, a dopiero potem lokalny cache poe.ninja. Dla zwyklych skladnikow fallback jest uzywany dopiero wtedy, gdy manual override i cache nie dadza wyniku. Dzieki temu uzytkownik nie musi recznie poprawiac kazdej brakujacej ceny, ale nadal moze nadpisac cene komenda `price-override-set`.

## Importowana wycena outputu

Receptura moze zawierac sekcje:

```yaml
pricing:
  output:
    mode: "manual_estimate"
    estimated_sale_price_chaos: 350000
    failed_resale_value_chaos: 0
    confidence: "draft_manual"
    source: "recipe_import"
```

Dzieki temu docelowy workflow wymaga mniej ingerencji: aplikacja importuje paczke receptur, pobiera aktualne ceny skladnikow i od razu tworzy ranking expected profit. To nadal nie jest finalny trade search po modach; jest to stabilny kontrakt na czas, zanim dodamy automatyczne wyszukiwanie porownywalnych rare itemow.

## Co dalej

Nastepne etapy:

1. Dodanie checkpointow, salvage i osobnych kosztow etapow craftingu.
2. Dodanie mechanizmu output price provider, ktory docelowo zastapi `manual_estimate` w YAML.
3. Przeliczenie chaos <-> divine jako osobny serwis, gdy pojawia sie wiele walut bazowych.
4. Dodanie pierwszego ekranu PySide6 do importu, listowania receptur i uruchamiania analizy.

## Latest MVP additions

### Research seed recipe pack

The `data/recipes` directory now contains four PoE1/Mirage recipe YAML files:

- `poe1_mirage_viper_touch_spiked_gloves_recipe_cleaned.yaml`
- `poe1_mirage_large_cluster_alt_regal_recipe.yaml`
- `poe1_mirage_fractured_spell_suppression_boots_essence_recipe.yaml`
- `poe1_mirage_amethyst_ring_chaos_res_essence_recipe.yaml`

The three new recipes are draft research seeds. They are useful for testing the hands-off ranking workflow, but their output prices and expected quantities should later be replaced by mod-weight simulation and trade-search pricing.

### Quality score in ranking

`rank-recipes` and `auto-rank` now show a `confidence X/100` value. This is not a profit prediction. It is a data-quality score based on missing prices, warning count, fallback price usage, manual overrides, recipe status and output pricing confidence.

Use:

```powershell
python -m poe_market_analyser.cli auto-rank --recipe-dir data\recipes --league Mirage --db poe_market.db --show-problems
```

The `--show-problems` flag now also prints quality flags such as recipe fallback price count and draft output pricing.

## GitHub handoff and continuation docs

This package includes:

- `GITHUB_SETUP.md` - how to create the GitHub repository and push local code.
- `PROJECT_STATE.md` - current architecture, commands, implemented features and missing elements.
- `CONTINUATION_PROMPT.md` - prompt/context for continuing the project in a new ChatGPT chat.
- `.gitignore` - excludes `.venv`, local SQLite databases, pytest cache and exported reports.

## New ranking filter

You can now hide low-quality draft recipes with:

```powershell
python -m poe_market_analyser.cli auto-rank --skip-import --league Mirage --db poe_market.db --min-confidence-score 70
```

## Expanded draft recipe pack

The recipe pack now contains six recipes. Two new draft research seeds were added:

- `poe1_mirage_eldritch_attack_speed_gloves_essence_recipe.yaml`
- `poe1_mirage_medium_cluster_flask_alt_regal_recipe.yaml`

They are intentionally marked as draft and should be treated as data-pipeline seeds until exact output pricing and mod-weight simulation are implemented.

## Output price overrides and cost drivers

A recipe can still carry a draft `pricing.output` estimate, but the project now also supports stored output price overrides. This lets a user or a future trade-search provider update the finished item price without editing recipe YAML:

    python -m poe_market_analyser.cli output-price-override-set poe1_mirage_fractured_spell_suppression_boots_essence --league Mirage --sale-chaos 1400 --confidence checked_trade_output --note "Checked comparable boots on trade" --db poe_market.db
    python -m poe_market_analyser.cli output-price-override-list --league Mirage --db poe_market.db

Ranking and single-recipe analysis resolve output price in this order:

  1. explicit CLI sale price override,
  2. stored output price override,
  3. imported recipe `pricing.output`,
  4. missing output price.

Ranking can also show the largest cost drivers for each craft:

    python -m poe_market_analyser.cli auto-rank --skip-import --league Mirage --db poe_market.db --show-cost-drivers
    python -m poe_market_analyser.cli auto-rank --skip-import --league Mirage --db poe_market.db --show-problems --show-cost-drivers

This is useful before adding checkpoint-level craft simulation because it quickly shows which ingredients dominate the current expected cost.
