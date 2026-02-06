# Phase 2 — Ben (Simulation Systems)

All simulation code. Everything here is headless, testable without PyGame, and deterministic (integer math only). Work on a feature branch and merge via PR.

**Branch:** `phase2-simulation`

---

## Shared Setup (do first, coordinate with theCoon)

Before either dev starts, agree on and commit these shared interface changes together (or have one person do it in a `phase2-interfaces` PR that both branch from):

- [ ] **Expand Entity dataclass** in `src/simulation/state.py`
  - Add fields: `entity_type: EntityType`, `hp: int`, `max_hp: int`, `state: EntityState`, `path: list[tuple[int, int]]`, `carrying: int`, `carry_capacity: int`
  - Add `EntityType` enum: `WORKER = 0, SOLDIER = 1, NEST = 2`
  - Add `EntityState` enum: `IDLE = 0, MOVING = 1, GATHERING = 2, ATTACKING = 3, BUILDING = 4`
  - Keep existing fields (`entity_id`, `player_id`, `x`, `y`, `target_x`, `target_y`, `speed`) unchanged
  - Update `compute_hash()` to include new fields
  - Update `create_entity()` to accept new fields with sensible defaults

- [ ] **Expand CommandType** in `src/simulation/commands.py`
  - Add: `GATHER = 3`, `BUILD = 4`
  - Add `target_entity_id: int = 0` field to Command (for GATHER target)
  - Update `sort_key()` if needed
  - Update `encode_commands` / `decode_commands` in `serialization.py` for new field

- [ ] **Add new config constants** in `src/config.py`
  - `MAP_WIDTH_TILES = 100`, `MAP_HEIGHT_TILES = 100` (update from 60x40)
  - `TILE_FOOD_AMOUNT = 500` (initial food per FOOD tile)
  - `GATHER_RATE = 10` (food units per tick while gathering)
  - `CARRY_CAPACITY = 100` (max food a worker can carry)
  - `SIGHT_RADIUS = 5` (tiles)
  - `WORKER_SPEED = 80`, `WORKER_HP = 100`
  - `STARTING_WORKERS = 5`

---

## Task 1: Tile Map & Procedural Generation

**File:** `src/simulation/tilemap.py`
**Tests:** `tests/test_simulation/test_tilemap.py`

- [ ] Define `TileType(IntEnum)`: DIRT=0, ROCK=1, WATER=2, FOOD=3
- [ ] Implement `TileMap` class:
  - `width: int`, `height: int`
  - `tiles: list[int]` (flat array, row-major, `tiles[y * width + x]`)
  - `food: list[int]` (parallel array, resource amount per tile)
  - `get_tile(x, y) -> TileType`
  - `set_tile(x, y, tile_type)`
  - `get_food(x, y) -> int`
  - `remove_food(x, y, amount) -> int` (returns actual amount removed)
  - `is_walkable(x, y) -> bool` (DIRT and FOOD are walkable, ROCK and WATER are not)
- [ ] Implement `generate_map(seed: int, width: int, height: int) -> TileMap`
  - Use the GameState PRNG (or a separate LCG seeded from the shared seed) — NO `random` module
  - Generate rock/water clusters via cellular automata (integer math)
  - Mirror map along center vertical axis for fairness
  - Guarantee starting area for each player: clear of obstacles, food nearby
  - Place food clusters (set tile type + food amount)
- [ ] Tests:
  - Same seed produces identical map
  - Different seeds produce different maps
  - Starting areas are walkable
  - Map is symmetric
  - `is_walkable` correct for each tile type
  - `remove_food` depletes and converts FOOD to DIRT

## Task 2: Integrate TileMap into GameState

**File:** `src/simulation/state.py`

- [ ] Add `tilemap: TileMap` field to `GameState`
- [ ] Add `player_resources: dict[int, int]` to `GameState` (player_id -> food)
- [ ] Generate tilemap in `GameState.__init__()` using the seed
- [ ] Update `compute_hash()` to include tilemap state (food amounts) and player resources
- [ ] Update `_setup_initial_state` in `game.py`: spawn `STARTING_WORKERS` per player + one NEST entity at each starting location

## Task 3: A* Pathfinding

**File:** `src/simulation/pathfinding.py`
**Tests:** `tests/test_simulation/test_pathfinding.py`

- [ ] Implement `find_path(tilemap: TileMap, start_x: int, start_y: int, goal_x: int, goal_y: int) -> list[tuple[int, int]]`
  - Coordinates are tile coordinates (not milli-tiles)
  - Returns list of (tile_x, tile_y) waypoints, empty list if no path
  - 8-directional movement
  - Cardinal cost: 1000, diagonal cost: 1414
  - Use a binary heap / heapq for the open set
  - Tie-breaking: deterministic (e.g., prefer lower y, then lower x)
- [ ] Tests:
  - Straight-line path on open map
  - Path around a wall of ROCK tiles
  - No path when completely blocked
  - Same inputs always produce same path (determinism)
  - Diagonal paths cost more than cardinal
  - Path avoids WATER tiles

## Task 4: Movement Along Path

**File:** `src/simulation/tick.py`

- [ ] Replace simple target-based movement with path-following:
  - Entity has `path: list[tuple[int, int]]` (waypoints in milli-tiles)
  - Each tick: move toward `path[0]`, when reached pop it, move toward next
  - When path is empty, entity state becomes IDLE
  - Entity state is MOVING while path is non-empty
- [ ] On MOVE command:
  - Convert target from milli-tiles to tile coords
  - Call `find_path()` from entity's current tile to target tile
  - Convert path waypoints back to milli-tile centers
  - Store on entity
- [ ] On STOP command:
  - Clear entity's path
  - Set state to IDLE
- [ ] Tests:
  - Entity follows multi-waypoint path
  - Entity stops at final waypoint
  - STOP clears path mid-movement

## Task 5: Resource Gathering

**File:** `src/simulation/tick.py` (extend `advance_tick`)
**Tests:** `tests/test_simulation/test_resources.py`

- [ ] GATHER command processing:
  - Find nearest FOOD tile to target location
  - Pathfind worker to that tile
  - Set entity state to MOVING, then GATHERING when arrived
- [ ] Gathering tick logic:
  - Entity in GATHERING state: remove `GATHER_RATE` food from tile per tick, add to `carrying`
  - When `carrying == carry_capacity` or tile depleted: auto-return to nearest NEST
  - Set state to MOVING (returning)
- [ ] Returning logic:
  - When worker arrives at NEST: add `carrying` to `player_resources[player_id]`, set `carrying = 0`
  - Auto-return to last food tile (or find new one if depleted)
- [ ] Tile depletion: when food reaches 0, convert FOOD tile to DIRT
- [ ] Tests:
  - Worker gathers food, carrying increases
  - Worker returns food to nest, stockpile increases
  - Depleted tile becomes DIRT
  - Worker auto-returns when full
  - Multiple workers can gather simultaneously

## Task 6: Fog of War

**File:** `src/simulation/visibility.py`
**Tests:** `tests/test_simulation/test_visibility.py`

- [ ] Define visibility states: `UNEXPLORED = 0`, `FOG = 1`, `VISIBLE = 2`
- [ ] Implement `VisibilityMap` class:
  - Per-player 2D grid of visibility states
  - `update(entities, player_id)` — recompute VISIBLE tiles from unit positions
  - Previously VISIBLE tiles become FOG (not UNEXPLORED)
  - `get_visibility(player_id, x, y) -> int`
  - Sight radius uses integer distance check: `dx*dx + dy*dy <= radius*radius`
- [ ] Add `VisibilityMap` to `GameState`
- [ ] Call `visibility.update()` at end of each `advance_tick()`
- [ ] Update `compute_hash()` to include visibility state
- [ ] Tests:
  - Unit reveals tiles within sight radius
  - Moving unit updates visibility
  - Previously seen tiles become FOG, not UNEXPLORED
  - Visibility is per-player

---

## Integration Notes

- theCoon will build rendering/input against **mock data** and the agreed interfaces
- Your TileMap, Entity fields, and visibility data are what the renderer will read
- Keep the `TileMap`, `Entity`, and `VisibilityMap` interfaces stable once agreed
- The renderer needs: `tilemap.get_tile(x,y)`, `tilemap.get_food(x,y)`, `entity.*` fields, `visibility.get_visibility(player_id, x, y)`
- Run `python -m pytest tests/` before every commit — all simulation tests must pass
