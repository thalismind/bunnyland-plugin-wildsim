"""Runtime wiring: register the passive survival consequences on a world actor."""

from __future__ import annotations

from bunnyland.core.world_actor import WorldActor

from .campfire import CampfireConsequence
from .scent import ScentConsequence
from .warmth import WarmthConsequence


def install_wildsim(actor: WorldActor) -> None:
    """Register the scent, warmth, and campfire consequences (a ``service_factories`` entry)."""
    actor.register_consequence(ScentConsequence())
    actor.register_consequence(WarmthConsequence())
    actor.register_consequence(CampfireConsequence())


__all__ = ["install_wildsim"]
