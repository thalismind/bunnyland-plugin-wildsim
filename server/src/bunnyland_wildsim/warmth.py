"""Cold & warmth: characters lose body warmth in cold rooms and regain it by a fire.

:class:`WarmthConsequence` runs each tick. For each character with a
:class:`WarmthComponent` it derives a per-hour *chill* from the room (weather, darkness,
biome, and whether the room is sheltered indoors) — unless a lit campfire is present, in
which case warmth is *restored* instead. Warmth that falls to the freezing band bleeds the
character's :class:`HealthComponent` and emits a :class:`FreezingDamageEvent`.
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import HealthComponent, LightComponent, RoomComponent, contents
from bunnyland.core.components import DeadComponent, SuspendedComponent
from bunnyland.core.ecs import replace_component
from bunnyland.core.events import DomainEvent, EventVisibility, event_base
from bunnyland.mechanics.environment import WeatherComponent
from bunnyland.mechanics.meter import with_value
from relics import Entity, World

from .components import CampfireComponent, WarmthComponent, warmth_band
from .events import FreezingDamageEvent
from .spatial import room_of
from .tanning import total_insulation

SECONDS_PER_HOUR = 3600.0

#: Biome name fragments that make a room cold on their own.
COLD_BIOME_TERMS = (
    "snow",
    "ice",
    "tundra",
    "arctic",
    "glacier",
    "frozen",
    "winter",
    "mountain",
    "alpine",
    "taiga",
)

#: Weather conditions that add chill, and how much (per-hour fraction of drain).
COLD_WEATHER = {"cloudy": 0.2, "overcast": 0.4, "rain": 0.7, "storm": 1.0}

#: Light level under which a room counts as dark/night-cold.
NIGHT_LIGHT_LEVEL = 0.3


def lit_campfire_in_room(world: World, room: Entity) -> bool:
    """True when the room contains at least one lit campfire with fuel remaining."""
    for item_id in contents(room):
        if not world.has_entity(item_id):
            continue
        item = world.get_entity(item_id)
        if item.has_component(CampfireComponent):
            fire = item.get_component(CampfireComponent)
            if fire.lit and fire.fuel > 0.0:
                return True
    return False


def _weather_condition(world: World) -> str:
    for clock in world.query().with_all([WeatherComponent]).execute_entities():
        return clock.get_component(WeatherComponent).condition
    return "clear"


def room_chill(world: World, room: Entity | None) -> float:
    """Per-hour chill pressure for a room.

    Positive drains warmth; negative (a lit fire) restores it. ``1.0`` is a full-strength
    cold exposure that drains at the character's ``drain_rate`` per game hour.
    """
    if room is None:
        return 0.0
    if lit_campfire_in_room(world, room):
        return -1.0  # a fire actively warms the room
    room_comp = room.get_component(RoomComponent) if room.has_component(RoomComponent) else None
    chill = 0.0
    sheltered = room_comp is not None and room_comp.indoor
    if not sheltered:
        chill += 0.4  # base exposure of being outdoors
        chill += COLD_WEATHER.get(_weather_condition(world), 0.0)
        if room.has_component(LightComponent):
            if room.get_component(LightComponent).level < NIGHT_LIGHT_LEVEL:
                chill += 0.4  # night cold
    if room_comp is not None:
        biome = room_comp.biome.casefold()
        if any(term in biome for term in COLD_BIOME_TERMS):
            chill += 0.6
    return chill


class WarmthConsequence:
    """Drain or restore each character's warmth from their room, each tick."""

    def process(self, world: World, epoch: int) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        query = world.query().with_all([WarmthComponent]).with_none(
            [SuspendedComponent, DeadComponent]
        )
        for character in query.execute_entities():
            events.extend(self._update(world, epoch, character))
        return events

    def _update(self, world: World, epoch: int, character: Entity) -> list[DomainEvent]:
        warmth = character.get_component(WarmthComponent)
        last = warmth.last_updated_epoch if warmth.last_updated_epoch is not None else epoch
        hours = max(0.0, (epoch - last) / SECONDS_PER_HOUR)
        room = room_of(world, character.id)
        chill = room_chill(world, room)
        if chill > 0.0:
            # Carried pelts blunt the cold, but can never turn exposure into warming.
            chill = max(0.0, chill - total_insulation(world, character))
        if chill >= 0.0:
            delta = -warmth.drain_rate * chill * hours
        else:
            delta = warmth.warm_rate * (-chill) * hours
        new_meter = with_value(warmth.meter, warmth.meter.value + delta)
        replace_component(
            character, replace(warmth, meter=new_meter, last_updated_epoch=epoch)
        )
        return self._maybe_freeze(world, epoch, character, warmth, new_meter, hours)

    def _maybe_freeze(self, world, epoch, character, warmth, new_meter, hours) -> list[DomainEvent]:
        if warmth_band(new_meter) != "freezing" or hours <= 0.0:
            return []
        if not character.has_component(HealthComponent):
            return []
        health = character.get_component(HealthComponent)
        damage = warmth.freeze_damage * hours
        updated = replace(health, current=health.current - damage)
        replace_component(character, updated)
        room = room_of(world, character.id)
        return [
            FreezingDamageEvent(
                **event_base(
                    epoch,
                    default_visibility=EventVisibility.ROOM,
                    room_id=str(room.id) if room is not None else None,
                    actor_id=str(character.id),
                    target_ids=(str(character.id),),
                    target_id=str(character.id),
                    damage=damage,
                    health=updated.current,
                )
            )
        ]


def install_warmth(actor) -> None:
    actor.register_consequence(WarmthConsequence())


__all__ = [
    "COLD_BIOME_TERMS",
    "COLD_WEATHER",
    "WarmthConsequence",
    "install_warmth",
    "lit_campfire_in_room",
    "room_chill",
]
