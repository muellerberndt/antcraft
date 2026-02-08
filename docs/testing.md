# Testing Guide

AntCraft has two layers of automated tests, both run with pytest. No PyGame or networking is needed — tests exercise the deterministic simulation layer directly.

## Running tests

```bash
# Full suite
python -m pytest tests/ -v

# Scenario tests only
python -m pytest tests/test_scenarios/ -v

# Single test file
python -m pytest tests/test_scenarios/test_combat.py -v

# Single test
python -m pytest tests/test_scenarios/test_combat.py::TestCombat::test_attack_kills_enemy -v
```

## Test structure

```
tests/
├── conftest.py                  # Shared fixtures (game_state, mock_peer)
├── scenario.py                  # Scenario test harness
├── test_simulation/             # Low-level unit tests
│   ├── test_tick.py             #   Movement, commands, separation
│   ├── test_combat.py           #   Damage, death, corpse decay
│   ├── test_hive.py             #   Income, spawning, merging, founding
│   ├── test_pathfinding.py      #   A* pathfinder
│   ├── test_wildlife.py         #   Wildlife AI and spawning
│   ├── test_visibility.py       #   Fog of war
│   ├── test_state.py            #   GameState, PRNG, hashing
│   ├── test_commands.py         #   Command queue
│   └── test_tilemap.py          #   Map generation
├── test_scenarios/              # High-level gameplay flow tests
│   ├── test_movement.py         #   Move, pathfind, stop
│   ├── test_harvest.py          #   Harvest loop
│   ├── test_combat.py           #   Attack, auto-aggro, death
│   └── test_hive.py             #   Spawn, merge, found, income
├── test_input/                  # Selection
├── test_networking/             # Serialization, UDP, lockstep
└── test_rendering/              # Camera
```

**Unit tests** (`test_simulation/`) test individual subsystems at the milli-tile level — creating entities manually, calling `advance_tick`, and checking raw state.

**Scenario tests** (`test_scenarios/`) test gameplay flows end-to-end using the `Scenario` harness, which provides a high-level tile-coordinate API.

## Scenario test harness

The harness lives in `tests/scenario.py`. It wraps `GameState` with a declarative API so you can set up scenarios in a few lines and get rich failure output.

### Quick start

```python
from tests.scenario import Scenario, open_map
from src.simulation.state import EntityState

class TestMyFeature:
    def test_ant_moves_to_target(self):
        s = Scenario(open_map(20, 10))
        ant = s.add_ant(player=0, tile=(3, 5))
        s.move(ant, tile=(17, 5))
        s.run(ticks=300)
        s.assert_at(ant, tile=(17, 5))
        s.assert_state(ant, EntityState.IDLE)
```

### Creating maps

**`open_map(width, height)`** — all-dirt map with a 1-tile rock border.

```python
s = Scenario(open_map(20, 10))
```

**`ascii_map(text)`** — custom map from ASCII art. `.` = dirt, `X` = rock. Indentation is stripped automatically.

```python
from tests.scenario import Scenario, ascii_map

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
```

### Adding entities

All positions are in **tile coordinates** — the harness converts to milli-tiles internally. Every method returns an `entity_id` (int) for use in commands and assertions.

```python
ant    = s.add_ant(player=0, tile=(5, 5))
hive   = s.add_hive(player=0, tile=(3, 5))
corpse = s.add_corpse(tile=(10, 5), jelly=10)
queen  = s.add_queen(player=0, tile=(5, 5))
site   = s.add_hive_site(tile=(15, 5))
aphid  = s.add_aphid(tile=(7, 3))
beetle = s.add_beetle(tile=(9, 4))
mantis = s.add_mantis(tile=(12, 6))
```

Each entity is created with the correct stats from `src/config.py` (HP, speed, damage, sight, etc.).

You can add an optional `label` for more readable failure messages:

```python
scout = s.add_ant(player=0, tile=(5, 5), label="scout")
```

### Issuing commands

Commands are queued and executed on the next `run()` call.

```python
s.move(ant, tile=(15, 5))              # Move to tile
s.attack(ant, aphid)                   # Attack a target
s.harvest(ant, corpse)                 # Harvest a specific corpse
s.harvest_move([ant], tile=(10, 5))    # Move to area, auto-detect corpses
s.stop(ant)                            # Stop in place
s.spawn_ant(hive, player=0)            # Spawn ant from hive
s.merge_queen(ant_ids, hive, player=0) # Merge 5 ants into queen
s.found_hive(queen, site, player=0)    # Send queen to found hive
```

### Running the simulation

```python
s.run(ticks=100)
```

You can issue commands between `run()` calls to simulate multi-step interactions:

```python
s.move(ant, tile=(10, 5))
s.run(ticks=50)          # Ant starts moving
s.stop(ant)
s.run(ticks=1)           # Ant stops
s.run(ticks=50)          # Verify it stays put
```

### Setting resources

```python
s.set_jelly(player=0, amount=50)
```

Scenarios start with 0 jelly. Use `set_jelly` when testing mechanics that require it (spawning, etc.).

### Querying state

```python
e = s.entity(entity_id)                 # Get Entity object (raises if dead)
e = s.entity_at(tile=(5, 5))            # Find entity near tile (1-tile tolerance)
jelly = s.get_player_jelly(player_id)   # Current jelly count
ids = s.entities_of_type(EntityType.ANT, player=0)  # All matching entity IDs
```

### Assertions

All assertions produce rich failure messages with entity details, actual vs expected values, a 15x15 ASCII mini-map, tick count, and jelly balances.

```python
s.assert_at(ant, tile=(15, 5))                    # Within 1 tile (default)
s.assert_at(ant, tile=(15, 5), tolerance=0)        # Exact tile
s.assert_state(ant, EntityState.IDLE)
s.assert_alive(ant)
s.assert_dead(aphid)
s.assert_carrying(ant, 5)                          # Exact amount
s.assert_carrying_gte(ant, 3)                      # At least this much
s.assert_player_jelly(0, 50)                       # Exact jelly
s.assert_player_jelly_gte(0, 10)                   # At least this much
```

### Debugging with dump()

`dump()` returns a full ASCII visualization of the game state — the map with entity markers, a legend table, jelly counts, and tick number.

```python
print(s.dump())
```

Output:

```
=== Scenario State at tick 42 ===

Map (20x10):
  01234567890123456789
 0 XXXXXXXXXXXXXXXXXXXX
 1 X..................X
 2 X..................X
 3 X..................X
 4 X..................X
 5 X..h.a.....c......X
 6 X..................X
 7 X..................X
 8 X..................X
 9 XXXXXXXXXXXXXXXXXXXX

Markers: lowercase=p0 UPPERCASE=p1 a/A=ant q/Q=queen h/H=hive s=site c=corpse p=aphid b=beetle m=mantis

   ID  Type       Player  Tile     State        HP       Carry  Label
  ------------------------------------------------------------------------
    0  HIVE       p0      (3,5)   IDLE         200/200   0      base
    1  ANT        p0      (5,5)   HARVESTING   20/20     5      scout
    2  CORPSE     neutral (11,5)  IDLE         140/150   0      -

Jelly: p0=25, p1=0
Tick: 42
```

You can include `dump()` in assertion messages for full context on failure:

```python
assert len(hives) == 2, f"Expected 2 hives\n{s.dump()}"
```

### Example: full harvest test

```python
from src.simulation.state import EntityState
from tests.scenario import Scenario, open_map

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
```

### Example: combat with labeled entities

```python
from src.simulation.state import EntityType
from tests.scenario import Scenario, open_map

class TestCombat:
    def test_ant_dies_to_beetle(self):
        """Ant attacked by beetle eventually dies, leaves corpse."""
        s = Scenario(open_map(20, 10))
        ant = s.add_ant(player=0, tile=(5, 5), label="doomed")
        beetle = s.add_beetle(tile=(6, 5))
        s.attack(ant, beetle)
        s.run(ticks=50)
        s.assert_dead(ant)
        corpses = s.entities_of_type(EntityType.CORPSE)
        assert len(corpses) >= 1
```

### Example: pathfinding around obstacles

```python
from tests.scenario import Scenario, ascii_map

class TestMovement:
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
```

## Tips

- **Keep maps small.** Wildlife spawns every 100 ticks on walkable tiles that are at least 10 tiles from a hive. Small maps (under ~12 tiles wide with a hive) prevent wildlife interference entirely.
- **Use `_gte` assertions for jelly** when hives are present — passive income (2 jelly/sec) adds jelly on top of whatever the test deposits.
- **`assert_at` has 1-tile tolerance** by default. The separation system gently pushes overlapping units apart, so exact positions may drift by a fraction of a tile. Use `tolerance=0` only when entities are well-separated.
- **Corpses decay after 150 ticks** (15 seconds). If you need to check corpses after combat, keep the tick count low.
- **Queens are slow** (speed 30 vs ant speed 400). Place queens close to their target in founding tests.
- **Simulation runs at 10 ticks/sec.** Multiply seconds by 10 to estimate tick counts. A 5 DPS ant kills a 20 HP target in 4 seconds = 40 ticks.
