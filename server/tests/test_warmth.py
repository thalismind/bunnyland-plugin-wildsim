from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    HealthComponent,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    spawn_entity,
)
from bunnyland.core.ecs import replace_component
from bunnyland.mechanics.meter import with_value

from bunnyland_wildsim import (
    CampfireComponent,
    WarmthComponent,
    WarmthConsequence,
    room_chill,
)
from bunnyland_wildsim.warmth import lit_campfire_in_room

HOUR = 3600


def _cold_room(world, biome="tundra", indoor=False):
    return spawn_entity(world, [RoomComponent(title="Frozen waste", biome=biome, indoor=indoor)])


def _character(world, room, *, warmth_value=100.0, last_epoch=0, health=100.0):
    character = spawn_entity(
        world,
        [
            IdentityComponent(name="Wren", kind="character"),
            CharacterComponent(),
            HealthComponent(current=health),
        ],
    )
    warmth = WarmthComponent()
    warmth = replace(
        warmth,
        meter=with_value(warmth.meter, warmth_value),
        last_updated_epoch=last_epoch,
    )
    replace_component(character, warmth)
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)
    return character


def _warmth(character):
    return character.get_component(WarmthComponent).meter.value


def _lit_fire(world, room):
    fire = spawn_entity(world, [CampfireComponent(lit=True, fuel=4.0)])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), fire.id)
    return fire


def test_cold_room_drains_warmth():
    actor = WorldActor()
    room = _cold_room(actor.world)
    character = _character(actor.world, room, warmth_value=80.0)

    WarmthConsequence().process(actor.world, HOUR)

    assert _warmth(character) < 80.0


def test_lit_fire_restores_warmth():
    actor = WorldActor()
    room = _cold_room(actor.world)
    character = _character(actor.world, room, warmth_value=50.0)
    _lit_fire(actor.world, room)

    WarmthConsequence().process(actor.world, HOUR)

    assert _warmth(character) > 50.0


def test_sheltered_indoor_room_does_not_drain_warmth():
    actor = WorldActor()
    room = spawn_entity(actor.world, [RoomComponent(title="Cabin", biome="cabin", indoor=True)])
    character = _character(actor.world, room, warmth_value=80.0)

    WarmthConsequence().process(actor.world, HOUR)

    assert _warmth(character) == 80.0


def test_freezing_character_takes_health_damage():
    actor = WorldActor()
    room = _cold_room(actor.world)
    character = _character(actor.world, room, warmth_value=5.0, health=100.0)

    events = WarmthConsequence().process(actor.world, HOUR)

    assert character.get_component(HealthComponent).current < 100.0
    assert any(type(event).__name__ == "FreezingDamageEvent" for event in events)


def test_warm_character_takes_no_freezing_damage():
    actor = WorldActor()
    room = _cold_room(actor.world)
    character = _character(actor.world, room, warmth_value=90.0, health=100.0)

    events = WarmthConsequence().process(actor.world, HOUR)

    assert character.get_component(HealthComponent).current == 100.0
    assert events == []


def test_first_process_without_prior_timestamp_is_a_no_op():
    actor = WorldActor()
    room = _cold_room(actor.world)
    character = spawn_entity(
        actor.world,
        [IdentityComponent(name="Ash", kind="character"), CharacterComponent(), WarmthComponent()],
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), character.id)

    WarmthConsequence().process(actor.world, HOUR)

    assert _warmth(character) == 100.0  # no elapsed time on the first pass


def test_room_chill_and_lit_fire_helpers():
    actor = WorldActor()
    room = _cold_room(actor.world)
    assert room_chill(actor.world, room) > 0.0
    assert not lit_campfire_in_room(actor.world, room)
    _lit_fire(actor.world, room)
    assert room_chill(actor.world, room) < 0.0
    assert lit_campfire_in_room(actor.world, room)


def test_room_chill_of_no_room_is_zero():
    actor = WorldActor()
    assert room_chill(actor.world, None) == 0.0
