"""Coverage for the spatial helpers and the aggregated v2 prompt fragments."""

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
from bunnyland.foundation.environment.mechanics import CalendarComponent
from bunnyland.foundation.meters.mechanics import Meter

from bunnyland_wildsim.components import (
    CampfireComponent,
    ResourceNodeComponent,
    ScentTrailComponent,
    TrackerComponent,
    WarmthComponent,
)
from bunnyland_wildsim.fragments import wildsim_fragments
from bunnyland_wildsim.spatial import holder_of, room_of
from bunnyland_wildsim.tanning import PeltComponent
from bunnyland_wildsim.trapping import TrapComponent
from bunnyland_wildsim.trophies import spawn_game_meat, spawn_hide

INV = ContainmentMode.INVENTORY


def _room(actor, title="A"):
    return spawn_entity(actor.world, [RoomComponent(title=title)])


def _place(container, entity, mode=ContainmentMode.ROOM_CONTENT):
    container.add_relationship(Contains(mode=mode), entity.id)


def _person(actor, room, *extra):
    person = spawn_entity(
        actor.world,
        [IdentityComponent(name="Vin", kind="character"), CharacterComponent(), *extra],
    )
    _place(room, person)
    return person


def _item(actor, name, *comps):
    return spawn_entity(actor.world, [IdentityComponent(name=name, kind="item"), *comps])


def test_holder_of_and_room_of():
    actor = WorldActor()
    world = actor.world
    room = _room(actor)
    char = _person(actor, room)
    held = _item(actor, "knife")
    _place(char, held, INV)
    loose = _item(actor, "log")
    _place(room, loose)
    orphan = _item(actor, "drifter")

    assert holder_of(world, held.id).id == char.id  # carried -> the holder
    assert holder_of(world, loose.id) is None  # loose in a room -> nobody
    assert holder_of(world, orphan.id) is None  # uncontained -> nobody
    assert holder_of(world, "entity_9999") is None  # missing -> nobody

    assert room_of(world, held.id).id == room.id  # resolves up through the holder
    assert room_of(world, loose.id).id == room.id  # loose on the floor
    assert room_of(world, orphan.id) is None  # uncontained -> no room
    assert room_of(world, "entity_9999") is None  # missing -> no room


def test_fragments_render_every_v2_signal():
    actor = WorldActor()
    world = actor.world
    room = _room(actor)
    room.add_component(ScentTrailComponent(strength=2.0))  # a lingering trail in this room

    # An adjacent room downwind carries a strong scent for the tracker to pull toward.
    downwind = _room(actor, "Downwind")
    downwind.add_component(ScentTrailComponent(strength=9.0))
    room.add_relationship(ExitTo(direction="north"), downwind.id)

    freezing = WarmthComponent(meter=Meter(value=8.0, warning_at=60, urgent_at=35, crisis_at=15))
    char = _person(actor, room, freezing)
    _place(char, _item(actor, "collar", TrackerComponent()), INV)
    _place(char, spawn_hide(world, species="deer", weight=6.0), INV)
    _place(char, spawn_game_meat(world, species="elk", weight=9.0), INV)
    _place(char, _item(actor, "pelt", PeltComponent()), INV)

    # Reachable room furniture: a campfire, a forage node, and both a set and a sprung trap.
    _place(room, _item(actor, "fire", CampfireComponent(lit=True, fuel=3.0)))
    _place(room, _item(actor, "bush", ResourceNodeComponent()))
    _place(room, _item(actor, "snare", TrapComponent(set_epoch=0)))
    _place(room, _item(actor, "snare", TrapComponent(sprung=True, caught_species="hare")))
    spawn_entity(world, [CalendarComponent(season="winter")])  # lean season -> scarcity line

    text = " ".join(wildsim_fragments(world, char))
    assert "freezing" in text  # warmth first-person line
    assert "tracker" in text.lower()  # tracker read
    assert "pelt" in text and "hide" in text and "trophy" in text  # carried items
    assert "campfire" in text.lower() and "forage" in text  # reachable furniture
    assert "trap" in text  # trap lines
    assert "scent trail" in text  # lingering trail
    assert "scarce" in text  # lean winter


def test_fragments_tracker_with_no_adjacent_scent():
    actor = WorldActor()
    char = _person(actor, _room(actor))
    _place(char, _item(actor, "collar", TrackerComponent()), INV)
    assert any("no fresh trail" in line for line in wildsim_fragments(actor.world, char))


def test_fragments_empty_for_a_bare_character():
    actor = WorldActor()
    char = _person(actor, _room(actor))
    assert wildsim_fragments(actor.world, char) == []
