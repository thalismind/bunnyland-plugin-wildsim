"""Campfires: a lightable, fuel-burning light+warmth source, plus its build/stoke verbs.

:class:`CampfireConsequence` burns each lit fire's fuel down over time and, while a fire is
lit, raises its room's :class:`LightComponent` by the fire's ``light_boost`` (restoring the
room to its ambient level once the fire dies). The warmth side is read by
:mod:`bunnyland_wildsim.warmth`, which checks for a lit fire in the room.

Two verbs act in the character's current room:

- ``build-fire`` spawns and lights a fresh campfire in the room.
- ``stoke-fire`` feeds fuel to a reachable campfire (relighting a fire that had gone out).
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    ContainmentMode,
    Contains,
    IdentityComponent,
    LightComponent,
    contents,
    spawn_entity,
)
from bunnyland.core.actions import ActionArgument, ActionDefinition
from bunnyland.core.commands import CommandCost, Lane, SubmittedCommand
from bunnyland.core.ecs import container_of, parse_entity_id, replace_component
from bunnyland.core.events import DomainEvent, EventVisibility, event_base
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    ok,
    rejected,
    require_character,
    require_reachable_entity,
)
from relics import Entity, World

from .components import CampfireComponent
from .events import FireBuiltEvent, FireBurnedOutEvent, FireStokedEvent
from .spatial import room_of

SECONDS_PER_HOUR = 3600.0

#: Fuel a freshly built fire starts with, and the maximum a fire can be stoked to.
BUILD_FUEL = 4.0
STOKE_FUEL = 3.0
MAX_FUEL = 12.0


class CampfireConsequence:
    """Burn lit fires down and keep each room's light in step with its fires."""

    def __init__(self):
        # Room id -> the light boost this consequence is currently adding to that room.
        self._boosted: dict[str, float] = {}

    def process(self, world: World, epoch: int) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        boost_by_room: dict[str, float] = {}
        for fire_entity in list(world.query().with_all([CampfireComponent]).execute_entities()):
            fire = fire_entity.get_component(CampfireComponent)
            if fire.lit:
                fire = self._burn(fire_entity, fire, epoch, events)
            room = room_of(world, fire_entity.id)
            if fire.lit and fire.fuel > 0.0 and room is not None:
                key = str(room.id)
                boost_by_room[key] = max(boost_by_room.get(key, 0.0), fire.light_boost)
        self._apply_light(world, boost_by_room)
        return events

    def _burn(
        self, entity: Entity, fire: CampfireComponent, epoch: int, events: list
    ) -> CampfireComponent:
        hours = max(0.0, (epoch - fire.last_updated_epoch) / SECONDS_PER_HOUR)
        fuel = fire.fuel - fire.burn_rate * hours
        if fuel <= 0.0:
            updated = replace(fire, lit=False, fuel=0.0, last_updated_epoch=epoch)
            replace_component(entity, updated)
            events.append(
                FireBurnedOutEvent(
                    **event_base(
                        epoch,
                        default_visibility=EventVisibility.ROOM,
                        target_ids=(str(entity.id),),
                        item_id=str(entity.id),
                    )
                )
            )
            return updated
        updated = replace(fire, fuel=fuel, last_updated_epoch=epoch)
        replace_component(entity, updated)
        return updated

    def _apply_light(self, world: World, boost_by_room: dict[str, float]) -> None:
        for key in set(self._boosted) | set(boost_by_room):
            parsed = parse_entity_id(key)
            if parsed is None or not world.has_entity(parsed):
                self._boosted.pop(key, None)
                continue
            room = world.get_entity(parsed)
            if not room.has_component(LightComponent):
                self._boosted.pop(key, None)
                continue
            owned = self._boosted.get(key, 0.0)
            desired = boost_by_room.get(key, 0.0)
            if desired == owned:
                continue
            light = room.get_component(LightComponent)
            new_level = round(max(0.0, light.level - owned + desired), 4)
            replace_component(room, replace(light, level=new_level))
            if desired > 0.0:
                self._boosted[key] = desired
            else:
                self._boosted.pop(key, None)


class BuildFireHandler:
    """Build and light a campfire in the character's current room."""

    command_type = "build-fire"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, character, error = require_character(ctx, command.character_id)
        if error is not None:
            return error
        room_id = container_of(character)
        if room_id is None or not ctx.world.has_entity(room_id):
            return rejected("you have nowhere to build a fire")
        room = ctx.world.get_entity(room_id)
        for item_id in contents(room):
            item = ctx.world.get_entity(item_id)
            if item.has_component(CampfireComponent):
                fire = item.get_component(CampfireComponent)
                if fire.lit and fire.fuel > 0.0:
                    return rejected("there is already a fire burning here")
        fire_item = spawn_entity(
            ctx.world,
            [
                IdentityComponent(name="campfire", kind="item", tags=("wildsim",)),
                CampfireComponent(lit=True, fuel=BUILD_FUEL, last_updated_epoch=ctx.epoch),
            ],
        )
        room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), fire_item.id)
        return ok(
            FireBuiltEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(room_id),
                    target_ids=(str(fire_item.id),),
                    item_id=str(fire_item.id),
                    fuel=BUILD_FUEL,
                )
            )
        )


class StokeFireHandler:
    """Feed fuel to a reachable campfire, relighting it if it had gone out."""

    command_type = "stoke-fire"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, character, error = require_character(ctx, command.character_id)
        if error is not None:
            return error
        target_id, item, error = require_reachable_entity(
            ctx,
            character,
            command.payload.get("item_id"),
            invalid_reason="invalid item id",
            missing_reason="item does not exist",
            unreachable_reason="that campfire is not within reach",
        )
        if error is not None:
            return error
        if not item.has_component(CampfireComponent):
            return rejected("that is not a campfire")
        fire = item.get_component(CampfireComponent)
        new_fuel = min(MAX_FUEL, fire.fuel + STOKE_FUEL)
        replace_component(
            item, replace(fire, lit=True, fuel=new_fuel, last_updated_epoch=ctx.epoch)
        )
        room = room_of(ctx.world, item.id)
        return ok(
            FireStokedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(room.id) if room is not None else None,
                    target_ids=(str(target_id),),
                    item_id=str(target_id),
                    fuel=new_fuel,
                )
            )
        )


BUILD_FIRE_DEF = ActionDefinition(
    command_type="build-fire",
    title="Build fire",
    description="Build and light a campfire in your current room.",
    lane=Lane.WORLD,
    cost=CommandCost(action=1),
    arguments={},
)

STOKE_FIRE_DEF = ActionDefinition(
    command_type="stoke-fire",
    title="Stoke fire",
    description="Feed fuel to a nearby campfire, relighting it if it went out.",
    lane=Lane.WORLD,
    cost=CommandCost(action=1),
    arguments={
        "item_id": ActionArgument(
            title="Campfire",
            description="The campfire to stoke.",
            kind="entity",
            required=True,
        ),
    },
)

CAMPFIRE_ACTION_DEFINITIONS = (BUILD_FIRE_DEF, STOKE_FIRE_DEF)
CAMPFIRE_ACTION_HANDLERS = (BuildFireHandler, StokeFireHandler)


def install_campfire(actor) -> None:
    actor.register_consequence(CampfireConsequence())


__all__ = [
    "BUILD_FIRE_DEF",
    "BUILD_FUEL",
    "CAMPFIRE_ACTION_DEFINITIONS",
    "CAMPFIRE_ACTION_HANDLERS",
    "MAX_FUEL",
    "STOKE_FIRE_DEF",
    "STOKE_FUEL",
    "BuildFireHandler",
    "CampfireConsequence",
    "StokeFireHandler",
    "install_campfire",
]
