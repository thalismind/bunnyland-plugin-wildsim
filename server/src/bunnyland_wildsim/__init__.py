"""Out-of-tree Bunnyland plugin: a wilderness-survival pack.

Bundles four cohesive mechanics — scent trails, cold & warmth, campfires, and foraging —
built on the core Relics ECS and reusing the server's light, weather, needs/meter, and
health subsystems.
"""

from .campfire import (
    BuildFireHandler,
    CampfireConsequence,
    StokeFireHandler,
    install_campfire,
)
from .components import (
    CampfireComponent,
    ResourceNodeComponent,
    ScentComponent,
    ScentTrailComponent,
    TrackerComponent,
    WarmthComponent,
    warmth_band,
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
from .foraging import ForageHandler
from .fragments import wildsim_fragments
from .hunting import HuntHandler, hunt_score
from .install import install_wildsim
from .luck import luck_bonus
from .plugin import PLUGIN_ID, bunnyland_plugins, plugin
from .predators import (
    PredatorIncursionConsequence,
    PredatorPressureComponent,
    ensure_predator_pressure,
    install_predators,
)
from .scent import ScentConsequence, strongest_adjacent_scent, tracker_carrier
from .seasons import current_season, scarcity_fragment, season_scarcity
from .spatial import holder_of, room_of
from .tanning import HideComponent, PeltComponent, TanHideHandler, total_insulation
from .trapping import (
    CheckTrapHandler,
    SetTrapHandler,
    SnareComponent,
    TrapComponent,
    TrappedIn,
    TrappingConsequence,
    install_trapping,
)
from .trophies import TrophyComponent, spawn_game_meat, spawn_hide
from .warmth import WarmthConsequence, lit_campfire_in_room, room_chill

__all__ = [
    "PLUGIN_ID",
    "BuildFireHandler",
    "CampfireComponent",
    "CampfireConsequence",
    "CheckTrapHandler",
    "FireBuiltEvent",
    "FireBurnedOutEvent",
    "FireStokedEvent",
    "ForageHandler",
    "ForagedEvent",
    "FreezingDamageEvent",
    "GameBaggedEvent",
    "GameTrappedEvent",
    "HideComponent",
    "HideTannedEvent",
    "HuntFoiledEvent",
    "HuntHandler",
    "PeltComponent",
    "PredatorIncursionConsequence",
    "PredatorIncursionEvent",
    "PredatorPressureComponent",
    "ResourceNodeComponent",
    "ScentComponent",
    "ScentConsequence",
    "ScentTrailComponent",
    "SetTrapHandler",
    "SnareComponent",
    "StokeFireHandler",
    "TanHideHandler",
    "TrackerComponent",
    "TrapComponent",
    "TrapSetEvent",
    "TrappedIn",
    "TrappingConsequence",
    "TrophyComponent",
    "WarmthComponent",
    "WarmthConsequence",
    "WildGenerationEnricher",
    "bunnyland_plugins",
    "current_season",
    "ensure_predator_pressure",
    "holder_of",
    "hunt_score",
    "install_campfire",
    "install_predators",
    "install_trapping",
    "install_wildsim",
    "lit_campfire_in_room",
    "luck_bonus",
    "plugin",
    "room_chill",
    "room_of",
    "scarcity_fragment",
    "season_scarcity",
    "spawn_game_meat",
    "spawn_hide",
    "strongest_adjacent_scent",
    "tracker_carrier",
    "total_insulation",
    "warmth_band",
    "wildsim_fragments",
]
