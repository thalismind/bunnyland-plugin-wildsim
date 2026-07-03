"""Scent trails: creatures deposit a decaying scent in their room; trackers read it.

The :class:`ScentConsequence` runs each tick. In every room a scent-bearing creature
currently occupies it tops up that room's :class:`ScentTrailComponent`; every existing
trail then decays by a fixed factor and is removed once it fades below a threshold. A held
:class:`TrackerComponent` reads the strongest-scented *adjacent* room (via ``ExitTo``) and
renders a direction to follow — see :func:`bunnyland_wildsim.fragments.wildsim_fragments`.
"""

from __future__ import annotations

from bunnyland.core import ExitTo, contents
from bunnyland.core.ecs import replace_component
from bunnyland.core.events import DomainEvent
from relics import Entity, World

from .components import ScentComponent, ScentTrailComponent, TrackerComponent
from .spatial import room_of

#: Fraction of a trail's strength that survives each tick before fresh deposits are added.
DECAY_FACTOR = 0.5

#: Trails weaker than this are removed so faded rooms drop their component.
FADE_THRESHOLD = 0.05

#: Multiplier applied to a creature's scent strength when depositing into its room.
DEPOSIT_RATE = 1.0


class ScentConsequence:
    """Top up scent trails under scent-bearing creatures and decay all trails each tick."""

    def __init__(
        self,
        *,
        decay_factor: float = DECAY_FACTOR,
        fade_threshold: float = FADE_THRESHOLD,
        deposit_rate: float = DEPOSIT_RATE,
    ):
        self.decay_factor = decay_factor
        self.fade_threshold = fade_threshold
        self.deposit_rate = deposit_rate

    def process(self, world: World, epoch: int) -> list[DomainEvent]:
        deposits = self._deposits_by_room(world)
        rooms: dict[str, Entity] = {key: room for key, (room, _s) in deposits.items()}
        for room in world.query().with_all([ScentTrailComponent]).execute_entities():
            rooms.setdefault(str(room.id), room)

        for key, room in rooms.items():
            current = (
                room.get_component(ScentTrailComponent).strength
                if room.has_component(ScentTrailComponent)
                else 0.0
            )
            deposit = deposits.get(key, (None, 0.0))[1] * self.deposit_rate
            new_strength = current * self.decay_factor + deposit
            if new_strength <= self.fade_threshold:
                if room.has_component(ScentTrailComponent):
                    room.remove_component(ScentTrailComponent)
                continue
            replace_component(
                room, ScentTrailComponent(strength=new_strength, last_updated_epoch=epoch)
            )
        return []

    def _deposits_by_room(self, world: World) -> dict[str, tuple[Entity, float]]:
        """Map room id -> (room entity, summed scent strength of creatures within)."""
        rooms: dict[str, tuple[Entity, float]] = {}
        for creature in world.query().with_all([ScentComponent]).execute_entities():
            room = room_of(world, creature.id)
            if room is None:
                continue
            strength = creature.get_component(ScentComponent).strength
            key = str(room.id)
            prev = rooms.get(key, (room, 0.0))[1]
            rooms[key] = (room, prev + strength)
        return rooms


def tracker_carrier(world: World, character: Entity) -> bool:
    """True when the character is, or is carrying, a tracker."""
    if character.has_component(TrackerComponent):
        return True
    for item_id in contents(character):
        if world.has_entity(item_id) and world.get_entity(item_id).has_component(TrackerComponent):
            return True
    return False


def strongest_adjacent_scent(world: World, room: Entity) -> tuple[float, str] | None:
    """Return ``(strength, direction)`` of the strongest-scented adjacent room, or ``None``."""
    best: tuple[float, str] | None = None
    for edge, target_id in room.get_relationships(ExitTo):
        if not world.has_entity(target_id):
            continue
        neighbor = world.get_entity(target_id)
        if not neighbor.has_component(ScentTrailComponent):
            continue
        strength = neighbor.get_component(ScentTrailComponent).strength
        if strength <= 0.0:
            continue
        direction = edge.direction or edge.label or "onward"
        if best is None or strength > best[0]:
            best = (strength, direction)
    return best


__all__ = [
    "DECAY_FACTOR",
    "DEPOSIT_RATE",
    "FADE_THRESHOLD",
    "ScentConsequence",
    "strongest_adjacent_scent",
    "tracker_carrier",
]
