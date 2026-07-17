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
)
from bunnyland.core.actions import ActionArgument, ActionDefinition, ActionEffort, effort_cost
from bunnyland.core.commands import Lane, SubmittedCommand
from bunnyland.core.ecs import container_of, replace_component
from bunnyland.core.events import DomainEvent, EventVisibility, event_base
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    planned,
    rejected,
    require_character,
    require_reachable_entity,
)
from bunnyland.core.mutations import (
    AddEdge,
    AddEntity,
    DeleteEntity,
    EntityReference,
    MutationPlan,
    RemoveEdge,
    SetComponent,
)
from pydantic.dataclasses import dataclass
from relics import Component, Edge, Entity, World

from .components import ScentComponent
from .events import GameBaggedEvent, GameTrappedEvent, TrapSetEvent
from .seasons import season_scarcity
from .spatial import room_of
from .trophies import game_meat_components, game_weight, hide_components

#: A freshly set trap must be down this long before it can catch (scaled up by scarcity).
DEFAULT_DWELL_SECONDS = 3600

#: Weight used when a caught creature has vanished before harvest (fallback trophy size).
FALLBACK_PREY_WEIGHT = 5.0


@dataclass(frozen=True)
class SnareComponent(Component):
    """A set snare in a room. Once ``sprung`` it holds a creature via a :class:`TrappedIn` edge."""

    set_epoch: int = 0
    dwell_seconds: int = DEFAULT_DWELL_SECONDS
    sprung: bool = False
    caught_species: str = ""


# Keep the original import surface while giving the ECS type a globally unique name.
TrapComponent = SnareComponent


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
        trap = EntityReference()
        return planned(
            MutationPlan(
                (
                    AddEntity(
                        (
                            IdentityComponent(name="snare", kind="item", tags=("wildsim", "trap")),
                            TrapComponent(set_epoch=ctx.epoch),
                        ),
                        reference=trap,
                    ),
                    AddEdge(room.id, trap, Contains(mode=ContainmentMode.ROOM_CONTENT)),
                )
            ),
            lambda: TrapSetEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(room_id),
                    target_ids=(str(trap.require()),),
                    trap_id=str(trap.require()),
                )
            ),
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

        species, weight, creature_id = self._harvest_target(ctx, trap_entity, trap)
        meat = EntityReference()
        hide = EntityReference()
        operations = [
            AddEntity(game_meat_components(species=species, weight=weight), reference=meat),
            AddEntity(hide_components(species=species, weight=weight), reference=hide),
            AddEdge(character.id, meat, Contains(mode=ContainmentMode.INVENTORY)),
            AddEdge(character.id, hide, Contains(mode=ContainmentMode.INVENTORY)),
            SetComponent(
                trap_entity.id,
                replace(trap, sprung=False, caught_species="", set_epoch=ctx.epoch),
            ),
        ]
        if creature_id is not None:
            operations.extend(
                (
                    RemoveEdge(trap_entity.id, creature_id, TrappedIn),
                    DeleteEntity(creature_id),
                )
            )
        room = room_of(ctx.world, target_id)
        return planned(
            MutationPlan(tuple(operations)),
            lambda: GameBaggedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(room.id) if room is not None else None,
                    target_ids=(str(meat.require()), str(hide.require())),
                    hunter_id=str(character_id),
                    species=species,
                    weight=weight,
                    trophy_id=str(hide.require()),
                    game_id=str(meat.require()),
                    method="trap",
                )
            ),
        )

    def _harvest_target(
        self, ctx: HandlerContext, trap_entity: Entity, trap: TrapComponent
    ) -> tuple[str, float, object | None]:
        """Resolve the caught species/weight and the held creature, if it still lives."""
        for _edge, creature_id in trap_entity.get_relationships(TrappedIn):
            creature = ctx.world.get_entity(creature_id)
            strength = (
                creature.get_component(ScentComponent).strength
                if creature.has_component(ScentComponent)
                else 1.0
            )
            weight = game_weight(strength)
            return trap.caught_species or "game", weight, creature_id
        # The creature vanished before harvest; fall back to the recorded species.
        return trap.caught_species or "game", FALLBACK_PREY_WEIGHT, None


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
    "SnareComponent",
    "TrapComponent",
    "TrappedIn",
    "TrappingConsequence",
    "install_trapping",
]
