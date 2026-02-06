# Scenario Test Harness

Spec for a high-level test framework that lets you define game scenarios declaratively and assert outcomes. Write the test first, then implement until it passes.

## Problem

Current tests operate at low level: manually create entities, set milli-tile positions, build Command objects, call `advance_tick`. This is fine for unit tests but bad for verifying gameplay flows like "ant harvests corpse and returns jelly to hive."

## Design

### Files

```
tests/
├── scenario.py              # Scenario class + map helpers
└── test_scenarios/
    ├── __init__.py
    ├── test_movement.py      # movement + pathfinding scenarios
    ├── test_harvest.py       # harvest loop scenarios
    ├── test_combat.py        # attack + auto-aggro scenarios
    └── test_hive.py          # spawn, merge, found scenarios
```

### ASCII Map Format

Small, explicit maps defined as strings. No random generation — you control every tile.

```python
MAP = """
..........
..........
.....X....
.....X....
.....X....
..........
..........
"""
```

Characters:
- `.` — dirt (walkable)
- `X` — rock (not walkable)

Leading/trailing blank lines are stripped. Map dimensions are inferred from the string.

### Scenario Class API

```python
class Scenario:
    def __init__(self, tilemap: TileMap, seed: int = 42): ...
```

Creates a GameState with the given tilemap (overriding the default `generate_map`). No starting entities, no starting jelly, no hives — blank slate.

#### Adding entities

All positions in **tile coordinates** (the class handles milli-tile conversion internally, placing entities at tile centers).

```python
# Returns entity_id (int)
ant = s.add_ant(player=0, tile=(5, 5))
hive = s.add_hive(player=0, tile=(2, 5))
corpse = s.add_corpse(tile=(8, 5), jelly=10)
queen = s.add_queen(player=0, tile=(5, 5))
site = s.add_hive_site(tile=(10, 5))
aphid = s.add_aphid(tile=(7, 3))
beetle = s.add_beetle(tile=(9, 4))
```

Each method creates an entity with the correct EntityType and default stats from config (HP, damage, speed, sight, etc). Returns the `entity_id`.

#### Issuing commands

Tile coordinates for targets. The class builds proper `Command` objects with milli-tile positions and correct tick timing.

```python
s.move(entity_id, tile=(15, 5))            # MOVE command
s.attack(entity_id, target_entity_id)      # ATTACK command
s.harvest(entity_id, corpse_entity_id)     # HARVEST to specific corpse
s.harvest_move(entity_ids, tile=(10, 5))   # HARVEST with target_entity_id=-1
s.stop(entity_id)                          # STOP command
s.spawn_ant(hive_entity_id, player=0)      # SPAWN_ANT command
s.merge_queen(ant_ids, hive_entity_id, player=0)  # MERGE_QUEEN command
s.found_hive(queen_id, site_id, player=0)  # FOUND_HIVE command
```

Commands are queued at `state.tick + 1` (executed on the next `run` call).

#### Running the simulation

```python
s.run(ticks=100)   # advance_tick N times
```

Each call to `run` advances the simulation by N ticks with any queued commands. Commands are consumed on the tick they're scheduled for; subsequent ticks get empty command lists.

#### Querying state

```python
s.entity(entity_id)          # returns the Entity object (or raises)
s.entity_at(tile=(5, 5))     # returns Entity at that tile (within 1 tile tolerance)
s.player_jelly(player_id)    # returns jelly count
s.entities_of_type(EntityType.ANT, player=0)  # list of entity_ids
s.state                      # raw GameState access
```

#### Assertions

```python
s.assert_at(entity_id, tile=(15, 5))                   # entity within 1 tile of target
s.assert_at(entity_id, tile=(15, 5), tolerance=0)       # exact tile match
s.assert_state(entity_id, EntityState.IDLE)             # entity state check
s.assert_carrying(entity_id, amount)                    # exact carrying amount
s.assert_carrying_gte(entity_id, amount)                # carrying >= amount
s.assert_alive(entity_id)                               # entity exists and hp > 0
s.assert_dead(entity_id)                                # entity removed or hp <= 0
s.assert_player_jelly(player_id, amount)                # exact jelly
s.assert_player_jelly_gte(player_id, amount)            # jelly >= amount
```

All assertions raise `AssertionError` with a descriptive message including actual vs expected values and entity position.

### Map Helper Functions

```python
def ascii_map(text: str) -> TileMap:
    """Parse ASCII art into a TileMap. '.' = dirt, 'X' = rock."""

def open_map(width: int, height: int) -> TileMap:
    """All-dirt map with rock border (1 tile thick)."""
```

`open_map` adds a 1-tile rock border so out-of-bounds movement is blocked naturally (matching how `TileMap.get_tile` returns ROCK for OOB).

### GameState Integration

The `Scenario` class needs to inject a custom tilemap into GameState. Options:

1. **Monkey-patch after init**: Create `GameState(seed=N)`, then replace `state.tilemap` with the custom one. Simple but the constructor still generates the full 100x100 map (wasted work).

2. **New GameState parameter**: Add an optional `tilemap` kwarg to `GameState.__init__`. If provided, skip `generate_map`. Cleaner.

**Go with option 2.** Modify `GameState.__init__`:

```python
def __init__(self, seed: int = 0, tilemap: TileMap | None = None) -> None:
    ...
    if tilemap is not None:
        self.tilemap = tilemap
    else:
        self.tilemap = generate_map(seed, MAP_WIDTH_TILES, MAP_HEIGHT_TILES)
```

Also set `player_jelly` to `{0: 0, 1: 0}` when a custom tilemap is provided (scenarios start from zero, add jelly explicitly if needed).

---

## Example Scenarios

### Movement

```python
class TestMovement:
    def test_move_straight_no_obstacles(self):
        s = Scenario(open_map(20, 10))
        ant = s.add_ant(player=0, tile=(3, 5))
        s.move(ant, tile=(17, 5))
        s.run(ticks=300)
        s.assert_at(ant, tile=(17, 5))
        s.assert_state(ant, EntityState.IDLE)

    def test_move_around_wall(self):
        MAP = """
        ............
        ............
        .....X......
        .....X......
        .....X......
        ............
        ............
        """
        s = Scenario(ascii_map(MAP))
        ant = s.add_ant(player=0, tile=(3, 3))
        s.move(ant, tile=(8, 3))
        s.run(ticks=200)
        s.assert_at(ant, tile=(8, 3))

    def test_stop_halts_movement(self):
        s = Scenario(open_map(20, 10))
        ant = s.add_ant(player=0, tile=(3, 5))
        s.move(ant, tile=(17, 5))
        s.run(ticks=10)
        s.stop(ant)
        s.run(ticks=1)
        pos_after_stop = (s.entity(ant).x, s.entity(ant).y)
        s.run(ticks=50)
        assert s.entity(ant).x == pos_after_stop[0]
        assert s.entity(ant).y == pos_after_stop[1]
```

### Harvest

```python
class TestHarvest:
    def test_harvest_specific_corpse(self):
        """Ant walks to corpse, extracts jelly, returns to hive, deposits."""
        s = Scenario(open_map(20, 10))
        hive = s.add_hive(player=0, tile=(3, 5))
        ant = s.add_ant(player=0, tile=(4, 5))
        corpse = s.add_corpse(tile=(10, 5), jelly=10)
        s.harvest(ant, corpse)
        s.run(ticks=500)
        s.assert_player_jelly_gte(0, 10)

    def test_harvest_multiple_trips(self):
        """Corpse has more jelly than carry capacity — ant makes multiple trips."""
        s = Scenario(open_map(20, 10))
        hive = s.add_hive(player=0, tile=(3, 5))
        ant = s.add_ant(player=0, tile=(4, 5))
        corpse = s.add_corpse(tile=(10, 5), jelly=25)
        s.harvest(ant, corpse)
        s.run(ticks=1500)
        s.assert_player_jelly_gte(0, 25)

    def test_harvest_move_finds_corpse(self):
        """Harvest-move: ant walks to area and auto-detects corpse nearby."""
        s = Scenario(open_map(20, 10))
        hive = s.add_hive(player=0, tile=(3, 5))
        ant = s.add_ant(player=0, tile=(4, 5))
        corpse = s.add_corpse(tile=(10, 5), jelly=10)
        s.harvest_move([ant], tile=(9, 5))  # near the corpse
        s.run(ticks=500)
        s.assert_player_jelly_gte(0, 5)  # got at least some jelly

    def test_ant_idles_after_corpse_empty(self):
        """Ant goes idle when corpse jelly is depleted."""
        s = Scenario(open_map(20, 10))
        hive = s.add_hive(player=0, tile=(3, 5))
        ant = s.add_ant(player=0, tile=(4, 5))
        corpse = s.add_corpse(tile=(6, 5), jelly=3)
        s.harvest(ant, corpse)
        s.run(ticks=500)
        s.assert_state(ant, EntityState.IDLE)
        s.assert_player_jelly_gte(0, 3)
```

### Combat

```python
class TestCombat:
    def test_attack_kills_enemy(self):
        """Ant attacks and kills a weak enemy."""
        s = Scenario(open_map(20, 10))
        ant = s.add_ant(player=0, tile=(5, 5))
        aphid = s.add_aphid(tile=(7, 5))
        s.attack(ant, aphid)
        s.run(ticks=200)
        s.assert_dead(aphid)

    def test_auto_aggro_diverts_to_closer_enemy(self):
        """Attack-moving ant diverts to enemy that enters aggro range."""
        s = Scenario(open_map(30, 10))
        ant = s.add_ant(player=0, tile=(5, 5))
        far_aphid = s.add_aphid(tile=(25, 5))
        near_aphid = s.add_aphid(tile=(7, 5))
        s.attack(ant, far_aphid)
        s.run(ticks=200)
        # Should have killed the near aphid first
        s.assert_dead(near_aphid)
```

### Hive Mechanics

```python
class TestHiveMechanics:
    def test_spawn_ant(self):
        """Spawn ant from hive deducts jelly and creates ant."""
        s = Scenario(open_map(20, 10))
        hive = s.add_hive(player=0, tile=(10, 5))
        s.set_jelly(player=0, amount=50)
        ant_count_before = len(s.entities_of_type(EntityType.ANT, player=0))
        s.spawn_ant(hive, player=0)
        s.run(ticks=100)  # wait for cooldown
        ant_count_after = len(s.entities_of_type(EntityType.ANT, player=0))
        assert ant_count_after == ant_count_before + 1

    def test_merge_queen(self):
        """Merge 5 ants at hive into a queen."""
        s = Scenario(open_map(20, 10))
        hive = s.add_hive(player=0, tile=(10, 5))
        ants = [s.add_ant(player=0, tile=(10, 5)) for _ in range(5)]
        s.merge_queen(ants, hive, player=0)
        s.run(ticks=10)
        queens = s.entities_of_type(EntityType.QUEEN, player=0)
        assert len(queens) == 1

    def test_found_hive(self):
        """Queen walks to hive site and founds a new hive."""
        s = Scenario(open_map(20, 10))
        s.add_hive(player=0, tile=(3, 5))  # need at least 1 existing hive
        queen = s.add_queen(player=0, tile=(5, 5))
        site = s.add_hive_site(tile=(15, 5))
        s.found_hive(queen, site, player=0)
        s.run(ticks=500)
        hives = s.entities_of_type(EntityType.HIVE, player=0)
        assert len(hives) == 2  # original + new one
```

---

## Implementation Notes

- `Scenario` is pure simulation — no PyGame, no rendering, no input handler.
- All commands go through `advance_tick` just like the real game.
- `run(ticks=N)` must handle command scheduling: commands are injected on the tick they were created for, empty lists for all other ticks.
- The `ascii_map` parser should `textwrap.dedent` and strip blank lines so indented maps in test code work.
- Entity creation helpers use config values (`ANT_HP`, `ANT_SPEED`, etc.) so tests break when balance changes — this is intentional.
- Tolerance for `assert_at` defaults to 1 tile (1000 milli-tiles) to account for separation push and path waypoint rounding.
