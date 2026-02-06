# Phase 2 — Ben (Simulation Systems)

All simulation code. Everything here is headless, testable without PyGame, and deterministic (integer math only). Work on a feature branch and merge via PR.

**Branch:** `phase2-simulation`

**Reference:** [game_mechanics.md](../game_mechanics.md), [balance.md](../balance.md)

---

## Shared Setup — DONE

The shared interfaces PR has been merged. The following are already in place:

- [x] `EntityType`: ANT, QUEEN, HIVE, HIVE_SITE, CORPSE, APHID, BEETLE, MANTIS
- [x] `EntityState`: IDLE, MOVING, ATTACKING, HARVESTING, FOUNDING
- [x] `Entity` fields: entity_id, entity_type, player_id, x, y, target_x, target_y, speed, hp, max_hp, damage, state, path, carrying, jelly_value
- [x] `CommandType`: MOVE, STOP, HARVEST, SPAWN_ANT, MERGE_QUEEN, FOUND_HIVE
- [x] `Command.target_entity_id` field added, serialization updated
- [x] Config: all balance parameters from balance.md

---

## Task 1: Tile Map & Procedural Generation — DONE

**File:** `src/simulation/tilemap.py`
**Tests:** `tests/test_simulation/test_tilemap.py`

- [x] Define `TileType(IntEnum)`: DIRT=0, ROCK=1
  - Two tile types only: DIRT (walkable) and ROCK (impassable)
- [x] Implement `TileMap` class:
  - `width: int`, `height: int`
  - `tiles: list[int]` (flat array, row-major, `tiles[y * width + x]`)
  - `get_tile(x, y) -> TileType` (out-of-bounds returns ROCK)
  - `set_tile(x, y, tile_type)`
  - `is_walkable(x, y) -> bool` (DIRT is walkable, ROCK is not)
  - `start_positions: list[tuple[int, int]]` — player spawn tile coords
  - `hive_site_positions: list[tuple[int, int]]` — expansion point tile coords
- [x] Implement `generate_map(seed: int, width: int, height: int) -> TileMap`
  - Deterministic LCG — NO `random` module
  - Cellular automata (4 iterations, 5-neighbor rule) for organic rock formations
  - Horizontally mirrored for 2-player fairness
  - Rock border around map edges
  - Player starting areas cleared (radius 6)
  - Hive sites at symmetrical locations, cleared (radius 3)
  - All clearings applied symmetrically via `_clear_symmetric()`
- [x] Tests (17 passing):
  - Same seed → identical map
  - Different seeds → different maps
  - Map is horizontally symmetric
  - Starting areas are walkable
  - Start positions are symmetric
  - Border is rock
  - Hive sites placed and walkable
  - Both tile types present
  - Determinism verified across multiple seeds

## Task 2: Integrate TileMap + Jelly Economy into GameState — DONE

**Files:** `src/simulation/state.py`, `src/game.py`, `src/rendering/renderer.py`

- [x] Add `tilemap: TileMap` field to `GameState` (generated from seed in `__init__`)
- [x] Add `player_jelly: dict[int, int]` to `GameState` — `{0: 50, 1: 50}` (STARTING_JELLY)
- [x] Update `compute_hash()` to include player_jelly + tilemap tiles + signed player_id
- [x] Update `_setup_initial_state` in `game.py`:
  - 1 HIVE per player (hp=200, speed=0) at tilemap start positions
  - 5 ANTs per player (hp=20, dmg=5, speed=60) clustered around hive
  - HIVE_SITE entities (neutral, player_id=-1) at expansion points
- [x] Renderer draws entity types distinctly (hive=large circle, hive_site=diamond, ant=small circle)
- [x] Debug overlay shows Jelly + Ant count

## Task 3: A* Pathfinding — DONE

**File:** `src/simulation/pathfinding.py`
**Tests:** `tests/test_simulation/test_pathfinding.py`

- [x] Implement `find_path(tilemap, start_x, start_y, goal_x, goal_y) -> list[tuple[int, int]]`
  - Tile coordinates (not milli-tiles)
  - Returns waypoints from start (exclusive) to goal (inclusive), empty list if no path
  - 8-directional movement with diagonal corner-cutting prevention
  - Cardinal cost: 1000, diagonal cost: 1414
  - Binary heap (heapq) open set
  - Deterministic tie-breaking: lower f-cost, then lower y, then lower x
  - Octile distance heuristic (admissible and consistent)
- [x] Tests (16 passing):
  - Straight-line paths: horizontal, vertical, diagonal
  - Path around a wall of ROCK tiles, path through gap in wall
  - No path: completely blocked, goal is rock, start is rock, start == goal
  - Determinism: same inputs same path, identical maps same path
  - Diagonal costs more than cardinal, prefers cardinal when shorter
  - Path avoids ROCK tiles
  - No diagonal corner-cutting through rocks
  - Start position excluded from returned path

## Task 4: Movement Along Path — DONE

**File:** `src/simulation/tick.py`

- [x] Path-following movement:
  - Entity's `path: list[tuple[int, int]]` stores milli-tile waypoints
  - Each tick: move toward `path[0]`, snap + pop when within speed distance
  - When path empties, target_x/target_y set to current position (idle)
  - Direct movement fallback for entities with target but no path
- [x] On MOVE command:
  - Convert target to tile coords, call `find_path()` for A* path
  - Convert tile waypoints to milli-tile centers, store on entity
  - Set target_x/target_y to final waypoint for renderer indicator
- [x] On STOP command:
  - Clear entity's path, set target to current position
- [x] Tests (5 new path-following + existing updated):
  - Entity follows path waypoints
  - Waypoints popped as reached
  - Entity stops at final waypoint
  - STOP clears path mid-movement
  - MOVE computes walkable path around rocks

## Task 5: Combat System

**File:** `src/simulation/combat.py`
**Tests:** `tests/test_simulation/test_combat.py`

- [ ] Auto-attack logic:
  - Each tick, ants attack the nearest enemy within `ATTACK_RANGE` tiles
  - Damage is `entity.damage // TICK_RATE` per tick (DPS converted to per-tick)
  - Both ants and wildlife can be attacked
  - Hives can be attacked (structures don't fight back)
- [ ] Death and corpse creation:
  - When `entity.hp <= 0`, remove entity and create a CORPSE entity at that position
  - Corpse `jelly_value` = `ANT_CORPSE_JELLY` (or wildlife's jelly value)
  - Corpse has `player_id = -1` (neutral, any player can harvest)
- [ ] Corpse decay:
  - Corpses lose jelly_value over time, removed after `CORPSE_DECAY_TICKS`
- [ ] Tests:
  - Ants deal damage to enemies in range
  - Entity dies when HP reaches 0
  - Corpse is created on death with correct jelly value
  - Corpses decay and disappear
  - Hives take damage from enemy ants

## Task 6: Harvesting (Corpse Jelly Collection)

**File:** `src/simulation/tick.py` (extend `advance_tick`)
**Tests:** `tests/test_simulation/test_harvest.py`

- [ ] HARVEST command processing:
  - Pathfind ants to target corpse entity
  - Set entity state to MOVING, then HARVESTING when arrived
- [ ] Harvesting tick logic:
  - Entity in HARVESTING state: transfer jelly from corpse to `carrying`
  - When corpse is depleted or ant is full: auto-return to nearest own HIVE
  - Set state to MOVING (returning)
- [ ] Returning logic:
  - When ant arrives at HIVE: add `carrying` to `player_jelly[player_id]`, set `carrying = 0`
- [ ] Tests:
  - Ant harvests corpse, carrying increases
  - Ant returns jelly to hive, stockpile increases
  - Depleted corpse is removed
  - Multiple ants can harvest same corpse

## Task 7: Hive Mechanics (Spawning, Income)

**File:** `src/simulation/tick.py` (extend `advance_tick`)
**Tests:** `tests/test_simulation/test_hive.py`

- [ ] Passive jelly income:
  - Each HIVE entity generates `HIVE_PASSIVE_INCOME / TICK_RATE` jelly per tick
  - Add to `player_jelly[player_id]`
- [ ] SPAWN_ANT command:
  - Target a HIVE entity (via `target_entity_id`)
  - Deduct `ANT_SPAWN_COST` from player_jelly
  - After `ANT_SPAWN_COOLDOWN` ticks, create a new ANT entity near the hive
  - Reject if insufficient jelly
- [ ] MERGE_QUEEN command:
  - Select `QUEEN_MERGE_COST` ants at a hive
  - Remove those ants, create one QUEEN entity
  - Queen has QUEEN_HP, QUEEN_SPEED, no damage
- [ ] FOUND_HIVE command:
  - Queen moves to a HIVE_SITE entity
  - When queen arrives: remove queen, convert HIVE_SITE to HIVE (set player_id)
- [ ] Win condition:
  - Player is eliminated when all their HIVE entities are destroyed
  - Last player with >=1 hive wins → set `game_over=True`, `winner=player_id`
- [ ] Tests:
  - Passive income accumulates
  - Ant spawns after cooldown, jelly deducted
  - Queen merges from ants
  - Queen founds hive at site
  - Player eliminated when last hive destroyed

## Task 8: Wildlife

**File:** `src/simulation/wildlife.py`
**Tests:** `tests/test_simulation/test_wildlife.py`

- [ ] Wildlife entity creation:
  - APHID: `hp=5, damage=0, jelly_value=3, speed=0` (passive, doesn't move)
  - BEETLE: `hp=80, damage=8, jelly_value=25, speed=20`
  - MANTIS: `hp=200, damage=20, jelly_value=80, speed=15`
- [ ] Wildlife spawning:
  - Periodically spawn wildlife at random map locations (using GameState PRNG)
  - Spawn rates configurable; avoid spawning near hives
- [ ] Wildlife AI (simple):
  - Beetles/mantis: attack nearby ants if any within range, otherwise idle
  - Aphids: do nothing
- [ ] Tests:
  - Wildlife spawns at valid locations
  - Beetles attack ants in range
  - Aphids don't attack
  - Killed wildlife creates corpse with correct jelly

## Task 9: Fog of War

**File:** `src/simulation/visibility.py`
**Tests:** `tests/test_simulation/test_visibility.py`

- [ ] Define visibility states: `UNEXPLORED = 0`, `FOG = 1`, `VISIBLE = 2`
- [ ] Implement `VisibilityMap` class:
  - Per-player 2D grid of visibility states
  - `update(entities, player_id)` — recompute VISIBLE tiles from unit/hive positions
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
- The renderer needs: `tilemap.get_tile(x,y)`, `entity.*` fields, `visibility.get_visibility(player_id, x, y)`
- Run `python -m pytest tests/` before every commit — all simulation tests must pass
