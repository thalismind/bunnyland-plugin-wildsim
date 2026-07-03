from __future__ import annotations

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

from bunnyland_wildsim import ScentComponent, ScentConsequence, ScentTrailComponent
from bunnyland_wildsim.scent import strongest_adjacent_scent

EPOCH = 100


def _room(world, title="Glade"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _creature(world, room, *, strength=1.0):
    creature = spawn_entity(
        world,
        [
            IdentityComponent(name="fox", kind="character"),
            CharacterComponent(),
            ScentComponent(strength=strength),
        ],
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), creature.id)
    return creature


def _trail(room):
    return room.get_component(ScentTrailComponent).strength if room.has_component(
        ScentTrailComponent
    ) else 0.0


def test_creature_deposits_a_trail_in_its_room():
    actor = WorldActor()
    room = _room(actor.world)
    _creature(actor.world, room)

    ScentConsequence().process(actor.world, EPOCH)

    assert _trail(room) > 0.0


def test_empty_room_has_no_trail():
    actor = WorldActor()
    room = _room(actor.world)

    ScentConsequence().process(actor.world, EPOCH)

    assert not room.has_component(ScentTrailComponent)


def test_two_creatures_deposit_more_than_one():
    actor = WorldActor()
    solo_room = _room(actor.world, "Solo")
    pair_room = _room(actor.world, "Pair")
    _creature(actor.world, solo_room)
    _creature(actor.world, pair_room)
    _creature(actor.world, pair_room)

    ScentConsequence().process(actor.world, EPOCH)

    assert _trail(pair_room) > _trail(solo_room)


def test_trail_fades_after_creature_leaves():
    actor = WorldActor()
    room = _room(actor.world)
    creature = _creature(actor.world, room)
    consequence = ScentConsequence()

    consequence.process(actor.world, EPOCH)
    assert _trail(room) > 0.0

    actor.world.remove(creature.id)
    # Decay repeatedly until it fades below the removal threshold.
    for step in range(1, 12):
        consequence.process(actor.world, EPOCH + step)

    assert not room.has_component(ScentTrailComponent)


def test_trail_reaches_steady_state_while_creature_stays():
    actor = WorldActor()
    room = _room(actor.world)
    _creature(actor.world, room, strength=1.0)
    consequence = ScentConsequence()

    consequence.process(actor.world, EPOCH)
    first = _trail(room)
    consequence.process(actor.world, EPOCH + 1)
    second = _trail(room)

    assert second > first  # accumulates toward its steady state


def test_strongest_adjacent_scent_points_down_the_exit():
    actor = WorldActor()
    here = _room(actor.world, "Here")
    north = _room(actor.world, "North")
    south = _room(actor.world, "South")
    here.add_relationship(ExitTo(direction="north"), north.id)
    here.add_relationship(ExitTo(direction="south"), south.id)
    _creature(actor.world, north)  # only the north room is scented
    ScentConsequence().process(actor.world, EPOCH)

    best = strongest_adjacent_scent(actor.world, here)

    assert best is not None
    assert best[1] == "north"


def test_no_adjacent_scent_returns_none():
    actor = WorldActor()
    here = _room(actor.world, "Here")
    north = _room(actor.world, "North")
    here.add_relationship(ExitTo(direction="north"), north.id)

    assert strongest_adjacent_scent(actor.world, here) is None
