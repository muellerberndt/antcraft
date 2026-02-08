# AntCraft

P2P multiplayer real-time strategy game built with PyGame. Players control ant colonies, managing resources, building structures, and commanding units in real time.

## Tech Stack

- **Language:** Python 3.12
- **Game engine:** PyGame
- **Networking:** P2P lockstep over UDP

## Project Structure

```
antcraft/
├── CLAUDE.md              # This file — project context for AI agents
├── AGENTS.md              # Guidelines for AI coding agents
├── README.md
├── requirements.txt       # Python dependencies
├── specs/                 # Game design specs (source of truth)
│   ├── game_mechanics.md  # All game rules and mechanics
│   └── balance.md         # Unit stats, costs, economy parameters
├── src/
│   ├── config.py          # All game constants
│   ├── main.py            # Entry point (CLI args)
│   ├── game.py            # Game loop, tick scheduling
│   ├── simulation/        # Deterministic game logic (no PyGame)
│   │   ├── state.py       # GameState, Entity, EntityType, EntityState
│   │   ├── tick.py        # Per-tick simulation (movement, commands)
│   │   ├── commands.py    # Command types and processing
│   │   ├── combat.py      # Auto-attack, death, corpse decay
│   │   ├── harvest.py     # Corpse harvesting, jelly carry/deposit
│   │   ├── hive.py        # Spawn, merge queen, found hive, income
│   │   ├── wildlife.py    # Wildlife spawning and aggro AI
│   │   ├── pathfinding.py # A* on tile grid
│   │   ├── tilemap.py     # Tile map and procedural generation
│   │   └── visibility.py  # Fog of war
│   ├── networking/        # P2P lockstep protocol
│   │   ├── peer.py        # Peer interface
│   │   ├── udp_peer.py    # UDP implementation
│   │   ├── protocol.py    # Lockstep sync, hash checks
│   │   └── serialization.py
│   ├── rendering/         # PyGame drawing
│   │   ├── renderer.py    # Map, entities, fog overlay
│   │   ├── camera.py      # Scrollable camera
│   │   └── hud.py         # Minimap, resource bar, selection panel
│   ├── input/             # Player input
│   │   ├── handler.py     # Hotkeys, right-click context commands
│   │   └── selection.py   # Click/box selection
│   └── audio/             # (not yet implemented)
├── tests/
│   ├── scenario.py        # Scenario test harness
│   ├── test_simulation/   # Unit tests for simulation subsystems
│   └── test_scenarios/    # High-level gameplay scenario tests
└── docs/
    ├── manual.md
    ├── hotkeys.md
    ├── simulation.md
    └── testing.md
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
# Local single-player test
python -m src.main --local

# Host multiplayer
python -m src.main --host 23456

# Join multiplayer
python -m src.main --join <HOST_IP>:23456
```

## Development Commands

```bash
# Run the game (local mode)
python -m src.main --local

# Run all tests
python -m pytest tests/ -v

# Run only scenario tests
python -m pytest tests/test_scenarios/ -v

# Run only unit tests
python -m pytest tests/test_simulation/ -v
```

## Game Design

All game mechanics are defined in `specs/game_mechanics.md` and `specs/balance.md`. These are the source of truth — always consult them before implementing or modifying gameplay systems.

Key mechanics:
- **Jelly** is the single resource. It comes from passive hive income and harvesting corpses (killed ants/wildlife). There are no map pickups.
- **Ants** are the versatile base unit. They fight, harvest, and can morph into queens or spitters.
- **Spitter ants** are ranged combat specialists morphed from ants at a hive (irreversible, cannot harvest or merge).
- **Queens** are created by merging ants at a hive. Their only purpose is to found new hives at hive sites.
- **Hives** spawn ants, generate passive jelly income, and are the win condition (lose all hives = eliminated).
- **Wildlife** (aphids, beetles, mantis) are NPCs that drop jelly-bearing corpses when killed.

## Testing

Every change must go through this checklist:

1. **Unit tests** — add/update tests in `tests/test_simulation/` for the subsystem changed.
2. **Scenario tests** — add/update end-to-end tests in `tests/test_scenarios/` using the `Scenario` harness (`tests/scenario.py`).
3. **Regression** — re-run affected scenario tests: `python -m pytest tests/test_scenarios/ -v`.
4. **Balance** — if stats/costs/income changed, run scenario tests to verify no dominant strategy emerges.
5. **Full suite** — `python -m pytest tests/ -v` must pass with zero failures.

See `AGENTS.md` for scenario harness API reference and tips.

## Architecture Notes

- **Deterministic simulation:** All game logic uses integer math (no floats). Positions are in milli-tiles (1 tile = 1000 milli-tiles). The simulation ticks at 10 Hz.
- **Lockstep P2P:** Both peers run identical simulations. Only player commands are sent over the network. Commands execute 2 ticks in the future. State hashes are compared every 10 ticks to detect desync.
- **Separation of concerns:** `src/simulation/` is pure logic with no PyGame dependency. `src/rendering/` and `src/input/` handle display and player interaction. Tests exercise simulation directly.
- **Entity system:** All game objects (ants, queens, hives, wildlife, corpses, hive sites) are `Entity` dataclass instances in a flat list on `GameState`. Each has an `EntityType`, `EntityState`, position, HP, speed, damage, etc.
- **Command system:** Player inputs are converted to `Command` objects (MOVE, STOP, HARVEST, ATTACK, SPAWN_ANT, MERGE_QUEEN, FOUND_HIVE, MORPH_SPITTER). Commands are the only way to mutate game state.
