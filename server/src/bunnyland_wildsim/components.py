"""Wilderness-survival components.

Each concept is its own immutable component. Behaviour lives in the per-mechanic modules
(:mod:`scent`, :mod:`warmth`, :mod:`campfire`, :mod:`foraging`); this module only holds the
component value types and the small amount of prompt text that reads directly off a single
component's own state.

Components are frozen; mutate them by swapping whole values with
``replace_component(entity, replace(component, ...))``.
"""

from __future__ import annotations

from bunnyland.mechanics.meter import Meter, band
from bunnyland.prompts.context import ComponentPromptContext
from pydantic.dataclasses import dataclass
from relics import Component

# --------------------------------------------------------------------------------------
# Scent & trails
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ScentComponent(Component):
    """A creature that leaves a scent in whatever room it currently occupies."""

    strength: float = 1.0
    kind: str = "creature"  # e.g. "predator" or "prey"


@dataclass(frozen=True)
class ScentTrailComponent(Component):
    """A decaying scent deposit accumulated on a room by passing creatures."""

    strength: float = 0.0
    last_updated_epoch: int = 0


@dataclass(frozen=True)
class TrackerComponent(Component):
    """Carried tracking gear (a collar, a nose) that reads nearby scent trails."""

    sensitivity: float = 1.0


# --------------------------------------------------------------------------------------
# Cold & warmth
# --------------------------------------------------------------------------------------

#: Warmth is a resource that drains in the cold, so the meter's thresholds read
#: *low-is-bad*: at/under ``crisis_at`` the character is freezing.
WARMTH_METER = Meter(value=100.0, warning_at=60.0, urgent_at=35.0, crisis_at=15.0)

_WARMTH_PHRASES = {
    "chilly": "You are starting to feel the cold.",
    "cold": "You are cold and beginning to shiver.",
    "freezing": "You are freezing; you need warmth soon.",
}


def warmth_band(meter: Meter) -> str:
    """Coarse warmth band (``warm`` > ``chilly`` > ``cold`` > ``freezing``).

    Inverted from :func:`bunnyland.mechanics.meter.band` because low warmth is the danger.
    """
    if meter.value <= meter.crisis_at:
        return "freezing"
    if meter.value <= meter.urgent_at:
        return "cold"
    if meter.value <= meter.warning_at:
        return "chilly"
    return "warm"


@dataclass(frozen=True)
class WarmthComponent(Component):
    """A character's body warmth, drained by cold rooms and restored by fire/shelter."""

    meter: Meter = WARMTH_METER
    drain_rate: float = 6.0  # warmth lost per game hour of full-strength cold
    warm_rate: float = 12.0  # warmth regained per game hour by a fire or shelter
    freeze_damage: float = 5.0  # health lost per game hour while freezing
    last_updated_epoch: int | None = None

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        if not ctx.is_first_person:
            return ()
        phrase = _WARMTH_PHRASES.get(warmth_band(self.meter))
        return (phrase,) if phrase else ()


# --------------------------------------------------------------------------------------
# Campfire
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CampfireComponent(Component):
    """A placeable, lightable campfire that burns fuel down over time.

    While ``lit`` with fuel remaining it raises its room's ``LightComponent`` (by
    ``light_boost``) and supplies warmth to characters in the room.
    """

    lit: bool = False
    fuel: float = 4.0
    burn_rate: float = 1.0  # fuel consumed per game hour while lit
    light_boost: float = 0.8
    last_updated_epoch: int = 0

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        if self.lit and self.fuel > 0.0:
            return ("A campfire crackles here, warm and bright.",)
        return ("A cold campfire sits here, unlit.",)


# --------------------------------------------------------------------------------------
# Foraging
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ResourceNodeComponent(Component):
    """A forageable source seeded into a room or object, yielding an item on a cooldown."""

    resource: str = "berries"
    yield_kind: str = "food"
    cooldown: int = 3600  # game-seconds between successful forages
    remaining: int | None = None  # None = inexhaustible; else uses left
    last_foraged_epoch: int | None = None

    def depleted(self) -> bool:
        return self.remaining is not None and self.remaining <= 0

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        if self.depleted():
            return ()
        return (f"There is {self.resource} to forage here.",)


# Re-export the shared band helper so callers importing from this module get the pattern.
__all__ = [
    "WARMTH_METER",
    "CampfireComponent",
    "ResourceNodeComponent",
    "ScentComponent",
    "ScentTrailComponent",
    "TrackerComponent",
    "WarmthComponent",
    "band",
    "warmth_band",
]
