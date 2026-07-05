"""Behaviour tests for the wildsim v2 bundle: hunting, trapping, tanning, seasons, predators."""

from __future__ import annotations

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    HealthComponent,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    WorldClockComponent,
    spawn_entity,
)
from bunnyland.core.commands import CommandCost, Lane, build_submitted_command
from bunnyland.core.handlers import HandlerContext
from bunnyland.mechanics.consumables import FoodComponent
from bunnyland.mechanics.environment import CalendarComponent
from bunnyland.mechanics.storyteller import IncidentComponent

from bunnyland_wildsim.components import ScentComponent, TrackerComponent
from bunnyland_wildsim.events import (
    GameBaggedEvent,
    GameTrappedEvent,
    HideTannedEvent,
    HuntFoiledEvent,
    PredatorIncursionEvent,
    TrapSetEvent,
)
from bunnyland_wildsim.hunting import HuntHandler
from bunnyland_wildsim.luck import character_luck, luck_bonus
from bunnyland_wildsim.predators import (
    SECONDS_PER_DAY,
    PredatorIncursionConsequence,
    ensure_predator_pressure,
)
from bunnyland_wildsim.seasons import current_season, scarcity_fragment, season_scarcity
from bunnyland_wildsim.tanning import HideComponent, PeltComponent, TanHideHandler, total_insulation
from bunnyland_wildsim.trapping import (
    CheckTrapHandler,
    SetTrapHandler,
    TrapComponent,
    TrappedIn,
    TrappingConsequence,
)
from bunnyland_wildsim.trophies import TrophyComponent, spawn_hide

# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------


def _room(world, title="Woods"):
    return spawn_entity(world, [RoomComponent(title=title)])


def _place(world, room, entity, mode=ContainmentMode.ROOM_CONTENT):
    room.add_relationship(Contains(mode=mode), entity.id)


def _hold(character, item):
    character.add_relationship(Contains(mode=ContainmentMode.INVENTORY), item.id)


def _item(world, name, *extra):
    return spawn_entity(world, [IdentityComponent(name=name, kind="item"), *extra])


def _hunter(world, room, *, health=100.0, name="Vill"):
    character = spawn_entity(
        world,
        [
            IdentityComponent(name=name, kind="character"),
            CharacterComponent(),
            HealthComponent(current=health, maximum=100.0),
        ],
    )
    _place(world, room, character)
    return character


def _creature(world, room, name, *, kind="prey", strength=1.0):
    creature = spawn_entity(
        world,
        [
            IdentityComponent(name=name, kind="character"),
            ScentComponent(strength=strength, kind=kind),
        ],
    )
    _place(world, room, creature)
    return creature


def _cmd(character_id, command_type, payload=None):
    return build_submitted_command(
        character_id=str(character_id),
        controller_id="ctrl",
        controller_generation=0,
        command_type=command_type,
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload=payload or {},
    )


def _run(handler_cls, actor, character, command_type, payload=None, epoch=0):
    ctx = HandlerContext(world=actor.world, epoch=epoch)
    return handler_cls().execute(ctx, _cmd(character.id, command_type, payload))


def _inventory(world, character):
    return [world.get_entity(i) for _e, i in character.get_relationships(Contains)]


# --------------------------------------------------------------------------------------
# hunting
# --------------------------------------------------------------------------------------


def test_hunt_prey_yields_meat_and_hide():
    actor = WorldActor()
    room = _room(actor.world)
    hunter = _hunter(actor.world, room)
    deer = _creature(actor.world, room, "deer", kind="prey", strength=2.0)

    result = _run(HuntHandler, actor, hunter, "hunt", {"target_id": str(deer.id)})

    assert result.ok
    assert isinstance(result.events[0], GameBaggedEvent)
    assert not actor.world.has_entity(deer.id)  # quarry taken
    items = _inventory(actor.world, hunter)
    assert any(i.has_component(FoodComponent) for i in items)  # meat feeds core hunger
    assert any(i.has_component(HideComponent) for i in items)  # a tannable hide
    assert all(i.has_component(TrophyComponent) or i.has_component(FoodComponent) for i in items)


def test_hunt_rejects_unhuntable_target():
    actor = WorldActor()
    room = _room(actor.world)
    hunter = _hunter(actor.world, room)
    rock = _item(actor.world, "rock")
    _place(actor.world, room, rock)

    result = _run(HuntHandler, actor, hunter, "hunt", {"target_id": str(rock.id)})

    assert not result.ok
    assert result.reason == "there is nothing here to hunt"


def test_hunting_a_predator_barehanded_is_foiled_and_wounds():
    actor = WorldActor()
    room = _room(actor.world)
    hunter = _hunter(actor.world, room, health=100.0)
    bear = _creature(actor.world, room, "bear", kind="predator", strength=1.5)

    result = _run(HuntHandler, actor, hunter, "hunt", {"target_id": str(bear.id)})

    assert result.ok
    assert isinstance(result.events[0], HuntFoiledEvent)
    assert actor.world.has_entity(bear.id)  # it got away
    assert hunter.get_component(HealthComponent).current < 100.0  # mauled


def test_tracking_gear_lets_a_hunter_take_a_predator():
    actor = WorldActor()
    room = _room(actor.world)
    hunter = _hunter(actor.world, room, health=100.0)
    _hold(hunter, _item(actor.world, "tracking collar", TrackerComponent()))
    wolf = _creature(actor.world, room, "wolf", kind="predator", strength=1.5)

    result = _run(HuntHandler, actor, hunter, "hunt", {"target_id": str(wolf.id)})

    assert result.ok
    assert isinstance(result.events[0], GameBaggedEvent)
    assert not actor.world.has_entity(wolf.id)
    assert hunter.get_component(HealthComponent).current < 100.0  # a graze even on a kill


# --------------------------------------------------------------------------------------
# trapping
# --------------------------------------------------------------------------------------


def test_set_trap_places_a_snare():
    actor = WorldActor()
    room = _room(actor.world)
    trapper = _hunter(actor.world, room)

    result = _run(SetTrapHandler, actor, trapper, "set-trap")

    assert result.ok and isinstance(result.events[0], TrapSetEvent)
    assert len(list(actor.world.query().with_all([TrapComponent]).execute_entities())) == 1


def test_set_trap_rejects_when_not_in_a_room():
    actor = WorldActor()
    stray = spawn_entity(
        actor.world, [IdentityComponent(name="stray", kind="character"), CharacterComponent()]
    )

    result = _run(SetTrapHandler, actor, stray, "set-trap")

    assert not result.ok
    assert result.reason == "you have nowhere to set a trap"


def test_trap_catches_passing_prey_then_is_harvested():
    actor = WorldActor()
    room = _room(actor.world)
    trapper = _hunter(actor.world, room)
    trap = _item(actor.world, "snare", TrapComponent(set_epoch=0))
    _place(actor.world, room, trap)
    hare = _creature(actor.world, room, "hare", kind="prey", strength=1.0)

    # After the dwell time (no calendar -> scarcity 0 -> 3600s) the trap springs.
    dwell = 3600
    events = TrappingConsequence().process(actor.world, dwell)
    assert any(isinstance(e, GameTrappedEvent) for e in events)
    assert trap.get_component(TrapComponent).sprung
    assert [t for _e, t in trap.get_relationships(TrappedIn)] == [hare.id]

    result = _run(
        CheckTrapHandler, actor, trapper, "check-trap", {"trap_id": str(trap.id)}, epoch=dwell
    )
    assert result.ok and isinstance(result.events[0], GameBaggedEvent)
    assert not actor.world.has_entity(hare.id)  # harvested
    assert not trap.get_component(TrapComponent).sprung  # re-armed
    assert any(i.has_component(FoodComponent) for i in _inventory(actor.world, trapper))


def test_check_trap_rejects_non_trap_and_unsprung():
    actor = WorldActor()
    room = _room(actor.world)
    trapper = _hunter(actor.world, room)
    rock = _item(actor.world, "rock")
    _place(actor.world, room, rock)
    fresh = _item(actor.world, "snare", TrapComponent(set_epoch=0))
    _place(actor.world, room, fresh)

    not_trap = _run(CheckTrapHandler, actor, trapper, "check-trap", {"trap_id": str(rock.id)})
    assert not_trap.reason == "that is not a trap"
    empty = _run(CheckTrapHandler, actor, trapper, "check-trap", {"trap_id": str(fresh.id)})
    assert empty.reason == "the trap is empty and still set"


# --------------------------------------------------------------------------------------
# tanning
# --------------------------------------------------------------------------------------


def test_tan_hide_makes_a_warm_pelt():
    actor = WorldActor()
    room = _room(actor.world)
    tanner = _hunter(actor.world, room)
    hide = spawn_hide(actor.world, species="deer", weight=6.0)
    _hold(tanner, hide)

    result = _run(TanHideHandler, actor, tanner, "tan-hide", {"hide_id": str(hide.id)})

    assert result.ok and isinstance(result.events[0], HideTannedEvent)
    assert not hide.has_component(HideComponent)
    assert hide.has_component(PeltComponent)
    assert total_insulation(actor.world, tanner) > 0.0


def test_tan_hide_rejects_non_hide():
    actor = WorldActor()
    room = _room(actor.world)
    tanner = _hunter(actor.world, room)
    rock = _item(actor.world, "rock")
    _hold(tanner, rock)

    result = _run(TanHideHandler, actor, tanner, "tan-hide", {"hide_id": str(rock.id)})

    assert not result.ok
    assert result.reason == "that is not a hide to tan"


# --------------------------------------------------------------------------------------
# seasons & luck
# --------------------------------------------------------------------------------------


def test_season_scarcity_reads_the_calendar():
    actor = WorldActor()
    assert current_season(actor.world) is None
    assert season_scarcity(actor.world) == 0.0  # no calendar -> plenty
    spawn_entity(actor.world, [CalendarComponent(season="winter")])
    assert current_season(actor.world) == "winter"
    assert season_scarcity(actor.world) == 0.7
    assert "scarce" in scarcity_fragment(actor.world)


def test_luck_is_neutral_without_the_fortune_pack():
    actor = WorldActor()
    hunter = _hunter(actor.world, _room(actor.world))
    assert character_luck(hunter) == 0.0
    assert luck_bonus(hunter) == 0.0


# --------------------------------------------------------------------------------------
# predator incursions (a core storyteller incident)
# --------------------------------------------------------------------------------------


def _predator_world():
    actor = WorldActor()
    if not list(actor.world.query().with_all([WorldClockComponent]).execute_entities()):
        spawn_entity(actor.world, [WorldClockComponent()])
    ensure_predator_pressure(actor.world)
    _hunter(actor.world, _room(actor.world))  # a victim to threaten
    return actor


def test_lean_season_spawns_a_predator_incursion():
    actor = _predator_world()
    spawn_entity(actor.world, [CalendarComponent(season="winter")])  # 0.7 + base 0.4 > threshold

    events = PredatorIncursionConsequence().process(actor.world, SECONDS_PER_DAY)

    assert any(isinstance(e, PredatorIncursionEvent) for e in events)
    predators = [
        e
        for e in actor.world.query().with_all([ScentComponent]).execute_entities()
        if e.get_component(ScentComponent).kind == "predator"
    ]
    assert predators  # a predator arrived
    # It is stamped as a core storyteller incident, not a private one.
    assert list(actor.world.query().with_all([IncidentComponent]).execute_entities())


def test_no_incursion_before_it_is_due_or_in_plenty():
    actor = _predator_world()
    spawn_entity(actor.world, [CalendarComponent(season="winter")])
    # Not yet due (next_incursion_epoch defaults to one day out).
    assert PredatorIncursionConsequence().process(actor.world, 0) == []

    # Due, but a plentiful season keeps pressure below the incursion threshold.
    plentiful = _predator_world()
    spawn_entity(plentiful.world, [CalendarComponent(season="summer")])
    assert PredatorIncursionConsequence().process(plentiful.world, SECONDS_PER_DAY) == []
