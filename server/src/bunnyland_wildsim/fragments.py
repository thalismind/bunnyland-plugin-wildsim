"""Prompt fragment provider aggregating every wildsim mechanic.

A single ``(world, character) -> list[str]`` provider feeds both the LLM actor context and
the human character-chat prompt. It renders:

- the character's own warmth state (first person),
- a tracker's read on the strongest-scented adjacent room,
- lit/unlit campfires and forageable nodes the character can reach, and
- a lingering scent trail in the current room.
"""

from __future__ import annotations

from bunnyland.core import reachable_ids
from bunnyland.prompts.context import ComponentPromptContext
from relics import Entity, World

from .components import (
    CampfireComponent,
    ResourceNodeComponent,
    ScentTrailComponent,
    WarmthComponent,
)
from .scent import strongest_adjacent_scent, tracker_carrier
from .spatial import room_of


def _tracker_line(world: World, character: Entity) -> str | None:
    if not tracker_carrier(world, character):
        return None
    room = room_of(world, character.id)
    if room is None:
        return None
    best = strongest_adjacent_scent(world, room)
    if best is None:
        return "Your tracker finds no fresh trail nearby."
    return f"Your tracker pulls {best[1]} toward a strong scent."


def wildsim_fragments(world: World, character: Entity) -> list[str]:
    lines: list[str] = []

    if character.has_component(WarmthComponent):
        ctx = ComponentPromptContext.for_entity(world, character)
        lines.extend(character.get_component(WarmthComponent).prompt_fragments(ctx))

    tracker_line = _tracker_line(world, character)
    if tracker_line is not None:
        lines.append(tracker_line)

    for entity_id in reachable_ids(world, character):
        entity = world.get_entity(entity_id)
        if entity.has_component(CampfireComponent) or entity.has_component(ResourceNodeComponent):
            ctx = ComponentPromptContext.for_entity(world, entity)
            if entity.has_component(CampfireComponent):
                lines.extend(entity.get_component(CampfireComponent).prompt_fragments(ctx))
            if entity.has_component(ResourceNodeComponent):
                lines.extend(entity.get_component(ResourceNodeComponent).prompt_fragments(ctx))
        if entity.has_component(ScentTrailComponent):
            lines.append("A lingering scent trail hangs in the air here.")

    return sorted(dict.fromkeys(lines))


__all__ = ["wildsim_fragments"]
