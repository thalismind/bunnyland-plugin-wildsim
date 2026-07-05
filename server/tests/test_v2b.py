"""Coverage tests for wildsim v2: rejection paths, prompt fragments, helpers, edge branches."""

from __future__ import annotations

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    WorldClockComponent,
    spawn_entity,
)
from bunnyland.core.commands import CommandCost, Lane, build_submitted_command
from bunnyland.core.components import SuspendedComponent
from bunnyland.core.ecs import replace_component
from bunnyland.core.handlers import HandlerContext
from bunnyland.mechanics.environment import CalendarComponent
from bunnyland.prompts.context import ComponentPromptContext, PromptPerspective

from bunnyland_wildsim.components import ScentComponent
from bunnyland_wildsim.events import GameBaggedEvent, GameTrappedEvent
from bunnyland_wildsim.hunting import HuntHandler
from bunnyland_wildsim.luck import character_luck, luck_bonus
from bunnyland_wildsim.predators import (
    PredatorIncursionConsequence,
    PredatorPressureComponent,
    ensure_predator_pressure,
)
from bunnyland_wildsim.seasons import scarcity_fragment
from bunnyland_wildsim.tanning import HideComponent, PeltComponent, TanHideHandler, total_insulation
from bunnyland_wildsim.trapping import (
    CheckTrapHandler,
    SetTrapHandler,
    TrapComponent,
    TrappedIn,
    TrappingConsequence,
)
from bunnyland_wildsim.trophies import (
    TrophyComponent,
    game_weight,
    rarity_for,
    spawn_game_meat,
    spawn_hide,
)


def _cmd(cid, ct, payload=None):
    return build_submitted_command(
        character_id=str(cid),
        controller_id="ctrl",
        controller_generation=0,
        command_type=ct,
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload=payload or {},
    )


def _exec(handler_cls, actor, cid, ct, payload=None):
    return handler_cls().execute(HandlerContext(world=actor.world, epoch=0), _cmd(cid, ct, payload))


def _reason(handler_cls, actor, cid, ct, payload=None):
    return _exec(handler_cls, actor, cid, ct, payload).reason


def _room(actor, title="A"):
    return spawn_entity(actor.world, [RoomComponent(title=title)])


def _place(room, entity):
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), entity.id)


def _char(actor, room=None, *extra):
    c = spawn_entity(
        actor.world, [IdentityComponent(name="Vin", kind="character"), CharacterComponent(), *extra]
    )
    if room is not None:
        _place(room, c)
    return c


def _beast(actor, room, name, **scent):
    b = spawn_entity(
        actor.world, [IdentityComponent(name=name, kind="character"), ScentComponent(**scent)]
    )
    _place(room, b)
    return b


def _snare(actor, room=None, **trap):
    t = spawn_entity(
        actor.world, [IdentityComponent(name="snare", kind="item"), TrapComponent(**trap)]
    )
    if room is not None:
        _place(room, t)
    return t


# --- handler rejection paths ----------------------------------------------------------


def test_hunt_rejections():
    actor = WorldActor()
    room = _room(actor)
    hunter = _char(actor, room)
    assert _reason(HuntHandler, actor, "???", "hunt", {"target_id": "x"}) == "invalid character id"
    assert _reason(HuntHandler, actor, hunter.id, "hunt", {"target_id": "!"}) == "invalid target id"
    missing = _reason(HuntHandler, actor, hunter.id, "hunt", {"target_id": "entity_9999"})
    assert missing == "target does not exist"
    quarry = _beast(actor, _room(actor, "B"), "elk")
    far = _reason(HuntHandler, actor, hunter.id, "hunt", {"target_id": str(quarry.id)})
    assert far == "that quarry is not within reach"


def test_set_trap_rejects_bad_character():
    actor = WorldActor()
    assert _reason(SetTrapHandler, actor, "???", "set-trap") == "invalid character id"


def test_check_trap_and_tan_rejections():
    actor = WorldActor()
    who = _char(actor, _room(actor))
    bad_char = _reason(CheckTrapHandler, actor, "???", "check-trap", {"trap_id": "x"})
    assert bad_char == "invalid character id"
    bad_trap = _reason(CheckTrapHandler, actor, who.id, "check-trap", {"trap_id": "!"})
    assert bad_trap == "invalid trap id"
    no_char = _reason(TanHideHandler, actor, "???", "tan-hide", {"hide_id": "x"})
    assert no_char == "invalid character id"
    bad_hide = _reason(TanHideHandler, actor, who.id, "tan-hide", {"hide_id": "!"})
    assert bad_hide == "invalid hide id"


def test_hunt_without_health_component_does_not_crash():
    actor = WorldActor()
    room = _room(actor)
    hunter = _char(actor, room)  # no HealthComponent
    bear = _beast(actor, room, "bear", kind="predator")
    assert _exec(HuntHandler, actor, hunter.id, "hunt", {"target_id": str(bear.id)}).ok


def test_hunt_quarry_without_identity_is_named_game():
    actor = WorldActor()
    room = _room(actor)
    hunter = _char(actor, room)
    prey = spawn_entity(actor.world, [ScentComponent(kind="prey", strength=1.0)])  # no identity
    _place(room, prey)
    result = _exec(HuntHandler, actor, hunter.id, "hunt", {"target_id": str(prey.id)})
    assert result.ok and isinstance(result.events[0], GameBaggedEvent)
    assert result.events[0].species == "game"


# --- prompt fragments (first vs third person) -----------------------------------------


def _fp(world, entity):
    return ComponentPromptContext.for_entity(world, entity)


def _tp(world, entity, other):
    return ComponentPromptContext.for_entity(
        world, entity, perspective=PromptPerspective(viewer=other)
    )


def test_component_prompt_fragments():
    actor = WorldActor()
    world = actor.world
    other = spawn_entity(world, [IdentityComponent(name="bystander", kind="character")])
    hide = spawn_hide(world, species="deer", weight=6.0)
    assert hide.get_component(HideComponent).prompt_fragments(_fp(world, hide))
    assert hide.get_component(HideComponent).prompt_fragments(_tp(world, hide, other)) == ()
    pelt = spawn_entity(world, [IdentityComponent(name="pelt", kind="item"), PeltComponent()])
    assert pelt.get_component(PeltComponent).prompt_fragments(_fp(world, pelt))
    assert pelt.get_component(PeltComponent).prompt_fragments(_tp(world, pelt, other)) == ()
    trophy = spawn_game_meat(world, species="deer", weight=6.0)
    assert trophy.get_component(TrophyComponent).prompt_fragments(_fp(world, trophy))
    assert trophy.get_component(TrophyComponent).prompt_fragments(_tp(world, trophy, other)) == ()


# --- trophy helpers -------------------------------------------------------------------


def test_rarity_tiers_and_weight():
    assert rarity_for(2.0) == "common"
    assert rarity_for(5.0) == "uncommon"
    assert rarity_for(9.0) == "rare"
    assert game_weight(0.1) == 5.0  # floored at 1.0 strength
    assert game_weight(3.0) == 15.0


def test_total_insulation_with_no_pelts():
    actor = WorldActor()
    assert total_insulation(actor.world, _char(actor)) == 0.0


# --- seasons fragment bands -----------------------------------------------------------


def test_scarcity_fragment_bands():
    actor = WorldActor()
    assert scarcity_fragment(actor.world) is None  # no calendar
    cal = spawn_entity(actor.world, [CalendarComponent(season="autumn")])
    assert "thinning" in scarcity_fragment(actor.world)  # mid band
    replace_component(cal, CalendarComponent(season="summer"))
    assert scarcity_fragment(actor.world) is None  # plentiful


# --- luck active branch (fortune present) ---------------------------------------------


def test_luck_active_when_fortune_present(monkeypatch):
    monkeypatch.setattr("bunnyland_wildsim.luck._effective_luck", lambda entity: 6.0)
    actor = WorldActor()
    someone = _char(actor)
    assert character_luck(someone) == 6.0
    assert round(luck_bonus(someone), 6) == 0.3  # 6.0 * 0.05, under the cap


# --- trapping consequence edge branches -----------------------------------------------


def test_trapping_consequence_skips_sprung_unrooted_and_early():
    actor = WorldActor()
    room = _room(actor)
    _snare(actor, room, sprung=True)  # already sprung -> skipped
    _snare(actor, set_epoch=0)  # not in any room -> skipped
    _snare(actor, room, set_epoch=0)  # dwell not elapsed at epoch 100 -> skipped
    assert TrappingConsequence().process(actor.world, 100) == []


def test_check_trap_fallback_when_catch_vanished():
    actor = WorldActor()
    room = _room(actor)
    trapper = _char(actor, room)
    # A sprung trap with a recorded species but no live TrappedIn edge (the catch was lost).
    trap = _snare(actor, room, sprung=True, caught_species="hare")
    result = _exec(CheckTrapHandler, actor, trapper.id, "check-trap", {"trap_id": str(trap.id)})
    assert result.ok and isinstance(result.events[0], GameBaggedEvent)
    assert result.events[0].species == "hare"


def test_trap_catches_only_free_prey_and_reports():
    actor = WorldActor()
    room = _room(actor)
    trap = _snare(actor, room, set_epoch=0)
    hare = _beast(actor, room, "hare", kind="prey")
    events = TrappingConsequence().process(actor.world, 3600)
    assert any(isinstance(e, GameTrappedEvent) for e in events)
    assert [t for _e, t in trap.get_relationships(TrappedIn)] == [hare.id]


# --- predator target-room selection skips wild and suspended characters ---------------


def _predator_ready(actor):
    if not list(actor.world.query().with_all([WorldClockComponent]).execute_entities()):
        spawn_entity(actor.world, [WorldClockComponent()])
    clock = ensure_predator_pressure(actor.world)
    replace_component(clock, PredatorPressureComponent(base_pressure=0.9, next_incursion_epoch=0))
    return clock


def test_incursion_skips_wild_and_suspended_and_uses_a_room():
    actor = WorldActor()
    _predator_ready(actor)
    room = _room(actor, "Clearing")
    # The only "characters" are a wild predator and a suspended villager — both skipped, so
    # the incursion falls back to an available room rather than targeting them.
    _beast(actor, room, "fox", kind="predator")  # a CharacterComponent-less wild creature? no:
    _char(actor, room, ScentComponent(kind="predator"))  # a wild character -> skipped
    _char(actor, room, SuspendedComponent())  # suspended -> skipped
    assert PredatorIncursionConsequence().process(actor.world, 0)  # still lands in the room


def test_no_incursion_when_there_is_nowhere_to_send_one():
    actor = WorldActor()
    _predator_ready(actor)  # pressure is high and due, but there are no rooms at all
    assert PredatorIncursionConsequence().process(actor.world, 0) == []


def test_ensure_predator_pressure_is_idempotent():
    actor = WorldActor()
    first = ensure_predator_pressure(actor.world)
    second = ensure_predator_pressure(actor.world)
    assert first is not None and first.id == second.id
