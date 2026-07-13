from __future__ import annotations

import asyncio
import io
import sys

import pytest
from bunnyland.core import WorldActor
from bunnyland.foundation.media.plugin import plugin as media_plugin
from bunnyland.plugins import apply_plugins
from bunnyland.worldgen import RoomSpec, WorldProposal, instantiate

from bunnyland_wildsim.components import ResourceNodeComponent
from bunnyland_wildsim.integration_3d import berry_room, forest_room
from bunnyland_wildsim.plugin import plugin as wild_plugin


def _plugins_3d():
    from bunnyland_3d.plugin import plugin as plugin_3d

    return [media_plugin(), plugin_3d(), wild_plugin()]


def _room(actor, spec):
    result = asyncio.run(instantiate(actor, WorldProposal(seed="seed", rooms=[spec])))
    return actor.world.get_entity(result.rooms[spec.key])


def test_plugin_stays_independent_when_3d_is_disabled():
    sys.modules.pop("bunnyland_3d", None)
    actor = WorldActor()

    apply_plugins([wild_plugin()], actor)

    assert "bunnyland_3d" not in sys.modules
    assert wild_plugin().dependencies.integrates_with == ("bunnyland.3d",)


@pytest.mark.parametrize("biome", ["forest", "misty woodland", "rain jungle"])
def test_forest_and_berry_predicates(biome):
    actor = WorldActor()
    apply_plugins([wild_plugin()], actor)
    room = _room(actor, RoomSpec(key="wild", title="Wilds", biome=biome))

    assert forest_room(room)
    assert berry_room(room)
    assert room.get_component(ResourceNodeComponent).resource in {"berries", "wild fruit"}


def test_predicates_reject_indoor_and_nonfruit_resources():
    actor = WorldActor()
    apply_plugins([wild_plugin()], actor)
    indoor = _room(actor, RoomSpec(key="cabin", title="Cabin", biome="forest", indoor=True))
    tundra = _room(actor, RoomSpec(key="tundra", title="Tundra", biome="tundra"))

    assert not forest_room(indoor)
    assert not berry_room(indoor)
    assert not forest_room(tundra)
    assert not berry_room(tundra)


def test_models_convert_and_groups_are_stable_edge_biased(tmp_path, monkeypatch):
    trimesh = pytest.importorskip("trimesh")
    monkeypatch.setenv("BUNNYLAND_MEDIA_DIR", str(tmp_path / "media"))
    actor = WorldActor()
    apply_plugins(_plugins_3d(), actor)
    room = _room(actor, RoomSpec(key="forest", title="Forest", biome="forest"))

    from bunnyland_3d import HasDecoration3D, PropGroup3DComponent, require_model_registry
    from bunnyland_3d.api import room_scene_view

    registry = require_model_registry(actor)
    for key in ("bunnyland.wildsim/berry-bush", "bunnyland.wildsim/deciduous-tree"):
        model = registry.models[key]
        data = registry.media.read("models3d", model.url.rsplit("/", 1)[1])
        assert len(trimesh.load_scene(io.BytesIO(data), file_type="glb").geometry) >= 2
        assert model.asset.source.resolve().is_relative_to(model.asset.source.root)

    groups = {
        edge.role: actor.world.get_entity(target).get_component(PropGroup3DComponent)
        for edge, target in room.get_relationships(HasDecoration3D)
        if edge.role.startswith("bunnyland.wildsim/")
    }
    first = room_scene_view(actor, str(room.id))
    second = room_scene_view(actor, str(room.id))
    trees = next(
        item
        for item in first["decorations"]
        if item.get("decoration_source3d", {}).get("role") == "bunnyland.wildsim/deciduous-trees"
    )["prop_group3d"]["instances"]

    assert groups["bunnyland.wildsim/berry-bushes"].count == 9
    assert groups["bunnyland.wildsim/deciduous-trees"].count == 12
    assert first == second
    assert all(
        min(
            instance["position"]["x"],
            instance["position"]["z"],
            16 - instance["position"]["x"],
            16 - instance["position"]["z"],
        )
        == 2.0
        for instance in trees
    )
