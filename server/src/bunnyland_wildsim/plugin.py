"""Bunnyland plugin entrypoint for the out-of-tree wilderness-survival pack."""

from __future__ import annotations

from bunnyland.plugins import (
    CommandContribution,
    ContentContribution,
    EcsContribution,
    Plugin,
    RuntimeContribution,
)

from .campfire import CAMPFIRE_ACTION_DEFINITIONS, CAMPFIRE_ACTION_HANDLERS
from .components import (
    CampfireComponent,
    ResourceNodeComponent,
    ScentComponent,
    ScentTrailComponent,
    TrackerComponent,
    WarmthComponent,
)
from .enrichment import WildWorldgenHook
from .events import (
    FireBuiltEvent,
    FireBurnedOutEvent,
    FireStokedEvent,
    ForagedEvent,
    FreezingDamageEvent,
)
from .foraging import FORAGE_ACTION_DEFINITIONS, FORAGE_ACTION_HANDLERS
from .fragments import wildsim_fragments
from .install import install_wildsim

PLUGIN_ID = "bunnyland_wildsim"


def plugin() -> Plugin:
    return Plugin(
        id=PLUGIN_ID,
        name="Bunnyland Wildsim",
        version="0.1.0",
        default_enabled=True,
        ecs=EcsContribution(
            components=(
                ScentComponent,
                ScentTrailComponent,
                TrackerComponent,
                WarmthComponent,
                CampfireComponent,
                ResourceNodeComponent,
            ),
        ),
        commands=CommandContribution(
            action_handlers=(*CAMPFIRE_ACTION_HANDLERS, *FORAGE_ACTION_HANDLERS),
            action_definitions=(*CAMPFIRE_ACTION_DEFINITIONS, *FORAGE_ACTION_DEFINITIONS),
            typed_events=(
                FireBuiltEvent,
                FireStokedEvent,
                FireBurnedOutEvent,
                ForagedEvent,
                FreezingDamageEvent,
            ),
        ),
        runtime=RuntimeContribution(service_factories=(install_wildsim,)),
        content=ContentContribution(
            prompt_fragments=(wildsim_fragments,),
            worldgen_hooks=(WildWorldgenHook,),
        ),
    )


def bunnyland_plugins() -> list[Plugin]:
    return [plugin()]


__all__ = ["PLUGIN_ID", "bunnyland_plugins", "plugin"]
