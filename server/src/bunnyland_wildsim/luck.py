"""Optional luck bias: fold a character's fortune ``Luck`` into hunt/trap odds.

Wildsim runs perfectly well standalone. When the fortune pack happens to be installed, a
character's materialised luck gently nudges hunting outcomes their way; when it is not, the
import simply fails and luck stays neutral (a no-op). The dependency is *soft*: the guarded
import is the only place wildsim ever touches the fortune pack, and we read a value rather
than reaching into its state.
"""

from __future__ import annotations

import logging

from relics import Entity

logger = logging.getLogger(__name__)

try:  # Soft, optional: the fortune pack may not be installed.
    from bunnyland_fortunesim import effective_luck as _effective_luck
except ImportError:  # Standalone: no fortune pack, so luck is always neutral.
    _effective_luck = None
    logger.warning("bunnyland_fortunesim not installed; wildsim hunts run without a luck bias.")

#: How strongly luck tilts a deterministic outcome score. Gentle by design.
LUCK_WEIGHT = 0.05

#: The most luck may ever shift an outcome, either way — luck flavours, never decides.
LUCK_CAP = 0.5


def character_luck(entity: Entity) -> float:
    """Return an entity's materialised luck, or ``0.0`` when the fortune pack is absent."""
    if _effective_luck is None:
        return 0.0
    return _effective_luck(entity)


def luck_bonus(entity: Entity) -> float:
    """A bounded additive bias in ``[-LUCK_CAP, LUCK_CAP]`` from a character's luck."""
    return max(-LUCK_CAP, min(LUCK_CAP, character_luck(entity) * LUCK_WEIGHT))


__all__ = ["LUCK_CAP", "LUCK_WEIGHT", "character_luck", "luck_bonus"]
