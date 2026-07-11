"""Optional, lazily imported Bunnyland 3D presentation integration."""

from __future__ import annotations

from pathlib import Path

from bunnyland.core import RoomComponent

from .components import ResourceNodeComponent

ASSET_ROOT = Path(__file__).with_name("assets")
FOREST_TERMS = ("forest", "woodland", "jungle")
BERRY_RESOURCES = ("berries", "wild fruit")


def berry_room(room) -> bool:
    if not room.has_component(RoomComponent) or not room.has_component(ResourceNodeComponent):
        return False
    component = room.get_component(RoomComponent)
    resource = room.get_component(ResourceNodeComponent).resource.casefold()
    return not component.indoor and any(term in resource for term in BERRY_RESOURCES)


def forest_room(room) -> bool:
    if not room.has_component(RoomComponent):
        return False
    component = room.get_component(RoomComponent)
    folded = f"{component.title} {component.biome}".casefold()
    return not component.indoor and any(term in folded for term in FOREST_TERMS)


def install_wildsim_3d(actor, context) -> None:
    if context.plugins is None or not context.plugins.enabled("bunnyland.3d"):
        return
    from bunnyland_3d import (
        AssetSource,
        ModelAsset,
        RoomDecorationRule,
        register_models,
        register_room_decorations,
    )

    register_models(
        actor,
        "bunnyland.wildsim",
        (
            ModelAsset(
                key="bunnyland.wildsim/berry-bush",
                source=AssetSource(ASSET_ROOT, "berry-bush.obj"),
                instanced=True,
                license="AGPL-3.0-or-later",
                attribution="Bunnyland Wildsim contributors",
            ),
            ModelAsset(
                key="bunnyland.wildsim/deciduous-tree",
                source=AssetSource(ASSET_ROOT, "deciduous-tree.obj"),
                instanced=True,
                license="AGPL-3.0-or-later",
                attribution="Bunnyland Wildsim contributors",
            ),
        ),
    )
    register_room_decorations(
        actor,
        "bunnyland.wildsim",
        (
            RoomDecorationRule(
                key="bunnyland.wildsim/berry-bushes",
                model_key="bunnyland.wildsim/berry-bush",
                room_predicate=berry_room,
                count=9,
                min_scale=0.72,
                max_scale=1.12,
                margin=2.4,
                tint="#477d3f",
            ),
            RoomDecorationRule(
                key="bunnyland.wildsim/deciduous-trees",
                model_key="bunnyland.wildsim/deciduous-tree",
                room_predicate=forest_room,
                count=12,
                min_scale=0.78,
                max_scale=1.28,
                margin=2.0,
                tint="#4f8248",
            ),
        ),
    )


__all__ = [
    "BERRY_RESOURCES",
    "FOREST_TERMS",
    "berry_room",
    "forest_room",
    "install_wildsim_3d",
]
