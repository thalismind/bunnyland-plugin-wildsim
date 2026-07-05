"""Seasonal predator incursions, registered as core storyteller incidents.

When game grows scarce the predators come down hungry too. :class:`PredatorIncursionConsequence`
paces itself like the core storyteller (an interval and a next-due epoch) and, when a lean
season pushes pressure over the line, spawns a predator into an occupied room. Crucially it
does not roll its own private incident type: it stamps the spawned threat with the **core**
:class:`~bunnyland.mechanics.storyteller.IncidentComponent` and links it with the core
:class:`~bunnyland.mechanics.storyteller.IncidentSpawned` edge, so the storyteller's own
auto-resolution closes the incident once the predator is dealt with. The pack registers into
the shared world-pressure budget rather than reinventing one.
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    HealthComponent,
    IdentityComponent,
    RoomComponent,
    WorldClockComponent,
    container_of,
    spawn_entity,
)
from bunnyland.core.components import DeadComponent, SuspendedComponent
from bunnyland.core.ecs import replace_component
from bunnyland.core.events import DomainEvent, EventVisibility, event_base
from bunnyland.mechanics.storyteller import IncidentComponent, IncidentSpawned
from pydantic.dataclasses import dataclass
from relics import Component, Entity, World

from .components import ScentComponent
from .events import PredatorIncursionEvent
from .seasons import current_season, season_scarcity

SECONDS_PER_DAY = 24 * 60 * 60

#: Predators that answer a lean season, in a stable order (chosen deterministically by epoch).
PREDATOR_NAMES: tuple[str, ...] = ("brown bear", "gray wolf", "lynx")

#: Pressure needed before an incursion actually arrives (base + seasonal scarcity).
INCURSION_THRESHOLD = 0.5

#: A wilderness predator's scent and toughness.
PREDATOR_SCENT_STRENGTH = 1.5
PREDATOR_HEALTH = 30.0


@dataclass(frozen=True)
class PredatorPressureComponent(Component):
    """World-level pacing/policy for predator incursions (rests on the world clock).

    ``enabled`` gates the whole mechanic; ``base_pressure`` is the standing danger that the
    season's scarcity is added to; ``next_incursion_epoch`` is the next time an incursion is
    evaluated.
    """

    enabled: bool = True
    interval_seconds: int = SECONDS_PER_DAY
    next_incursion_epoch: int = SECONDS_PER_DAY
    base_pressure: float = 0.4


def ensure_predator_pressure(world: World) -> Entity | None:
    """Seed a :class:`PredatorPressureComponent` onto the world clock if none exists yet.

    Idempotent: called from both install and worldgen so a world only ever holds one.
    """
    existing = list(world.query().with_all([PredatorPressureComponent]).execute_entities())
    if existing:
        return existing[0]
    clocks = sorted(
        world.query().with_all([WorldClockComponent]).execute_entities(), key=lambda e: str(e.id)
    )
    if not clocks:
        return None
    clock = clocks[0]
    replace_component(clock, PredatorPressureComponent())
    return clock


def _target_room(world: World) -> Entity | None:
    """The room of the lowest-id living, non-predator character; else the first room."""
    characters = sorted(
        world.query().with_all([CharacterComponent]).execute_entities(), key=lambda e: str(e.id)
    )
    for character in characters:
        if character.has_component(DeadComponent) or character.has_component(SuspendedComponent):
            continue
        if character.has_component(ScentComponent):
            continue  # skip wild creatures (including earlier predators)
        room_id = container_of(character)
        if room_id is not None and world.has_entity(room_id):
            return world.get_entity(room_id)
    rooms = sorted(
        world.query().with_all([RoomComponent]).execute_entities(), key=lambda e: str(e.id)
    )
    return rooms[0] if rooms else None


class PredatorIncursionConsequence:
    """Pace and spawn seasonal predator incursions as core storyteller incidents."""

    def process(self, world: World, epoch: int) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        markers = sorted(
            world.query().with_all([PredatorPressureComponent]).execute_entities(),
            key=lambda e: str(e.id),
        )
        for marker_entity in markers:
            marker = marker_entity.get_component(PredatorPressureComponent)
            if not marker.enabled or epoch < marker.next_incursion_epoch:
                continue
            replace_component(
                marker_entity,
                replace(marker, next_incursion_epoch=epoch + marker.interval_seconds),
            )
            pressure = marker.base_pressure + season_scarcity(world)
            if pressure < INCURSION_THRESHOLD:
                continue
            event = self._spawn_incursion(world, epoch, pressure)
            if event is not None:
                events.append(event)
        return events

    def _spawn_incursion(self, world: World, epoch: int, pressure: float):
        room = _target_room(world)
        if room is None:
            return None
        name = PREDATOR_NAMES[(epoch // SECONDS_PER_DAY) % len(PREDATOR_NAMES)]
        predator = spawn_entity(
            world,
            [
                IdentityComponent(name=name, kind="character", tags=("wildsim", "predator")),
                CharacterComponent(species="predator"),
                HealthComponent(current=PREDATOR_HEALTH, maximum=PREDATOR_HEALTH),
                ScentComponent(strength=PREDATOR_SCENT_STRENGTH, kind="predator"),
            ],
        )
        room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), predator.id)
        incident = spawn_entity(
            world,
            [
                IdentityComponent(name="predator incursion", kind="incident"),
                IncidentComponent(
                    kind="predator_incursion",
                    budget_spent=pressure,
                    started_at_epoch=epoch,
                    room_id=str(room.id),
                ),
            ],
        )
        incident.add_relationship(IncidentSpawned(kind="monster"), predator.id)
        room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), incident.id)
        return PredatorIncursionEvent(
            **event_base(
                epoch,
                default_visibility=EventVisibility.ROOM,
                actor_id=str(incident.id),
                room_id=str(room.id),
                target_ids=(str(predator.id),),
                incident_id=str(incident.id),
                predator_id=str(predator.id),
                season=current_season(world) or "unknown",
            )
        )


def install_predators(actor) -> None:
    actor.register_consequence(PredatorIncursionConsequence())
    ensure_predator_pressure(actor.world)


__all__ = [
    "INCURSION_THRESHOLD",
    "PREDATOR_HEALTH",
    "PREDATOR_NAMES",
    "PREDATOR_SCENT_STRENGTH",
    "SECONDS_PER_DAY",
    "PredatorIncursionConsequence",
    "PredatorPressureComponent",
    "ensure_predator_pressure",
    "install_predators",
]
