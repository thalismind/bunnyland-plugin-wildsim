"""Domain events emitted by the wildsim mechanics."""

from __future__ import annotations

from bunnyland.core.events import DomainEvent


class FireBuiltEvent(DomainEvent):
    """A character built and lit a campfire."""

    item_id: str
    fuel: float


class FireStokedEvent(DomainEvent):
    """A character fed fuel to a campfire."""

    item_id: str
    fuel: float


class FireBurnedOutEvent(DomainEvent):
    """A campfire consumed its last fuel and went out."""

    item_id: str


class ForagedEvent(DomainEvent):
    """A character foraged a resource node and gained an item."""

    node_id: str
    item_id: str
    resource: str


class FreezingDamageEvent(DomainEvent):
    """A freezing character lost health to the cold."""

    target_id: str
    damage: float
    health: float


# --------------------------------------------------------------------------------------
# v2: hunting, trapping, tanning, and seasonal predator incursions
# --------------------------------------------------------------------------------------


class GameBaggedEvent(DomainEvent):
    """Game was taken (by hunt or trap): the pack's public 'biggest-game' signal.

    A published connector event. Museum/festival packs can read ``species``/``weight`` to
    score a biggest-game contest, and ``trophy_id``/``game_id`` name the donatable items.
    """

    hunter_id: str
    species: str
    weight: float
    trophy_id: str
    game_id: str
    method: str  # "hunt" or "trap"


class HuntFoiledEvent(DomainEvent):
    """A hunt failed — the quarry escaped, and a cornered predator may have wounded the hunter."""

    target_id: str
    damage: float
    health: float


class TrapSetEvent(DomainEvent):
    """A character set a snare in their room."""

    trap_id: str


class GameTrappedEvent(DomainEvent):
    """A passing creature was caught in a set trap, awaiting harvest."""

    trap_id: str
    species: str


class HideTannedEvent(DomainEvent):
    """A raw hide was tanned into a warm pelt."""

    hide_id: str
    pelt_id: str
    insulation: float


class PredatorIncursionEvent(DomainEvent):
    """A seasonal predator incursion arrived as a storyteller incident."""

    incident_id: str
    predator_id: str
    season: str


__all__ = [
    "FireBuiltEvent",
    "FireBurnedOutEvent",
    "FireStokedEvent",
    "ForagedEvent",
    "FreezingDamageEvent",
    "GameBaggedEvent",
    "GameTrappedEvent",
    "HideTannedEvent",
    "HuntFoiledEvent",
    "PredatorIncursionEvent",
    "TrapSetEvent",
]
