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

## Task 5: Combat System — DONE

**File:** `src/simulation/combat.py`
**Tests:** `tests/test_simulation/test_combat.py`

- [x] Auto-attack logic:
  - Each tick, entities with damage > 0 attack nearest enemy within `ATTACK_RANGE` tiles
  - Damage uses Bresenham-style distribution: `_damage_this_tick(dps, tick)` guarantees exactly `dps` total damage over every `TICK_RATE` ticks using integer math only
  - Two-phase snapshot: compute all attacks, then apply — order-independent and deterministic
  - Deterministic tie-breaking: lower entity_id wins when equidistant
  - Both ants and wildlife can be attacked; hives can be attacked (structures don't fight back)
  - Wildlife doesn't attack other wildlife
  - Entity state set to ATTACKING during combat, resets to IDLE when no target
- [x] Death and corpse creation:
  - When `entity.hp <= 0`, entity removed and CORPSE created at same position
  - Corpse `jelly_value` = `ANT_CORPSE_JELLY` / wildlife's configured jelly value
  - Corpse `hp` = `CORPSE_DECAY_TICKS` (used as decay timer), `player_id = -1`
  - Hives/queens destroyed without leaving corpses
  - Simultaneous kills supported (both entities can die on same tick)
- [x] Corpse decay:
  - Corpse `hp` decrements by 1 each tick, removed when `hp <= 0`
  - Decay runs before combat so newly created corpses aren't decayed immediately
- [x] Integration: `process_combat(state)` called in `advance_tick()` after separation, before fog of war
- [x] Tests (22 passing):
  - Damage distribution: sums to DPS, zero damage, even division, periodic
  - Auto-attack: damages enemy in range, no damage out of range, no friendly fire, attacks nearest, state management, mutual combat
  - Death: entity removed at 0 HP, corpse created with correct jelly, hive no corpse, simultaneous kills
  - Corpse decay: hp decrements, removed when expired, full decay cycle
  - Hive combat: takes damage, doesn't fight back
  - Determinism: identical state after multiple ticks, correct death timing

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

## Task 7: Hive Mechanics (Spawning, Income) — DONE

**File:** `src/simulation/hive.py`
**Tests:** `tests/test_simulation/test_hive.py`

- [x] Passive jelly income:
  - Bresenham-style distribution: HIVE_PASSIVE_INCOME (2) jelly/sec across TICK_RATE ticks
  - Multiple hives stack income for the same player
- [x] SPAWN_ANT command:
  - Target a HIVE (via `target_entity_id`), deduct ANT_SPAWN_COST from player_jelly
  - Set hive.cooldown = ANT_SPAWN_COOLDOWN; ant spawns at hive when cooldown reaches 0
  - Rejected if: insufficient jelly, hive already spawning, wrong player, not a hive
- [x] MERGE_QUEEN command:
  - Validate QUEEN_MERGE_COST ants within MERGE_RANGE (3 tiles) of own hive
  - Remove ants, create QUEEN (QUEEN_HP, QUEEN_SPEED, damage=0, QUEEN_SIGHT)
  - Rejected if: too few ants, ants too far, wrong player
- [x] FOUND_HIVE command:
  - Pathfind queen to HIVE_SITE, set state=FOUNDING
  - Each tick `_check_founding` detects arrival within FOUND_HIVE_RANGE (1 tile)
  - On arrival: remove queen + site, create new HIVE for player
- [x] Win condition:
  - Player eliminated when all HIVE entities destroyed
  - Last player with ≥1 hive wins → game_over=True, winner=player_id
  - Simultaneous elimination → draw (winner=-1)
- [x] Data model: added `cooldown: int = 0` to Entity, included in compute_hash
- [x] Config: added MERGE_RANGE=3, FOUND_HIVE_RANGE=1
- [x] Tick pipeline: `commands → movement → separation → combat → hive mechanics → fog of war → tick++`
- [x] Tests (26 passing):
  - Income: sums correctly, hive generates jelly, multiple hives stack, neutral sites no income
  - Spawn: deducts jelly, sets cooldown, ant appears after cooldown, rejected (insufficient jelly / already spawning / wrong player / not hive), correct ant stats
  - Merge: creates queen, removes ants, rejected (too few / too far / wrong player), correct queen stats
  - Found: queen moves to site, hive created on arrival, correct stats, site removed, rejected (not queen / not site), idle queen ignored
  - Win condition: eliminated, no false trigger, mutual elimination draw, site not counted
  - Determinism: spawn cycle, cooldown affects hash

## Task 8: Wildlife — DONE

**File:** `src/simulation/wildlife.py`
**Tests:** `tests/test_simulation/test_wildlife.py`

- [x] Wildlife entity creation:
  - APHID: `hp=5, damage=0, jelly_value=3, speed=0` (passive, doesn't move)
  - BEETLE: `hp=80, damage=8, jelly_value=25, speed=20`
  - MANTIS: `hp=200, damage=20, jelly_value=80, speed=15`
- [x] Wildlife spawning:
  - Every WILDLIFE_SPAWN_INTERVAL (100) ticks, roll PRNG to pick type (50% aphid, 30% beetle, 20% mantis)
  - Check population cap (20 aphids, 5 beetles, 2 mantis), spawn on random walkable tile
  - Avoid spawning within WILDLIFE_HIVE_EXCLUSION (10 tiles) of any hive
  - Up to 10 placement attempts per spawn; all PRNG via GameState.next_random()
- [x] Wildlife AI (simple):
  - Beetles/mantis: scan for nearest player entity within WILDLIFE_AGGRO_RANGE (5 tiles)
  - If found and idle (not attacking/moving), pathfind toward target
  - Combat system handles auto-attack when within ATTACK_RANGE
  - Aphids: do nothing (speed=0, damage=0)
- [x] Config: added BEETLE_SPEED=20, MANTIS_SPEED=15, WILDLIFE_SPAWN_INTERVAL=100, WILDLIFE_HIVE_EXCLUSION=10, WILDLIFE_MAX_APHIDS=20, WILDLIFE_MAX_BEETLES=5, WILDLIFE_MAX_MANTIS=2, WILDLIFE_AGGRO_RANGE=5
- [x] game.py: updated initial wildlife to use BEETLE_SPEED and MANTIS_SPEED
- [x] Tick pipeline: `commands → wildlife AI/spawn → movement → separation → combat → hive mechanics → fog of war → tick++`
- [x] Tests (19 passing):
  - AI: beetle chases ant, mantis chases ant, ignores distant ant, aphid no movement, no chase other wildlife, attacking doesn't retarget, moving doesn't retarget, chases nearest
  - Spawning: no spawn outside interval, spawns at interval, walkable tile, avoids hives, cap respected, correct stats (aphid/beetle/mantis), deterministic
  - Integration: killed wildlife creates corpse with correct jelly, determinism across ticks


## Integration Notes

- theCoon will build rendering/input against **mock data** and the agreed interfaces
- Your TileMap, Entity fields, and visibility data are what the renderer will read
- Keep the `TileMap`, `Entity`, and `VisibilityMap` interfaces stable once agreed
- The renderer needs: `tilemap.get_tile(x,y)`, `entity.*` fields, `visibility.get_visibility(player_id, x, y)`
- Run `python -m pytest tests/` before every commit — all simulation tests must pass
