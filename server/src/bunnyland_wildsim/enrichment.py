"""World-generation enrichment for the wilderness pack.

Two classifications run off generated entities' semantic text:

- Generated **creatures** whose tags/description read as predators or prey get a
  :class:`ScentComponent` so scent trails and trackers have something to follow.
- Generated **rooms** get a biome-appropriate :class:`ResourceNodeComponent` so foraging
  has something to yield — outdoor rooms only, and only for biomes the pack understands.
"""

from __future__ import annotations

from bunnyland.core.ecs import parse_entity_id, replace_component
from bunnyland.core.events import (
    CharacterGeneratedEvent,
    GeneratedEntityEvent,
    RoomGeneratedEvent,
)
from bunnyland.core.world_actor import WorldActor

from .components import ResourceNodeComponent, ScentComponent
from .predators import ensure_predator_pressure

#: Predator terms → a strong scent that reads as ``predator``.
PREDATOR_TERMS = (
    "wolf",
    "bear",
    "fox",
    "lynx",
    "cougar",
    "lion",
    "tiger",
    "hunter",
    "predator",
    "hound",
    "hyena",
    "jackal",
)

#: Prey/animal terms → a lighter scent that reads as ``prey``.
PREY_TERMS = (
    "rabbit",
    "hare",
    "deer",
    "elk",
    "mouse",
    "vole",
    "boar",
    "goat",
    "sheep",
    "prey",
    "quail",
    "beast",
    "animal",
    "creature",
)

#: Biome substring → (resource name, yield kind). First match wins.
BIOME_RESOURCES: tuple[tuple[str, str, str], ...] = (
    ("forest", "berries", "food"),
    ("wood", "berries", "food"),
    ("jungle", "wild fruit", "food"),
    ("swamp", "cattail roots", "food"),
    ("marsh", "cattail roots", "food"),
    ("plain", "wild herbs", "food"),
    ("grass", "wild herbs", "food"),
    ("meadow", "wild herbs", "food"),
    ("desert", "cactus fruit", "food"),
    ("tundra", "lichen", "food"),
    ("snow", "lichen", "food"),
    ("mountain", "mushrooms", "food"),
    ("coast", "shellfish", "food"),
    ("beach", "shellfish", "food"),
    ("river", "reeds", "food"),
)


def _text(event: GeneratedEntityEvent) -> str:
    generation = event.generation
    return " ".join(
        (
            event.entity_kind,
            generation.description,
            *generation.tags,
            *generation.wants,
            *generation.needs,
        )
    ).casefold()


def _mentions(event: GeneratedEntityEvent, terms: tuple[str, ...]) -> str | None:
    text = _text(event)
    return next((term for term in terms if term in text), None)


def _biome_resource(biome: str) -> tuple[str, str] | None:
    folded = biome.casefold()
    for term, resource, kind in BIOME_RESOURCES:
        if term in folded:
            return resource, kind
    return None


class WildWorldgenHook:
    """Tag generated creatures with scent, seed forage nodes, and arm the predator pressure.

    Seeding the v2 :class:`~bunnyland_wildsim.predators.PredatorPressureComponent` here means
    generated worlds get seasonal predator incursions with no extra setup — the newest
    mechanic ships with the pack's world content.
    """

    def subscribe(self, actor: WorldActor) -> None:
        self._actor = actor
        actor.bus.subscribe(CharacterGeneratedEvent, self._on_character)
        actor.bus.subscribe(RoomGeneratedEvent, self._on_room)

    def _entity(self, entity_id: str):
        parsed = parse_entity_id(entity_id)
        if parsed is None or not self._actor.world.has_entity(parsed):
            return None
        return self._actor.world.get_entity(parsed)

    def _on_character(self, event: CharacterGeneratedEvent) -> None:
        entity = self._entity(event.entity_id)
        if entity is None or entity.has_component(ScentComponent):
            return
        if _mentions(event, PREDATOR_TERMS):
            replace_component(entity, ScentComponent(strength=1.5, kind="predator"))
        elif _mentions(event, PREY_TERMS):
            replace_component(entity, ScentComponent(strength=1.0, kind="prey"))

    def _on_room(self, event: RoomGeneratedEvent) -> None:
        ensure_predator_pressure(self._actor.world)
        entity = self._entity(event.entity_id)
        if entity is None or entity.has_component(ResourceNodeComponent):
            return
        if event.indoor:
            return
        resource = _biome_resource(event.biome)
        if resource is None:
            return
        name, kind = resource
        replace_component(entity, ResourceNodeComponent(resource=name, yield_kind=kind))


__all__ = ["BIOME_RESOURCES", "PREDATOR_TERMS", "PREY_TERMS", "WildWorldgenHook"]
