import asyncio

from bunnyland.core import WorldActor
from bunnyland.plugins import apply_plugins
from bunnyland.worldgen import CharacterSpec, RoomSpec, WorldProposal, instantiate

from bunnyland_wildsim import ResourceNodeComponent, ScentComponent
from bunnyland_wildsim.plugin import bunnyland_plugins as _plugins


def _world(*, room=None, character=None):
    actor = WorldActor()
    apply_plugins(_plugins(), actor)
    result = asyncio.run(
        instantiate(
            actor,
            WorldProposal(
                seed="seed",
                rooms=[room or RoomSpec(key="room", title="Room")],
                characters=[character] if character else [],
            ),
        )
    )
    return actor, result


def test_predator_and_prey_get_scent_components():
    actor, result = _world(character=CharacterSpec(key="wolf", name="Wolf", room_key="room"))
    assert (
        actor.world.get_entity(result.characters["wolf"]).get_component(ScentComponent).kind
        == "predator"
    )
    actor, result = _world(character=CharacterSpec(key="rabbit", name="Rabbit", room_key="room"))
    assert (
        actor.world.get_entity(result.characters["rabbit"]).get_component(ScentComponent).kind
        == "prey"
    )


def test_plain_character_is_ignored():
    actor, result = _world(character=CharacterSpec(key="smith", name="Smith", room_key="room"))
    assert not actor.world.get_entity(result.characters["smith"]).has_component(ScentComponent)


def test_outdoor_biomes_get_resource_nodes_but_indoor_rooms_do_not():
    actor, result = _world(room=RoomSpec(key="forest", title="Forest", biome="forest"))
    assert (
        actor.world.get_entity(result.rooms["forest"]).get_component(ResourceNodeComponent).resource
        == "berries"
    )
    actor, result = _world(room=RoomSpec(key="tundra", title="Tundra", biome="frozen tundra"))
    assert (
        actor.world.get_entity(result.rooms["tundra"]).get_component(ResourceNodeComponent).resource
        == "lichen"
    )
    actor, result = _world(room=RoomSpec(key="house", title="House", biome="forest", indoor=True))
    assert not actor.world.get_entity(result.rooms["house"]).has_component(ResourceNodeComponent)
