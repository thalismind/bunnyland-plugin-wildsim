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
from .enrichment import WildWorldgenHook
from .events import (
    FireBuiltEvent,
    FireBurnedOutEvent,
    FireStokedEvent,
    ForagedEvent,
    FreezingDamageEvent,
)
from .foraging import ForageHandler
from .fragments import wildsim_fragments
from .install import install_wildsim
from .plugin import PLUGIN_ID, bunnyland_plugins, plugin
from .scent import ScentConsequence, strongest_adjacent_scent, tracker_carrier
from .spatial import holder_of, room_of
from .warmth import WarmthConsequence, lit_campfire_in_room, room_chill

__all__ = [
    "PLUGIN_ID",
    "BuildFireHandler",
    "CampfireComponent",
    "CampfireConsequence",
    "FireBuiltEvent",
    "FireBurnedOutEvent",
    "FireStokedEvent",
    "ForageHandler",
    "ForagedEvent",
    "FreezingDamageEvent",
    "ResourceNodeComponent",
    "ScentComponent",
    "ScentConsequence",
    "ScentTrailComponent",
    "StokeFireHandler",
    "TrackerComponent",
    "WarmthComponent",
    "WarmthConsequence",
    "WildWorldgenHook",
    "bunnyland_plugins",
    "holder_of",
    "install_campfire",
    "install_wildsim",
    "lit_campfire_in_room",
    "plugin",
    "room_chill",
    "room_of",
    "strongest_adjacent_scent",
    "tracker_carrier",
    "warmth_band",
    "wildsim_fragments",
]
