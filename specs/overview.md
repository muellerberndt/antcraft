# AntCraft — Game Design & Architecture Overview

## Game Concept

AntCraft is a 1v1 real-time strategy game where each player controls an ant colony. Players gather food, build structures, raise armies of specialized ants, and wage war to destroy the opponent's nest.

- **Perspective:** Top-down 2D
- **Players:** 2 (P2P, no server)
- **Match length:** ~15–20 minutes
- **Depth:** Mid-complexity — tech tree with meaningful choices, multiple unit types, but not overwhelming

## High-Level Architecture

```
┌─────────────────────────────────────────────────┐
│                   Game Client                    │
│                                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────┐ │
│  │  Rendering   │  │   Input     │  │  Audio   │ │
│  │  (PyGame)    │  │  Handler    │  │          │ │
│  └──────┬───────┘  └──────┬──────┘  └──────────┘ │
│         │                 │                       │
│         │    ┌────────────▼──────────────┐        │
│         │    │     Command Queue         │        │
│         │    │  (player inputs → cmds)   │        │
│         │    └────────────┬──────────────┘        │
│         │                 │                       │
│  ┌──────▼─────────────────▼──────────────┐       │
│  │       Deterministic Simulation        │       │
│  │  (game state, logic, fixed-tick)      │       │
│  │  ┌──────────────────────────────┐     │       │
│  │  │  Entities · Map · Pathfinding │    │       │
│  │  │  Resources · Combat · AI      │    │       │
│  │  └──────────────────────────────┘     │       │
│  └───────────────────┬───────────────────┘       │
│                      │                            │
│         ┌────────────▼──────────────┐             │
│         │    Networking Layer        │             │
│         │  (P2P lockstep protocol)  │             │
│         └────────────┬──────────────┘             │
└──────────────────────┼────────────────────────────┘
                       │
                   UDP/TCP
                       │
               ┌───────▼───────┐
               │  Other Peer   │
               └───────────────┘
```

### Layer Responsibilities

| Layer | Responsibility | Deterministic? |
|-------|---------------|----------------|
| **Rendering** | Draws game state to screen via PyGame. Interpolates between ticks for smooth visuals. | No |
| **Input** | Captures mouse/keyboard, converts to commands. | No |
| **Command Queue** | Buffers commands, tags them with tick number. | Yes |
| **Simulation** | Advances game state one tick at a time. All game logic lives here. | **Yes — critical** |
| **Networking** | Exchanges commands with peer, runs lockstep synchronization. | N/A |

### Deterministic Lockstep Model

Both peers run an identical simulation. Instead of syncing game state, they sync **inputs only**:

1. Player actions become **commands** (move unit, build structure, attack).
2. Each command is tagged with the **tick number** it should execute on.
3. Both peers exchange commands for tick N.
4. Once both peers have all commands for tick N, both advance the simulation.
5. Periodic **state hashes** detect desync (if hashes diverge, something is non-deterministic).

This means:
- **All simulation code must be deterministic** — no floats in game logic, no random() without shared seed, no dict iteration order dependencies.
- Integer/fixed-point math for positions, health, damage, timers.
- Shared PRNG with synchronized seed for any randomness.

## Technology

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.12 | Performance improvements, mature ecosystem |
| Rendering / Input / Audio | PyGame 2.x | Simple 2D game framework, good for prototyping |
| Networking | Python `socket` (UDP) | Low-latency, lockstep doesn't need TCP reliability for commands |
| Serialization | `struct` or msgpack | Compact binary command encoding |
| Testing | pytest | Standard Python testing |
| Math | Integer arithmetic | Determinism for P2P sync |

## Module Structure

```
src/
├── main.py              # Entry point, PyGame init
├── game.py              # Top-level game loop, state machine
├── config.py            # Constants (screen size, tick rate, colors)
├── simulation/
│   ├── state.py         # GameState — the complete simulation state
│   ├── commands.py      # Command types and command queue
│   ├── tick.py          # Tick logic — advance simulation by one step
│   ├── entities.py      # Entity system (units, buildings)
│   ├── map.py           # Tile map, terrain
│   ├── pathfinding.py   # A* pathfinding
│   ├── combat.py        # Damage, health, attack resolution
│   └── resources.py     # Food economy
├── networking/
│   ├── peer.py          # P2P connection management
│   ├── protocol.py      # Lockstep protocol, message types
│   └── serialization.py # Command encoding/decoding
├── rendering/
│   ├── renderer.py      # Main draw loop
│   ├── camera.py        # Viewport, scrolling
│   ├── hud.py           # UI overlay (resources, minimap, selection)
│   └── effects.py       # Visual effects (pheromone trails, etc.)
├── input/
│   ├── handler.py       # Mouse/keyboard → commands
│   └── selection.py     # Unit selection logic
└── audio/
    └── manager.py       # Sound effects, music (Phase 4)

tests/
├── test_simulation/     # Mirrors src/simulation/
├── test_networking/     # Protocol and serialization tests
└── conftest.py          # Shared fixtures
```

## Development Phases

1. **[Phase 1: Core + Networking](phase1-core-and-networking.md)** — Deterministic game loop, command system, P2P lockstep. Milestone: two players moving placeholder ants.
2. **[Phase 2: Game Engine](phase2-engine.md)** — Tile map, pathfinding, selection, resources, fog of war.
3. **[Phase 3: Units & Buildings](phase3-units-and-buildings.md)** — Ant types, structures, tech tree, combat.
4. **[Phase 4: Iteration](phase4-iteration.md)** — Playtesting, bots, balance, polish.

## Collaboration Workflow

AntCraft is built by two developers. The work is split along a natural boundary: **simulation/logic** vs **networking/rendering/UI**.

### Roles

| | Dev A — Simulation | Dev B — Networking & Presentation |
|---|---|---|
| **Phase 1** | Game loop, GameState, commands, tick logic | UDP peer, lockstep protocol, serialization |
| **Phase 2** | Map, pathfinding, resources, fog of war, entities | Camera, renderer, HUD, minimap, selection, input |
| **Phase 3** | Combat, production, tech tree, unit behaviors | Build menu, production UI, effects, attack visuals |
| **Phase 4** | Bots, balance testing, stat tuning | Audio, visual polish, UX improvements, performance |

### Git Workflow

```
main (always working / playable)
 ├── phase1/simulation    (Dev A)
 ├── phase1/networking    (Dev B)
 ├── phase2/map-pathfinding  (Dev A)
 ├── phase2/rendering-input  (Dev B)
 └── ...
```

1. **Interface-first**: at the start of each phase, both devs agree on shared interfaces (dataclasses, ABCs) in a small shared PR. Both branch from there.
2. **Feature branches**: each dev works on their own branch, named `phaseN/feature-name`.
3. **Mock-driven development**: Dev A tests with mock networking (loopback). Dev B tests with mock simulation data (hardcoded state).
4. **Integration PRs**: when both sides are ready, merge into a shared integration branch, test together, then merge to `main`.
5. **PR reviews**: every PR gets reviewed by the other dev before merge.

### Integration Testing

After each phase integration:
- Run the game with two instances on localhost.
- Play for 5+ minutes — verify no desync.
- Run the full test suite.
- Check that the phase's "Done Criteria" are all met.

### Communication

- Keep a shared list of "interface changes" — if you need to modify a shared type (Command, Entity, GameState), notify the other dev immediately.
- Short daily sync (~5 min): what did you do, what's next, any blockers.
- Playtest together at least once per phase.
