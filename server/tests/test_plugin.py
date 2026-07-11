from __future__ import annotations

from bunnyland.core.world_actor import WorldActor
from bunnyland.plugins import apply_plugins

from bunnyland_wildsim import (
    CampfireComponent,
    HideComponent,
    PeltComponent,
    PredatorPressureComponent,
    ResourceNodeComponent,
    ScentComponent,
    ScentTrailComponent,
    TrackerComponent,
    TrapComponent,
    TrophyComponent,
    WarmthComponent,
    WildGenerationEnricher,
    wildsim_fragments,
)
from bunnyland_wildsim.plugin import PLUGIN_ID
from bunnyland_wildsim.plugin import bunnyland_plugins as _plugins


def test_plugin_loads_with_module_qualified_id():
    plugins = _plugins()
    assert [p.id for p in plugins] == [PLUGIN_ID]


def test_plugin_declares_its_contributions():
    plugin = _plugins()[0]
    for component in (
        ScentComponent,
        ScentTrailComponent,
        TrackerComponent,
        WarmthComponent,
        CampfireComponent,
        ResourceNodeComponent,
    ):
        assert component in plugin.ecs.components
    assert WildGenerationEnricher in [type(item) for item in plugin.content.generation_enrichers]
    assert wildsim_fragments in plugin.content.prompt_fragments


def test_plugin_is_v2():
    plugin = _plugins()[0]
    assert plugin.version == "0.2.0"
    for component in (
        TrapComponent,
        HideComponent,
        PeltComponent,
        TrophyComponent,
        PredatorPressureComponent,
    ):
        assert component in plugin.ecs.components
    # Optional synergy with the fortune pack is a recommendation, never a hard requirement.
    assert plugin.dependencies.recommends == ("bunnyland.fortunesim",)
    assert plugin.dependencies.requires == ()


def test_plugin_applies_and_registers_verbs():
    actor = WorldActor()
    applied = apply_plugins(_plugins(), actor)
    assert applied[0].id == PLUGIN_ID
    command_types = {definition.command_type for definition in actor.action_definitions()}
    assert {
        "build-fire",
        "stoke-fire",
        "forage",
        "hunt",
        "set-trap",
        "check-trap",
        "tan-hide",
    } <= command_types
