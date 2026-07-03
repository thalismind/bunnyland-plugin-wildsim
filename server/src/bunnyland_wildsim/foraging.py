"""Foraging: harvest a resource node for an item, gated by a per-node cooldown.

The ``forage`` verb targets a reachable :class:`ResourceNodeComponent` — most often the
character's current room, which world generation seeds per biome — and, when the node is
neither depleted nor on cooldown, spawns the yielded item into the character's inventory
and stamps the node's cooldown.
"""

from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    ContainmentMode,
    Contains,
    IdentityComponent,
    PortableComponent,
    spawn_entity,
)
from bunnyland.core.actions import ActionArgument, ActionDefinition
from bunnyland.core.commands import CommandCost, Lane, SubmittedCommand
from bunnyland.core.ecs import container_of, replace_component
from bunnyland.core.events import EventVisibility
from bunnyland.core.handlers import (
    HandlerContext,
    HandlerResult,
    ok,
    rejected,
    require_character,
    require_reachable_entity,
)

from .components import ResourceNodeComponent
from .events import ForagedEvent
from .spatial import room_of


class ForageHandler:
    """Forage a reachable resource node (defaults to the current room)."""

    command_type = "forage"

    def execute(self, ctx: HandlerContext, command: SubmittedCommand) -> HandlerResult:
        character_id, character, error = require_character(ctx, command.character_id)
        if error is not None:
            return error

        raw_target = command.payload.get("target_id")
        if raw_target is None:
            room_id = container_of(character)
            if room_id is None or not ctx.world.has_entity(room_id):
                return rejected("there is nothing to forage here")
            target_id, node_entity = room_id, ctx.world.get_entity(room_id)
        else:
            target_id, node_entity, error = require_reachable_entity(
                ctx,
                character,
                raw_target,
                invalid_reason="invalid target id",
                missing_reason="target does not exist",
                unreachable_reason="that is not within reach",
            )
            if error is not None:
                return error

        if not node_entity.has_component(ResourceNodeComponent):
            return rejected("there is nothing to forage there")
        node = node_entity.get_component(ResourceNodeComponent)
        if node.depleted():
            return rejected("this has been picked clean")
        if node.last_foraged_epoch is not None and (
            ctx.epoch - node.last_foraged_epoch < node.cooldown
        ):
            return rejected("there is nothing ready to forage here yet")

        item = spawn_entity(
            ctx.world,
            [
                IdentityComponent(
                    name=node.resource, kind="item", tags=("wildsim", node.yield_kind)
                ),
                PortableComponent(),
            ],
        )
        character.add_relationship(Contains(mode=ContainmentMode.INVENTORY), item.id)
        remaining = node.remaining - 1 if node.remaining is not None else None
        replace_component(
            node_entity, replace(node, last_foraged_epoch=ctx.epoch, remaining=remaining)
        )
        room = room_of(ctx.world, character_id)
        return ok(
            ForagedEvent(
                **ctx.event_base(
                    visibility=EventVisibility.ROOM,
                    actor_id=str(character_id),
                    room_id=str(room.id) if room is not None else None,
                    target_ids=(str(target_id),),
                    node_id=str(target_id),
                    item_id=str(item.id),
                    resource=node.resource,
                )
            )
        )


FORAGE_DEF = ActionDefinition(
    command_type="forage",
    title="Forage",
    description="Gather food or materials from a resource node (defaults to this room).",
    lane=Lane.WORLD,
    cost=CommandCost(action=1),
    arguments={
        "target_id": ActionArgument(
            title="Source",
            description="What to forage; omit to forage your current room.",
            kind="entity",
        ),
    },
)

FORAGE_ACTION_DEFINITIONS = (FORAGE_DEF,)
FORAGE_ACTION_HANDLERS = (ForageHandler,)


__all__ = [
    "FORAGE_ACTION_DEFINITIONS",
    "FORAGE_ACTION_HANDLERS",
    "FORAGE_DEF",
    "ForageHandler",
]
