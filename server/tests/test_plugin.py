from __future__ import annotations

from bunnyland.core.world_actor import WorldActor
from bunnyland.plugins import apply_plugins, load_modules

from bunnyland_wildsim import (
    CampfireComponent,
    ResourceNodeComponent,
    ScentComponent,
    ScentTrailComponent,
    TrackerComponent,
    WarmthComponent,
    WildWorldgenHook,
    wildsim_fragments,
)
from bunnyland_wildsim.plugin import PLUGIN_ID


def test_plugin_loads_with_module_qualified_id():
    plugins = load_modules(["bunnyland_wildsim"])
    assert [p.id for p in plugins] == [f"bunnyland_wildsim.{PLUGIN_ID}"]


def test_plugin_declares_its_contributions():
    plugin = load_modules(["bunnyland_wildsim"])[0]
    for component in (
        ScentComponent,
        ScentTrailComponent,
        TrackerComponent,
        WarmthComponent,
        CampfireComponent,
        ResourceNodeComponent,
    ):
        assert component in plugin.ecs.components
    assert WildWorldgenHook in plugin.content.worldgen_hooks
    assert wildsim_fragments in plugin.content.prompt_fragments


def test_plugin_applies_and_registers_verbs():
    actor = WorldActor()
    applied = apply_plugins(load_modules(["bunnyland_wildsim"]), actor)
    assert applied[0].id == f"bunnyland_wildsim.{PLUGIN_ID}"
    command_types = {definition.command_type for definition in actor.action_definitions()}
    assert {"build-fire", "stoke-fire", "forage"} <= command_types
