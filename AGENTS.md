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

## File Organization

- `src/` — all game source code.
- `tests/` — mirrors `src/` structure.
- `assets/` — sprites, sounds, maps (tracked via Git LFS if large).

## Commit Practices

- Small, focused commits with clear messages.
- Don't commit generated files, caches, or virtual environments.
