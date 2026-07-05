"""Seasonal scarcity: game and predators both grow lean and hungry in the cold months.

This module never re-derives the calendar; it reads the core
:class:`~bunnyland.mechanics.environment.CalendarComponent` season and maps it to a
``[0, 1]`` scarcity pressure. Hunting, trapping, and predator incursions each fold that
pressure into their own deterministic outcomes, so one core input (the season) ripples
across the whole pack.
"""

from __future__ import annotations

from bunnyland.mechanics.environment import CalendarComponent
from relics import World

#: Scarcity per season (higher is leaner). Winter is hardest; summer is plentiful.
SEASON_SCARCITY: dict[str, float] = {
    "spring": 0.1,
    "summer": 0.0,
    "autumn": 0.3,
    "winter": 0.7,
}

#: With no calendar in the world we assume plenty, so the pack runs cleanly bare.
DEFAULT_SCARCITY = 0.0


def current_season(world: World) -> str | None:
    """Return the world's current season, or ``None`` if no calendar clock exists."""
    clocks = sorted(
        world.query().with_all([CalendarComponent]).execute_entities(), key=lambda e: str(e.id)
    )
    if not clocks:
        return None
    return clocks[0].get_component(CalendarComponent).season


def season_scarcity(world: World) -> float:
    """Return the ``[0, 1]`` scarcity pressure for the current season (``0`` with no clock)."""
    season = current_season(world)
    if season is None:
        return DEFAULT_SCARCITY
    return SEASON_SCARCITY.get(season, DEFAULT_SCARCITY)


def scarcity_fragment(world: World) -> str | None:
    """A prompt line describing lean seasons, or ``None`` when game is plentiful/unknown."""
    season = current_season(world)
    if season is None:
        return None
    scarcity = SEASON_SCARCITY.get(season, DEFAULT_SCARCITY)
    if scarcity >= 0.6:
        return f"Game is scarce this {season}; the hunting is lean and hungry."
    if scarcity >= 0.25:
        return f"The {season} game is thinning out; tracks are harder to come by."
    return None


__all__ = [
    "DEFAULT_SCARCITY",
    "SEASON_SCARCITY",
    "current_season",
    "scarcity_fragment",
    "season_scarcity",
]
