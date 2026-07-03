# Bunnyland Wildsim

Out-of-tree [Bunnyland](https://github.com/thalismind/bunnyland-server) plugin that adds a
Sims-4-expansion-sized **wilderness survival** pack. It layers four cohesive mechanics onto
the core Relics ECS, reusing the server's light, weather, needs/meter, and health systems:

- **Scent & trails** — creatures leave a decaying scent in each room they pass through;
  carried tracking gear points down the exit toward the strongest-scented neighbour.
- **Cold & warmth** — a body-warmth meter drains in cold rooms (weather, night, biome,
  exposure) and is restored by fire or shelter; freezing bleeds health.
- **Campfires** — a lightable, fuel-burning fire that raises its room's light and warms
  everyone in it, with `build-fire` and `stoke-fire` verbs.
- **Foraging** — biome-seeded resource nodes yield items on a per-node cooldown via a
  `forage` verb.

This repo intentionally keeps all wildsim work outside the main `bunnyland-server` repo.

## Layout

- `server/` - Python Bunnyland plugin package with the survival components, the passive
  consequences (scent, warmth, campfire), prompt fragments, a worldgen enrichment hook, the
  player/AI verbs, and tests.

## Server Plugin

The plugin exposes `bunnyland_wildsim.bunnyland_plugins()` and contributes:

- `ScentComponent`, `ScentTrailComponent`, `TrackerComponent` - scent & tracking.
- `WarmthComponent` - body warmth (reuses the shared needs/meter primitive).
- `CampfireComponent` - a lightable fire; `ResourceNodeComponent` - a forageable source.
- `ScentConsequence`, `WarmthConsequence`, `CampfireConsequence` - the per-tick passive sim.
- `wildsim_fragments` - renders survival state into both human and AI prompts.
- `WildWorldgenHook` - scents generated predators/prey and seeds resource nodes per biome.
- `build-fire`, `stoke-fire`, and `forage` - verbs for humans and AI.

## Running

This package builds no containers. It is loaded into the stock server via `--module`:

```bash
bunnyland serve --module bunnyland_wildsim
```

`default_enabled=True`, so no `--plugin` flag is required once the module is imported. The
`bunnyland_wildsim` package must be importable by the server (installed into the server's
environment, or on `PYTHONPATH`).

## Development

Run server tests against a sibling `bunnyland-server` checkout (no install required —
`server/tests/conftest.py` puts both packages on `sys.path`). From `server/`:

```bash
uv run --project ../../bunnyland-server -m pytest
uv run --project ../../bunnyland-server ruff check src tests
```

See [`server/README.md`](server/README.md) for more detail.

## Contributing & Conduct

This plugin follows the Bunnyland project's
[contribution guidelines](CONTRIBUTING.md) and [code of conduct](CODE_OF_CONDUCT.md),
which point back to the `bunnyland-server` repository.

## License

Licensed under the GNU Affero General Public License v3.0. See [LICENSE](LICENSE).
