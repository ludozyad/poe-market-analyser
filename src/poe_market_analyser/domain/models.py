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
class OutputPricingConfig:
    """Recipe-level estimate for the finished item sale price.

    This is intentionally separate from ingredient pricing. It lets imported
    recipe packs carry their own provisional output estimate until exact trade
    search support is added. CLI/manual values can still override it for quick
    experiments.
    """

    mode: str = "manual_estimate"
    estimated_sale_price_chaos: float | None = None
    failed_resale_value_chaos: float = 0.0
    confidence: str = "unknown"
    source: str = "recipe"
    note: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def has_sale_price(self) -> bool:
        return self.estimated_sale_price_chaos is not None


@dataclass(frozen=True)
class PricingConfig:
    base_currency: str
    price_sources: tuple[str, ...] = ()
    output: OutputPricingConfig | None = None


@dataclass(frozen=True)
class Ingredient:
    id: str
    type: str
    price_lookup: bool = True
    quantity: float = 1.0
    quantity_mode: str = "fixed"
    expected_quantity: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def resolved_quantity(self) -> float:
        """Quantity used by the MVP cost engine.

        Recipes can keep both a fixed per-attempt quantity and an expected
        quantity. Expected quantities let imported recipe packs model average
        consumption such as alteration spam, 50/50 dominance attempts, or
        repeated bench crafts without requiring user-side overrides.
        """
        if self.expected_quantity is not None:
            return self.expected_quantity
        return self.quantity

    @property
    def quantity_label(self) -> str:
        if self.expected_quantity is not None:
            return "expected"
        return self.quantity_mode or "fixed"


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
