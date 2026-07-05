"""Tanning: cure a raw hide into a pelt that keeps the cold off its carrier.

A hide dropped by hunting or trapping carries a :class:`HideComponent`. The ``tan-hide``
verb converts it in place into a :class:`PeltComponent` item; carrying pelts reduces the
cold pressure the warmth mechanic (:mod:`bunnyland_wildsim.warmth`) applies each tick, so
the trapline feeds directly back into surviving the winter.
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import IdentityComponent, contents
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
from bunnyland.prompts.context import ComponentPromptContext
from pydantic.dataclasses import dataclass
from relics import Component, Entity, World

from .events import HideTannedEvent
from .spatial import room_of

#: Warmth insulation a single cured pelt provides (a fraction of a room's cold pressure).
PELT_INSULATION = 0.5


@dataclass(frozen=True)
class HideComponent(Component):
    """A raw, untanned hide taken from game — the input to :class:`PeltComponent`."""

    species: str = "game"

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        if not ctx.is_first_person:
            return ()
        return (f"You carry a raw {self.species} hide that could be tanned.",)


@dataclass(frozen=True)
class PeltComponent(Component):
    """A cured pelt. While carried, its ``insulation`` blunts the cold for its holder."""

    species: str = "game"
    insulation: float = PELT_INSULATION

    def prompt_fragments(self, ctx: ComponentPromptContext) -> tuple[str, ...]:
        if not ctx.is_first_person:
            return ()
        return (f"A cured {self.species} pelt helps hold the chill off you.",)


def total_insulation(world: World, character: Entity) -> float:
    """Sum the insulation of every pelt the character is carrying (``0.0`` if none)."""
    total = 0.0
    for item_id in sorted(contents(character), key=str):
        if not world.has_entity(item_id):
            continue
        item = world.get_entity(item_id)
        if item.has_component(PeltComponent):
            total += item.get_component(PeltComponent).insulation
    return total


class TanHideHandler:
    """Tan a reachable raw hide, turning it into a warm pelt in place."""

    command_type = "tan-hide"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, character, error = require_character(ctx, command.character_id)
        if error is not None:
            return error
        target_id, hide, error = require_reachable_entity(
            ctx,
            character,
            command.payload.get("hide_id"),
            invalid_reason="invalid hide id",
            missing_reason="hide does not exist",
            unreachable_reason="that hide is not within reach",
        )
        if error is not None:
            return error
        if not hide.has_component(HideComponent):
            return rejected("that is not a hide to tan")

        species = hide.get_component(HideComponent).species
        hide.remove_component(HideComponent)
        pelt = PeltComponent(species=species)
        replace_component(hide, pelt)
        if hide.has_component(IdentityComponent):
            identity = hide.get_component(IdentityComponent)
            replace_component(
                hide, replace(identity, name=f"{species} pelt", tags=(*identity.tags, "pelt"))
            )
        room = room_of(ctx.world, target_id)
        return ok(
            HideTannedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(room.id) if room is not None else None,
                    target_ids=(str(target_id),),
                    hide_id=str(target_id),
                    pelt_id=str(target_id),
                    insulation=pelt.insulation,
                )
            )
        )


TAN_HIDE_DEF = ActionDefinition(
    command_type="tan-hide",
    title="Tan hide",
    description="Cure a raw hide into a pelt that keeps you warm.",
    lane=Lane.WORLD,
    cost=CommandCost(action=1),
    arguments={
        "hide_id": ActionArgument(
            title="Hide",
            description="The raw hide to tan.",
            kind="entity",
            required=True,
        ),
    },
)

TANNING_ACTION_DEFINITIONS = (TAN_HIDE_DEF,)
TANNING_ACTION_HANDLERS = (TanHideHandler,)


__all__ = [
    "PELT_INSULATION",
    "TANNING_ACTION_DEFINITIONS",
    "TANNING_ACTION_HANDLERS",
    "TAN_HIDE_DEF",
    "HideComponent",
    "PeltComponent",
    "TanHideHandler",
    "total_insulation",
]
