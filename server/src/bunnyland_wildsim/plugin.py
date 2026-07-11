"""Bunnyland plugin entrypoint for the out-of-tree wilderness-survival pack."""

from __future__ import annotations

from bunnyland.plugins import (
    CommandContribution,
    ContentContribution,
    DependencyContribution,
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
from .enrichment import WildGenerationEnricher
from .events import (
    FireBuiltEvent,
    FireBurnedOutEvent,
    FireStokedEvent,
    ForagedEvent,
    FreezingDamageEvent,
    GameBaggedEvent,
    GameTrappedEvent,
    HideTannedEvent,
    HuntFoiledEvent,
    PredatorIncursionEvent,
    TrapSetEvent,
)
from .foraging import FORAGE_ACTION_DEFINITIONS, FORAGE_ACTION_HANDLERS
from .fragments import wildsim_fragments
from .hunting import HUNTING_ACTION_DEFINITIONS, HUNTING_ACTION_HANDLERS
from .install import install_wildsim
from .integration_3d import install_wildsim_3d
from .predators import PredatorPressureComponent, install_predators
from .tanning import (
    TANNING_ACTION_DEFINITIONS,
    TANNING_ACTION_HANDLERS,
    HideComponent,
    PeltComponent,
)
from .trapping import (
    TRAPPING_ACTION_DEFINITIONS,
    TRAPPING_ACTION_HANDLERS,
    TrapComponent,
    TrappedIn,
    install_trapping,
)
from .trophies import TrophyComponent

PLUGIN_ID = "bunnyland.wildsim"


def plugin() -> Plugin:
    return Plugin(
        id=PLUGIN_ID,
        name="Bunnyland Wildsim",
        version="0.2.0",
        default_enabled=True,
        # Optional synergy: fortunesim's luck gently nudges hunt/trap odds when present.
        dependencies=DependencyContribution(
            recommends=("bunnyland.fortunesim",), integrates_with=("bunnyland.3d",)
        ),
        ecs=EcsContribution(
            components=(
                ScentComponent,
                ScentTrailComponent,
                TrackerComponent,
                WarmthComponent,
                CampfireComponent,
                ResourceNodeComponent,
                TrapComponent,
                HideComponent,
                PeltComponent,
                TrophyComponent,
                PredatorPressureComponent,
            ),
            edges=(TrappedIn,),
        ),
        commands=CommandContribution(
            action_handlers=(
                *CAMPFIRE_ACTION_HANDLERS,
                *FORAGE_ACTION_HANDLERS,
                *HUNTING_ACTION_HANDLERS,
                *TRAPPING_ACTION_HANDLERS,
                *TANNING_ACTION_HANDLERS,
            ),
            action_definitions=(
                *CAMPFIRE_ACTION_DEFINITIONS,
                *FORAGE_ACTION_DEFINITIONS,
                *HUNTING_ACTION_DEFINITIONS,
                *TRAPPING_ACTION_DEFINITIONS,
                *TANNING_ACTION_DEFINITIONS,
            ),
            typed_events=(
                FireBuiltEvent,
                FireStokedEvent,
                FireBurnedOutEvent,
                ForagedEvent,
                FreezingDamageEvent,
                GameBaggedEvent,
                HuntFoiledEvent,
                TrapSetEvent,
                GameTrappedEvent,
                HideTannedEvent,
                PredatorIncursionEvent,
            ),
        ),
        runtime=RuntimeContribution(
            service_factories=(install_wildsim, install_trapping, install_predators),
            integration_factories=(install_wildsim_3d,),
        ),
        content=ContentContribution(
            prompt_fragments=(wildsim_fragments,),
            generation_enrichers=(WildGenerationEnricher(),),
        ),
    )


def bunnyland_plugins() -> list[Plugin]:
    return [plugin()]


__all__ = ["PLUGIN_ID", "bunnyland_plugins", "plugin"]
