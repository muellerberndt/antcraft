# AntCraft

P2P multiplayer real-time strategy game built with PyGame. Players control ant colonies, managing resources, building structures, and commanding units in real time.

## Tech Stack

- **Language:** Python 3.12
- **Game engine:** PyGame
- **Networking:** P2P multiplayer (protocol TBD)

## Project Structure

```
antcraft/
├── CLAUDE.md          # This file — project context for AI agents
├── AGENTS.md          # Guidelines for AI coding agents
├── README.md
├── requirements.txt   # Python dependencies
└── src/               # Game source code (TBD)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running

```bash
python -m src.main    # (once implemented)
```

## Development Commands

```bash
# Run the game
python -m src.main

# Run tests
python -m pytest tests/

# Lint
python -m flake8 src/
```

## Game Design

All game mechanics are defined in `specs/game_mechanics.md` and `specs/balance.md`. These are the source of truth — always consult them before implementing or modifying gameplay systems.

Key mechanics:
- **Jelly** is the single resource. It comes from passive hive income and harvesting corpses (killed ants/wildlife). There are no map pickups.
- **Ants** are the only unit. They fight, harvest, and merge into queens.
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

- This is a real-time strategy game — game loop timing and frame-rate independence matter.
- P2P networking means no authoritative server; synchronization and determinism are key concerns.
- PyGame handles rendering, input, and audio.
