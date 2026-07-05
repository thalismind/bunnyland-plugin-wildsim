"""Hunting: the headline verb — take a scented creature for meat and a hide.

The ``hunt`` verb targets a reachable creature that carries a :class:`ScentComponent` (the
same trail surface trackers follow). The outcome is deterministic — no randomness — from a
success score that folds in whether the hunter is tracking, the season's scarcity, and an
optional luck bias from the fortune pack. Prey is easy; a cornered predator is dangerous and
can wound the hunter (routed through the core :class:`HealthComponent`), win or lose. On a
kill the quarry is removed and its game meat (which feeds core hunger) and hide drop into the
hunter's pack, and a :class:`GameBaggedEvent` publishes the take.
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    ContainmentMode,
    Contains,
    HealthComponent,
    IdentityComponent,
)
from bunnyland.core.actions import ActionArgument, ActionDefinition
from bunnyland.core.commands import CommandCost, Lane, SubmittedCommand
from bunnyland.core.ecs import replace_component
from bunnyland.core.events import EventVisibility
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    ok,
    rejected,
    require_character,
    require_reachable_entity,
)
from relics import Entity, World

from .components import ScentComponent
from .events import GameBaggedEvent, HuntFoiledEvent
from .luck import luck_bonus
from .scent import tracker_carrier
from .seasons import season_scarcity
from .spatial import room_of
from .trophies import game_weight, spawn_game_meat, spawn_hide

#: Base chance-of-success scores per quarry (deterministic thresholds, not rolls).
PREY_SUCCESS_BASE = 0.85
PREDATOR_SUCCESS_BASE = 0.45

#: A hunt succeeds when its score clears this line.
SUCCESS_THRESHOLD = 0.5

#: Carrying a tracker steadies the shot; scarcity makes game skittish and hard to close on.
TRACKER_BONUS = 0.15
SCARCITY_PENALTY = 0.4

#: Health a cornered predator costs the hunter — a graze on a kill, a mauling on a miss.
PREDATOR_KILL_DAMAGE = 8.0
PREDATOR_FOIL_DAMAGE = 18.0


def hunt_score(world: World, hunter: Entity, scent: ScentComponent) -> float:
    """The deterministic success score for ``hunter`` taking a creature of ``scent``."""
    base = PREDATOR_SUCCESS_BASE if scent.kind == "predator" else PREY_SUCCESS_BASE
    score = base - SCARCITY_PENALTY * season_scarcity(world) + luck_bonus(hunter)
    if tracker_carrier(world, hunter):
        score += TRACKER_BONUS
    return score


def _species(creature: Entity) -> str:
    if creature.has_component(IdentityComponent):
        return creature.get_component(IdentityComponent).name
    return "game"


def _wound(hunter: Entity, damage: float) -> float:
    """Apply hunting damage to the hunter's health; return the resulting health value."""
    if damage <= 0.0 or not hunter.has_component(HealthComponent):
        return hunter.get_component(HealthComponent).current if (
            hunter.has_component(HealthComponent)
        ) else 0.0
    health = hunter.get_component(HealthComponent)
    updated = replace(health, current=health.current - damage)
    replace_component(hunter, updated)
    return updated.current


class HuntHandler:
    """Hunt a reachable scented creature for game and a hide."""

    command_type = "hunt"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, character, error = require_character(ctx, command.character_id)
        if error is not None:
            return error
        target_id, quarry, error = require_reachable_entity(
            ctx,
            character,
            command.payload.get("target_id"),
            invalid_reason="invalid target id",
            missing_reason="target does not exist",
            unreachable_reason="that quarry is not within reach",
        )
        if error is not None:
            return error
        if not quarry.has_component(ScentComponent):
            return rejected("there is nothing here to hunt")

        scent = quarry.get_component(ScentComponent)
        predator = scent.kind == "predator"
        room = room_of(ctx.world, character_id)
        room_id = str(room.id) if room is not None else None

        if hunt_score(ctx.world, character, scent) < SUCCESS_THRESHOLD:
            health = _wound(character, PREDATOR_FOIL_DAMAGE if predator else 0.0)
            return ok(
                HuntFoiledEvent(
                    **ctx.event_base(
                        visibility=EventVisibility.ROOM,
                        actor_id=str(character_id),
                        room_id=room_id,
                        target_ids=(str(target_id),),
                        target_id=str(target_id),
                        damage=PREDATOR_FOIL_DAMAGE if predator else 0.0,
                        health=health,
                    )
                )
            )

        species = _species(quarry)
        weight = game_weight(scent.strength)
        ctx.world.remove(target_id)
        meat = spawn_game_meat(ctx.world, species=species, weight=weight)
        hide = spawn_hide(ctx.world, species=species, weight=weight)
        for item in (meat, hide):
            character.add_relationship(Contains(mode=ContainmentMode.INVENTORY), item.id)
        if predator:
            _wound(character, PREDATOR_KILL_DAMAGE)
        return ok(
            GameBaggedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=room_id,
                    target_ids=(str(meat.id), str(hide.id)),
                    hunter_id=str(character_id),
                    species=species,
                    weight=weight,
                    trophy_id=str(hide.id),
                    game_id=str(meat.id),
                    method="hunt",
                )
            )
        )


HUNT_DEF = ActionDefinition(
    command_type="hunt",
    title="Hunt",
    description="Take a nearby creature for meat and a hide. Predators are dangerous.",
    lane=Lane.WORLD,
    cost=CommandCost(action=1),
    arguments={
        "target_id": ActionArgument(
            title="Quarry",
            description="The creature to hunt.",
            kind="entity",
            required=True,
        ),
    },
)

HUNTING_ACTION_DEFINITIONS = (HUNT_DEF,)
HUNTING_ACTION_HANDLERS = (HuntHandler,)


__all__ = [
    "HUNTING_ACTION_DEFINITIONS",
    "HUNTING_ACTION_HANDLERS",
    "HUNT_DEF",
    "PREDATOR_FOIL_DAMAGE",
    "PREDATOR_KILL_DAMAGE",
    "PREY_SUCCESS_BASE",
    "SUCCESS_THRESHOLD",
    "HuntHandler",
    "hunt_score",
]
