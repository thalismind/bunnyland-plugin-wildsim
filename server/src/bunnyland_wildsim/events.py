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


__all__ = [
    "FireBuiltEvent",
    "FireBurnedOutEvent",
    "FireStokedEvent",
    "ForagedEvent",
    "FreezingDamageEvent",
]
