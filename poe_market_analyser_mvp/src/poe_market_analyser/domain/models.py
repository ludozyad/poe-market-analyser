from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SUPPORTED_SCHEMA_VERSION = "0.3"


@dataclass(frozen=True)
class LeagueScope:
    default_league: str
    compatible_with_other_leagues: bool = False


@dataclass(frozen=True)
class RecipeInfo:
    id: str
    name: str
    game: str
    league_scope: LeagueScope
    status: str = "draft"


@dataclass(frozen=True)
class TargetBase:
    item_class: str
    base_type: str
    item_level_min: int | None = None
    influences: tuple[str, ...] = ()
    corrupted: bool = False


@dataclass(frozen=True)
class TextMod:
    id: str
    text: str
    stat_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AnyOfAffixGroup:
    group_id: str
    min_required: int
    options: tuple[TextMod, ...]


@dataclass(frozen=True)
class TargetItem:
    base: TargetBase
    required_implicits: tuple[TextMod, ...] = ()
    required_affixes: tuple[TextMod, ...] = ()
    any_of_affix_groups: tuple[AnyOfAffixGroup, ...] = ()


@dataclass(frozen=True)
class PricingConfig:
    base_currency: str
    price_sources: tuple[str, ...] = ()


@dataclass(frozen=True)
class Ingredient:
    id: str
    type: str
    price_lookup: bool = True
    quantity: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CraftingCheckpoint:
    id: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CraftingStep:
    id: str
    type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CraftingFlow:
    checkpoints: tuple[CraftingCheckpoint, ...] = ()
    steps: tuple[CraftingStep, ...] = ()


@dataclass(frozen=True)
class Assumption:
    id: str
    value: float
    text: str | None = None
    confidence: str = "unknown"
    source: str = "manual"
    can_override: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulationConfig:
    mode: str = "expected_value"
    include_failed_vaal_resale: bool = False
    default_monte_carlo_attempts: int = 10000
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CraftingRecipe:
    schema_version: str
    recipe: RecipeInfo
    target: TargetItem
    pricing: PricingConfig
    ingredients: tuple[Ingredient, ...]
    crafting_flow: CraftingFlow
    assumptions: tuple[Assumption, ...] = ()
    simulation: SimulationConfig = field(default_factory=SimulationConfig)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.recipe.id

    @property
    def name(self) -> str:
        return self.recipe.name

    @property
    def game(self) -> str:
        return self.recipe.game

    @property
    def default_league(self) -> str:
        return self.recipe.league_scope.default_league

    def assumption_by_id(self, assumption_id: str) -> Assumption | None:
        for assumption in self.assumptions:
            if assumption.id == assumption_id:
                return assumption
        return None
