from __future__ import annotations

from dataclasses import replace

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    contents,
    spawn_entity,
)
from bunnyland.core.commands import CommandCost, Lane, build_submitted_command
from bunnyland.core.handlers import HandlerContext
from conftest import execute_handler

from bunnyland_wildsim import ForageHandler, ResourceNodeComponent


def _world(*, resource="berries", cooldown=3600, remaining=None):
    actor = WorldActor()
    room = spawn_entity(
        actor.world,
        [
            RoomComponent(title="Thicket", biome="forest"),
            ResourceNodeComponent(resource=resource, cooldown=cooldown, remaining=remaining),
        ],
    )
    forager = spawn_entity(
        actor.world, [IdentityComponent(name="Bram", kind="character"), CharacterComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), forager.id)
    return actor, room, forager


def _cmd(character_id, payload):
    return build_submitted_command(
        character_id=str(character_id),
        controller_id="ctrl",
        controller_generation=0,
        command_type="forage",
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload=payload,
    )


def _ctx(actor, epoch=0):
    return HandlerContext(world=actor.world, epoch=epoch)


def _inventory_names(actor, character):
    return [
        actor.world.get_entity(item_id).get_component(IdentityComponent).name
        for item_id in contents(character)
    ]


def test_forage_current_room_yields_the_resource_item():
    actor, _room, forager = _world(resource="berries")

    result = execute_handler(ForageHandler(), _ctx(actor), _cmd(forager.id, {}))

    assert result.ok
    assert "berries" in _inventory_names(actor, forager)


def test_forage_stamps_cooldown_and_rejects_immediate_repeat():
    actor, _room, forager = _world(cooldown=3600)

    execute_handler(ForageHandler(), _ctx(actor, epoch=0), _cmd(forager.id, {}))
    result = execute_handler(ForageHandler(), _ctx(actor, epoch=100), _cmd(forager.id, {}))

    assert not result.ok
    assert result.reason == "there is nothing ready to forage here yet"


def test_forage_allowed_again_after_cooldown_elapses():
    actor, _room, forager = _world(cooldown=3600)

    execute_handler(ForageHandler(), _ctx(actor, epoch=0), _cmd(forager.id, {}))
    result = execute_handler(ForageHandler(), _ctx(actor, epoch=4000), _cmd(forager.id, {}))

    assert result.ok


def test_forage_depletes_a_finite_node():
    actor, room, forager = _world(cooldown=0, remaining=1)

    execute_handler(ForageHandler(), _ctx(actor, epoch=0), _cmd(forager.id, {}))
    result = execute_handler(ForageHandler(), _ctx(actor, epoch=10), _cmd(forager.id, {}))

    assert not result.ok
    assert result.reason == "this has been picked clean"
    assert room.get_component(ResourceNodeComponent).remaining == 0


def test_forage_rejects_room_without_a_node():
    actor = WorldActor()
    room = spawn_entity(actor.world, [RoomComponent(title="Bare rock", biome="stone")])
    forager = spawn_entity(
        actor.world, [IdentityComponent(name="Bram", kind="character"), CharacterComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), forager.id)

    result = execute_handler(ForageHandler(), _ctx(actor), _cmd(forager.id, {}))

    assert not result.ok
    assert result.reason == "there is nothing to forage there"


def test_forage_rejects_when_not_in_a_room():
    actor = WorldActor()
    loner = spawn_entity(
        actor.world, [IdentityComponent(name="Drift", kind="character"), CharacterComponent()]
    )

    result = execute_handler(ForageHandler(), _ctx(actor), _cmd(loner.id, {}))

    assert not result.ok
    assert result.reason == "there is nothing to forage here"


def test_forage_rejects_unreachable_explicit_target():
    actor, _room, forager = _world()
    far_room = spawn_entity(
        actor.world,
        [RoomComponent(title="Far grove", biome="forest"), ResourceNodeComponent()],
    )

    result = execute_handler(
        ForageHandler(), _ctx(actor), _cmd(forager.id, {"target_id": str(far_room.id)})
    )

    assert not result.ok
    assert result.reason == "that is not within reach"


def test_forage_rejects_invalid_character():
    actor, _room, _forager = _world()

    result = execute_handler(ForageHandler(), _ctx(actor), _cmd("???", {}))

    assert not result.ok
    assert result.reason == "invalid character id"


def test_forage_explicit_node_item_in_room():
    actor, room, forager = _world()
    bush = spawn_entity(
        actor.world,
        [IdentityComponent(name="berry bush", kind="item"), ResourceNodeComponent(resource="figs")],
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), bush.id)

    result = execute_handler(
        ForageHandler(), _ctx(actor), _cmd(forager.id, {"target_id": str(bush.id)})
    )

    assert result.ok
    assert "figs" in _inventory_names(actor, forager)


def test_depleted_helper_and_prompt():
    node = ResourceNodeComponent(remaining=0)
    assert node.depleted()
    assert node.prompt_fragments(None) == ()
    live = replace(node, remaining=2)
    assert not live.depleted()
