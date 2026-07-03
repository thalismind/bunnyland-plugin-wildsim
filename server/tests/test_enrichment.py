from __future__ import annotations

import asyncio

from bunnyland.core import (
    CharacterComponent,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    spawn_entity,
)
from bunnyland.core.components import GenerationIntentComponent
from bunnyland.core.events import CharacterGeneratedEvent, RoomGeneratedEvent, event_base
from bunnyland.plugins import apply_plugins, load_modules

from bunnyland_wildsim import ResourceNodeComponent, ScentComponent


def _actor():
    actor = WorldActor()
    apply_plugins(load_modules(["bunnyland_wildsim"]), actor)
    return actor


def _publish(actor, event):
    asyncio.run(actor.bus.publish(event))


def _character(actor, *, tags=(), description=""):
    entity = spawn_entity(
        actor.world, [IdentityComponent(name="beast", kind="character"), CharacterComponent()]
    )
    _publish(
        actor,
        CharacterGeneratedEvent(
            **event_base(0),
            seed="seed",
            entity_id=str(entity.id),
            entity_key="beast",
            entity_kind="character",
            generation=GenerationIntentComponent(tags=tuple(tags), description=description),
            character_key="beast",
            room_id="room_1",
        ),
    )
    return entity


def _room(actor, *, biome="forest", indoor=False):
    entity = spawn_entity(actor.world, [RoomComponent(title="Wilds", biome=biome, indoor=indoor)])
    _publish(
        actor,
        RoomGeneratedEvent(
            **event_base(0),
            seed="seed",
            entity_id=str(entity.id),
            entity_key="wilds",
            entity_kind="room",
            generation=GenerationIntentComponent(),
            room_key="wilds",
            biome=biome,
            indoor=indoor,
        ),
    )
    return entity


def test_predator_gets_a_strong_scent():
    actor = _actor()
    wolf = _character(actor, tags=("wolf", "hostile"))
    scent = wolf.get_component(ScentComponent)
    assert scent.kind == "predator"
    assert scent.strength >= 1.5


def test_prey_gets_a_scent_from_description():
    actor = _actor()
    rabbit = _character(actor, description="a nervous wild rabbit")
    assert rabbit.get_component(ScentComponent).kind == "prey"


def test_plain_character_is_not_scented():
    actor = _actor()
    villager = _character(actor, tags=("baker",), description="a cheerful townsperson")
    assert not villager.has_component(ScentComponent)


def test_outdoor_biome_room_gets_a_resource_node():
    actor = _actor()
    room = _room(actor, biome="forest")
    node = room.get_component(ResourceNodeComponent)
    assert node.resource == "berries"


def test_tundra_room_yields_lichen():
    actor = _actor()
    room = _room(actor, biome="frozen tundra")
    assert room.get_component(ResourceNodeComponent).resource == "lichen"


def test_indoor_room_gets_no_resource_node():
    actor = _actor()
    room = _room(actor, biome="forest", indoor=True)
    assert not room.has_component(ResourceNodeComponent)


def test_unknown_biome_gets_no_resource_node():
    actor = _actor()
    room = _room(actor, biome="obsidian void")
    assert not room.has_component(ResourceNodeComponent)
