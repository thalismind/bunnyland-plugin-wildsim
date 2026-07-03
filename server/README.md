# bunnyland-wildsim (server plugin)

The out-of-tree Bunnyland plugin package `bunnyland_wildsim` — a wilderness-survival pack.

## Development

Tests run against a sibling `bunnyland-server` checkout without installing anything —
`tests/conftest.py` puts both this package's `src/` and `../bunnyland-server/src` on
`sys.path`. From this `server/` directory:

```bash
# uses the sibling bunnyland-server's virtualenv/deps
uv run --project ../../bunnyland-server -m pytest
# or, if bunnyland + relics are already importable:
python -m pytest
```

Lint:

```bash
uv run --project ../../bunnyland-server ruff check src tests
```

## Loading into the server

```bash
bunnyland serve --module bunnyland_wildsim
```

`default_enabled=True`, so no `--plugin` flag is required once the module is imported.

## What it contributes

- **Components** — `ScentComponent`, `ScentTrailComponent`, `TrackerComponent` (scent);
  `WarmthComponent` (body warmth, reusing the needs/meter primitive); `CampfireComponent`
  (a lightable fire); `ResourceNodeComponent` (a forageable source).
- **Consequences** — `ScentConsequence` (deposit/decay trails), `WarmthConsequence` (drain
  or restore warmth, freeze damage), `CampfireConsequence` (burn fuel, drive room light).
- **Prompt fragments** — `wildsim_fragments` renders warmth, tracker direction, campfires,
  forageable nodes, and lingering trails into both human and AI prompts.
- **A worldgen hook** — `WildWorldgenHook` scents generated predators/prey and seeds
  biome-appropriate resource nodes into outdoor rooms.
- **Three verbs** — `build-fire`, `stoke-fire`, and `forage`.
