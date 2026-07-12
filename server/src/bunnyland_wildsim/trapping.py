"""Trapping: set a snare and let a passing creature walk into it.

Unlike hunting, trapping is passive: :class:`TrappingConsequence` runs each tick, and once a
set trap has been down long enough (longer in a scarce season) it catches the first eligible
prey sharing its room. The catch is modelled as a **typed structural edge**,
:class:`TrappedIn`, from the trap to the held creature — never a list on the trap — so the
edge index is the single source of truth for what a trap holds. ``check-trap`` then harvests
a sprung trap for game and a hide, freeing it to re-arm.
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    ContainmentMode,
    Contains,
    IdentityComponent,
    contents,
    spawn_entity,
)
from bunnyland.core.actions import ActionArgument, ActionDefinition, ActionEffort, effort_cost
from bunnyland.core.commands import Lane, SubmittedCommand
from bunnyland.core.ecs import container_of, replace_component
from bunnyland.core.events import DomainEvent, EventVisibility, event_base
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    ok,
    rejected,
    require_character,
    require_reachable_entity,
)
from pydantic.dataclasses import dataclass
from relics import Component, Edge, Entity, World

from .components import ScentComponent
from .events import GameBaggedEvent, GameTrappedEvent, TrapSetEvent
from .seasons import season_scarcity
from .spatial import room_of
from .trophies import game_weight, spawn_game_meat, spawn_hide

#: A freshly set trap must be down this long before it can catch (scaled up by scarcity).
DEFAULT_DWELL_SECONDS = 3600

#: Weight used when a caught creature has vanished before harvest (fallback trophy size).
FALLBACK_PREY_WEIGHT = 5.0


@dataclass(frozen=True)
class TrapComponent(Component):
    """A set snare in a room. Once ``sprung`` it holds a creature via a :class:`TrappedIn` edge."""

    set_epoch: int = 0
    dwell_seconds: int = DEFAULT_DWELL_SECONDS
    sprung: bool = False
    caught_species: str = ""


@dataclass(frozen=True)
class TrappedIn(Edge):
    """A trap -> caught-creature structural link (the trap holds that creature)."""

    caught_at_epoch: int = 0


def _eligible_prey(world: World, room: Entity, caught_ids: set[str]) -> Entity | None:
    """The lowest-id free prey creature in ``room`` not already held by a trap."""
    candidates: list[Entity] = []
    for entity_id in contents(room):
        if not world.has_entity(entity_id) or str(entity_id) in caught_ids:
            continue
        entity = world.get_entity(entity_id)
        if not entity.has_component(ScentComponent):
            continue
        if entity.get_component(ScentComponent).kind != "prey":
            continue
        candidates.append(entity)
    candidates.sort(key=lambda e: str(e.id))
    return candidates[0] if candidates else None


class TrappingConsequence:
    """Catch a passing prey creature in each set, ready trap."""

    def process(self, world: World, epoch: int) -> list[DomainEvent]:
        events: list[DomainEvent] = []
        traps = sorted(
            world.query().with_all([TrapComponent]).execute_entities(), key=lambda e: str(e.id)
        )
        caught_ids: set[str] = set()
        for trap_entity in traps:
            for _edge, target_id in trap_entity.get_relationships(TrappedIn):
                caught_ids.add(str(target_id))

        for trap_entity in traps:
            trap = trap_entity.get_component(TrapComponent)
            if trap.sprung:
                continue
            room = room_of(world, trap_entity.id)
            if room is None:
                continue
            dwell = trap.dwell_seconds * (1.0 + season_scarcity(world))
            if epoch - trap.set_epoch < dwell:
                continue
            prey = _eligible_prey(world, room, caught_ids)
            if prey is None:
                continue
            species = (
                prey.get_component(IdentityComponent).name
                if prey.has_component(IdentityComponent)
                else "game"
            )
            trap_entity.add_relationship(TrappedIn(caught_at_epoch=epoch), prey.id)
            replace_component(trap_entity, replace(trap, sprung=True, caught_species=species))
            caught_ids.add(str(prey.id))
            events.append(
                GameTrappedEvent(
                    **event_base(
                        epoch,
                        default_visibility=EventVisibility.ROOM,
                        room_id=str(room.id),
                        actor_id=str(trap_entity.id),
                        target_ids=(str(prey.id),),
                        trap_id=str(trap_entity.id),
                        species=species,
                    )
                )
            )
        return events


class SetTrapHandler:
    """Set a snare in the character's current room."""

    command_type = "set-trap"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, character, error = require_character(ctx, command.character_id)
        if error is not None:
            return error
        room_id = container_of(character)
        if room_id is None or not ctx.world.has_entity(room_id):
            return rejected("you have nowhere to set a trap")
        room = ctx.world.get_entity(room_id)
        trap = spawn_entity(
            ctx.world,
            [
                IdentityComponent(name="snare", kind="item", tags=("wildsim", "trap")),
                TrapComponent(set_epoch=ctx.epoch),
            ],
        )
        room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), trap.id)
        return ok(
            TrapSetEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(room_id),
                    target_ids=(str(trap.id),),
                    trap_id=str(trap.id),
                )
            )
        )


class CheckTrapHandler:
    """Harvest a sprung trap for game and a hide, freeing it to re-arm."""

    command_type = "check-trap"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, character, error = require_character(ctx, command.character_id)
        if error is not None:
            return error
        target_id, trap_entity, error = require_reachable_entity(
            ctx,
            character,
            command.payload.get("trap_id"),
            invalid_reason="invalid trap id",
            missing_reason="trap does not exist",
            unreachable_reason="that trap is not within reach",
        )
        if error is not None:
            return error
        if not trap_entity.has_component(TrapComponent):
            return rejected("that is not a trap")
        trap = trap_entity.get_component(TrapComponent)
        if not trap.sprung:
            return rejected("the trap is empty and still set")

        species, weight = self._harvest_target(ctx, trap_entity, trap)
        meat = spawn_game_meat(ctx.world, species=species, weight=weight)
        hide = spawn_hide(ctx.world, species=species, weight=weight)
        for item in (meat, hide):
            character.add_relationship(Contains(mode=ContainmentMode.INVENTORY), item.id)
        replace_component(
            trap_entity,
            replace(trap, sprung=False, caught_species="", set_epoch=ctx.epoch),
        )
        room = room_of(ctx.world, target_id)
        return ok(
            GameBaggedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(room.id) if room is not None else None,
                    target_ids=(str(meat.id), str(hide.id)),
                    hunter_id=str(character_id),
                    species=species,
                    weight=weight,
                    trophy_id=str(hide.id),
                    game_id=str(meat.id),
                    method="trap",
                )
            )
        )

    def _harvest_target(
        self, ctx: HandlerContext, trap_entity: Entity, trap: TrapComponent
    ) -> tuple[str, float]:
        """Resolve the caught species/weight and remove the held creature if it still lives."""
        for _edge, creature_id in trap_entity.get_relationships(TrappedIn):
            creature = ctx.world.get_entity(creature_id)
            strength = (
                creature.get_component(ScentComponent).strength
                if creature.has_component(ScentComponent)
                else 1.0
            )
            weight = game_weight(strength)
            trap_entity.remove_relationship(TrappedIn, creature_id)
            ctx.world.remove(creature_id)
            return trap.caught_species or "game", weight
        # The creature vanished before harvest; fall back to the recorded species.
        return trap.caught_species or "game", FALLBACK_PREY_WEIGHT


SET_TRAP_DEF = ActionDefinition(
    command_type="set-trap",
    title="Set trap",
    description="Set a snare in your current room to catch passing game.",
    lane=Lane.WORLD,
    cost=effort_cost(action=ActionEffort.ROUTINE),
    arguments={},
)

CHECK_TRAP_DEF = ActionDefinition(
    command_type="check-trap",
    title="Check trap",
    description="Harvest a trap that has caught something.",
    lane=Lane.WORLD,
    cost=effort_cost(action=ActionEffort.ROUTINE),
    arguments={
        "trap_id": ActionArgument(
            title="Trap",
            description="The trap to check.",
            kind="entity",
            required=True,
        ),
    },
)

TRAPPING_ACTION_DEFINITIONS = (SET_TRAP_DEF, CHECK_TRAP_DEF)
TRAPPING_ACTION_HANDLERS = (SetTrapHandler, CheckTrapHandler)


def install_trapping(actor) -> None:
    actor.register_consequence(TrappingConsequence())


__all__ = [
    "CHECK_TRAP_DEF",
    "DEFAULT_DWELL_SECONDS",
    "FALLBACK_PREY_WEIGHT",
    "SET_TRAP_DEF",
    "TRAPPING_ACTION_DEFINITIONS",
    "TRAPPING_ACTION_HANDLERS",
    "CheckTrapHandler",
    "SetTrapHandler",
    "TrapComponent",
    "TrappedIn",
    "TrappingConsequence",
    "install_trapping",
]
