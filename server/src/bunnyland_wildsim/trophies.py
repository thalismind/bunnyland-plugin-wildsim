"""Published trophy surface: what bagged game and hides *become*.

Wildsim publishes its own open component so other packs can consume it without wildsim
depending on any of them:

- :class:`TrophyComponent` carries a museum-style ``category``/``rarity`` (the donatable
  ``Collectible`` shape) **and** a ``weight`` score (the festival biggest-game
  ``ContestEntry`` shape). A museum or festival pack reads these fields off the item.
- Game meat additionally carries the core :class:`~bunnyland.mechanics.consumables.FoodComponent`,
  so it feeds core hunger through the ordinary ``eat`` verb rather than a private meter.

Both spawn helpers are pure factories: deterministic, no randomness, no time.
"""

from __future__ import annotations

from bunnyland.core import IdentityComponent, PortableComponent, spawn_entity
from bunnyland.mechanics.consumables import FoodComponent
from bunnyland.prompts.context import ComponentPromptContext
from pydantic.dataclasses import dataclass
from relics import Component, Entity, World

from .tanning import HideComponent

#: Nutrition/satiety a portion of fresh game restores through the core ``eat`` verb.
GAME_NUTRITION = 25.0
GAME_SATIETY = 30.0


@dataclass(frozen=True)
class TrophyComponent(Component):
    """An open marker on bagged game or a cured hide — a trophy other packs can claim.

    ``category`` and ``rarity`` mirror the museum collectible shape (a donatable specimen);
    ``species`` and ``weight`` give a festival biggest-game contest a comparable score.
    """

    species: str = "game"
    category: str = "game"  # museum exhibit group ("game" | "trophy")
    rarity: str = "common"  # museum rarity tier
    weight: float = 1.0  # contest score — heavier is bigger game

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        if not ctx.is_first_person:
            return ()
        return (f"A {self.rarity} {self.species} trophy ({self.weight:g} lb) is yours.",)


def game_weight(strength: float) -> float:
    """Map a creature's scent strength to a trophy weight (deterministic)."""
    return round(max(1.0, strength) * 5.0, 1)


def rarity_for(weight: float) -> str:
    """Bucket a trophy weight into a museum rarity tier."""
    if weight >= 8.0:
        return "rare"
    if weight >= 4.0:
        return "uncommon"
    return "common"


def spawn_game_meat(world: World, *, species: str, weight: float) -> Entity:
    """Spawn a portion of fresh game: edible (feeds core hunger) and a donatable trophy."""
    return spawn_entity(
        world,
        [
            IdentityComponent(
                name=f"{species} meat", kind="item", tags=("wildsim", "food", "game")
            ),
            PortableComponent(),
            FoodComponent(nutrition=GAME_NUTRITION, satiety=GAME_SATIETY, raw=True),
            TrophyComponent(
                species=species, category="game", rarity=rarity_for(weight), weight=weight
            ),
        ],
    )


def spawn_hide(world: World, *, species: str, weight: float) -> Entity:
    """Spawn a raw hide: tannable into a pelt, and a donatable trophy in its own right."""
    return spawn_entity(
        world,
        [
            IdentityComponent(name=f"{species} hide", kind="item", tags=("wildsim", "hide")),
            PortableComponent(),
            HideComponent(species=species),
            TrophyComponent(
                species=species, category="trophy", rarity=rarity_for(weight), weight=weight
            ),
        ],
    )


__all__ = [
    "GAME_NUTRITION",
    "GAME_SATIETY",
    "TrophyComponent",
    "game_weight",
    "rarity_for",
    "spawn_game_meat",
    "spawn_hide",
]
