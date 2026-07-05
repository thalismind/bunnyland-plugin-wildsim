"""Prompt fragment provider aggregating every wildsim mechanic.

A single ``(world, character) -> list[str]`` provider feeds both the LLM actor context and
the human character-chat prompt. It renders:

- the character's own warmth state (first person),
- a tracker's read on the strongest-scented adjacent room,
- lit/unlit campfires, forageable nodes, and set traps the character can reach,
- a lingering scent trail in the current room,
- carried pelts/hides/trophies from hunting and trapping, and
- how lean the current season's hunting is.
"""

from __future__ import annotations

from bunnyland.core import contents, reachable_ids
from bunnyland.prompts.context import ComponentPromptContext
from relics import Entity, World

from .components import (
    CampfireComponent,
    ResourceNodeComponent,
    ScentTrailComponent,
    WarmthComponent,
)
from .scent import strongest_adjacent_scent, tracker_carrier
from .seasons import scarcity_fragment
from .spatial import room_of
from .tanning import HideComponent, PeltComponent
from .trapping import TrapComponent
from .trophies import TrophyComponent


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


def _trap_line(entity: Entity) -> str:
    trap = entity.get_component(TrapComponent)
    if trap.sprung:
        return f"A set trap here has caught {trap.caught_species or 'something'}."
    return "A set trap waits here, ready to spring."


def _carried_lines(world: World, character: Entity) -> list[str]:
    lines: list[str] = []
    for item_id in sorted(contents(character), key=str):
        if not world.has_entity(item_id):
            continue
        item = world.get_entity(item_id)
        if item.has_component(PeltComponent):
            species = item.get_component(PeltComponent).species
            lines.append(f"A cured {species} pelt in your pack helps hold the chill off.")
        elif item.has_component(HideComponent):
            species = item.get_component(HideComponent).species
            lines.append(f"You carry a raw {species} hide that could be tanned.")
        elif item.has_component(TrophyComponent):
            trophy = item.get_component(TrophyComponent)
            lines.append(f"You carry a {trophy.rarity} {trophy.species} trophy.")
    return lines


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
        if entity.has_component(TrapComponent):
            lines.append(_trap_line(entity))
        if entity.has_component(ScentTrailComponent):
            lines.append("A lingering scent trail hangs in the air here.")

    lines.extend(_carried_lines(world, character))

    scarcity = scarcity_fragment(world)
    if scarcity is not None:
        lines.append(scarcity)

    return sorted(dict.fromkeys(lines))


__all__ = ["wildsim_fragments"]
