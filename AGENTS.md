# Agent Guidelines for AntCraft

## Code Style

- Python 3, PEP 8 conventions.
- Use type hints for function signatures.
- Keep modules focused — one responsibility per file.
- Prefer composition over inheritance for game entities.

## Game Mechanics

- **Always consult `specs/game_mechanics.md` and `specs/balance.md`** before implementing or changing any gameplay system. These specs are the source of truth for how the game works.
- Do not invent mechanics or make assumptions — if it's not in the specs, ask.

## Game Development Rules

- **Frame-rate independence:** All movement and timers must use delta-time (`dt`), never raw frame counts.
- **Game loop:** Maintain a clear separation between `update(dt)` and `draw(screen)` phases.
- **State management:** Use a state/scene system (menu, gameplay, pause, etc.) — don't put everything in one loop.
- **Constants:** Define magic numbers (screen size, speeds, colors) as named constants in a config module.

## P2P / Multiplayer

- Game logic must be deterministic — same inputs produce same outputs regardless of platform.
- Avoid floating-point math in game simulation where determinism is required; use fixed-point or integer math.
- Separate rendering from simulation so the network layer only needs to synchronize inputs/commands.

## Testing

- Write tests for game logic (pathfinding, resource calculations, combat resolution).
- Rendering code doesn't need unit tests, but simulation code does.
- Use `pytest` for all tests.

### Testing checklist for every change

For every new feature or bug fix, complete all applicable steps:

1. **Unit tests** — create or update low-level tests in `tests/test_simulation/` for the specific subsystem changed.
2. **Scenario tests** — create or update high-level scenario tests in `tests/test_scenarios/` that exercise the feature end-to-end. Use the `Scenario` harness in `tests/scenario.py` (see below).
3. **Regression** — re-run existing scenario tests that may be affected by the change: `python -m pytest tests/test_scenarios/ -v`.
4. **Balance validation** — if the change affects combat stats, unit costs, income rates, or any value in `src/config.py`, run relevant scenario tests to confirm no single unit or strategy becomes dominant (e.g. an ant should not trivially solo a beetle).
5. **Full suite** — run `python -m pytest tests/ -v` and confirm zero failures before considering the task complete.

### Scenario test harness (`tests/scenario.py`)

The scenario harness provides a high-level, declarative API for testing gameplay flows without touching PyGame or networking. Key features:

- **`ascii_map(text)`** / **`open_map(w, h)`** — create small test maps.
- **`Scenario(tilemap)`** — wraps a `GameState` with tile-coordinate helpers.
- **Entity creation** — `add_ant(player, tile)`, `add_hive(...)`, `add_corpse(tile, jelly)`, `add_queen(...)`, `add_hive_site(...)`, `add_aphid(...)`, `add_beetle(...)`, `add_mantis(...)`. All accept an optional `label` for readable error output.
- **Commands** — `move(id, tile)`, `attack(id, target_id)`, `harvest(id, corpse_id)`, `stop(id)`, `spawn_ant(hive_id, player)`, `merge_queen(ant_ids, hive_id, player)`, `found_hive(queen_id, site_id, player)`.
- **`run(ticks=N)`** — advances the simulation.
- **Assertions** — `assert_at`, `assert_state`, `assert_alive`, `assert_dead`, `assert_carrying`, `assert_player_jelly`, `assert_player_jelly_gte`, etc. Each produces rich failure messages with entity details, an ASCII mini-map, and game state context.
- **`dump()`** — returns a full ASCII state visualization (map with entity markers, legend table, jelly, tick). Use this in assertion messages or for debugging.

Example:
```python
from tests.scenario import Scenario, open_map
from src.simulation.state import EntityState

s = Scenario(open_map(20, 10))
ant = s.add_ant(player=0, tile=(3, 5))
s.move(ant, tile=(17, 5))
s.run(ticks=300)
s.assert_at(ant, tile=(17, 5))
s.assert_state(ant, EntityState.IDLE)
```

Tips for writing scenario tests:
- Keep maps small to avoid wildlife interference (hive exclusion zone is 10 tiles).
- Use `assert_player_jelly_gte` instead of exact jelly checks when hives are present (passive income adds jelly).
- `assert_at` has a default 1-tile tolerance to account for separation push.
- Corpses decay after 150 ticks — keep combat tests short if you need to check corpses.

## File Organization

- `src/` — all game source code.
- `tests/` — mirrors `src/` structure.
- `assets/` — sprites, sounds, maps (tracked via Git LFS if large).

## Hotkeys

- When adding or changing keyboard shortcuts, always update `docs/hotkeys.md` to keep the manual in sync.

## Commit Practices

- Small, focused commits with clear messages.
- Don't commit generated files, caches, or virtual environments.
