# Simulation Architecture

The simulation is the deterministic core of AntCraft. Both peers run identical simulation code on identical state, driven by identical commands. If the simulation ever diverges between peers, it's a desync bug.

## Determinism Rules

- **All math is integer.** No floats anywhere in simulation code.
- **Coordinates use milli-tiles.** 1 tile = 1000 milli-tiles. This gives sub-tile precision without floating point.
- **Entity lists are ordered by entity_id.** New entities get incrementing IDs.
- **The PRNG is part of the state.** Use `state.next_random(bound)` (LCG). Never use Python's `random` module.
- **Bresenham-style distribution** converts per-second rates (DPS, income, harvest rate) to per-tick amounts using integer division: `(rate * (t+1)) // TICK_RATE - (rate * t) // TICK_RATE`. This guarantees exactly `rate` total over every `TICK_RATE` ticks.

## Tick Pipeline

`advance_tick()` in `tick.py` runs once per simulation tick (10 Hz). The phases run in this exact order:

```
1. _process_commands     — apply player commands (MOVE, STOP, ATTACK, HARVEST, SPAWN, MERGE, FOUND)
2. process_wildlife      — wildlife AI (aggro chase) + periodic spawning
3. _check_aggro          — divert attack-mode units to closer enemies within 25% sight range
4. _check_harvest_aggro  — divert harvesting ants to nearby corpses within 25% sight range
5. _update_movement      — move entities along A* paths or direct toward target
6. _apply_separation     — push overlapping mobile entities apart (snapshot-then-apply)
7. process_harvesting    — extract jelly from corpses, deposit at hives, auto-loop
8. process_combat        — decay corpses → auto-attack → process deaths
9. process_hive_mechanics — passive income → spawn cooldowns → founding → win condition
10. visibility.update     — recompute fog of war for both players
11. tick++
```

Order matters. Commands must be processed before movement. Movement must finish before harvesting checks arrival. Combat creates corpses that harvesting will handle next tick. Hive mechanics run last so newly spawned ants don't act until next tick.

## Modules

### `state.py` — Game State and Entities

The single source of truth. Contains:

- **GameState**: tick counter, entity list, PRNG state, player jelly, tilemap, visibility, game_over/winner
- **Entity**: dataclass with position (x, y in milli-tiles), target, path, HP, damage, speed, state, carrying, cooldown, etc.
- **EntityType**: ANT, QUEEN, HIVE, HIVE_SITE, CORPSE, APHID, BEETLE, MANTIS
- **EntityState**: IDLE, MOVING, ATTACKING, HARVESTING, FOUNDING
- **compute_hash()**: SHA-256 of full state for desync detection

### `commands.py` — Command Types and Queue

Commands are the only way players affect the simulation. All inputs become commands tagged with a tick number, shared over the network, and executed identically by both peers.

| Command | Description |
|---------|-------------|
| MOVE | Pathfind selected entities to a position |
| STOP | Halt entities at current position |
| ATTACK | Chase and fight a target entity |
| HARVEST | Send ants to collect jelly from a corpse |
| SPAWN_ANT | Spawn an ant from a hive (costs jelly) |
| MERGE_QUEEN | Merge 5 ants at a hive into a queen |
| FOUND_HIVE | Send a queen to claim a hive site |

The `CommandQueue` collects commands from both players keyed by tick. `pop_tick()` returns them sorted deterministically. `mark_empty()` signals that a player sent no commands for a tick (needed for lockstep sync).

### `tick.py` — Tick Processor

Orchestrates the tick pipeline. Contains:

- **`advance_tick(state, commands)`** — the main entry point
- **Command handlers**: `_handle_move`, `_handle_stop`, `_handle_attack`, `_handle_harvest` (hive commands delegate to `hive.py`)
- **`_update_movement`** / **`_follow_path`** / **`_move_toward`** — integer movement along A* paths
- **`_apply_separation`** — two-phase push: compute all pushes from snapshot, then apply. Deterministic tiebreaker for exact overlaps using entity_id
- **`_check_aggro`** / **`_check_harvest_aggro`** — smart retargeting for attack and harvest commands
- **`_find_nearest_walkable`** — BFS fallback when clicking on non-walkable tiles

### `combat.py` — Combat System

- **Auto-attack**: each entity with damage > 0 attacks nearest enemy within 1 tile (ATTACK_RANGE)
- **Two-phase snapshot**: compute all attacks first, then apply damage. Order-independent.
- **Death processing**: dead entities are removed, corpses created with jelly_value
- **Corpse decay**: corpses lose 1 HP per tick, removed when HP reaches 0 (15 sec lifetime)

### `harvest.py` — Harvesting System

Ant harvesting lifecycle:
1. Receive HARVEST command → pathfind to corpse
2. Arrive at corpse → extract jelly at HARVEST_RATE (Bresenham distributed, 5/sec)
3. When carrying capacity full (10 jelly) or corpse empty → pathfind to nearest own hive
4. Arrive at hive → deposit jelly to player stockpile
5. If corpse still has jelly → pathfind back for more; otherwise → go idle

### `hive.py` — Hive Mechanics

- **Passive income**: each hive generates 2 jelly/sec (Bresenham distributed)
- **Ant spawning**: SPAWN_ANT deducts 10 jelly, sets hive cooldown to 20 ticks (2 sec). Ant appears at hive when cooldown reaches 0. Spawn position chosen from 8 adjacent tiles (PRNG-rotated)
- **Queen merging**: MERGE_QUEEN validates 5+ ants within 3 tiles of hive, removes ants, creates queen
- **Hive founding**: FOUND_HIVE pathfinds queen to hive site, sets state=FOUNDING. On arrival within 1 tile, queen + site removed, new hive created for player
- **Win condition**: player with 0 hives is eliminated. Last player standing wins. Simultaneous elimination = draw (winner=-1)

### `wildlife.py` — Wildlife AI and Spawning

- **AI**: beetles and mantis chase nearest player entity within 5-tile aggro range. Pathfind when idle. Aphids are stationary.
- **Spawning**: every 100 ticks (10 sec), roll PRNG: 50% aphid, 30% beetle, 20% mantis. Check population cap, find walkable tile away from hives (10-tile exclusion), create entity.

### `pathfinding.py` — A* Pathfinding

Grid-based A* on the tilemap. Returns a list of tile coordinates. Callers convert to milli-tile waypoints (tile center = `tile * 1000 + 500`).

### `tilemap.py` — Tile Map

Procedurally generated terrain. `is_walkable(tx, ty)` is the key query used by pathfinding, movement, spawning, and separation.

### `visibility.py` — Fog of War

Per-player visibility grids. Updated each tick from entity positions and sight radii. Three states: unexplored, fogged (seen before), visible (currently in sight).

## Desync Detection

Every `HASH_CHECK_INTERVAL` ticks (default 10), both peers compute `state.compute_hash()` (SHA-256 of all state fields) and compare. A mismatch means the simulations have diverged — a critical bug.

## Adding New Mechanics

When adding simulation logic:

1. Use integer math only. Convert per-second rates with the Bresenham formula.
2. Use `state.next_random(bound)` for any randomness. Both peers must call it the same number of times in the same order.
3. Add new fields to `Entity` if needed, and include them in `compute_hash()`.
4. Wire into the tick pipeline at the appropriate phase in `advance_tick()`.
5. Write tests that verify determinism (run N ticks, check hash matches expected).
