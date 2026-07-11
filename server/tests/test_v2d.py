"""A few remaining v2 branch cases: component fragments and identity-less tanning."""

from __future__ import annotations

from bunnyland.core import (
    CharacterComponent,
    ContainmentMode,
    Contains,
    IdentityComponent,
    RoomComponent,
    WorldActor,
    spawn_entity,
)
from bunnyland.core.commands import CommandCost, Lane, build_submitted_command
from bunnyland.core.handlers import HandlerContext
from bunnyland.foundation.meters.mechanics import Meter
from bunnyland.prompts.context import ComponentPromptContext, PromptPerspective

from bunnyland_wildsim.components import CampfireComponent, ResourceNodeComponent, WarmthComponent
from bunnyland_wildsim.tanning import HideComponent, PeltComponent, TanHideHandler


def test_warmth_fragment_only_first_person_and_only_when_cold():
    actor = WorldActor()
    world = actor.world
    me = spawn_entity(world, [IdentityComponent(name="me", kind="character"), WarmthComponent()])
    other = spawn_entity(world, [IdentityComponent(name="other", kind="character")])
    warm = me.get_component(WarmthComponent)
    # Third person: a bystander does not read my body warmth.
    tp = ComponentPromptContext.for_entity(world, me, perspective=PromptPerspective(viewer=other))
    assert warm.prompt_fragments(tp) == ()
    # First person but comfortably warm (default meter is full): no line.
    assert warm.prompt_fragments(ComponentPromptContext.for_entity(world, me)) == ()


def test_warmth_bands_render_escalating_phrases():
    actor = WorldActor()
    world = actor.world
    for value in (55.0, 25.0, 8.0):  # chilly, cold, freezing bands
        meter = Meter(value=value, warning_at=60, urgent_at=35, crisis_at=15)
        who = spawn_entity(
            world, [IdentityComponent(name="c", kind="character"), WarmthComponent(meter=meter)]
        )
        ctx = ComponentPromptContext.for_entity(world, who)
        assert who.get_component(WarmthComponent).prompt_fragments(ctx)


def test_campfire_and_node_fragment_branches():
    actor = WorldActor()
    world = actor.world
    fire = spawn_entity(world, [IdentityComponent(name="fire", kind="item"), CampfireComponent()])
    ctx = ComponentPromptContext.for_entity(world, fire)
    assert "unlit" in fire.get_component(CampfireComponent).prompt_fragments(ctx)[0]
    node = spawn_entity(
        world, [IdentityComponent(name="bush", kind="item"), ResourceNodeComponent(remaining=0)]
    )
    node_ctx = ComponentPromptContext.for_entity(world, node)
    assert node.get_component(ResourceNodeComponent).prompt_fragments(node_ctx) == ()


def test_tan_a_hide_without_an_identity():
    actor = WorldActor()
    world = actor.world
    room = spawn_entity(world, [RoomComponent(title="Camp")])
    tanner = spawn_entity(
        world, [IdentityComponent(name="tanner", kind="character"), CharacterComponent()]
    )
    room.add_relationship(Contains(mode=ContainmentMode.ROOM_CONTENT), tanner.id)
    hide = spawn_entity(world, [HideComponent(species="fox")])  # no IdentityComponent
    tanner.add_relationship(Contains(mode=ContainmentMode.INVENTORY), hide.id)

    command = build_submitted_command(
        character_id=str(tanner.id),
        controller_id="ctrl",
        controller_generation=0,
        command_type="tan-hide",
        cost=CommandCost(action=1),
        lane=Lane.WORLD,
        payload={"hide_id": str(hide.id)},
    )
    result = TanHideHandler().execute(HandlerContext(world=world, epoch=0), command)
    assert result.ok
    assert hide.has_component(PeltComponent) and not hide.has_component(HideComponent)
