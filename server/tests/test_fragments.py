from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    ExitTo,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    spawn_entity,
)
from bunnyland.core.ecs import replace_component
from bunnyland.mechanics.meter import with_value

from bunnyland_wildsim import (
    CampfireComponent,
    ResourceNodeComponent,
    ScentComponent,
    ScentConsequence,
    TrackerComponent,
    WarmthComponent,
    wildsim_fragments,
)


def _room(world, title="Clearing", biome="forest"):
    return spawn_entity(world, [RoomComponent(title=title, biome=biome)])


def _character(world, room, name="Fen"):
    character = spawn_entity(
        world, [IdentityComponent(name=name, kind="character"), CharacterComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)
    return character


def test_cold_character_reads_a_warmth_line():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    warmth = WarmthComponent()
    replace_component(character, replace(warmth, meter=with_value(warmth.meter, 10.0)))

    lines = wildsim_fragments(actor.world, character)

    assert any("freezing" in line for line in lines)


def test_warm_character_reads_no_warmth_line():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    replace_component(character, WarmthComponent())  # full warmth

    assert wildsim_fragments(actor.world, character) == []


def test_tracker_points_toward_the_strongest_scent():
    actor = WorldActor()
    here = _room(actor.world, "Here")
    east = _room(actor.world, "East")
    here.add_relationship(ExitTo(direction="east"), east.id)
    creature = spawn_entity(
        actor.world,
        [IdentityComponent(name="stag", kind="character"), ScentComponent()],
    )
    east.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), creature.id)
    ScentConsequence().process(actor.world, 0)

    tracker = _character(actor.world, here, "Scout")
    collar = spawn_entity(
        actor.world, [IdentityComponent(name="tracking collar", kind="item"), TrackerComponent()]
    )
    tracker.add_relationship(Contains(mode=ContainmentMode.INVENTORY), collar.id)

    lines = wildsim_fragments(actor.world, tracker)

    assert any("east" in line for line in lines)


def test_tracker_without_a_trail_reports_nothing_nearby():
    actor = WorldActor()
    here = _room(actor.world, "Here")
    tracker = _character(actor.world, here, "Scout")
    replace_component(tracker, TrackerComponent())

    lines = wildsim_fragments(actor.world, tracker)

    assert any("no fresh trail" in line for line in lines)


def test_lit_campfire_and_resource_node_render_in_the_room():
    actor = WorldActor()
    room = _room(actor.world)
    replace_component(room, ResourceNodeComponent(resource="berries"))
    character = _character(actor.world, room)
    fire = spawn_entity(actor.world, [CampfireComponent(lit=True, fuel=3.0)])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), fire.id)

    lines = wildsim_fragments(actor.world, character)

    assert any("campfire crackles" in line for line in lines)
    assert any("berries to forage" in line for line in lines)


def test_scent_trail_in_room_is_described():
    actor = WorldActor()
    room = _room(actor.world)
    character = _character(actor.world, room)
    creature = spawn_entity(
        actor.world, [IdentityComponent(name="hare", kind="character"), ScentComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), creature.id)
    ScentConsequence().process(actor.world, 0)

    lines = wildsim_fragments(actor.world, character)

    assert any("scent trail" in line for line in lines)
