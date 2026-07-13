from __future__ import annotations

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    IdentityComponent,
    LightComponent,
    PortableComponent,
    RoomComponent,
    WorldActor,
    contents,
    spawn_entity,
)
from bunnyland.core.commands import CommandCost, Lane, build_submitted_command
from bunnyland.core.handlers import HandlerContext
from conftest import execute_handler

from bunnyland_wildsim import CampfireComponent, CampfireConsequence
from bunnyland_wildsim.campfire import BuildFireHandler, StokeFireHandler

HOUR = 3600


def _world():
    actor = WorldActor()
    room = spawn_entity(actor.world, [RoomComponent(title="Camp"), LightComponent(level=0.1)])
    holder = spawn_entity(
        actor.world, [IdentityComponent(name="Rue", kind="character"), CharacterComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), holder.id)
    return actor, room, holder


def _cmd(character_id, command_type, payload):
    return build_submitted_command(
        character_id=str(character_id),
        controller_id="ctrl",
        controller_generation=0,
        command_type=command_type,
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload=payload,
    )


def _ctx(actor, epoch=0):
    return HandlerContext(world=actor.world, epoch=epoch)


def _campfire_in(actor, room):
    for item_id in contents(room):
        item = actor.world.get_entity(item_id)
        if item.has_component(CampfireComponent):
            return item
    return None


def test_build_fire_creates_a_lit_campfire():
    actor, room, holder = _world()

    result = execute_handler(BuildFireHandler(), _ctx(actor), _cmd(holder.id, "build-fire", {}))

    assert result.ok
    fire = _campfire_in(actor, room)
    assert fire is not None
    assert fire.get_component(CampfireComponent).lit is True


def test_build_fire_rejects_when_a_fire_already_burns():
    actor, room, holder = _world()
    execute_handler(BuildFireHandler(), _ctx(actor), _cmd(holder.id, "build-fire", {}))

    result = execute_handler(BuildFireHandler(), _ctx(actor), _cmd(holder.id, "build-fire", {}))

    assert not result.ok
    assert result.reason == "there is already a fire burning here"


def test_build_fire_rejects_without_a_room():
    actor = WorldActor()
    loner = spawn_entity(
        actor.world, [IdentityComponent(name="Nomad", kind="character"), CharacterComponent()]
    )

    result = execute_handler(BuildFireHandler(), _ctx(actor), _cmd(loner.id, "build-fire", {}))

    assert not result.ok
    assert result.reason == "you have nowhere to build a fire"


def test_build_fire_rejects_invalid_character():
    actor, _room, _holder = _world()

    result = execute_handler(BuildFireHandler(), _ctx(actor), _cmd("???", "build-fire", {}))

    assert not result.ok
    assert result.reason == "invalid character id"


def test_stoke_fire_adds_fuel():
    actor, room, holder = _world()
    fire = spawn_entity(actor.world, [CampfireComponent(lit=True, fuel=1.0)])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), fire.id)

    result = execute_handler(
        StokeFireHandler(), _ctx(actor), _cmd(holder.id, "stoke-fire", {"item_id": str(fire.id)})
    )

    assert result.ok
    assert fire.get_component(CampfireComponent).fuel > 1.0


def test_stoke_fire_relights_a_dead_fire():
    actor, room, holder = _world()
    fire = spawn_entity(actor.world, [CampfireComponent(lit=False, fuel=0.0)])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), fire.id)

    execute_handler(
        StokeFireHandler(), _ctx(actor), _cmd(holder.id, "stoke-fire", {"item_id": str(fire.id)})
    )

    assert fire.get_component(CampfireComponent).lit is True


def test_stoke_fire_rejects_non_campfire():
    actor, room, holder = _world()
    log = spawn_entity(
        actor.world, [IdentityComponent(name="log", kind="item"), PortableComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), log.id)

    result = execute_handler(
        StokeFireHandler(), _ctx(actor), _cmd(holder.id, "stoke-fire", {"item_id": str(log.id)})
    )

    assert not result.ok
    assert result.reason == "that is not a campfire"


def test_stoke_fire_rejects_unreachable_target():
    actor, _room, holder = _world()
    far_room = spawn_entity(actor.world, [RoomComponent(title="Elsewhere")])
    fire = spawn_entity(actor.world, [CampfireComponent(lit=True, fuel=1.0)])
    far_room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), fire.id)

    result = execute_handler(
        StokeFireHandler(), _ctx(actor), _cmd(holder.id, "stoke-fire", {"item_id": str(fire.id)})
    )

    assert not result.ok
    assert result.reason == "that campfire is not within reach"


def test_lit_fire_raises_room_light_and_restores_it_when_out():
    actor, room, _holder = _world()  # room starts at light 0.1
    fire = spawn_entity(actor.world, [CampfireComponent(lit=True, fuel=1.0, last_updated_epoch=0)])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), fire.id)
    consequence = CampfireConsequence()

    consequence.process(actor.world, 0)
    assert room.get_component(LightComponent).level > 0.1

    # Burn the fuel out; the fire dies and the room returns to its ambient level.
    consequence.process(actor.world, HOUR * 2)
    assert fire.get_component(CampfireComponent).lit is False
    assert room.get_component(LightComponent).level == 0.1


def test_campfire_consequence_burns_fuel_down():
    actor, room, _holder = _world()
    fire = spawn_entity(actor.world, [CampfireComponent(lit=True, fuel=4.0, last_updated_epoch=0)])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), fire.id)

    CampfireConsequence().process(actor.world, HOUR)

    assert fire.get_component(CampfireComponent).fuel < 4.0


def test_fire_burned_out_event_emitted():
    actor, room, _holder = _world()
    fire = spawn_entity(actor.world, [CampfireComponent(lit=True, fuel=0.5, last_updated_epoch=0)])
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), fire.id)

    events = CampfireConsequence().process(actor.world, HOUR)

    assert any(type(event).__name__ == "FireBurnedOutEvent" for event in events)
