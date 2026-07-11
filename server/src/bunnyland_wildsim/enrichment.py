"""Declarative scent and forage-node generation enrichment."""

from bunnyland.core.generation import GenerationDelta, GenerationRequest

from .components import ResourceNodeComponent, ScentComponent

PREDATOR_TERMS = (
    "wolf",
    "bear",
    "fox",
    "lynx",
    "cougar",
    "lion",
    "tiger",
    "hunter",
    "predator",
    "hound",
    "hyena",
    "jackal",
)
PREY_TERMS = (
    "rabbit",
    "hare",
    "deer",
    "elk",
    "mouse",
    "vole",
    "boar",
    "goat",
    "sheep",
    "prey",
    "quail",
    "beast",
    "animal",
    "creature",
)
BIOME_RESOURCES = (
    ("forest", "berries", "food"),
    ("wood", "berries", "food"),
    ("jungle", "wild fruit", "food"),
    ("swamp", "cattail roots", "food"),
    ("marsh", "cattail roots", "food"),
    ("plain", "wild herbs", "food"),
    ("grass", "wild herbs", "food"),
    ("meadow", "wild herbs", "food"),
    ("desert", "cactus fruit", "food"),
    ("tundra", "lichen", "food"),
    ("snow", "lichen", "food"),
    ("mountain", "mushrooms", "food"),
    ("coast", "shellfish", "food"),
    ("beach", "shellfish", "food"),
    ("river", "reeds", "food"),
)


def _text(request):
    return " ".join(
        (request.source_key, request.entity_kind, request.description, *request.tags)
    ).casefold()


class WildGenerationEnricher:
    capabilities: tuple[str, ...] = ()

    def enrich(self, request: GenerationRequest) -> GenerationDelta:
        existing = tuple(request.context.get("base_components", ()))
        text = _text(request)
        if request.entity_kind == "character" and not any(
            isinstance(item, ScentComponent) for item in existing
        ):
            if any(term in text for term in PREDATOR_TERMS):
                return GenerationDelta(components=(ScentComponent(strength=1.5, kind="predator"),))
            if any(term in text for term in PREY_TERMS):
                return GenerationDelta(components=(ScentComponent(strength=1.0, kind="prey"),))
        if request.entity_kind == "room" and not any(
            isinstance(item, ResourceNodeComponent) for item in existing
        ):
            room = next(
                (item for item in existing if item.__class__.__name__ == "RoomComponent"), None
            )
            if room is None or room.indoor:
                return GenerationDelta()
            folded = room.biome.casefold()
            match = next(
                ((resource, kind) for term, resource, kind in BIOME_RESOURCES if term in folded),
                None,
            )
            if match is not None:
                return GenerationDelta(
                    components=(ResourceNodeComponent(resource=match[0], yield_kind=match[1]),)
                )
        return GenerationDelta()


__all__ = ["BIOME_RESOURCES", "PREDATOR_TERMS", "PREY_TERMS", "WildGenerationEnricher"]
